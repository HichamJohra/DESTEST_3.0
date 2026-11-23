"""Write a ResultMetadata template from the spec files.

The template has every section and key the checker expects, in order, with the
description of each key as a comment, so the template and the checker can never
disagree. Given the name of a ResultData file, the values that follow from the
name (CME, data file, date, modeller, tool) are filled in already.

Example:

    >>> from destest.metadata_check import make_template
    >>> text = make_template("DHN", 1)
    >>> "model_details:" in text and "pipe_model:" in text
    True
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..filename_check import convention as conv
from ..filename_check.validate import check_name, partner_names
from ..specs import load_cme_spec, load_result_metadata_layout
from .validate import METADATA_TYPE, expected_sections

_COMMENT_COLUMN = 40
_RULE = "# " + "-" * 77


def _scalar(value: Any) -> str:
    """A value written as YAML: dates as YYYY-MM-DD hh:mm:ss, everything else quoted."""
    if isinstance(value, datetime):
        return f"{value:%Y-%m-%d %H:%M:%S}"
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def _line(indent: str, key: str, value: str, comment: str) -> str:
    text = f"{indent}{key}: {value}"
    if comment:
        text = text.ljust(_COMMENT_COLUMN - 1) + f" # {comment}"
    return text


def make_template(series: str, exercise_number: int, prefill: dict[str, Any] | None = None) -> str:
    """The text of a ResultMetadata file for one CME, with `prefill` values filled in.

    `prefill` maps `must_match` targets (naming-field keys, `cme`, `result_data_file`)
    to values; every other value is left empty.
    """
    spec = load_cme_spec(series, exercise_number)
    layout = load_result_metadata_layout()
    prefill = {"cme": spec.folder_name, **(prefill or {})}
    lines = [
        "# " + "=" * 77,
        f"# DESTEST 3.0 - ResultMetadata file for {spec.folder_name}",
        f"# {spec.cme.full_title}",
        "# " + "=" * 77,
        "# One ResultMetadata file per ResultData file; it describes that one submission.",
        "# Save it next to the ResultData file, with the same name except:",
        f"#   ResultData_...{conv.EXTENSIONS.get('ResultData', ('.csv',))[0]}"
        f"  ->  {METADATA_TYPE}_...{conv.EXTENSIONS.get(METADATA_TYPE, ('.yaml',))[0]}",
        "# Keep EVERY key and the indentation; only change the values.",
        "# A missing or an extra key is an error. 'required' values must be filled in.",
        '# Write text that looks like a number in quotes, e.g. "18.40".',
        "# This file is published in a PUBLIC repository.",
        "# " + "=" * 77,
        "",
        _line("", "metadata_format_version", str(layout.format_version), "do not change"),
    ]
    for s in expected_sections(spec, layout):
        lines += ["", _RULE, f"# {s.name}", _RULE]
        if s.kind == "text":
            req = "required" if s.required else "optional"
            lines += [f"# {req} - {s.description}", f'{s.name}: ""']
            continue
        lines.append(f"{s.name}:")
        for f in s.fields:
            req = "required" if f.required else "optional"
            comment = f"{req} - {f.description}" if f.description else req
            value = prefill.get(f.must_match) if f.must_match else None
            lines.append(_line("  ", f.key, _scalar(value), comment))
    return "\n".join(lines) + "\n"


def template_for_data_file(data_file: str | Path) -> tuple[str, str]:
    """`(metadata file name, template text)` for a ResultData file, pre-filled from its name.

    Raises `ValueError` if the name is not a valid ResultData name.
    """
    name = check_name(Path(data_file).name)
    if not name.ok:
        problems = " ".join(i.message for i in name.errors)
        raise ValueError(f"Not a valid file name: {problems}")
    if name.values.get(conv.DATA_TYPE_KEY) == METADATA_TYPE:
        raise ValueError("Give the ResultData file, not the ResultMetadata file.")
    partners = partner_names(name)
    if not partners:
        raise ValueError("This data type has no metadata file.")
    values = name.values
    prefill = {**values, "result_data_file": name.name}
    text = make_template(str(values["series"]), int(values["exercise_number"]), prefill)
    return partners[0], text
