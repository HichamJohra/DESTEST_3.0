"""Submissions over time: one column per month, one cell per submission (home page).

The date of a submission is the creation date in its file name. The months run from
the first submission (or `min_months` back) to the current month, so the last column
is always "now". Within a month, submissions are stacked by CME, then by tool.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ..results import Submission
from .colors import category_colors, category_of, cme_colors, cme_order

#: What a timeline can be coloured by.
COLOR_BY = ("cme", "tool", "institution", "country")

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass
class TimelineCell:
    """One submission in the timeline."""

    cme: str
    tool: str
    label: str  # submission label
    created: datetime
    institution: str = "-"
    country: str = "-"


@dataclass
class TimelineMonth:
    """One column: a month and its submissions, bottom first."""

    year: int
    month: int
    cells: list[TimelineCell] = field(default_factory=list)

    @property
    def name(self) -> str:
        """E.g. `Jan 2022`."""
        return f"{MONTHS[self.month - 1]} {self.year}"


@dataclass
class Timeline:
    """All months, oldest first, and the submissions without a date."""

    months: list[TimelineMonth]
    undated: list[str] = field(default_factory=list)
    color_by: str = "cme"  # one of COLOR_BY

    @property
    def height(self) -> int:
        """Most submissions in one month."""
        return max((len(m.cells) for m in self.months), default=0)

    @property
    def cells(self) -> list[TimelineCell]:
        """All submissions shown, oldest month first."""
        return [c for m in self.months for c in m.cells]

    def key(self, cell: TimelineCell) -> str:
        """The category a cell is coloured by (its CME, tool, institution or country)."""
        return str(getattr(cell, self.color_by))

    def colors(self) -> dict[str, str]:
        """Category -> colour, in legend order (same colours as the maps)."""
        if self.color_by == "cme":
            by_cme = cme_colors({c.cme for c in self.cells})
            return {k: by_cme[k] for k in sorted(by_cme, key=cme_order)}
        return category_colors(self.key(c) for c in self.cells)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {
            "color_by": self.color_by,
            "colors": self.colors(),
            "undated": self.undated,
            "months": [
                {
                    "month": f"{m.year}-{m.month:02d}",
                    "cells": [
                        {
                            "cme": c.cme,
                            "tool": c.tool,
                            "institution": c.institution,
                            "country": c.country,
                            "label": c.label,
                            "created": c.created.isoformat(),
                        }
                        for c in m.cells
                    ],
                }
                for m in self.months
            ],
        }


def _shift(year: int, month: int, by: int) -> tuple[int, int]:
    """The month `by` months later (or earlier, if negative).

    >>> _shift(2026, 11, 2), _shift(2026, 1, -1)
    ((2027, 1), (2025, 12))
    """
    k = year * 12 + month - 1 + by
    return k // 12, k % 12 + 1


def submission_timeline(
    cmes: dict[str, list[Submission]],
    today: date | None = None,
    min_months: int = 24,
    color_by: str = "cme",
) -> Timeline:
    """Group the submissions of several CMEs by month of creation, up to `today`.

    `color_by`: `cme`, `tool`, `institution` or `country`, used when it is drawn.
    """
    if color_by not in COLOR_BY:
        raise ValueError(f"color_by must be one of {', '.join(COLOR_BY)} (got '{color_by}')")
    today = today or date.today()
    cells: list[TimelineCell] = []
    undated: list[str] = []
    for name, subs in cmes.items():
        for s in subs:
            created = s.name_parts.get("creation_date_time")
            if isinstance(created, datetime):
                where = (category_of(s, "institution"), category_of(s, "country"))
                cells.append(TimelineCell(name, category_of(s, "tool"), s.label, created, *where))
            else:
                undated.append(s.label)
    last = (today.year, today.month)
    first = _shift(*last, -(min_months - 1))
    if cells:
        oldest = min(c.created for c in cells)
        first = min(first, (oldest.year, oldest.month))
    months: list[TimelineMonth] = []
    year, month = first
    while (year, month) <= last:
        months.append(TimelineMonth(year, month))
        year, month = _shift(year, month, 1)
    index = {(m.year, m.month): m for m in months}
    order = sorted(cells, key=lambda c: (cme_order(c.cme), c.tool.lower(), c.created))
    for c in order:
        column = index.get((c.created.year, c.created.month))
        if column is not None:  # dated after today: left out
            column.cells.append(c)
    return Timeline(months, undated, color_by)
