"""The DESTEST spec files: the rules every check reads, stored as YAML.

```text
specs/
├── naming_convention.yaml     file-name rules, shared by all CMEs
├── result_metadata.yaml       sections of a ResultMetadata file, shared by all CMEs
├── locations.yaml             coordinates of cities, for the map of contributions
└── cme/
    └── CME_DHN_1.yaml         content rules for one CME (one file per CME)
```

```python
from destest.specs import load_naming_convention, load_cme_spec, list_cme_specs

conv = load_naming_convention()          # -> NamingConvention
layout = load_result_metadata_layout()   # -> ResultMetadataLayout
spec = load_cme_spec("DHN", 1)           # -> CmeSpec
list_cme_specs()                         # -> ["CME_DHN_1", ...]
```

Each file is checked when it is loaded (see `schema.py`). Problems are raised as
`SpecError`, with one line per problem naming the file and the place in it.
New CME: copy `cme/CME_DHN_1.yaml` to `cme/CME_<Series>_<Number>.yaml` and edit it.
"""

from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from .schema import CmeSpec, Locations, MetadataField, NamingConvention, ResultMetadataLayout

__all__ = [
    "CmeSpec",
    "Locations",
    "NamingConvention",
    "ResultMetadataLayout",
    "SpecError",
    "cme_spec_path",
    "list_cme_specs",
    "load_cme_spec",
    "load_cme_spec_file",
    "load_locations",
    "load_locations_file",
    "load_naming_convention",
    "load_naming_convention_file",
    "load_result_metadata_layout",
    "load_result_metadata_layout_file",
    "locations_path",
    "naming_convention_path",
    "result_metadata_layout_path",
]

_Model = TypeVar("_Model", bound=BaseModel)


class SpecError(ValueError):
    """A spec file is missing, is not valid YAML, or breaks the rules in `schema.py`."""


def _spec_dir() -> Path:
    return Path(str(files("destest.specs")))


def naming_convention_path() -> Path:
    """Path of the packaged `naming_convention.yaml`."""
    return _spec_dir() / "naming_convention.yaml"


def locations_path() -> Path:
    """Path of the packaged `locations.yaml`."""
    return _spec_dir() / "locations.yaml"


def load_locations_file(path: Path) -> Locations:
    """Load and check a locations file (any path)."""
    return _parse(Locations, _read_yaml(path), path)


@cache
def load_locations() -> Locations:
    """The packaged locations (loaded once, then cached)."""
    return load_locations_file(locations_path())


def result_metadata_layout_path() -> Path:
    """Path of the packaged `result_metadata.yaml`."""
    return _spec_dir() / "result_metadata.yaml"


def cme_spec_path(series: str, exercise_number: int) -> Path:
    """Path of the packaged spec file of one CME, e.g. `.../cme/CME_DHN_1.yaml`."""
    return _spec_dir() / "cme" / f"CME_{series}_{exercise_number}.yaml"


def list_cme_specs() -> list[str]:
    """Names of the CMEs that have a spec file, e.g. `['CME_DHN_1']`."""
    return sorted(p.stem for p in (_spec_dir() / "cme").glob("CME_*.yaml"))


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise SpecError(f"Spec file not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise SpecError(f"{path.name} is not valid YAML:\n{exc}") from exc


def _location(loc: tuple[int | str, ...]) -> str:
    """('fields', 3, 'text', 'label') -> 'fields[3].label' (drops the union tag)."""
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        elif part not in {"choice", "literal", "integer", "text", "timestamp"}:
            out += f".{part}" if out else str(part)
    return out or "(top level)"


def _parse(model: type[_Model], data: Any, path: Path) -> _Model:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        lines = [f"{path.name}: {exc.error_count()} problem(s)"]
        for err in exc.errors():
            lines.append(f"  - {_location(err['loc'])}: {err['msg']}")
        raise SpecError("\n".join(lines)) from exc


def load_naming_convention_file(path: Path) -> NamingConvention:
    """Load and check a naming-convention file (any path)."""
    return _parse(NamingConvention, _read_yaml(path), path)


def _raise_if(problems: list[str], path: Path) -> None:
    if problems:
        head = f"{path.name}: {len(problems)} problem(s)"
        raise SpecError("\n".join([head, *(f"  - {p}" for p in problems)]))


def _bad_must_match(fields: list[MetadataField], where: str, conv: NamingConvention) -> list[str]:
    """`must_match` values that are neither a naming field nor a special target."""
    allowed = {f.key for f in conv.fields} | {"cme", "result_data_file"}
    return [
        f"{where}.{f.key}.must_match: '{f.must_match}' is not a field of the naming convention "
        "nor 'cme' / 'result_data_file'"
        for f in fields
        if f.must_match is not None and f.must_match not in allowed
    ]


def _check_analysis(spec: CmeSpec) -> list[str]:
    """Names in the `analysis` section that the analysis code does not know."""
    if spec.analysis is None:
        return []
    # imported here: avoids an import cycle (the analysis code imports the specs)
    from ..analysis.context import item_keys
    from ..analysis.general_comparison import GENERAL_FUNCTIONS
    from ..analysis.point_by_point_comparison import POINT_METRICS, all_time_series_metrics
    from ..analysis.visuals import VISUALS

    problems: list[str] = []
    for g in spec.analysis.general_comparison:
        where = f"analysis.general_comparison.{g.key}"
        f = GENERAL_FUNCTIONS.get(g.function)
        if f is None:
            known = ", ".join(sorted(GENERAL_FUNCTIONS))
            problems.append(f"{where}.function: unknown '{g.function}' (known: {known})")
            continue
        given = set(g.columns_by_input)
        missing = sorted(set(f.inputs) - given)
        extra = sorted(given - set(f.inputs) - set(f.optional_inputs))
        if missing:
            problems.append(f"{where}: '{g.function}' needs the input(s) {', '.join(missing)}")
        if extra:
            problems.append(f"{where}: '{g.function}' has no input {', '.join(extra)}")
        extra = sorted(set(g.params) - f.parameters)
        if extra:
            problems.append(f"{where}.params: '{g.function}' has no parameter {', '.join(extra)}")
        missing = sorted(f.required_parameters - set(g.params))
        if missing:
            problems.append(f"{where}.params: '{g.function}' needs {', '.join(missing)}")
    pbp = spec.analysis.point_by_point_comparison
    if pbp is not None:
        usable = (all_time_series_metrics() if pbp.time_series is not None else {}) | (
            POINT_METRICS if pbp.data_profiles else {}
        )
        for m in pbp.metric_choices:
            where = f"analysis.point_by_point_comparison.metrics.{m.name}"
            metric = usable.get(m.name)
            if metric is None:
                problems.append(f"{where}: unknown metric (known: {', '.join(usable)})")
                continue
            extra = sorted(set(m.params) - (metric.parameters - {"time"}))
            if extra:
                problems.append(f"{where}.params: '{m.name}' has no parameter {', '.join(extra)}")
            if pbp.data_profiles and m.name not in POINT_METRICS:
                problems.append(f"{where}: a time-series metric cannot be used on data profiles")
    items = set(item_keys(spec))
    columns = {c.key for c in spec.result_data.columns}
    for kind in ("overview", "detail", "comparison"):
        for i, panel in enumerate(getattr(spec.analysis.dashboards, kind)):
            where = f"analysis.dashboards.{kind}[{i}]"
            v = VISUALS.get(panel.visual)
            if v is None:
                known = ", ".join(sorted(VISUALS))
                problems.append(f"{where}.visual: unknown '{panel.visual}' (known: {known})")
                continue
            extra = sorted(set(panel.options) - v.options)
            if extra:
                names = ", ".join(extra)
                problems.append(f"{where}.options: '{panel.visual}' has no option {names}")
            for opt, known_keys, what in [
                *((o, items, "compared item") for o in v.item_options),
                *((o, columns, "column") for o in v.column_options),
            ]:
                value = panel.options.get(opt)
                given_names = [value] if isinstance(value, str) else list(value or [])
                special = {"all", "general", "aggregates"} if what == "compared item" else {"all"}
                bad = [n for n in given_names if n not in special and n not in known_keys]
                if bad:
                    problems.append(f"{where}.options.{opt}: not a {what} key: {', '.join(bad)}")
    return problems


def load_result_metadata_layout_file(
    path: Path, convention: NamingConvention | None = None
) -> ResultMetadataLayout:
    """Load and check a result-metadata layout file (any path)."""
    layout = _parse(ResultMetadataLayout, _read_yaml(path), path)
    conv = convention or load_naming_convention()
    problems: list[str] = []
    for s in layout.sections:
        problems += _bad_must_match(s.fields, s.name, conv)
    _raise_if(problems, path)
    return layout


def load_cme_spec_file(path: Path, convention: NamingConvention | None = None) -> CmeSpec:
    """Load and check a CME spec file (any path), also against the shared spec files."""
    spec = _parse(CmeSpec, _read_yaml(path), path)
    conv = convention or load_naming_convention()
    problems: list[str] = []
    if spec.cme.series not in conv.series:
        problems.append(f"cme.series: '{spec.cme.series}' is not in the naming convention")
    if path.stem != spec.folder_name:
        problems.append(f"file name: should be {spec.folder_name}.yaml to match 'cme'")
    meta = spec.result_metadata
    for name in ("simulation_config", "model_details"):
        problems += _bad_must_match(getattr(meta, name), f"result_metadata.{name}", conv)
    problems += _check_analysis(spec)
    _raise_if(problems, path)
    return spec


@cache
def load_naming_convention() -> NamingConvention:
    """The packaged naming convention (loaded once, then cached)."""
    return load_naming_convention_file(naming_convention_path())


@cache
def load_result_metadata_layout() -> ResultMetadataLayout:
    """The packaged result-metadata layout (loaded once, then cached)."""
    return load_result_metadata_layout_file(result_metadata_layout_path())


@cache
def load_cme_spec(series: str, exercise_number: int) -> CmeSpec:
    """The packaged spec of one CME (loaded once, then cached)."""
    return load_cme_spec_file(cme_spec_path(series, exercise_number))
