"""The schema of the YAML spec files: their allowed layout, as pydantic models.

Loading a YAML file through these models checks it: a misspelt key, a missing
value or a wrong type stops with a message that names the place in the file
(see `destest.specs.SpecError`). Two files are described here:

- `naming_convention.yaml` -> `NamingConvention` (one file for all CMEs)
- `cme/CME_<Series>_<Number>.yaml` -> `CmeSpec` (one file per CME)

To add a new setting to a YAML file, add it to the matching model first;
unknown keys are rejected so that typos do not pass silently.
"""

import re
import string
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Severity = Literal["error", "warning"]

#: Codes allowed in a time-stamp `format`, with the datetime part and digit count.
TIMESTAMP_CODES: dict[str, tuple[str, int]] = {
    "%Y": ("year", 4),
    "%m": ("month", 2),
    "%d": ("day", 2),
    "%H": ("hour", 2),
    "%M": ("minute", 2),
    "%S": ("second", 2),
}

_KEY = r"^[A-Za-z][A-Za-z0-9_]*$"  # keys are used as Python identifiers in code and reports


class _Strict(BaseModel):
    """Base for every model: unknown keys are errors, objects are read-only."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# =============================================================================
# naming_convention.yaml
# =============================================================================
class DataTypeSpec(_Strict):
    """One data type, e.g. `ResultData`."""

    description: str
    extensions: list[str] = Field(min_length=1)

    @field_validator("extensions")
    @classmethod
    def _dot_and_lower_case(cls, v: list[str]) -> list[str]:
        for ext in v:
            if not re.fullmatch(r"\.[a-z0-9]+", ext):
                raise ValueError(f"'{ext}': write extensions in lower case with a dot, e.g. '.csv'")
        return v


class _FieldBase(_Strict):
    key: str = Field(pattern=_KEY)
    label: str
    placeholder: str | None = None


class ChoiceField(_FieldBase):
    """A part that must be one of the values of a list (`data_types` or `series`)."""

    kind: Literal["choice"]
    from_: Literal["data_types", "series"] = Field(alias="from")


class LiteralField(_FieldBase):
    """Fixed text, e.g. `DESTEST_CME`. May contain the separator (then spans several parts)."""

    kind: Literal["literal"]
    value: str = Field(min_length=1)


class IntegerField(_FieldBase):
    """A whole number."""

    kind: Literal["integer"]
    min: int = 0


class TextField(_FieldBase):
    """Free text, not empty, without the separator."""

    kind: Literal["text"]
    warn_if_no_digit: bool = False
    warn_if_no_letter: bool = False


class TimestampField(_FieldBase):
    """Date and time, written with `format` (strftime codes joined by the separator)."""

    kind: Literal["timestamp"]
    format: str
    warn_if_future_hours: float | None = None


NameField = Annotated[
    ChoiceField | LiteralField | IntegerField | TextField | TimestampField,
    Field(discriminator="kind"),
]


class TextRules(_Strict):
    """Rules for every free-text part."""

    forbidden_characters: str = ""
    warn_on_spaces: bool = True


class FolderRule(_Strict):
    """Name of the folder a file must be in, e.g. `CME_{series}_{exercise_number}`."""

    pattern: str
    must_match_name: bool = True

    @property
    def keys(self) -> list[str]:
        """The `{field}` names used in the pattern."""
        return [name for _, name, _, _ in string.Formatter().parse(self.pattern) if name]


class Pair(_Strict):
    """A data file type and the metadata file type that must go with it."""

    data: str
    metadata: str


class PairingRule(_Strict):
    """Which data files need a metadata file with the same name."""

    required: bool = True
    severity: Severity = "error"  # for a data file without its metadata file
    pairs: list[Pair] = Field(default_factory=list)


class NamingConvention(_Strict):
    """Contents of `naming_convention.yaml`."""

    schema_version: Literal[1]
    separator: str = Field(min_length=1, max_length=1)
    data_types: dict[str, DataTypeSpec] = Field(min_length=1)
    series: dict[str, str] = Field(min_length=1)
    fields: list[NameField] = Field(min_length=1)
    text_rules: TextRules = TextRules()
    folder: FolderRule
    pairing: PairingRule = PairingRule()

    @model_validator(mode="after")
    def _consistent(self) -> "NamingConvention":
        sep = self.separator
        keys = [f.key for f in self.fields]
        doubles = sorted({k for k in keys if keys.count(k) > 1})
        if doubles:
            raise ValueError(f"fields: key used more than once: {', '.join(doubles)}")
        for name in [*self.data_types, *self.series]:
            if sep in name or not name:
                raise ValueError(f"'{name}': list values must not be empty or contain '{sep}'")
        for f in self.fields:
            if isinstance(f, TimestampField):
                codes = f.format.split(sep)
                bad = [c for c in codes if c not in TIMESTAMP_CODES]
                if bad or len(set(codes)) != len(codes):
                    allowed = ", ".join(TIMESTAMP_CODES)
                    raise ValueError(
                        f"fields.{f.key}.format: use each of {allowed} at most once, "
                        f"joined by '{sep}' (found '{f.format}')"
                    )
        # The checker reads the free-text parts as one block between the fixed parts.
        text_at = [i for i, f in enumerate(self.fields) if isinstance(f, TextField)]
        if text_at and text_at != list(range(text_at[0], text_at[-1] + 1)):
            raise ValueError("fields: the 'text' fields must follow each other")
        if sum(isinstance(f, ChoiceField) and f.from_ == "data_types" for f in self.fields) != 1:
            raise ValueError("fields: exactly one field must be a choice 'from: data_types'")
        unknown = [k for k in self.folder.keys if k not in keys]
        if unknown:
            raise ValueError(f"folder.pattern: unknown field(s) {', '.join(unknown)}")
        for p in self.pairing.pairs:
            for t in (p.data, p.metadata):
                if t not in self.data_types:
                    raise ValueError(f"pairing.pairs: '{t}' is not in data_types")
        return self


# =============================================================================
# cme/CME_<Series>_<Number>.yaml
# =============================================================================
class CmeInfo(_Strict):
    """Which exercise the file describes."""

    series: str
    exercise_number: int = Field(ge=0)
    title: str
    status: Literal["draft", "active", "closed"] = "draft"


class Range(_Strict):
    """Plausible values; leave `min` or `max` out for no limit."""

    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "Range":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"min ({self.min}) is larger than max ({self.max})")
        return self


class CsvFormat(_Strict):
    """How the CSV file is written."""

    extension: str = ".csv"
    encoding: str = "utf-8"
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    decimal: str = Field(default=".", min_length=1, max_length=1)
    header_rows: int = Field(default=1, ge=1)


class RowRule(_Strict):
    """Number of data rows (header not counted)."""

    min: int = Field(default=1, ge=0)
    expected: int | None = None
    max: int | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "RowRule":
        values = [v for v in (self.min, self.expected, self.max) if v is not None]
        if values != sorted(values):
            raise ValueError("rows: need min <= expected <= max")
        return self


class HeaderRule(_Strict):
    """How strictly the header must match `columns`."""

    match: Literal["exact", "ignore_case_and_spaces"] = "exact"
    order: Literal["strict", "any"] = "strict"
    extra_columns: Literal["error", "warning", "ignore"] = "error"


class ColumnDefaults(_Strict):
    """Rules applied to every column unless the column overrides them."""

    type: Literal["number", "text"] = "number"
    missing_values: list[str] = Field(default_factory=lambda: ["", "NaN", "nan", "NA"])
    all_missing: Severity = "error"
    max_missing_fraction: float = Field(default=0, ge=0, le=1)
    on_missing: Severity = "error"


class TimeRule(_Strict):
    """The time column."""

    column: str
    unit: str
    start: float | None = None
    step: float | None = Field(default=None, gt=0)
    strictly_increasing: bool = True


class ColumnSpec(_Strict):
    """One column of the CSV file."""

    key: str = Field(pattern=_KEY)
    header: str = Field(min_length=1)
    unit: str
    range: Range | None = None
    type: Literal["number", "text"] | None = None  # None: use column_defaults
    max_missing_fraction: float | None = Field(default=None, ge=0, le=1)


class ConsistencyRule(_Strict):
    """A check across columns, evaluated row by row."""

    name: str
    expression: str
    tolerance_relative: float | None = Field(default=None, ge=0)
    severity: Severity = "warning"


class ResultDataSpec(_Strict):
    """Rules for the ResultData (.csv) file."""

    file: CsvFormat = CsvFormat()
    rows: RowRule = RowRule()
    header: HeaderRule = HeaderRule()
    column_defaults: ColumnDefaults = ColumnDefaults()
    time: TimeRule | None = None
    on_out_of_range: Severity = "warning"
    columns: list[ColumnSpec] = Field(min_length=1)
    consistency: list[ConsistencyRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "ResultDataSpec":
        for what in ("key", "header"):
            values = [getattr(c, what) for c in self.columns]
            doubles = sorted({v for v in values if values.count(v) > 1})
            if doubles:
                raise ValueError(f"columns: {what} used more than once: {', '.join(doubles)}")
        if self.time and self.time.column not in {c.key for c in self.columns}:
            raise ValueError(f"time.column: '{self.time.column}' is not a column key")
        return self


class MetadataFormat(_Strict):
    """How the metadata file is written."""

    extension: str = ".yaml"


class MetadataField(_Strict):
    """One key the modeller fills in in the metadata file."""

    key: str = Field(pattern=_KEY)
    type: Literal["text", "integer", "number", "date", "datetime", "choice", "list"]
    required: bool = False
    matches_name_part: str | None = None  # must agree with this part of the file name
    range: Range | None = None
    choices: list[str] | None = None
    example: str | None = None

    @model_validator(mode="after")
    def _choices(self) -> "MetadataField":
        if (self.type == "choice") != (self.choices is not None):
            raise ValueError(f"{self.key}: 'choices' is needed for, and only for, type 'choice'")
        return self


class ResultMetadataSpec(_Strict):
    """Rules for the ResultMetadata (.yaml) file."""

    file: MetadataFormat = MetadataFormat()
    unknown_keys: Literal["error", "warning", "ignore"] = "warning"
    fields: list[MetadataField] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "ResultMetadataSpec":
        keys = [f.key for f in self.fields]
        doubles = sorted({k for k in keys if keys.count(k) > 1})
        if doubles:
            raise ValueError(f"fields: key used more than once: {', '.join(doubles)}")
        return self


class CmeSpec(_Strict):
    """Contents of `cme/CME_<Series>_<Number>.yaml`."""

    schema_version: Literal[1]
    cme: CmeInfo
    result_data: ResultDataSpec
    result_metadata: ResultMetadataSpec

    @property
    def folder_name(self) -> str:
        """E.g. `CME_DHN_1`."""
        return f"CME_{self.cme.series}_{self.cme.exercise_number}"
