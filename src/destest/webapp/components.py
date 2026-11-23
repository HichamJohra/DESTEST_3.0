"""Reusable layout blocks of the web app, and the rendering of dashboard panels.

`render_dashboard` turns a `destest.analysis.Dashboard` (built from the CME spec
file) into Dash components: a figure becomes a `dcc.Graph`, a table an HTML
table with the same cell classes as the static HTML pages. The pages never know
which visuals a CME uses: they render whatever its spec file lists.
"""

from typing import Any

from dash import dcc, html

from ..analysis import Dashboard, Panel, Table

# Plotly options shared by all graphs (no Plotly logo in the mode bar).
GRAPH_CONFIG: Any = {"displaylogo": False, "responsive": True}

# Remember a control's value in the browser tab (sessionStorage): kept when moving between
# pages or reloading, private to the tab and the user. Use as dcc.Dropdown(..., **PERSIST).
PERSIST: Any = {"persistence": True, "persistence_type": "session"}


def page_head(title: str, text: str = "") -> html.Div:
    """Title and short explanation at the top of a page."""
    return html.Div([html.H1(title), html.P(text) if text else None], className="page-head")


def card(children: Any, title: str | None = None, subtitle: str | None = None) -> html.Div:
    """A white box with an optional title and subtitle."""
    head: list[Any] = []
    if title:
        head.append(html.H3(title, className="card-title"))
    if subtitle:
        head.append(html.P(subtitle, className="card-subtitle"))
    body = children if isinstance(children, list) else [children]
    return html.Div(head + body, className="card")


def control(label: str, component: Any) -> html.Div:
    """A labelled input."""
    return html.Div([html.Label(label, className="control-label"), component], className="control")


def message(text: str, kind: str = "info") -> html.Div:
    """A coloured message box: kind `info`, `ok`, `warn` or `error`."""
    return html.Div(text, className=f"msg msg-{kind}")


def _cell(text: str) -> list[Any]:
    """Cell text with its line breaks kept."""
    lines = text.split("\n")
    out: list[Any] = []
    for i, line in enumerate(lines):
        if i:
            out.append(html.Br())
        out.append(line)
    return out


def render_table(t: Table) -> html.Div:
    """A `Table` as an HTML table (horizontal scrolling when wide)."""
    head = html.Tr(
        [html.Th(h, style={"textAlign": t.alignment(j)}) for j, h in enumerate(t.headers)]
    )
    rows = []
    for i, row in enumerate(t.rows):
        cls = t.classes[i] if i < len(t.classes) else []
        cells = []
        for j, text in enumerate(row):
            style: dict[str, str] = {"textAlign": t.alignment(j)}
            if t.color(i, j):
                style["background"] = t.color(i, j)
            name = (cls[j] if j < len(cls) else "") or None
            cells.append(html.Td(_cell(text), className=name, style=style))
        rows.append(html.Tr(cells))
    table_class = "data-table full-width" if t.full_width else "data-table"
    table = html.Div(
        html.Table([html.Thead(head), html.Tbody(rows)], className=table_class),
        className="table-scroll",
    )
    note = html.P(t.note, className="table-note") if t.note else None
    return html.Div([table, note])


def render_panel(p: Panel) -> html.Div:
    """One dashboard panel as a card."""
    if p.table is not None:
        body: Any = render_table(p.table)
    elif p.figure is not None:
        body = dcc.Graph(figure=p.figure, config=GRAPH_CONFIG)
    else:
        body = html.P("Nothing to show.", className="muted")
    return card(body, title=p.title, subtitle=p.description or None)


def render_dashboard(board: Dashboard) -> list[Any]:
    """All panels of a dashboard, in the order of the CME spec file."""
    return [render_panel(p) for p in board.panels]


def skipped_notice(skipped: list[tuple[str, str]]) -> html.Details | None:
    """A note listing result files left out because they do not pass `destest check`."""
    if not skipped:
        return None
    items = [html.Li([html.Code(name), f": {reason}"]) for name, reason in skipped]
    return html.Details(
        [html.Summary(f"{len(skipped)} result file(s) not shown (invalid)"), html.Ul(items)],
        className="msg msg-warn",
    )
