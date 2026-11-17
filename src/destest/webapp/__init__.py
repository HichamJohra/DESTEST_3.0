"""The DESTEST web app (Dash): dashboards of the common modelling exercises.

```text
webapp/
├── app.py           the Dash app: navigation bar, pages; `server` for gunicorn
├── data.py          CMEs, submissions and dashboards, cached (reloaded when files change)
├── components.py    layout blocks; renders the dashboard panels of a CME spec file
├── pages/           one module per page: home, overview, detail, comparison, contribute, about
└── assets/          style.css (auto-loaded by Dash)
```

The pages only display what `destest.analysis` builds from the CME spec files: adding a
KPI or a visual to a CME's `analysis` section shows it in the web app without code changes.

Needs the `web` dependency group (`uv sync` installs it). Run with `destest web`.
"""
