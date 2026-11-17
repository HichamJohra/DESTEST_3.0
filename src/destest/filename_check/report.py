"""Present naming-check results: a readable text report and a CSV export."""

import csv
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from . import convention as conv
from .validate import NameCheck, PathLike

_STATUS = {"ok": "OK  ", "warning": "WARN", "error": "FAIL"}


def _display_name(c: NameCheck, base: Path | None) -> str:
    if c.path is not None and base is not None:
        try:
            return str(c.path.relative_to(base))
        except ValueError:
            pass
    return c.name


def summary(checks: Sequence[NameCheck]) -> str:
    """One-line summary, e.g. `Summary: 5 valid, 1 with errors - 6 files checked.`"""
    n = len(checks)
    if n == 0:
        return "No files to check."
    n_ok = sum(c.ok for c in checks)
    n_warn = sum(1 for c in checks if c.ok and c.warnings)
    valid = f"{n_ok} valid" + (f" ({n_warn} with warnings)" if n_warn else "")
    return f"Summary: {valid}, {n - n_ok} with errors - {n} file{'s' if n != 1 else ''} checked."


def format_report(
    checks: Sequence[NameCheck],
    base: Path | None = None,
    show_ok: bool = True,
    show_template: bool = True,
) -> str:
    """The full text report: one block per file, then the summary."""
    where = f' in "{base}"' if base is not None else ""
    lines = [f"Checking {len(checks)} file name{'s' if len(checks) != 1 else ''}{where}", ""]
    for c in checks:
        if c.status == "ok" and not show_ok:
            continue
        lines.append(f"[{_STATUS[c.status]}] {_display_name(c, base)}")
        lines.extend(f"         {i.level:<7} {i.message}" for i in c.errors + c.warnings)
    lines += ["", summary(checks)]
    if show_template and any(not c.ok for c in checks):
        lines += ["", "Expected: " + conv.template()]
    return "\n".join(lines)


def print_report(
    checks: Sequence[NameCheck],
    base: Path | None = None,
    stream: TextIO | None = None,
    show_ok: bool = True,
    show_template: bool = True,
) -> None:
    """Print `format_report()` to `stream` (default: standard output)."""
    text = format_report(checks, base=base, show_ok=show_ok, show_template=show_template)
    print(text, file=stream or sys.stdout)


def write_csv(checks: Sequence[NameCheck], path: PathLike, base: Path | None = None) -> Path:
    """Write one row per file: status, issues, and every field value that could be read."""
    out = Path(path)
    keys = [f.key for f in conv.FIELDS if f.kind != "literal"]
    with out.open("w", newline="", encoding="utf-8-sig") as fh:  # utf-8-sig opens cleanly in Excel
        w = csv.writer(fh)
        w.writerow(["file", "status", "errors", "warnings", "extension", *keys])
        for c in checks:
            vals = [
                v.strftime("%Y-%m-%d %H:%M:%S") if hasattr(v, "strftime") else v
                for v in (c.values.get(k, "") for k in keys)
            ]
            w.writerow(
                [
                    _display_name(c, base),
                    c.status,
                    " | ".join(i.message for i in c.errors),
                    " | ".join(i.message for i in c.warnings),
                    c.extension,
                    *vals,
                ]
            )
    return out
