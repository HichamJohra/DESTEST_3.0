"""KPIs, accuracy metrics, visuals and dashboards, driven by the CME spec files.

The building blocks are written once and reused by every CME:

* `kpis.py`: KPI functions (one number from a time series), e.g. `steady_state`;
* `accuracy_metric.py`: accuracy against the reference, e.g. `relative_deviation`, `nmbe`;
* `visuals.py`: tables and figures, e.g. `kpi_table`, `profile`, `carpet`;
* `dashboard.py`: the dashboards listed in a CME spec file (`overview`, `detail`,
  `comparison`), as JSON for a web front end or as an HTML page.

Each CME chooses its KPIs and visuals in the `analysis` section of its spec file.

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

from .accuracy_metric import SERIES_METRICS, VALUE_METRICS
from .context import AnalysisContext, build_context, compute_kpis
from .dashboard import KINDS, Dashboard, Panel, build_dashboard, render_html
from .kpis import KPI_FUNCTIONS, kpi_function
from .visuals import VISUALS, Table, visual

__all__ = [
    "KINDS",
    "KPI_FUNCTIONS",
    "SERIES_METRICS",
    "VALUE_METRICS",
    "VISUALS",
    "AnalysisContext",
    "Dashboard",
    "Panel",
    "Table",
    "build_context",
    "build_dashboard",
    "compute_kpis",
    "kpi_function",
    "render_html",
    "visual",
]
