"""Comparison metrics that need the time axis of a series (time series only).

Every metric of `point_by_point_difference` applies to time series as they are. This
module adds the metrics that depend on time:

* metrics on time-aggregated data, as in the DESTEST comparison tool (Johra et al., 2021):
  `HourlyCVRMSE` (CVRMSE of hourly means: tolerant to small time shifts), `CVRMSE_24hAmp`
  and `RMSE_24hAmp` (on the daily amplitude max - min: how well the dynamics are predicted);
* elastic distances, for series shifted or stretched in time (Johra et al., 2021, after
  Mori, Mendiburu and Lozano, 2016, R package TSdist): `DTW` (dynamic time warping),
  `Frechet` (discrete Frechet distance), `COR` (dissimilarity based on Pearson's
  correlation) and `CORT` (temporal correlation and raw values, Chouakria & Nagabhushan).

Every metric takes `time` (seconds, same length as the series) as a keyword argument;
y = simulated, x = reference, as in `point_by_point_difference`.

    >>> t = [0.0, 1800.0, 3600.0, 5400.0]
    >>> f = TIME_SERIES_METRICS["HourlyCVRMSE"]
    >>> f([1.0, 3.0, 2.0, 2.0], [2.0, 2.0, 2.0, 2.0], time=t)
    0.0

References
----------
* H. Johra et al. (2021). Evaluating different metrics for inter-model comparison of
  urban-scale building energy simulation time series. Building Simulation 2021.
  https://doi.org/10.26868/25222708.2021.30410
* H. Johra et al. (2023). Coherent description of 48 metrics to compare, validate and assess
  accuracy of building energy models and indoor environment simulations. DCE Technical
  Report No. 314, Aalborg University. https://doi.org/10.54337/aau533917780
* H. Johra et al. (2023). What metrics does the building energy performance community use
  to compare dynamic models? Building Simulation 2023, 861-868.
  https://doi.org/10.26868/25222708.2023.1309
* U. Mori, A. Mendiburu, J.A. Lozano (2016). Distance measures for time series in R: the
  TSdist package. The R Journal 8(2), 451-459.
* A. Douzal-Chouakria, P.N. Nagabhushan (2007). Adaptive dissimilarity index for measuring
  time series proximity. Advances in Data Analysis and Classification 1, 5-21.
"""

import math
from collections.abc import Callable

import numpy as np

from .point_by_point_difference import (
    POINT_METRICS,
    Array,
    Metric,
    MetricFunction,
    Values,
    cvrmse,
    pairs,
    rmse,
)

#: name -> time-series metric (each needs `time`). Filled by `@time_series_metric`.
TIME_SERIES_METRICS: dict[str, Metric] = {}

HOUR = 3600.0
DAY = 86400.0


def time_series_metric(
    name: str,
    *,
    full_name: str,
    group: str,
    equation: str,
    unit: str,
    value_range: str,
    optimum: float,
    note: str = "",
) -> Callable[[MetricFunction], MetricFunction]:
    """Register f(y, x, *, time, **params) -> float | None as a time-series metric."""

    def register(f: MetricFunction) -> MetricFunction:
        TIME_SERIES_METRICS[name] = Metric(
            name, full_name, group, equation, unit, value_range, optimum, f, (), note
        )
        return f

    return register


def all_time_series_metrics() -> dict[str, Metric]:
    """Every metric usable on time series: the point-by-point ones and the time-aware ones."""
    return {**POINT_METRICS, **TIME_SERIES_METRICS}


# ---- aggregation in time -------------------------------------------------------------------
def block_values(
    values: Values, time: Values, period: float, how: str = "mean"
) -> dict[int, float]:
    """Values grouped by time block of `period` seconds (block k: k*period <= t < (k+1)*period).

    `how`: `mean` (e.g. hourly means) or `amplitude` (max - min, e.g. daily amplitude).

    >>> block_values([1.0, 3.0, 5.0], [0.0, 1800.0, 3600.0], 3600.0)
    {0: 2.0, 1: 5.0}
    """
    groups: dict[int, list[float]] = {}
    for v, t in zip(values, time, strict=False):
        if v is None or t is None or not math.isfinite(v):
            continue
        groups.setdefault(math.floor(t / period), []).append(v)
    if how == "mean":
        return {k: sum(g) / len(g) for k, g in groups.items()}
    if how == "amplitude":
        return {k: max(g) - min(g) for k, g in groups.items()}
    raise ValueError(f"block_values: how must be 'mean' or 'amplitude' (got '{how}')")


def _blocked(
    y: Values, x: Values, time: Values, period: float, how: str
) -> tuple[list[float], list[float]]:
    by, bx = block_values(y, time, period, how), block_values(x, time, period, how)
    keys = sorted(set(by) & set(bx))
    return [by[k] for k in keys], [bx[k] for k in keys]


@time_series_metric(
    "HourlyCVRMSE",
    full_name="CVRMSE of hourly-averaged data",
    group="Time-aggregated (DESTEST)",
    equation="CVRMSE of the hourly means of y and x",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Johra et al. (2021): smooths small time shifts. `period` in s (default 3600).",
)
def hourly_cvrmse(y: Values, x: Values, *, time: Values, period: float = HOUR) -> float | None:
    by, bx = _blocked(y, x, time, period, "mean")
    return cvrmse(by, bx)


@time_series_metric(
    "CVRMSE_24hAmp",
    full_name="CVRMSE of the daily amplitude",
    group="Time-aggregated (DESTEST)",
    equation="CVRMSE of (max - min) per day of y and x",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Johra et al. (2021): days from t = 0 (midnight); `period` in s (default 86400).",
)
def cvrmse_24h_amp(y: Values, x: Values, *, time: Values, period: float = DAY) -> float | None:
    by, bx = _blocked(y, x, time, period, "amplitude")
    return cvrmse(by, bx)


@time_series_metric(
    "RMSE_24hAmp",
    full_name="RMSE of the daily amplitude",
    group="Time-aggregated (DESTEST)",
    equation="RMSE of (max - min) per day of y and x",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Johra et al. (2021): days from t = 0 (midnight); `period` in s (default 86400).",
)
def rmse_24h_amp(y: Values, x: Values, *, time: Values, period: float = DAY) -> float | None:
    by, bx = _blocked(y, x, time, period, "amplitude")
    return rmse(by, bx)


# ---- elastic distances ---------------------------------------------------------------------
def _clean(y: Values, x: Values) -> tuple[Array, Array]:
    return pairs(y, x)


@time_series_metric(
    "DTW",
    full_name="Dynamic Time Warping distance",
    group="Elastic distance",
    equation="DTW = min over warping paths of sum |y_i - x_j| (absolute cost)",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Optional Sakoe-Chiba `window` (points); O(n * window) memory-light computation.",
)
def dtw(y: Values, x: Values, *, time: Values, window: int | None = None) -> float | None:
    ya, xa = _clean(y, x)
    n = ya.size
    if n == 0:
        return None
    w = n if window is None else max(int(window), 0)
    inf = math.inf
    prev = np.full(n + 1, inf)
    prev[0] = 0.0
    for i in range(1, n + 1):
        cur = np.full(n + 1, inf)
        lo, hi = max(1, i - w), min(n, i + w)
        for j in range(lo, hi + 1):
            cost = abs(float(ya[i - 1]) - float(xa[j - 1]))
            cur[j] = cost + min(prev[j], cur[j - 1], prev[j - 1])
        prev = cur
    return float(prev[n])


@time_series_metric(
    "Frechet",
    full_name="Discrete Frechet distance",
    group="Elastic distance",
    equation="Frechet = min over couplings of max |y_i - x_j|",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Discrete version (Eiter and Mannila, 1994), on the values only.",
)
def frechet(y: Values, x: Values, *, time: Values) -> float | None:
    ya, xa = _clean(y, x)
    n = ya.size
    if n == 0:
        return None
    prev = np.empty(n)
    for i in range(n):
        cur = np.empty(n)
        for j in range(n):
            d = abs(float(ya[i]) - float(xa[j]))
            if i == 0 and j == 0:
                cur[j] = d
            elif i == 0:
                cur[j] = max(cur[j - 1], d)
            elif j == 0:
                cur[j] = max(prev[j], d)
            else:
                cur[j] = max(min(prev[j], prev[j - 1], cur[j - 1]), d)
        prev = cur
    return float(prev[n - 1])


@time_series_metric(
    "COR",
    full_name="Dissimilarity based on Pearson's correlation",
    group="Elastic distance",
    equation="COR = sqrt(2 (1 - r_xy))",
    unit="-",
    value_range="[0, 2]",
    optimum=0.0,
    note="As CorDistance of TSdist (Mori et al., 2016).",
)
def cor_distance(y: Values, x: Values, *, time: Values) -> float | None:
    r = POINT_METRICS["r"](y, x)
    return None if r is None else math.sqrt(max(0.0, 2.0 * (1.0 - r)))


@time_series_metric(
    "CORT",
    full_name="Dissimilarity combining temporal correlation and raw values",
    group="Elastic distance",
    equation="CORT = 2 / (1 + exp(k * cort)) * sqrt(sum (y_i - x_i)^2), "
    "cort = sum dy_t dx_t / sqrt(sum dy_t^2 sum dx_t^2)",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Douzal-Chouakria & Nagabhushan (2007); k = 2 by default (k = 0: Euclidean).",
)
def cort_distance(y: Values, x: Values, *, time: Values, k: float = 2.0) -> float | None:
    ya, xa = _clean(y, x)
    if ya.size < 2:
        return None
    dy, dx = np.diff(ya), np.diff(xa)
    den = math.sqrt(float(np.sum(dy**2)) * float(np.sum(dx**2)))
    cort = float(np.sum(dy * dx)) / den if den else 0.0
    return 2.0 / (1.0 + math.exp(k * cort)) * math.sqrt(float(np.sum((ya - xa) ** 2)))


def series_metric(name: str) -> Metric:
    """A metric usable on time series, by name (point-by-point or time-aware)."""
    known = all_time_series_metrics()
    if name not in known:
        raise KeyError(f"unknown time-series metric '{name}' (known: {', '.join(known)})")
    return known[name]
