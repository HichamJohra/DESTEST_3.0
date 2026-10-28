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
│       └── naming/           result-file naming convention
│           ├── convention.py   the rules (edit here when the convention changes)
│           ├── validate.py     check a name, a list of files or a folder
│           ├── build.py        build a correct name
│           └── report.py       text report and CSV export
├── scripts/                  ready-to-run tasks (click Run in PyCharm)
│   └── check_result_names.py
├── tests/                    automatic tests
│   └── test_naming.py
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
| A check that a function works | a `tests/test_<topic>.py` file |
| A third-party package the code needs | `uv add <package>` (updates `pyproject.toml` and `uv.lock`) |

Possible next sub-packages: `destest.io` (read result and metadata files),
`destest.kpi` (NMBE and other comparison KPIs), `destest.dashboard` (HTML dashboards),
`destest.cme` (the exercise graph built from `cme_links.ttl`).

## Why `src/`?

The package lives in `src/destest/`, not directly in the repository root. Python then
cannot import it by accident from the current folder; tests and scripts always use the
installed package, so packaging mistakes show up on your machine first. You never type
`src` in code: imports are `from destest.naming import ...`.
