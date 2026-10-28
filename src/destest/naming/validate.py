"""Check that result-file names follow the DESTEST naming convention.

Example:

    >>> from destest.naming import check_name
    >>> result = check_name(
    ...     "ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv"
    ... )
    >>> result.ok
    True
    >>> result.values["series"], result.values["number"]
    ('DHN', 1)

Every problem found is recorded as an `Issue` (level `error` or `warning`).
A name is valid when it has no errors; warnings point at things that are
allowed but probably unintended (a leading zero, a date in the future, ...).
"""

import difflib
import fnmatch
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import convention as conv
from .convention import Field

PathLike = str | Path

#: Files and folders skipped when checking a folder (shell-style patterns).
DEFAULT_IGNORE: tuple[str, ...] = (".*", "desktop.ini", "Thumbs.db", "~$*")

#: Characters that are not allowed in Windows file names.
_FORBIDDEN_CHARS = set('<>:"/\\|?*')

#: A real extension: a dot followed by letters/digits at the very end, e.g. ".csv".
#: (A plain Path.suffix would treat ".4_TUD_..." in "TRNSYS_18.4_TUD_..." as an extension.)
_EXTENSION = re.compile(r"\.([A-Za-z][A-Za-z0-9]{0,9})$")


# --------------------------------------------------------------------------
# Result objects
# --------------------------------------------------------------------------
@dataclass
class Issue:
    """One problem found in a name."""

    level: str  # "error" or "warning"
    field: str  # Field.key, or "name" / "extension" / "folder"
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.message}"


@dataclass
class NameCheck:
    """Outcome of checking one file name."""

    name: str
    path: Path | None = None
    extension: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        """Problems that make the name invalid."""
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        """Things that are allowed but probably unintended."""
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        """True when the name follows the convention (warnings are allowed)."""
        return not self.errors

    @property
    def status(self) -> str:
        """`ok`, `warning` or `error`."""
        return "error" if self.errors else ("warning" if self.warnings else "ok")

    def add(self, level: str, key: str, message: str) -> None:
        """Record an issue."""
        self.issues.append(Issue(level, key, message))


# --------------------------------------------------------------------------
# Single name
# --------------------------------------------------------------------------
def split_extension(name: str) -> tuple[str, str]:
    """Split `stem.ext` into `(stem, ".ext")`; the extension is `""` if there is none."""
    m = _EXTENSION.search(name)
    if not m:
        return name, ""
    return name[: m.start()], m.group(0)


def check_name(name: str, now: datetime | None = None) -> NameCheck:
    """Check one file name against the convention.

    A path is accepted too (Windows or POSIX style); only its last part is checked.
    `now` is the reference time for the "time stamp in the future" warning.
    """
    name = re.split(r"[\\/]", name)[-1]
    stem, ext = split_extension(name)
    result = NameCheck(name=name, extension=ext)
    tokens = stem.split(conv.SEPARATOR)

    fields = conv.FIELDS
    head = conv.head_fields()  # data type, DESTEST, CME, series, number

    # 1. Fixed markers (DESTEST, CME) and listed values in the wrong place.
    #    Either means the parts are shifted, so report it once and stop
    #    instead of listing a dozen follow-up errors. (A marker in the wrong
    #    case is not a shift; it is reported precisely in step 3.)
    starts = [sum(f.n_tokens for f in head[:k]) for k in range(len(head))]
    bad_marker = next(
        (
            k
            for k, f in enumerate(head)
            if f.kind == "literal"
            and (tokens[starts[k]] if starts[k] < len(tokens) else "").lower()
            != f.allowed[0].lower()
        ),
        None,
    )
    # listed values are checked up to the first broken marker (or all, if none)
    limit = len(head) if bad_marker is None else bad_marker
    for k in range(limit):
        f = head[k]
        tok = tokens[starts[k]] if starts[k] < len(tokens) else ""
        if f.kind == "choice" and tok not in f.allowed:
            elsewhere = [t for j, t in enumerate(tokens) if t in f.allowed and j != starts[k]]
            if elsewhere:
                where = "first" if k == 0 else f"right after '{head[k - 1].placeholder}'"
                result.add(
                    "error",
                    f.key,
                    f"{f.label} '{elsewhere[0]}' is in the wrong place: it must come {where}. "
                    "Further checks skipped.",
                )
                return result
    if bad_marker is not None:
        sep = conv.SEPARATOR
        found = sep.join(tokens[: len(head)])
        result.add(
            "error",
            "name",
            f"Name must start with '{conv.head_template()}{sep}' "
            f"(found '{found}{sep}...'). Further checks skipped.",
        )
        return result

    # 2. Assign tokens to fields. Fields before the free-text block are read
    #    from the left, fields after it from the right; whatever is left in the
    #    middle belongs to the free-text fields. This pinpoints a '_' inside a
    #    tool or person name instead of shifting every later field by one.
    text_idx = [i for i, f in enumerate(fields) if f.kind == "text"]
    first_t, last_t = (text_idx[0], text_idx[-1]) if text_idx else (len(fields), len(fields) - 1)
    left = fields[:first_t]  # single-token fields before the free text
    middle = fields[first_t : last_t + 1]  # free-text fields
    right = fields[last_t + 1 :]  # time stamp
    n_left = sum(f.n_tokens for f in left)
    n_right = sum(f.n_tokens for f in right)
    n_mid = len(tokens) - n_left - n_right

    assigned: list[tuple[Field, list[str]]] = []
    pos = 0
    for f in left:
        part = tokens[pos : pos + f.n_tokens]
        pos += f.n_tokens
        if len(part) < f.n_tokens:
            result.add("error", f.key, f"{f.label} is missing.")
            continue
        assigned.append((f, part))

    if n_mid >= 0:
        rpos = len(tokens) - n_right
        for f in right:
            assigned.append((f, tokens[rpos : rpos + f.n_tokens]))
            rpos += f.n_tokens
    else:
        what = ", ".join(f.label.lower() for f in right)
        result.add(
            "error",
            "name",
            f"Name is too short: found {len(tokens)} parts separated by '{conv.SEPARATOR}', "
            f"expected {conv.expected_token_count()}. Cannot read the {what}.",
        )

    mid_tokens = tokens[n_left : n_left + max(n_mid, 0)]
    labels = ", ".join(f.label.lower() for f in middle)
    joined = conv.SEPARATOR.join(mid_tokens)
    if n_mid == len(middle):
        assigned.extend((f, [t]) for f, t in zip(middle, mid_tokens, strict=True))
    elif n_mid > len(middle):
        result.add(
            "error",
            "name",
            f"Found {n_mid} parts where {len(middle)} are expected ({labels}): '{joined}'. "
            f"One of these probably contains '{conv.SEPARATOR}' - use '-' or CamelCase instead.",
        )
    elif n_mid >= 0:
        result.add(
            "error",
            "name",
            f"Found {n_mid} of the {len(middle)} free-text parts ({labels}): '{joined}'. "
            f"{len(middle) - n_mid} missing.",
        )

    # 3. Check each field, in name order.
    order = {f.key: i for i, f in enumerate(fields)}
    for f, part in sorted(assigned, key=lambda fp: order[fp[0].key]):
        _CHECKERS[f.kind](f, part, result, now)

    # 4. Extension.
    if not ext:
        result.add("warning", "extension", "File has no extension (e.g. '.csv').")
    elif conv.ALLOWED_EXTENSIONS is not None and ext.lower() not in conv.ALLOWED_EXTENSIONS:
        allowed = ", ".join(conv.ALLOWED_EXTENSIONS)
        result.add("error", "extension", f"Extension '{ext}' is not allowed; use one of {allowed}.")
    return result


# ---- field checkers ------------------------------------------------------
def _check_literal(f: Field, part: list[str], r: NameCheck, now: datetime | None) -> None:
    tok = part[0]
    if tok == f.allowed[0]:
        r.values[f.key] = tok
    elif tok.lower() == f.allowed[0].lower():
        r.add("error", f.key, f"{f.label} must be written '{f.allowed[0]}' (found '{tok}').")
    else:
        r.add("error", f.key, f"{f.label} '{f.allowed[0]}' expected here (found '{tok}').")


def _check_choice(f: Field, part: list[str], r: NameCheck, now: datetime | None) -> None:
    tok = part[0]
    if tok in f.allowed:
        r.values[f.key] = tok
        return
    if not tok:
        r.add("error", f.key, f"{f.label} is empty.")
        return
    same_case = [a for a in f.allowed if a.lower() == tok.lower()]
    if same_case:
        r.add("error", f.key, f"{f.label} must be written '{same_case[0]}' (found '{tok}').")
        return
    close = difflib.get_close_matches(tok, f.allowed, n=1, cutoff=0.6)
    hint = f" Did you mean '{close[0]}'?" if close else ""
    allowed = ", ".join(f.allowed)
    r.add("error", f.key, f"{f.label} '{tok}' is not in the list ({allowed}).{hint}")


def _check_integer(f: Field, part: list[str], r: NameCheck, now: datetime | None) -> None:
    tok = part[0]
    if not tok:
        r.add("error", f.key, f"{f.label} is empty.")
    elif re.fullmatch(r"[0-9]+", tok):
        r.values[f.key] = int(tok)
        if len(tok) > 1 and tok.startswith("0"):
            r.add("warning", f.key, f"{f.label} '{tok}' has a leading zero; write '{int(tok)}'.")
    else:
        r.add("error", f.key, f"{f.label} must be a whole number (found '{tok}').")


def _check_text(f: Field, part: list[str], r: NameCheck, now: datetime | None) -> None:
    tok = part[0]
    if not tok:
        r.add("error", f.key, f"{f.label} is empty (two '{conv.SEPARATOR}' in a row?).")
        return
    bad = sorted(set(tok) & _FORBIDDEN_CHARS)
    if bad:
        r.add(
            "error",
            f.key,
            f"{f.label} '{tok}' contains characters not allowed in file names: {' '.join(bad)}",
        )
        return
    r.values[f.key] = tok
    if any(ch.isspace() for ch in tok):
        r.add("warning", f.key, f"{f.label} '{tok}' contains spaces; prefer '-' or CamelCase.")
    # A version without any digit usually means the parts have shifted, e.g. a
    # missing version plus a '_' in the tool name: 'Modelica_Buildings_AAU_...'.
    if f.key == "tool_version" and not any(ch.isdigit() for ch in tok):
        r.add(
            "warning",
            f.key,
            f"{f.label} '{tok}' contains no digit - is a part missing, "
            f"or does the tool name contain '{conv.SEPARATOR}'?",
        )


def _check_timestamp(f: Field, part: list[str], r: NameCheck, now: datetime | None) -> None:
    problems = [
        f"{unit} must be {width} digits (found '{tok}')"
        for tok, (unit, width) in zip(part, conv.TIMESTAMP_PARTS, strict=True)
        if not (len(tok) == width and tok.isdigit())
    ]
    if problems:
        detail = "; ".join(problems)
        r.add("error", f.key, f"{f.label}: {detail}. Expected YYYY_MM_DD_hh_mm_ss.")
        return
    year, month, day, hour, minute, second = (int(t) for t in part)
    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        shown = "{}-{}-{} {}:{}:{}".format(*part)
        r.add("error", f.key, f"{f.label} {shown} is not a valid date/time ({exc}).")
        return
    r.values[f.key] = dt
    now = now or datetime.now()
    if dt > now + timedelta(hours=conv.FUTURE_TOLERANCE_HOURS):
        r.add("warning", f.key, f"{f.label} {dt:%Y-%m-%d %H:%M:%S} is in the future.")


_Checker = Callable[[Field, list[str], NameCheck, datetime | None], None]
_CHECKERS: dict[str, _Checker] = {
    "literal": _check_literal,
    "choice": _check_choice,
    "integer": _check_integer,
    "text": _check_text,
    "timestamp": _check_timestamp,
}


# --------------------------------------------------------------------------
# Location: file name vs. folder
# --------------------------------------------------------------------------
def check_location(result: NameCheck) -> NameCheck:
    """Check that a file in a `CME_<Series>_<Number>` folder has the same series and number."""
    if result.path is None:
        return result
    folder = result.path.parent.name
    m = re.match(conv.FOLDER_PATTERN, folder)
    if not m:
        return result
    want_series, want_number = m["series"], int(m["number"])
    got_series, got_number = result.values.get("series"), result.values.get("number")
    if got_series is None or got_number is None:
        return result  # already reported as a name error
    if (got_series, got_number) != (want_series, want_number):
        result.add(
            "error",
            "folder",
            f"File is in folder '{folder}' but its name says {got_series} {got_number}. "
            "Move the file or correct the name.",
        )
    return result


# --------------------------------------------------------------------------
# Several files
# --------------------------------------------------------------------------
def _ignored(name: str, ignore: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in ignore)


def check_files(paths: Iterable[PathLike], now: datetime | None = None) -> list[NameCheck]:
    """Check the names of the given files, including the folder they are in."""
    out = []
    for p in paths:
        path = Path(p)
        res = check_name(path.name, now=now)
        res.path = path
        out.append(check_location(res))
    return out


def check_folder(
    folder: PathLike,
    recursive: bool = False,
    ignore: Sequence[str] = DEFAULT_IGNORE,
    now: datetime | None = None,
) -> list[NameCheck]:
    """Check the names of all files in a folder (optionally including sub-folders).

    Raises `FileNotFoundError` or `NotADirectoryError` for a wrong folder.
    """
    root = Path(folder)
    if not root.exists():
        raise FileNotFoundError(f"Folder not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")
    candidates = root.rglob("*") if recursive else root.iterdir()
    paths = sorted(
        (
            p
            for p in candidates
            if p.is_file()
            and not _ignored(p.name, ignore)
            and not any(_ignored(part, ignore) for part in p.relative_to(root).parts[:-1])
        ),
        key=lambda p: str(p.relative_to(root)).lower(),
    )
    return check_files(paths, now=now)
