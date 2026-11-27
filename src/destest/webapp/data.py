"""Data access for the web app: CMEs, their submissions and dashboards, cached.

Results are read from the folder `RESULTS_DIR` (environment variable
`DESTEST_RESULTS`, default `Result data` in the working directory or else at
the repository root), one
sub-folder per CME (`CME_DHN_1`, ...). Loaded submissions are cached and
reloaded automatically when a file in the CME folder changes, so adding a
result file and refreshing the page is enough.

Files that do not pass `destest check` are not shown; they are listed in
`CmeData.skipped` with the reason.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..analysis import Dashboard, build_dashboard
from ..data_check.validate import DATA_TYPE
from ..results import Submission, load_submission
from ..specs import list_cme_specs, load_cme_spec
from ..specs.schema import CmeSpec

#: `Result data` at the repository root (src/destest/webapp/data.py -> parents[3]).
REPO_RESULTS = Path(__file__).resolve().parents[3] / "Result data"


def results_dir() -> Path:
    """Folder with one sub-folder per CME.

    `DESTEST_RESULTS` if set; otherwise `Result data` in the working directory,
    or, if there is none (e.g. app.py run from its own folder), the one at the
    repository root.
    """
    if env := os.environ.get("DESTEST_RESULTS"):
        return Path(env)
    local = Path("Result data")
    return local if local.is_dir() else REPO_RESULTS


@dataclass
class CmeData:
    """One CME: its spec, its valid submissions, and the files left out."""

    spec: CmeSpec
    submissions: list[Submission] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (file name, reason)

    @property
    def name(self) -> str:
        """E.g. `CME_DHN_1`."""
        return self.spec.folder_name

    def by_id(self, ids: list[str] | None) -> list[Submission]:
        """The submissions with these ids, in the given order (unknown ids ignored)."""
        index = {s.id: s for s in self.submissions}
        return [index[i] for i in ids or [] if i in index]


Stamp = tuple[tuple[str, int, int], ...]
_cache: dict[str, tuple[Stamp, CmeData]] = {}


def _stamp(folder: Path) -> Stamp:
    """The files of a folder with their size and change time: changes when any file does."""
    if not folder.is_dir():
        return ()
    files = sorted(p for p in folder.iterdir() if p.is_file())
    return tuple((p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in files)


def cme_names() -> list[str]:
    """CMEs that have a spec file with an `analysis` section, e.g. `['CME_DHN_1']`."""
    out: list[str] = []
    for name in list_cme_specs():
        _, series, number = name.split("_")
        if load_cme_spec(series, int(number)).analysis is not None:
            out.append(name)
    return out


def get_cme(name: str) -> CmeData:
    """The CME and its valid submissions (cached; reloaded when the folder changes)."""
    _, series, number = name.split("_")
    folder = results_dir() / name
    stamp = _stamp(folder)
    cached = _cache.get(name)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    data = CmeData(load_cme_spec(series, int(number)))
    for path in sorted(folder.glob(f"{DATA_TYPE}_*")) if folder.is_dir() else []:
        try:
            data.submissions.append(load_submission(path, require_valid=True))
        except ValueError as exc:
            data.skipped.append((path.name, str(exc)))
    data.submissions.sort(key=lambda s: s.label.lower())
    _cache[name] = (stamp, data)
    return data


def submission_options(name: str) -> list[dict[str, str]]:
    """Dropdown options (label, value = submission id) of a CME."""
    return [{"label": s.label, "value": s.id} for s in get_cme(name).submissions]


def dashboard(name: str, kind: str, ids: list[str] | None = None) -> Dashboard:
    """Build a dashboard of a CME; `ids` are the submissions to show (detail, comparison)."""
    data = get_cme(name)
    focus = data.by_id(ids) if kind != "overview" else None
    return build_dashboard(data.spec, data.submissions, kind, focus)
