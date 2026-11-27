"""Write docs/comparison-metrics.md (the catalogue of comparison metrics) from the code.

Run after adding or changing a metric: in PyCharm, right-click this file > Run
'make_metrics_doc'. From a terminal:

    uv run python scripts/make_metrics_doc.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "comparison-metrics.md"

try:
    from destest.analysis.point_by_point_comparison.catalogue import metrics_catalogue_markdown
except ImportError:  # package not installed yet (`uv sync`): use the source folder
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from destest.analysis.point_by_point_comparison.catalogue import metrics_catalogue_markdown


def main() -> int:
    """Write the page; report where."""
    DOC.write_text(metrics_catalogue_markdown(), encoding="utf-8", newline="\n")
    print(f"Written: {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
