"""Colours shared by the home-page visuals (map and timeline).

* By CME: one colour family per series (DHN blue, DCN green, DEL amber, ...), and
  within a series one shade per exercise, from light (lowest number) to dark.
* By modelling tool, institution or country: one distinct colour per value
  (`category_colors`), the same on every map and timeline.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results import Submission

#: Light-to-dark ramps; series in `SERIES_RAMP` get theirs, other series the next free one.
RAMPS: dict[str, tuple[str, ...]] = {
    "blue": ("#b5d4f4", "#85b7eb", "#378add", "#185fa5", "#0c447c"),
    "green": ("#c0dd97", "#97c459", "#639922", "#3b6d11", "#27500a"),
    "amber": ("#fac775", "#ef9f27", "#ba7517", "#854f0b", "#633806"),
    "purple": ("#cecbf6", "#afa9ec", "#7f77dd", "#534ab7", "#3c3489"),
    "teal": ("#9fe1cb", "#5dcaa5", "#1d9e75", "#0f6e56", "#085041"),
    "coral": ("#f5c4b3", "#f0997b", "#d85a30", "#993c1d", "#712b13"),
    "pink": ("#f4c0d1", "#ed93b1", "#d4537e", "#993556", "#72243e"),
}
SERIES_RAMP = {"DHN": "blue", "DCN": "green", "DEL": "amber"}

#: Distinct colours for modelling tools (in alphabetical order of the tools).
TOOL_PALETTE = (
    "#7f77dd",
    "#ef9f27",
    "#1d9e75",
    "#d4537e",
    "#d85a30",
    "#378add",
    "#639922",
    "#888780",
    "#993556",
    "#0f6e56",
)


def split_cme(name: str) -> tuple[str, int]:
    """`CME_DHN_1` -> (`DHN`, 1).

    >>> split_cme("CME_DCN_12")
    ('DCN', 12)
    """
    _, series, number = name.split("_")
    return series, int(number)


def _mix(a: str, b: str, t: float) -> str:
    """Colour between `a` and `b` (t from 0 to 1)."""
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb, strict=True))


def ramp_shade(ramp: tuple[str, ...], t: float) -> str:
    """The shade at position `t` (0 = lightest, 1 = darkest) of a ramp.

    >>> ramp_shade(RAMPS["blue"], 0.0), ramp_shade(RAMPS["blue"], 1.0)
    ('#b5d4f4', '#0c447c')
    """
    t = max(0.0, min(1.0, t))
    pos = t * (len(ramp) - 1)
    i = min(int(pos), len(ramp) - 2)
    return _mix(ramp[i], ramp[i + 1], pos - i)


def cme_colors(names: Iterable[str]) -> dict[str, str]:
    """Colour of each CME: its series' ramp, lighter for lower exercise numbers.

    >>> c = cme_colors(["CME_DHN_1", "CME_DHN_2", "CME_DHN_3", "CME_DCN_1"])
    >>> c["CME_DHN_1"], c["CME_DHN_3"]
    ('#85b7eb', '#0c447c')
    >>> c["CME_DCN_1"]  # a single exercise in its series: a middle shade
    '#639922'
    """
    by_series: dict[str, list[int]] = {}
    for name in names:
        series, number = split_cme(name)
        by_series.setdefault(series, []).append(number)
    free = [r for r in RAMPS if r not in SERIES_RAMP.values()]
    out: dict[str, str] = {}
    for k, series in enumerate(sorted(by_series)):
        ramp = RAMPS[SERIES_RAMP.get(series) or free[k % len(free)]]
        numbers = sorted(set(by_series[series]))
        for i, number in enumerate(numbers):
            # From the second-lightest shade to the darkest; one exercise: the middle.
            t = 0.5 if len(numbers) == 1 else 0.25 + 0.75 * i / (len(numbers) - 1)
            out[f"CME_{series}_{number}"] = ramp_shade(ramp, t)
    return out


def tool_of(sub: "Submission") -> str:
    """The modelling tool of a submission, as in its file name (e.g. `TRNSYS`)."""
    return str(sub.name_parts.get("tool") or "unknown").strip() or "unknown"


def _modeller(sub: "Submission", key: str) -> str:
    block = sub.metadata.get("modeller")
    value = block.get(key) if isinstance(block, dict) else None
    return "" if value is None or isinstance(value, dict) else str(value).strip()


def category_of(sub: "Submission", by: str) -> str:
    """The category of a submission for colouring: `tool`, `institution` or `country`.

    Tool and institution as in the file name when the metadata file does not say; the
    country from the metadata file (`-` when unknown).
    """
    if by == "tool":
        return tool_of(sub)
    if by == "institution":
        return _modeller(sub, "institution") or str(sub.name_parts.get("institution") or "-")
    if by == "country":
        return _modeller(sub, "institution_country") or "-"
    raise ValueError(f"unknown category '{by}' (tool, institution or country)")


def category_colors(values: Iterable[str]) -> dict[str, str]:
    """A distinct colour per value (tools, institutions, countries), in alphabetical order.

    >>> category_colors(["TRNSYS", "CitySim", "TRNSYS"])
    {'CitySim': '#7f77dd', 'TRNSYS': '#ef9f27'}
    """
    names = sorted(set(values), key=str.lower)
    return {t: TOOL_PALETTE[i % len(TOOL_PALETTE)] for i, t in enumerate(names)}


#: Kept for readability where the values are tools.
tool_colors = category_colors


def cme_order(name: str) -> tuple[str, int]:
    """Sort key: series, then exercise number (so CME_DHN_10 comes after CME_DHN_9)."""
    return split_cme(name)
