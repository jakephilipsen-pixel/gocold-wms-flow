"""Slotting recommender — operator-assigned bay + algorithm-computed pick face.

Division of labour:
  - Operator decides bay height per SKU (the `pallet_height_bucket` column)
  - Algorithm computes pick face capacity + replen strategy for that location

Bay height comes from the operator's `Pallet height 1, 2 or 3` column:
  Bucket 1 → 750mm  (small/low bay)
  Bucket 2 → 1100mm (medium bay)
  Bucket 3 → 1500mm (large/top bay)

Routing comes from `Pickbench for repack (Y/N)`:
  Y → bench flow (replen as days-of-cover at pick face)
  N → bypass flow (replen as whole-pallet units)

Fallbacks when operator hasn't classified yet:
  - Missing bay: bay_height_mm = None, flagged "AWAITING BAY ASSIGNMENT"
  - Missing pickbench: defaults to bench-flow logic (bench can handle anything)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

MIN_DAYS_COVER_AT_FACE = 2.0
MAX_DAYS_COVER_AT_FACE = 7.0

# Tolerance for "stack fits the bay" — the operator-assigned bay heights are
# nominal guides, not hard caps. 10% covers typical real-world overruns
# (e.g. Funday 4-layer × 290mm = 1160mm in a 1100mm bay; fine in practice).
# Beyond that we genuinely have to drop a layer at the pick face.
STACK_FIT_TOLERANCE = 0.10


@dataclass
class SlottingResult:
    recommendations: pd.DataFrame
    unmeasured_count: int
    measured_count: int
    no_bay_assignment_count: int
    pickbench_y_count: int
    pickbench_n_count: int
    pickbench_unclassified_count: int


def _pickbench_label(p: object) -> str:
    if p is True:
        return "bench"
    if p is False:
        return "bypass"
    return "unclassified"


def _pick_face_cartons_at_position(
    cartons_per_pallet: float,
    layers_per_pallet: float,
    carton_h_mm: float,
    bay_height_mm: int,
) -> tuple[int, bool]:
    """How many cartons at the pick face at this operator-assigned position?

    Returns (cartons_at_face, fits_cleanly).

    The pick face is essentially a single pallet of this SKU sitting at the
    assigned position. The number of cartons that fit = how many full layers
    stack within the bay height (with a small tolerance for tight fits).
    """
    if (
        pd.isna(cartons_per_pallet) or pd.isna(layers_per_pallet)
        or pd.isna(carton_h_mm)
        or cartons_per_pallet <= 0 or layers_per_pallet <= 0 or carton_h_mm <= 0
    ):
        return 0, False

    cartons_per_layer = cartons_per_pallet / layers_per_pallet
    stack_height = carton_h_mm * layers_per_pallet
    cap = bay_height_mm * (1.0 + STACK_FIT_TOLERANCE)
    if stack_height <= cap:
        # whole pallet fits at the face
        return int(round(cartons_per_pallet)), stack_height <= bay_height_mm

    # otherwise: only as many layers as fit
    layers_fitting = int(bay_height_mm // carton_h_mm)
    if layers_fitting <= 0:
        return 0, False
    return int(round(cartons_per_layer * layers_fitting)), False


def _replen_bench(
    upd: float, face_cartons: int, ipq: float,
) -> tuple[str, int, float]:
    """Bench-flow replen sized by days-of-cover at pick face."""
    if pd.isna(upd) or upd <= 0:
        return ("manual", 0, float("nan"))
    ipq = ipq if ipq and not pd.isna(ipq) and ipq > 0 else 1
    cartons_per_day = upd / ipq if ipq > 0 else upd
    if face_cartons <= 0 or cartons_per_day <= 0:
        return ("manual", 0, float("nan"))
    days = face_cartons / cartons_per_day
    if days < MIN_DAYS_COVER_AT_FACE:
        return ("fill_to_max", max(1, int(face_cartons * 0.3)), round(days, 1))
    if days <= MAX_DAYS_COVER_AT_FACE:
        return ("set_qty", max(1, int(face_cartons * 0.25)), round(days, 1))
    return ("set_qty", max(1, int(cartons_per_day * 2)), round(days, 1))


def _replen_bypass(upd: float, cpp: float) -> tuple[str, int, float]:
    """Bypass-flow replen in whole-pallet units."""
    if pd.isna(upd) or upd <= 0 or pd.isna(cpp) or cpp <= 0:
        return ("manual", 0, float("nan"))
    days_per_pallet = cpp / upd if upd > 0 else float("inf")
    trigger = max(1, int(cpp * 0.25))
    return ("whole_pallet", trigger, round(days_per_pallet, 1))


def recommend_slotting(
    sku_metrics: pd.DataFrame,
    dims: pd.DataFrame,
) -> SlottingResult:
    """Generate per-SKU recommendations using operator bay assignment + algo replen."""
    metrics = sku_metrics.copy()
    if metrics.index.name == "product_code":
        metrics = metrics.reset_index()

    dim_cols = [
        "product_code", "outer_l_mm", "outer_w_mm", "outer_h_mm",
        "outer_cube_mm3", "cartons_per_pallet", "cartons_per_layer",
        "inner_pack_qty", "measurement_complete", "pickbench",
        "pallet_height_bucket", "bay_height_mm",
    ]
    dim_cols = [c for c in dim_cols if c in dims.columns]
    dims_subset = dims[dim_cols].copy()
    if "pickbench" not in dims_subset.columns:
        dims_subset["pickbench"] = None
    if "bay_height_mm" not in dims_subset.columns:
        dims_subset["bay_height_mm"] = pd.NA
    if "pallet_height_bucket" not in dims_subset.columns:
        dims_subset["pallet_height_bucket"] = pd.NA

    merged = metrics.merge(dims_subset, on="product_code", how="left")

    rows = []
    no_bay_count = 0
    for _, r in merged.iterrows():
        complete = bool(r.get("measurement_complete"))
        abc = str(r.get("abc_class", "")) or "C"
        upd = float(r.get("units_per_day") or 0)
        pb = r.get("pickbench")
        if isinstance(pb, float) and pd.isna(pb):
            pb = None
        routing = _pickbench_label(pb)
        cpp_raw = r.get("cartons_per_pallet")
        cpp = float(cpp_raw) if not pd.isna(cpp_raw) else np.nan
        cube_l = (
            float(r["outer_cube_mm3"]) / 1_000_000
            if not pd.isna(r.get("outer_cube_mm3")) else np.nan
        )

        # Bay assigned by operator?
        bay_raw = r.get("bay_height_mm")
        operator_bay = (
            int(bay_raw) if not pd.isna(bay_raw) else None
        )
        bucket_raw = r.get("pallet_height_bucket")
        bucket = int(bucket_raw) if not pd.isna(bucket_raw) else None

        if not complete:
            rows.append({
                "product_code": r["product_code"],
                "product_name": r.get("product_name", ""),
                "abc_class": abc,
                "units_per_day": upd,
                "pickbench": pb,
                "routing": routing,
                "pallet_height_bucket": bucket,
                "bay_height_mm": operator_bay,
                "pick_face_cartons": None,
                "cartons_per_pallet": int(cpp) if not pd.isna(cpp) else None,
                "replen_strategy": "awaiting_dims",
                "replen_trigger_qty": None,
                "days_of_cover_at_face": None,
                "outer_cube_l": (
                    round(cube_l, 1) if not pd.isna(cube_l) else None
                ),
                "notes": "AWAITING DIMENSIONS",
            })
            continue

        if operator_bay is None:
            no_bay_count += 1
            rows.append({
                "product_code": r["product_code"],
                "product_name": r.get("product_name", ""),
                "abc_class": abc,
                "units_per_day": upd,
                "pickbench": pb,
                "routing": routing,
                "pallet_height_bucket": bucket,
                "bay_height_mm": None,
                "pick_face_cartons": None,
                "cartons_per_pallet": int(cpp) if not pd.isna(cpp) else None,
                "replen_strategy": "awaiting_bay",
                "replen_trigger_qty": None,
                "days_of_cover_at_face": None,
                "outer_cube_l": round(cube_l, 1) if not pd.isna(cube_l) else None,
                "notes": "AWAITING BAY ASSIGNMENT (Pallet height column)",
            })
            continue

        # Compute pick face + replen for this operator-assigned bay
        cartons_per_layer = r.get("cartons_per_layer")
        layers_per_pallet = r.get("layers_per_pallet")
        cpl = (
            cartons_per_layer if not pd.isna(cartons_per_layer) else np.nan
        )
        lpp = (
            float(layers_per_pallet)
            if not pd.isna(layers_per_pallet) else np.nan
        )

        # Pick face capacity: use the actual stack of cartons at the operator's
        # assigned bay. fits_cleanly=False means we had to drop layers because
        # the pallet's normal stack didn't fit the bay cap.
        face_cartons, fits_cleanly = _pick_face_cartons_at_position(
            cpp, lpp, r["outer_h_mm"], operator_bay,
        )
        stack_h = (
            float(r["outer_h_mm"]) * lpp if not pd.isna(lpp) else np.nan
        )

        if pb is False:
            # bypass: pick face is the pallet at this position; replen by pallet
            strat, trigger, days_cover = _replen_bypass(upd, cpp)
            note_bits = [f"{abc}-class bypass", f"bay {operator_bay}mm"]
            if not pd.isna(days_cover):
                note_bits.append(f"~{days_cover:.1f}d per pallet")
        else:
            # bench flow: replen by days-of-cover at face
            strat, trigger, days_cover = _replen_bench(
                upd, face_cartons, r.get("inner_pack_qty") or 1,
            )
            label = "bench" if pb is True else "bench(default)"
            note_bits = [f"{abc}-class {label}", f"bay {operator_bay}mm"]
            if not pd.isna(days_cover):
                note_bits.append(f"~{days_cover:.1f}d cover")
            if not pd.isna(cube_l) and cube_l > 40:
                note_bits.append("large cube")

        # Tight-fit flag: stack just barely fits or has to drop layers
        if not pd.isna(stack_h):
            if stack_h > operator_bay and stack_h <= operator_bay * (
                1.0 + STACK_FIT_TOLERANCE
            ):
                note_bits.append(
                    f"TIGHT FIT (stack {int(stack_h)}mm vs bay {operator_bay}mm)"
                )
            elif stack_h > operator_bay * (1.0 + STACK_FIT_TOLERANCE):
                note_bits.append(
                    f"OVERSIZED — only partial pallet fits "
                    f"(stack {int(stack_h)}mm vs bay {operator_bay}mm)"
                )
        notes = "; ".join(note_bits)

        rows.append({
            "product_code": r["product_code"],
            "product_name": r.get("product_name", ""),
            "abc_class": abc,
            "units_per_day": upd,
            "pickbench": pb,
            "routing": routing,
            "pallet_height_bucket": bucket,
            "bay_height_mm": operator_bay,
            "pick_face_cartons": face_cartons,
            "cartons_per_pallet": int(cpp) if not pd.isna(cpp) else None,
            "replen_strategy": strat,
            "replen_trigger_qty": trigger,
            "days_of_cover_at_face": days_cover,
            "outer_cube_l": round(cube_l, 1) if not pd.isna(cube_l) else None,
            "notes": notes,
        })

    rec = (
        pd.DataFrame(rows)
        .sort_values(
            ["routing", "bay_height_mm", "units_per_day"],
            ascending=[True, True, False],
            na_position="last",
        )
        .reset_index(drop=True)
    )

    measured = int(rec["bay_height_mm"].notna().sum())
    unmeasured = int(
        (rec["replen_strategy"] == "awaiting_dims").sum()
    )
    py = int((rec["pickbench"] == True).sum())  # noqa: E712
    pn = int((rec["pickbench"] == False).sum())  # noqa: E712
    pu = int(rec["pickbench"].isna().sum())

    log.info(
        "slotting recs: %d slotted / %d awaiting dims / %d awaiting bay assignment. "
        "Routing: %d bench-Y, %d bypass-N, %d unclassified",
        measured, unmeasured, no_bay_count, py, pn, pu,
    )

    return SlottingResult(
        recommendations=rec,
        measured_count=measured,
        unmeasured_count=unmeasured,
        no_bay_assignment_count=no_bay_count,
        pickbench_y_count=py,
        pickbench_n_count=pn,
        pickbench_unclassified_count=pu,
    )
