# Web app

The web app shows the dashboards of the common modelling exercises in the browser. It is a
multi-page [Dash](https://dash.plotly.com/) application inside the package
(`src/destest/webapp/`), built on the same code as `destest dashboard`.

```bash
uv sync                    # installs Dash (dependency group "web")
uv run destest web         # http://127.0.0.1:8050
uv run destest web --debug --results "Result data"
```

## Pages

| Page | Path | Shows |
|---|---|---|
| Home | `/` | map of the contributions, submissions per month (timeline), their distribution (pie), the exercises (CMEs) with links |
| Overview | `/overview?cme=CME_DHN_1` | dashboard `overview` of the CME: all submissions |
| Detail | `/detail?cme=CME_DHN_1&submission=<id>` | dashboard `detail`: one submission |
| Comparison | `/comparison?cme=CME_DHN_1` | dashboard `comparison`: a selection of submissions |
| Contribute | `/contribute` | how to submit results (online upload: to be developed) |
| About | `/about` | DESTEST, the exercises, the naming convention, how to read the dashboards |

## What is shown comes from the spec files

The pages contain no exercise-specific code. Each dashboard page builds the dashboard listed in
the CME's spec file (`analysis.dashboards.overview`, `.detail`, `.comparison`) and renders every
panel in order: figures as interactive Plotly graphs, tables as HTML tables. Adding a KPI or a
visual to a CME's `analysis` section, or adding a new CME with an `analysis` section, shows up
in the app without changing the web code. See [Dashboards](dashboards.md).

Below the exercise selection, every dashboard page first shows a card describing the CME
(`cme.description`, `cme.characteristics`) and how its reference is built (`analysis.reference`,
`analysis.reference_note`), all taken from the spec file. The overview page ends with a
"Comments and observations" card listing `analysis.comments_and_observations` (if any).

On the home page, the map and the timeline each have a "Colour by" switch: by exercise
(each series one colour family, e.g. DHN blue and DCN green, lighter for lower exercise
numbers; `analysis/colors.py`), modelling tool or institution, and for the timeline also
country. A tool, institution or country has the same colour on every map and timeline.
The timeline has one column per month up to the current one, and opens scrolled to the
right. On the overview page, the map and the timeline of the selected CME have their own
switches (options from the CME spec file).

## Structure

```text
src/destest/webapp/
├── app.py           Dash app: navigation bar, page container; `server` for gunicorn
├── data.py          CMEs, submissions, dashboards, cached; reloaded when a result file changes
├── components.py    layout blocks; renders the dashboard panels
├── pages/           home, overview, detail, comparison, contribute, about
└── assets/style.css styling (auto-loaded by Dash)
```

Conventions (as in the NSBI Smart Building Mapping app):

- one module per page, registered with `dash.register_page(...)`; add it to `PAGES` in `app.py`;
- component ids are prefixed per page: `ov-`, `dt-`, `cmp-`; callbacks are private (`_name`);
- selections are remembered per browser tab (Dash persistence, sessionStorage).

## Data

The app reads the results from `DESTEST_RESULTS` (default `Result data`), one sub-folder per
CME. Result files that do not pass `destest check` are not shown; the overview lists them.

## Deployment (Docker)

```bash
docker build -t destest-web .
docker run -p 8080:8080 destest-web        # http://localhost:8080
```

The image installs the package and the `web` group with uv (no development tools), copies
`Result data/`, and serves the app with gunicorn (`destest.webapp.app:server`) on `$PORT`
(Cloud Run sets it). Results added later need a rebuild, or a mounted folder and
`DESTEST_RESULTS` pointing to it.

| Variable | Default | Purpose |
|---|---|---|
| `DESTEST_RESULTS` | `Result data` | folder with one sub-folder per CME |
| `PORT` | `8080` | port of the web server (set by Cloud Run) |
