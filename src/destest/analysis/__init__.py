"""Comparisons, accuracy grade, visuals and dashboards, driven by the CME spec files.

The building blocks are written once and reused by every CME:

* `general_comparison/`: one value per submission, compared between submissions:
  `data_aggregates.py` (mean, integral, steady-state value, ...) and `physics_check.py`
  (heat balance, temperature difference, symmetry, ... with a known target);
* `point_by_point_comparison/`: series compared point by point with the reference series:
  the metrics of Technical Report 314 (`point_by_point_difference.py`), time series
  (`time_series.py`), data profiles (`data_profiles.py`), the references (median of all
  submissions) and the comparison of each submission with them;
* `accuracy_grade/`: the closeness to target (0-100) of each submission;
* `context.py`: every compared item of every submission, computed once per dashboard;
* `visuals.py`: tables and figures, e.g. `results_table`, `profile`, `time_series`;
* `dashboard.py`: the dashboards listed in a CME spec file (`overview`, `detail`,
  `comparison`), as JSON for a web front end or as an HTML page.

Each CME chooses what is compared, and its visuals, in the `analysis` section of its spec
file.

```python
from destest.analysis import build_dashboard, render_html
from destest.results import load_cme_submissions
from destest.specs import load_cme_spec

spec = load_cme_spec("DHN", 1)
subs = load_cme_submissions("Result data/CME_DHN_1")
board = build_dashboard(spec, subs, "overview")
html_page = render_html(board)
```
"""

from .context import AnalysisContext, ResultItem, build_context, describe_reference
from .dashboard import KINDS, Dashboard, Panel, build_dashboard, render_html
from .general_comparison import GENERAL_FUNCTIONS, general_function
from .point_by_point_comparison import POINT_METRICS, TIME_SERIES_METRICS, point_metric
from .visuals import VISUALS, Table, visual

__all__ = [
    "GENERAL_FUNCTIONS",
    "KINDS",
    "POINT_METRICS",
    "TIME_SERIES_METRICS",
    "VISUALS",
    "AnalysisContext",
    "Dashboard",
    "Panel",
    "ResultItem",
    "Table",
    "build_context",
    "build_dashboard",
    "describe_reference",
    "general_function",
    "point_metric",
    "render_html",
    "visual",
]
