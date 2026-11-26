"""The analysis context: every compared item of every submission, the references, colours.

Built once per dashboard from the CME spec (`analysis` section) and the submissions, then
handed to every visual, so all visuals show the same numbers.

A **compared item** (`ResultItem`) is one row of the results table, one value per
submission, scored in the accuracy grade:

* `data_aggregate` and `physics_check` items, from `analysis.general_comparison`
  (`general_comparison/`); reference = median of all submissions, or the item's `target`;
* `time_series` items: one metric on one column, against the reference time series;
* `data_profile` items: one metric on one data profile, against the reference profile
  (`point_by_point_comparison/`); reference = the metric's value for a perfect fit.

`submissions` are all valid submissions of the CME (the references are built from them);
`focus` are the submissions a dashboard shows (all, one, or a selection).
"""

from dataclasses import dataclass, field
from typing import Literal

from ..results import Submission
from ..specs.schema import AnalysisSpec, CmeSpec, DeviationLimits
from .accuracy_grade import closeness_grade, closeness_scores
from .general_comparison import GENERAL_FUNCTIONS, VALUE_DIFFERENCE_UNITS, VALUE_DIFFERENCES
from .point_by_point_comparison import (
    MetricRequest,
    all_time_series_metrics,
    central_value,
    compare_data_profiles,
    compare_time_series,
    reference_time_series,
)

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

#: How each reference method (`analysis.reference` in the CME spec) is built, in words.
REFERENCE_METHODS = {
    "median": "Median of all valid submissions",
    "mean": "Mean (arithmetic average) of all valid submissions",
}

ItemKind = Literal["data_aggregate", "physics_check", "time_series", "data_profile"]


def describe_reference(analysis: AnalysisSpec, n_submissions: int) -> str:
    """The reference of a CME in one sentence, e.g. for the dashboard header.

    >>> from destest.specs import load_cme_spec
    >>> describe_reference(load_cme_spec("DHN", 1).analysis, 7)  # doctest: +ELLIPSIS
    'Median of all valid submissions (currently 7), value by value...'
    """
    return (
        f"{REFERENCE_METHODS[analysis.reference]} (currently {n_submissions}), value by value "
        "and point by point for the time series and data profiles."
    )


@dataclass(frozen=True)
class ResultItem:
    """One compared item: one row of the results table, one value per submission."""

    key: str
    label: str
    unit: str
    kind: ItemKind
    weight: float
    columns: tuple[str, ...] = ()  # the source columns
    metric: str | None = None  # comparison metric (time_series, data_profile)
    target: float | None = None  # known ideal value (physics checks)
    limits: DeviationLimits | None = None  # when a value is highlighted

    @property
    def against_median(self) -> bool:
        """True if the item is compared with the median of all (no target, no metric)."""
        return self.metric is None and self.target is None

    @property
    def deviation_mode(self) -> str:
        """`relative` (% of the reference) or `absolute` (in the unit of the value)."""
        if self.limits is not None and self.limits.mode is not None:
            return self.limits.mode
        return "relative" if self.against_median else "absolute"


def item_keys(spec: CmeSpec) -> list[str]:
    """Keys of every compared item of a CME, in display order (no data needed)."""
    return [i.key for i in result_items(spec)]


def result_items(spec: CmeSpec) -> list[ResultItem]:
    """The compared items of a CME, from its spec: general comparison, then series metrics."""
    analysis = _analysis(spec)
    items: list[ResultItem] = []
    for g in analysis.general_comparison:
        f = GENERAL_FUNCTIONS.get(g.function)
        kind: ItemKind = (
            "physics_check" if f is not None and f.kind == "physics_check" else "data_aggregate"
        )
        cols = tuple(g.columns_by_input.values())
        limits = g.limits or (analysis.default_limits if g.target is None else None)
        items.append(
            ResultItem(g.key, g.label, g.unit, kind, g.weight, cols, None, g.target, limits)
        )
    pbp = analysis.point_by_point_comparison
    if pbp is None:
        return items
    units = {c.key: c.unit for c in spec.result_data.columns}
    headers = {c.key: c.header for c in spec.result_data.columns}
    metrics = all_time_series_metrics()
    for col in spec.compared_columns:
        for m in pbp.metric_choices:
            unit = metrics[m.name].unit_for(units.get(col, "")) if m.name in metrics else ""
            items.append(
                ResultItem(
                    f"{col}:{m.name}",
                    f"{m.name} {headers.get(col, col)}",
                    unit,
                    "time_series",
                    m.weight,
                    (col,),
                    m.name,
                    None,
                    m.limits,
                )
            )
    for p in pbp.data_profiles:
        for m in pbp.metric_choices:
            unit = metrics[m.name].unit_for(p.unit) if m.name in metrics else ""
            items.append(
                ResultItem(
                    f"{p.key}:{m.name}",
                    f"{m.name} {p.label}",
                    unit,
                    "data_profile",
                    m.weight,
                    tuple(p.points),
                    m.name,
                    None,
                    m.limits,
                )
            )
    return items


def general_values(spec: CmeSpec, sub: Submission) -> dict[str, float | None]:
    """Every general-comparison value of the CME for one submission, by item key."""
    analysis = _analysis(spec)
    time = time_values(spec, sub)
    out: dict[str, float | None] = {}
    for g in analysis.general_comparison:
        inputs = g.columns_by_input
        if any(col not in sub.series for col in inputs.values()):
            out[g.key] = None
            continue
        data = {name: sub.series[col] for name, col in inputs.items()}
        out[g.key] = GENERAL_FUNCTIONS[g.function].evaluate(data, time, g.params)
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
    items: list[ResultItem]
    values: dict[str, dict[str, float | None]]  # submission id -> item key -> value
    reference: dict[str, float | None]  # item key -> reference (median, target or ideal)
    colors: dict[str, str]  # submission id -> colour
    # submission id -> item key -> score 0-100, and submission id -> accuracy grade 0-100
    scores: dict[str, dict[str, float | None]] = field(default_factory=dict)
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

    def item(self, key: str) -> ResultItem:
        """A compared item by key."""
        return next(i for i in self.items if i.key == key)

    def item_keys(self, selection: str | list[str]) -> list[str]:
        """A selection -> list of item keys, in order: `all`, `general` (data aggregates and
        physics checks), `aggregates` (data aggregates only) or a list of item keys."""
        if selection == "all":
            return [i.key for i in self.items]
        if selection == "general":
            return [i.key for i in self.items if i.metric is None]
        if selection == "aggregates":
            return [i.key for i in self.items if i.kind == "data_aggregate"]
        return list(selection)

    def item_label(self, key: str, unit: bool = True) -> str:
        """E.g. `Heat loss supply i-h [W]`."""
        i = self.item(key)
        return f"{i.label} [{i.unit}]" if unit and i.unit else i.label

    def reference_text(self, key: str) -> str:
        """How the reference of an item is given: '', 'target', or 'ideal'."""
        i = self.item(key)
        if i.metric is not None:
            return "ideal"
        return "target" if i.target is not None else ""

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
            self._series_ref[column] = reference_time_series(series, self.analysis.reference)
        return self._series_ref[column]

    def metric(self, metric: str, sub: Submission, key: str) -> float | None:
        """A value difference on an item (e.g. `relative_deviation` from its reference), or a
        comparison metric (e.g. `CVRMSE`) on the item's column against its reference series."""
        if metric in VALUE_DIFFERENCES:
            value, ref = self.values[sub.id].get(key), self.reference.get(key)
            return None if value is None or ref is None else VALUE_DIFFERENCES[metric](value, ref)
        item = self.item(key)
        if len(item.columns) != 1 or item.columns[0] not in sub.series:
            return None
        column = item.columns[0]
        m = all_time_series_metrics()[metric]
        extra = {"time": self.time(sub)} if "time" in m.parameters else {}
        return m(sub.series[column], self.series_reference(column), **extra)

    def metric_unit(self, metric: str, key: str) -> str:
        """Unit of a difference or metric on an item (`%`, or the item's unit)."""
        if metric in VALUE_DIFFERENCE_UNITS:
            return VALUE_DIFFERENCE_UNITS[metric] or self.item(key).unit
        m = all_time_series_metrics().get(metric)
        item = self.item(key)
        data_unit = (
            next((c.unit for c in self.spec.result_data.columns if c.key in item.columns), "")
            if item.columns
            else ""
        )
        return m.unit_for(data_unit) if m else ""

    def deviation(self, sub: Submission, key: str) -> float | None:
        """Deviation of a submission's value from the item's reference (median, target or
        ideal): in % of it (`relative`) or in the unit of the value (`absolute`)."""
        item = self.item(key)
        value, ref = self.values[sub.id].get(key), self.reference.get(key)
        if value is None or ref is None:
            return None
        if item.deviation_mode == "relative":
            return VALUE_DIFFERENCES["relative_deviation"](value, ref)
        return value - ref

    def highlight(self, sub: Submission, key: str) -> str:
        """`bad` beyond the critical limit, `warn` beyond the acceptable one, else ``."""
        limits = self.item(key).limits
        dev = self.deviation(sub, key)
        if limits is None or dev is None:
            return ""
        if abs(dev) > limits.critical:
            return "bad"
        return "warn" if abs(dev) > limits.acceptable else ""

    def closeness_rank(self, sub: Submission) -> tuple[int, int] | None:
        """(rank, number ranked) of a submission by accuracy grade; 1 = closest."""
        grade = self.closeness.get(sub.id)
        if grade is None:
            return None
        grades = [g for g in self.closeness.values() if g is not None]
        return 1 + sum(g > grade for g in grades), len(grades)


def build_context(
    spec: CmeSpec, submissions: list[Submission], focus: list[Submission] | None = None
) -> AnalysisContext:
    """Compute every compared item, its reference and the accuracy grade of each submission."""
    analysis = _analysis(spec)
    method = analysis.reference
    every = [*submissions, *(s for s in focus or [] if s not in submissions)]
    items = result_items(spec)
    values: dict[str, dict[str, float | None]] = {s.id: general_values(spec, s) for s in every}
    reference: dict[str, float | None] = {}
    for it in items:
        if it.metric is not None:
            continue
        reference[it.key] = (
            it.target
            if it.target is not None
            else central_value([values[s.id][it.key] for s in submissions], method)
        )
    pbp = analysis.point_by_point_comparison
    if pbp is not None:
        requests = [MetricRequest(m.name, m.weight, m.params) for m in pbp.metric_choices]
        ref_series: dict[str, list[float | None]] = {}
        for col in spec.compared_columns:
            pool = [s.series[col] for s in submissions if col in s.series]
            compared = {s.id: s.series[col] for s in every if col in s.series}
            time = time_values(spec, every[0]) if every else []
            c = compare_time_series(compared, time, requests, method, pool)
            ref_series[col] = c.reference
            for m in requests:
                key = f"{col}:{m.name}"
                reference[key] = c.ideal[m.name]
                for sid, v in c.values[m.name].items():
                    values[sid][key] = v
        for p in pbp.data_profiles:
            cols = {s.id: s.series for s in every}
            pool_cols = [s.series for s in submissions]
            c = compare_data_profiles(cols, p.points, requests, method, pool_cols, p.aggregate)
            for m in requests:
                key = f"{p.key}:{m.name}"
                reference[key] = c.ideal[m.name]
                for sid, v in c.values[m.name].items():
                    values[sid][key] = v
    else:
        ref_series = {}
    colors = {s.id: PALETTE[i % len(PALETTE)] for i, s in enumerate(every)}
    # Accuracy grade: per item, 100 for the closest to its reference, 0 for the furthest.
    scores: dict[str, dict[str, float | None]] = {s.id: {} for s in every}
    for it in items:
        sc = closeness_scores({s.id: values[s.id].get(it.key) for s in every}, reference[it.key])
        for sid, score in sc.items():
            scores[sid][it.key] = score
    weights = [it.weight for it in items]
    closeness = {
        sid: closeness_grade([sc.get(it.key) for it in items], weights)
        for sid, sc in scores.items()
    }
    return AnalysisContext(
        spec=spec,
        submissions=submissions,
        focus=list(focus) if focus is not None else list(submissions),
        items=items,
        values=values,
        reference=reference,
        colors=colors,
        scores=scores,
        closeness=closeness,
        _series_ref=ref_series,
    )
