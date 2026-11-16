"""Tests for destest.specs: the YAML spec files and their checks. Run with:  uv run pytest"""

import csv
from pathlib import Path
from typing import Any

import pytest
import yaml

from destest.cli import main
from destest.specs import (
    SpecError,
    cme_spec_path,
    list_cme_specs,
    load_cme_spec,
    load_cme_spec_file,
    load_naming_convention,
    load_naming_convention_file,
    load_result_metadata_layout,
    load_result_metadata_layout_file,
    naming_convention_path,
    result_metadata_layout_path,
)

RESULT_DATA = Path(__file__).resolve().parents[1] / "Result data"


# ---- the packaged files ----------------------------------------------------
def test_naming_convention_loads() -> None:
    conv = load_naming_convention()
    assert [f.key for f in conv.fields] == [
        "data_type",
        "marker",
        "series",
        "exercise_number",
        "tool",
        "tool_version",
        "institution",
        "first_name",
        "last_name",
        "creation_date_time",
    ]
    assert set(conv.series) == {"DHN", "DCN", "DEL"}
    assert conv.data_types["ResultMetadata"].extensions == [".yaml"]
    assert conv.folder.keys == ["series", "exercise_number"]


def test_every_cme_spec_loads() -> None:
    names = list_cme_specs()
    assert "CME_DHN_1" in names
    for name in names:
        _, series, number = name.split("_")
        spec = load_cme_spec(series, int(number))
        assert spec.folder_name == name


def test_cme_dhn_1_content() -> None:
    spec = load_cme_spec("DHN", 1)
    cols = spec.result_data.columns
    assert len(cols) == 19
    assert cols[0].header == "Time [s]"
    assert spec.result_data.time is not None
    assert spec.result_data.time.column == "time"
    assert spec.result_data.rows.max == 10
    assert spec.cme.full_title == "Steady-state simulation of a district heating network"
    assert spec.result_metadata.model_details[0].key == "pipe_model"


def test_result_metadata_layout_loads() -> None:
    layout = load_result_metadata_layout()
    assert [s.name for s in layout.sections] == [
        "submission_info",
        "modeller",
        "modelling_tool",
        "simulation_config",
        "model_details",
        "deviations",
        "other_comments",
    ]
    modeller = next(s for s in layout.sections if s.name == "modeller")
    assert "institution_city" in [f.key for f in modeller.fields]


def _result_files() -> list[Path]:
    return sorted(RESULT_DATA.glob("CME_*/ResultData_*.csv")) if RESULT_DATA.is_dir() else []


@pytest.mark.parametrize("path", _result_files(), ids=lambda p: p.name)
def test_result_files_have_the_header_of_their_spec(path: Path) -> None:
    _, series, number = path.parent.name.split("_")
    spec = load_cme_spec(series, int(number))
    with path.open(encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))
    assert header == [c.header for c in spec.result_data.columns]


# ---- broken files give clear messages ----------------------------------------
def _write(tmp_path: Path, name: str, data: Any) -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p


def _naming() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(naming_convention_path().read_text(encoding="utf-8"))
    return data


def _cme() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(cme_spec_path("DHN", 1).read_text(encoding="utf-8"))
    return data


def test_naming_typo_in_key_is_reported_with_its_place(tmp_path: Path) -> None:
    data = _naming()
    data["fields"][5]["warn_if_no_digt"] = True  # typo
    with pytest.raises(SpecError) as info:
        load_naming_convention_file(_write(tmp_path, "n.yaml", data))
    msg = str(info.value)
    assert "n.yaml: 1 problem(s)" in msg
    assert "fields[5].warn_if_no_digt" in msg


def test_naming_unknown_kind(tmp_path: Path) -> None:
    data = _naming()
    data["fields"][4]["kind"] = "txt"
    with pytest.raises(SpecError, match=r"fields\[4\]"):
        load_naming_convention_file(_write(tmp_path, "n.yaml", data))


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d["fields"][-1].update(format="%Y_%m_%d_%H_%M_%Q"), "use each of"),
        (lambda d: d["folder"].update(pattern="CME_{series}_{number}"), "unknown field"),
        (lambda d: d["series"].update({"D_X": "x"}), "must not be empty or contain"),
        (lambda d: d["data_types"]["ResultData"].update(extensions=["csv"]), "with a dot"),
        (lambda d: d["pairing"]["pairs"][0].update(metadata="Meta"), "not in data_types"),
        (lambda d: d["fields"].append(dict(d["fields"][4])), "used more than once"),
    ],
)
def test_naming_rules_are_checked(tmp_path: Path, change: Any, expected: str) -> None:
    data = _naming()
    change(data)
    with pytest.raises(SpecError, match=expected):
        load_naming_convention_file(_write(tmp_path, "n.yaml", data))


def test_not_yaml(tmp_path: Path) -> None:
    p = tmp_path / "n.yaml"
    p.write_text("fields: [unclosed", encoding="utf-8")
    with pytest.raises(SpecError, match="not valid YAML"):
        load_naming_convention_file(p)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="not found"):
        load_naming_convention_file(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d["cme"].update(series="XYZ"), "not in the naming convention"),
        (lambda d: d["cme"].update(exercise_number=2), "should be CME_DHN_2.yaml"),
        (lambda d: d["result_data"]["time"].update(column="t"), "not a column key"),
        (lambda d: d["result_data"]["rows"].update(min=20), "min <= expected <= max"),
        (lambda d: d["result_data"]["columns"][1]["range"].update(max=-1), "larger than max"),
        (
            lambda d: d["result_metadata"]["model_details"][0].update(requird=True),
            r"result_metadata\.model_details\[0\]\.requird",
        ),
        (
            lambda d: d["result_metadata"]["simulation_config"].append({"key": "solver"}),
            "used more than once: solver",
        ),
        (
            lambda d: d["result_metadata"]["model_details"][0].update(must_match="tol"),
            "'tol' is not a field of the naming convention",
        ),
        (lambda d: d["cme"].pop("full_title"), r"cme\.full_title: Field required"),
    ],
)
def test_cme_rules_are_checked(tmp_path: Path, change: Any, expected: str) -> None:
    data = _cme()
    change(data)
    with pytest.raises(SpecError, match=expected):
        load_cme_spec_file(_write(tmp_path, "CME_DHN_1.yaml", data))


def _layout() -> dict[str, Any]:
    text = result_metadata_layout_path().read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    return data


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d["sections"][3].update(kind="fields"), "needed for, and only for"),
        (lambda d: d["sections"].pop(4), "per_cme' sections must be"),
        (lambda d: d["sections"].append(dict(d["sections"][0])), "name used more than once"),
        (lambda d: d["sections"][1]["fields"][0].update(must_match="nme"), "'nme' is not a field"),
        (lambda d: d["sections"][0].update(kind="list"), r"sections\[0\]\.kind"),
    ],
)
def test_layout_rules_are_checked(tmp_path: Path, change: Any, expected: str) -> None:
    data = _layout()
    change(data)
    with pytest.raises(SpecError, match=expected):
        load_result_metadata_layout_file(_write(tmp_path, "m.yaml", data))


# ---- command line ------------------------------------------------------------
def test_cli_specs(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["specs"]) == 0
    out = capsys.readouterr().out
    assert "CME_DHN_1: OK" in out
    assert "ResultMetadata layout:" in out
