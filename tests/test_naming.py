"""Tests for destest.naming. Run with:  uv run pytest"""

from datetime import datetime
from pathlib import Path

import pytest

from destest.cli import main
from destest.naming import (
    check_files,
    check_folder,
    check_name,
    describe,
    make_filename,
    template,
    write_csv,
)

NOW = datetime(2026, 10, 24, 12, 0, 0)
VALID = "ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv"

# The result files in "Result data/CME_DHN_1" (renamed October 2026).
REPO_FILES = [
    "ResultData_DESTEST_CME_DHN_1_Modelica_Buildings_AAU_Alessandro_Maccarini_2022_01_01_12_00_00.csv",
    "ResultData_DESTEST_CME_DHN_1_Modelica_Buildings_AAU_Jerome_Laluce_2022_01_01_12_00_00.csv",
    "ResultData_DESTEST_CME_DHN_1_Modelica_Buildings_AAU_Martin_Frandsen_2022_01_01_12_00_00.csv",
    "ResultData_DESTEST_CME_DHN_1_SIM VICUS_-_TUD_Hauke_Hirsch_2022_01_01_12_00_00.csv",
    "ResultData_DESTEST_CME_DHN_1_TRNSYS_2021_TUD_Clemens_Felsmann_2021_01_01_12_00_00.csv",
    "ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv",
]


def errors(name: str) -> list[str]:
    return [i.message for i in check_name(name, now=NOW).errors]


def warnings(name: str) -> list[str]:
    return [i.message for i in check_name(name, now=NOW).warnings]


def error_fields(name: str) -> set[str]:
    return {i.field for i in check_name(name, now=NOW).errors}


# ---- valid names -----------------------------------------------------------
def test_valid_name_is_parsed() -> None:
    r = check_name(VALID, now=NOW)
    assert r.ok
    assert not r.warnings
    assert r.values["data_type"] == "ResultData"
    assert r.values["series"] == "DHN"
    assert r.values["number"] == 1
    assert r.values["tool"] == "TRNSYS"
    assert r.values["tool_version"] == "2022"
    assert r.values["institution"] == "TUD"
    assert r.values["last_name"] == "Felsmann"
    assert r.values["created"] == datetime(2022, 1, 1, 12, 0, 0)
    assert r.extension == ".csv"


@pytest.mark.parametrize("name", REPO_FILES)
def test_files_in_repo_are_valid(name: str) -> None:
    assert errors(name) == []


def test_files_in_repo_get_the_expected_warnings() -> None:
    # 'Modelica_Buildings' is read as tool 'Modelica', version 'Buildings'
    assert any("contains no digit" in w for w in warnings(REPO_FILES[0]))
    # 'SIM VICUS' has a space, and the version is '-'
    w = warnings(REPO_FILES[3])
    assert any("spaces" in x for x in w)
    assert any("'-' contains no digit" in x for x in w)


@pytest.mark.parametrize(
    "name",
    [
        "ResultMetadata_DESTEST_CME_DEL_0_PowerFactory_2024-SP1_SINTEF_Ola_Nordmann_2026_01_31_23_59_59.json",
        "ResultData_DESTEST_CME_DHN_12_Modelica-Buildings_11.0.0_AAU_Jean-Luc_Dupont_2025_02_28_00_00_00.csv",
        "ResultData_DESTEST_CME_DHN_3_SIM-VICUS_1.1_TUD_Bjørn_Ødegård_2024_02_29_08_30_00.csv",
    ],
)
def test_other_valid_names(name: str) -> None:
    assert errors(name) == []
    assert warnings(name) == []


def test_path_is_reduced_to_file_name() -> None:
    assert check_name("C:\\data\\Result data\\CME_DHN_1\\" + VALID, now=NOW).ok
    assert check_name("Result data/CME_DHN_1/" + VALID, now=NOW).ok


def test_make_filename_round_trip() -> None:
    name = make_filename(
        series="DHN",
        number=1,
        data_type="ResultData",
        tool="TRNSYS",
        tool_version="2022",
        institution="TUD",
        first_name="Clemens",
        last_name="Felsmann",
        created=datetime(2022, 1, 1, 12, 0, 0),
    )
    assert name == VALID


def _make(series: str = "DHN", tool: str = "TRNSYS") -> str:
    return make_filename(
        series=series,
        number=1,
        data_type="ResultData",
        tool=tool,
        tool_version="1",
        institution="I",
        first_name="A",
        last_name="B",
    )


def test_make_filename_rejects_bad_parts() -> None:
    with pytest.raises(ValueError, match="'_'"):
        _make(tool="Modelica_Buildings")
    with pytest.raises(ValueError, match="series"):
        _make(series="XYZ")


def test_template_and_description() -> None:
    assert template().startswith("<DataType>_DESTEST_CME_<Series>_<Number>_<ModellingTool>")
    assert "District Heating Network" in describe()


# ---- data type position and fixed markers ------------------------------------
def test_old_style_name_fails_once() -> None:
    errs = errors("Modelica_Buildings_AAU_Alessandro_Network_0.csv")
    assert len(errs) == 1
    assert "Name must start with '<DataType>_DESTEST_CME_<Series>_<Number>_'" in errs[0]


@pytest.mark.parametrize(
    "name",
    [
        # earlier order of the files in the repository
        "DESTEST_ResultData_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv",
        # order of the template in the original text file
        "DESTEST_CME_DHN_1_ResultData_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv",
    ],
)
def test_data_type_in_wrong_place_is_reported_once(name: str) -> None:
    assert errors(name) == [
        "Data type 'ResultData' is in the wrong place: it must come first. Further checks skipped."
    ]


def test_destest_marker_wrong_case() -> None:
    assert errors(VALID.replace("_DESTEST_", "_Destest_")) == [
        "DESTEST marker must be written 'DESTEST' (found 'Destest')."
    ]


def test_cme_marker_wrong_case() -> None:
    assert errors(VALID.replace("_CME_", "_cme_")) == [
        "CME marker must be written 'CME' (found 'cme')."
    ]


def test_missing_cme_marker() -> None:
    (e,) = errors(VALID.replace("_CME_", "_"))
    assert e.startswith("Name must start with '<DataType>_DESTEST_CME_<Series>_<Number>_'")
    assert "(found 'ResultData_DESTEST_DHN_1_TRNSYS_...')" in e


# ---- listed values ---------------------------------------------------------
def test_series_wrong_case() -> None:
    assert errors(VALID.replace("_DHN_", "_dhn_")) == [
        "Exercise series must be written 'DHN' (found 'dhn')."
    ]


def test_unknown_series_with_suggestion() -> None:
    (e,) = errors(VALID.replace("_DHN_", "_DHM_"))
    assert "not in the list (DHN, DEL)" in e
    assert "Did you mean 'DHN'?" in e


def test_unknown_data_type() -> None:
    (e,) = errors(VALID.replace("ResultData", "Results"))
    assert "Data type 'Results' is not in the list" in e


def test_metadata_spelling() -> None:
    assert errors(VALID.replace("ResultData", "ResultMetadata")) == []
    assert errors(VALID.replace("ResultData", "ResultMetaData")) == [
        "Data type must be written 'ResultMetadata' (found 'ResultMetaData')."
    ]


# ---- integer ---------------------------------------------------------------
@pytest.mark.parametrize("bad", ["1a", "-1", "one"])
def test_number_must_be_integer(bad: str) -> None:
    assert error_fields(VALID.replace("_DHN_1_", f"_DHN_{bad}_")) == {"number"}


def test_number_zero_is_valid_and_leading_zero_warns() -> None:
    assert errors(VALID.replace("_DHN_1_", "_DHN_0_")) == []
    assert any("leading zero" in w for w in warnings(VALID.replace("_DHN_1_", "_DHN_01_")))


# ---- free text ---------------------------------------------------------------
def test_empty_free_field() -> None:
    assert errors(VALID.replace("_2022_TUD_", "__TUD_")) == [
        "Tool version is empty (two '_' in a row?)."
    ]


def test_underscore_inside_free_field_is_pinpointed() -> None:
    name = VALID.replace("_TRNSYS_", "_TRNSYS_TUD-Edition_")
    (e,) = errors(name)
    assert "Found 6 parts where 5 are expected" in e
    # the fields outside the free-text block are still read and checked
    r = check_name(name, now=NOW)
    assert r.values["series"] == "DHN"
    assert r.values["created"] == datetime(2022, 1, 1, 12, 0, 0)


def test_missing_free_field() -> None:
    (e,) = errors(VALID.replace("_TUD_", "_"))
    assert "Found 4 of the 5 free-text parts" in e


def test_version_without_digit_warns() -> None:
    # missing version + '_' in the tool name gives the right number of parts but shifted values
    name = VALID.replace("_TRNSYS_2022_", "_Modelica_Buildings_")
    assert errors(name) == []
    assert any("contains no digit" in w for w in warnings(name))


def test_space_in_name_warns() -> None:
    assert any("spaces" in w for w in warnings(VALID.replace("_Clemens_", "_Clemens Maria_")))


# ---- time stamp ------------------------------------------------------------
def test_invalid_date() -> None:
    (e,) = errors(VALID.replace("2022_01_01", "2022_02_30"))
    assert "2022-02-30 12:00:00 is not a valid date/time" in e


def test_invalid_time() -> None:
    assert error_fields(VALID.replace("_12_00_00", "_25_00_00")) == {"created"}


def test_timestamp_digit_count() -> None:
    (e,) = errors(VALID.replace("2022_01_01", "22_01_01"))
    assert "year must be 4 digits (found '22')" in e


def test_future_timestamp_warns() -> None:
    assert any("future" in w for w in warnings(VALID.replace("2022_01_01", "2027_01_01")))


def test_name_too_short() -> None:
    assert any("too short" in e for e in errors("ResultData_DESTEST_CME_DHN_1.csv"))


# ---- extension -------------------------------------------------------------
def test_missing_extension_warns_and_dot_in_version_is_not_an_extension() -> None:
    name = VALID.replace("_2022_TUD_", "_18.4_TUD_")[: -len(".csv")]
    r = check_name(name, now=NOW)
    assert r.ok
    assert r.extension == ""
    assert any("no extension" in w.message for w in r.warnings)
    assert r.values["tool_version"] == "18.4"


# ---- folder consistency ----------------------------------------------------
def test_file_in_matching_folder_is_ok(tmp_path: Path) -> None:
    f = tmp_path / "CME_DHN_1" / VALID
    f.parent.mkdir()
    f.write_text("x")
    (r,) = check_files([f], now=NOW)
    assert r.ok


def test_file_in_wrong_folder_is_an_error(tmp_path: Path) -> None:
    f = tmp_path / "CME_DHN_2" / VALID
    f.parent.mkdir()
    f.write_text("x")
    (r,) = check_files([f], now=NOW)
    assert [i.field for i in r.errors] == ["folder"]
    assert "folder 'CME_DHN_2' but its name says DHN 1" in r.errors[0].message


# ---- folders, CSV and command line -----------------------------------------
@pytest.fixture
def result_folder(tmp_path: Path) -> Path:
    (tmp_path / VALID).write_text("x")
    (tmp_path / "Modelica_Buildings_AAU_JL_Network_0.csv").write_text("x")
    (tmp_path / ".hidden").write_text("x")
    sub = tmp_path / "CME_DEL_1"
    sub.mkdir()
    (sub / VALID.replace("_DHN_", "_DEL_")).write_text("x")
    return tmp_path


def test_check_folder(result_folder: Path) -> None:
    flat = check_folder(result_folder, now=NOW)
    assert [c.ok for c in flat] == [
        False,
        True,
    ]  # sorted by name (Modelica... first), .hidden skipped
    deep = check_folder(result_folder, recursive=True, now=NOW)
    assert len(deep) == 3
    assert all(c.ok for c in deep if c.path is not None and c.path.parent.name == "CME_DEL_1")


def test_check_folder_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        check_folder(tmp_path / "nope")


def test_write_csv(result_folder: Path, tmp_path: Path) -> None:
    out = write_csv(check_folder(result_folder, now=NOW), tmp_path / "r.csv", base=result_folder)
    text = out.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0].startswith("file,status,errors,warnings,extension,data_type")
    assert "2022-01-01 12:00:00" in text


def test_cli_check_names(result_folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check-names", str(result_folder)]) == 1
    assert "Summary: 1 valid, 1 with errors - 2 files checked." in capsys.readouterr().out
    assert main(["check-names", VALID]) == 0
    assert main(["check-names", str(result_folder / "missing_dir")]) == 1  # treated as a bare name


def test_cli_make_name_and_convention(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["make-name", "--series", "DHN", "--number", "1", "--data-type", "ResultData"]
    args += ["--tool", "TRNSYS", "--tool-version", "2022", "--institution", "TUD"]
    args += [
        "--first-name",
        "Clemens",
        "--last-name",
        "Felsmann",
        "--created",
        "2022-01-01 12:00:00",
    ]
    assert main(args) == 0
    assert capsys.readouterr().out.strip() == VALID
    assert main(["convention"]) == 0
    assert main([]) == 2
