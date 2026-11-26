"""The schema of the YAML spec files: their allowed layout, as pydantic models.

Loading a YAML file through these models checks it: a misspelt key, a missing
value or a wrong type stops with a message that names the place in the file
(see `destest.specs.SpecError`). Two files are described here:

- `naming_convention.yaml` -> `NamingConvention` (one file for all CMEs)
- `result_metadata.yaml` -> `ResultMetadataLayout` (one file for all CMEs)
- `locations.yaml` -> `Locations` (coordinates for the map of contributions)
- `cme/CME_<Series>_<Number>.yaml` -> `CmeSpec` (one file per CME)

To add a new setting to a YAML file, add it to the matching model first;
unknown keys are rejected so that typos do not pass silently.
"""

import re
import string
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .expressions import parse_rule

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
    full_title: str = Field(min_length=1)
    description_reference: str = ""  # where the CME is described (report, section)
    status: Literal["draft", "active", "closed"] = "draft"
    #: What the exercise tests, in a few sentences (shown on the dashboards).
    description: str = Field(default="")
    #: Key characteristics, label -> value (shown as a table, in this order).
    characteristics: dict[str, str] = Field(default_factory=dict)


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
        keys = {c.key for c in self.columns}
        if self.time and self.time.column not in keys:
            raise ValueError(f"time.column: '{self.time.column}' is not a column key")
        for i, c in enumerate(self.consistency):
            where = f"consistency[{i}] ({c.name})"
            try:
                rule = parse_rule(c.expression)
            except ValueError as exc:
                raise ValueError(f"{where}: {exc}") from exc
            unknown = sorted(rule.names - keys)
            if unknown:
                raise ValueError(f"{where}: not a column key: {', '.join(unknown)}")
            if rule.op == "≈" and c.tolerance_relative is None:
                raise ValueError(f"{where}: a rule with '≈' needs tolerance_relative")
        return self


class MetadataField(_Strict):
    """One key the modeller fills in in the ResultMetadata file (free text)."""

    key: str = Field(pattern=_KEY)
    required: bool = False
    description: str = ""
    # The value must agree with a part of the file name (its key in
    # naming_convention.yaml), with "cme" (the folder) or "result_data_file".
    must_match: str | None = None


def _unique_keys(fields: list[MetadataField], where: str) -> None:
    keys = [f.key for f in fields]
    doubles = sorted({k for k in keys if keys.count(k) > 1})
    if doubles:
        raise ValueError(f"{where}: key used more than once: {', '.join(doubles)}")


class ResultMetadataSpec(_Strict):
    """The ResultMetadata sections defined per CME (in the CME file)."""

    simulation_config: list[MetadataField] = Field(min_length=1)
    model_details: list[MetadataField] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "ResultMetadataSpec":
        _unique_keys(self.simulation_config, "simulation_config")
        _unique_keys(self.model_details, "model_details")
        return self


class MetadataSection(_Strict):
    """One section of a ResultMetadata file (in `result_metadata.yaml`)."""

    name: str = Field(pattern=_KEY)
    kind: Literal["fields", "per_cme", "text"]
    fields: list[MetadataField] = Field(default_factory=list)  # kind "fields"
    required: bool = False  # kind "text"
    description: str = ""  # kind "text"

    @model_validator(mode="after")
    def _fits_kind(self) -> "MetadataSection":
        if (self.kind == "fields") != bool(self.fields):
            raise ValueError(f"{self.name}: 'fields' is needed for, and only for, kind 'fields'")
        _unique_keys(self.fields, self.name)
        return self


class ResultMetadataLayout(_Strict):
    """Contents of `result_metadata.yaml`: the sections of every ResultMetadata file."""

    schema_version: Literal[1]
    format_version: int = Field(ge=1)  # expected value of `metadata_format_version`
    sections: list[MetadataSection] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> "ResultMetadataLayout":
        names = [s.name for s in self.sections]
        doubles = sorted({n for n in names if names.count(n) > 1})
        if doubles:
            raise ValueError(f"sections: name used more than once: {', '.join(doubles)}")
        per_cme = sorted(s.name for s in self.sections if s.kind == "per_cme")
        expected = sorted(ResultMetadataSpec.model_fields)
        if per_cme != expected:
            raise ValueError(
                f"sections: the 'per_cme' sections must be {', '.join(expected)} "
                f"(found {', '.join(per_cme) or 'none'})"
            )
        return self


class Coordinates(_Strict):
    """A point on the map, in degrees."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Locations(_Strict):
    """Contents of `locations.yaml`: where institutions are, for the map."""

    schema_version: Literal[1]
    cities: dict[str, Coordinates] = Field(default_factory=dict)  # "City, Country" -> point
    countries: dict[str, Coordinates] = Field(default_factory=dict)  # fallback: centre

    @field_validator("cities")
    @classmethod
    def _city_and_country(cls, v: dict[str, Coordinates]) -> dict[str, Coordinates]:
        bad = [k for k in v if len([p for p in k.split(", ") if p.strip()]) != 2]
        if bad:
            raise ValueError(f"write cities as 'City, Country': {', '.join(bad)}")
        return v


class DeviationLimits(_Strict):
    """When a value is highlighted: beyond `acceptable` (yellow), beyond `critical` (red).

    `mode`: `relative` (deviation in % of the reference) or `absolute` (difference from the
    reference, in the unit of the value). Default: relative for values compared with the
    median of all submissions, absolute for targets and ideal values of metrics.
    """

    acceptable: float = Field(ge=0)
    critical: float = Field(ge=0)
    mode: Literal["relative", "absolute"] | None = Field(default=None)

    @model_validator(mode="after")
    def _order(self) -> "DeviationLimits":
        if self.critical < self.acceptable:
            raise ValueError("critical must be at least acceptable")
        return self


class GeneralComparisonSpec(_Strict):
    """One value per submission: a general-comparison function on one or more columns.

    See `destest.analysis.general_comparison` (data aggregates and physics checks).
    """

    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    function: str  # name of a general-comparison function
    #: One input series (column key): the `values` of a data aggregate ...
    column: str | None = Field(default=None)
    #: ... or several, by input name: e.g. {power: Q_supplied, m_flow: m_flow_supply_i}
    inputs: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)  # keyword parameters of the function
    unit: str = Field(default="")
    #: Known ideal value (physics checks): compared with it instead of the median of all.
    target: float | None = Field(default=None)
    #: Weight in the accuracy grade (0 = shown, not counted).
    weight: float = Field(default=1.0, ge=0)
    #: Highlight limits (default: `default_limits` of the analysis section).
    limits: DeviationLimits | None = Field(default=None)

    @model_validator(mode="after")
    def _one_source(self) -> "GeneralComparisonSpec":
        if (self.column is None) == (not self.inputs):
            raise ValueError("give either `column` (one series) or `inputs` (several)")
        return self

    @property
    def columns_by_input(self) -> dict[str, str]:
        """Input name -> column key."""
        return {"values": self.column} if self.column is not None else dict(self.inputs)


class MetricChoiceSpec(_Strict):
    """A comparison metric (see `destest.analysis.point_by_point_comparison`) and its weight."""

    name: str
    weight: float = Field(default=1.0, ge=0)
    params: dict[str, Any] = Field(default_factory=dict)
    #: Highlight limits on the metric value (distance to its ideal value, in its unit).
    limits: DeviationLimits | None = Field(default=None)


class TimeSeriesComparisonSpec(_Strict):
    """Which columns are compared as time series with the reference time series."""

    columns: Literal["all"] | list[str] = Field(default="all")


class DataProfileSpec(_Strict):
    """A data profile: values of several columns read as one series (e.g. along a network)."""

    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1)
    points: list[str] = Field(min_length=2)  # column keys, in order
    positions: list[str] | None = Field(default=None)  # labels of the points, e.g. node names
    unit: str = Field(default="")
    aggregate: Literal["mean", "last"] = "mean"  # one value per column (mean = steady state)

    @model_validator(mode="after")
    def _positions(self) -> "DataProfileSpec":
        if self.positions is not None and len(self.positions) != len(self.points):
            raise ValueError("positions: one label per point")
        return self


class PointByPointComparisonSpec(_Strict):
    """Series compared point by point with the reference series, and the metrics used."""

    metrics: list[str | MetricChoiceSpec] = Field(min_length=1)
    time_series: TimeSeriesComparisonSpec | None = Field(default=None)
    data_profiles: list[DataProfileSpec] = Field(default_factory=list)

    @property
    def metric_choices(self) -> list[MetricChoiceSpec]:
        """The metrics, each with its weight and parameters."""
        return [
            m if isinstance(m, MetricChoiceSpec) else MetricChoiceSpec(name=m) for m in self.metrics
        ]


class PanelSpec(_Strict):
    """One element of a dashboard: a visual (see `destest.analysis.visuals`) and its options."""

    visual: str
    title: str = Field(min_length=1)
    description: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


class DashboardsSpec(_Strict):
    """The visuals of the three dashboards, in display order."""

    overview: list[PanelSpec] = Field(default_factory=list)
    detail: list[PanelSpec] = Field(default_factory=list)
    comparison: list[PanelSpec] = Field(default_factory=list)


class AnalysisSpec(_Strict):
    """What is compared in a CME, and its dashboards."""

    reference: Literal["median", "mean"] = "median"
    #: Why this reference, or anything to know about it (shown with the reference).
    reference_note: str = Field(default="")
    #: Highlight limits of the values compared with the median that have none of their own.
    default_limits: DeviationLimits | None = Field(default=None)
    #: Comments and observations on the results, one bullet each (end of the overview).
    comments_and_observations: list[str] = Field(default_factory=list)
    general_comparison: list[GeneralComparisonSpec] = Field(min_length=1)
    point_by_point_comparison: PointByPointComparisonSpec | None = Field(default=None)
    dashboards: DashboardsSpec = DashboardsSpec()

    @model_validator(mode="after")
    def _unique(self) -> "AnalysisSpec":
        pbp = self.point_by_point_comparison
        profiles = pbp.data_profiles if pbp is not None else []
        keys = [g.key for g in self.general_comparison] + [p.key for p in profiles]
        doubles = sorted({k for k in keys if keys.count(k) > 1})
        if doubles:
            raise ValueError(f"key used more than once: {', '.join(doubles)}")
        weights = [g.weight for g in self.general_comparison]
        if pbp is not None and (pbp.time_series is not None or pbp.data_profiles):
            weights += [m.weight for m in pbp.metric_choices]
        if not any(w > 0 for w in weights):
            raise ValueError("at least one compared item needs a weight above 0")
        return self


class CmeSpec(_Strict):
    """Contents of `cme/CME_<Series>_<Number>.yaml`."""

    schema_version: Literal[1]
    cme: CmeInfo
    result_data: ResultDataSpec
    result_metadata: ResultMetadataSpec
    analysis: AnalysisSpec | None = None

    @model_validator(mode="after")
    def _analysis_columns(self) -> "CmeSpec":
        if self.analysis is None:
            return self
        columns = {c.key for c in self.result_data.columns}
        bad: list[str] = []
        for g in self.analysis.general_comparison:
            where = f"analysis.general_comparison.{g.key}"
            bad += [
                f"{where}.{'column' if g.column else 'inputs.' + name}: '{col}' is not a column"
                for name, col in g.columns_by_input.items()
                if col not in columns
            ]
        pbp = self.analysis.point_by_point_comparison
        if pbp is not None:
            ts = pbp.time_series
            if ts is not None and ts.columns != "all":
                where = "analysis.point_by_point_comparison.time_series.columns"
                bad += [f"{where}: '{c}' is not a column" for c in ts.columns if c not in columns]
            for p in pbp.data_profiles:
                where = f"analysis.point_by_point_comparison.data_profiles.{p.key}.points"
                bad += [f"{where}: '{c}' is not a column" for c in p.points if c not in columns]
        if bad:
            raise ValueError("; ".join(bad))
        return self

    @property
    def compared_columns(self) -> list[str]:
        """Columns compared as time series (all but the time column if `columns: all`)."""
        pbp = self.analysis.point_by_point_comparison if self.analysis else None
        if pbp is None or pbp.time_series is None:
            return []
        if pbp.time_series.columns != "all":
            return list(pbp.time_series.columns)
        time = self.result_data.time.column if self.result_data.time else None
        return [c.key for c in self.result_data.columns if c.key != time]

    @property
    def folder_name(self) -> str:
        """E.g. `CME_DHN_1`."""
        return f"CME_{self.cme.series}_{self.cme.exercise_number}"
