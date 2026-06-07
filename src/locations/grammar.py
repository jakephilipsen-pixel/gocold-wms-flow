"""Parse Go Cold's warehouse location naming convention.

Grammar (operator confirmed, May 2026):

    XX-YY-ZZ            3-segment NON-split bay
                          ZZ=01    → PICK FACE position 1 (~750mm, floor level)
                          ZZ=02    → PICK FACE position 2 (~1500mm, upper but
                                       still hand-pickable, no forklift needed)
                          ZZ=03+   → RESERVE (forklift territory)

    XX-YY-ZZ-WW         4-segment SPLIT bay (only some aisles built this way)
                          ZZ=01 always (splits live at floor level)
                          WW=01    → PICK FACE position 1 (~750mm, lower half)
                          WW=02    → PICK FACE position 2 (~1100mm, upper half
                                       of split)

Where:
    XX = aisle code (two letters)
    YY = bay number within aisle (two digits)
    ZZ = level (two digits)
    WW = split sub-level (two digits, only on split bays)

Note on truth sources:
    For 'is this a pick face', CC's efficiency field is authoritative
    (efficiency >= 21 = pick face). The grammar here infers position +
    bay-height which CC doesn't model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

# Strict regex — only accepts AA-99-99 or AA-99-99-99 form
_LOC_RE = re.compile(r"^([A-Z]{2})-(\d{2})-(\d{2})(?:-(\d{2}))?$")


@dataclass
class LocationInfo:
    """Parsed structure for a single warehouse location name."""
    raw: str
    valid: bool
    aisle: str | None = None
    bay: int | None = None
    level: int | None = None
    sublevel: int | None = None
    is_split_bay: bool = False
    is_pick_face_by_grammar: bool = False  # grammar-inferred (advisory)
    position: int | None = None  # 1, 2, or 3
    bay_height_mm: int | None = None  # 750 / 1100 / 1500
    role_by_grammar: str = "unknown"  # 'pick_face' | 'reserve' | 'unknown'
    reason: str = ""


# Position → bay height (mm) — used by slotting logic.
#   Position 1: floor pick face. In non-split bay = lower of two stacked pick
#               faces, ~750mm reach. In split bay = lower half, ~750mm reach.
#   Position 2: upper pick face. In non-split bay = upper position, still hand-
#               pickable up to ~1500mm. In split bay = upper half, ~1100mm.
#   Position 3: reserve (forklift) above pick faces. Not used for slotting.
#
# Note: Position 2 height differs between split (1100mm) and non-split (1500mm)
# bays. We resolve this at parse time based on is_split_bay.
POSITION_TO_HEIGHT_MM_SPLIT = {1: 750, 2: 1100}
POSITION_TO_HEIGHT_MM_NONSPLIT = {1: 750, 2: 1500}


def parse_location_name(name: str) -> LocationInfo:
    """Parse a single location name string into structured info.

    Examples:
        >>> parse_location_name("AA-05-01")     # non-split lower pick face
        LocationInfo(... position=1, bay_height_mm=750, role='pick_face' ...)
        >>> parse_location_name("AA-05-02")     # non-split upper pick face
        LocationInfo(... position=2, bay_height_mm=1500, role='pick_face' ...)
        >>> parse_location_name("AA-05-03")     # reserve above
        LocationInfo(... position=None, role='reserve' ...)
        >>> parse_location_name("DJ-01-01-01")  # split lower
        LocationInfo(... position=1, bay_height_mm=750, role='pick_face' ...)
        >>> parse_location_name("DJ-01-01-02")  # split upper
        LocationInfo(... position=2, bay_height_mm=1100, role='pick_face' ...)
    """
    if not isinstance(name, str):
        return LocationInfo(raw=str(name), valid=False, reason="not a string")
    name = name.strip().upper()
    if not name:
        return LocationInfo(raw=name, valid=False, reason="empty")

    m = _LOC_RE.match(name)
    if not m:
        return LocationInfo(
            raw=name, valid=False,
            reason="does not match XX-YY-ZZ or XX-YY-ZZ-WW grammar",
        )

    aisle, bay_s, level_s, sublevel_s = m.groups()
    bay = int(bay_s)
    level = int(level_s)
    sublevel = int(sublevel_s) if sublevel_s else None
    is_split = sublevel is not None

    info = LocationInfo(
        raw=name, valid=True, aisle=aisle, bay=bay, level=level,
        sublevel=sublevel, is_split_bay=is_split,
    )

    if is_split:
        # 4-segment split bay. Splits only valid at level 01.
        if level != 1:
            info.role_by_grammar = "unknown"
            info.reason = (
                f"split bay at level {level}; splits expected only at level 01"
            )
            return info
        if sublevel in (1, 2):
            info.is_pick_face_by_grammar = True
            info.position = sublevel
            info.bay_height_mm = POSITION_TO_HEIGHT_MM_SPLIT[sublevel]
            info.role_by_grammar = "pick_face"
            info.reason = (
                f"split bay sub-level {sublevel:02d} → "
                f"position {sublevel} ({info.bay_height_mm}mm)"
            )
        else:
            info.role_by_grammar = "unknown"
            info.reason = f"split bay sub-level {sublevel} not in {{01,02}}"
        return info

    # 3-segment non-split bay
    if level in (1, 2):
        info.is_pick_face_by_grammar = True
        info.position = level
        info.bay_height_mm = POSITION_TO_HEIGHT_MM_NONSPLIT[level]
        info.role_by_grammar = "pick_face"
        info.reason = (
            f"non-split bay level {level:02d} → "
            f"position {level} ({info.bay_height_mm}mm)"
        )
    else:
        info.is_pick_face_by_grammar = False
        info.position = None
        info.bay_height_mm = None
        info.role_by_grammar = "reserve"
        info.reason = (
            f"non-split bay level {level} → reserve storage (forklift)"
        )
    return info


def classify_locations(
    names: Iterable[str],
    excluded: set[str] | None = None,
) -> pd.DataFrame:
    """Apply parse_location_name to every name; return a DataFrame.

    `excluded` is an optional set of location names that should be marked
    role='excluded' (e.g. blacked-out locations in the PDF map).
    """
    excluded = excluded or set()
    rows = []
    for n in names:
        info = parse_location_name(n)
        excluded_flag = info.raw in excluded
        rows.append({
            "location_name": info.raw,
            "valid": info.valid,
            "aisle": info.aisle,
            "bay": info.bay,
            "level": info.level,
            "sublevel": info.sublevel,
            "is_split_bay": info.is_split_bay,
            "is_pick_face_by_grammar": info.is_pick_face_by_grammar and not excluded_flag,
            "position": info.position,
            "bay_height_mm": info.bay_height_mm,
            "role_by_grammar": (
                "excluded" if excluded_flag else info.role_by_grammar
            ),
            "parse_reason": (
                "excluded; do not use" if excluded_flag else info.reason
            ),
        })
    return pd.DataFrame(rows)
