"""The DESTEST result-file naming convention, as read from the spec file.

The rules are no longer written in Python: they live in
`src/destest/specs/naming_convention.yaml`. This module loads that file once
(checking it on the way, see `destest.specs`) and exposes it in the form the
checker (`validate.py`), the name builder (`build.py`) and the reports use.
Change the YAML file to change the convention; nothing here needs editing.

Current convention:

    <DataType>_DESTEST_CME_<Series>_<Number>_<ModellingTool>_<ToolVersion>_<Institution>_<FirstName>_<LastName>_<YYYY>_<MM>_<DD>_<hh>_<mm>_<ss>.<ext>

Example:

    ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv

with a matching `ResultMetadata_DESTEST_CME_..._.yaml` file for the metadata.
"""

import re
import string
from dataclasses import dataclass

from ..specs import load_naming_convention
from ..specs.schema import (
    TIMESTAMP_CODES,
    ChoiceField,
    IntegerField,
    LiteralField,
    NameField,
    NamingConvention,
    TextField,
    TimestampField,
)

#: The loaded spec file (`specs/naming_convention.yaml`).
SPEC: NamingConvention = load_naming_convention()

#: Character that separates the parts of a file name.
SEPARATOR: str = SPEC.separator

#: Exercise series: code -> description.
SERIES: dict[str, str] = dict(SPEC.series)

#: Data types: name -> description.
DATA_TYPES: dict[str, str] = {k: v.description for k, v in SPEC.data_types.items()}

#: Allowed file extensions per data type (lower case, with dot).
EXTENSIONS: dict[str, tuple[str, ...]] = {
    k: tuple(v.extensions) for k, v in SPEC.data_types.items()
}

#: Characters not allowed in a free-text part (on top of the separator).
FORBIDDEN_CHARS: frozenset[str] = frozenset(SPEC.text_rules.forbidden_characters)

#: Warn when a free-text part contains spaces.
WARN_ON_SPACES: bool = SPEC.text_rules.warn_on_spaces


@dataclass(frozen=True)
class Field:
    """One part of the file name, in the form the checker uses.

    `kind` is one of `literal`, `choice`, `integer`, `text`, `timestamp`
    (see `naming_convention.yaml` for what each means).
    """

    key: str
    label: str
    kind: str
    allowed: tuple[str, ...] = ()  # choice: the list; literal: the fixed text
    placeholder: str = ""
    min_value: int = 0  # integer
    timestamp_parts: tuple[tuple[str, int], ...] = ()  # timestamp: (unit, digits) in order
    timestamp_format: str = ""  # timestamp: strftime format
    warn_if_no_digit: bool = False  # text
    warn_if_no_letter: bool = False  # text
    warn_if_future_hours: float | None = None  # timestamp

    @property
    def n_tokens(self) -> int:
        """How many separator-delimited parts this field occupies."""
        if self.kind == "literal":
            return len(self.allowed[0].split(SEPARATOR))
        if self.kind == "timestamp":
            return len(self.timestamp_parts)
        return 1


def _to_field(f: NameField) -> Field:
    placeholder = f.placeholder or ""
    if isinstance(f, LiteralField):
        return Field(f.key, f.label, "literal", (f.value,), placeholder or f.value)
    placeholder = placeholder or f"<{f.key}>"
    if isinstance(f, ChoiceField):
        values = tuple(SPEC.data_types if f.from_ == "data_types" else SPEC.series)
        return Field(f.key, f.label, "choice", values, placeholder)
    if isinstance(f, IntegerField):
        return Field(f.key, f.label, "integer", placeholder=placeholder, min_value=f.min)
    if isinstance(f, TextField):
        return Field(
            f.key,
            f.label,
            "text",
            placeholder=placeholder,
            warn_if_no_digit=f.warn_if_no_digit,
            warn_if_no_letter=f.warn_if_no_letter,
        )
    assert isinstance(f, TimestampField)
    codes = f.format.split(SEPARATOR)
    return Field(
        f.key,
        f.label,
        "timestamp",
        placeholder=placeholder,
        timestamp_parts=tuple(TIMESTAMP_CODES[c] for c in codes),
        timestamp_format=f.format,
        warn_if_future_hours=f.warn_if_future_hours,
    )


#: The fields, in the order they appear in the file name.
FIELDS: tuple[Field, ...] = tuple(_to_field(f) for f in SPEC.fields)

#: Field keys, for convenience.
FIELD_KEYS: tuple[str, ...] = tuple(f.key for f in FIELDS)

#: Key of the field that holds the data type (decides the allowed extensions).
DATA_TYPE_KEY: str = next(
    f.key for f in SPEC.fields if isinstance(f, ChoiceField) and f.from_ == "data_types"
)

#: Folder rule: e.g. "CME_{series}_{exercise_number}", and whether it is checked.
FOLDER_TEMPLATE: str = SPEC.folder.pattern
FOLDER_KEYS: tuple[str, ...] = tuple(SPEC.folder.keys)
FOLDER_MUST_MATCH: bool = SPEC.folder.must_match_name


def _folder_regex() -> str:
    by_key = {f.key: f for f in FIELDS}
    out = "^"
    for literal, key, _, _ in string.Formatter().parse(FOLDER_TEMPLATE):
        out += re.escape(literal)
        if key:
            pat = r"\d+" if by_key[key].kind == "integer" else r"[A-Za-z0-9-]+"
            out += f"(?P<{key}>{pat})"
    return out + "$"


#: Regular expression matching a correct folder name, with one group per field.
FOLDER_PATTERN: str = _folder_regex()

#: Data and metadata types that must come in pairs, e.g. [("ResultData", "ResultMetadata")].
PAIRS: tuple[tuple[str, str], ...] = (
    tuple((p.data, p.metadata) for p in SPEC.pairing.pairs) if SPEC.pairing.required else ()
)

#: Level of the issue for a data file without its metadata file ("error" or "warning").
PAIRING_SEVERITY: str = SPEC.pairing.severity


def head_fields() -> tuple[Field, ...]:
    """The fields before the free-text block (data type, DESTEST_CME, series, number)."""
    out: list[Field] = []
    for f in FIELDS:
        if f.kind == "text":
            break
        out.append(f)
    return tuple(out)


def head_template() -> str:
    """Template of the start of a name, e.g. `<DataType>_DESTEST_CME_<Series>_<Number>`."""
    return SEPARATOR.join(f.placeholder for f in head_fields())


def template(extension: str = ".<ext>") -> str:
    """Human-readable template of a correct file name."""
    return SEPARATOR.join(f.placeholder for f in FIELDS) + extension


def folder_template() -> str:
    """The folder rule with placeholders, e.g. `CME_<Series>_<Number>`."""
    by_key = {f.key: f.placeholder for f in FIELDS}
    return FOLDER_TEMPLATE.format(**{k: by_key[k] for k in FOLDER_KEYS})


def expected_token_count() -> int:
    """Number of separator-delimited parts in a correct name (without extension)."""
    return sum(f.n_tokens for f in FIELDS)


def describe() -> str:
    """The rules as plain text, for the command line and the docs."""
    lines = ["DESTEST result-file naming convention", "", "  " + template(), ""]
    for f in FIELDS:
        if f.kind == "literal":
            rule = f"must be '{f.allowed[0]}'"
        elif f.kind == "choice":
            names = SERIES if set(f.allowed) <= set(SERIES) else DATA_TYPES
            rule = "one of: " + ", ".join(f"{v} ({names[v]})" for v in f.allowed)
        elif f.kind == "integer":
            rule = f"whole number >= {f.min_value}"
        elif f.kind == "text":
            rule = f"free text, not empty, no '{SEPARATOR}'"
        else:
            rule = f"valid date and time, {f.placeholder}"
        lines.append(f"  {f.placeholder:<32} {f.label}: {rule}")
    lines.append("")
    for dt, exts in EXTENSIONS.items():
        lines.append(f"  Extension of {dt} files: {', '.join(exts)}")
    lines.append(f"  Folder: {folder_template()}")
    for data, meta in PAIRS:
        lines.append(
            f"  Every {data} file needs a {meta} file with the same name "
            f"(else: {PAIRING_SEVERITY})."
        )
    return "\n".join(lines)
