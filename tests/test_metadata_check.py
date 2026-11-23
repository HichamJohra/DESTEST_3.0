"""Tests for destest.metadata_check. Run with:  uv run pytest"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from destest.cli import main
from destest.metadata_check import (
    check_metadata,
    check_metadata_folder,
    make_template,
    template_for_data_file,
)

DATA = "ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv"
META = DATA.replace("ResultData", "ResultMetadata").replace(".csv", ".yaml")

#: Values for the required keys the file name cannot provide.
FILL = {
    ("modeller", "institution_full_name"): "Technische Universitaet Dresden",
    ("modeller", "institution_city"): "Dresden",
    ("modeller", "institution_country"): "Germany",
    ("modelling_tool", "licence"): "commercial",
    ("simulation_config", "time_step_s"): "1",
}


def _filled() -> dict[str, Any]:
    """A complete, valid metadata file for DATA, as loaded YAML."""
    _, text = template_for_data_file(DATA)
    data: dict[str, Any] = yaml.safe_load(text)
    for (section, key), value in FILL.items():
        data[section][key] = value
    data["deviations"] = "none"
    return data


def _write(tmp_path: Path, data: Any, name: str = META) -> Path:
    folder = tmp_path / "CME_DHN_1"
    folder.mkdir(exist_ok=True)
    p = folder / name
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


def _issues(tmp_path: Path, data: Any, name: str = META) -> list[tuple[str, str]]:
    return [(i.field, i.message) for i in check_metadata(_write(tmp_path, data, name)).errors]


# ---- template ----------------------------------------------------------------
def test_template_has_every_section_in_order() -> None:
    data = yaml.safe_load(make_template("DHN", 1))
    assert list(data) == [
        "metadata_format_version",
        "submission_info",
        "modeller",
        "modelling_tool",
        "simulation_config",
        "model_details",
        "deviations",
        "other_comments",
    ]
    assert data["submission_info"]["cme"] == "CME_DHN_1"
    assert "steady_state_approach" in data["model_details"]


def test_template_for_data_file_is_prefilled() -> None:
    name, text = template_for_data_file(DATA)
    assert name == META
    data = yaml.safe_load(text)
    assert data["submission_info"]["result_data_file"] == DATA
    assert data["modeller"]["last_name"] == "Felsmann"
    assert data["modelling_tool"]["version"] == "2022"  # quoted: stays text


def test_template_for_data_file_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="Not a valid file name"):
        template_for_data_file("bad_name.csv")
    with pytest.raises(ValueError, match="not the ResultMetadata"):
        template_for_data_file(META)


# ---- valid file ----------------------------------------------------------------
def test_filled_template_is_valid(tmp_path: Path) -> None:
    assert _issues(tmp_path, _filled()) == []


def test_prefilled_template_reports_only_the_empty_required_values(tmp_path: Path) -> None:
    _, text = template_for_data_file(DATA)
    found = _issues(tmp_path, yaml.safe_load(text))
    assert {f for f, _ in found} == {
        "modeller.institution_full_name",
        "modeller.institution_city",
        "modeller.institution_country",
        "modelling_tool.licence",
        "simulation_config.time_step_s",
        "deviations",
    }


def test_date_written_as_text_is_accepted(tmp_path: Path) -> None:
    data = _filled()
    data["submission_info"]["creation_date_time"] = "2022-01-01 12:00:00"
    assert _issues(tmp_path, data) == []


# ---- keys ------------------------------------------------------------------------
def test_missing_key(tmp_path: Path) -> None:
    data = _filled()
    del data["modeller"]["orcid"]  # optional value, but the key must be there
    assert _issues(tmp_path, data) == [("modeller.orcid", "Key 'orcid' is missing in 'modeller'.")]


def test_unknown_key(tmp_path: Path) -> None:
    data = _filled()
    data["model_details"]["pipe_modle"] = "plug-flow"
    assert _issues(tmp_path, data) == [
        ("model_details.pipe_modle", "Unknown key 'pipe_modle' in 'model_details'.")
    ]


def test_missing_and_unknown_section(tmp_path: Path) -> None:
    data = _filled()
    del data["other_comments"]
    data["notes"] = "x"
    assert _issues(tmp_path, data) == [
        ("other_comments", "Section 'other_comments' is missing."),
        ("notes", "Unknown section or key 'notes'."),
    ]


def test_list_instead_of_text(tmp_path: Path) -> None:
    data = _filled()
    data["modelling_tool"]["libraries"] = ["a", "b"]
    data["deviations"] = ["none"]
    assert [f for f, _ in _issues(tmp_path, data)] == ["modelling_tool.libraries", "deviations"]


def test_section_not_a_group(tmp_path: Path) -> None:
    data = _filled()
    data["model_details"] = "plug-flow"
    ((field, msg),) = _issues(tmp_path, data)
    assert field == "model_details"
    assert msg.startswith("'model_details' must be a group of keys: pipe_model,")


def test_format_version(tmp_path: Path) -> None:
    data = _filled()
    data["metadata_format_version"] = 0
    assert [f for f, _ in _issues(tmp_path, data)] == ["metadata_format_version"]


# ---- agreement with the file name ------------------------------------------------
@pytest.mark.parametrize(
    ("section", "key", "value", "expected"),
    [
        ("modeller", "first_name", "Clement", "does not match the file name ('Clemens')"),
        ("modelling_tool", "version", 2023, "Write the value in quotes"),
        ("submission_info", "cme", "CME_DHN_2", "does not match the CME (folder)"),
        ("submission_info", "result_data_file", "x.csv", "does not match the ResultData file"),
        ("submission_info", "creation_date_time", "2022-01-02 12:00:00", "2022-01-01 12:00:00"),
    ],
)
def test_must_match(tmp_path: Path, section: str, key: str, value: Any, expected: str) -> None:
    data = _filled()
    data[section][key] = value
    ((field, msg),) = _issues(tmp_path, data)
    assert field == f"{section}.{key}"
    assert expected in msg


def test_unquoted_number_that_matches_is_fine(tmp_path: Path) -> None:
    data = _filled()
    data["modelling_tool"]["version"] = 2022  # YAML reads 2022 as a number
    assert _issues(tmp_path, data) == []


# ---- the file itself -------------------------------------------------------------
def test_not_yaml(tmp_path: Path) -> None:
    p = _write(tmp_path, {})
    p.write_text("modeller: [unclosed", encoding="utf-8")
    assert [i.field for i in check_metadata(p).errors] == ["file"]


def test_empty_file(tmp_path: Path) -> None:
    p = _write(tmp_path, {})
    p.write_text("", encoding="utf-8")
    ((field, msg),) = [(i.field, i.message) for i in check_metadata(p).errors]
    assert field == "file"
    assert "empty" in msg


def test_bad_file_name(tmp_path: Path) -> None:
    ((field, _),) = _issues(tmp_path, _filled(), name="metadata.yaml")
    assert field == "file name"


def test_data_file_is_not_checked_as_metadata(tmp_path: Path) -> None:
    assert _issues(tmp_path, _filled(), name=DATA) == [("file name", "Not a ResultMetadata file.")]


def test_cme_without_spec(tmp_path: Path) -> None:
    name = META.replace("_DHN_1_", "_DHN_7_")
    folder = tmp_path / "CME_DHN_7"
    folder.mkdir()
    p = folder / name
    p.write_text("x: 1", encoding="utf-8")
    ((field, msg),) = [(i.field, i.message) for i in check_metadata(p).errors]
    assert field == "spec"
    assert "CME_DHN_7" in msg


# ---- folders and command line ------------------------------------------------------
def test_check_metadata_folder(tmp_path: Path) -> None:
    _write(tmp_path, _filled())
    (tmp_path / "CME_DHN_1" / DATA).write_text("x", encoding="utf-8")  # not a metadata file
    checks = check_metadata_folder(tmp_path)
    assert [c.name for c in checks] == [META]
    assert checks[0].ok


def test_cli_metadata_template_and_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "CME_DHN_1"
    folder.mkdir()
    data_file = folder / DATA
    data_file.write_text("x", encoding="utf-8")

    assert main(["metadata-template", "CME_DHN_1"]) == 0
    assert "model_details:" in capsys.readouterr().out

    assert main(["metadata-template", str(data_file), "-o", str(folder)]) == 0
    written = folder / META
    assert written.is_file()
    assert main(["metadata-template", str(data_file), "-o", str(folder)]) == 1  # no overwrite
    capsys.readouterr()

    assert main(["check-metadata", str(tmp_path)]) == 1  # required values still empty
    assert "1 with errors" in capsys.readouterr().out

    _write(tmp_path, _filled())
    assert main(["check-metadata", str(written)]) == 0
