"""The DESTEST result-file naming convention.

```python
from destest.filename_check import check_name, check_folder, make_filename

check_name("ResultData_DESTEST_CME_DHN_1_...csv").ok    # one name
check_folder("Result data", recursive=True)             # every file in a folder
make_filename(series="DHN", exercise_number=1, ...)  # build a correct name
```

The rules live in `src/destest/specs/naming_convention.yaml`.
"""

from ..result import Issue
from .build import make_filename
from .convention import describe, template
from .report import format_report, print_report, summary, write_csv
from .validate import (
    NameCheck,
    check_files,
    check_folder,
    check_location,
    check_name,
    check_pairing,
    partner_names,
)

__all__ = [
    "Issue",
    "NameCheck",
    "check_files",
    "check_folder",
    "check_location",
    "check_name",
    "check_pairing",
    "describe",
    "format_report",
    "make_filename",
    "partner_names",
    "print_report",
    "summary",
    "template",
    "write_csv",
]
