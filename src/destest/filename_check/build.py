"""Build a correct result-file name from its parts.

Example:

    >>> from datetime import datetime
    >>> from destest.filename_check import make_filename
    >>> make_filename(
    ...     data_type="ResultData", series="DHN", exercise_number=1,
    ...     tool="TRNSYS", tool_version="2022", institution="TUD",
    ...     first_name="Clemens", last_name="Felsmann",
    ...     creation_date_time=datetime(2022, 1, 1, 12, 0, 0),
    ... )
    'ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv'

The parts are the fields of `naming_convention.yaml` (by their `key`), put in the
order the file defines. The time stamp defaults to now, the extension to the first
one allowed for the data type. The result is checked with `check_name()` before
it is returned.
"""

from datetime import datetime

from . import convention as conv
from .validate import check_name


def make_filename(*, extension: str | None = None, **parts: object) -> str:
    """Return a file name that follows the convention.

    Pass every part of the name as a keyword named after its field `key`
    (see `destest convention`). Raises `ValueError` for a missing or unknown
    part, or if a part breaks the convention (e.g. an unknown series or a `_`).
    """
    needed = [f.key for f in conv.FIELDS if f.kind not in ("literal", "timestamp")]
    missing = [k for k in needed if parts.get(k) is None]
    unknown = sorted(set(parts) - set(conv.FIELD_KEYS))
    if missing or unknown:
        msg = []
        if missing:
            msg.append(f"missing: {', '.join(missing)}")
        if unknown:
            msg.append(f"unknown: {', '.join(unknown)}")
        raise ValueError(f"Cannot build a name ({'; '.join(msg)}).")

    out: list[str] = []
    for f in conv.FIELDS:
        if f.kind == "literal":
            out.append(f.allowed[0])
        elif f.kind == "timestamp":
            stamp = parts.get(f.key) or datetime.now()
            if not isinstance(stamp, datetime):
                raise ValueError(f"{f.key} must be a datetime (got {stamp!r}).")
            out.append(stamp.replace(microsecond=0).strftime(f.timestamp_format))
        else:
            out.append(str(parts[f.key]))

    if extension is None:
        exts = conv.EXTENSIONS.get(str(parts.get(conv.DATA_TYPE_KEY)), ())
        extension = exts[0] if exts else ""
    if extension and not extension.startswith("."):
        extension = "." + extension
    name = conv.SEPARATOR.join(out) + extension

    result = check_name(name)
    if not result.ok:
        problems = " ".join(i.message for i in result.errors)
        raise ValueError(f"Cannot build a valid name: {problems}")
    return name
