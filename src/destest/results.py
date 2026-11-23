"""Load submitted results: one `Submission` per ResultData file (+ its metadata).

    >>> from destest.results import load_cme_submissions
    >>> subs = load_cme_submissions("Result data/CME_DHN_1")  # doctest: +SKIP
    >>> subs[0].label, subs[0].series["T_supply_i"][:3]  # doctest: +SKIP

The time series are stored by column key (from the CME spec), as lists of floats
(`None` for a missing value), so the analysis code never depends on how a column
is named in the CSV header.
"""

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .data_check import check_data
from .data_check.validate import DATA_TYPE
from .filename_check import check_name
from .filename_check import convention as conv
from .filename_check.validate import partner_names
from .specs import load_cme_spec
from .specs.schema import CmeSpec

PathLike = str | Path


@dataclass
class Submission:
    """One submitted result: its time series, name parts and metadata."""

    path: Path
    cme: str  # e.g. CME_DHN_1
    name_parts: dict[str, Any]
    series: dict[str, list[float | None]]  # column key -> values, in file order
    metadata: dict[str, Any] = field(default_factory=dict)  # {} if there is no metadata file

    @property
    def id(self) -> str:
        """Unique id: the file name without extension."""
        return self.path.stem

    @property
    def label(self) -> str:
        """Short readable label, e.g. `TRNSYS 2022 - C. Felsmann (TUD)`."""
        p = self.name_parts
        first = str(p.get("first_name", ""))[:1]
        return (
            f"{p.get('tool')} {p.get('tool_version')} - "
            f"{first}. {p.get('last_name')} ({p.get('institution')})"
        )

    @property
    def tick_label(self) -> str:
        """The label on three lines, for chart axes: tool + version, modeller, institution."""
        p = self.name_parts
        first = str(p.get("first_name", ""))[:1]
        return (
            f"{p.get('tool')} {p.get('tool_version')}<br>"
            f"{first}. {p.get('last_name')}<br>({p.get('institution')})"
        )


def _number(text: str, decimal: str, missing: set[str]) -> float | None:
    raw = text.strip()
    if raw in missing or text in missing:
        return None
    try:
        return float(raw.replace(decimal, ".") if decimal != "." else raw)
    except ValueError:
        return None


def read_series(path: Path, spec: CmeSpec) -> dict[str, list[float | None]]:
    """The columns of a ResultData file, by column key (columns found by header text)."""
    rd = spec.result_data
    text = path.read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=rd.file.delimiter))
    while rows and not any(cell.strip() for cell in rows[-1]):
        rows.pop()
    header = rows[rd.file.header_rows - 1] if rows else []
    data = rows[rd.file.header_rows :]
    missing = set(rd.column_defaults.missing_values)
    out: dict[str, list[float | None]] = {}
    for c in rd.columns:
        if c.header not in header:
            continue
        i = header.index(c.header)
        out[c.key] = [
            _number(row[i], rd.file.decimal, missing) if i < len(row) else None for row in data
        ]
    return out


def load_submission(path: PathLike, require_valid: bool = True) -> Submission:
    """Load one ResultData file and, if present, its ResultMetadata file.

    With `require_valid`, the data file must pass `check_data` (else `ValueError`).
    """
    p = Path(path)
    name = check_name(p.name)
    if not name.ok or name.values.get(conv.DATA_TYPE_KEY) != DATA_TYPE:
        raise ValueError(f"Not a valid ResultData file name: {p.name}")
    if require_valid:
        checked = check_data(p)
        if not checked.ok:
            problems = "; ".join(i.message for i in checked.errors)
            raise ValueError(f"{p.name} has content errors: {problems}")
    series_key, number = name.values["series"], name.values["exercise_number"]
    spec = load_cme_spec(str(series_key), int(number))
    metadata: dict[str, Any] = {}
    for partner in partner_names(name):
        mp = p.parent / partner
        if mp.is_file():
            loaded = yaml.safe_load(mp.read_text(encoding="utf-8-sig"))
            metadata = loaded if isinstance(loaded, dict) else {}
            break
    return Submission(
        path=p,
        cme=spec.folder_name,
        name_parts=dict(name.values),
        series=read_series(p, spec),
        metadata=metadata,
    )


def load_cme_submissions(folder: PathLike, require_valid: bool = True) -> list[Submission]:
    """Every ResultData file in a CME folder, sorted by label."""
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")
    subs = [load_submission(p, require_valid) for p in sorted(root.glob(f"{DATA_TYPE}_*"))]
    return sorted(subs, key=lambda s: s.label.lower())
