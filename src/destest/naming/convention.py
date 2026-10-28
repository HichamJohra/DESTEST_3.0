"""The DESTEST result-file naming convention, written as data.

This is the only place where the convention is defined. The checker
(`validate.py`), the name builder (`build.py`) and the printed template all
read `FIELDS` below, so a change here - a new exercise series, a new data
type, or moving a field - is picked up everywhere.

Current convention:

    <DataType>_DESTEST_CME_<Series>_<Number>_<ModellingTool>_<ToolVersion>_<Institution>_<FirstName>_<LastName>_<YYYY>_<MM>_<DD>_<hh>_<mm>_<ss>.<ext>

Example:

    ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv

with a matching `ResultMetadata_DESTEST_CME_...` file for the metadata.

Rules (from "Data file naming conventions.txt"):

* The data type comes first and must be one of the listed values.
* `DESTEST_CME` follows the data type and is mandatory.
* The series must be one of the listed values; the number is an integer (0, 1, 2, ...).
* Tool, version, institution, first and last name are free text, not empty.
* `YYYY_MM_DD_hh_mm_ss` is a valid date and time when the file was created.

Decisions taken when turning the text into code:

* `_` separates the fields, so free-text fields must not contain `_`. Use `-`
  or CamelCase instead, e.g. `Modelica-Buildings` or `ModelicaBuildings`.
* The file extension is not checked yet (see `ALLOWED_EXTENSIONS`).
"""

from dataclasses import dataclass

#: Character that separates the fields of a file name.
SEPARATOR = "_"

#: Exercise series: code -> description.
SERIES: dict[str, str] = {
    "DHN": "District Heating Network",
    "DEL": "Distribution Electrical Grid",
}

#: Allowed data types.
DATA_TYPES: tuple[str, ...] = ("ResultData", "ResultMetadata")

#: Allowed file extensions (lower case, with dot), or None to accept any.
#: Example: ``ALLOWED_EXTENSIONS = (".csv", ".txt", ".json")``
ALLOWED_EXTENSIONS: tuple[str, ...] | None = None

#: Warn when the time stamp is later than "now + this many hours"
#: (a small margin allows for files created in other time zones).
FUTURE_TOLERANCE_HOURS = 24

#: The six parts of the time stamp, with the number of digits each must have.
TIMESTAMP_PARTS: tuple[tuple[str, int], ...] = (
    ("year", 4),
    ("month", 2),
    ("day", 2),
    ("hour", 2),
    ("minute", 2),
    ("second", 2),
)
TIMESTAMP_FORMAT = SEPARATOR.join(("%Y", "%m", "%d", "%H", "%M", "%S"))

#: Result files are grouped in folders named like this, e.g. "CME_DHN_1".
#: The checker verifies that a file's series and number match its folder.
FOLDER_PATTERN = r"^CME_(?P<series>[A-Za-z]+)_(?P<number>\d+)$"


@dataclass(frozen=True)
class Field:
    """One field of the file name.

    `kind` is one of:

    - `literal`: fixed text (`DESTEST`, `CME`)
    - `choice`: one of `allowed`
    - `integer`: whole number >= 0
    - `text`: free text, not empty, no separator
    - `timestamp`: date and time, written as `YYYY_MM_DD_hh_mm_ss`
    """

    key: str
    label: str
    kind: str
    allowed: tuple[str, ...] = ()
    placeholder: str = ""

    @property
    def n_tokens(self) -> int:
        """How many separator-delimited parts this field occupies."""
        return len(TIMESTAMP_PARTS) if self.kind == "timestamp" else 1


#: The fields, in the order they appear in the file name.
FIELDS: tuple[Field, ...] = (
    Field("data_type", "Data type", "choice", DATA_TYPES, "<DataType>"),
    Field("prefix_project", "DESTEST marker", "literal", ("DESTEST",), "DESTEST"),
    Field("prefix_cme", "CME marker", "literal", ("CME",), "CME"),
    Field("series", "Exercise series", "choice", tuple(SERIES), "<Series>"),
    Field("number", "Exercise number", "integer", placeholder="<Number>"),
    Field("tool", "Modelling tool", "text", placeholder="<ModellingTool>"),
    Field("tool_version", "Tool version", "text", placeholder="<ToolVersion>"),
    Field("institution", "Institution", "text", placeholder="<Institution>"),
    Field("first_name", "First name", "text", placeholder="<FirstName>"),
    Field("last_name", "Last name", "text", placeholder="<LastName>"),
    Field(
        "created",
        "Creation date and time",
        "timestamp",
        placeholder="<YYYY>_<MM>_<DD>_<hh>_<mm>_<ss>",
    ),
)

#: Field keys, for convenience.
FIELD_KEYS: tuple[str, ...] = tuple(f.key for f in FIELDS)


def head_fields() -> tuple[Field, ...]:
    """The fields before the free-text block (data type, DESTEST, CME, series, number)."""
    out: list[Field] = []
    for f in FIELDS:
        if f.kind == "text":
            break
        out.append(f)
    return tuple(out)


def head_template() -> str:
    """Template of the start of a name, e.g. `<DataType>_DESTEST_CME_<Series>_<Number>`."""
    return SEPARATOR.join(f.placeholder or f.key for f in head_fields())


def template(extension: str = ".<ext>") -> str:
    """Human-readable template of a correct file name."""
    return SEPARATOR.join(f.placeholder or f.key for f in FIELDS) + extension


def expected_token_count() -> int:
    """Number of separator-delimited parts in a correct name (without extension)."""
    return sum(f.n_tokens for f in FIELDS)


def describe() -> str:
    """The rules as plain text, for the command line and the docs."""
    lines = ["DESTEST result-file naming convention", "", "  " + template(), ""]
    for f in FIELDS:
        if f.kind == "literal":
            rule = f"must be '{f.allowed[0]}'"
        elif f.kind == "choice":
            names = SERIES if f.key == "series" else {}
            rule = "one of: " + ", ".join(
                f"{v} ({names[v]})" if v in names else v for v in f.allowed
            )
        elif f.kind == "integer":
            rule = "whole number, e.g. 0, 1, 2"
        elif f.kind == "text":
            rule = f"free text, not empty, no '{SEPARATOR}'"
        else:
            rule = "valid date and time, YYYY_MM_DD_hh_mm_ss"
        lines.append(f"  {f.placeholder or f.key:<32} {f.label}: {rule}")
    ext = "any" if ALLOWED_EXTENSIONS is None else ", ".join(ALLOWED_EXTENSIONS)
    lines += ["", f"  File extension: {ext}", "  Folder: CME_<Series>_<Number>, e.g. CME_DHN_1"]
    return "\n".join(lines)
