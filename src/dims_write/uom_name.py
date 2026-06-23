"""CartonCloud UoM name validity — the 3–64 char rule, shared by the UoM probes.

CC validates the WHOLE unit-of-measure object whenever you PATCH any sub-field of it (the dim
fields included). So a UoM whose `name` is outside 3–64 chars rejects an otherwise-valid dims
write with a 422 (`/unitOfMeasures/{uom}/name` "Must be between 3 and 64 characters") — the trap
that blocked the CT carton UoM (every CT UoM was named "CT", 2 chars). This primitive lets both
the CT probe and the each/Base-UoM probe check that name trap read-only, BEFORE any write.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# CartonCloud's UoM-name length rule, learned from the 422.
UOM_NAME_MIN_CHARS = 3
UOM_NAME_MAX_CHARS = 64


@dataclass(frozen=True)
class UomNameStatus:
    """Whether a UoM name would pass CC's 3–64 char validation, with the detail for reporting."""

    ok: bool
    name: Any
    length: int | None   # len(name) when name is a string, else None
    reason: str


def uom_name_status(name: Any) -> UomNameStatus:
    """Classify a UoM `name` against CC's 3–64 char rule (boundaries inclusive).

    A missing name (`None`) or a non-string value is not OK — a dims PATCH onto that UoM would
    422 on the name. Whitespace is NOT trimmed: CC validates the raw string length, so we report
    what CC would see.
    """
    if isinstance(name, str):
        n = len(name)
        if UOM_NAME_MIN_CHARS <= n <= UOM_NAME_MAX_CHARS:
            return UomNameStatus(True, name, n, "name ok")
        return UomNameStatus(
            False, name, n, f"name length {n} not in [{UOM_NAME_MIN_CHARS},{UOM_NAME_MAX_CHARS}]"
        )
    reason = "name missing" if name is None else f"name not a string ({type(name).__name__})"
    return UomNameStatus(False, name, None, reason)
