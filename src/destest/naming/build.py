"""Build a correct result-file name from its parts.

Example:

    >>> from datetime import datetime
    >>> from destest.naming import make_filename
    >>> make_filename(
    ...     series="DHN", number=1, data_type="ResultData",
    ...     tool="TRNSYS", tool_version="2022", institution="TUD",
    ...     first_name="Clemens", last_name="Felsmann",
    ...     created=datetime(2022, 1, 1, 12, 0, 0),
    ... )
    'ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv'

The parts are put in the order defined in `convention.FIELDS`, and the result
is checked with `check_name()` before it is returned.
"""

from datetime import datetime

from . import convention as conv
from .validate import check_name


def make_filename(
    *,
    series: str,
    number: int,
    data_type: str,
    tool: str,
    tool_version: str,
    institution: str,
    first_name: str,
    last_name: str,
    created: datetime | None = None,
    extension: str = ".csv",
) -> str:
    """Return a file name that follows the convention.

    `created` defaults to the current time. Raises `ValueError` if any part
    breaks the convention (for example an unknown series or a `_` in a name).
    """
    values: dict[str, object] = {
        "series": series,
        "number": number,
        "data_type": data_type,
        "tool": tool,
        "tool_version": tool_version,
        "institution": institution,
        "first_name": first_name,
        "last_name": last_name,
    }
    stamp = (created or datetime.now()).replace(microsecond=0)
    parts: list[str] = []
    for f in conv.FIELDS:
        if f.kind == "literal":
            parts.append(f.allowed[0])
        elif f.kind == "timestamp":
            parts.append(stamp.strftime(conv.TIMESTAMP_FORMAT))
        else:
            parts.append(str(values[f.key]))
    if extension and not extension.startswith("."):
        extension = "." + extension
    name = conv.SEPARATOR.join(parts) + (extension or "")

    result = check_name(name)
    if not result.ok:
        problems = " ".join(i.message for i in result.errors)
        raise ValueError(f"Cannot build a valid name: {problems}")
    return name
