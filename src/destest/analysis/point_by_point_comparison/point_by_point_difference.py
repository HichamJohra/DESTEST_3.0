"""Point-by-point comparison metrics: how far a series y is from a reference series x.

The metrics of the review by Johra et al. (2023), with the notation, names, units, ranges
and optimum values of its supplementary Technical Report 314:

* x = reference (true) values, y = simulated (predicted) values, both of length n;
* x-bar, y-bar = means; sigma_x, sigma_y = standard deviations;
* errors are y - x: a positive bias means that the model over-predicts.

The series are compared point by point: element i of y with element i of x. Pairs where
y or x is missing (None, NaN) are left out. Nothing here knows about time or positions:
`time_series.py` and `data_profiles.py` add what depends on them.

Every metric is registered in `POINT_METRICS` under its main acronym (e.g. `CVRMSE`) with
its description (`Metric`), so the CME spec files, the dashboards and the documentation
use the same names and definitions.

    >>> round(POINT_METRICS["MBE"]([2.0, 4.0], [2.0, 2.0]), 3)
    1.0
    >>> round(POINT_METRICS["CVRMSE"]([2.0, 4.0], [2.0, 2.0]), 2)
    70.71

Corrections and choices with respect to Technical Report 314 (Table 1), see `note` of the
metrics concerned: MaxAPE and MedianAPE as percentages of |x| (range [0, +inf]); RNRMSE
labelled correctly; IA as Willmott's index of agreement 1 - ... (optimum 100 %); R2 as
1 - RSS/TSS; optimum of Cov and Var = the reference's own value; optimum of Theil's Uc = 1;
CRM and the threshold error dimensionless. MANMAE is computed as printed (identical to
NMAE). nCPBES is not implemented (no equation in the report).

References
----------
* H. Johra, M. Mans, K. Filonenko, I. De Jaeger, D. Saelens, T. Tvedebrink (2021).
  Evaluating different metrics for inter-model comparison of urban-scale building energy
  simulation time series. Proceedings of Building Simulation 2021, Bruges, Belgium.
  https://doi.org/10.26868/25222708.2021.30410
* H. Johra, M. Schaffer, G. Chaudhary, H. Syed Kazmi, J. Le Dreau, S. Petersen (2023).
  Coherent description of 48 metrics to compare, validate and assess accuracy of building
  energy models and indoor environment simulations. DCE Technical Report No. 314, Aalborg
  University. https://doi.org/10.54337/aau533917780
* H. Johra, M. Schaffer, G. Chaudhary, H.S. Kazmi, J. Le Dreau, S. Petersen (2023). What
  metrics does the building energy performance community use to compare dynamic models?
  Proceedings of Building Simulation 2023, Shanghai, China, 861-868.
  https://doi.org/10.26868/25222708.2023.1309
"""

import inspect
import math
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

Values = Sequence[float | None]
Array = npt.NDArray[np.float64]
MetricFunction = Callable[..., float | None]

#: Reference methods: how the reference is built from all submissions, point by point.
REFERENCE_METHODS = ("median", "mean")


def central_value(values: Sequence[float | None], method: str = "median") -> float | None:
    """Median (or mean) of the values that are not missing: one point of a reference.

    >>> central_value([1.0, 5.0, None, 2.0])
    2.0
    """
    v = [x for x in values if x is not None and math.isfinite(x)]
    if not v:
        return None
    if method not in REFERENCE_METHODS:
        raise ValueError(f"reference method must be one of {', '.join(REFERENCE_METHODS)}")
    return statistics.median(v) if method == "median" else statistics.fmean(v)


@dataclass(frozen=True)
class Metric:
    """A comparison metric and its description (as in Technical Report 314, Table 1)."""

    name: str  # main acronym, used in the spec files, e.g. "CVRMSE"
    full_name: str
    group: str  # e.g. "Bias based"
    equation: str  # plain text, x = reference, y = simulated
    unit: str  # "X" (unit of the data), "X^2", "%" or "-" (dimensionless)
    value_range: str
    optimum: float | None  # value for a perfect fit; None: see `optimum_from_reference`
    function: MetricFunction = field(repr=False)
    alternative_names: tuple[str, ...] = ()
    note: str = ""  # correction or choice with respect to the report
    #: For metrics whose ideal value depends on the reference (e.g. Var): x -> optimum.
    optimum_from_reference: Callable[[Array], float] | None = field(default=None, repr=False)

    def __call__(self, y: Values, x: Values, **params: Any) -> float | None:
        return self.function(y, x, **params)

    @property
    def parameters(self) -> set[str]:
        """Keyword parameters the metric accepts (for checking spec files)."""
        sig = inspect.signature(self.function)
        return {p.name for p in sig.parameters.values() if p.kind == p.KEYWORD_ONLY}

    def ideal(self, x: Values) -> float | None:
        """The value of a perfect fit against reference x (for the accuracy grade)."""
        if self.optimum_from_reference is not None:
            _, xa = pairs(x, x)
            return self.optimum_from_reference(xa) if xa.size > 1 else None
        return self.optimum

    def unit_for(self, data_unit: str) -> str:
        """The unit to show: e.g. `X` -> `degC`, `X^2` -> `degC^2`."""
        if self.unit == "X":
            return data_unit
        if self.unit == "X^2":
            return f"({data_unit})^2" if data_unit else ""
        return "" if self.unit == "-" else self.unit


#: name -> metric, in the order of Technical Report 314. Filled by `@point_metric`.
POINT_METRICS: dict[str, Metric] = {}


def point_metric(
    name: str,
    *,
    full_name: str,
    group: str,
    equation: str,
    unit: str,
    value_range: str,
    optimum: float | None,
    alternative_names: tuple[str, ...] = (),
    note: str = "",
    optimum_from_reference: Callable[[Array], float] | None = None,
) -> Callable[[MetricFunction], MetricFunction]:
    """Register a function f(y, x, **params) -> float | None as a comparison metric."""

    def register(f: MetricFunction) -> MetricFunction:
        POINT_METRICS[name] = Metric(
            name,
            full_name,
            group,
            equation,
            unit,
            value_range,
            optimum,
            f,
            alternative_names,
            note,
            optimum_from_reference,
        )
        return f

    return register


# ---- helpers ------------------------------------------------------------------------------
def pairs(y: Values, x: Values) -> tuple[Array, Array]:
    """y and x as arrays, without the pairs where one of them is missing.

    >>> pairs([1.0, None, 3.0], [1.0, 2.0, float("nan")])
    (array([1.]), array([1.]))
    """
    n = min(len(y), len(x))
    ya = np.array([np.nan if v is None else v for v in list(y)[:n]], dtype=float)
    xa = np.array([np.nan if v is None else v for v in list(x)[:n]], dtype=float)
    ok = np.isfinite(ya) & np.isfinite(xa)
    return ya[ok], xa[ok]


def _ratio(num: float, den: float, scale: float = 1.0) -> float | None:
    return None if den == 0 or not math.isfinite(den) else num / den * scale


def _mae(y: Array, x: Array) -> float:
    return float(np.mean(np.abs(y - x)))


def _mbe(y: Array, x: Array) -> float:
    return float(np.mean(y - x))


def _mse(y: Array, x: Array) -> float:
    return float(np.mean((y - x) ** 2))


def _rmse(y: Array, x: Array) -> float:
    return math.sqrt(_mse(y, x))


def _sd(a: Array, ddof: int) -> float:
    return float(np.std(a, ddof=ddof))


def ranks(a: Array) -> Array:
    """Ranks 1..n, ties get their average rank (for Spearman's coefficient).

    >>> ranks(np.array([10.0, 30.0, 20.0, 20.0]))
    array([1. , 4. , 2.5, 2.5])
    """
    order = np.argsort(a, kind="mergesort")
    r = np.empty(a.size, dtype=float)
    r[order] = np.arange(1, a.size + 1, dtype=float)
    for value in np.unique(a):
        tied = a == value
        if tied.sum() > 1:
            r[tied] = r[tied].mean()
    return r


def _pearson(y: Array, x: Array) -> float | None:
    if y.size < 2:
        return None
    dy, dx = y - y.mean(), x - x.mean()
    den = math.sqrt(float(np.sum(dx**2)) * float(np.sum(dy**2)))
    return _ratio(float(np.sum(dx * dy)), den)


def _discordant_pairs(y: Array, x: Array) -> int:
    """Pairs (i, j) ordered one way by x and the other way by y (merge-sort count)."""
    order = np.lexsort((y, x))  # by x, then y: tied x are never counted as discordant
    seq = [float(v) for v in y[order]]

    def count(a: list[float]) -> tuple[list[float], int]:
        if len(a) < 2:
            return a, 0
        mid = len(a) // 2
        left, cl = count(a[:mid])
        right, cr = count(a[mid:])
        merged: list[float] = []
        inv = cl + cr
        i = j = 0
        while i < len(left) and j < len(right):
            if right[j] < left[i]:  # strict: tied y are not discordant
                merged.append(right[j])
                inv += len(left) - i
                j += 1
            else:
                merged.append(left[i])
                i += 1
        merged += left[i:] + right[j:]
        return merged, inv

    return count(seq)[1]


# ---- absolute error based -----------------------------------------------------------------
@point_metric(
    "MaxAE",
    full_name="Maximum Absolute Error",
    group="Absolute error based",
    equation="MaxAE = max |y_i - x_i|",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
)
def max_ae(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return float(np.max(np.abs(ya - xa))) if ya.size else None


@point_metric(
    "ThresholdError",
    full_name="Threshold percentage error (e.g. 0.5 C percentage error)",
    group="Absolute error based",
    equation="share of points with |y_i - x_i| > threshold = #{|y_i - x_i| > threshold} / n",
    unit="-",
    value_range="[0, 1]",
    optimum=0.0,
    alternative_names=("0.5C Percentage Error",),
    note="Threshold as a parameter (report: 0.5 C or 1 C); result is a share (0-1).",
)
def threshold_error(y: Values, x: Values, *, threshold: float = 0.5) -> float | None:
    ya, xa = pairs(y, x)
    return float(np.mean(np.abs(ya - xa) > threshold)) if ya.size else None


@point_metric(
    "MAE",
    full_name="Mean Absolute Error",
    group="Absolute error based",
    equation="MAE = sum |y_i - x_i| / n",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
)
def mae(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _mae(ya, xa) if ya.size else None


@point_metric(
    "NMAE",
    full_name="Normalised Mean Absolute Error",
    group="Absolute error based",
    equation="NMAE = sum |y_i - x_i| / sum x_i * 100 % = MAE / x-bar * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("MAE%",),
)
def nmae(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_mae(ya, xa), float(np.mean(xa)), 100.0) if ya.size else None


@point_metric(
    "MANMAE",
    full_name="Mean Absolute Normalized MAE",
    group="Absolute error based",
    equation="MANMAE = sum |y_i - x_i| / sum x_i * 100 % (as printed in the report)",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="The report prints the same equation as NMAE; computed as printed.",
)
def manmae(y: Values, x: Values) -> float | None:
    return nmae(y, x)


@point_metric(
    "RNMAE",
    full_name="Range Normalized Mean Absolute Error",
    group="Absolute error based",
    equation="RNMAE = MAE / (max x - min x) * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("NMAE",),
)
def rnmae(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_mae(ya, xa), float(np.ptp(xa)), 100.0) if ya.size else None


@point_metric(
    "ZMAE",
    full_name="MAE normalised by the standard deviation of the reference",
    group="Absolute error based",
    equation="ZMAE = MAE / sigma_x * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="sigma_x with n - 1 (as Var in the report); ddof = 0 for n.",
)
def zmae(y: Values, x: Values, *, ddof: int = 1) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_mae(ya, xa), _sd(xa, ddof), 100.0) if ya.size > ddof else None


@point_metric(
    "rMAE",
    full_name="Relative Mean Absolute Error",
    group="Absolute error based",
    equation="rMAE = MAE(model) / MAE(baseline)",
    unit="-",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("relative MAE",),
    note="Needs the series of a baseline model (`baseline`); None without it.",
)
def rmae(y: Values, x: Values, *, baseline: Values | None = None) -> float | None:
    if baseline is None:
        return None
    ya, xa = pairs(y, x)
    ba, xb = pairs(baseline, x)
    if not ya.size or not ba.size:
        return None
    return _ratio(_mae(ya, xa), _mae(ba, xb))


# ---- bias based ---------------------------------------------------------------------------
@point_metric(
    "MBE",
    full_name="Mean Bias Error",
    group="Bias based",
    equation="MBE = sum (y_i - x_i) / n",
    unit="X",
    value_range="[-inf, +inf]",
    optimum=0.0,
)
def mbe(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _mbe(ya, xa) if ya.size else None


@point_metric(
    "NMBE",
    full_name="Normalised Mean Bias Error",
    group="Bias based",
    equation="NMBE = MBE / x-bar * 100 %",
    unit="%",
    value_range="[-inf, +inf]",
    optimum=0.0,
    alternative_names=("RPE", "RAE"),
)
def nmbe(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_mbe(ya, xa), float(np.mean(xa)), 100.0) if ya.size else None


@point_metric(
    "RNMBE",
    full_name="Range Normalized Mean Bias Error",
    group="Bias based",
    equation="RNMBE = MBE / (max x - min x) * 100 %",
    unit="%",
    value_range="[-inf, +inf]",
    optimum=0.0,
)
def rnmbe(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_mbe(ya, xa), float(np.ptp(xa)), 100.0) if ya.size else None


# ---- absolute percentage error ------------------------------------------------------------
def _ape(y: Values, x: Values) -> Array | None:
    ya, xa = pairs(y, x)
    ok = xa != 0
    return np.abs(ya[ok] - xa[ok]) / np.abs(xa[ok]) * 100.0 if ok.any() else None


@point_metric(
    "MaxAPE",
    full_name="Maximum Absolute Percentage Error",
    group="Absolute percentage error",
    equation="MaxAPE = max |y_i - x_i| / |x_i| * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="In % of |x_i| (report: unit X, no factor 100); points with x_i = 0 left out.",
)
def max_ape(y: Values, x: Values) -> float | None:
    e = _ape(y, x)
    return float(np.max(e)) if e is not None else None


@point_metric(
    "MedianAPE",
    full_name="Median Absolute Percentage Error",
    group="Absolute percentage error",
    equation="MedianAPE = median |y_i - x_i| / |x_i| * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("med(absRTE)", "MdAPE"),
    note="Range [0, +inf] (report: [-inf, +inf]); in %; points with x_i = 0 left out.",
)
def median_ape(y: Values, x: Values) -> float | None:
    e = _ape(y, x)
    return float(np.median(e)) if e is not None else None


@point_metric(
    "MAPE",
    full_name="Mean Absolute Percentage Error",
    group="Absolute percentage error",
    equation="MAPE = sum |y_i - x_i| / |x_i| / n * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("MAPD",),
    note="Points with x_i = 0 left out.",
)
def mape(y: Values, x: Values) -> float | None:
    e = _ape(y, x)
    return float(np.mean(e)) if e is not None else None


# ---- square error based -------------------------------------------------------------------
@point_metric(
    "MSE",
    full_name="Mean Square Error",
    group="Square error based",
    equation="MSE = sum (y_i - x_i)^2 / n",
    unit="X^2",
    value_range="[0, +inf]",
    optimum=0.0,
)
def mse(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _mse(ya, xa) if ya.size else None


def _tss(xa: Array) -> float:
    return float(np.sum((xa - xa.mean()) ** 2))


@point_metric(
    "NMSE",
    full_name="Normalised Mean Square Error",
    group="Square error based",
    equation="NMSE = sum (y_i - x_i)^2 / sum (x_i - x-bar)^2 * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
)
def nmse(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(float(np.sum((ya - xa) ** 2)), _tss(xa), 100.0) if ya.size else None


@point_metric(
    "IA",
    full_name="Index of Agreement (Willmott)",
    group="Square error based",
    equation="IA = (1 - sum (y_i - x_i)^2 / sum (|y_i - x-bar| + |x_i - x-bar|)^2) * 100 %",
    unit="%",
    value_range="[0, 100]",
    optimum=100.0,
    note="Willmott's index 1 - ... (the report prints the ratio alone, optimum 0).",
)
def index_of_agreement(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    if not ya.size:
        return None
    den = float(np.sum((np.abs(ya - xa.mean()) + np.abs(xa - xa.mean())) ** 2))
    ratio = _ratio(float(np.sum((ya - xa) ** 2)), den)
    return None if ratio is None else (1.0 - ratio) * 100.0


@point_metric(
    "EF",
    full_name="Modelling efficiency (Nash-Sutcliffe)",
    group="Square error based",
    equation="EF = (sum (x_i - x-bar)^2 - sum (y_i - x_i)^2) / sum (x_i - x-bar)^2 * 100 %",
    unit="%",
    value_range="[-inf, 100]",
    optimum=100.0,
)
def modelling_efficiency(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    if not ya.size:
        return None
    tss = _tss(xa)
    return _ratio(tss - float(np.sum((ya - xa) ** 2)), tss, 100.0)


def _theil(y: Values, x: Values) -> tuple[float, float, float] | None:
    """(Um, Uv, Uc), with population standard deviations so that Um + Uv + Uc = 1."""
    ya, xa = pairs(y, x)
    if ya.size < 2:
        return None
    m = _mse(ya, xa)
    r = _pearson(ya, xa)
    if m == 0 or r is None:
        return None
    sy, sx = _sd(ya, 0), _sd(xa, 0)
    return (
        (float(ya.mean()) - float(xa.mean())) ** 2 / m,
        (sy - sx) ** 2 / m,
        2 * (1 - r) * sy * sx / m,
    )


_THEIL_NOTE = "Population standard deviations (n), so that Um + Uv + Uc = 1."


@point_metric(
    "TheilUm",
    full_name="Theil's coefficient of inequality: bias proportion Um",
    group="Square error based",
    equation="Um = (y-bar - x-bar)^2 / MSE",
    unit="-",
    value_range="[0, 1]",
    optimum=0.0,
    note=_THEIL_NOTE + " Undefined for a perfect match (MSE = 0).",
)
def theil_um(y: Values, x: Values) -> float | None:
    u = _theil(y, x)
    return u[0] if u else None


@point_metric(
    "TheilUv",
    full_name="Theil's coefficient of inequality: variance proportion Uv",
    group="Square error based",
    equation="Uv = (sigma_y - sigma_x)^2 / MSE",
    unit="-",
    value_range="[0, 1]",
    optimum=0.0,
    note=_THEIL_NOTE,
)
def theil_uv(y: Values, x: Values) -> float | None:
    u = _theil(y, x)
    return u[1] if u else None


@point_metric(
    "TheilUc",
    full_name="Theil's coefficient of inequality: covariance proportion Uc",
    group="Square error based",
    equation="Uc = 2 (1 - r_xy) sigma_y sigma_x / MSE",
    unit="-",
    value_range="[0, 1]",
    optimum=1.0,
    note=_THEIL_NOTE + " Optimum 1: all remaining error unsystematic (report: garbled).",
)
def theil_uc(y: Values, x: Values) -> float | None:
    u = _theil(y, x)
    return u[2] if u else None


@point_metric(
    "RMSE",
    full_name="Root Mean Square Error",
    group="Square error based",
    equation="RMSE = sqrt(sum (y_i - x_i)^2 / n) = sqrt(MSE)",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("RMSD", "DRMS"),
)
def rmse(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _rmse(ya, xa) if ya.size else None


@point_metric(
    "RMSEP",
    full_name="Root Mean Square Error Percentage",
    group="Square error based",
    equation="RMSEP = sqrt(sum ((y_i - x_i) / x_i)^2 / n) * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Points with x_i = 0 left out.",
)
def rmsep(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    ok = xa != 0
    if not ok.any():
        return None
    return math.sqrt(float(np.mean(((ya[ok] - xa[ok]) / xa[ok]) ** 2))) * 100.0


@point_metric(
    "RNRMSE",
    full_name="Range Normalized Root Mean Square Error",
    group="Square error based",
    equation="RNRMSE = RMSE / (max x - min x) * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="The report labels this equation 'RMSEP'.",
)
def rnrmse(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_rmse(ya, xa), float(np.ptp(xa)), 100.0) if ya.size else None


@point_metric(
    "CVRMSE",
    full_name="Coefficient of Variation of Root Mean Square Error",
    group="Square error based",
    equation="CVRMSE = RMSE / x-bar * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("(CV)RMSE", "NRMSE", "RMSE%", "RRMSE"),
)
def cvrmse(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_rmse(ya, xa), float(np.mean(xa)), 100.0) if ya.size else None


@point_metric(
    "RMSEIQR",
    full_name="Root Mean Square Error normalised by the interquartile range",
    group="Square error based",
    equation="RMSEIQR = RMSE / IQR(x) * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
)
def rmse_iqr(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    if not ya.size:
        return None
    q75, q25 = np.percentile(xa, [75, 25])
    return _ratio(_rmse(ya, xa), float(q75 - q25), 100.0)


@point_metric(
    "RMSLE",
    full_name="Root Mean Square Logarithmic Error",
    group="Square error based",
    equation="RMSLE = sqrt(sum (log(y_i + 1) - log(x_i + 1))^2 / n)",
    unit="-",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Natural logarithm; only for values above -1. Dimensionless (report: unit X).",
)
def rmsle(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    if not ya.size or float(np.min(ya)) <= -1 or float(np.min(xa)) <= -1:
        return None
    return math.sqrt(float(np.mean((np.log1p(ya) - np.log1p(xa)) ** 2)))


@point_metric(
    "ZRMSE",
    full_name="RMSE normalised by the standard deviation of the reference",
    group="Square error based",
    equation="ZRMSE = RMSE / sigma_x * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="sigma_x with n - 1 (as Var in the report); ddof = 0 for n.",
)
def zrmse(y: Values, x: Values, *, ddof: int = 1) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_rmse(ya, xa), _sd(xa, ddof), 100.0) if ya.size > ddof else None


@point_metric(
    "NRMSE",
    full_name="Normalized Root Mean Squared Error",
    group="Square error based",
    equation="NRMSE = sqrt(sum (y_i - x_i)^2) / sqrt(sum (x_i - x-bar)^2) * 100 %",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
)
def nrmse(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    if not ya.size:
        return None
    return _ratio(math.sqrt(float(np.sum((ya - xa) ** 2))), math.sqrt(_tss(xa)), 100.0)


# ---- statistical dispersion -----------------------------------------------------------------
def _var(a: Array) -> float:
    return float(np.var(a, ddof=1))


@point_metric(
    "Var",
    full_name="Variance of the simulated values",
    group="Based on statistical dispersion",
    equation="Var(y) = sum (y_i - y-bar)^2 / (n - 1)",
    unit="X^2",
    value_range="[0, +inf]",
    optimum=None,
    note="Optimum: Var(x), the variance of the reference.",
    optimum_from_reference=_var,
)
def variance(y: Values, x: Values) -> float | None:
    ya, _ = pairs(y, x)
    return _var(ya) if ya.size > 1 else None


@point_metric(
    "sd_ratio",
    full_name="Standard deviation ratio",
    group="Based on statistical dispersion",
    equation="sd_ratio = sigma_y / sigma_x",
    unit="-",
    value_range="]0, +inf]",
    optimum=1.0,
)
def sd_ratio(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(_sd(ya, 1), _sd(xa, 1)) if ya.size > 1 else None


@point_metric(
    "sd_error",
    full_name="Standard deviation of an error metric over periods",
    group="Based on statistical dispersion",
    equation="sd_error = sd(metric on period 1, ..., metric on period k)",
    unit="X",
    value_range="[0, +inf]",
    optimum=0.0,
    note="`metric` computed on consecutive blocks of `period` points; unit of that metric.",
)
def sd_error(y: Values, x: Values, *, metric: str = "MBE", period: int = 24) -> float | None:
    if period < 1:
        raise ValueError("sd_error: period must be at least 1")
    f = POINT_METRICS[metric]
    values = [f(y[i : i + period], x[i : i + period]) for i in range(0, len(x), period)]
    v = [e for e in values if e is not None]
    return statistics.stdev(v) if len(v) > 1 else None


def _cov(ya: Array, xa: Array) -> float:
    return float(np.sum((xa - xa.mean()) * (ya - ya.mean())) / (xa.size - 1))


@point_metric(
    "Cov",
    full_name="Covariance",
    group="Based on statistical dispersion",
    equation="cov(x, y) = sum (x_i - x-bar)(y_i - y-bar) / (n - 1)",
    unit="X^2",
    value_range="[-inf, +inf]",
    optimum=None,
    note="Optimum: Var(x) (report: 1).",
    optimum_from_reference=_var,
)
def covariance(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _cov(ya, xa) if ya.size > 1 else None


# ---- correlation based -------------------------------------------------------------------
@point_metric(
    "r",
    full_name="Pearson correlation coefficient",
    group="Correlation based",
    equation="r_xy = sum (x_i - x-bar)(y_i - y-bar) "
    "/ sqrt(sum (x_i - x-bar)^2 sum (y_i - y-bar)^2)",
    unit="-",
    value_range="[-1, +1]",
    optimum=1.0,
)
def pearson_r(y: Values, x: Values) -> float | None:
    return _pearson(*pairs(y, x))


@point_metric(
    "rs",
    full_name="Spearman's rank correlation coefficient",
    group="Correlation based",
    equation="r_s = r(rank(x), rank(y))",
    unit="-",
    value_range="[-1, +1]",
    optimum=1.0,
    alternative_names=("rho",),
    note="Ties get their average rank.",
)
def spearman_rs(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _pearson(ranks(ya), ranks(xa)) if ya.size > 1 else None


@point_metric(
    "tau",
    full_name="Kendall rank correlation coefficient",
    group="Correlation based",
    equation="tau = 1 - 2 * (number of discordant pairs) / (n (n - 1) / 2)",
    unit="-",
    value_range="[-1, +1]",
    optimum=1.0,
    note="As in the report (tau-a); tied pairs are not counted as discordant.",
)
def kendall_tau(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    n = ya.size
    if n < 2:
        return None
    return 1.0 - 2.0 * _discordant_pairs(ya, xa) / (n * (n - 1) / 2)


# ---- relative difference based ------------------------------------------------------------
def calibration_signature(y: Values, x: Values) -> list[float | None]:
    """Calibration signature, one value per point: -(y_i - x_i) / max(y) * 100 %.

    A series rather than one number (Technical Report 314); not a registered metric.
    """
    ya, _ = pairs(y, y)
    top = float(np.max(ya)) if ya.size else 0.0
    return [
        None if yi is None or xi is None or top == 0 else -(yi - xi) / top * 100.0
        for yi, xi in zip(y, x, strict=False)
    ]


@point_metric(
    "CRM",
    full_name="Coefficient of residual mass",
    group="Relative difference based",
    equation="CRM = (sum y_i - sum x_i) / sum x_i",
    unit="-",
    value_range="[-inf, +inf]",
    optimum=0.0,
    note="Dimensionless (report: unit X).",
)
def crm(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return _ratio(float(np.sum(ya) - np.sum(xa)), float(np.sum(xa))) if ya.size else None


# ---- miscellaneous -------------------------------------------------------------------------
@point_metric(
    "SSE",
    full_name="Sum of Squared Errors",
    group="Miscellaneous",
    equation="SSE = sum (y_i - x_i)^2",
    unit="X^2",
    value_range="[0, +inf]",
    optimum=0.0,
    alternative_names=("SSR", "RSS"),
)
def sse(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    return float(np.sum((ya - xa) ** 2)) if ya.size else None


@point_metric(
    "R2",
    full_name="Coefficient of determination (R squared)",
    group="Miscellaneous",
    equation="R2 = 1 - RSS / TSS = 1 - sum (y_i - x_i)^2 / sum (x_i - x-bar)^2",
    unit="-",
    value_range="[-inf, 1]",
    optimum=1.0,
    note="1 - RSS/TSS (ESS/TSS equals it only for least-squares fits); can be negative.",
)
def r_squared(y: Values, x: Values) -> float | None:
    ya, xa = pairs(y, x)
    if not ya.size:
        return None
    ratio = _ratio(float(np.sum((ya - xa) ** 2)), _tss(xa))
    return None if ratio is None else 1.0 - ratio


@point_metric(
    "GOF",
    full_name="Goodness of Fit",
    group="Miscellaneous",
    equation="GOF = sqrt((w_cv^2 CVRMSE^2 + w_b^2 NMBE^2) / (w_cv^2 + w_b^2))",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
    note="Bias term NMBE (default) or MBE (`bias='MBE'`); weights as parameters.",
)
def gof(
    y: Values, x: Values, *, w_cvrmse: float = 1.0, w_bias: float = 1.0, bias: str = "NMBE"
) -> float | None:
    cv = cvrmse(y, x)
    b = nmbe(y, x) if bias == "NMBE" else mbe(y, x)
    den = w_cvrmse**2 + w_bias**2
    if cv is None or b is None or den == 0:
        return None
    return math.sqrt((w_cvrmse**2 * cv**2 + w_bias**2 * b**2) / den)


@point_metric(
    "ACF",
    full_name="Auto-correlation of the residuals",
    group="Miscellaneous",
    equation="ACF(k) = sum (e_i - e-bar)(e_(i+k) - e-bar) / sum (e_i - e-bar)^2, e = y - x",
    unit="-",
    value_range="[-1, 1]",
    optimum=0.0,
    note="At lag `lag` (default 1); should be close to 0 for non-zero lags.",
)
def residual_autocorrelation(y: Values, x: Values, *, lag: int = 1) -> float | None:
    ya, xa = pairs(y, x)
    e = ya - xa
    if lag < 1 or e.size <= lag:
        return None
    d = e - e.mean()
    return _ratio(float(np.sum(d[:-lag] * d[lag:])), float(np.sum(d**2)))
