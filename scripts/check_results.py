"""Check every file in the 'Result data' folder: names, pairing and content.

The same as `uv run destest check "Result data"`, but runnable with one click:
in PyCharm, right-click this file > Run 'check_results'. From a terminal:

    uv run python scripts/check_results.py
    uv run python scripts/check_results.py "some/other/folder"

Set ERRORS_ONLY = True to list only the files with problems.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_FOLDER = REPO_ROOT / "Result data"  # Default folder "Result data" to check all result files
ERRORS_ONLY = False

try:
    from destest.check import check_submissions, format_reports
except ImportError:  # package not installed yet (`uv sync`): use the source folder
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from destest.check import check_submissions, format_reports


def main() -> int:
    """Check the folder given on the command line, or 'Result data'."""
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else RESULT_FOLDER
    reports = check_submissions(folder)
    print(format_reports(reports, base=folder, show_ok=not ERRORS_ONLY))
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
