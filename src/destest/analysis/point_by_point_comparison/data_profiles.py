"""Data profiles: series of values that are not time series (all other data series).

A data profile is an ordered series of values at labelled positions, e.g. the supply
temperature at the nodes i, h, g, f, e and SimpleDistrict_1 along the network. Each point
of a profile comes from one column of the result file, reduced to one value (by default
the mean of the column, i.e. the steady-state value of a steady-state run).

Profiles are compared with the reference profile point by point, with the metrics of
`point_by_point_difference` (same notation: y = simulated, x = reference). The positions
only name and order the points; no metric uses the distance between them yet.

    >>> profile_values({"T_i": [70.0, 70.0], "T_h": [69.0, 69.2]}, ["T_i", "T_h"])
    [70.0, 69.1]

References
----------
* H. Johra et al. (2023). Coherent description of 48 metrics to compare, validate and assess
  accuracy of building energy models and indoor environment simulations. DCE Technical
  Report No. 314, Aalborg University. https://doi.org/10.54337/aau533917780
* H. Johra et al. (2021). Evaluating different metrics for inter-model comparison of
  urban-scale building energy simulation time series. Building Simulation 2021.
  https://doi.org/10.26868/25222708.2021.30410
"""

import math
from collections.abc import Mapping, Sequence

from .point_by_point_difference import POINT_METRICS, Metric, Values

#: How one column becomes one point of a profile.
POINT_AGGREGATES = ("mean", "last")


def point_value(values: Values, aggregate: str = "mean") -> float | None:
    """One value from a column: its mean (steady state) or its last value."""
    v = [x for x in values if x is not None and math.isfinite(x)]
    if not v:
        return None
    if aggregate == "mean":
        return sum(v) / len(v)
    if aggregate == "last":
        return v[-1]
    raise ValueError(f"aggregate must be one of {', '.join(POINT_AGGREGATES)}")


def profile_values(
    series: Mapping[str, Values], points: Sequence[str], aggregate: str = "mean"
) -> list[float | None]:
    """The profile of one submission: one value per point (column key), in order."""
    return [point_value(series[p], aggregate) if p in series else None for p in points]


def profile_metric(name: str) -> Metric:
    """A metric usable on data profiles, by name (all point-by-point metrics)."""
    if name not in POINT_METRICS:
        known = ", ".join(POINT_METRICS)
        raise KeyError(f"unknown data-profile metric '{name}' (known: {known})")
    return POINT_METRICS[name]
