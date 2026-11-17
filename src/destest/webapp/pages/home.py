"""Home page: the common modelling exercises and their number of submissions."""

from typing import Any

import dash
from dash import dcc, html

from ...analysis.maps import exercises_map
from ..components import GRAPH_CONFIG, card, message, page_head
from ..data import cme_names, get_cme


def _cme_card(name: str) -> html.Div:
    data = get_cme(name)
    info = data.spec.cme
    links = [
        dcc.Link("Overview", href=f"/overview?cme={name}", className="btn"),
        dcc.Link("Detail", href=f"/detail?cme={name}", className="btn btn-light"),
        dcc.Link("Comparison", href=f"/comparison?cme={name}", className="btn btn-light"),
    ]
    facts: list[Any] = [
        html.Span(f"{len(data.submissions)} submission(s)", className="badge"),
        html.Span(f"status: {info.status}", className="badge badge-muted"),
    ]
    if data.skipped:
        invalid = f"{len(data.skipped)} invalid file(s)"
        facts.append(html.Span(invalid, className="badge badge-warn"))
    return card(
        [
            html.Div(facts, className="badges"),
            html.P(info.description_reference, className="muted")
            if info.description_reference
            else None,
            html.Div(links, className="btn-row"),
        ],
        title=f"{name} - {info.full_title}",
    )


def layout(**_: Any) -> html.Div:
    names = cme_names()
    body: list[Any] = [_cme_card(n) for n in names] or [
        message("No common modelling exercise with an analysis section was found.", "warn")
    ]
    if names:
        figure = exercises_map({n: get_cme(n).submissions for n in names})
        body.insert(
            0,
            card(
                dcc.Graph(figure=figure, config=GRAPH_CONFIG),
                title="Contributions",
                subtitle="Every submission at its institution's city, coloured by exercise.",
            ),
        )
    return html.Div(
        [
            page_head(
                "DESTEST 3.0",
                "District Energy Simulation Test Procedure: common modelling exercises (CMEs) "
                "for the comparison and verification of district energy simulation tools. "
                "Choose an exercise to see all results, one result in detail, or a comparison.",
            ),
            *body,
        ]
    )


dash.register_page(
    __name__,
    path="/",
    name="Home",
    order=0,
    title="DESTEST 3.0",
    layout=layout,
)
