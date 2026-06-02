"""Assign measured SKUs to specific warehouse locations.

Inputs:
    sku_metrics  : per-SKU velocity (cleaned, with tags applied)
    dims         : per-SKU dimensions + pickbench routing + operator-assigned
                   pallet_height_bucket (1/2/3)
    locations    : CC location master with is_pick_face, cc_product_type,
                   aisle, bay, level, position, etc.

Output:
    AssignmentResult.assignments  : one row per SKU with assigned location
    AssignmentResult.coverage     : supply vs demand by (product_type, position)
    AssignmentResult.unassigned   : SKUs we couldn't place + reason
    AssignmentResult.unused       : pick faces that didn't get a SKU

Strategy:
    1. Build a "demand table": for each measured SKU, what's required —
         required_product_type (DRY / CHILLED / AMBIENT / etc.)
         required_position     (1, 2, or 3 per operator assignment)
    2. Build a "supply pool" of available pick faces grouped by
         (product_type, position).
    3. Sort demand by units_per_day desc — highest-velocity SKUs assigned
       first (they get first pick of available pick faces).
    4. For each SKU, take a pick face from its matching pool. If pool is
       empty, record as unassigned with reason "no supply".

This is a SIMPLE greedy assignment. Sophisticated WMS slotting also
considers aisle adjacency (zone runs), pick path optimisation, etc. We
do the basic match first; refinements come later if needed.

Product type inference (which CC zone a SKU lives in):
    Forage SKUs split across DRY / CHILLED / AMBIENT / A-RK. We use:
      - 'A-RK' for RK-prefix SKUs (their dedicated zone)
      - dim file Notes or product name keywords for chilled/frozen
      - default DRY otherwise
    The user can override via the manual_tag column.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

log = logging.getLogger(__name__)


# Product-type inference rules from product_name / brand.
# Most accurate signal we have without operator confirmation.
_CHILLED_KEYWORDS = ("CHILLED", "REFRIG", "DAIRY")
_FROZEN_KEYWORDS = ("FROZEN",)
_AMBIENT_KEYWORDS = ("AMBIENT",)


def _infer_product_type(brand: str, name: str, manual_tag: str = "") -> str:
    """Return CC product type ('DRY' / 'CHILLED' / 'AMBIENT' / 'A-RK' / 'FROZEN').

    Manual tag overrides everything. Then brand RK → A-RK (dedicated zone).
    Then keywords in product name. Default DRY.
    """
    tag = (manual_tag or "").strip().upper()
    if tag in ("CHILLED", "FROZEN", "AMBIENT", "DRY", "A-RK"):
        return tag

    if (brand or "").upper() == "RK":
        return "A-RK"

    name_up = (name or "").upper()
    if any(k in name_up for k in _CHILLED_KEYWORDS):
        return "CHILLED"
    if any(k in name_up for k in _FROZEN_KEYWORDS):
        return "FROZEN"
    if any(k in name_up for k in _AMBIENT_KEYWORDS):
        return "AMBIENT"

    return "DRY"


@dataclass
class AssignmentResult:
    assignments: pd.DataFrame  # SKU → location with all context
    coverage: pd.DataFrame     # supply vs demand by (product_type, position)
    unassigned: pd.DataFrame   # SKUs we couldn't place
    unused: pd.DataFrame       # pick faces with no SKU assigned


def assign_skus_to_locations(
    sku_metrics: pd.DataFrame,
    dims: pd.DataFrame,
    locations: pd.DataFrame,
) -> AssignmentResult:
    """Match each measured SKU to a specific pick-face location."""
    metrics = sku_metrics.copy()
    if metrics.index.name == "product_code":
        metrics = metrics.reset_index()

    # --- build the demand table
    dim_cols = [
        "product_code", "pickbench", "pallet_height_bucket",
        "tag",  # manual tag if set
        "outer_l_mm", "outer_w_mm", "outer_h_mm", "cartons_per_pallet",
        "measurement_complete",
    ]
    dim_cols = [c for c in dim_cols if c in dims.columns]
    dims_subset = dims[dim_cols].copy()
    if "tag" not in dims_subset.columns:
        dims_subset["tag"] = ""

    demand = metrics.merge(dims_subset, on="product_code", how="inner")

    # Only assign SKUs with full measurement + assigned position
    demand = demand[
        demand["measurement_complete"]
        & demand["pallet_height_bucket"].notna()
    ].copy()

    if demand.empty:
        log.warning("no demand to assign (no measured SKUs with position)")
        return AssignmentResult(
            assignments=pd.DataFrame(),
            coverage=pd.DataFrame(),
            unassigned=pd.DataFrame(),
            unused=locations[locations["is_pick_face"]].copy(),
        )

    # Infer product_type per SKU
    demand["required_product_type"] = [
        _infer_product_type(b, n, t)
        for b, n, t in zip(
            demand.get("brand", ""),
            demand.get("product_name", ""),
            demand["tag"],
        )
    ]
    demand["required_position"] = demand["pallet_height_bucket"].astype(int)

    # Sort by velocity desc — fastest movers get first pick of locations
    demand = demand.sort_values("units_per_day", ascending=False).reset_index(drop=True)

    # --- build the supply pool: pick faces by (product_type, position)
    pf = locations[locations["is_pick_face"]].copy()
    # need a position; without it we can't match. Use grammar's position.
    pf = pf[pf["position"].notna()].copy()
    pf["position"] = pf["position"].astype(int)

    # Pool is consumed in aisle order (alphabetical) then bay number — gives
    # deterministic, sensible "fill from the front" behaviour.
    pf = pf.sort_values(["cc_product_type", "position", "aisle", "bay"]).reset_index(drop=True)
    pf["_assigned_to"] = None
    pool_idx = {
        (ptype, pos): list(group.index)
        for (ptype, pos), group in pf.groupby(["cc_product_type", "position"])
    }

    # --- greedy assignment
    assignments_rows = []
    unassigned_rows = []
    for _, sku in demand.iterrows():
        ptype = sku["required_product_type"]
        pos = sku["required_position"]
        key = (ptype, pos)

        pool = pool_idx.get(key, [])
        if not pool:
            unassigned_rows.append({
                "product_code": sku["product_code"],
                "product_name": sku.get("product_name", ""),
                "brand": sku.get("brand", ""),
                "units_per_day": sku.get("units_per_day", 0),
                "required_product_type": ptype,
                "required_position": pos,
                "reason": f"no pick faces available for ({ptype}, position {pos})",
            })
            continue

        # take the first available pick face from the pool
        loc_idx = pool.pop(0)
        pf.at[loc_idx, "_assigned_to"] = sku["product_code"]
        loc_row = pf.loc[loc_idx]

        assignments_rows.append({
            "product_code": sku["product_code"],
            "product_name": sku.get("product_name", ""),
            "brand": sku.get("brand", ""),
            "abc_class": sku.get("abc_class", ""),
            "units_per_day": float(sku.get("units_per_day", 0)),
            "pickbench": sku.get("pickbench"),
            "required_product_type": ptype,
            "required_position": pos,
            "assigned_location": loc_row["location_name"],
            "aisle": loc_row["aisle"],
            "bay": int(loc_row["bay"]) if pd.notna(loc_row["bay"]) else None,
            "level": int(loc_row["level"]) if pd.notna(loc_row["level"]) else None,
            "sublevel": (
                int(loc_row["sublevel"]) if pd.notna(loc_row["sublevel"]) else None
            ),
            "bay_height_mm": (
                int(loc_row["bay_height_mm"])
                if pd.notna(loc_row["bay_height_mm"]) else None
            ),
            "cc_location_id": loc_row["location_id"],
            "cartons_per_pallet": (
                int(sku["cartons_per_pallet"])
                if pd.notna(sku["cartons_per_pallet"]) else None
            ),
        })

    assignments = pd.DataFrame(assignments_rows)
    unassigned = pd.DataFrame(unassigned_rows)

    # --- coverage report
    demand_grp = demand.groupby(
        ["required_product_type", "required_position"]
    ).size().rename("demand_skus").reset_index()
    supply_grp = pf.groupby(
        ["cc_product_type", "position"]
    ).size().rename("supply_pick_faces").reset_index()
    supply_grp = supply_grp.rename(columns={
        "cc_product_type": "required_product_type",
        "position": "required_position",
    })
    coverage = supply_grp.merge(
        demand_grp, on=["required_product_type", "required_position"], how="outer"
    ).fillna(0)
    coverage["supply_pick_faces"] = coverage["supply_pick_faces"].astype(int)
    coverage["demand_skus"] = coverage["demand_skus"].astype(int)
    coverage["surplus_or_deficit"] = (
        coverage["supply_pick_faces"] - coverage["demand_skus"]
    )
    coverage = coverage.sort_values(
        ["required_product_type", "required_position"],
    ).reset_index(drop=True)

    # --- unused pick faces
    unused = pf[pf["_assigned_to"].isna()].copy()
    unused = unused[[
        "location_name", "cc_product_type", "aisle", "bay", "level", "sublevel",
        "position", "bay_height_mm", "cc_efficiency",
    ]].sort_values(["cc_product_type", "position", "aisle", "bay"]).reset_index(drop=True)

    log.info(
        "assignment complete: %d SKUs assigned, %d unassigned, "
        "%d pick faces unused (out of %d total pick faces)",
        len(assignments), len(unassigned), len(unused), len(pf),
    )

    return AssignmentResult(
        assignments=assignments,
        coverage=coverage,
        unassigned=unassigned,
        unused=unused,
    )
