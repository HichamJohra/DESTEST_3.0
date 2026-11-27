"""Data aggregates: one value per submission from one series (no reference needed).

Mean, minimum, maximum, steady-state value, final value, sum and time integral of one
column of a result file. The value is then compared between submissions (with the median
of all submissions, or with a target given in the CME spec file).

This module also holds the registry of all general-comparison functions
(`GENERAL_FUNCTIONS`), shared with `physics_check.py`. A function's **inputs** are its
named series (here: `values`; in physics checks e.g. `power`, `m_flow`), given in the spec
file as `column:` (one series) or `inputs:` (several); its **parameters** are its
keyword-only arguments (`params:` in the spec file). Every function also gets `time`.

    >>> GENERAL_FUNCTIONS["integral"].evaluate({"values": [1000.0, 1000.0]}, [0.0, 3600.0],
    ...                                         {"to_unit": "kWh"})
    1.0
"""

import inspect
import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

Values = Sequence[float | None]
GeneralFunction = Callable[..., float | None]

#: Energy units for the integral of a power in W over time in s, in J per unit.
ENERGY_UNITS = {"J": 1.0, "kJ": 1e3, "MJ": 1e6, "Wh": 3600.0, "kWh": 3.6e6, "MWh": 3.6e9}


@dataclass(frozen=True)
class ComparisonFunction:
    """A general-comparison function: named input series + time + keyword parameters."""

    name: str
    kind: str  # "data_aggregate" or "physics_check"
    function: GeneralFunction = field(repr=False)

    def _signature(self) -> list[inspect.Parameter]:
        return list(inspect.signature(self.function).parameters.values())

    @property
    def inputs(self) -> list[str]:
        """Required input series, e.g. `['values']` or `['power', 'm_flow', ...]`."""
        return [
            p.name
            for p in self._signature()
            if p.kind is p.POSITIONAL_OR_KEYWORD and p.name != "time" and p.default is p.empty
        ]

    @property
    def optional_inputs(self) -> list[str]:
        """Input series that may be left out (default None)."""
        return [
            p.name
            for p in self._signature()
            if p.kind is p.POSITIONAL_OR_KEYWORD and p.name != "time" and p.default is None
        ]

    @property
    def parameters(self) -> set[str]:
        """Keyword parameters (`params:` in the spec file)."""
        return {p.name for p in self._signature() if p.kind is p.KEYWORD_ONLY}

    @property
    def required_parameters(self) -> set[str]:
        """Keyword parameters without a default: they must be given in `params:`."""
        return {
            p.name for p in self._signature() if p.kind is p.KEYWORD_ONLY and p.default is p.empty
        }

    @property
    def description(self) -> str:
        """First line of the docstring."""
        return (self.function.__doc__ or "").strip().splitlines()[0]

    def evaluate(
        self, data: Mapping[str, Values], time: Values, params: Mapping[str, Any]
    ) -> float | None:
        """Compute the value from the input series (name -> values) and the time column."""
        return self.function(**data, time=time, **params)


#: name -> function. Filled by `@general_function` here and in `physics_check.py`.
GENERAL_FUNCTIONS: dict[str, ComparisonFunction] = {}


def general_function(name: str, kind: str) -> Callable[[GeneralFunction], GeneralFunction]:
    """Register a general-comparison function under `name`."""

    def register(f: GeneralFunction) -> GeneralFunction:
        GENERAL_FUNCTIONS[name] = ComparisonFunction(name, kind, f)
        return f

    return register


def _valid(values: Values) -> list[float]:
    return [v for v in values if v is not None and math.isfinite(v)]


@general_function("steady_state", "data_aggregate")
def steady_state(values: Values, time: Values, *, last_n: int | None = None) -> float | None:
    """Steady-state value: mean of the last `last_n` values (all values if not given)."""
    v = _valid(values)
    if last_n is not None:
        v = v[-last_n:]
    return sum(v) / len(v) if v else None


@general_function("mean", "data_aggregate")
def mean(values: Values, time: Values) -> float | None:
    """Arithmetic mean of all values."""
    v = _valid(values)
    return sum(v) / len(v) if v else None


@general_function("minimum", "data_aggregate")
def minimum(values: Values, time: Values) -> float | None:
    """Smallest value."""
    v = _valid(values)
    return min(v) if v else None


@general_function("maximum", "data_aggregate")
def maximum(values: Values, time: Values) -> float | None:
    """Largest value."""
    v = _valid(values)
    return max(v) if v else None


@general_function("final_value", "data_aggregate")
def final_value(values: Values, time: Values) -> float | None:
    """Last value."""
    v = _valid(values)
    return v[-1] if v else None


@general_function("total", "data_aggregate")
def total(values: Values, time: Values, *, factor: float = 1.0) -> float | None:
    """Sum of the values, times `factor`."""
    v = _valid(values)
    return sum(v) * factor if v else None


@general_function("integral", "data_aggregate")
def integral(
    values: Values, time: Values, *, to_unit: str | None = None, factor: float = 1.0
) -> float | None:
    """Integral over time (trapezoidal rule), e.g. energy from power.

    With time in s, a power in W gives J; `to_unit` converts that energy (J, kJ, MJ, Wh,
    kWh, MWh). `factor` multiplies the result (for other quantities). Pairs of points with
    a missing value are skipped.
    """
    pts = [
        (t, v)
        for t, v in zip(time, values, strict=False)
        if t is not None and v is not None and math.isfinite(v)
    ]
    if len(pts) < 2:
        return None
    area = sum((t1 - t0) * (v0 + v1) / 2 for (t0, v0), (t1, v1) in itertools.pairwise(pts))
    if to_unit is not None:
        if to_unit not in ENERGY_UNITS:
            raise ValueError(f"integral: to_unit must be one of {', '.join(ENERGY_UNITS)}")
        area /= ENERGY_UNITS[to_unit]
    return area * factor


# ---- difference of one value from its reference ------------------------------------------
def relative_deviation(value: float, reference: float) -> float | None:
    """(value - reference) / |reference| * 100, in %.

    >>> relative_deviation(105.0, 100.0)
    5.0
    """
    return (value - reference) / abs(reference) * 100 if reference else None


def absolute_deviation(value: float, reference: float) -> float | None:
    """value - reference, in the unit of the value."""
    return value - reference


#: name -> (value, reference) -> difference; used by tables and heatmaps.
VALUE_DIFFERENCES: dict[str, Callable[[float, float], float | None]] = {
    "relative_deviation": relative_deviation,
    "absolute_deviation": absolute_deviation,
}
#: Unit of each difference ("" = unit of the value).
VALUE_DIFFERENCE_UNITS = {"relative_deviation": "%", "absolute_deviation": ""}
