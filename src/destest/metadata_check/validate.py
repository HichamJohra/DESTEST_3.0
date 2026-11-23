"""Check the content of a ResultMetadata file against the spec files.

Example:

    >>> from destest.metadata_check import check_metadata
    >>> result = check_metadata("Result data/CME_DHN_1/ResultMetadata_...yaml")  # doctest: +SKIP
    >>> result.ok, [str(i) for i in result.issues]  # doctest: +SKIP

What is checked (all from `specs/result_metadata.yaml` and the CME's spec file):

* the file name is a valid ResultMetadata name; its CME has a spec file;
* the file is valid YAML and a mapping of keys;
* `metadata_format_version` has the expected value;
* every section and every key is present (missing -> error), and no other key
  is there (unknown -> error);
* values are single values (text, number, date), not lists or sub-sections;
* required values are not empty;
* values marked `must_match` agree with the file name, the CME (folder) or the
  name of the paired ResultData file.
"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from ..filename_check import convention as conv
from ..filename_check.validate import check_location, check_name, partner_names
from ..result import CheckResult
from ..specs import SpecError, load_cme_spec, load_result_metadata_layout
from ..specs.schema import CmeSpec, MetadataField, ResultMetadataLayout

PathLike = str | Path

#: Data type of the files this module checks.
METADATA_TYPE = "ResultMetadata"


@dataclass
class MetadataCheck(CheckResult):
    """Outcome of checking one ResultMetadata file (see `destest.result.CheckResult`).

    Issue `field`s are places in the file, e.g. `modeller.first_name`.
    """

    path: Path

    @property
    def name(self) -> str:
        """File name."""
        return self.path.name


# --------------------------------------------------------------------------
# Expected layout
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Section:
    """One section of a ResultMetadata file, as expected for one CME."""

    name: str
    kind: str  # "fields" (a group of keys) or "text" (one value)
    fields: tuple[MetadataField, ...] = ()
    required: bool = False  # kind "text"
    description: str = ""  # kind "text"


def expected_sections(spec: CmeSpec, layout: ResultMetadataLayout | None = None) -> list[Section]:
    """The sections of a ResultMetadata file for one CME, in file order."""
    layout = layout or load_result_metadata_layout()
    out: list[Section] = []
    for s in layout.sections:
        if s.kind == "text":
            out.append(Section(s.name, "text", required=s.required, description=s.description))
        else:
            fields = s.fields if s.kind == "fields" else getattr(spec.result_metadata, s.name)
            out.append(Section(s.name, "fields", tuple(fields)))
    return out


# --------------------------------------------------------------------------
# Checking
# --------------------------------------------------------------------------
def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_single(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool | date)


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _check_match(
    r: MetadataCheck, where: str, value: Any, target: str, expected: dict[str, Any]
) -> None:
    want = expected.get(target)
    if want is None or _is_empty(value):
        return  # nothing to compare with, or already reported as empty
    if isinstance(want, datetime):
        got = _as_datetime(value)
        if got != want:
            r.add(
                "error",
                where,
                f"'{value}' does not match the file name ({want:%Y-%m-%d %H:%M:%S}).",
            )
        return
    if str(value).strip() != str(want):
        hint = ""
        if not isinstance(value, str):
            hint = ' Write the value in quotes, e.g. "18.40", so it is read as text.'
        source = {"cme": "the CME (folder)", "result_data_file": "the ResultData file name"}
        r.add(
            "error",
            where,
            f"'{value}' does not match {source.get(target, 'the file name')} ('{want}').{hint}",
        )


def _check_section(
    r: MetadataCheck, s: Section, data: dict[str, Any], expected: dict[str, Any]
) -> None:
    if s.name not in data:
        r.add("error", s.name, f"Section '{s.name}' is missing.")
        return
    value = data[s.name]
    if s.kind == "text":
        if not _is_single(value):
            r.add("error", s.name, f"'{s.name}' must be text, not a list or sub-section.")
        elif s.required and _is_empty(value):
            r.add("error", s.name, f"'{s.name}' is required and must not be empty.")
        return
    if not isinstance(value, dict):
        keys = ", ".join(f.key for f in s.fields)
        r.add("error", s.name, f"'{s.name}' must be a group of keys: {keys}.")
        return
    known = {f.key for f in s.fields}
    for f in s.fields:
        where = f"{s.name}.{f.key}"
        if f.key not in value:
            r.add("error", where, f"Key '{f.key}' is missing in '{s.name}'.")
            continue
        v = value[f.key]
        if not _is_single(v):
            r.add("error", where, "Must be a single value (text), not a list or sub-section.")
        elif f.required and _is_empty(v):
            r.add("error", where, "Required value is empty.")
        elif f.must_match:
            _check_match(r, where, v, f.must_match, expected)
    for k in value:
        if k not in known:
            r.add("error", f"{s.name}.{k}", f"Unknown key '{k}' in '{s.name}'.")


def check_metadata_data(
    data: Any,
    spec: CmeSpec,
    expected: dict[str, Any],
    path: PathLike = "metadata.yaml",
    layout: ResultMetadataLayout | None = None,
) -> MetadataCheck:
    """Check already-loaded YAML content for one CME.

    `expected` holds the values the `must_match` fields are compared with: the
    parts of the file name (by naming-field key), `cme` and `result_data_file`.
    """
    layout = layout or load_result_metadata_layout()
    r = MetadataCheck(Path(path))
    if not isinstance(data, dict):
        r.add("error", "file", "The file must contain keys and values (it is empty or a list).")
        return r
    version = data.get("metadata_format_version")
    if "metadata_format_version" not in data:
        r.add("error", "metadata_format_version", "Key 'metadata_format_version' is missing.")
    elif version != layout.format_version:
        r.add(
            "error",
            "metadata_format_version",
            f"Must be {layout.format_version} (found {version!r}): use the current template.",
        )
    sections = expected_sections(spec, layout)
    for s in sections:
        _check_section(r, s, data, expected)
    known = {"metadata_format_version", *(s.name for s in sections)}
    for k in data:
        if k not in known:
            r.add("error", str(k), f"Unknown section or key '{k}'.")
    return r


def check_metadata(path: PathLike) -> MetadataCheck:
    """Check one ResultMetadata file: its name, then its content against the specs."""
    p = Path(path)
    r = MetadataCheck(p)
    name = check_name(p.name)
    name.path = p
    check_location(name)
    if not name.ok:
        problems = " ".join(i.message for i in name.errors)
        r.add("error", "file name", f"The file name is not valid: {problems}")
        return r
    values = name.values
    if values.get(conv.DATA_TYPE_KEY) != METADATA_TYPE:
        r.add("error", "file name", f"Not a {METADATA_TYPE} file.")
        return r
    series, number = values.get("series"), values.get("exercise_number")
    try:
        spec = load_cme_spec(str(series), int(str(number)))
    except SpecError as exc:
        r.add("error", "spec", f"No valid spec for CME_{series}_{number}: {exc}")
        return r
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        r.add("error", "file", f"Not valid YAML: {exc}")
        return r
    except (OSError, UnicodeDecodeError) as exc:
        r.add("error", "file", f"Cannot read the file: {exc}")
        return r
    partners = partner_names(name)
    expected: dict[str, Any] = {
        **values,
        "cme": spec.folder_name,
        "result_data_file": partners[0] if partners else None,
    }
    checked = check_metadata_data(data, spec, expected, path=p)
    r.issues += checked.issues
    return r


def check_metadata_folder(folder: PathLike, recursive: bool = True) -> list[MetadataCheck]:
    """Check every `ResultMetadata_*` file in a folder (and its sub-folders)."""
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")
    pattern = f"{METADATA_TYPE}_*"
    files = root.rglob(pattern) if recursive else root.glob(pattern)
    return [check_metadata(p) for p in sorted(f for f in files if f.is_file())]
