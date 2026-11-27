"""Overview page: all submissions of a CME (dashboard `overview` of its spec file)."""

from typing import Any

import dash
from dash import Input, Output, callback, dcc, html

from ..components import (
    card,
    cme_info_card,
    comments_card,
    control,
    message,
    page_head,
    render_dashboard,
    skipped_notice,
)
from ..data import cme_names, dashboard, get_cme


def cme_dropdown(component_id: str, cme: str | None) -> html.Div:
    """The CME selector shared by the dashboard pages (value from the URL, else the first)."""
    names = cme_names()
    value = cme if cme in names else (names[0] if names else None)
    options = [{"label": f"{n} - {get_cme(n).spec.cme.full_title}", "value": n} for n in names]
    return control(
        "Common modelling exercise",
        dcc.Dropdown(id=component_id, options=options, value=value, clearable=False),
    )


def layout(cme: str | None = None, **_: Any) -> html.Div:
    return html.Div(
        [
            page_head("Overview", "All submissions of an exercise, against the reference."),
            card(cme_dropdown("ov-cme", cme)),
            dcc.Loading(html.Div(id="ov-content")),
        ]
    )


dash.register_page(
    __name__,
    path="/overview",
    name="Overview",
    order=1,
    title="Overview - DESTEST 3.0",
    layout=layout,
)


@callback(Output("ov-content", "children"), Input("ov-cme", "value"))
def _overview(cme: str | None) -> list[Any]:
    if not cme:
        return [message("No exercise selected.", "warn")]
    data = get_cme(cme)
    info = cme_info_card(data.spec, len(data.submissions))
    if not data.submissions:
        return [info, skipped_notice(data.skipped), message("No valid submission yet.", "info")]
    try:
        board = dashboard(cme, "overview")
    except ValueError as exc:
        return [info, message(str(exc), "error")]
    return [
        info,
        skipped_notice(data.skipped),
        *render_dashboard(board),
        comments_card(data.spec),
    ]
