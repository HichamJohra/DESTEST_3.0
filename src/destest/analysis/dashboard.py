"""Dashboards: the visuals listed in a CME's spec file, built for some submissions.

Three kinds, each listed under `analysis.dashboards` in the CME spec file:

* `overview`: all submissions of the CME;
* `detail`: one submission, against the reference;
* `comparison`: a selection of submissions, against the reference.

The reference is always built from all submissions. A `Dashboard` can be turned
into JSON (`to_dict`, for a web front end) or into a stand-alone HTML page
(`render_html`, figures drawn with plotly.js from a CDN).
"""

import html
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from ..results import Submission
from ..specs.schema import CmeSpec
from .context import build_context, describe_reference
from .visuals import VISUALS, Figure, Table

Kind = Literal["overview", "detail", "comparison"]
KINDS: tuple[str, ...] = ("overview", "detail", "comparison")

#: plotly.js used by the HTML pages (loaded from its CDN).
PLOTLY_JS = "https://cdn.plot.ly/plotly-2.35.2.min.js"


@dataclass
class Panel:
    """One element of a dashboard: a table or a figure, with a title."""

    title: str
    visual: str
    description: str = ""
    table: Table | None = None
    figure: Figure | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {
            "title": self.title,
            "visual": self.visual,
            "description": self.description,
            "table": self.table.to_dict() if self.table else None,
            "figure": self.figure,
        }


@dataclass
class Dashboard:
    """A built dashboard."""

    cme: str
    title: str
    kind: str
    submissions: list[str]  # labels of the submissions shown
    panels: list[Panel] = field(default_factory=list)
    description: str = ""  # what the CME tests (from its spec file)
    reference: str = ""  # how the reference is built, in words
    created: str = field(default_factory=lambda: f"{datetime.now():%Y-%m-%d %H:%M}")

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form, for a web front end."""
        return {
            "cme": self.cme,
            "title": self.title,
            "kind": self.kind,
            "submissions": self.submissions,
            "description": self.description,
            "reference": self.reference,
            "created": self.created,
            "panels": [p.to_dict() for p in self.panels],
        }


def build_dashboard(
    spec: CmeSpec,
    submissions: list[Submission],
    kind: str = "overview",
    focus: list[Submission] | None = None,
) -> Dashboard:
    """Build one kind of dashboard of a CME.

    `submissions`: all submissions (for the reference). `focus`: the ones to show;
    default all for `overview`; exactly one for `detail`; one or more for `comparison`.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)} (got '{kind}')")
    if spec.analysis is None:
        raise ValueError(f"{spec.folder_name}: the spec file has no 'analysis' section")
    if kind == "detail" and (focus is None or len(focus) != 1):
        raise ValueError("A detail dashboard shows exactly one submission.")
    if kind == "comparison" and not focus:
        raise ValueError("A comparison dashboard needs at least one submission to show.")
    ctx = build_context(spec, submissions, focus if kind != "overview" else None)
    names = {"overview": "Overview", "detail": "Detail", "comparison": "Comparison"}
    title = f"{spec.folder_name} - {spec.cme.full_title} - {names[kind]}"
    if kind == "detail":
        title += f": {ctx.focus[0].label}"
    board = Dashboard(spec.folder_name, title, kind, [s.label for s in ctx.focus])
    board.description = spec.cme.description
    board.reference = describe_reference(spec.analysis, len(submissions))
    for p in getattr(spec.analysis.dashboards, kind):
        result = VISUALS[p.visual].builder(ctx, **p.options)
        panel = Panel(p.title, p.visual, p.description)
        if isinstance(result, Table):
            panel.table = result
        else:
            panel.figure = result
        board.panels.append(panel)
    return board


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
_CSS = """
body { font-family: system-ui, sans-serif; margin: 0; padding: 0 24px 40px; color: #222; }
header { position: sticky; top: 0; background: #fff; padding: 14px 0 8px;
         border-bottom: 1px solid #ddd; z-index: 1; }
h1 { font-size: 1.3rem; margin: 0 0 4px; }
.meta { color: #666; font-size: .85rem; }
section { margin-top: 28px; }
h2 { font-size: 1.05rem; margin: 0 0 4px; }
.desc, .note { color: #555; font-size: .85rem; margin: 2px 0 8px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; font-size: .82rem; margin: 0 auto; }
th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: right; white-space: nowrap; }
th { background: #f3f4f6; position: sticky; top: 0; }
td:first-child, th:first-child { text-align: left; }
td.ref { background: #f3f4f6; font-weight: 600; }
td.warn { background: #fff4d6; }
td.bad { background: #ffd9d6; }
td.score { font-weight: 600; background: #eef6ee; }
td.wrap { white-space: normal; text-align: left; min-width: 220px; max-width: 520px; }
"""


def _table_html(t: Table) -> str:
    head = "".join(
        f'<th style="text-align:{t.alignment(j)}">{html.escape(h)}</th>'
        for j, h in enumerate(t.headers)
    )
    body = []
    for i, row in enumerate(t.rows):
        cls = t.classes[i] if i < len(t.classes) else []
        cells = []
        for j, cell in enumerate(row):
            c = cls[j] if j < len(cls) and cls[j] else ""
            style = f"text-align:{t.alignment(j)}"
            if t.color(i, j):
                style += f";background:{t.color(i, j)}"
            attr = (f' class="{c}"' if c else "") + f' style="{style}"'
            text = html.escape(cell).replace("\n", "<br>")
            cells.append(f"<td{attr}>{text}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    note = f'<p class="note">{html.escape(t.note)}</p>' if t.note else ""
    rows = "".join(body)
    width = ' style="width:100%"' if t.full_width else ""
    return f'<div class="scroll"><table{width}><tr>{head}</tr>{rows}</table></div>{note}'


def render_html(board: Dashboard) -> str:
    """A stand-alone HTML page of the dashboard (needs internet for plotly.js)."""
    parts = []
    figures = []
    for i, p in enumerate(board.panels):
        desc = f'<p class="desc">{html.escape(p.description)}</p>' if p.description else ""
        if p.table is not None:
            content = _table_html(p.table)
        else:
            content = f'<div id="fig{i}"></div>'
            figures.append((f"fig{i}", p.figure))
        parts.append(f"<section><h2>{html.escape(p.title)}</h2>{desc}{content}</section>")
    scripts = "".join(
        f"Plotly.newPlot({json.dumps(div)}, {json.dumps(f['data'])}, "
        f"{json.dumps(f['layout'])}, {{responsive: true}});\n"
        for div, f in figures
        if f is not None
    )
    shown = ", ".join(board.submissions)
    intro = f'<p class="desc">{html.escape(board.description)}</p>' if board.description else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(board.title)}</title>
<script src="{PLOTLY_JS}"></script>
<style>{_CSS}</style></head>
<body><header><h1>{html.escape(board.title)}</h1>
<div class="meta">{len(board.submissions)} submission(s): {html.escape(shown)}
- built {board.created} with destest</div>
<div class="meta">Reference: {html.escape(board.reference)}</div>
</header>
{intro}
{"".join(parts)}
<script>{scripts}</script>
</body></html>
"""
