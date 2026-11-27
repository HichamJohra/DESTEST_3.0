"""Compare the time series of submissions with the reference time series of a CME.

For one variable (one column of the result files): the reference is built from all valid
submissions (`reference_time_series`, method from the CME spec file), then each chosen
metric (`point_by_point_difference` or `time_series`) is computed for each submission
against it.

    >>> pool = {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 5.0], "c": [2.0, 2.0, 3.0]}
    >>> c = compare_time_series(pool, [0.0, 1.0, 2.0], [MetricRequest("MBE")])
    >>> c.reference
    [1.0, 2.0, 3.0]
    >>> round(c.values["MBE"]["b"], 3)
    0.667

Reference: H. Johra et al. (2021). Evaluating different metrics for inter-model comparison
of urban-scale building energy simulation time series. Building Simulation 2021.
https://doi.org/10.26868/25222708.2021.30410
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .point_by_point_difference import Values
from .reference_time_series import reference_time_series
from .time_series import TIME_SERIES_METRICS, series_metric


@dataclass(frozen=True)
class MetricRequest:
    """A metric chosen in the CME spec file, with its weight in the accuracy grade."""

    name: str
    weight: float = 1.0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeriesComparison:
    """The reference series and, per metric, the value of each submission."""

    reference: list[float | None]
    values: dict[str, dict[str, float | None]]  # metric -> submission id -> value
    ideal: dict[str, float | None]  # metric -> value of a perfect fit


def compare_time_series(
    compared: Mapping[str, Values],
    time: Values,
    metrics: Sequence[MetricRequest],
    method: str = "median",
    pool: Sequence[Values] | None = None,
) -> SeriesComparison:
    """Each metric of each compared series (submission id -> values) against the reference.

    `pool`: the series the reference is built from (default: all compared series).
    """
    reference = reference_time_series(list(compared.values()) if pool is None else pool, method)
    values: dict[str, dict[str, float | None]] = {}
    ideal: dict[str, float | None] = {}
    for m in metrics:
        metric = series_metric(m.name)
        extra = {"time": time} if m.name in TIME_SERIES_METRICS else {}
        values[m.name] = {
            sid: metric(series, reference, **extra, **m.params) for sid, series in compared.items()
        }
        ideal[m.name] = metric.ideal(reference)
    return SeriesComparison(reference, values, ideal)
