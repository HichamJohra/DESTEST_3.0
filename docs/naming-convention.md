# Result-file naming convention

Every result file submitted to a DESTEST common modelling exercise (CME) is named:

```text
<DataType>_DESTEST_CME_<Series>_<Number>_<ModellingTool>_<ToolVersion>_<Institution>_<FirstName>_<LastName>_<YYYY>_<MM>_<DD>_<hh>_<mm>_<ss>.<ext>
```

The results and their metadata are two files with the same name apart from the data
type, stored in a folder named after the exercise, `CME_<Series>_<Number>`:

```text
Result data/
└── CME_DHN_1/
    ├── ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv
    └── ResultMetadata_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.<ext>
```

| Part | Rule |
|---|---|
| `<DataType>` | One of `ResultData`, `ResultMetadata` – always first |
| `DESTEST` | Mandatory, exactly as written |
| `CME` | Mandatory, exactly as written |
| `<Series>` | One of `DHN` (District Heating Network), `DEL` (Distribution Electrical Grid) |
| `<Number>` | Exercise number in the series, a whole number: `0`, `1`, `2`, … |
| `<ModellingTool>` | Name of the modelling tool – free text, not empty |
| `<ToolVersion>` | Version of the modelling tool – free text, not empty |
| `<Institution>` | Institution of the modeller – free text, not empty |
| `<FirstName>` | First name of the modeller – free text, not empty |
| `<LastName>` | Last name of the modeller – free text, not empty |
| `<YYYY>_<MM>_<DD>_<hh>_<mm>_<ss>` | Date and time the file was created; must be a real date and time |

## Rules that follow from the format

- **No `_` inside a part.** The underscore separates the parts, so a tool or person
  name cannot contain one. Write `Modelica-Buildings` or `ModelicaBuildings`, not
  `Modelica_Buildings`; `Jean-Luc`, not `Jean_Luc`.
- **Exact spelling and case** for `DESTEST`, `CME`, the series and the data type
  (`ResultMetadata`, not `ResultMetaData`).
- **Fixed digit counts** in the time stamp: 4 for the year, 2 for everything else
  (`2026_03_07_09_05_00`).
- **Dots are fine inside a part** (`18.4`); the extension is whatever follows the last
  dot at the very end of the name.
- **Folder and name agree**: a file in `CME_DHN_1/` must say `DHN` and `1` in its name.

## What the checker reports

| Severity | What |
|---|---|
| Error | Data type not first, or not in the list; missing or misspelled `DESTEST`/`CME`; series not in the list or in the wrong place; number not a whole number; empty part; too many or too few parts; time stamp not a valid date/time or wrong digit count; file in a folder for another exercise |
| Warning | Leading zero in the number (`01`); spaces in a part; tool version without any digit (often a sign that a part is missing); time stamp in the future; no file extension |

A file passes when it has no errors. Warnings are shown but do not fail the check.

!!! note "Limit of any automatic check"
    If one part is missing **and** another contains an extra `_`, the number of parts is
    right again and the values are simply shifted, e.g. `Modelica_Buildings_AAU_…` is read
    as tool `Modelica`, version `Buildings`. The checker flags this with the
    "tool version contains no digit" warning, but cannot be certain.

## Open points

- **Changing the order.** The order of the parts is defined once, in `FIELDS` in
  `src/destest/naming/convention.py`; the checker, `make-name` and the template follow it.
- **Allowed file extensions** per data type (e.g. `.csv` for `ResultData`) are not
  specified yet; set `ALLOWED_EXTENSIONS` in `convention.py` once agreed.
