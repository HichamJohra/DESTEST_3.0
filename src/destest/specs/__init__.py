"""The DESTEST spec files: the rules every check reads, stored as YAML.

```text
specs/
├── naming_convention.yaml     file-name rules, shared by all CMEs
├── result_metadata.yaml       sections of a ResultMetadata file, shared by all CMEs
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

from .schema import CmeSpec, MetadataField, NamingConvention, ResultMetadataLayout

__all__ = [
    "CmeSpec",
    "NamingConvention",
    "ResultMetadataLayout",
    "SpecError",
    "cme_spec_path",
    "list_cme_specs",
    "load_cme_spec",
    "load_cme_spec_file",
    "load_naming_convention",
    "load_naming_convention_file",
    "load_result_metadata_layout",
    "load_result_metadata_layout_file",
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
