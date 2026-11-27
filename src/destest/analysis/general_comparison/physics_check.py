"""Physics checks: is a result consistent with physics and with the exercise description?

Each check gives one value per submission from several series (e.g. power, mass flow and
temperatures). Unlike the other comparisons, the ideal value is known: it is given as
`target` in the CME spec file (e.g. 0 % heat-balance error, 30 K over a substation), and
the submission is scored on its distance to that target, not to the median of all.

    >>> heat_balance_error([41800.0], [1.0], [70.0], [60.0], [0.0], m_flow_unit="kg/s")
    0.0
"""

import math

from .data_aggregates import Values, general_function

#: Mass-flow units understood by the checks, as factors to kg/s.
MASS_FLOW_UNITS = {"kg/s": 1.0, "kg/h": 1 / 3600}


def _rows(*series: Values | None) -> list[tuple[float, ...]]:
    """Rows where every given series has a finite value (series given as None are skipped)."""
    given = [s for s in series if s is not None]
    n = min((len(s) for s in given), default=0)
    out: list[tuple[float, ...]] = []
    for i in range(n):
        row = [s[i] for s in given]
        if all(v is not None and math.isfinite(v) for v in row):
            out.append(tuple(float(v) for v in row if v is not None))
    return out


def _flow_factor(unit: str) -> float:
    if unit not in MASS_FLOW_UNITS:
        raise ValueError(f"m_flow_unit must be one of {', '.join(MASS_FLOW_UNITS)}")
    return MASS_FLOW_UNITS[unit]


@general_function("heat_balance_error", "physics_check")
def heat_balance_error(
    power: Values,
    m_flow: Values,
    T_hot: Values,
    T_cold: Values,
    time: Values,
    *,
    cp: float = 4180.0,
    m_flow_unit: str = "kg/h",
    min_flow: float = 0.0,
) -> float | None:
    """Heat-balance error: reported power against m * cp * (T_hot - T_cold), in %.

    (sum Q - sum m cp dT) / sum m cp dT * 100, over the rows where the mass flow is above
    `min_flow` (in `m_flow_unit`). Target 0 %.
    """
    k = _flow_factor(m_flow_unit)
    rows = [r for r in _rows(power, m_flow, T_hot, T_cold) if r[1] > min_flow]
    ideal = sum(m * k * cp * (th - tc) for _, m, th, tc in rows)
    if not rows or ideal == 0:
        return None
    return (sum(q for q, *_ in rows) - ideal) / ideal * 100.0


@general_function("temperature_difference", "physics_check")
def temperature_difference(
    T_hot: Values,
    T_cold: Values,
    time: Values,
    m_flow: Values | None = None,
    *,
    min_flow: float = 0.0,
) -> float | None:
    """Mean temperature difference T_hot - T_cold, e.g. over a substation (target 30 K).

    With `m_flow`, only the rows where the mass flow is above `min_flow`.
    """
    rows = _rows(T_hot, T_cold, m_flow)
    if m_flow is not None:
        rows = [r for r in rows if r[2] > min_flow]
    return sum(r[0] - r[1] for r in rows) / len(rows) if rows else None


@general_function("relative_difference", "physics_check")
def relative_difference(a: Values, b: Values, time: Values) -> float | None:
    """Relative difference of two series that should be equal, in % of their mean.

    (mean a - mean b) / ((|mean a| + |mean b|) / 2) * 100, e.g. the pressure drops of two
    symmetric pipes. Target 0 %.
    """
    rows = _rows(a, b)
    if not rows:
        return None
    ma = sum(r[0] for r in rows) / len(rows)
    mb = sum(r[1] for r in rows) / len(rows)
    den = (abs(ma) + abs(mb)) / 2
    return (ma - mb) / den * 100.0 if den else None


@general_function("time_steps_below", "physics_check")
def time_steps_below(
    values: Values,
    time: Values,
    m_flow: Values | None = None,
    *,
    threshold: float,
    tolerance: float = 0.1,
    min_flow: float = 0.0,
) -> float | None:
    """Number of time steps below `threshold - tolerance`, e.g. outlet below 28 C (target 0).

    With `m_flow`, only the rows where the mass flow is above `min_flow` count.
    """
    rows = _rows(values, m_flow)
    if m_flow is not None:
        rows = [r for r in rows if r[1] > min_flow]
    if not rows:
        return None
    return float(sum(1 for r in rows if r[0] < threshold - tolerance))
