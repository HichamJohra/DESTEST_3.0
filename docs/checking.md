# Checking submissions

## Start a new submission

One command creates both files of a submission, correctly named, in a folder:

```bash
uv run destest new-submission --series DHN --exercise-number 1 \
    --tool TRNSYS --tool-version 18.4 --institution TUD \
    --first-name Clemens --last-name Felsmann -o "Result data/CME_DHN_1"
```

- `ResultData_...csv` contains only the header row of the CME (exact column names, in
  order). Paste the results below it; the number of rows is up to you.
- `ResultMetadata_...yaml` is the metadata template, with everything that follows from the
  name already filled in.

Or, in PyCharm: fill in the values at the top of `scripts/new_submission.py` and run it.

The creation date and time is the current time unless `--creation-date-time` is given.
Existing files are never overwritten unless `--force` is added. The two parts on their own:

```bash
uv run destest data-template CME_DHN_1 -o my_results.csv          # header-only CSV
uv run destest metadata-template "Result data/CME_DHN_1/ResultData_...csv" -o "Result data/CME_DHN_1"
```

## Check everything

One command checks everything about the submitted result files:

```bash
uv run destest check "Result data"
uv run destest check "Result data" --errors-only     # list only files with problems
```

For every file in the folder and its sub-folders:

| Stage | What | Rules from |
|---|---|---|
| `name` | Naming convention, folder (`CME_<Series>_<Number>`), data/metadata pairing | `specs/naming_convention.yaml` |
| `content` of a ResultData file | Header, rows, values, time column, ranges, consistency rules | `result_data` in `specs/cme/CME_<Series>_<Number>.yaml` |
| `content` of a ResultMetadata file | Sections and keys, required values, agreement with the file name | `specs/result_metadata.yaml` + the CME file |

The content is only checked once the name is valid (the name says which CME, and so which
rules, apply). Each problem is reported as `stage/where: message`, e.g.

```text
[WARN] CME_DHN_1/ResultData_DESTEST_CME_DHN_1_Modelica_Buildings_AAU_Jerome_Laluce_2022_01_01_12_00_00.csv
         warning content/consistency: Heat supplied matches m_flow * cp * (T_supply - T_return): fails in 10 row(s) (first: line 2, 308203 vs 313648, 1.74% apart).
```

The command ends with exit code 0 when no file has errors, 1 otherwise. The separate
commands `check-names`, `check-data` and `check-metadata` run one stage only.

## ResultData content

Every setting below lives in the `result_data` part of the CME's spec file.

| Check | Setting | Failure |
|---|---|---|
| Encoding (a UTF-8 byte-order mark from Excel is accepted) | `file.encoding` | error |
| Column names, exactly and in order; no extra columns | `header`, `columns[].header` | error |
| Number of data rows | `rows.min`, `rows.max` / `rows.expected` | error / warning |
| Every row has as many cells as the header | – | error |
| Values are numbers | `column_defaults.type`, `columns[].type` | error |
| Missing values (`""`, `NaN`, …) | `column_defaults.missing_values`, `max_missing_fraction` | `on_missing` / `all_missing` |
| Time column starts at `start`, steps by `step`, increases | `time` | error |
| Plausible values | `columns[].range` | `on_out_of_range` |
| Rules across columns, row by row | `consistency` | `severity` of the rule |

Problems in a column are reported once, with the number of rows concerned and the first
line (line numbers count the header as line 1).

### Consistency rules

A rule compares two expressions built from column keys, numbers, `+ - * / **` and brackets:

```yaml
consistency:
  - name: Heat supplied matches m_flow * cp * (T_supply - T_return)
    expression: "Q_supplied ≈ m_flow_supply_i / 3600 * 4180 * (T_supply_i - T_return_i)"
    tolerance_relative: 0.01      # needed with ≈: |left - right| <= 1 % of right
    severity: warning

  - name: Supply temperature above return temperature
    expression: "T_supply_i > T_return_i"
    severity: error
```

`≈` (or `~=`) means "equal within `tolerance_relative`"; otherwise use exactly one of
`<`, `<=`, `>`, `>=`, `==`, `!=`. Function calls and anything else are refused, so a spec
file can never run code. Rules are checked when the spec file is loaded: an unknown column
key or a missing tolerance is reported by `uv run destest specs`.
