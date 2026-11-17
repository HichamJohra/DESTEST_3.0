"""The pages of the web app, one module each (imported by `destest.webapp.app`).

Adding a page: create `pages/<name>.py` calling `dash.register_page(__name__, path=...,
name=..., order=...)` with a `layout()` function, and add `<name>` to `PAGES` in `app.py`.
Component ids are prefixed per page: `ov-` (overview), `dt-` (detail), `cmp-` (comparison).
"""
