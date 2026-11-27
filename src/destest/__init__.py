"""destest - tools for the District Energy Simulation Test Procedure (DESTEST).

Sub-packages:

- `destest.specs`: the rules, as YAML files (naming convention, one file per CME)
- `destest.filename_check`: check and build result-file names
- `destest.metadata_check`: check ResultMetadata files, write templates
- `destest.data_check`: check the content of ResultData files
- `destest.check`: everything at once (`destest check`)
- `destest.results`: load the submissions of a CME
- `destest.analysis`: comparisons, metrics, accuracy grade, visuals and dashboards
  (`destest dashboard`)

Command line:

    destest check "Result data"
    destest check-names "Result data" --recursive
    python -m destest check-names "Result data" --recursive
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("destest")  # single source of truth: pyproject.toml
except PackageNotFoundError:  # running from the source tree without installing
    __version__ = "0.0.0+unknown"
