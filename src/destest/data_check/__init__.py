"""Check the content of ResultData (.csv) files.

```python
from destest.data_check import check_data, check_data_folder

check_data("Result data/CME_DHN_1/ResultData_...csv").ok   # one file
check_data_folder("Result data")                          # every ResultData file
make_data_template("DHN", 1)                              # header row of an empty file
```

The rules come from `result_data` in `specs/cme/CME_<Series>_<Number>.yaml`.
"""

from .template import make_data_template
from .validate import DataCheck, check_data, check_data_folder, check_data_text

__all__ = ["DataCheck", "check_data", "check_data_folder", "check_data_text", "make_data_template"]
