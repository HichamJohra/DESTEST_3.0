"""About page: DESTEST, the exercises, the file naming convention, how to read the dashboards."""

from typing import Any

import dash
from dash import html

from ...analysis.visuals import CLOSENESS_NOTE
from ...filename_check.convention import describe
from ..components import card, page_head
from ..data import cme_names, get_cme

REPOSITORY = "https://github.com/HichamJohra/DESTEST_3.0"
DOCUMENTATION = "https://hichamjohra.github.io/DESTEST_3.0/"


def layout(**_: Any) -> html.Div:
    rows = [
        html.Tr(
            [
                html.Td(n),
                html.Td(get_cme(n).spec.cme.full_title),
                html.Td(get_cme(n).spec.cme.description_reference),
            ]
        )
        for n in cme_names()
    ]
    return html.Div(
        [
            page_head("About DESTEST"),
            card(
                [
                    html.P(
                        "DESTEST (District Energy Simulation Test Procedure) is a series of "
                        "common modelling exercises: several participants model the same "
                        "district energy case with their own tools, and the results are "
                        "compared to check the tools and the modelling practice. It was "
                        "started in IBPSA Project 1."
                    ),
                    html.P(
                        "There is no measured truth: each result is compared with a reference "
                        "built from all submissions (the median, unless the exercise says "
                        "otherwise)."
                    ),
                ],
                title="What is DESTEST?",
            ),
            card(
                html.Div(
                    html.Table(
                        [
                            html.Tr(
                                [html.Th("Exercise"), html.Th("Title"), html.Th("Described in")]
                            ),
                            *rows,
                        ],
                        className="data-table",
                    ),
                    className="table-scroll",
                ),
                title="Exercises",
            ),
            card(
                [
                    html.P(
                        "Overview: all submissions. Detail: one submission. Comparison: a "
                        "selection. Each compared item has a target: the median of all "
                        "submissions, a set target (physics checks) or the ideal value of a "
                        "metric. Values beyond the acceptable deviation are yellow, beyond the "
                        "critical deviation red (limits set per exercise)."
                    ),
                    html.P(CLOSENESS_NOTE),
                ],
                title="Reading the dashboards",
            ),
            card(html.Pre(describe(), className="pre"), title="File naming convention"),
            card(
                html.Ul(
                    [
                        html.Li(html.A("Source code (GitHub)", href=REPOSITORY, target="_blank")),
                        html.Li(html.A("Documentation", href=DOCUMENTATION, target="_blank")),
                    ]
                ),
                title="Links",
            ),
        ]
    )


dash.register_page(
    __name__,
    path="/about",
    name="About",
    order=5,
    title="About - DESTEST 3.0",
    layout=layout,
)
