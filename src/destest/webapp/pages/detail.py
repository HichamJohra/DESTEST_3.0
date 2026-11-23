"""Detail page: one submission against the reference (dashboard `detail` of the spec file).

Open directly with `/detail?cme=CME_DHN_1&submission=<file name without extension>`.
"""

from typing import Any

import dash
from dash import Input, Output, State, callback, dcc, html

from ..components import PERSIST, card, control, message, page_head, render_dashboard
from ..data import dashboard, submission_options
from .overview import cme_dropdown


def layout(cme: str | None = None, submission: str | None = None, **_: Any) -> html.Div:
    return html.Div(
        [
            page_head("Detail", "One submission against the reference of all submissions."),
            card(
                html.Div(
                    [
                        cme_dropdown("dt-cme", cme),
                        control(
                            "Submission",
                            dcc.Dropdown(id="dt-sub", value=submission, clearable=False, **PERSIST),
                        ),
                    ],
                    className="grid-2",
                )
            ),
            dcc.Loading(html.Div(id="dt-content")),
        ]
    )


dash.register_page(
    __name__,
    path="/detail",
    name="Detail",
    order=2,
    title="Detail - DESTEST 3.0",
    layout=layout,
)


@callback(
    Output("dt-sub", "options"),
    Output("dt-sub", "value"),
    Input("dt-cme", "value"),
    State("dt-sub", "value"),
)
def _submissions(cme: str | None, current: str | None) -> tuple[list[dict[str, str]], str | None]:
    options = submission_options(cme) if cme else []
    ids = [o["value"] for o in options]
    return options, current if current in ids else (ids[0] if ids else None)


@callback(Output("dt-content", "children"), Input("dt-cme", "value"), Input("dt-sub", "value"))
def _detail(cme: str | None, sub_id: str | None) -> list[Any]:
    if not cme or not sub_id:
        return [message("Choose an exercise and a submission.", "info")]
    try:
        board = dashboard(cme, "detail", [sub_id])
    except ValueError as exc:
        return [message(str(exc), "error")]
    return render_dashboard(board)
