"""The analysis context: KPIs of every submission, the reference, colours.

Built once per dashboard from the CME spec (`analysis` section) and the
submissions, then handed to every visual, so all visuals show the same numbers.

* `submissions`: every submission of the CME; the reference is built from them;
* `focus`: the submissions a dashboard shows (all, one, or a selection).
"""

from dataclasses import dataclass, field

from ..results import Submission
from ..specs.schema import AnalysisSpec, CmeSpec, KpiSpec
from .accuracy_metric import (
    METRIC_UNITS,
    SERIES_METRICS,
    VALUE_METRICS,
    closeness_grade,
    closeness_scores,
    reference_series,
    reference_value,
)
from .kpis import KPI_FUNCTIONS

#: Colours given to the submissions, in order (Plotly's default palette).
PALETTE = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
)
REFERENCE_COLOR = "#000000"


def compute_kpis(spec: CmeSpec, sub: Submission) -> dict[str, float | None]:
    """Every KPI of the CME for one submission, by KPI key."""
    analysis = _analysis(spec)
    time = time_values(spec, sub)
    out: dict[str, float | None] = {}
    for k in analysis.kpis:
        values = sub.series.get(k.column)
        out[k.key] = None if values is None else KPI_FUNCTIONS[k.function](values, time, **k.params)
    return out


def time_values(spec: CmeSpec, sub: Submission) -> list[float | None]:
    """The time column of a submission, or 0, 1, 2, ... if the CME has none."""
    t = spec.result_data.time
    n = max((len(v) for v in sub.series.values()), default=0)
    if t is not None and t.column in sub.series:
        return sub.series[t.column]
    return [float(i) for i in range(n)]


def _analysis(spec: CmeSpec) -> AnalysisSpec:
    if spec.analysis is None:
        raise ValueError(f"{spec.folder_name}: the spec file has no 'analysis' section")
    return spec.analysis


@dataclass
class AnalysisContext:
    """Everything a visual needs; see `build_context`."""

    spec: CmeSpec
    submissions: list[Submission]
    focus: list[Submission]
    kpi_values: dict[str, dict[str, float | None]]  # submission id -> KPI key -> value
    reference: dict[str, float | None]  # KPI key -> reference value
    colors: dict[str, str]  # submission id -> colour
    # submission id -> KPI key -> score 0-100, and submission id -> closeness grade 0-100
    kpi_scores: dict[str, dict[str, float | None]] = field(default_factory=dict)
    closeness: dict[str, float | None] = field(default_factory=dict)
    _series_ref: dict[str, list[float | None]] = field(default_factory=dict, repr=False)

    @property
    def analysis(self) -> AnalysisSpec:
        """The `analysis` section of the CME spec."""
        return _analysis(self.spec)

    @property
    def reference_label(self) -> str:
        """E.g. `Reference (median of 7)`."""
        return f"Reference ({self.analysis.reference} of {len(self.submissions)})"

    def kpi(self, key: str) -> KpiSpec:
        """The spec of one KPI."""
        return next(k for k in self.analysis.kpis if k.key == key)

    def kpi_keys(self, selection: str | list[str]) -> list[str]:
        """`"all"` or a list of KPI keys -> list of KPI keys, in spec order."""
        if selection == "all":
            return [k.key for k in self.analysis.kpis]
        return list(selection)

    def kpi_label(self, key: str, unit: bool = True) -> str:
        """E.g. `Heat loss supply i-h [W]`."""
        k = self.kpi(key)
        return f"{k.label} [{k.unit}]" if unit and k.unit else k.label

    def column_label(self, column: str) -> str:
        """The CSV header of a column key."""
        return next(c.header for c in self.spec.result_data.columns if c.key == column)

    def time(self, sub: Submission) -> list[float | None]:
        """Time column of a submission."""
        return time_values(self.spec, sub)

    def series_reference(self, column: str) -> list[float | None]:
        """Point-by-point reference of one column (cached)."""
        if column not in self._series_ref:
            series = [s.series[column] for s in self.submissions if column in s.series]
            self._series_ref[column] = reference_series(series, self.analysis.reference)
        return self._series_ref[column]

    def metric(self, metric: str, sub: Submission, kpi_key: str) -> float | None:
        """A value metric on a KPI, or a series metric on the KPI's column."""
        if metric in VALUE_METRICS:
            value, ref = self.kpi_values[sub.id].get(kpi_key), self.reference.get(kpi_key)
            return None if value is None or ref is None else VALUE_METRICS[metric](value, ref)
        column = self.kpi(kpi_key).column
        if column not in sub.series:
            return None
        return SERIES_METRICS[metric](sub.series[column], self.series_reference(column))

    def closeness_rank(self, sub: Submission) -> tuple[int, int] | None:
        """(rank, number ranked) of a submission by closeness grade; 1 = closest."""
        grade = self.closeness.get(sub.id)
        if grade is None:
            return None
        grades = [g for g in self.closeness.values() if g is not None]
        return 1 + sum(g > grade for g in grades), len(grades)

    def metric_unit(self, metric: str, kpi_key: str) -> str:
        """Unit of a metric on a KPI (`%`, or the KPI's unit)."""
        return METRIC_UNITS.get(metric) or self.kpi(kpi_key).unit


def build_context(
    spec: CmeSpec, submissions: list[Submission], focus: list[Submission] | None = None
) -> AnalysisContext:
    """Compute all KPIs and the reference for a CME and its submissions."""
    analysis = _analysis(spec)
    kpi_values = {s.id: compute_kpis(spec, s) for s in submissions}
    for s in focus or []:
        kpi_values.setdefault(s.id, compute_kpis(spec, s))
    reference = {
        k.key: reference_value([kpi_values[s.id][k.key] for s in submissions], analysis.reference)
        for k in analysis.kpis
    }
    every = [*submissions, *(s for s in focus or [] if s not in submissions)]
    colors = {s.id: PALETTE[i % len(PALETTE)] for i, s in enumerate(every)}
    # Closeness to the reference: per KPI, 100 for the closest, 0 for the furthest.
    kpi_scores: dict[str, dict[str, float | None]] = {s.id: {} for s in every}
    for k in analysis.kpis:
        scores = closeness_scores({s.id: kpi_values[s.id][k.key] for s in every}, reference[k.key])
        for sid, score in scores.items():
            kpi_scores[sid][k.key] = score
    closeness = {sid: closeness_grade(list(sc.values())) for sid, sc in kpi_scores.items()}
    return AnalysisContext(
        spec=spec,
        submissions=submissions,
        focus=list(focus) if focus is not None else list(submissions),
        kpi_values=kpi_values,
        reference=reference,
        colors=colors,
        kpi_scores=kpi_scores,
        closeness=closeness,
    )
