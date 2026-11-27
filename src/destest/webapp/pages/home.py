"""Home page: map and timeline of the contributions, and the common modelling exercises.

The map, the timeline and the pie chart each have a "Colour by" switch: exercise,
modelling tool or institution (and country for the timeline and the pie chart).
"""

from typing import Any

import dash
from dash import Input, Output, callback, dcc, html

from ...analysis.maps import COLOR_BY, contributions_pie, exercises_map
from ...analysis.timeline import submission_timeline
from ...results import Submission
from ..components import GRAPH_CONFIG, card, message, page_head, switch, timeline_view
from ..data import cme_names, get_cme

#: Colour options of the home-page map (the timeline offers all of COLOR_BY).
MAP_OPTIONS = {k: COLOR_BY[k] for k in ("cme", "tool", "institution")}


def _all_submissions() -> dict[str, list[Submission]]:
    return {n: get_cme(n).submissions for n in cme_names()}


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
        body[0:0] = [
            card(
                dcc.Graph(id="home-map", config=GRAPH_CONFIG),
                title="Mapping contributions",
                tools=switch("home-map-color", MAP_OPTIONS),
            ),
            card(
                html.Div(id="home-timeline"),
                title="Contributions over time",
                tools=switch("home-timeline-color", COLOR_BY),
            ),
            card(
                dcc.Graph(id="home-pie", config=GRAPH_CONFIG),
                title="Distribution of contributions",
                tools=switch("home-pie-color", COLOR_BY),
            ),
        ]
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


@callback(Output("home-map", "figure"), Input("home-map-color", "value"))
def _map(color_by: str | None) -> Any:
    return exercises_map(_all_submissions(), color_by=color_by or "cme")


@callback(Output("home-timeline", "children"), Input("home-timeline-color", "value"))
def _timeline(color_by: str | None) -> list[Any]:
    return timeline_view(submission_timeline(_all_submissions(), color_by=color_by or "cme"))


@callback(Output("home-pie", "figure"), Input("home-pie-color", "value"))
def _pie(color_by: str | None) -> Any:
    return contributions_pie(_all_submissions(), color_by=color_by or "cme")


dash.register_page(
    __name__,
    path="/",
    name="Home",
    order=0,
    title="DESTEST 3.0",
    layout=layout,
)
