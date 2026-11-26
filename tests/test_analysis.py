"""Tests for destest.results and destest.analysis (KPIs, metrics, visuals, dashboards)."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from destest.analysis import (
    KPI_FUNCTIONS,
    VISUALS,
    Table,
    build_context,
    build_dashboard,
    render_html,
)
from destest.analysis.accuracy_metric import (
    SERIES_METRICS,
    VALUE_METRICS,
    closeness_grade,
    closeness_scores,
    reference_series,
)
from destest.analysis.colors import cme_colors, tool_colors
from destest.analysis.maps import contributions_pie, exercises_map
from destest.analysis.timeline import Timeline, submission_timeline
from destest.analysis.visuals import Choice, rank_color
from destest.cli import main
from destest.results import Submission, load_cme_submissions, load_submission
from destest.specs import (
    SpecError,
    cme_spec_path,
    load_cme_spec,
    load_cme_spec_file,
    load_locations_file,
)

RESULT_DATA = Path(__file__).resolve().parents[1] / "Result data"
CME_FOLDER = RESULT_DATA / "CME_DHN_1"
SPEC = load_cme_spec("DHN", 1)

needs_results = pytest.mark.skipif(not CME_FOLDER.is_dir(), reason="no Result data folder")


@pytest.fixture(scope="module")
def subs() -> list[Submission]:
    return load_cme_submissions(CME_FOLDER)


# ---- KPI functions and metrics ---------------------------------------------------------
@pytest.mark.parametrize(
    ("name", "values", "params", "expected"),
    [
        ("steady_state", [1.0, None, 3.0, 5.0], {}, 3.0),
        ("steady_state", [1.0, 3.0, 5.0], {"last_n": 2}, 4.0),
        ("mean", [2.0, 4.0], {}, 3.0),
        ("minimum", [2.0, None, -1.0], {}, -1.0),
        ("maximum", [2.0, 7.0], {}, 7.0),
        ("final_value", [2.0, 7.0, None], {}, 7.0),
        ("total", [1.0, 2.0], {"factor": 10.0}, 30.0),
        ("integral", [0.0, 2.0, 2.0], {}, 3.0),  # time 0, 1, 2
        ("mean", [None, None], {}, None),
    ],
)
def test_kpi_functions(
    name: str, values: list[float | None], params: dict[str, Any], expected: float | None
) -> None:
    time = [float(i) for i in range(len(values))]
    assert KPI_FUNCTIONS[name](values, time, **params) == expected


def test_value_metrics() -> None:
    assert VALUE_METRICS["relative_deviation"](110.0, 100.0) == pytest.approx(10.0)
    assert VALUE_METRICS["relative_deviation"](1.0, 0.0) is None
    assert VALUE_METRICS["absolute_deviation"](110.0, 100.0) == 10.0


def test_series_metrics() -> None:
    y, ref = [1.0, 3.0, None], [2.0, 2.0, 2.0]
    assert SERIES_METRICS["nmbe"](y, ref) == pytest.approx(0.0)
    assert SERIES_METRICS["cvrmse"](y, ref) == pytest.approx(50.0)
    assert SERIES_METRICS["rmse"](y, ref) == pytest.approx(1.0)
    assert SERIES_METRICS["mae"](y, ref) == pytest.approx(1.0)
    assert SERIES_METRICS["max_abs_error"](y, ref) == pytest.approx(1.0)


def test_reference_series_uses_the_most_common_length() -> None:
    ref = reference_series([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [9.0]], "median")
    assert ref == [3.0, 4.0]


# ---- loading submissions -------------------------------------------------------------------
@needs_results
def test_load_submissions(subs: list[Submission]) -> None:
    assert len(subs) == 7
    trnsys = next(s for s in subs if s.label.startswith("TRNSYS 2022"))
    assert trnsys.label == "TRNSYS 2022 - C. Felsmann (TUD)"
    assert trnsys.series["time"] == [float(t) for t in range(10)]
    assert trnsys.metadata["modeller"]["institution_city"] == "Dresden"


def test_load_submission_refuses_invalid_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Not a valid ResultData file name"):
        load_submission(tmp_path / "results.csv")
    folder = tmp_path / "CME_DHN_1"
    folder.mkdir()
    bad = folder / "ResultData_DESTEST_CME_DHN_1_T_1_I_A_B_2022_01_01_12_00_00.csv"
    bad.write_text("Elapsed time [s]\n0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="content errors"):
        load_submission(bad)
    assert load_submission(bad, require_valid=False).series["time"] == [0.0]


# ---- context: the numbers behind every dashboard ---------------------------------------------
@needs_results
def test_context_kpis_and_reference(subs: list[Submission]) -> None:
    ctx = build_context(SPEC, subs)
    assert len(ctx.reference) == 18
    assert ctx.reference["T_supply_i"] == pytest.approx(70.0, abs=0.01)
    laluce = next(s for s in subs if "Laluce" in s.label)
    assert ctx.kpi_values[laluce.id]["Q_supplied"] == pytest.approx(308203)
    vicus = next(s for s in subs if s.label.startswith("SIM VICUS"))
    assert ctx.metric("relative_deviation", vicus, "Q_loss_supply_i_h") == pytest.approx(
        31.6, abs=0.1
    )
    # steady state: deviation of the KPI value equals the NMBE of the time series
    assert ctx.metric("nmbe", vicus, "Q_loss_supply_i_h") == pytest.approx(
        ctx.metric("relative_deviation", vicus, "Q_loss_supply_i_h"), abs=0.01
    )
    assert len({ctx.colors[s.id] for s in subs}) == 7


# ---- visuals -----------------------------------------------------------------------------------
@needs_results
@pytest.mark.parametrize("name", sorted(VISUALS))
def test_every_visual_builds_and_is_json(subs: list[Submission], name: str) -> None:
    ctx = build_context(SPEC, subs)
    per_visual: dict[str, dict[str, Any]] = {
        "profile": {"kpis": ["T_supply_i", "T_supply_h"], "x_labels": ["i", "h"]},
        "time_series": {"columns": ["T_supply_i"], "show_reference": True},
        "carpet": {"column": "Q_supplied", "period": 5},
        "kpi_bar": {"kpis": ["Q_supplied"]},
    }
    options = per_visual.get(name, {})
    result = VISUALS[name].builder(ctx, **options)
    if isinstance(result, Table):
        assert result.rows
        assert all(len(r) == len(result.headers) for r in result.rows)
    elif isinstance(result, Choice):
        assert result.options
        for option in result.options.values():
            assert isinstance(option, Timeline) or (option["data"] and "layout" in option)
    elif isinstance(result, Timeline):
        assert result.months
        assert result.cells
    else:
        assert result["data"]
        assert "layout" in result
    json.dumps(result.to_dict() if isinstance(result, Table | Choice | Timeline) else result)


@needs_results
def test_kpi_table_marks_large_deviations(subs: list[Submission]) -> None:
    table = VISUALS["kpi_table"].builder(build_context(SPEC, subs), kpis=["Q_loss_supply_i_h"])
    assert isinstance(table, Table)
    assert table.headers[1] == "Weight"
    assert table.headers[2] == "Reference (median of 7)"
    assert table.rows[0][0] == "Closeness to the reference [0-100]"
    assert table.rows[0][1] == "18 (sum)"  # weights of all KPIs, also those not shown
    assert table.rows[1][1] == "1"
    assert "bad" in table.classes[1]  # SIM VICUS and TRNSYS 2021 are > 20 % off
    no_weights = VISUALS["kpi_table"].builder(build_context(SPEC, subs), weights=False)
    assert isinstance(no_weights, Table)
    assert no_weights.headers[1] == "Reference (median of 7)"


# ---- closeness to the reference ---------------------------------------------------------------
def test_closeness_scores_and_grade() -> None:
    scores = closeness_scores({"a": 1.0, "b": 3.0, "c": 2.0, "d": None}, 1.0)
    assert scores == {"a": 100.0, "b": 0.0, "c": 50.0, "d": None}
    assert closeness_scores({"a": 2.0, "b": 2.0}, 1.0) == {"a": 100.0, "b": 100.0}
    assert closeness_scores({"a": 2.0}, None) == {"a": None}
    assert closeness_grade([100.0, 0.0, None]) == 50.0
    assert closeness_grade([None]) is None
    assert closeness_grade([100.0, 0.0], [3.0, 1.0]) == 75.0
    assert closeness_grade([100.0, 0.0], [1.0, 0.0]) == 100.0  # weight 0: not counted
    with pytest.raises(ValueError, match="one weight per score"):
        closeness_grade([100.0], [1.0, 1.0])


@needs_results
def test_closeness_of_cme_dhn_1(subs: list[Submission]) -> None:
    ctx = build_context(SPEC, subs)
    grades = {s.label: ctx.closeness[s.id] for s in subs}
    assert all(g is not None and 0 <= g <= 100 for g in grades.values())
    worst = min(subs, key=lambda s: ctx.closeness[s.id] or 0.0)
    assert worst.label.startswith("SIM VICUS")
    assert ctx.closeness_rank(worst) == (7, 7)
    # the grade is the mean of the 18 KPI scores (all weights 1)
    assert SPEC.analysis is not None
    assert {k.weight for k in SPEC.analysis.kpis} == {1.0}
    scores = list(ctx.kpi_scores[worst.id].values())
    assert len(scores) == 18
    assert ctx.closeness[worst.id] == pytest.approx(sum(s or 0 for s in scores) / 18)


@needs_results
def test_kpi_weights_change_the_grade(subs: list[Submission]) -> None:
    assert SPEC.analysis is not None
    first = SPEC.analysis.kpis[0].key
    kpis = [
        k.model_copy(update={"weight": 1.0 if k.key == first else 0.0}) for k in SPEC.analysis.kpis
    ]
    analysis = SPEC.analysis.model_copy(update={"kpis": kpis})
    ctx = build_context(SPEC.model_copy(update={"analysis": analysis}), subs)
    for s in subs:  # only the first KPI counts
        assert ctx.closeness[s.id] == ctx.kpi_scores[s.id][first]


@needs_results
def test_submission_table_has_dates_issues_and_closeness(subs: list[Submission]) -> None:
    renamed = VISUALS["data_check_table"].builder(build_context(SPEC, subs), first_column="X")
    assert isinstance(renamed, Table)
    assert renamed.headers[0] == "X"
    table = VISUALS["data_check_table"].builder(build_context(SPEC, subs))
    assert isinstance(table, Table)
    assert table.headers == [
        "Submission",
        "Created",
        "Data file",
        "Metadata file",
        "Closeness to the reference [0-100]",
        "Errors",
        "Warnings",
    ]
    laluce = next(r for r in table.rows if "Laluce" in r[0])
    assert laluce[1] == "2022-01-01 12:00"
    assert "(rank" in laluce[4]
    assert laluce[5] == "-"
    assert "content/consistency: Heat supplied" in laluce[6]
    # one line per issue; a warning found in both files is shown once, marked with both
    lines = laluce[6].split("\n")
    assert "[data + metadata] name/tool_version: Modelling tool version 'Buildings'" in lines[0]
    assert any(line.startswith("[data] content/consistency: Heat supplied") for line in lines)
    assert table.full_width
    assert table.alignment(1) == "center"
    best = next(r for r in table.rows if "(rank 1 of" in r[4])
    assert table.color(table.rows.index(best), 4) == rank_color(1, 7) == "#8fd19e"


@needs_results
def test_closeness_bar_ranks_best_first(subs: list[Submission]) -> None:
    ctx = build_context(SPEC, subs)
    fig = VISUALS["closeness_bar"].builder(ctx, colors="rank")
    assert isinstance(fig, dict)
    bar = fig["data"][0]
    assert bar["y"] == sorted(bar["y"], reverse=True)
    assert bar["marker"]["color"][0] == rank_color(1, 7)
    assert bar["marker"]["color"][-1] == rank_color(7, 7)
    assert bar["x"][0].startswith("Modelica Buildings<br>M. Frandsen")


@needs_results
def test_closeness_bar_selected_keeps_the_overall_rank(subs: list[Submission]) -> None:
    ctx = build_context(SPEC, subs, [subs[0], subs[1]])
    fig = VISUALS["closeness_bar"].builder(ctx, colors="rank", submissions="selected")
    assert isinstance(fig, dict)
    bar = fig["data"][0]
    assert len(bar["x"]) == 2
    ranks = [int(r.split()[1]) for r in bar["customdata"]]
    assert ranks == sorted(ranks)
    assert all(r.endswith("of 7") for r in bar["customdata"])
    assert bar["marker"]["color"] == [rank_color(r, 7) for r in ranks]
    with pytest.raises(ValueError, match="submissions must be"):
        VISUALS["closeness_bar"].builder(ctx, submissions="some")


def test_rank_colors_go_from_green_to_pale_red() -> None:
    colors = [rank_color(r, 4) for r in range(1, 5)]
    assert colors[0] == "#8fd19e"
    assert colors[-1] == "#f7c6c5"
    assert len(set(colors)) == 4
    assert rank_color(1, 1) == "#8fd19e"


@needs_results
def test_bars_have_readable_labels_and_a_reference_legend(subs: list[Submission]) -> None:
    fig = VISUALS["kpi_bar"].builder(build_context(SPEC, subs), kpis=["Q_supplied"])
    assert isinstance(fig, dict)
    bars = [t for t in fig["data"] if t["type"] == "bar"]
    assert bars[0]["x"][0].count("<br>") == 2  # tool + version / modeller / institution
    ref = [t for t in fig["data"] if t["type"] == "scatter"]
    assert ref[0]["name"] == "Reference (median of 7) (dashed line)"
    assert ref[0]["line"]["dash"] == "dash"


@needs_results
def test_exercises_map_colours_by_cme(subs: list[Submission]) -> None:
    fig = exercises_map({"CME_DHN_1": subs, "CME_DHN_2": subs[:1]})
    assert [t["name"] for t in fig["data"]] == ["CME_DHN_1", "CME_DHN_2"]
    assert all(t["type"] == "scattermap" for t in fig["data"])
    assert "updatemenus" not in fig["layout"]  # one colour field only: no menu
    assert fig["layout"]["map"]["style"] == "carto-positron"
    one = exercises_map({"CME_DHN_1": subs})
    assert one["layout"]["showlegend"] is True  # legend shown even with a single exercise


@needs_results
def test_exercises_map_series_shades_and_tools(subs: list[Submission]) -> None:
    fig = exercises_map({"CME_DHN_2": subs[:1], "CME_DHN_1": subs, "CME_DCN_1": subs[:1]})
    colors = {t["name"]: t["marker"]["color"] for t in fig["data"]}
    assert list(colors) == ["CME_DCN_1", "CME_DHN_1", "CME_DHN_2"]  # series, then number
    assert colors == cme_colors(colors)
    by_tool = exercises_map({"CME_DHN_1": subs}, color_by="tool")
    names = [t["name"] for t in by_tool["data"]]
    assert {"Modelica", "TRNSYS"} <= set(names)
    assert by_tool["layout"]["legend"]["title"]["text"] == "Modelling tool"
    with pytest.raises(ValueError, match="color_by"):
        exercises_map({"CME_DHN_1": subs}, color_by="city")


@needs_results
def test_contributions_pie_counts_and_colours(subs: list[Submission]) -> None:
    pie = contributions_pie({"CME_DHN_1": subs, "CME_DHN_2": subs[:2]})["data"][0]
    assert pie["labels"] == ["CME_DHN_1", "CME_DHN_2"]
    assert pie["values"] == [7, 2]
    assert pie["marker"]["colors"] == list(cme_colors(["CME_DHN_1", "CME_DHN_2"]).values())
    by_tool = contributions_pie({"CME_DHN_1": subs}, color_by="tool")["data"][0]
    assert dict(zip(by_tool["labels"], by_tool["values"], strict=True))["Modelica"] == 3
    country = contributions_pie({"CME_DHN_1": subs}, color_by="country")
    assert country["layout"]["legend"]["title"]["text"] == "Country"


@needs_results
def test_contributions_pie_visual_of_one_cme(subs: list[Submission]) -> None:
    choice = VISUALS["contributions_pie"].builder(build_context(SPEC, subs))
    assert isinstance(choice, Choice)
    assert list(choice.options) == ["Modelling tool", "Institution", "Country"]  # no Exercise
    by_tool = choice.options["Modelling tool"]
    assert isinstance(by_tool, dict)
    assert sum(by_tool["data"][0]["values"]) == 7
    one = VISUALS["contributions_pie"].builder(build_context(SPEC, subs), color_by=["country"])
    assert isinstance(one, dict)  # a single option: a plain figure, no switch


def test_cme_colors_light_to_dark_per_series() -> None:
    c = cme_colors(["CME_DHN_3", "CME_DHN_1", "CME_DHN_2", "CME_XYZ_1"])
    lightness = [sum(int(c[n][i : i + 2], 16) for i in (1, 3, 5)) for n in sorted(c)[:3]]
    assert lightness == sorted(lightness, reverse=True)  # DHN_1 lightest, DHN_3 darkest
    assert list(c.values()).count(c["CME_XYZ_1"]) == 1  # unknown series: its own colour


@needs_results
def test_submission_timeline_months_up_to_today(subs: list[Submission]) -> None:
    tl = submission_timeline({"CME_DHN_1": subs}, today=date(2026, 11, 24))
    first, last = tl.months[0], tl.months[-1]
    assert (first.year, first.month) == (2021, 1)  # oldest submission (TRNSYS 2021)
    assert (last.year, last.month) == (2026, 11)  # the current month is the last column
    assert len(tl.months) == 6 * 12 - 1
    jan_2022 = next(m for m in tl.months if (m.year, m.month) == (2022, 1))
    assert len(jan_2022.cells) == 5
    assert tl.height == 5
    assert sum(len(m.cells) for m in tl.months) == len(subs)
    empty = submission_timeline({}, today=date(2026, 11, 24))
    assert len(empty.months) == 24
    assert empty.height == 0


@needs_results
def test_metadata_table_all_sections(subs: list[Submission]) -> None:
    table = VISUALS["metadata_table"].builder(build_context(SPEC, subs, [subs[0]]), sections="all")
    assert isinstance(table, Table)
    fields = [r[0] for r in table.rows]
    assert "submission_info.result_data_file" in fields
    assert "modeller.institution_city" in fields
    assert "deviations" in fields
    assert "metadata_format_version" not in fields


@needs_results
def test_contributions_map(subs: list[Submission]) -> None:
    choice = VISUALS["contributions_map"].builder(
        build_context(SPEC, subs), color_by=["modelling_tool.name", "modeller.institution"]
    )
    assert isinstance(choice, Choice)
    assert choice.label == "Colour by"
    assert list(choice.options) == ["Modelling tool", "Institution"]  # one map per field
    fig = choice.options["Modelling tool"]
    assert isinstance(fig, dict)
    assert sum(len(t["lat"]) for t in fig["data"]) == 7  # every submission placed once
    assert {t["name"] for t in fig["data"]} == {"CitySim", "Modelica", "SIM VICUS", "TRNSYS"}
    assert "updatemenus" not in fig["layout"]  # the switch is outside the figure
    assert fig["layout"]["legend"]["title"]["text"] == "Modelling tool"
    tools = tool_colors(["CitySim", "Modelica", "SIM VICUS", "TRNSYS"])
    assert {t["name"]: t["marker"]["color"] for t in fig["data"]} == tools  # as on home page
    # markers sharing a city (3 x TUD in Dresden) are spread apart
    by_institution = choice.options["Institution"]
    assert isinstance(by_institution, dict)
    tud = next(t for t in by_institution["data"] if t["name"] == "TUD")
    assert len(set(zip(tud["lat"], tud["lon"], strict=True))) == 3


@needs_results
def test_contributions_timeline(subs: list[Submission]) -> None:
    ctx = build_context(SPEC, subs)
    tl = VISUALS["contributions_timeline"].builder(ctx, color_by=["tool"])
    assert isinstance(tl, Timeline)  # a single option: no switch
    assert tl.color_by == "tool"
    assert len(tl.cells) == 7
    assert tl.months[-1].year == date.today().year  # ends at the current month
    assert set(tl.colors()) == {"CitySim", "Modelica", "SIM VICUS", "TRNSYS"}
    choice = VISUALS["contributions_timeline"].builder(ctx)  # default: tool, institution, country
    assert isinstance(choice, Choice)
    assert list(choice.options) == ["Modelling tool", "Institution", "Country"]
    by_institution = choice.options["Institution"]
    assert isinstance(by_institution, Timeline)
    assert set(by_institution.colors()) == {"AAU", "Idiap", "TUD"}
    # same colours as the map, for the same values
    map_choice = VISUALS["contributions_map"].builder(ctx, color_by=["modeller.institution"])
    assert isinstance(map_choice, Choice)
    map_fig = map_choice.options["Institution"]
    assert isinstance(map_fig, dict)
    assert {t["name"]: t["marker"]["color"] for t in map_fig["data"]} == by_institution.colors()
    overview = build_dashboard(SPEC, subs, "overview")
    panel = next(p for p in overview.panels if p.visual == "contributions_timeline")
    assert panel.choice is not None
    assert panel.figure is None
    page = render_html(overview)
    assert 'class="tl-scroll"' in page
    assert "Colour by: Modelling tool" in page
    json.dumps(overview.to_dict())


def test_locations_file_is_checked(tmp_path: Path) -> None:
    p = tmp_path / "l.yaml"
    p.write_text("schema_version: 1\ncities:\n  Dresden:\n    lat: 51\n    lon: 13\n")
    with pytest.raises(SpecError, match="City, Country"):
        load_locations_file(p)
    p.write_text("schema_version: 1\ncountries:\n  X:\n    lat: 91\n    lon: 0\n")
    with pytest.raises(SpecError, match="lat"):
        load_locations_file(p)


def test_carpet_cuts_the_series_into_periods() -> None:
    sub = Submission(
        path=Path("x.csv"),
        cme="CME_DHN_1",
        name_parts={},
        series={"Q_supplied": [float(i) for i in range(48)], "time": [float(i) for i in range(48)]},
    )
    fig = VISUALS["carpet"].builder(build_context(SPEC, [sub]), column="Q_supplied", period=24)
    assert isinstance(fig, dict)
    z = fig["data"][0]["z"]
    assert len(z) == 2
    assert z[1][0] == 24.0


# ---- dashboards ----------------------------------------------------------------------------------
@needs_results
def test_dashboards_of_cme_dhn_1(subs: list[Submission]) -> None:
    assert SPEC.analysis is not None
    overview = build_dashboard(SPEC, subs, "overview")
    assert len(overview.panels) == len(SPEC.analysis.dashboards.overview)
    assert len(overview.submissions) == 7
    detail = build_dashboard(SPEC, subs, "detail", [subs[0]])
    assert detail.submissions == [subs[0].label]
    assert detail.title.endswith(subs[0].label)
    comparison = build_dashboard(SPEC, subs, "comparison", subs[:2])
    page = render_html(comparison)
    assert page.startswith("<!DOCTYPE html>")
    assert "Plotly.newPlot" in page
    assert "Reference: Median of all valid submissions (currently 7)" in page
    json.dumps(comparison.to_dict())


@needs_results
def test_dashboard_needs_the_right_selection(subs: list[Submission]) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        build_dashboard(SPEC, subs, "detail", subs[:2])
    with pytest.raises(ValueError, match="at least one"):
        build_dashboard(SPEC, subs, "comparison", [])
    with pytest.raises(ValueError, match="kind must be"):
        build_dashboard(SPEC, subs, "summary")


@needs_results
def test_cli_dashboard(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "o.html"
    assert main(["dashboard", "CME_DHN_1", "--folder", str(CME_FOLDER), "-o", str(out)]) == 0
    assert "<table>" in out.read_text(encoding="utf-8")
    js = tmp_path / "d.json"
    args = ["dashboard", "CME_DHN_1", "--folder", str(CME_FOLDER), "--kind", "detail"]
    assert main([*args, "--submission", "Laluce", "-o", str(js)]) == 0
    assert json.loads(js.read_text(encoding="utf-8"))["kind"] == "detail"
    assert main([*args, "--submission", "Modelica"]) == 2  # matches 3
    assert "matches 3" in capsys.readouterr().err


# ---- the analysis section of a spec file is checked on load ----------------------------------------
def panel(analysis: dict[str, Any], dashboard: str, visual: str) -> dict[str, Any]:
    """The first panel of a dashboard with this visual (by name, so adding panels is safe)."""
    return next(p for p in analysis["dashboards"][dashboard] if p["visual"] == visual)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda a: a["kpis"][0].update(function="median"), "unknown 'median'"),
        (lambda a: a["kpis"][0].update(params={"last": 2}), "has no parameter last"),
        (lambda a: a["kpis"][0].update(column="T_x"), "'T_x' is not a column"),
        (lambda a: a["kpis"].append(dict(a["kpis"][0])), "key used more than once"),
        (lambda a: a["kpis"][0].update(weight=-1), "greater than or equal to 0"),
        (lambda a: [k.update(weight=0) for k in a["kpis"]], "weight above 0"),
        (
            lambda a: panel(a, "overview", "contributions_map").update(visual="pie"),
            "unknown 'pie'",
        ),
        (
            lambda a: panel(a, "overview", "contributions_map")["options"].update(colour="red"),
            "has no option colour",
        ),
        (
            lambda a: panel(a, "overview", "deviation_heatmap")["options"].update(kpis=["Q_los"]),
            "not a KPI key: Q_los",
        ),
        (
            lambda a: panel(a, "detail", "time_series")["options"].update(columns=["T_x"]),
            "not a column key: T_x",
        ),
    ],
)
def test_analysis_section_is_checked(tmp_path: Path, change: Any, expected: str) -> None:
    data: dict[str, Any] = yaml.safe_load(cme_spec_path("DHN", 1).read_text(encoding="utf-8"))
    change(data["analysis"])
    p = tmp_path / "CME_DHN_1.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(SpecError, match=expected):
        load_cme_spec_file(p)
