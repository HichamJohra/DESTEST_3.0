"""Check the names of all files in the 'Result data' folder (including sub-folders).

Run it from PyCharm (right-click > Run 'check_result_names') or from a terminal:

    uv run python scripts/check_result_names.py
    uv run python scripts/check_result_names.py "some/other/folder"

Set SAVE_CSV = True to also write a CSV report to output/result_name_check.csv
(output/ is ignored by git).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_FOLDER = REPO_ROOT / "Result data"
SAVE_CSV = False
CSV_REPORT = REPO_ROOT / "output" / "result_name_check.csv"

try:
    from destest.filename_check import check_folder, print_report, write_csv
except ImportError:  # package not installed yet (`uv sync`): use the source folder
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from destest.filename_check import check_folder, print_report, write_csv


def main() -> int:
    """Check the folder given on the command line, or 'Result data'."""
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else RESULT_FOLDER
    checks = check_folder(folder, recursive=True)
    print_report(checks, base=folder)
    if SAVE_CSV:
        CSV_REPORT.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nReport written to {write_csv(checks, CSV_REPORT, base=folder)}")
    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
