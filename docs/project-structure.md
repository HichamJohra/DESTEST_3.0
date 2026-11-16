# Project structure

```text
DESTEST_3.0/
├── pyproject.toml            package metadata, dependencies, tool settings (Ruff, mypy, pytest)
├── uv.lock                   exact versions of every dependency (written by uv; commit it)
├── .python-version           Python version uv uses for the local environment
├── .pre-commit-config.yaml   checks run before each commit
├── mkdocs.yml                documentation site settings
├── Result data/              submitted result files, one folder per exercise (CME_DHN_1, …)
├── src/
│   └── destest/              the library: reusable code, grouped in sub-packages
│       ├── __init__.py
│       ├── __main__.py       allows `python -m destest ...`
│       ├── cli.py            the `destest` command and its sub-commands
│       ├── py.typed          tells type checkers the package has type hints
│       ├── specs/            the rules, as YAML files (edit these, not the code)
│       │   ├── naming_convention.yaml   file-name rules, shared by all CMEs
│       │   ├── result_metadata.yaml     sections of a ResultMetadata file, shared by all CMEs
│       │   ├── cme/CME_DHN_1.yaml       content rules, one file per CME
│       │   ├── schema.py                the allowed layout of those files (pydantic)
│       │   ├── expressions.py           the safe mini-language of the consistency rules
│       │   └── __init__.py              load_naming_convention(), load_cme_spec()
│       ├── check.py          `destest check`: names, pairing and content in one go
│       ├── result.py         shared result types: Issue, CheckResult (base of every check)
│       ├── submission.py     create the two files of a new submission
│       ├── data_check/       check the content of ResultData (.csv) files
│       │   ├── validate.py     header, rows, values, time, ranges, consistency rules
│       │   └── template.py     empty ResultData file: the header row of a CME
│       ├── metadata_check/   check ResultMetadata files, write templates
│       │   ├── validate.py     check one file or a folder against the specs
│       │   └── template.py     write a (pre-filled) template from the specs
│       └── filename_check/   check and build result-file names (naming convention)
│           ├── convention.py   reads specs/naming_convention.yaml for the checker
│           ├── validate.py     check a name, a list of files or a folder
│           ├── build.py        build a correct name
│           └── report.py       text report and CSV export
├── scripts/                  ready-to-run tasks (click Run in PyCharm)
│   ├── check_results.py      full check of "Result data" (one click in PyCharm)
│   └── new_submission.py     create a new, correctly named file pair (fill in the values first)
├── tests/                    automatic tests
│   ├── test_data_check.py
│   ├── test_filename_check.py
│   ├── test_metadata_check.py
│   └── test_specs.py
├── docs/                     this documentation (Markdown)
└── .github/
    ├── workflows/ci.yml      tests + checks on every push and pull request
    ├── workflows/docs.yml    builds the docs; publishes them from main
    └── dependabot.yml        monthly update pull requests for actions and dependencies
```

## Where things go

| You are writing… | Put it in |
|---|---|
| A function you will reuse (read a result file, compute a KPI, plot) | a module in a sub-package of `src/destest/`, e.g. `src/destest/kpi/nmbe.py` |
| A new topic with several functions | a new sub-package: a folder in `src/destest/` with an `__init__.py` |
| Something you run to get a job done | a script in `scripts/` that imports from `destest` |
| A task others should run from the terminal | a sub-command in `src/destest/cli.py` |
| A rule a file must follow (name, columns, ranges, metadata keys) | the YAML files in `src/destest/specs/` |
| A new common modelling exercise | copy `specs/cme/CME_DHN_1.yaml` to `CME_<Series>_<Number>.yaml` and edit it |
| A check that a function works | a `tests/test_<topic>.py` file |
| A third-party package the code needs | `uv add <package>` (updates `pyproject.toml` and `uv.lock`) |

Possible next sub-packages: `destest.io` (read result and metadata files),
`destest.kpi` (NMBE and other comparison KPIs), `destest.dashboard` (HTML dashboards),
`destest.cme` (the exercise graph built from `cme_links.ttl`).

## Why `src/`?

The package lives in `src/destest/`, not directly in the repository root. Python then
cannot import it by accident from the current folder; tests and scripts always use the
installed package, so packaging mistakes show up on your machine first. You never type
`src` in code: imports are `from destest.filename_check import ...`.
