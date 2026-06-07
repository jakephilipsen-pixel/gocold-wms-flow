"""Full-pallet SO line detection + cleaned velocity computation.

The problem: brands like TC (chocolate) sometimes ship a complete pallet to
a single customer in one SO line. A 480-carton line of TC-MCS isn't a
"pick velocity" signal — it's a one-shot full-pallet build that should
bypass the pick bench entirely. Counting it as velocity makes TC look like
a top-runner when in reality it almost never hits the pick face.

We flag those lines and provide a "cleaned" velocity recompute that
excludes them. We KEEP them visible in a separate per-line table so they
feed the dispatch / direct-to-pallet planning logic downstream.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from .loaders import Snapshot
from .velocity import VelocityResult, compute_velocity

log = logging.getLogger(__name__)

# A line is "full pallet" if it ships at least this fraction of a full pallet.
# 0.9 is conservative — only catches near-full or full pallets. Tune later.
DEFAULT_FULL_PALLET_RATIO = 0.9


@dataclass
class FullPalletAnalysis:
    flagged_so_lines: pd.DataFrame      # SO lines flagged as full-pallet bypass
    summary_by_sku: pd.DataFrame        # per SKU: how many full-pallet shipments
    cleaned_velocity: VelocityResult    # velocity recomputed without these lines
    ratio_used: float
    n_flagged: int


def detect_full_pallet_lines(
    snap: Snapshot,
    dims: pd.DataFrame,
    tagged_metrics: pd.DataFrame,
    ratio: float = DEFAULT_FULL_PALLET_RATIO,
    require_full_pallet_brand: bool = True,
) -> pd.DataFrame:
    """Flag SO lines where qty >= ratio * cartons_per_pallet.

    If require_full_pallet_brand=True, only flag lines whose SKU brand is in
    the FULL_PALLET_BRANDS set. This stops us accidentally excluding genuine
    high-volume non-pallet picks (e.g. a big customer regularly buying 100
    cartons of a fast mover).

    Returns the original SO line rows with extra columns:
        cartons_per_pallet, pallet_fraction, is_full_pallet_line
    """
    so = snap.so_lines.copy()
    so["quantity"] = pd.to_numeric(so["quantity"], errors="coerce").fillna(0)

    # join cartons_per_pallet from dims, brand from tagged_metrics
    dims_lookup = dims.set_index("product_code")[["cartons_per_pallet"]]
    so = so.merge(
        dims_lookup,
        left_on="product_code",
        right_index=True,
        how="left",
    )

    brand_lookup = tagged_metrics[["brand", "is_full_pallet_brand"]] \
        if "brand" in tagged_metrics.columns else None
    if brand_lookup is not None:
        so = so.merge(
            brand_lookup,
            left_on="product_code",
            right_index=True,
            how="left",
        )
    else:
        so["brand"] = ""
        so["is_full_pallet_brand"] = False

    so["pallet_fraction"] = so["quantity"] / so["cartons_per_pallet"]
    qty_meets = so["pallet_fraction"] >= ratio
    if require_full_pallet_brand:
        so["is_full_pallet_line"] = qty_meets & so["is_full_pallet_brand"].fillna(False)
    else:
        so["is_full_pallet_line"] = qty_meets.fillna(False)

    return so


def summarise_full_pallet_by_sku(flagged_so: pd.DataFrame) -> pd.DataFrame:
    """One row per SKU: how many full-pallet shipments, total qty, % of qty."""
    grouped = flagged_so.groupby("product_code")
    summary = grouped.agg(
        total_qty=("quantity", "sum"),
        total_lines=("so_id", "size"),
        cartons_per_pallet=("cartons_per_pallet", "first"),
        brand=("brand", "first"),
    )
    full_pallet_grouped = (
        flagged_so[flagged_so["is_full_pallet_line"]]
        .groupby("product_code")
        .agg(
            full_pallet_lines=("so_id", "size"),
            full_pallet_qty=("quantity", "sum"),
        )
    )
    summary = summary.join(full_pallet_grouped, how="left").fillna(
        {"full_pallet_lines": 0, "full_pallet_qty": 0}
    )
    summary["full_pallet_lines"] = summary["full_pallet_lines"].astype(int)
    summary["pct_qty_via_full_pallet"] = (
        summary["full_pallet_qty"] / summary["total_qty"] * 100
    ).round(1)
    return summary.sort_values("full_pallet_qty", ascending=False)


def recompute_velocity_excluding_full_pallets(
    snap: Snapshot,
    flagged_so: pd.DataFrame,
) -> VelocityResult:
    """Build a new VelocityResult with full-pallet lines removed from SO data."""
    keep_so = flagged_so[~flagged_so["is_full_pallet_line"]].copy()
    keep_so = keep_so[snap.so_lines.columns]  # drop the joined extras
    clean_snap = Snapshot(
        so_lines=keep_so,
        po_lines=snap.po_lines,
        products=snap.products,
        so_path=snap.so_path,
        po_path=snap.po_path,
        products_path=snap.products_path,
    )
    return compute_velocity(clean_snap)


def run_full_pallet_analysis(
    snap: Snapshot,
    dims: pd.DataFrame,
    tagged_metrics: pd.DataFrame,
    ratio: float = DEFAULT_FULL_PALLET_RATIO,
) -> FullPalletAnalysis:
    """Detect full-pallet SO lines and produce a cleaned velocity result."""
    flagged = detect_full_pallet_lines(
        snap, dims, tagged_metrics, ratio=ratio,
    )
    n_flagged = int(flagged["is_full_pallet_line"].sum())
    log.info(
        "flagged %d/%d SO lines as full-pallet bypass (ratio >= %.2f)",
        n_flagged, len(flagged), ratio,
    )

    summary = summarise_full_pallet_by_sku(flagged)
    cleaned = recompute_velocity_excluding_full_pallets(snap, flagged)

    return FullPalletAnalysis(
        flagged_so_lines=flagged[flagged["is_full_pallet_line"]].copy(),
        summary_by_sku=summary,
        cleaned_velocity=cleaned,
        ratio_used=ratio,
        n_flagged=n_flagged,
    )
