"""Check that result-file names follow the DESTEST naming convention.

Example:

    >>> from destest.filename_check import check_name
    >>> result = check_name(
    ...     "ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv"
    ... )
    >>> result.ok
    True
    >>> result.values["series"], result.values["exercise_number"]
    ('DHN', 1)

Every problem found is recorded as an `Issue` (level `error` or `warning`,
see `destest.result`).
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

from ..result import CheckResult
from . import convention as conv
from .convention import Field

PathLike = str | Path

#: Files and folders skipped when checking a folder (shell-style patterns).
DEFAULT_IGNORE: tuple[str, ...] = (".*", "desktop.ini", "Thumbs.db", "~$*")

#: A real extension: a dot followed by letters/digits at the very end, e.g. ".csv".
#: (A plain Path.suffix would treat ".4_TUD_..." in "TRNSYS_18.4_TUD_..." as an extension.)
_EXTENSION = re.compile(r"\.([A-Za-z][A-Za-z0-9]{0,9})$")


# --------------------------------------------------------------------------
# Result objects
# --------------------------------------------------------------------------
@dataclass
class NameCheck(CheckResult):
    """Outcome of checking one file name (see `destest.result.CheckResult`)."""

    name: str
    path: Path | None = None
    extension: str = ""
    values: dict[str, Any] = field(default_factory=dict)


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
    head = conv.head_fields()  # data type, DESTEST_CME, series, exercise number
    sep = conv.SEPARATOR

    def head_token(k: int) -> str:
        """The text at the place of head field k (several parts for DESTEST_CME)."""
        return sep.join(tokens[starts[k] : starts[k] + head[k].n_tokens])

    # 1. Fixed markers (DESTEST_CME) and listed values in the wrong place.
    #    Either means the parts are shifted, so report it once and stop
    #    instead of listing a dozen follow-up errors. (A marker in the wrong
    #    case is not a shift; it is reported precisely in step 3.)
    starts = [sum(f.n_tokens for f in head[:k]) for k in range(len(head))]
    bad_marker = next(
        (
            k
            for k, f in enumerate(head)
            if f.kind == "literal" and head_token(k).lower() != f.allowed[0].lower()
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
        found = sep.join(tokens[: sum(f.n_tokens for f in head)])
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

    # 4. Extension, which depends on the data type.
    data_type = result.values.get(conv.DATA_TYPE_KEY)
    allowed = conv.EXTENSIONS.get(data_type, ()) if isinstance(data_type, str) else ()
    if not ext:
        hint = f" ({', '.join(allowed)} for {data_type})" if allowed else ""
        result.add("error", "extension", f"File has no extension{hint}.")
    elif allowed and ext.lower() not in allowed:
        result.add(
            "error",
            "extension",
            f"Extension '{ext}' is not allowed for {data_type} files; use {', '.join(allowed)}.",
        )
    return result


# ---- field checkers ------------------------------------------------------
def _check_literal(f: Field, part: list[str], r: NameCheck, now: datetime | None) -> None:
    tok = conv.SEPARATOR.join(part)
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
        if int(tok) < f.min_value:
            r.add("error", f.key, f"{f.label} must be at least {f.min_value} (found '{tok}').")
            return
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
    bad = sorted(set(tok) & conv.FORBIDDEN_CHARS)
    if bad:
        r.add(
            "error",
            f.key,
            f"{f.label} '{tok}' contains characters not allowed in file names: {' '.join(bad)}",
        )
        return
    r.values[f.key] = tok
    if conv.WARN_ON_SPACES and any(ch.isspace() for ch in tok):
        r.add("warning", f.key, f"{f.label} '{tok}' contains spaces; prefer '-' or CamelCase.")
    # A version without any digit usually means the parts have shifted, e.g. a
    # missing version plus a '_' in the tool name: 'Modelica_Buildings_AAU_...'.
    if f.warn_if_no_digit and not any(ch.isdigit() for ch in tok):
        r.add(
            "warning",
            f.key,
            f"{f.label} '{tok}' contains no digit - is a part missing, "
            f"or does an earlier part contain '{conv.SEPARATOR}'?",
        )
    if f.warn_if_no_letter and not any(ch.isalpha() for ch in tok):
        r.add("warning", f.key, f"{f.label} '{tok}' contains no letter - are parts shifted?")


def _check_timestamp(f: Field, part: list[str], r: NameCheck, now: datetime | None) -> None:
    problems = [
        f"{unit} must be {width} digits (found '{tok}')"
        for tok, (unit, width) in zip(part, f.timestamp_parts, strict=True)
        if not (len(tok) == width and tok.isdigit())
    ]
    if problems:
        detail = "; ".join(problems)
        r.add("error", f.key, f"{f.label}: {detail}. Expected {f.placeholder}.")
        return
    given = {unit: tok for tok, (unit, _) in zip(part, f.timestamp_parts, strict=True)}
    parts = {"year": "1", "month": "1", "day": "1", "hour": "0", "minute": "0", "second": "0"}
    parts.update(given)
    try:
        n = {unit: int(v) for unit, v in parts.items()}
        dt = datetime(n["year"], n["month"], n["day"], n["hour"], n["minute"], n["second"])
    except ValueError as exc:
        p = {**{"year": "?", "month": "?", "day": "?"}, **parts}
        shown = f"{p['year']}-{p['month']}-{p['day']} {p['hour']}:{p['minute']}:{p['second']}"
        r.add("error", f.key, f"{f.label} {shown} is not a valid date/time ({exc}).")
        return
    r.values[f.key] = dt
    if f.warn_if_future_hours is None:
        return
    now = now or datetime.now()
    if dt > now + timedelta(hours=f.warn_if_future_hours):
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
    """Check that a file in a `CME_<Series>_<Number>` folder has the same series and number.

    Files in folders with other names are not checked here.
    """
    if result.path is None or not conv.FOLDER_MUST_MATCH:
        return result
    folder = result.path.parent.name
    m = re.match(conv.FOLDER_PATTERN, folder)
    if not m:
        return result
    got = [result.values.get(k) for k in conv.FOLDER_KEYS]
    if any(v is None for v in got):
        return result  # already reported as a name error
    want = [m[k] for k in conv.FOLDER_KEYS]
    if [str(v) for v in got] != [str(int(w)) if w.isdigit() else w for w in want]:
        says = " ".join(str(v) for v in got)
        result.add(
            "error",
            "folder",
            f"File is in folder '{folder}' but its name says {says}. "
            "Move the file or correct the name.",
        )
    return result


# --------------------------------------------------------------------------
# Pairing: data file <-> metadata file
# --------------------------------------------------------------------------
def partner_names(result: NameCheck) -> list[str]:
    """Possible names of the partner file (metadata for data, data for metadata).

    Same name, other data type, one entry per extension allowed for that type.
    Empty if the name is not valid or its data type has no partner.
    """
    data_type = result.values.get(conv.DATA_TYPE_KEY)
    if not result.ok or not isinstance(data_type, str):
        return []
    partner = next((b if data_type == a else a for a, b in conv.PAIRS if data_type in (a, b)), None)
    if partner is None:
        return []
    stem, _ = split_extension(result.name)
    tokens = stem.split(conv.SEPARATOR)
    at = 0
    for f in conv.FIELDS:  # position of the data type in the name
        if f.key == conv.DATA_TYPE_KEY:
            break
        at += f.n_tokens
    tokens[at] = partner
    new_stem = conv.SEPARATOR.join(tokens)
    return [new_stem + ext for ext in conv.EXTENSIONS[partner]]


def check_pairing(result: NameCheck) -> NameCheck:
    """Check that the partner file is in the same folder.

    A data file without its metadata file gets an issue at the level set in
    `naming_convention.yaml` (`pairing.severity`); a metadata file without its
    data file gets a warning. Only files on disk with a valid name are checked.
    """
    if result.path is None:
        return result
    names = partner_names(result)
    if not names or any((result.path.parent / n).is_file() for n in names):
        return result
    data_type = result.values[conv.DATA_TYPE_KEY]
    is_data = any(data_type == a for a, _ in conv.PAIRS)
    if is_data:
        result.add(
            conv.PAIRING_SEVERITY,
            "pairing",
            f"No matching metadata file: expected '{names[0]}' in the same folder.",
        )
    else:
        result.add(
            "warning",
            "pairing",
            f"No matching data file: expected '{names[0]}' in the same folder.",
        )
    return result


# --------------------------------------------------------------------------
# Several files
# --------------------------------------------------------------------------
def _ignored(name: str, ignore: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in ignore)


def check_files(paths: Iterable[PathLike], now: datetime | None = None) -> list[NameCheck]:
    """Check the names of the given files, the folder they are in, and their partner file."""
    out = []
    for p in paths:
        path = Path(p)
        res = check_name(path.name, now=now)
        res.path = path
        out.append(check_pairing(check_location(res)))
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
