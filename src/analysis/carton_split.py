"""Split each-denominated SO lines into carton picks + each remainders.

Forage orders everything in eaches in CartonCloud, but 73 SKUs are
each/carton combos (``inner_pack_qty`` of 2–12 eaches per carton). When
an EA line spans at least ``min_full_cartons`` full cartons the picker
physically pulls cartons off the reserve pallet, so the picksheet line
must say cartons and point at the reserve — not the pick face.

``split_lines`` is pure (no I/O): it returns the input frame with two
extra columns and convertible lines expanded.

Required input columns:

* ``so_lines`` — must include ``product_code`` and ``quantity``
* ``dims`` — must include ``product_code`` and ``inner_pack_qty``

Output columns added:

* ``pick_uom``  — "CTN" for converted carton lines, "EA" otherwise
* ``qty_eaches`` — original each-count covered by a CTN line (for
  "4 CTN (24 EA)" display); NA on EA lines (nullable Int64)

On CTN lines ``quantity`` is the carton count; on EA lines it remains
the each count (a remainder line carries ``quantity % inner_pack_qty``).
Lines pass through untouched when the SKU has ``inner_pack_qty`` <= 1,
is absent from dims, or the qty is under the threshold.

Input row order is preserved. When a line is split, the CTN line appears
first and the EA remainder immediately follows. The index is reset.
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
    out.index = range(len(out))  # positional — order survives odd caller indexes
    out["pick_uom"] = PICK_UOM_EACH
    out["qty_eaches"] = pd.array([pd.NA] * len(out), dtype="Int64")
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
    convertible = (
        (ipq > 1)
        & (ipq.mod(1) == 0)
        & (qty.mod(1) == 0)
        & (qty >= ipq * threshold)
    )
    n_fractional = int(((ipq > 1) & ((ipq.mod(1) != 0) | (qty.mod(1) != 0))).sum())
    if n_fractional:
        log.warning(
            "carton split: %d combo-SKU lines left as eaches — fractional "
            "quantity or inner_pack_qty (check the dims capture sheet)",
            n_fractional,
        )
    if not convertible.any():
        return out

    ctn = out[convertible].copy()
    full_ctns = (qty[convertible] // ipq[convertible]).astype(int)
    rem = (qty[convertible] % ipq[convertible]).astype(int)

    # quantity cast matches the extract's float64 quantity dtype
    ctn["quantity"] = full_ctns.astype(float)
    ctn["pick_uom"] = PICK_UOM_CARTON
    ctn["qty_eaches"] = (full_ctns * ipq[convertible]).astype("Int64")

    remainder = out[convertible][rem > 0].copy()
    remainder["quantity"] = rem[rem > 0].astype(float)
    remainder["pick_uom"] = PICK_UOM_EACH
    remainder["qty_eaches"] = pd.array([pd.NA] * len(remainder), dtype="Int64")

    # Preserve input row order: each CTN line (tie=0) sorts before its
    # EA remainder (tie=1); untouched lines keep their original position.
    untouched = out[~convertible].copy()
    untouched["_order"] = untouched.index
    untouched["_tie"] = 0
    ctn["_order"] = ctn.index
    ctn["_tie"] = 0
    remainder["_order"] = remainder.index
    remainder["_tie"] = 1
    result = (
        pd.concat([untouched, ctn, remainder])
        .sort_values(["_order", "_tie"], kind="mergesort")
        .drop(columns=["_order", "_tie"])
        .reset_index(drop=True)
    )
    log.info(
        "carton split: %d/%d lines converted to carton picks "
        "(%d with each remainders, min_full_cartons=%d)",
        len(ctn), len(out), len(remainder), threshold,
    )
    return result
