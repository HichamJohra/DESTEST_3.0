"""Compare the data profiles of submissions with the reference profile of a CME.

For one profile (e.g. the supply temperature at the nodes along the network): each
submission's profile is read from its columns (`data_profiles.profile_values`), the
reference is built position by position from all valid submissions
(`reference_data_profiles`, method from the CME spec file), then each chosen metric of
`point_by_point_difference` is computed for each submission against it.

    >>> subs = {"a": {"T1": [70.0], "T2": [60.0]}, "b": {"T1": [72.0], "T2": [60.0]}}
    >>> c = compare_data_profiles(subs, ["T1", "T2"], [MetricRequest("MBE")], method="mean")
    >>> c.reference, c.values["MBE"]["b"]
    ([71.0, 60.0], 0.5)
"""

from collections.abc import Mapping, Sequence

from .data_profiles import profile_metric, profile_values
from .point_by_point_difference import Values
from .reference_data_profiles import reference_data_profile
from .time_series_to_reference import MetricRequest, SeriesComparison


def compare_data_profiles(
    compared: Mapping[str, Mapping[str, Values]],
    points: Sequence[str],
    metrics: Sequence[MetricRequest],
    method: str = "median",
    pool: Sequence[Mapping[str, Values]] | None = None,
    aggregate: str = "mean",
) -> SeriesComparison:
    """Each metric of each compared submission (id -> its columns) against the reference.

    `points`: the column keys of the profile, in order. `pool`: the submissions (columns)
    the reference is built from (default: all compared ones).
    """
    profiles = {sid: profile_values(cols, points, aggregate) for sid, cols in compared.items()}
    source = (
        list(profiles.values())
        if pool is None
        else [profile_values(cols, points, aggregate) for cols in pool]
    )
    reference = reference_data_profile(source, method)
    values: dict[str, dict[str, float | None]] = {}
    ideal: dict[str, float | None] = {}
    for m in metrics:
        metric = profile_metric(m.name)
        values[m.name] = {sid: metric(p, reference, **m.params) for sid, p in profiles.items()}
        ideal[m.name] = metric.ideal(reference)
    return SeriesComparison(reference, values, ideal)


__all__ = ["MetricRequest", "compare_data_profiles"]
