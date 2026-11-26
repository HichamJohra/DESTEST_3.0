"""Reusable layout blocks of the web app, and the rendering of dashboard panels.

`render_dashboard` turns a `destest.analysis.Dashboard` (built from the CME spec
file) into Dash components: a figure becomes a `dcc.Graph`, a table an HTML
table with the same cell classes as the static HTML pages. The pages never know
which visuals a CME uses: they render whatever its spec file lists.
"""

from typing import Any

from dash import ALL, MATCH, Input, Output, State, clientside_callback, dcc, html

from ..analysis import Dashboard, Panel, Table, describe_reference
from ..analysis.context import result_items
from ..analysis.timeline import Timeline
from ..analysis.visuals import Choice
from ..specs.schema import CmeSpec

# Plotly options shared by all graphs (no Plotly logo in the mode bar).
GRAPH_CONFIG: Any = {"displaylogo": False, "responsive": True}

# Remember a control's value in the browser tab (sessionStorage): kept when moving between
# pages or reloading, private to the tab and the user. Use as dcc.Dropdown(..., **PERSIST).
PERSIST: Any = {"persistence": True, "persistence_type": "session"}


def page_head(title: str, text: str = "") -> html.Div:
    """Title and short explanation at the top of a page."""
    return html.Div([html.H1(title), html.P(text) if text else None], className="page-head")


def card(
    children: Any,
    title: str | None = None,
    subtitle: str | None = None,
    tools: Any = None,
) -> html.Div:
    """A white box with an optional title and subtitle; `tools` sit right of the title."""
    head: list[Any] = []
    if title and tools is not None:
        head.append(
            html.Div([html.H3(title, className="card-title"), tools], className="card-head")
        )
    elif title:
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


def switch(
    component_id: Any,
    options: dict[str, str],
    value: str | None = None,
    label: str = "Colour by",
    persist: bool = True,
) -> html.Div:
    """A labelled segmented switch (`options`: value -> label), e.g. for card titles."""
    radio = dcc.RadioItems(
        id=component_id,
        options=[{"label": text, "value": v} for v, text in options.items()],
        value=value if value is not None else next(iter(options)),
        inline=True,
        className="toggle",
        **(PERSIST if persist else {}),
    )
    return html.Div(
        [html.Span(label, className="control-label inline"), radio], className="toggle-row"
    )


def timeline_view(timeline: Timeline) -> list[Any]:
    """Submissions per month as columns of squares (scrolls sideways, opens at today)."""
    colors = timeline.colors()
    height = max(6, timeline.height)
    columns = []
    for m in timeline.months:
        slots = []
        for k in range(height):
            if k < len(m.cells):
                c = m.cells[k]
                tip = f"{c.cme} - {c.label} - {c.created:%Y-%m-%d}"
                style = {"background": colors[timeline.key(c)]}
                slots.append(html.Div(className="tl-cell", title=tip, style=style))
            else:
                slots.append(html.Div(className="tl-cell tl-empty", title=f"{m.name}: -"))
        if m.month == 1 or m is timeline.months[0]:
            label: Any = html.Span(str(m.year), className="tl-year")
        elif m.month in (4, 7, 10):
            label = m.name[:3]
        else:
            label = ""
        columns.append(
            html.Div(
                [html.Div(slots, className="tl-stack"), html.Div(label, className="tl-label")],
                className="tl-col",
                title=f"{m.name}: {len(m.cells)} submission(s)",
            )
        )
    swatches = [
        html.Span([html.I(style={"background": v}), k], className="legend-item")
        for k, v in colors.items()
    ]
    note = f"{len(timeline.cells)} submission(s)"
    if timeline.undated:
        note += f"; {len(timeline.undated)} without a date in the file name (not shown)"
    return [
        html.Div(html.Div(columns, className="timeline"), className="timeline-scroll"),
        html.Div(swatches, className="legend-row"),
        html.P(note, className="table-note"),
    ]


def _choice_panel(p: Panel, choice: Choice, index: str) -> html.Div:
    """A visual with a switch at the right of the card title (e.g. its colouring).

    Figures: one graph, its figure swapped from a Store. Timelines (HTML): all versions
    rendered, only the chosen one shown. Both switch in the browser, without the server.
    """
    first = next(iter(choice.options))
    labels = {label: label for label in choice.options}
    body: list[Any]
    if isinstance(choice.options[first], Timeline):
        switch_id = {"type": "choice-html-switch", "index": index}
        body = [
            html.Div(
                timeline_view(option),
                id={"type": "choice-item", "index": index, "option": label},
                style={"display": "block" if label == first else "none"},
            )
            for label, option in choice.options.items()
            if isinstance(option, Timeline)
        ]
    else:
        switch_id = {"type": "choice-switch", "index": index}
        body = [
            dcc.Graph(
                id={"type": "choice-graph", "index": index},
                figure=choice.options[first],
                config=GRAPH_CONFIG,
            ),
            dcc.Store(id={"type": "choice-figures", "index": index}, data=choice.options),
        ]
    tools = switch(switch_id, labels, first, choice.label, False)
    return card(body, title=p.title, subtitle=p.description or None, tools=tools)


# Choice panels switch in the browser: a figure from the Store, or which version is shown.
clientside_callback(
    "function(choice, figures) {"
    " return (figures && figures[choice]) || window.dash_clientside.no_update; }",
    Output({"type": "choice-graph", "index": MATCH}, "figure"),
    Input({"type": "choice-switch", "index": MATCH}, "value"),
    State({"type": "choice-figures", "index": MATCH}, "data"),
    prevent_initial_call=True,
)
clientside_callback(
    "function(choice, ids) {"
    " return ids.map(function(i) { return {display: i.option === choice ? 'block' : 'none'}; }); }",
    Output({"type": "choice-item", "index": MATCH, "option": ALL}, "style"),
    Input({"type": "choice-html-switch", "index": MATCH}, "value"),
    State({"type": "choice-item", "index": MATCH, "option": ALL}, "id"),
    prevent_initial_call=True,
)


def render_panel(p: Panel, index: str = "0") -> html.Div:
    """One dashboard panel as a card (`index`: unique on the page, for Choice panels)."""
    if p.choice is not None:
        return _choice_panel(p, p.choice, index)
    if p.table is not None:
        body: Any = render_table(p.table)
    elif p.timeline is not None:
        body = timeline_view(p.timeline)
    elif p.figure is not None:
        body = dcc.Graph(figure=p.figure, config=GRAPH_CONFIG)
    else:
        body = html.P("Nothing to show.", className="muted")
    return card(body, title=p.title, subtitle=p.description or None)


def render_dashboard(board: Dashboard) -> list[Any]:
    """All panels of a dashboard, in the order of the CME spec file."""
    return [render_panel(p, f"{board.kind}-{i}") for i, p in enumerate(board.panels)]


def _comparison_summary(spec: CmeSpec) -> str:
    """E.g. `25 compared items (21 values, 4 series metrics); all weight 1 in the grade`."""
    items = result_items(spec)
    n_series = sum(1 for i in items if i.metric is not None)
    weights = sorted({i.weight for i in items})
    if len(weights) == 1:
        how = f"all weight {weights[0]:g} in the accuracy grade"
    else:
        how = "weighted in the accuracy grade (see the results table)"
    parts = f"{len(items) - n_series} values, {n_series} series metrics"
    return f"{len(items)} compared items ({parts}); {how}"


def cme_info_card(spec: CmeSpec, n_submissions: int) -> html.Div:
    """Description, key characteristics and reference of a CME, from its spec file."""
    info = spec.cme
    rows: list[tuple[str, Any]] = list(info.characteristics.items())
    if spec.analysis is not None:
        reference: list[Any] = [describe_reference(spec.analysis, n_submissions)]
        if spec.analysis.reference_note:
            reference += [html.Br(), html.Span(spec.analysis.reference_note, className="muted")]
        rows += [
            ("Reference", reference),
            ("Compared items", _comparison_summary(spec)),
        ]
    rows += [("Status", info.status)]
    if info.description_reference:
        rows.append(("Described in", info.description_reference))
    table = html.Table(
        html.Tbody([html.Tr([html.Th(label), html.Td(value)]) for label, value in rows]),
        className="info-table",
    )
    body = [html.P(info.description) if info.description else None, table]
    return card(body, title=f"{spec.folder_name} - {info.full_title}")


def comments_card(spec: CmeSpec) -> html.Div | None:
    """Comments and observations on the results of a CME (bullets), or None if there are none."""
    items = spec.analysis.comments_and_observations if spec.analysis is not None else []
    if not items:
        return None
    return card(html.Ul([html.Li(text) for text in items]), title="Comments and observations")


def skipped_notice(skipped: list[tuple[str, str]]) -> html.Details | None:
    """A note listing result files left out because they do not pass `destest check`."""
    if not skipped:
        return None
    items = [html.Li([html.Code(name), f": {reason}"]) for name, reason in skipped]
    return html.Details(
        [html.Summary(f"{len(skipped)} result file(s) not shown (invalid)"), html.Ul(items)],
        className="msg msg-warn",
    )
