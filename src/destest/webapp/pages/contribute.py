"""Contribute page: how to submit results. Online upload: to be developed.

For now it explains the procedure with the existing tools (`destest new-submission`,
`destest check`). The upload form (with the same checks run on the server) will be
added here later.
"""

from typing import Any

import dash
from dash import dcc, html

from ..components import card, message, page_head
from ..data import cme_names


def layout(**_: Any) -> html.Div:
    names = ", ".join(cme_names()) or "-"
    return html.Div(
        [
            page_head("Contribute results", "Take part in a common modelling exercise."),
            message(
                "Online submission is being developed. Until then, follow the steps below.", "info"
            ),
            card(
                html.Ol(
                    [
                        html.Li(
                            [
                                "Model the exercise as described in the DESTEST case report. "
                                f"Exercises with a dashboard: {names}."
                            ]
                        ),
                        html.Li(
                            [
                                "Create the two files of your submission, correctly named: ",
                                html.Code(
                                    "destest new-submission --series DHN --exercise-number 1 "
                                    "--tool <Tool> --tool-version <Version> --institution <Inst> "
                                    "--first-name <First> --last-name <Last> -o <folder>"
                                ),
                                " (or the script scripts/new_submission.py).",
                            ]
                        ),
                        html.Li(
                            "Paste your results under the header of the ResultData file, and fill "
                            "in the ResultMetadata file."
                        ),
                        html.Li(["Check both files: ", html.Code("destest check <folder>"), "."]),
                        html.Li("Send the two files to the DESTEST organisers."),
                    ]
                ),
                title="How to submit",
            ),
            card(
                html.P(
                    [
                        "The naming convention, the file formats and the checks are described "
                        "in the ",
                        dcc.Link("About", href="/about"),
                        " page and in the project documentation.",
                    ]
                ),
                title="More information",
            ),
        ]
    )


dash.register_page(
    __name__,
    path="/contribute",
    name="Contribute",
    order=4,
    title="Contribute - DESTEST 3.0",
    layout=layout,
)
