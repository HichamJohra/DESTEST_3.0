# DESTEST_3.0
Web App for the District Energy Simulation Test Procedure

[![CI](https://github.com/HichamJohra/DESTEST_3.0/actions/workflows/ci.yml/badge.svg)](https://github.com/HichamJohra/DESTEST_3.0/actions/workflows/ci.yml)
[![Docs](https://github.com/HichamJohra/DESTEST_3.0/actions/workflows/docs.yml/badge.svg)](https://hichamjohra.github.io/DESTEST_3.0/)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

The `destest` Python package holds the building blocks of the app. It checks submitted
result files: their names, the pairing of data and metadata files, the content of the
ResultData (.csv) and ResultMetadata (.yaml) files. The rules are YAML spec files in
`src/destest/specs/` (one per CME). File names follow the DESTEST naming convention:

```text
<DataType>_DESTEST_CME_<Series>_<Number>_<ModellingTool>_<ToolVersion>_<Institution>_<FirstName>_<LastName>_<YYYY>_<MM>_<DD>_<hh>_<mm>_<ss>.<ext>
```

where `<DataType>` is `ResultData` for the results and `ResultMetadata` for the matching metadata file.

## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync                                                # set up .venv with everything needed
uv run destest check "Result data"                     # check names, pairing and content
uv run destest web                                     # web app on http://127.0.0.1:8050
uv run pytest                                          # run the tests
uv run pre-commit install                              # run the checks before each commit
```

## Documentation

- [Getting started](docs/getting-started.md)
- [Checking submissions](docs/checking.md)
- [Naming convention](docs/naming-convention.md)
- [ResultMetadata files](docs/result-metadata.md)
- [Dashboards](docs/dashboards.md): KPIs and visuals per CME
- [Web app](docs/web-app.md): the dashboards in the browser (Dash), Docker
- [Project structure](docs/project-structure.md)
- [Development](docs/development.md): uv, Ruff, mypy, pre-commit, CI, docs site

Published site: <https://hichamjohra.github.io/DESTEST_3.0/>

## Repository layout

```text
src/destest/     the library (sub-package per topic, e.g. filename_check/)
scripts/         ready-to-run tasks
tests/           automatic tests
docs/            documentation site (MkDocs)
Result data/     submitted result files, one folder per exercise
```

## License

MIT – see [LICENSE](LICENSE).
