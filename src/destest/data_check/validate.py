"""Check the content of a ResultData (.csv) file against its CME spec file.

Example:

    >>> from destest.data_check import check_data
    >>> check_data("Result data/CME_DHN_1/ResultData_...csv").ok  # doctest: +SKIP

What is checked (all settings from `specs/cme/CME_<Series>_<Number>.yaml`, `result_data`):

* the file name is a valid ResultData name and its CME has a spec file;
* the file is readable text in the expected encoding;
* header: every column present, with the exact name and in the right order (`header`);
* rows: number of data rows (`rows`), every row with as many cells as the header;
* values: numbers where numbers are expected, missing values (`column_defaults`);
* time column: start, step, strictly increasing (`time`);
* plausible ranges per column (`range`, `on_out_of_range`);
* rules across columns, row by row (`consistency`).

Problems in one column are reported once, with a count and the first row concerned.
Row numbers are line numbers in the file (the header is line 1).
"""

import csv
import io
import itertools
import math
from dataclasses import dataclass
from pathlib import Path

from ..filename_check import convention as conv
from ..filename_check.validate import check_location, check_name
from ..result import CheckResult
from ..specs import SpecError, load_cme_spec
from ..specs.expressions import check_rule, parse_rule
from ..specs.schema import CmeSpec, ColumnSpec, ResultDataSpec

PathLike = str | Path

#: Data type of the files this module checks.
DATA_TYPE = "ResultData"

#: Allowed difference between the time column and start + n * step.
_TIME_TOLERANCE = 1e-6


@dataclass
class DataCheck(CheckResult):
    """Outcome of checking one ResultData file (see `destest.result.CheckResult`).

    Issue `field`s are e.g. `header`, `rows`, `consistency` or a column key.
    """

    path: Path
    n_rows: int = 0

    @property
    def name(self) -> str:
        """File name."""
        return self.path.name


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
def _normalise(text: str, match: str) -> str:
    return "".join(text.lower().split()) if match == "ignore_case_and_spaces" else text


def _map_columns(r: DataCheck, header: list[str], rd: ResultDataSpec) -> dict[str, int]:
    """Column key -> index in the file, for the columns that were found."""
    match = rd.header.match
    found = [_normalise(h, match) for h in header]
    doubles = sorted({h for h in header if header.count(h) > 1})
    if doubles:
        r.add("error", "header", f"Column name used more than once: {', '.join(doubles)}.")
    index: dict[str, int] = {}
    for pos, c in enumerate(rd.columns):
        want = _normalise(c.header, match)
        at = found.index(want) if want in found else None
        if at is None:
            close = header[pos] if pos < len(header) else None
            hint = f" (found '{close}' at that place)" if close is not None else ""
            r.add("error", "header", f"Column {pos + 1} '{c.header}' is missing{hint}.")
            continue
        if rd.header.order == "strict" and at != pos:
            r.add("error", "header", f"Column '{c.header}' is column {at + 1}, expected {pos + 1}.")
        index[c.key] = at
    used = set(index.values())
    extra = [h for i, h in enumerate(header) if i not in used and h not in doubles]
    if extra:
        names = ", ".join(f"'{h}'" for h in extra)
        r.add(rd.header.extra_columns, "header", f"Column(s) not in the spec: {names}.")
    return index


# --------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------
def _to_number(text: str, decimal: str) -> float | None:
    raw = text.strip()
    if decimal != ".":
        raw = raw.replace(decimal, ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _fmt(value: float) -> str:
    return f"{value:.6g}"


def _check_column(
    r: DataCheck,
    c: ColumnSpec,
    cells: list[tuple[int, str]],
    rd: ResultDataSpec,
) -> list[tuple[int, float]]:
    """Check one column; return its numbers as (line, value)."""
    d = rd.column_defaults
    missing_set = set(d.missing_values)
    missing = [line for line, v in cells if v in missing_set or v.strip() in missing_set]
    n = len(cells)
    if n and len(missing) == n:
        r.add(d.all_missing, c.key, f"'{c.header}': no value at all.")
        return []
    max_fraction = c.max_missing_fraction
    if max_fraction is None:
        max_fraction = d.max_missing_fraction
    if missing and len(missing) > max_fraction * n:
        r.add(
            d.on_missing,
            c.key,
            f"'{c.header}': {len(missing)} missing value(s) of {n} (first: line {missing[0]}).",
        )
    if (c.type or d.type) == "text":
        return []
    numbers: list[tuple[int, float]] = []
    not_numbers: list[tuple[int, str]] = []
    missing_lines = set(missing)
    for line, v in cells:
        if line in missing_lines:
            continue
        x = _to_number(v, rd.file.decimal)
        if x is None:
            not_numbers.append((line, v))
        else:
            numbers.append((line, x))
    if not_numbers:
        line, v = not_numbers[0]
        r.add(
            "error",
            c.key,
            f"'{c.header}': {len(not_numbers)} value(s) are not numbers "
            f"(first: line {line}, '{v}').",
        )
    if c.range is not None:
        lo, hi = c.range.min, c.range.max
        out = [
            (line, x)
            for line, x in numbers
            if (lo is not None and x < lo) or (hi is not None and x > hi)
        ]
        if out:
            line, x = out[0]
            limits = f"[{'' if lo is None else _fmt(lo)}, {'' if hi is None else _fmt(hi)}]"
            r.add(
                rd.on_out_of_range,
                c.key,
                f"'{c.header}': {len(out)} value(s) outside {limits} "
                f"(first: line {line}, {_fmt(x)}).",
            )
    return numbers


Numbers = dict[str, list[tuple[int, float]]]  # column key -> (line, value)


def _check_time(r: DataCheck, rd: ResultDataSpec, numbers: Numbers) -> None:
    t = rd.time
    if t is None or t.column not in numbers or not numbers[t.column]:
        return
    values = numbers[t.column]
    where = t.column
    if t.start is not None and abs(values[0][1] - t.start) > _TIME_TOLERANCE:
        found = _fmt(values[0][1])
        r.add("error", where, f"Time must start at {_fmt(t.start)} {t.unit} (found {found}).")
    if t.strictly_increasing:
        bad = [(a, b) for a, b in itertools.pairwise(values) if b[1] <= a[1]]
        if bad:
            line = bad[0][1][0]
            r.add(
                "error",
                where,
                f"Time is not strictly increasing ({len(bad)} time(s), first: line {line}).",
            )
    if t.step is not None:
        steps = itertools.pairwise(values)
        off = [b for a, b in steps if abs(b[1] - a[1] - t.step) > _TIME_TOLERANCE]
        if off:
            line, x = off[0]
            r.add(
                "error",
                where,
                f"Time step must be {_fmt(t.step)} {t.unit} ({len(off)} step(s) differ, "
                f"first: line {line}, time {_fmt(x)}).",
            )


def _check_consistency(r: DataCheck, rd: ResultDataSpec, numbers: Numbers) -> None:
    by_line: dict[int, dict[str, float]] = {}
    for key, values in numbers.items():
        for line, x in values:
            by_line.setdefault(line, {})[key] = x
    for c in rd.consistency:
        rule = parse_rule(c.expression)
        if not rule.names <= numbers.keys():
            continue  # a column is missing: already reported
        failures = []
        for line in sorted(by_line):
            row = by_line[line]
            if not rule.names <= row.keys():
                continue  # a value is missing in this row: already reported
            outcome = check_rule(rule, row, c.tolerance_relative or 0.0)
            if not outcome.ok:
                failures.append((line, outcome))
        if failures:
            line, o = failures[0]
            detail = f"{_fmt(o.left)} vs {_fmt(o.right)}"
            if rule.op == "≈" and o.right:
                detail += f", {abs(o.left - o.right) / abs(o.right):.2%} apart"
            r.add(
                c.severity,
                "consistency",
                f"{c.name}: fails in {len(failures)} row(s) (first: line {line}, {detail}).",
            )


# --------------------------------------------------------------------------
# One file
# --------------------------------------------------------------------------
def check_data_text(text: str, spec: CmeSpec, path: PathLike = "data.csv") -> DataCheck:
    """Check the text of a ResultData file against a CME spec."""
    rd = spec.result_data
    r = DataCheck(Path(path))
    rows = list(csv.reader(io.StringIO(text), delimiter=rd.file.delimiter))
    while rows and not any(cell.strip() for cell in rows[-1]):
        rows.pop()  # blank lines at the end
    if len(rows) < rd.file.header_rows:
        r.add("error", "file", "The file is empty or has no header.")
        return r
    header = rows[rd.file.header_rows - 1]
    data = rows[rd.file.header_rows :]
    first_line = rd.file.header_rows + 1
    r.n_rows = len(data)

    index = _map_columns(r, header, rd)

    n = len(data)
    if n < rd.rows.min:
        r.add("error", "rows", f"{n} data row(s); at least {rd.rows.min} needed.")
    if rd.rows.max is not None and n > rd.rows.max:
        r.add("error", "rows", f"{n} data rows; at most {rd.rows.max} allowed.")
    elif rd.rows.expected is not None and n != rd.rows.expected and n >= rd.rows.min:
        r.add("warning", "rows", f"{n} data row(s); {rd.rows.expected} expected.")
    short = [first_line + i for i, row in enumerate(data) if len(row) != len(header)]
    if short:
        r.add(
            "error",
            "rows",
            f"{len(short)} row(s) do not have {len(header)} cells like the header "
            f"(first: line {short[0]}).",
        )

    numbers: Numbers = {}
    for c in rd.columns:
        if c.key not in index:
            continue
        col = index[c.key]
        cells = [(first_line + i, row[col] if col < len(row) else "") for i, row in enumerate(data)]
        numbers[c.key] = _check_column(r, c, cells, rd)

    _check_time(r, rd, numbers)
    _check_consistency(r, rd, numbers)
    return r


def check_data(path: PathLike) -> DataCheck:
    """Check one ResultData file: its name, then its content against its CME spec."""
    p = Path(path)
    r = DataCheck(p)
    name = check_name(p.name)
    name.path = p
    check_location(name)
    if not name.ok:
        problems = " ".join(i.message for i in name.errors)
        r.add("error", "file name", f"The file name is not valid: {problems}")
        return r
    if name.values.get(conv.DATA_TYPE_KEY) != DATA_TYPE:
        r.add("error", "file name", f"Not a {DATA_TYPE} file.")
        return r
    series, number = name.values.get("series"), name.values.get("exercise_number")
    try:
        spec = load_cme_spec(str(series), int(str(number)))
    except SpecError as exc:
        r.add("error", "spec", f"No valid spec for CME_{series}_{number}: {exc}")
        return r
    encoding = spec.result_data.file.encoding
    if encoding.lower().replace("_", "-") == "utf-8":
        encoding = "utf-8-sig"  # accept a byte-order mark (Excel)
    try:
        text = p.read_text(encoding=encoding)
    except UnicodeDecodeError:
        r.add("error", "file", f"The file is not {spec.result_data.file.encoding} text.")
        return r
    except OSError as exc:
        r.add("error", "file", f"Cannot read the file: {exc}")
        return r
    checked = check_data_text(text, spec, path=p)
    r.issues += checked.issues
    r.n_rows = checked.n_rows
    return r


def check_data_folder(folder: PathLike, recursive: bool = True) -> list[DataCheck]:
    """Check every `ResultData_*` file in a folder (and its sub-folders)."""
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")
    pattern = f"{DATA_TYPE}_*"
    files = root.rglob(pattern) if recursive else root.glob(pattern)
    return [check_data(p) for p in sorted(f for f in files if f.is_file())]
