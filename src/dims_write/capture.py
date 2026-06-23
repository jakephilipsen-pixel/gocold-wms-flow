"""Captured-dims → CartonCloud unit boundary (M-DIMS units fix, 23 Jun 2026).

The capture template measures cartons in **millimetres** — loaded by
``analysis.dim_loader`` as ``outer_l_mm`` / ``outer_w_mm`` / ``outer_h_mm`` (mm) plus
``outer_weight_kg``. CartonCloud's UoM ``length`` / ``width`` / ``height`` fields are
**centimetres** (Jake, confirmed against the CC UI 23 Jun 2026 — this supersedes the earlier
"mm" assumption in CLAUDE.md gotcha #6). So at the ONE boundary where captured dims become the
values PATCHed to CC, L/W/H are divided by 10; weight (kg) is unchanged.

This is the surgical fix chosen over a full repo-wide rename: the internal analysis pipeline
(slotting, weight estimation, tagging, routing) stays in mm and is self-consistent there, so it
is untouched. Only what crosses to CartonCloud is converted, in this single shared function the
dims-write scripts all call — so the ÷10 lives in one tested place, not duplicated five times.

⚠ Dims already written live before this fix (``sHL-BWC`` sandbox + the 4 EA Forage SKUs from
M-DIMS-5b) are 10× too large and must be corrected in a separate, deliberately-armed run.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

# CartonCloud stores carton dims in centimetres; the capture template is in millimetres.
MM_PER_CM = 10.0


def mm_to_cm(value: Any) -> float | None:
    """Convert a millimetre length to centimetres; pass ``None``/``NaN`` through as ``None``.

    Unset dims must stay unset (the write path drops them) — never coerce a missing value to
    ``0.0``, which would PATCH a real, wrong dimension.
    """
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return round(float(value) / MM_PER_CM, 4)


def captured_cc_dims_table(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Build the ``code -> CC dims`` table the dims-write scripts feed to CartonCloud.

    Reads the millimetre capture columns, converts L/W/H to centimetres (CC's unit), and keeps
    weight in kg unchanged. Only fully-measured SKUs (L/W/H all present) are offered — a SKU
    missing any of L/W/H is dropped; a SKU missing only weight is kept (its L/W/H still write,
    and the write path drops the NaN weight). Keyed by the captured base SKU code.

    This is the EXACT body the five run scripts used to duplicate, plus the mm→cm conversion —
    so every write path (sandbox round-trip/soak, shadow-validate, live proving, CT bulk) gets
    the unit fix from one place.
    """
    table: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        code = str(row["product_code"]).strip()
        l_mm, w_mm, h_mm = row.get("outer_l_mm"), row.get("outer_w_mm"), row.get("outer_h_mm")
        if any(v is None or v != v for v in (l_mm, w_mm, h_mm)):  # v != v catches NaN
            continue
        table[code] = {
            "length": mm_to_cm(l_mm),
            "width": mm_to_cm(w_mm),
            "height": mm_to_cm(h_mm),
            "weight": row.get("outer_weight_kg"),  # kg — unchanged, NaN dropped downstream
        }
    return table
