"""Visuals: tables and figures built from the analysis context.

Each visual is a function registered by name; a CME's spec file lists them per
dashboard (`analysis.dashboards.<kind>[].visual`) with their `options`. A visual
returns either a `Table` or a figure. Figures are Plotly figure specifications
(plain JSON: `{"data": [...], "layout": {...}}`), so any web front end can draw
them with plotly.js, and no plotting library is needed here.

To add a visual: write `def name(ctx: AnalysisContext, *, option=default, ...)`
returning a `Table` or a figure dict, and decorate it with `@visual("name")`.
Declare which options name compared items or columns, so spec files are checked on load.
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
from .colors import category_colors
from .context import REFERENCE_COLOR, AnalysisContext, ResultItem
from .maps import (
    MapPoint,
    category_map,
    contributions_pie,
    hover_text,
    locate,
    meta_value,
    spread,
)
from .timeline import Timeline, submission_timeline

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


@dataclass
class Choice:
    """Several versions of one visual; the viewer picks one (e.g. the colouring).

    `options`: option label -> figure or timeline, the first shown by default.
    """

    label: str
    options: dict[str, Figure | Timeline]

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {
            "label": self.label,
            "options": {
                k: v.to_dict() if isinstance(v, Timeline) else v for k, v in self.options.items()
            },
        }


Builder = Callable[..., Table | Figure | Choice | Timeline]


@dataclass(frozen=True)
class Visual:
    """A registered visual and which of its options refer to compared items or columns."""

    name: str
    builder: Builder
    item_options: tuple[str, ...] = ()
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
    name: str, *, item_options: tuple[str, ...] = (), column_options: tuple[str, ...] = ()
) -> Callable[[Builder], Builder]:
    """Register a visual under `name`."""

    def register(f: Builder) -> Builder:
        VISUALS[name] = Visual(name, f, item_options, column_options)
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


CLOSENESS_LABEL = "Closeness to target [0-100]"
CLOSENESS_NOTE = (
    "Closeness to target (accuracy grade): for each compared item, the closest "
    "submission scores 100 and the furthest 0, the others linearly in between by their "
    "distance to the item's target (median of all submissions, set target, or ideal value of "
    "the metric); the grade is the mean over all items, weighted by the item weights."
)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------
def _limit_text(item: ResultItem, value: float | None) -> str:
    """E.g. `±5 %` (relative) or `±0.5 K` (absolute); `-` without limits."""
    if value is None:
        return "-"
    unit = "%" if item.deviation_mode == "relative" else item.unit
    return f"±{value:g} {unit}".rstrip()


def ranked_focus(ctx: AnalysisContext) -> list[Submission]:
    """The shown submissions, best accuracy grade first (no grade: last, in order)."""

    def key(s: Submission) -> tuple[bool, float]:
        grade = ctx.closeness.get(s.id)
        return grade is None, -(grade or 0.0)

    return sorted(ctx.focus, key=key)


def _results_row(
    ctx: AnalysisContext,
    key: str,
    weights: bool,
    limits: bool,
    deviation: bool,
    subs: list[Submission],
) -> tuple[list[str], list[str], list[Any]]:
    """One row of the results table: texts, cell classes and raw values."""
    item = ctx.item(key)
    ref = ctx.reference.get(key)
    how = ctx.reference_text(key)
    if ref is None:
        ref_text = "-"
    elif how:
        ref_text = f"{ref:g} ({how})"
    else:
        ref_text = f"{fmt(ref)} (reference: {ctx.analysis.reference} of {len(ctx.submissions)})"
    lim = item.limits
    bounds: list[float | None] = [lim.acceptable, lim.critical] if lim else [None, None]
    l_text = [_limit_text(item, b) for b in bounds] if limits else []
    row = [ctx.item_label(key), *([f"{item.weight:g}"] if weights else []), ref_text, *l_text]
    # the limit cells take the colour of the values beyond them (yellow, red)
    l_cls = (["warn", "bad"] if lim else ["", ""]) if limits else []
    cls = ["", *([""] if weights else []), "ref", *l_cls]
    raw: list[Any] = [
        ctx.item_label(key),
        *([item.weight] if weights else []),
        ref,
        *(bounds if limits else []),
    ]
    for s in subs:
        value = ctx.values[s.id].get(key)
        text = fmt(value)
        if deviation and item.deviation_mode == "relative":
            dev = ctx.deviation(s, key)
            if dev is not None:
                text += f" ({dev:+.1f} %)"
        row.append(text)
        cls.append(ctx.highlight(s, key) if limits else "")
        raw.append(value)
    return row, cls, raw


@visual("results_table", item_options=("items",))
def results_table(
    ctx: AnalysisContext,
    *,
    items: str | list[str] = "all",
    deviation: bool = True,
    closeness: bool = True,
    weights: bool = True,
    limits: bool = True,
    zero_weight_last: bool = True,
    ranked: bool = True,
) -> Table:
    """All compared items: one row per item, one column per submission.

    The `Target` column gives each item's reference: the median of all submissions, the
    target of a physics check, or the ideal value of a comparison metric. With `limits`,
    two columns give the acceptable and critical deviation from it (`limits` in the CME
    spec file); values beyond them are highlighted yellow and red. With `deviation`,
    values compared with the median are followed by their deviation in %. With
    `closeness`, the first row is the accuracy grade (0-100); with `weights`, a column
    gives each item's weight in it. With `zero_weight_last`, the items that do not count
    in the grade (weight 0) come last, below a separator row. With `ranked`, the
    submissions are ordered by accuracy grade, best first (left).
    """
    subs = ranked_focus(ctx) if ranked else list(ctx.focus)
    keys = ctx.item_keys(items)
    not_counted: list[str] = []
    if zero_weight_last:
        not_counted = [k for k in keys if ctx.item(k).weight == 0]
        keys = [k for k in keys if ctx.item(k).weight != 0]
    w_head = ["Weight"] if weights else []
    l_head = ["Acceptable deviation", "Critical deviation"] if limits else []
    headers = ["Compared item", *w_head, "Target", *l_head, *(_label(s) for s in subs)]
    rows: list[list[str]] = []
    classes: list[list[str]] = []
    data: list[list[Any]] = []
    colors: list[list[str]] = []
    if closeness:
        total = sum(i.weight for i in ctx.items)
        w_text = [f"{total:g} (sum)"] if weights else []
        w_blank, l_blank = [""] * len(w_head), [""] * len(l_head)
        rows.append(
            [
                CLOSENESS_LABEL,
                *w_text,
                "100 (ideal)",
                *([""] * len(l_head)),
                *(_closeness_text(ctx, s) for s in subs),
            ]
        )
        classes.append(["score", *w_blank, "ref score", *l_blank, *("score" for _ in ctx.focus)])
        data.append(
            [
                CLOSENESS_LABEL,
                *([total] if weights else []),
                100.0,
                *([None] * len(l_head)),
                *(ctx.closeness.get(s.id) for s in subs),
            ]
        )
        colors.append(["", *w_blank, "", *l_blank, *(_closeness_color(ctx, s) for s in subs)])
    for key in keys:
        row, cls, raw = _results_row(ctx, key, weights, limits, deviation, subs)
        rows.append(row)
        classes.append(cls)
        data.append(raw)
    if not_counted:
        width = len(headers)
        label = "Not counted in the grade (weight 0): shown for verification"
        rows.append([label, *([""] * (width - 1))])
        classes.append(["ref"] * width)
        data.append([label, *([None] * (width - 1))])
        for key in not_counted:
            row, cls, raw = _results_row(ctx, key, weights, limits, deviation, subs)
            rows.append(row)
            classes.append(cls)
            data.append(raw)
    notes = []
    if limits:
        notes.append(
            "Highlighted: yellow beyond the acceptable deviation, red beyond the critical "
            "deviation from the target (limits set per CME)."
        )
    if deviation:
        notes.append("Deviation from the median in brackets.")
    if closeness:
        notes.append(CLOSENESS_NOTE)
    align = ["left", *(["center"] * len(w_head)), "right", *(["center"] * len(l_head))]
    return Table(headers, rows, classes, data, " ".join(notes), align=align, colors=colors)


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
def data_check_table(
    ctx: AnalysisContext,
    *,
    closeness: bool = True,
    first_column: str = "Submission",
    ranked: bool = True,
) -> Table:
    """One row per submission: creation date (from the file name), `destest check` result
    of the data and metadata files, the closeness grade coloured by rank, and the errors
    and warnings, one per line. `first_column`: header of the submission column. With
    `ranked`, rows are ordered by accuracy grade, best first."""
    headers = [first_column, "Created", "Data file", "Metadata file"]
    headers += [CLOSENESS_LABEL] if closeness else []
    headers += ["Errors", "Warnings"]
    align = ["left", "center", "center", "center"]
    align += ["center"] if closeness else []
    align += ["left", "left"]
    rows: list[list[str]] = []
    classes: list[list[str]] = []
    colors: list[list[str]] = []
    for s in ranked_focus(ctx) if ranked else ctx.focus:
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
@visual("deviation_heatmap", item_options=("items",))
def deviation_heatmap(
    ctx: AnalysisContext,
    *,
    items: str | list[str] = "general",
    metric: str = "relative_deviation",
    limit: float | None = None,
) -> Figure:
    """Matrix submissions x compared items of a difference or metric (e.g. deviation in %).

    `metric`: a difference from the item's reference (`relative_deviation`,
    `absolute_deviation`) or a comparison metric on the item's column against the
    reference series (`NMBE`, `CVRMSE`, ...). `items`: `general` (default: the general
    comparison), `all` or a list of keys. The colour scale is centred on 0 and capped at
    `limit` (default: the largest absolute value).
    """
    keys = ctx.item_keys(items)
    z = [[ctx.metric(metric, s, k) for k in keys] for s in ctx.focus]
    finite = [abs(v) for row in z for v in row if v is not None and math.isfinite(v)]
    cap = limit if limit is not None else (max(finite) if finite else 1.0)
    unit = ctx.metric_unit(metric, keys[0]) if keys else ""
    return {
        "data": [
            {
                "type": "heatmap",
                "z": z,
                "x": [ctx.item(k).label for k in keys],
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


@visual("value_bar", item_options=("items",))
def value_bar(
    ctx: AnalysisContext,
    *,
    items: str | list[str] = "general",
    show_reference: bool = True,
) -> Figure:
    """One bar chart per compared item (stacked vertically): one bar per submission."""
    keys = ctx.item_keys(items)
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
                "y": [ctx.values[s.id].get(key) for s in ctx.focus],
                "marker": {"color": [ctx.colors[s.id] for s in ctx.focus]},
                "name": ctx.item(key).label,
                "showlegend": False,
                "hovertemplate": "%{x}<br>%{y:.4g}<extra></extra>",
                "xaxis": f"x{ax}",
                "yaxis": f"y{ax}",
            }
        )
        layout[f"yaxis{ax}"] = {"title": {"text": ctx.item_label(key)}}
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


@visual("profile", item_options=("items",))
def profile(
    ctx: AnalysisContext,
    *,
    items: list[str],
    x_labels: list[str] | None = None,
    y_title: str = "",
    show_reference: bool = True,
) -> Figure:
    """Several compared items along an axis (e.g. temperatures along the network).

    One line per submission, plus the reference (dashed).
    """
    x = x_labels or [ctx.item(k).label for k in items]
    data: list[dict[str, Any]] = [
        {
            "type": "scatter",
            "mode": "lines+markers",
            "x": x,
            "y": [ctx.values[s.id].get(k) for k in items],
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
                "y": [ctx.reference.get(k) for k in items],
                "name": ctx.reference_label,
                "line": {"color": REFERENCE_COLOR, "dash": "dash"},
            }
        )
    unit = ctx.item(items[0]).unit if items else ""
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

#: Labels of the colour fields in the map's switch (others: from the key).
MAP_FIELD_LABELS = {
    "modelling_tool.name": "Modelling tool",
    "modeller.institution": "Institution",
    "modeller.institution_country": "Country",
    "modelling_tool.licence": "Licence",
}


def field_label(path: str) -> str:
    """Short label of a metadata field in the colour switch.

    >>> field_label("modelling_tool.name"), field_label("model_details.pipe_model")
    ('Modelling tool', 'Pipe model')
    """
    known = MAP_FIELD_LABELS.get(path)
    return known or path.rpartition(".")[2].replace("_", " ").capitalize()


@visual("contributions_map")
def contributions_map(
    ctx: AnalysisContext,
    *,
    color_by: list[str] | None = None,
    height: int = 560,
) -> Choice:
    """Map of the submissions at their institution's city (see `destest.analysis.maps`).

    One map per colour field (`color_by`, metadata fields as `section.key`); the viewer
    switches between them. Values have the same colours as on the home page and in the
    timeline. A submission whose city and country are unknown is counted under the map.
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
    figures: dict[str, Figure | Timeline] = {}
    for f in fields:
        label = field_label(f)
        colors = category_colors(p.categories[f] for p in points)
        fig = category_map(points, [f], height=height, note=note, colors=colors)
        fig["layout"]["legend"]["title"]["text"] = label
        figures[label] = fig
    return Choice("Colour by", figures)


#: Labels of the timeline's colour options.
TIMELINE_LABELS = {
    "cme": "Exercise",
    "tool": "Modelling tool",
    "institution": "Institution",
    "country": "Country",
}


@visual("contributions_timeline")
def contributions_timeline(
    ctx: AnalysisContext, *, color_by: list[str] | None = None, min_months: int = 24
) -> Timeline | Choice:
    """Submissions of the CME per month (one square each), up to the current month.

    `color_by`: `tool`, `institution`, `country` or `cme`; with several, a switch picks
    one (default: tool, institution and country).
    """
    keys = list(color_by or ["tool", "institution", "country"])
    subs = {ctx.spec.folder_name: ctx.focus}
    versions: dict[str, Figure | Timeline] = {
        TIMELINE_LABELS.get(k, k): submission_timeline(subs, min_months=min_months, color_by=k)
        for k in keys
    }
    if len(versions) == 1:
        only = next(iter(versions.values()))
        assert isinstance(only, Timeline)
        return only
    return Choice("Colour by", versions)


@visual("contributions_pie")
def contributions_share(
    ctx: AnalysisContext, *, color_by: list[str] | None = None, height: int = 420
) -> Figure | Choice:
    """Share of the CME's submissions per modelling tool, institution or country (donut).

    `color_by`: `tool`, `institution`, `country` (or `cme`); with several, a switch
    picks one (default: tool, institution and country). Colours as on the map.
    """
    keys = list(color_by or ["tool", "institution", "country"])
    subs = {ctx.spec.folder_name: ctx.focus}
    versions: dict[str, Figure | Timeline] = {}
    for k in keys:
        fig = contributions_pie(subs, color_by=k, height=height)
        fig["layout"]["legend"]["title"]["text"] = TIMELINE_LABELS.get(k, k)
        versions[TIMELINE_LABELS.get(k, k)] = fig
    if len(versions) == 1:
        only = next(iter(versions.values()))
        assert isinstance(only, dict)
        return only
    return Choice("Colour by", versions)
