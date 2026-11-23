"""Create the two files of a new submission, correctly named.

    >>> from destest.submission import create_submission
    >>> data_file, metadata_file = create_submission(  # doctest: +SKIP
    ...     "Result data/CME_DHN_1",
    ...     series="DHN", exercise_number=1, tool="TRNSYS", tool_version="18.4",
    ...     institution="TUD", first_name="Clemens", last_name="Felsmann",
    ... )

Writes, in the given folder:

* `ResultData_...csv`: only the header row of the CME (no data);
* `ResultMetadata_...yaml`: the metadata template, pre-filled from the name.

Used by `destest new-submission` and `scripts/new_submission.py`.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from .data_check import make_data_template
from .data_check.validate import DATA_TYPE
from .filename_check import convention as conv
from .filename_check import make_filename
from .metadata_check import template_for_data_file

PathLike = str | Path


def create_submission(
    folder: PathLike, *, force: bool = False, **parts: object
) -> tuple[Path, Path]:
    """Write an empty ResultData file and its ResultMetadata file; return both paths.

    `parts` are the parts of the file name by their key in `naming_convention.yaml`
    (the data type is set here). `creation_date_time` defaults to now.
    Raises `ValueError` for a wrong name part and `FileExistsError` if a file
    exists already and `force` is False. Nothing is written if either check fails.
    """
    values: dict[str, Any] = dict(parts)  # Any: the values are checked by make_filename
    values[conv.DATA_TYPE_KEY] = DATA_TYPE
    if values.get("creation_date_time") is None:
        values["creation_date_time"] = datetime.now().replace(microsecond=0)
    data_name = make_filename(**values)
    meta_name, meta_text = template_for_data_file(data_name)
    data_text = make_data_template(str(values["series"]), int(str(values["exercise_number"])))

    out = Path(folder)
    targets = [(out / data_name, data_text), (out / meta_name, meta_text)]
    existing = [p for p, _ in targets if p.exists()]
    if existing and not force:
        names = ", ".join(p.name for p in existing)
        raise FileExistsError(f"Exists already (use force to overwrite): {names}")
    out.mkdir(parents=True, exist_ok=True)
    for path, text in targets:
        path.write_text(text, encoding="utf-8")
    return targets[0][0], targets[1][0]
