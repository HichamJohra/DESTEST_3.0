"""Tests for destest.data_check, the consistency-rule expressions and `destest check`."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from destest.check import check_submissions, format_reports
from destest.cli import main
from destest.data_check import check_data, check_data_folder, check_data_text, make_data_template
from destest.metadata_check import template_for_data_file
from destest.specs import SpecError, cme_spec_path, load_cme_spec, load_cme_spec_file
from destest.specs.expressions import check_rule, parse_rule
from destest.submission import create_submission

RESULT_DATA = Path(__file__).resolve().parents[1] / "Result data"
SPEC = load_cme_spec("DHN", 1)
HEADER = ",".join(c.header for c in SPEC.result_data.columns)
# One steady-state row: time, mass flow, 3 pressure drops, 6 supply T, 6 return T, loss, heat.
ROW = (
    "8848,22371,22371,5644,70,69.94,69.87,69.76,69.59,69.46,"
    "39.53,39.56,39.51,39.47,39.43,39.49,312.6,313041"
)
DATA = "ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv"


def _csv(rows: int = 10, header: str = HEADER, row: str = ROW) -> str:
    return "\n".join([header, *(f"{t},{row}" for t in range(rows))]) + "\n"


def _issues(text: str) -> list[tuple[str, str, str]]:
    return [(i.level, i.field, i.message) for i in check_data_text(text, SPEC).issues]


def _replace_cell(text: str, line: int, column: int, value: str) -> str:
    lines = text.splitlines()
    cells = lines[line - 1].split(",")
    cells[column] = value
    lines[line - 1] = ",".join(cells)
    return "\n".join(lines) + "\n"


# ---- the submitted files ---------------------------------------------------------
def _result_files() -> list[Path]:
    return sorted(RESULT_DATA.glob("CME_*/ResultData_*.csv")) if RESULT_DATA.is_dir() else []


@pytest.mark.parametrize("path", _result_files(), ids=lambda p: p.name)
def test_submitted_files_have_no_content_errors(path: Path) -> None:
    r = check_data(path)
    assert [str(i) for i in r.errors] == []
    assert r.n_rows == 10


# ---- a good file -------------------------------------------------------------------
def test_good_file() -> None:
    assert _issues(_csv()) == []


def test_byte_order_mark_is_accepted(tmp_path: Path) -> None:
    folder = tmp_path / "CME_DHN_1"
    folder.mkdir()
    p = folder / DATA
    p.write_bytes(b"\xef\xbb\xbf" + _csv().encode())
    assert check_data(p).issues == []


def test_not_utf8(tmp_path: Path) -> None:
    folder = tmp_path / "CME_DHN_1"
    folder.mkdir()
    p = folder / DATA
    p.write_bytes(_csv().replace("Time", "T\xefme").encode("latin-1"))
    assert [i.field for i in check_data(p).errors] == ["file"]


# ---- header ----------------------------------------------------------------------------
def test_wrong_column_name() -> None:
    text = _csv(header=HEADER.replace("Time [s]", "Time"))
    assert [(lvl, f) for lvl, f, _ in _issues(text)] == [
        ("error", "header"),  # 'Time [s]' missing
        ("error", "header"),  # 'Time' not in the spec
    ]


def test_columns_in_wrong_order() -> None:
    cols = HEADER.split(",")
    cols[1], cols[2] = cols[2], cols[1]
    found = _issues(_csv(header=",".join(cols)))
    assert any("is column 3, expected 2" in m for _, _, m in found)


def test_extra_column() -> None:
    text = "\n".join(line + ",1" for line in _csv(header=HEADER).splitlines()) + "\n"
    text = text.replace(HEADER + ",1", HEADER + ",Extra [-]", 1)
    assert ("error", "header", "Column(s) not in the spec: 'Extra [-]'.") in _issues(text)


# ---- rows ------------------------------------------------------------------------------
def test_too_few_rows() -> None:
    assert ("error", "rows", "1 data row(s); at least 2 needed.") in _issues(_csv(rows=1))


def test_too_many_rows() -> None:
    assert ("error", "rows", "11 data rows; at most 10 allowed.") in _issues(_csv(rows=11))


def test_fewer_rows_than_expected_warns() -> None:
    assert _issues(_csv(rows=9)) == [("warning", "rows", "9 data row(s); 10 expected.")]


def test_row_with_missing_cell() -> None:
    lines = _csv().splitlines()
    lines[3] = lines[3].rsplit(",", 1)[0]
    found = _issues("\n".join(lines))
    assert any(f == "rows" and "first: line 4" in m for _, f, m in found)


# ---- values ------------------------------------------------------------------------------
def test_missing_value() -> None:
    found = _issues(_replace_cell(_csv(), 3, 5, "NaN"))
    assert (
        "error",
        "T_supply_i",
        "'Fluid temperature supply i [C]': 1 missing value(s) of 10 (first: line 3).",
    ) in found


def test_column_without_any_value() -> None:
    text = _csv()
    for line in range(2, 12):
        text = _replace_cell(text, line, 17, "")
    found = _issues(text)
    assert (
        "error",
        "Q_loss_supply_i_h",
        "'Heat loss supply between i and h [W]': no value at all.",
    ) in found


def test_not_a_number() -> None:
    found = _issues(_replace_cell(_csv(), 2, 1, "8848 kg/h"))
    assert any(f == "m_flow_supply_i" and "not numbers" in m for _, f, m in found)


def test_out_of_range_warns() -> None:
    found = _issues(_replace_cell(_csv(), 4, 17, "0.446"))
    assert (
        "warning",
        "Q_loss_supply_i_h",
        "'Heat loss supply between i and h [W]': 1 value(s) outside [1, ] (first: line 4, 0.446).",
    ) in found


# ---- time ----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("line", "value", "expected"),
    [
        (2, "1", "Time must start at 0"),
        (6, "3", "not strictly increasing"),
        (11, "9.5", "Time step must be 1 s"),
    ],
)
def test_time_column(line: int, value: str, expected: str) -> None:
    found = _issues(_replace_cell(_csv(), line, 0, value))
    assert any(f == "time" and expected in m for _, f, m in found)


# ---- consistency rules --------------------------------------------------------------------
def test_supply_below_return_is_an_error() -> None:
    found = _issues(_replace_cell(_csv(), 5, 11, "71"))  # return i above supply i (70)
    assert any(
        lvl == "error" and m.startswith("Supply temperature above return") for lvl, _, m in found
    )


def test_heat_balance_off_warns_with_percentage() -> None:
    text = _csv(row=ROW.replace("313041", "308203"))
    ((lvl, field, msg),) = _issues(text)
    assert (lvl, field) == ("warning", "consistency")
    assert "fails in 10 row(s)" in msg
    assert "% apart" in msg


# ---- expressions -------------------------------------------------------------------------
def test_parse_and_check_rules() -> None:
    approx = parse_rule("a ≈ 2 * b")
    assert approx.op == "≈"
    assert approx.names == frozenset({"a", "b"})
    assert check_rule(approx, {"a": 2.01, "b": 1.0}, 0.01).ok
    assert not check_rule(approx, {"a": 2.1, "b": 1.0}, 0.01).ok
    assert check_rule(parse_rule("a ~= b"), {"a": 1.0, "b": 1.0}).ok
    assert not check_rule(parse_rule("a / b > 0"), {"a": 1.0, "b": 0.0}).ok  # division by zero


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a + b", "needs '≈' or exactly one comparison"),
        ("a < b < c", "needs '≈' or exactly one comparison"),
        ("abs(a) > 0", "not allowed in a rule"),
        ("a.real > 0", "not allowed in a rule"),
        ("a ≈ b ≈ c", "only once"),
        ("a > ", "cannot read"),
        ("a in b", "comparison not allowed"),
    ],
)
def test_rules_that_are_not_allowed(text: str, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        parse_rule(text)


@pytest.mark.parametrize(
    ("expression", "tolerance", "expected"),
    [
        ("T_supply_i > T_retrun_i", None, "not a column key: T_retrun_i"),
        ("Q_supplied ≈ m_flow_supply_i", None, "needs tolerance_relative"),
        ("open('x') > 0", None, "not allowed in a rule"),
    ],
)
def test_rules_are_checked_when_the_spec_is_loaded(
    tmp_path: Path, expression: str, tolerance: float | None, expected: str
) -> None:
    data: dict[str, Any] = yaml.safe_load(cme_spec_path("DHN", 1).read_text(encoding="utf-8"))
    data["result_data"]["consistency"] = [
        {"name": "r", "expression": expression, "tolerance_relative": tolerance}
    ]
    p = tmp_path / "CME_DHN_1.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(SpecError, match=expected):
        load_cme_spec_file(p)


# ---- empty ResultData file and new submission ----------------------------------------------
def test_data_template_is_the_header_only() -> None:
    text = make_data_template("DHN", 1)
    assert text == HEADER + "\n"
    found = _issues(text)
    assert ("error", "rows", "0 data row(s); at least 2 needed.") in found
    assert all(f != "header" for _, f, _ in found)  # the header itself is right


def test_cli_data_template(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["data-template", "CME_DHN_1"]) == 0
    assert capsys.readouterr().out == HEADER + "\n"
    out = tmp_path / "x.csv"
    assert main(["data-template", "CME_DHN_1", "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == HEADER + "\n"
    assert main(["data-template", "CME_DHN_1", "-o", str(out)]) == 1  # no overwrite
    assert main(["data-template", "DHN_1"]) == 2


def test_cli_new_submission(tmp_path: Path) -> None:
    folder = tmp_path / "CME_DHN_1"
    args = ["new-submission", "--series", "DHN", "--exercise-number", "1"]
    args += ["--tool", "TRNSYS", "--tool-version", "2022", "--institution", "TUD"]
    args += ["--first-name", "Clemens", "--last-name", "Felsmann"]
    args += ["--creation-date-time", "2022-01-01 12:00:00", "-o", str(folder)]
    assert main(args) == 0
    data_file = folder / DATA
    meta_file = folder / DATA.replace("ResultData", "ResultMetadata").replace(".csv", ".yaml")
    assert data_file.read_text(encoding="utf-8") == HEADER + "\n"
    meta = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
    assert meta["submission_info"]["result_data_file"] == DATA
    assert meta["modeller"]["last_name"] == "Felsmann"
    assert main(args) == 1  # files exist: not overwritten
    assert main([*args, "--force"]) == 0
    # the pair is complete: only the content is still missing
    reports = check_submissions(tmp_path)
    assert all(i.stage == "content" for r in reports for i in r.errors)


def test_create_submission_refuses_bad_parts_and_overwrites(tmp_path: Path) -> None:
    parts: dict[str, Any] = {
        "series": "DHN",
        "exercise_number": 1,
        "tool": "TRNSYS",
        "tool_version": "2022",
        "institution": "TUD",
        "first_name": "Clemens",
        "last_name": "Felsmann",
        "creation_date_time": datetime(2022, 1, 1, 12),
    }
    with pytest.raises(ValueError, match="'_'"):
        create_submission(tmp_path / "a", **{**parts, "tool": "TRN_SYS"})
    assert not (tmp_path / "a").exists()  # nothing written
    data_file, meta_file = create_submission(tmp_path / "b", **parts)
    assert (data_file.name, meta_file.parent) == (DATA, tmp_path / "b")
    with pytest.raises(FileExistsError):
        create_submission(tmp_path / "b", **parts)
    create_submission(tmp_path / "b", force=True, **parts)


# ---- whole folders and `destest check` ----------------------------------------------------
def _submission(tmp_path: Path, with_metadata: bool = True) -> Path:
    folder = tmp_path / "CME_DHN_1"
    folder.mkdir()
    (folder / DATA).write_text(_csv(), encoding="utf-8")
    if with_metadata:
        name, text = template_for_data_file(DATA)
        meta = yaml.safe_load(text)
        meta["modeller"].update(
            institution_full_name="TU Dresden",
            institution_city="Dresden",
            institution_country="Germany",
        )
        meta["modelling_tool"]["licence"] = "commercial"
        meta["simulation_config"]["time_step_s"] = "1"
        meta["deviations"] = "none"
        (folder / name).write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")
    return tmp_path


def test_check_data_folder(tmp_path: Path) -> None:
    root = _submission(tmp_path)
    assert [c.ok for c in check_data_folder(root)] == [True]


def test_check_submissions_all_good(tmp_path: Path) -> None:
    reports = check_submissions(_submission(tmp_path))
    assert [(r.data_type, r.status) for r in reports] == [
        ("ResultData", "ok"),
        ("ResultMetadata", "ok"),
    ]
    text = format_reports(reports)
    assert "2 valid (0 with warnings), 0 with errors - 2 files checked" in text


def test_check_submissions_bad_name_stops_before_content(tmp_path: Path) -> None:
    root = _submission(tmp_path, with_metadata=False)
    (root / "CME_DHN_1" / "results.csv").write_text("not even csv", encoding="utf-8")
    reports = {r.path.name: r for r in check_submissions(root)}
    bad = reports["results.csv"]
    assert {i.stage for i in bad.issues} == {"name"}
    good = reports[DATA]
    assert [(i.stage, i.field) for i in good.issues] == [("name", "pairing")]  # no metadata yet


def test_cli_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _submission(tmp_path)
    assert main(["check", str(root)]) == 0
    assert main(["check-data", str(root)]) == 0
    data_file = root / "CME_DHN_1" / DATA
    data_file.write_text(_csv(rows=1), encoding="utf-8")
    assert main(["check", str(root), "--errors-only"]) == 1
    out = capsys.readouterr().out
    assert "content/rows: 1 data row(s); at least 2 needed." in out
    assert main(["check", str(root / "missing")]) == 2
