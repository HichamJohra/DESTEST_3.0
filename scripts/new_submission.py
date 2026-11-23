"""Create the two files of a new submission, correctly named.

Fill in the values below, then run: in PyCharm, right-click this file > Run
'new_submission'. From a terminal: `uv run python scripts/new_submission.py`.

It writes, in OUTPUT_FOLDER:

* ResultData_DESTEST_CME_..._.csv    only the header row of the CME; paste the results below it
* ResultMetadata_DESTEST_CME_..._.yaml  the metadata template, pre-filled from the name

Rules for the values: no "_" inside a value (use "-" or CamelCase), series one of
the list in specs/naming_convention.yaml. Existing files are not overwritten unless
OVERWRITE = True. The same as `uv run destest new-submission ...`.
"""

import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---- Fill in ------------------------------------------------------------------
SERIES = "DHN"  # DHN, DCN or DEL
EXERCISE_NUMBER = 1
TOOL = "TRNSYS"  # modelling tool, e.g. Modelica-Buildings
TOOL_VERSION = "18.4"
INSTITUTION = "TUD"  # short form
FIRST_NAME = "Clemens"
LAST_NAME = "Felsmann"
CREATION_DATE_TIME: datetime | None = None  # None = now, or e.g. datetime(2026, 1, 30, 9, 0, 0)
OUTPUT_FOLDER = REPO_ROOT / "Result data" / f"CME_{SERIES}_{EXERCISE_NUMBER}"
OVERWRITE = False
# -------------------------------------------------------------------------------

try:
    from destest.submission import create_submission
except ImportError:  # package not installed yet (`uv sync`): use the source folder
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from destest.submission import create_submission


def main() -> int:
    """Create the files and say where they are."""
    try:
        data_file, metadata_file = create_submission(
            OUTPUT_FOLDER,
            force=OVERWRITE,
            series=SERIES,
            exercise_number=EXERCISE_NUMBER,
            tool=TOOL,
            tool_version=TOOL_VERSION,
            institution=INSTITUTION,
            first_name=FIRST_NAME,
            last_name=LAST_NAME,
            creation_date_time=CREATION_DATE_TIME,
        )
    except (ValueError, FileExistsError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Written: {data_file}")
    print(f"Written: {metadata_file}")
    print("Next: paste the results under the header, fill in the metadata file, then run")
    print("scripts/check_results.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
