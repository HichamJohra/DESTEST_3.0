"""Comparison page: a selection of submissions against the reference (dashboard `comparison`)."""

from typing import Any

import dash
from dash import Input, Output, State, callback, dcc, html

from ..components import (
    PERSIST,
    card,
    cme_info_card,
    control,
    message,
    page_head,
    render_dashboard,
)
from ..data import dashboard, get_cme, submission_options
from .overview import cme_dropdown

#: Submissions selected when a comparison is opened for the first time.
DEFAULT_SELECTION = 3


def layout(cme: str | None = None, **_: Any) -> html.Div:
    return html.Div(
        [
            page_head(
                "Comparison",
                "Several submissions side by side, against the reference of all submissions.",
            ),
            card(
                html.Div(
                    [
                        cme_dropdown("cmp-cme", cme),
                        control("Submissions", dcc.Dropdown(id="cmp-subs", multi=True, **PERSIST)),
                    ],
                    className="grid-2",
                )
            ),
            dcc.Loading(html.Div(id="cmp-content")),
        ]
    )


dash.register_page(
    __name__,
    path="/comparison",
    name="Comparison",
    order=3,
    title="Comparison - DESTEST 3.0",
    layout=layout,
)


@callback(
    Output("cmp-subs", "options"),
    Output("cmp-subs", "value"),
    Input("cmp-cme", "value"),
    State("cmp-subs", "value"),
)
def _submissions(
    cme: str | None, current: list[str] | None
) -> tuple[list[dict[str, str]], list[str]]:
    options = submission_options(cme) if cme else []
    ids = [o["value"] for o in options]
    kept = [i for i in current or [] if i in ids]
    return options, kept or ids[:DEFAULT_SELECTION]


@callback(Output("cmp-content", "children"), Input("cmp-cme", "value"), Input("cmp-subs", "value"))
def _comparison(cme: str | None, ids: list[str] | None) -> list[Any]:
    if not cme:
        return [message("Choose an exercise and at least one submission.", "info")]
    data = get_cme(cme)
    info = cme_info_card(data.spec, len(data.submissions))
    if not ids:
        return [info, message("Choose at least one submission.", "info")]
    try:
        board = dashboard(cme, "comparison", ids)
    except ValueError as exc:
        return [info, message(str(exc), "error")]
    return [info, *render_dashboard(board)]
