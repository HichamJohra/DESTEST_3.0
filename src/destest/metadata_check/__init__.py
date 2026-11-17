"""Check ResultMetadata files, and write templates for them.

```python
from destest.metadata_check import check_metadata, check_metadata_folder, make_template

check_metadata("Result data/CME_DHN_1/ResultMetadata_...yaml").ok   # one file
check_metadata_folder("Result data")                              # every metadata file
make_template("DHN", 1)                                           # blank template text
template_for_data_file("ResultData_...csv")                       # pre-filled template
```

The rules come from `specs/result_metadata.yaml` (sections shared by all CMEs)
and `specs/cme/CME_<Series>_<Number>.yaml` (`simulation_config`, `model_details`).
"""

from .template import make_template, template_for_data_file
from .validate import (
    MetadataCheck,
    check_metadata,
    check_metadata_data,
    check_metadata_folder,
    expected_sections,
)

__all__ = [
    "MetadataCheck",
    "check_metadata",
    "check_metadata_data",
    "check_metadata_folder",
    "expected_sections",
    "make_template",
    "template_for_data_file",
]
