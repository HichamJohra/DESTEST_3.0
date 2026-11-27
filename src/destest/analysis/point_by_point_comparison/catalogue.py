"""The catalogue of comparison metrics, as a Markdown page (docs/comparison-metrics.md).

Written from the metric registries, so the documentation always matches the code:
`uv run python scripts/make_metrics_doc.py` rewrites the page; a test checks it is current.
"""

import re

from .point_by_point_difference import POINT_METRICS, Metric
from .time_series import TIME_SERIES_METRICS

UNIT_TEXT = {"X": "unit of the data", "X^2": "(unit of the data)²", "%": "%", "-": "-"}

INTRO = """# Comparison metrics

<!-- Written by scripts/make_metrics_doc.py from the code: do not edit by hand. -->

The point-by-point comparison metrics of DESTEST 3.0 (`destest.analysis.point_by_point_comparison`).
They follow the notation, names, units, ranges and optimum values of Technical Report 314
(Johra et al., 2023), the supplementary material of the review by Johra et al. (2023):

* **x** = reference values (here: the point-by-point median of all submissions),
  **y** = simulated values, **n** = number of points, x-bar, y-bar = means,
  sigma = standard deviations;
* errors are **y - x**: a positive bias means that the model over-predicts;
* pairs where y or x is missing are left out.

A CME chooses its metrics in `analysis.point_by_point_comparison.metrics` of its spec file
(CME_DHN_1 and CME_DHN_2: MBE and CVRMSE). In the accuracy grade, each submission is scored
on the distance of its metric value to the **optimum** (the value of a perfect fit).

References:

* H. Johra, M. Mans, K. Filonenko, I. De Jaeger, D. Saelens, T. Tvedebrink (2021).
  Evaluating different metrics for inter-model comparison of urban-scale building energy
  simulation time series. Building Simulation 2021, Bruges.
  <https://doi.org/10.26868/25222708.2021.30410>
* H. Johra, M. Schaffer, G. Chaudhary, H. Syed Kazmi, J. Le Dréau, S. Petersen (2023).
  Coherent description of 48 metrics to compare, validate and assess accuracy of building
  energy models and indoor environment simulations. DCE Technical Report No. 314, Aalborg
  University. <https://doi.org/10.54337/aau533917780>
* H. Johra, M. Schaffer, G. Chaudhary, H.S. Kazmi, J. Le Dréau, S. Petersen (2023). What
  metrics does the building energy performance community use to compare dynamic models?
  Building Simulation 2023, Shanghai, 861-868. <https://doi.org/10.26868/25222708.2023.1309>

Not implemented: the qualitative graphical assessment (see the dashboards) and nCPBES (no
equation in the report).
"""


def _no_pipes(text: str) -> str:
    """|a| -> abs(a): a pipe would end the Markdown table cell."""
    return re.sub(r"\|([^|]+)\|", r"abs(\1)", text).replace("|", "/")


def _optimum(m: Metric) -> str:
    if m.optimum is None:
        return "see note"
    return f"{m.optimum:g}"


def _table(metrics: dict[str, Metric]) -> list[str]:
    lines = [
        "| Name | Full name | Equation | Unit | Range | Optimum | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in metrics.values():
        notes = m.note
        if m.alternative_names:
            alt = "Also: " + ", ".join(m.alternative_names) + "."
            notes = f"{alt} {notes}".strip()
        params = sorted(m.parameters - {"time"})
        if params:
            notes = f"{notes} Parameters: {', '.join(params)}.".strip()
        cells = [
            f"`{m.name}`",
            m.full_name,
            f"`{_no_pipes(m.equation)}`",
            UNIT_TEXT.get(m.unit, m.unit),
            m.value_range,
            _optimum(m),
            _no_pipes(notes),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def metrics_catalogue_markdown() -> str:
    """The whole page, grouped as in Technical Report 314."""
    out = [INTRO]
    groups: dict[str, dict[str, Metric]] = {}
    for name, m in POINT_METRICS.items():
        groups.setdefault(m.group, {})[name] = m
    out.append("## Point-by-point metrics (time series and data profiles)\n")
    for group, metrics in groups.items():
        out.append(f"### {group}\n")
        out += _table(metrics)
        out.append("")
    out.append("## Time-series metrics (need the time axis)\n")
    tgroups: dict[str, dict[str, Metric]] = {}
    for name, m in TIME_SERIES_METRICS.items():
        tgroups.setdefault(m.group, {})[name] = m
    for group, metrics in tgroups.items():
        out.append(f"### {group}\n")
        out += _table(metrics)
        out.append("")
    return "\n".join(out).rstrip() + "\n"
