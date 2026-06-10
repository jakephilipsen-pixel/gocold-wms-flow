"""Split each-denominated SO lines into carton picks + each remainders.

Forage orders everything in eaches in CartonCloud, but 73 SKUs are
each/carton combos (``inner_pack_qty`` of 2–12 eaches per carton). When
an EA line spans at least ``min_full_cartons`` full cartons the picker
physically pulls cartons off the reserve pallet, so the picksheet line
must say cartons and point at the reserve — not the pick face.

``split_lines`` is pure (no I/O): it returns the input frame with two
extra columns and convertible lines expanded:

  * ``pick_uom``  — "CTN" for converted carton lines, "EA" otherwise
  * ``qty_eaches`` — original each-count covered by a CTN line (for
    "4 CTN (24 EA)" display); NA on EA lines

On CTN lines ``quantity`` is the carton count; on EA lines it remains
the each count (a remainder line carries ``quantity % inner_pack_qty``).
Lines pass through untouched when the SKU has ``inner_pack_qty`` <= 1,
is absent from dims, or the qty is under the threshold.
"""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

PICK_UOM_CARTON = "CTN"
PICK_UOM_EACH = "EA"


def split_lines(
    so_lines: pd.DataFrame,
    dims: pd.DataFrame | None,
    min_full_cartons: int = 1,
) -> pd.DataFrame:
    """Return ``so_lines`` with pick_uom / qty_eaches, splitting combo
    lines that span at least ``min_full_cartons`` full cartons."""
    out = so_lines.copy()
    out["pick_uom"] = PICK_UOM_EACH
    out["qty_eaches"] = pd.NA
    if (
        out.empty
        or dims is None
        or dims.empty
        or "inner_pack_qty" not in dims.columns
    ):
        return out

    ipq_map = (
        dims.dropna(subset=["product_code"])
        .drop_duplicates("product_code")
        .set_index("product_code")["inner_pack_qty"]
    )
    qty = pd.to_numeric(out["quantity"], errors="coerce").fillna(0)
    ipq = pd.to_numeric(out["product_code"].map(ipq_map), errors="coerce")

    threshold = max(int(min_full_cartons), 1)
    convertible = (ipq > 1) & (qty >= ipq * threshold)
    if not convertible.any():
        return out

    combo = out[convertible].copy()
    full_ctns = (qty[convertible] // ipq[convertible]).astype(int)
    rem = (qty[convertible] % ipq[convertible]).astype(int)

    ctn = combo.copy()
    ctn["quantity"] = full_ctns.astype(float)
    ctn["pick_uom"] = PICK_UOM_CARTON
    ctn["qty_eaches"] = (full_ctns * ipq[convertible]).astype(int)

    remainder = combo[rem > 0].copy()
    remainder["quantity"] = rem[rem > 0].astype(float)
    remainder["pick_uom"] = PICK_UOM_EACH
    remainder["qty_eaches"] = pd.NA

    result = pd.concat([out[~convertible], ctn, remainder], ignore_index=True)
    log.info(
        "carton split: %d/%d lines converted to carton picks "
        "(%d with each remainders, min_full_cartons=%d)",
        len(ctn), len(out), len(remainder), threshold,
    )
    return result
