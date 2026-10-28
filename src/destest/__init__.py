"""destest - tools for the District Energy Simulation Test Procedure (DESTEST).

Sub-packages:

- `destest.naming`: check and build result-file names

Command line:

    destest check-names "Result data" --recursive
    python -m destest check-names "Result data" --recursive
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("destest")  # single source of truth: pyproject.toml
except PackageNotFoundError:  # running from the source tree without installing
    __version__ = "0.0.0+unknown"
