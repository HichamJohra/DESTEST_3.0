"""General comparison: one value per submission, compared between submissions.

* `data_aggregates.py`: aggregates of one series (mean, maximum, steady-state value, time
  integral, ...), compared with the median of all submissions (or with a target);
* `physics_check.py`: consistency with physics and with the exercise description (heat
  balance, temperature difference over a substation, symmetry, ...), compared with a known
  target (e.g. 0 %, 30 K).

Both register their functions in `GENERAL_FUNCTIONS`; the CME spec file refers to them by
name (`analysis.general_comparison[].function`).
"""

from . import physics_check
from .data_aggregates import (
    ENERGY_UNITS,
    GENERAL_FUNCTIONS,
    VALUE_DIFFERENCE_UNITS,
    VALUE_DIFFERENCES,
    ComparisonFunction,
    general_function,
)

__all__ = [
    "ENERGY_UNITS",
    "GENERAL_FUNCTIONS",
    "VALUE_DIFFERENCES",
    "VALUE_DIFFERENCE_UNITS",
    "ComparisonFunction",
    "general_function",
    "physics_check",
]
