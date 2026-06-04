"""Delivery-address normalisation for run prediction.

Lifted from scripts/extract_address_runs.py so the script and the
predictor share one implementation. The address_key is the dedup key
the history model is built and queried on.
"""
from __future__ import annotations

from typing import Any


def normalise_address(
    addr: dict[str, Any] | None,
) -> tuple[str, str, str, str, str, str]:
    """Return (key, full, street, suburb, state, postcode).

    key is a lower-cased, whitespace-collapsed join of street + suburb +
    state + postcode. Two addresses with the same key are the same
    delivery point even if CC formatting differs (case, trailing spaces).
    """
    if not addr:
        return ("", "", "", "", "", "")

    lines = addr.get("lines") or addr.get("addressLines") or []
    if isinstance(lines, str):
        street = lines.strip()
    elif isinstance(lines, list):
        street = ", ".join(str(x).strip() for x in lines if x)
    else:
        street = ""

    state_raw = addr.get("state") or {}
    if isinstance(state_raw, dict):
        state = state_raw.get("code") or state_raw.get("name") or ""
    else:
        state = str(state_raw)

    suburb = addr.get("suburb") or addr.get("city") or ""
    postcode = addr.get("postcode") or addr.get("postCode") or ""

    full = ", ".join(p for p in [street, suburb, state, postcode] if p)
    key = " ".join(
        " ".join(str(x).lower().split())
        for x in [street, suburb, state, postcode] if x
    )
    return (key, full, street, suburb, state, postcode)


def address_key(addr: dict[str, Any] | None) -> str:
    """Just the normalised dedup key for an address."""
    return normalise_address(addr)[0]
