"""Tests for the web app (destest.webapp). The page tests need Dash (dependency group `web`)."""

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from destest.webapp import data

RESULT_DATA = Path(__file__).resolve().parents[1] / "Result data"
needs_results = pytest.mark.skipif(not RESULT_DATA.is_dir(), reason="no Result data folder")


@pytest.fixture
def results(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("DESTEST_RESULTS", str(RESULT_DATA))
    data._cache.clear()
    yield RESULT_DATA
    data._cache.clear()


# ---- data layer (no Dash needed) ----------------------------------------------------------------
@needs_results
def test_cmes_and_submissions(results: Path) -> None:
    assert "CME_DHN_1" in data.cme_names()
    cme = data.get_cme("CME_DHN_1")
    assert len(cme.submissions) == 7
    assert cme.skipped == []
    options = data.submission_options("CME_DHN_1")
    assert options[0]["label"] == cme.submissions[0].label
    assert cme.by_id([options[1]["value"], "nope"]) == [cme.submissions[1]]


@needs_results
def test_dashboards(results: Path) -> None:
    ids = [o["value"] for o in data.submission_options("CME_DHN_1")]
    assert data.dashboard("CME_DHN_1", "overview").panels
    assert data.dashboard("CME_DHN_1", "detail", ids[:1]).submissions == [
        data.get_cme("CME_DHN_1").submissions[0].label
    ]
    with pytest.raises(ValueError, match="exactly one"):
        data.dashboard("CME_DHN_1", "detail", ids[:2])


def test_invalid_files_are_skipped_and_cache_follows_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "CME_DHN_1"
    folder.mkdir()
    monkeypatch.setenv("DESTEST_RESULTS", str(tmp_path))
    data._cache.clear()
    assert data.get_cme("CME_DHN_1").submissions == []
    bad = folder / "ResultData_DESTEST_CME_DHN_1_T_1_I_A_B_2022_01_01_12_00_00.csv"
    bad.write_text("Time [s]\n0\n", encoding="utf-8")
    skipped = data.get_cme("CME_DHN_1").skipped
    assert [name for name, _ in skipped] == [bad.name]
    if RESULT_DATA.is_dir():  # a valid pair appears after a change in the folder
        good = sorted((RESULT_DATA / "CME_DHN_1").glob("*TRNSYS_2022*"))
        for f in good:
            shutil.copy(f, folder / f.name)
        assert len(data.get_cme("CME_DHN_1").submissions) == 1
    data._cache.clear()


# ---- pages (need Dash) ------------------------------------------------------------------------------
@pytest.fixture
def app(results: Path) -> Any:
    pytest.importorskip("dash")
    from destest.webapp import app as app_module

    return app_module.app


@needs_results
def test_app_has_all_pages(app: Any) -> None:
    import dash

    paths = {p["path"] for p in dash.page_registry.values()}
    assert {"/", "/overview", "/detail", "/comparison", "/contribute", "/about"} <= paths


@needs_results
def test_page_layouts_render(app: Any) -> None:
    from destest.webapp.pages import about, comparison, contribute, detail, home, overview

    for page in (home, overview, detail, comparison, contribute, about):
        assert page.layout() is not None
    assert overview.layout(cme="CME_DHN_1") is not None


@needs_results
def test_callbacks_build_the_dashboards(app: Any) -> None:
    from destest.webapp.pages import comparison, detail, overview

    panels = overview._overview("CME_DHN_1")
    assert len(panels) > 3
    options, value = detail._submissions("CME_DHN_1", None)
    assert value == options[0]["value"]
    assert len(detail._detail("CME_DHN_1", value)) > 3
    options, selected = comparison._submissions("CME_DHN_1", None)
    assert len(selected) == comparison.DEFAULT_SELECTION
    assert len(comparison._comparison("CME_DHN_1", selected)) > 3
    assert "Choose" in str(comparison._comparison("CME_DHN_1", []))


@needs_results
def test_cme_info_card_comes_first(app: Any) -> None:
    from destest.webapp.pages import comparison, detail, overview

    for content in (
        overview._overview("CME_DHN_1"),
        detail._detail("CME_DHN_1", None),
        comparison._comparison("CME_DHN_1", []),
    ):
        text = str(content[0])
        assert "Steady-state simulation of a district heating network" in text
        assert "Median of all valid submissions" in text
        assert "Heat source" in text


@needs_results
def test_comments_card_ends_the_overview(app: Any) -> None:
    from destest.webapp.pages import overview

    last = str(overview._overview("CME_DHN_1")[-1])
    assert "Comments and observations" in last
    assert "Comment 1" in last


def test_render_table() -> None:
    pytest.importorskip("dash")
    from destest.analysis import Table
    from destest.webapp.components import render_table

    out = render_table(Table(["a", "b"], [["x", "1\n2"]], [["", "bad"]], note="n"))
    text = str(out)
    assert "data-table" in text
    assert "bad" in text
