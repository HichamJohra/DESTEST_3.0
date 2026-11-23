# Getting started

## 1. Install uv (once per computer)

[uv](https://docs.astral.sh/uv/) installs Python, creates the project's virtual
environment and installs every dependency at the exact versions in `uv.lock`.

=== "Windows (PowerShell)"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

Open a new terminal afterwards and check with `uv --version`.

## 2. Set up the project (once per clone)

```bash
git clone https://github.com/HichamJohra/DESTEST_3.0.git
cd DESTEST_3.0
uv sync                         # creates .venv with Python 3.13, the package and all dev tools
uv run pre-commit install       # run the checks automatically before each commit
```

!!! tip "PyCharm"
    Point PyCharm at the environment uv created: *Settings → Project → Python Interpreter →
    Add Interpreter → Add Local Interpreter → Select existing → `.venv\Scripts\python.exe`*
    (or choose the **uv** interpreter type, which does the same).
    New terminal tabs then have `python` and `destest` available.

## 3. Check result files

```bash
uv run destest check-names "Result data" --recursive
uv run destest check-names "Result data" -r --csv report.csv   # also save a CSV report
uv run destest check-names my_new_file.csv                     # one file or bare name
```

The command ends with exit code 0 when every name is valid and 1 otherwise, so it
can be used in scripts and CI.

## 4. Create a correct file name

```bash
uv run destest make-name --data-type ResultData --series DHN --exercise-number 1 \
    --tool TRNSYS --tool-version 2022 --institution TUD \
    --first-name Clemens --last-name Felsmann
```

prints something like
`ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2026_10_24_12_31_05.csv`
(the time stamp is the current time unless `--creation-date-time` is given). Use
`--data-type ResultMetadata` for the matching metadata file (it gets `.yaml`).
The options follow the parts defined in `specs/naming_convention.yaml`;
`uv run destest make-name --help` lists them.

To create the files themselves (an empty, header-only CSV and the pre-filled metadata
file, both correctly named), use `destest new-submission` with the same options and
`-o <folder>`; see [Checking submissions](checking.md).

## From Python

```python
from destest.filename_check import check_folder, print_report

checks = check_folder("Result data", recursive=True)
print_report(checks)
bad = [c.name for c in checks if not c.ok]
```
