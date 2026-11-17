"""DESTEST web app: multi-page Dash application.

Run locally:      uv run destest web               ->  http://127.0.0.1:8050
In production:    gunicorn "destest.webapp.app:server"   (see Dockerfile)

The pages are modules in `destest/webapp/pages/`; each registers itself with
`dash.register_page(...)` and appears in the navigation bar in `order`.
What a dashboard shows comes from the CME spec files (`analysis` section),
not from the page code.
"""

import importlib
from pathlib import Path
from typing import Any

import dash
from dash import Dash, dcc, html

#: Page modules, imported after the app exists (they call dash.register_page).
PAGES = ("home", "overview", "detail", "comparison", "contribute", "about")

ASSETS = Path(__file__).parent / "assets"

#: Logos at the top right of every page (files in assets/logos/): (file, name, link).
#: The browser-tab icon is assets/favicon.ico, picked up automatically by Dash.
LOGOS = [
    ("logos/sintef_logo.png", "SINTEF Community", "https://www.sintef.no/en/community/"),
    ("logos/ibpsa_nordic_logo.png", "IBPSA Nordic", "https://www.ibpsa-nordic.org/"),
]


def navbar(app: Dash) -> html.Header:
    """Top bar: name, one link per page, logos (as in the NSBI app)."""
    links = [
        dcc.Link(page["name"], href=page["relative_path"], className="nav-link")
        for page in sorted(dash.page_registry.values(), key=lambda p: p.get("order", 0))
    ]
    logos = [
        html.A(
            html.Img(src=app.get_asset_url(path), alt=name, className="nav-logo"),
            href=url,
            target="_blank",
            rel="noopener noreferrer",
            title=f"{name} - {url}",
        )
        for path, name, url in LOGOS
    ]
    return html.Header(
        className="navbar",
        children=[
            dcc.Link("DESTEST 3.0", href="/", className="brand"),
            html.Div(
                className="nav-right",
                children=[html.Nav(links), html.Div(logos, className="nav-logos")],
            ),
        ],
    )


def create_app() -> Dash:
    """Build the Dash app with all pages."""
    app = Dash(
        __name__,
        use_pages=True,
        pages_folder="",  # pages registered explicitly below (works when installed as a package)
        assets_folder=str(ASSETS),
        title="DESTEST 3.0",
        suppress_callback_exceptions=True,
    )
    for page in PAGES:
        importlib.import_module(f"{__package__}.pages.{page}")
    app.layout = html.Div(
        [
            navbar(app),
            html.Main(dash.page_container, className="container"),
            html.Footer(
                "DESTEST - District Energy Simulation Test Procedure (IBPSA Project 1)",
                className="footer",
            ),
        ]
    )
    return app


app = create_app()
server: Any = app.server  # WSGI entry point for gunicorn


def main(host: str = "127.0.0.1", port: int = 8050, debug: bool = False) -> None:
    """Run the development server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main(debug=True)
