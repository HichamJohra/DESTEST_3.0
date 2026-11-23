"""Maps of the contributions (same style as the NSBI Smart Building Mapping app).

Submissions are placed at their institution's city (`modeller.institution_city`,
`modeller.institution_country` in the metadata file), with the coordinates of
`specs/locations.yaml`; an unknown city falls back to the centre of its country.
Maps use map tiles (Carto Positron, no key needed) and fit the view to the points.

* `category_map`: markers coloured by a category; a menu switches between fields;
* `exercises_map`: all submissions of several CMEs, coloured by CME (home page).
"""

import math
from dataclasses import dataclass, field
from typing import Any

from ..results import Submission
from ..specs import load_locations
from .context import PALETTE

Figure = dict[str, Any]

#: Map tiles (no API key needed), as in the NSBI app.
BASEMAP = "carto-positron"


@dataclass
class MapPoint:
    """One marker: position, hover text, and its category for each colour field."""

    lat: float
    lon: float
    hover: str
    categories: dict[str, str] = field(default_factory=dict)  # field -> category


def meta_value(sub: Submission, path: str) -> str:
    """A metadata value by `section.key` (or `section`), as text; `-` if missing."""
    section, _, key = path.partition(".")
    block = sub.metadata.get(section)
    value = block.get(key) if isinstance(block, dict) and key else block
    text = "" if value is None or isinstance(value, dict) else str(value).strip()
    return text or "-"


def locate(sub: Submission) -> tuple[float, float] | None:
    """(lat, lon) of a submission's institution, or None if city and country are unknown."""
    places = load_locations()
    city = meta_value(sub, "modeller.institution_city")
    country = meta_value(sub, "modeller.institution_country")
    where = places.cities.get(f"{city}, {country}") or places.countries.get(country)
    return (where.lat, where.lon) if where is not None else None


def spread(points: list[MapPoint], radius: float = 0.25) -> None:
    """Move markers that share a place onto a small circle, so all stay visible."""
    groups: dict[tuple[float, float], list[MapPoint]] = {}
    for p in points:
        groups.setdefault((p.lat, p.lon), []).append(p)
    for (lat, lon), same in groups.items():
        if len(same) > 1:
            for k, p in enumerate(same):
                angle = 2 * math.pi * k / len(same)
                p.lat = lat + radius * math.sin(angle)
                p.lon = lon + 1.6 * radius * math.cos(angle)


def auto_view(points: list[MapPoint]) -> tuple[dict[str, float], float]:
    """Centre and zoom that show all points (as in the NSBI app)."""
    if not points:
        return {"lat": 50.0, "lon": 10.0}, 2.5
    lats, lons = [p.lat for p in points], [p.lon for p in points]
    center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
    extent = max(max(lats) - min(lats), max(lons) - min(lons), 4.0)
    zoom = max(1.0, min(12.0, math.log2(360 / extent) - 0.6))
    return center, zoom


def category_map(
    points: list[MapPoint],
    fields: list[str],
    height: int = 560,
    note: str = "",
) -> Figure:
    """Markers coloured by category. With several `fields`, a menu chooses the one shown."""
    data: list[dict[str, Any]] = []
    owners: list[int] = []  # field index of each trace
    for f_i, name in enumerate(fields):
        groups: dict[str, list[MapPoint]] = {}
        for p in points:
            groups.setdefault(p.categories.get(name, "-"), []).append(p)
        for c_i, (category, members) in enumerate(sorted(groups.items())):
            data.append(
                {
                    "type": "scattermap",
                    "lat": [p.lat for p in members],
                    "lon": [p.lon for p in members],
                    "mode": "markers",
                    "name": category,
                    "visible": f_i == 0,
                    "marker": {"size": 14, "color": PALETTE[c_i % len(PALETTE)], "opacity": 0.9},
                    "hovertext": [p.hover for p in members],
                    "hovertemplate": "%{hovertext}<extra></extra>",
                }
            )
            owners.append(f_i)
    center, zoom = auto_view(points)
    layout: dict[str, Any] = {
        "map": {"style": BASEMAP, "center": center, "zoom": zoom},
        "height": height,
        "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
        "showlegend": True,  # Plotly hides the legend when there is only one trace
        "legend": {
            "title": {"text": fields[0] if fields else ""},
            "x": 0.01,
            "y": 0.99,
            "xanchor": "left",
            "yanchor": "top",
            "bgcolor": "rgba(255,255,255,0.85)",
        },
        "annotations": [],
    }
    if len(fields) > 1:
        layout["margin"]["t"] = 56
        layout["updatemenus"] = [
            {
                "buttons": [
                    {
                        "label": name,
                        "method": "update",
                        "args": [
                            {"visible": [o == f_i for o in owners]},
                            {"legend.title.text": name},
                        ],
                    }
                    for f_i, name in enumerate(fields)
                ],
                "direction": "down",
                "showactive": True,
                "x": 0,
                "xanchor": "left",
                "y": 1,
                "yanchor": "bottom",
                "pad": {"t": 0, "b": 4},
            }
        ]
        layout["annotations"].append(
            {
                "text": "Colour by",
                "xref": "paper",
                "yref": "paper",
                "x": 0,
                "y": 1,
                "yshift": 40,
                "xanchor": "left",
                "yanchor": "bottom",
                "showarrow": False,
                "font": {"size": 12, "color": "#5d6675"},
            }
        )
    if note:
        layout["annotations"].append(
            {
                "text": note,
                "xref": "paper",
                "yref": "paper",
                "x": 0.01,
                "y": 0.01,
                "xanchor": "left",
                "yanchor": "bottom",
                "showarrow": False,
                "bgcolor": "rgba(255,255,255,0.85)",
                "font": {"size": 11},
            }
        )
    return {"data": data, "layout": layout}


def hover_text(sub: Submission, *lines: str) -> str:
    """Hover text of a submission: label, institution, city, then extra lines."""
    head = [
        f"<b>{sub.label}</b>",
        f"{meta_value(sub, 'modeller.institution_full_name')}, "
        f"{meta_value(sub, 'modeller.institution_city')}",
    ]
    return "<br>".join([*head, *lines])


def exercises_map(cmes: dict[str, list[Submission]], height: int = 480) -> Figure:
    """All submissions of several CMEs, coloured by CME (for the home page)."""
    points: list[MapPoint] = []
    missing: list[str] = []
    for name, subs in cmes.items():
        for s in subs:
            where = locate(s)
            if where is None:
                missing.append(s.label)
                continue
            points.append(MapPoint(*where, hover_text(s, f"Exercise: {name}"), {"Exercise": name}))
    spread(points)
    note = f"Not placed (city unknown): {len(missing)}" if missing else ""
    return category_map(points, ["Exercise"], height=height, note=note)
