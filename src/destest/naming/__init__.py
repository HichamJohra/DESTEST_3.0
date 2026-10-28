"""The DESTEST result-file naming convention.

```python
from destest.naming import check_name, check_folder, make_filename

check_name("ResultData_DESTEST_CME_DHN_1_...csv").ok    # one name
check_folder("Result data", recursive=True)             # every file in a folder
make_filename(series="DHN", number=1, ...)              # build a correct name
```

The rules live in `destest.naming.convention`.
"""

from .build import make_filename
from .convention import describe, template
from .report import format_report, print_report, summary, write_csv
from .validate import Issue, NameCheck, check_files, check_folder, check_location, check_name

__all__ = [
    "Issue",
    "NameCheck",
    "check_files",
    "check_folder",
    "check_location",
    "check_name",
    "describe",
    "format_report",
    "make_filename",
    "print_report",
    "summary",
    "template",
    "write_csv",
]
