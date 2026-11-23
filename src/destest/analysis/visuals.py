"""Visuals: tables and figures built from the analysis context.

Each visual is a function registered by name; a CME's spec file lists them per
dashboard (`analysis.dashboards.<kind>[].visual`) with their `options`. A visual
returns either a `Table` or a figure. Figures are Plotly figure specifications
(plain JSON: `{"data": [...], "layout": {...}}`), so any web front end can draw
them with plotly.js, and no plotting library is needed here.

To add a visual: write `def name(ctx: AnalysisContext, *, option=default, ...)`
returning a `Table` or a figure dict, and decorate it with `@visual("name")`.
Declare which options name KPIs or columns, so spec files are checked on load.
"""

import inspect
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from ..check import check_submission_files
from ..filename_check.validate import check_name, partner_names
from ..result import Issue
from ..results import Submission
from .context import REFERENCE_COLOR, AnalysisContext
from .maps import MapPoint, category_map, hover_text, locate, meta_value, spread

Figure = dict[str, Any]


@dataclass
class Table:
    """A table: header row, body rows (as text), and a CSS class per body cell.

    Cell classes (space-separated): `warn`, `bad` (deviation thresholds), `ref`
    (reference), `score` (closeness grade), `wrap` (long text that may wrap).
    A new line in a cell is kept (shown as a line break).
    `align`: per column `left`, `center` or `right` (default: first left, others right).
    `colors`: a background colour per body cell (`""` for none), e.g. the rank colours.
    `full_width`: stretch the table to the width of the page.
    `data` holds the same rows as numbers, for a front end that formats itself.
    """

    headers: list[str]
    rows: list[list[str]]
    classes: list[list[str]] = field(default_factory=list)
    data: list[list[Any]] = field(default_factory=list)
    note: str = ""
    align: list[str] = field(default_factory=list)
    colors: list[list[str]] = field(default_factory=list)
    full_width: bool = False

    def alignment(self, column: int) -> str:
        """Alignment of a column: `align` if given, else left for the first, right for others."""
        if column < len(self.align) and self.align[column]:
            return self.align[column]
        return "left" if column == 0 else "right"

    def color(self, row: int, column: int) -> str:
        """Background colour of a body cell (`""` for none)."""
        if row < len(self.colors) and column < len(self.colors[row]):
            return self.colors[row][column]
        return ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return asdict(self)


Builder = Callable[..., Table | Figure]


@dataclass(frozen=True)
class Visual:
    """A registered visual and which of its options refer to KPIs or columns."""

    name: str
    builder: Builder
    kpi_options: tuple[str, ...] = ()
    column_options: tuple[str, ...] = ()

    @property
    def options(self) -> set[str]:
        """The keyword options the visual accepts."""
        sig = inspect.signature(self.builder)
        kinds = (inspect.Parameter.KEYWORD_ONLY,)
        return {p.name for p in sig.parameters.values() if p.kind in kinds}


#: name -> visual. Filled by the `@visual` decorator below.
VISUALS: dict[str, Visual] = {}


def visual(
    name: str, *, kpi_options: tuple[str, ...] = (), column_options: tuple[str, ...] = ()
) -> Callable[[Builder], Builder]:
    """Register a visual under `name`."""

    def register(f: Builder) -> Builder:
        VISUALS[name] = Visual(name, f, kpi_options, column_options)
        return f

    return register


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def fmt(value: float | None, digits: int = 4) -> str:
    """A number with `digits` significant digits; `-` when missing.

    >>> fmt(23006.4), fmt(69.937), fmt(0.000123), fmt(None)
    ('23010', '69.94', '0.000123', '-')
    """
    if value is None or not math.isfinite(value):
        return "-"
    if value == 0:
        return "0"
    if not 1e-3 <= abs(value) < 1e7:
        return f"{value:.{digits}g}"
    rounded = float(f"{value:.{digits}g}")  # e.g. 23006.4 -> 23010, 69.937 -> 69.94
    decimals = max(digits - 1 - math.floor(math.log10(abs(rounded))), 0)
    return f"{rounded:.{decimals}f}"


def _deviation_class(dev: float | None, warn: float, bad: float) -> str:
    if dev is None:
        return ""
    return "bad" if abs(dev) >= bad else ("warn" if abs(dev) >= warn else "")


def _axis(i: int) -> str:
    """Plotly axis suffix: '' for the first subplot, then '2', '3', ..."""
    return "" if i == 0 else str(i + 1)


def _stacked_layout(n: int, height_each: int = 260) -> dict[str, Any]:
    """Layout of `n` subplots stacked vertically, each with its own axes."""
    return {
        "grid": {"rows": n, "columns": 1, "pattern": "independent", "roworder": "top to bottom"},
        "height": max(320, height_each * n),
        "margin": {"l": 70, "r": 20, "t": 30, "b": 40},
        "showlegend": True,
        "legend": {"orientation": "h"},
    }


def _label(sub: Submission) -> str:
    return sub.label


def _closeness_text(ctx: AnalysisContext, sub: Submission) -> str:
    """E.g. `87.5 (rank 2 of 7)`."""
    grade, rank = ctx.closeness.get(sub.id), ctx.closeness_rank(sub)
    if grade is None or rank is None:
        return "-"
    return f"{grade:.1f} (rank {rank[0]} of {rank[1]})"


def rank_color(rank: int, n: int) -> str:
    """Background colour of a rank: green for the first, pale red for the last.

    >>> rank_color(1, 7), rank_color(7, 7)
    ('#8fd19e', '#f7c6c5')
    """
    # green -> pale yellow -> pale red (a straight green-red blend turns grey in the middle)
    stops = ((0x8F, 0xD1, 0x9E), (0xFB, 0xEC, 0xB0), (0xF7, 0xC6, 0xC5))
    f = 0.0 if n <= 1 else (rank - 1) / (n - 1)
    start, end = (stops[0], stops[1]) if f <= 0.5 else (stops[1], stops[2])
    f = f * 2 if f <= 0.5 else (f - 0.5) * 2
    r, g, b = (round(a + (z - a) * f) for a, z in zip(start, end, strict=True))
    return f"#{r:02x}{g:02x}{b:02x}"


def _closeness_color(ctx: AnalysisContext, sub: Submission) -> str:
    rank = ctx.closeness_rank(sub)
    return rank_color(*rank) if rank else ""


CLOSENESS_LABEL = "Closeness to the reference [0-100]"
CLOSENESS_NOTE = (
    "Closeness to the reference: for each KPI, the closest submission scores 100 and the "
    "furthest 0, the others linearly in between by their distance to the reference; the "
    "grade is the mean over all KPIs."
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------
@visual("kpi_table", kpi_options=("kpis",))
def kpi_table(
    ctx: AnalysisContext,
    *,
    kpis: str | list[str] = "all",
    deviation: bool = True,
    closeness: bool = True,
    warn_pct: float = 5.0,
    bad_pct: float = 20.0,
) -> Table:
    """KPI values: one row per KPI, one column per submission, plus the reference.

    With `deviation`, each value is followed by its deviation from the reference
    in %, and cells beyond `warn_pct` / `bad_pct` are marked. With `closeness`,
    the first row is the closeness-to-the-reference grade (0-100) over all KPIs.
    """
    keys = ctx.kpi_keys(kpis)
    headers = ["KPI", ctx.reference_label, *(_label(s) for s in ctx.focus)]
    rows: list[list[str]] = []
    classes: list[list[str]] = []
    data: list[list[Any]] = []
    colors: list[list[str]] = []
    if closeness:
        rows.append([CLOSENESS_LABEL, "100", *(_closeness_text(ctx, s) for s in ctx.focus)])
        classes.append(["score", "ref score", *("score" for _ in ctx.focus)])
        data.append([CLOSENESS_LABEL, 100.0, *(ctx.closeness.get(s.id) for s in ctx.focus)])
        colors.append(["", "", *(_closeness_color(ctx, s) for s in ctx.focus)])
    for key in keys:
        ref = ctx.reference.get(key)
        row = [ctx.kpi_label(key), fmt(ref)]
        cls = ["", "ref"]
        raw: list[Any] = [ctx.kpi_label(key), ref]
        for s in ctx.focus:
            value = ctx.kpi_values[s.id].get(key)
            dev = ctx.metric("relative_deviation", s, key) if deviation else None
            text = fmt(value)
            if deviation and dev is not None:
                text += f" ({dev:+.1f} %)"
            row.append(text)
            cls.append(_deviation_class(dev, warn_pct, bad_pct))
            raw.append(value)
        rows.append(row)
        classes.append(cls)
        data.append(raw)
    notes = []
    if deviation:
        notes.append(
            f"Deviation from the reference in brackets; marked from {warn_pct:g} % and "
            f"{bad_pct:g} %."
        )
    if closeness:
        notes.append(CLOSENESS_NOTE)
    return Table(headers, rows, classes, data, " ".join(notes), colors=colors)


@visual("metadata_table")
def metadata_table(
    ctx: AnalysisContext,
    *,
    sections: str | list[str] | None = None,
) -> Table:
    """Metadata side by side: one row per metadata field, one column per submission.

    `sections`: a list of sections, or `"all"` for the whole metadata files.
    Default: modelling_tool, simulation_config, model_details.
    """
    if sections == "all":
        wanted: list[str] = []
        for s in ctx.focus:
            wanted += [k for k in s.metadata if k not in wanted and k != "metadata_format_version"]
    elif isinstance(sections, list):
        wanted = sections
    else:
        wanted = ["modelling_tool", "simulation_config", "model_details"]
    headers = ["Field", *(_label(s) for s in ctx.focus)]
    rows: list[list[str]] = []
    for section in wanted:
        keys: list[str] = []
        for s in ctx.focus:
            block = s.metadata.get(section)
            if isinstance(block, dict):
                keys += [k for k in block if k not in keys]
            elif section in s.metadata and "" not in keys:
                keys.append("")
        for key in keys:
            row = [f"{section}.{key}" if key else section]
            for s in ctx.focus:
                block = s.metadata.get(section)
                value = block.get(key) if isinstance(block, dict) and key else block
                row.append("-" if value in (None, "") else str(value).strip())
            rows.append(row)
    classes = [["", *("wrap" for _ in ctx.focus)] for _ in rows]
    note = "" if rows else "No metadata files found for these submissions."
    return Table(headers, rows, classes, note=note, full_width=True)


def _issue_lines(reports: list[tuple[str, list[Issue]]]) -> str:
    """One line per issue, `stage/where: message`; an issue found in both the data and
    the metadata file (e.g. a name warning) is shown once, marked with both files."""
    seen: dict[str, list[str]] = {}
    for file_kind, issues in reports:
        for i in issues:
            text = f"{i.stage}/{i.field}: {i.message}" if i.stage else f"{i.field}: {i.message}"
            seen.setdefault(text, [])
            if file_kind not in seen[text]:
                seen[text].append(file_kind)
    return "\n".join(f"[{' + '.join(kinds)}] {text}" for text, kinds in seen.items()) or "-"


@visual("data_check_table")
def data_check_table(ctx: AnalysisContext, *, closeness: bool = True) -> Table:
    """One row per submission: creation date (from the file name), `destest check` result
    of the data and metadata files, the closeness grade coloured by rank, and the errors
    and warnings, one per line."""
    headers = ["Submission", "Created", "Data file", "Metadata file"]
    headers += [CLOSENESS_LABEL] if closeness else []
    headers += ["Errors", "Warnings"]
    align = ["left", "center", "center", "center"]
    align += ["center"] if closeness else []
    align += ["left", "left"]
    rows: list[list[str]] = []
    classes: list[list[str]] = []
    colors: list[list[str]] = []
    for s in ctx.focus:
        partners = partner_names(check_name(s.path.name))
        paths = [s.path, *(s.path.parent / n for n in partners)]
        reports = check_submission_files([p for p in paths if p.exists()])
        data = next((r for r in reports if r.path == s.path), None)
        meta = next((r for r in reports if r.path != s.path), None)
        kinds = [("data" if r.path == s.path else "metadata", r) for r in reports]
        created = s.name_parts.get("creation_date_time")
        row = [
            _label(s),
            f"{created:%Y-%m-%d %H:%M}" if created is not None else "-",
            data.status if data else "-",
            meta.status if meta else "missing",
        ]
        cls = ["", "", "", ""]
        col = ["", "", "", ""]
        if closeness:
            row.append(_closeness_text(ctx, s))
            cls.append("score")
            col.append(_closeness_color(ctx, s))
        n_err = sum(len(r.errors) for _, r in kinds)
        n_warn = sum(len(r.warnings) for _, r in kinds)
        row.append(_issue_lines([(k, r.errors) for k, r in kinds]))
        row.append(_issue_lines([(k, r.warnings) for k, r in kinds]))
        cls += ["bad" if n_err else "", "warn" if n_warn else ""]
        col += ["", ""]
        rows.append(row)
        classes.append(cls)
        colors.append(col)
    return Table(headers, rows, classes, align=align, colors=colors, full_width=True)


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------
@visual("deviation_heatmap", kpi_options=("kpis",))
def deviation_heatmap(
    ctx: AnalysisContext,
    *,
    kpis: str | list[str] = "all",
    metric: str = "relative_deviation",
    limit: float | None = None,
) -> Figure:
    """Matrix submissions x KPIs of a metric against the reference (e.g. deviation in %).

    `metric`: a value metric (`relative_deviation`, ...) or a series metric on the
    KPI's column (`nmbe`, `cvrmse`, ...). The colour scale is centred on 0 and
    capped at `limit` (default: the largest absolute value).
    """
    keys = ctx.kpi_keys(kpis)
    z = [[ctx.metric(metric, s, k) for k in keys] for s in ctx.focus]
    finite = [abs(v) for row in z for v in row if v is not None and math.isfinite(v)]
    cap = limit if limit is not None else (max(finite) if finite else 1.0)
    unit = ctx.metric_unit(metric, keys[0]) if keys else ""
    return {
        "data": [
            {
                "type": "heatmap",
                "z": z,
                "x": [ctx.kpi(k).label for k in keys],
                "y": [_label(s) for s in ctx.focus],
                "text": [[fmt(v, 3) for v in row] for row in z],
                "texttemplate": "%{text}",
                "colorscale": "RdBu",
                "reversescale": True,
                "zmid": 0,
                "zmin": -cap,
                "zmax": cap,
                "colorbar": {"title": {"text": f"{metric} [{unit}]" if unit else metric}},
            }
        ],
        "layout": {
            "height": max(300, 60 * len(ctx.focus) + 200),
            "margin": {"l": 260, "r": 20, "t": 20, "b": 160},
            "xaxis": {"tickangle": -45},
            "yaxis": {"autorange": "reversed"},
        },
    }


@visual("kpi_bar", kpi_options=("kpis",))
def kpi_bar(
    ctx: AnalysisContext,
    *,
    kpis: str | list[str] = "all",
    show_reference: bool = True,
) -> Figure:
    """One bar chart per KPI (stacked vertically): one bar per submission."""
    keys = ctx.kpi_keys(kpis)
    layout = _stacked_layout(len(keys), height_each=320)
    layout["grid"]["ygap"] = 0.45  # room for the labels under each chart
    layout["margin"] = {"l": 70, "r": 20, "t": 40, "b": 70}
    layout["legend"] = {"orientation": "h", "x": 1, "xanchor": "right", "y": 1.02}
    layout["legend"]["yanchor"] = "bottom"
    data: list[dict[str, Any]] = []
    shapes: list[dict[str, Any]] = []
    for i, key in enumerate(keys):
        ax = _axis(i)
        data.append(
            {
                "type": "bar",
                "x": [s.tick_label for s in ctx.focus],
                "y": [ctx.kpi_values[s.id].get(key) for s in ctx.focus],
                "marker": {"color": [ctx.colors[s.id] for s in ctx.focus]},
                "name": ctx.kpi(key).label,
                "showlegend": False,
                "hovertemplate": "%{x}<br>%{y:.4g}<extra></extra>",
                "xaxis": f"x{ax}",
                "yaxis": f"y{ax}",
            }
        )
        layout[f"yaxis{ax}"] = {"title": {"text": ctx.kpi_label(key)}}
        layout[f"xaxis{ax}"] = {"tickangle": 0, "automargin": True}
        ref = ctx.reference.get(key)
        if show_reference and ref is not None:
            shapes.append(
                {
                    "type": "line",
                    "xref": f"x{ax} domain",
                    "x0": 0,
                    "x1": 1,
                    "yref": f"y{ax}",
                    "y0": ref,
                    "y1": ref,
                    "line": {"color": REFERENCE_COLOR, "dash": "dash", "width": 1.5},
                }
            )
    layout["shapes"] = shapes
    if shapes:  # a legend entry for the dashed line (shapes have none)
        data.append(
            {
                "type": "scatter",
                "x": [None],
                "y": [None],
                "mode": "lines",
                "name": f"{ctx.reference_label} (dashed line)",
                "line": {"color": REFERENCE_COLOR, "dash": "dash", "width": 1.5},
                "hoverinfo": "skip",
            }
        )
    return {"data": data, "layout": layout}


@visual("profile", kpi_options=("kpis",))
def profile(
    ctx: AnalysisContext,
    *,
    kpis: list[str],
    x_labels: list[str] | None = None,
    y_title: str = "",
    show_reference: bool = True,
) -> Figure:
    """Several KPIs along an axis (e.g. temperatures along the network), one line per submission."""
    x = x_labels or [ctx.kpi(k).label for k in kpis]
    data: list[dict[str, Any]] = [
        {
            "type": "scatter",
            "mode": "lines+markers",
            "x": x,
            "y": [ctx.kpi_values[s.id].get(k) for k in kpis],
            "name": _label(s),
            "line": {"color": ctx.colors[s.id]},
        }
        for s in ctx.focus
    ]
    if show_reference:
        data.append(
            {
                "type": "scatter",
                "mode": "lines",
                "x": x,
                "y": [ctx.reference.get(k) for k in kpis],
                "name": ctx.reference_label,
                "line": {"color": REFERENCE_COLOR, "dash": "dash"},
            }
        )
    unit = ctx.kpi(kpis[0]).unit if kpis else ""
    return {
        "data": data,
        "layout": {
            "height": 420,
            "margin": {"l": 70, "r": 20, "t": 20, "b": 60},
            "yaxis": {"title": {"text": y_title or unit}},
            "legend": {"orientation": "h"},
        },
    }


@visual("time_series", column_options=("columns",))
def time_series(
    ctx: AnalysisContext,
    *,
    columns: list[str],
    show_reference: bool = False,
) -> Figure:
    """Time series of some columns (one subplot per column), one line per submission."""
    layout = _stacked_layout(len(columns))
    data: list[dict[str, Any]] = []
    for i, col in enumerate(columns):
        ax = _axis(i)
        for s in ctx.focus:
            if col not in s.series:
                continue
            data.append(
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": ctx.time(s),
                    "y": s.series[col],
                    "name": _label(s),
                    "legendgroup": s.id,
                    "showlegend": i == 0,
                    "line": {"color": ctx.colors[s.id]},
                    "xaxis": f"x{ax}",
                    "yaxis": f"y{ax}",
                }
            )
        if show_reference and ctx.focus:
            data.append(
                {
                    "type": "scatter",
                    "mode": "lines",
                    "x": ctx.time(ctx.focus[0]),
                    "y": ctx.series_reference(col),
                    "name": ctx.reference_label,
                    "legendgroup": "reference",
                    "showlegend": i == 0,
                    "line": {"color": REFERENCE_COLOR, "dash": "dash"},
                    "xaxis": f"x{ax}",
                    "yaxis": f"y{ax}",
                }
            )
        layout[f"yaxis{ax}"] = {"title": {"text": ctx.column_label(col)}}
    t = ctx.spec.result_data.time
    layout[f"xaxis{_axis(len(columns) - 1)}"] = {
        "title": {"text": f"Time [{t.unit}]" if t else "Row"}
    }
    return {"data": data, "layout": layout}


@visual("carpet", column_options=("column",))
def carpet(
    ctx: AnalysisContext,
    *,
    column: str,
    period: int = 24,
    x_title: str = "Hour of the day",
    y_title: str = "Day",
) -> Figure:
    """Carpet plot of one column: the series cut into rows of `period` values
    (e.g. 24 hourly values per day), one heatmap per submission."""
    layout = _stacked_layout(len(ctx.focus), height_each=320)
    layout["showlegend"] = False
    data: list[dict[str, Any]] = []
    for i, s in enumerate(ctx.focus):
        values = s.series.get(column, [])
        rows = [list(values[j : j + period]) for j in range(0, len(values), period)]
        ax = _axis(i)
        data.append(
            {
                "type": "heatmap",
                "z": rows,
                "x": list(range(period)),
                "y": list(range(len(rows))),
                "colorscale": "Viridis",
                "name": _label(s),
                "showscale": i == 0,
                "xaxis": f"x{ax}",
                "yaxis": f"y{ax}",
            }
        )
        layout[f"yaxis{ax}"] = {"title": {"text": f"{_label(s)}<br>{y_title}"}}
        layout[f"xaxis{ax}"] = {"title": {"text": x_title}}
    return {"data": data, "layout": layout}


@visual("closeness_bar")
def closeness_bar(
    ctx: AnalysisContext, *, colors: str = "submission", submissions: str = "all"
) -> Figure:
    """Closeness-to-the-reference grade of every submission, best first.

    `colors`: `submission` (each submission its own colour, as in the other charts)
    or `rank` (green for the first to pale red for the last, as in the tables).
    `submissions`: `all` (submissions not shown on the dashboard are grey, to show
    where the focus stands among all) or `selected` (only the dashboard's own
    submissions; the rank colours stay those among all).
    """
    if submissions not in ("all", "selected"):
        raise ValueError(f"submissions must be 'all' or 'selected' (got '{submissions}')")
    ranked = sorted(
        (s for s in ctx.submissions if ctx.closeness.get(s.id) is not None),
        key=lambda s: -(ctx.closeness[s.id] or 0.0),
    )
    focus_ids = {s.id for s in ctx.focus}
    n = len(ranked)

    def color(i: int, s: Submission) -> str:
        if s.id not in focus_ids:
            return "#cccccc"
        return rank_color(i + 1, n) if colors == "rank" else ctx.colors[s.id]

    shown = [(i, s) for i, s in enumerate(ranked) if submissions == "all" or s.id in focus_ids]
    grades = [ctx.closeness[s.id] for _, s in shown]
    return {
        "data": [
            {
                "type": "bar",
                "x": [s.tick_label for _, s in shown],
                "y": grades,
                "text": [fmt(g, 3) for g in grades],
                "textposition": "outside",
                "marker": {
                    "color": [color(i, s) for i, s in shown],
                    "line": {"color": "#5d6675", "width": 0.5},
                },
                "customdata": [f"rank {i + 1} of {n}" for i, _ in shown],
                "hovertemplate": "%{x}<br>%{y:.1f} (%{customdata})<extra></extra>",
            }
        ],
        "layout": {
            "height": 380,
            "bargap": 0.2 if len(shown) > 3 else 0.6,  # a single bar is not page-wide
            "margin": {"l": 60, "r": 20, "t": 20, "b": 70},
            "yaxis": {"title": {"text": CLOSENESS_LABEL}, "range": [0, 110]},
            "xaxis": {"tickangle": 0, "automargin": True},
        },
    }


#: Metadata fields offered in the colour menu of the map, by default.
MAP_COLOR_BY = (
    "modelling_tool.name",
    "modeller.institution",
    "modeller.institution_country",
    "modelling_tool.licence",
)


@visual("contributions_map")
def contributions_map(
    ctx: AnalysisContext,
    *,
    color_by: list[str] | None = None,
    height: int = 560,
) -> Figure:
    """Map of the submissions at their institution's city (see `destest.analysis.maps`).

    The menu colours the markers by a metadata field (`color_by`, as `section.key`).
    A submission whose city and country are unknown is counted under the map.
    """
    fields = list(color_by or MAP_COLOR_BY)
    points: list[MapPoint] = []
    missing = 0
    for s in ctx.focus:
        where = locate(s)
        if where is None:
            missing += 1
            continue
        hover = hover_text(s, f"Closeness: {fmt(ctx.closeness.get(s.id), 3)}")
        points.append(MapPoint(*where, hover, {f: meta_value(s, f) for f in fields}))
    spread(points)
    note = f"Not placed (city/country unknown): {missing}" if missing else ""
    return category_map(points, fields, height=height, note=note)
