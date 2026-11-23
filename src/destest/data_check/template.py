"""Write an empty ResultData (.csv) file: only the header row of a CME.

The header is built from `result_data` in the CME's spec file (column names,
order, delimiter), so it is exactly what the checker expects. No data row is
written: the number of rows is up to the modeller.

    >>> from destest.data_check import make_data_template
    >>> make_data_template("DHN", 1).split(",")[:2]
    ['Time [s]', 'Mass flow rate supply i [kg/h]']
"""

import csv
import io

from ..specs import load_cme_spec


def make_data_template(series: str, exercise_number: int) -> str:
    """The header row of a ResultData file for one CME, ending with a new line."""
    rd = load_cme_spec(series, exercise_number).result_data
    out = io.StringIO()
    csv.writer(out, delimiter=rd.file.delimiter, lineterminator="\n").writerow(
        c.header for c in rd.columns
    )
    return out.getvalue()
