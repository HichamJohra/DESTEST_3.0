"""Accuracy metrics: how far a submission is from the reference.

Two kinds, both registered by name for use in the spec files:

* **value metrics** compare one KPI value with the reference value of that KPI;
* **series metrics** compare a whole time series with the reference time series
  (point by point), as in the DESTEST comparison tool.

The reference is built from all submissions of a CME: the median (default) or the
mean, value by value or point by point (`reference_value`, `reference_series`).

    >>> VALUE_METRICS["relative_deviation"](105.0, 100.0)
    5.0
    >>> round(SERIES_METRICS["nmbe"]([2.0, 4.0], [2.0, 2.0]), 1)
    50.0

The **closeness to the reference** grade (0-100) combines all KPIs into one number per
submission (`closeness_scores`, `closeness_grade`).
"""

import math
import statistics
from collections.abc import Callable, Sequence

Values = Sequence[float | None]
ValueMetric = Callable[[float, float], float | None]
SeriesMetric = Callable[[Values, Values], float | None]

#: name -> (value, reference value) -> number. `None` when it cannot be computed.
VALUE_METRICS: dict[str, ValueMetric] = {}
#: name -> (series, reference series) -> number. `None` when it cannot be computed.
SERIES_METRICS: dict[str, SeriesMetric] = {}

#: Unit shown with each metric.
METRIC_UNITS: dict[str, str] = {}


def _register_value(name: str, unit: str) -> Callable[[ValueMetric], ValueMetric]:
    def register(f: ValueMetric) -> ValueMetric:
        VALUE_METRICS[name] = f
        METRIC_UNITS[name] = unit
        return f

    return register


def _register_series(name: str, unit: str) -> Callable[[SeriesMetric], SeriesMetric]:
    def register(f: SeriesMetric) -> SeriesMetric:
        SERIES_METRICS[name] = f
        METRIC_UNITS[name] = unit
        return f

    return register


# ---- reference -------------------------------------------------------------------
def reference_value(values: Sequence[float | None], method: str = "median") -> float | None:
    """Median or mean of the given KPI values (missing ones skipped)."""
    v = [x for x in values if x is not None and math.isfinite(x)]
    if not v:
        return None
    return statistics.median(v) if method == "median" else statistics.fmean(v)


def reference_series(series: Sequence[Values], method: str = "median") -> list[float | None]:
    """Point-by-point median or mean of time series of equal length.

    Series of another length than the most common one are left out.
    """
    if not series:
        return []
    lengths = [len(s) for s in series]
    n = max(set(lengths), key=lengths.count)
    usable = [s for s in series if len(s) == n]
    return [reference_value([s[i] for s in usable], method) for i in range(n)]


def _pairs(values: Values, reference: Values) -> list[tuple[float, float]]:
    return [
        (y, r)
        for y, r in zip(values, reference, strict=False)
        if y is not None and r is not None and math.isfinite(y) and math.isfinite(r)
    ]


# ---- value metrics -----------------------------------------------------------------
@_register_value("relative_deviation", "%")
def relative_deviation(value: float, reference: float) -> float | None:
    """(value - reference) / |reference| * 100."""
    return (value - reference) / abs(reference) * 100 if reference else None


@_register_value("absolute_deviation", "")
def absolute_deviation(value: float, reference: float) -> float | None:
    """value - reference, in the unit of the KPI."""
    return value - reference


# ---- series metrics ----------------------------------------------------------------
@_register_series("nmbe", "%")
def nmbe(values: Values, reference: Values) -> float | None:
    """Normalised mean bias error: sum(y - r) / (n * mean(r)) * 100."""
    p = _pairs(values, reference)
    if not p:
        return None
    mean_ref = sum(r for _, r in p) / len(p)
    return sum(y - r for y, r in p) / (len(p) * mean_ref) * 100 if mean_ref else None


@_register_series("cvrmse", "%")
def cvrmse(values: Values, reference: Values) -> float | None:
    """Coefficient of variation of the RMSE: sqrt(mean((y - r)^2)) / mean(r) * 100."""
    p = _pairs(values, reference)
    if not p:
        return None
    mean_ref = sum(r for _, r in p) / len(p)
    rmse_ = math.sqrt(sum((y - r) ** 2 for y, r in p) / len(p))
    return rmse_ / mean_ref * 100 if mean_ref else None


@_register_series("rmse", "")
def rmse(values: Values, reference: Values) -> float | None:
    """Root mean square error, in the unit of the series."""
    p = _pairs(values, reference)
    return math.sqrt(sum((y - r) ** 2 for y, r in p) / len(p)) if p else None


@_register_series("mae", "")
def mae(values: Values, reference: Values) -> float | None:
    """Mean absolute error, in the unit of the series."""
    p = _pairs(values, reference)
    return sum(abs(y - r) for y, r in p) / len(p) if p else None


@_register_series("max_abs_error", "")
def max_abs_error(values: Values, reference: Values) -> float | None:
    """Largest absolute difference, in the unit of the series."""
    p = _pairs(values, reference)
    return max(abs(y - r) for y, r in p) if p else None


# ---- closeness to the reference ------------------------------------------------------
def closeness_scores(
    values: dict[str, float | None], reference: float | None
) -> dict[str, float | None]:
    """Score (0-100) of each submission on one KPI, from its distance to the reference.

    The closest submission gets 100, the furthest 0, the others in between,
    linearly in their distance: 100 * (worst - d) / (worst - best). If all are
    equally close, all get 100. A missing value (or reference) gets `None`.

    >>> closeness_scores({"a": 10.0, "b": 12.0, "c": 11.0, "d": None}, 10.0)
    {'a': 100.0, 'b': 0.0, 'c': 50.0, 'd': None}
    """
    if reference is None:
        return dict.fromkeys(values)
    dist = {k: abs(v - reference) for k, v in values.items() if v is not None and math.isfinite(v)}
    if not dist:
        return dict.fromkeys(values)
    best, worst = min(dist.values()), max(dist.values())
    span = worst - best
    return {
        k: (None if k not in dist else 100.0 if span == 0 else 100 * (worst - dist[k]) / span)
        for k in values
    }


def closeness_grade(
    scores: Sequence[float | None], weights: Sequence[float] | None = None
) -> float | None:
    """Weighted mean of the per-KPI scores of one submission (missing scores left out).

    `weights`: one per score (default: all 1).

    >>> closeness_grade([100.0, 50.0, None])
    75.0
    >>> closeness_grade([100.0, 50.0], [3.0, 1.0])
    87.5
    """
    w = list(weights) if weights is not None else [1.0] * len(scores)
    if len(w) != len(scores):
        raise ValueError("closeness_grade: one weight per score")
    pairs = [(s, wi) for s, wi in zip(scores, w, strict=True) if s is not None and wi > 0]
    total = sum(wi for _, wi in pairs)
    return sum(s * wi for s, wi in pairs) / total if total else None
