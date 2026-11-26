"""The reference time series of a CME: point by point, from all submissions.

There is no measured or analytical truth for the DESTEST exercises: the reference is
built from all valid submissions, time step by time step, with the method given in the
CME spec file (`analysis.reference`): the **median** (DESTEST 3.0 choice, robust to single
outliers) or the mean (as in Johra et al., 2021).

    >>> reference_time_series([[1.0, 2.0], [3.0, 2.0], [5.0, None]], method="median")
    [3.0, 2.0]

Reference: H. Johra et al. (2021). Evaluating different metrics for inter-model comparison
of urban-scale building energy simulation time series. Building Simulation 2021.
https://doi.org/10.26868/25222708.2021.30410
"""

from collections.abc import Sequence

from .point_by_point_difference import Values, central_value


def reference_time_series(series: Sequence[Values], method: str = "median") -> list[float | None]:
    """Point-by-point median (or mean) of time series on the same time grid.

    Series of another length than the most common one are left out (they are not on
    the same time grid; `destest check` reports them).
    """
    if not series:
        return []
    lengths = [len(s) for s in series]
    n = max(set(lengths), key=lengths.count)
    usable = [s for s in series if len(s) == n]
    return [central_value([s[i] for s in usable], method) for i in range(n)]
