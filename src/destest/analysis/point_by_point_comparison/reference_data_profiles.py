"""The reference data profile of a CME: point by point, from all submissions.

Same principle as `reference_time_series`: no truth is known, so the reference is the
**median** (or the mean, from `analysis.reference` in the CME spec file) of all valid
submissions, here position by position along the profile.

    >>> reference_data_profile([[70.0, 69.0], [70.0, 68.0], [71.0, 69.5]])
    [70.0, 69.0]
"""

from collections.abc import Sequence

from .point_by_point_difference import Values, central_value


def reference_data_profile(
    profiles: Sequence[Values], method: str = "median"
) -> list[float | None]:
    """Position-by-position median (or mean) of profiles with the same points."""
    if not profiles:
        return []
    n = len(profiles[0])
    if any(len(p) != n for p in profiles):
        raise ValueError("reference_data_profile: all profiles must have the same points")
    return [central_value([p[i] for p in profiles], method) for i in range(n)]
