"""Check everything about submitted result files in one go.

For every file in a folder (and its sub-folders):

1. **name**: naming convention, folder, and the data/metadata pairing
   (`destest.filename_check`);
2. **content**, if the name is valid:
   ResultData files against `result_data` of their CME spec (`destest.data_check`),
   ResultMetadata files against the metadata layout (`destest.metadata_check`).

    >>> from destest.check import check_submissions
    >>> reports = check_submissions("Result data")  # doctest: +SKIP
    >>> all(r.ok for r in reports)  # doctest: +SKIP
"""

import contextlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from .data_check import check_data
from .data_check.validate import DATA_TYPE
from .filename_check import NameCheck, check_files, check_folder
from .filename_check import convention as conv
from .metadata_check import check_metadata
from .metadata_check.validate import METADATA_TYPE
from .result import CheckResult, Issue

PathLike = str | Path


@dataclass
class FileReport(CheckResult):
    """Everything found about one file (see `destest.result.CheckResult`).

    Each issue's `stage` says which check found it: `name` or `content`.
    """

    path: Path
    data_type: str | None = None


def _staged(stage: str, issues: list[Issue]) -> list[Issue]:
    return [replace(i, stage=stage) for i in issues]


def _report(name: NameCheck) -> FileReport:
    assert name.path is not None
    data_type = name.values.get(conv.DATA_TYPE_KEY)
    r = FileReport(name.path, data_type if isinstance(data_type, str) else None)
    r.issues += _staged("name", name.issues)
    if not name.ok:
        return r  # the content can only be checked once the name is right
    if r.data_type == DATA_TYPE:
        r.issues += _staged("content", check_data(name.path).issues)
    elif r.data_type == METADATA_TYPE:
        r.issues += _staged("content", check_metadata(name.path).issues)
    return r


def check_submissions(folder: PathLike) -> list[FileReport]:
    """Check every file in a folder and its sub-folders: name, pairing and content."""
    return [_report(n) for n in check_folder(folder, recursive=True)]


def check_submission_files(paths: Sequence[PathLike]) -> list[FileReport]:
    """Check the given files: name, pairing and content."""
    return [_report(n) for n in check_files(paths)]


def format_reports(
    reports: Sequence[FileReport], base: Path | None = None, show_ok: bool = True
) -> str:
    """Text report: one block per file, then a summary."""
    labels = {"ok": "OK  ", "warning": "WARN", "error": "FAIL"}
    lines = [f"Checking {len(reports)} file{'s' if len(reports) != 1 else ''}", ""]
    for r in reports:
        if r.status == "ok" and not show_ok:
            continue
        shown = r.path
        if base is not None:
            with contextlib.suppress(ValueError):  # not under base: show the full path
                shown = r.path.relative_to(base)
        lines.append(f"[{labels[r.status]}] {shown}")
        for i in r.errors + r.warnings:
            lines.append(f"         {i.level:<7} {i.stage}/{i.field}: {i.message}")
    n_err = sum(not r.ok for r in reports)
    n_warn = sum(1 for r in reports if r.ok and r.warnings)
    counts = {t: sum(r.data_type == t for r in reports) for t in (DATA_TYPE, METADATA_TYPE)}
    kinds = ", ".join(f"{n} {t}" for t, n in counts.items())
    lines += [
        "",
        f"Summary: {len(reports) - n_err} valid ({n_warn} with warnings), "
        f"{n_err} with errors - {len(reports)} files checked ({kinds}).",
    ]
    return "\n".join(lines)
