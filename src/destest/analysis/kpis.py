"""KPI functions: one number from one time series.

Each function is registered under a name; a CME's spec file refers to it by that
name (`analysis.kpis[].function`), with optional keyword parameters (`params`).
Every function takes the values and the time column of one submission (missing
values are `None` and are skipped) and returns a float, or `None` when there is
nothing to compute from.

    >>> KPI_FUNCTIONS["steady_state"]([1.0, 2.0, 3.0, 3.0], [0, 1, 2, 3], last_n=2)
    3.0
    >>> KPI_FUNCTIONS["integral"]([1.0, 1.0, 1.0], [0, 1, 2])
    2.0

To add a KPI: write a function with this signature and decorate it with
`@kpi_function("name")`. It is then usable from every CME spec file.
"""

import inspect
import itertools
import math
from collections.abc import Callable, Sequence

Values = Sequence[float | None]
KpiFunction = Callable[..., float | None]

#: name -> function. Filled by the `@kpi_function` decorator below.
KPI_FUNCTIONS: dict[str, KpiFunction] = {}


def kpi_function(name: str) -> Callable[[KpiFunction], KpiFunction]:
    """Register a KPI function under `name`."""

    def register(f: KpiFunction) -> KpiFunction:
        KPI_FUNCTIONS[name] = f
        return f

    return register


def parameters(name: str) -> set[str]:
    """The keyword parameters a KPI function accepts (for checking spec files)."""
    sig = inspect.signature(KPI_FUNCTIONS[name])
    return {p.name for p in sig.parameters.values() if p.kind is inspect.Parameter.KEYWORD_ONLY}


def _valid(values: Values) -> list[float]:
    return [v for v in values if v is not None and math.isfinite(v)]


@kpi_function("steady_state")
def steady_state(values: Values, time: Values, *, last_n: int | None = None) -> float | None:
    """Mean of the last `last_n` values (all values if not given): the steady-state value."""
    v = _valid(values)
    if last_n is not None:
        v = v[-last_n:]
    return sum(v) / len(v) if v else None


@kpi_function("mean")
def mean(values: Values, time: Values) -> float | None:
    """Arithmetic mean of all values."""
    v = _valid(values)
    return sum(v) / len(v) if v else None


@kpi_function("minimum")
def minimum(values: Values, time: Values) -> float | None:
    """Smallest value."""
    v = _valid(values)
    return min(v) if v else None


@kpi_function("maximum")
def maximum(values: Values, time: Values) -> float | None:
    """Largest value."""
    v = _valid(values)
    return max(v) if v else None


@kpi_function("final_value")
def final_value(values: Values, time: Values) -> float | None:
    """Last value."""
    v = _valid(values)
    return v[-1] if v else None


@kpi_function("total")
def total(values: Values, time: Values, *, factor: float = 1.0) -> float | None:
    """Sum of the values, times `factor` (e.g. hourly W values * 1e-3 -> kWh)."""
    v = _valid(values)
    return sum(v) * factor if v else None


@kpi_function("integral")
def integral(values: Values, time: Values, *, factor: float = 1.0) -> float | None:
    """Integral over time (trapezoidal rule), times `factor`.

    E.g. power in W over time in s gives J; `factor: 2.7778e-7` gives kWh.
    Pairs of points with a missing value are skipped.
    """
    pts = [
        (t, v)
        for t, v in zip(time, values, strict=False)
        if t is not None and v is not None and math.isfinite(v)
    ]
    if len(pts) < 2:
        return None
    area = sum((t1 - t0) * (v0 + v1) / 2 for (t0, v0), (t1, v1) in itertools.pairwise(pts))
    return area * factor
