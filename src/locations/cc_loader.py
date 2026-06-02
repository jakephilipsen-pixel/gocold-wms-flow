"""Load CC's UI-exported warehouse locations xlsx into normalised data.

CC's UI export schema (observed May 2026):
  id, name, barcode, zone_name, capacity, row, bay, level, depth,
  product_type, efficiency, max_pallets, active, pick_order, charge_group

Truth sources:
  - PICK FACE STATUS:  CC's `efficiency >= 21` is authoritative.
  - POSITION (1/2/3):  our grammar parser (CC doesn't model this).
  - BAY HEIGHT (mm):   derived from position; advisory only.
  - PRODUCT TYPE:      CC's `product_type` is authoritative.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .grammar import classify_locations

log = logging.getLogger(__name__)


# Per CC docs, efficiency 21-30 = pick face range. In Forage's tenant:
#   30 = pick face (most common)
#   1, 15, 20 = reserve at various qualities
CC_PICK_FACE_MIN_EFFICIENCY = 21


# Aisle-specific overrides where CC's efficiency data is stale or where
# physical rack rules differ from the standard grammar.
#
# DO aisle (reorganised May 2026 per Jake):
#   - 20 bays × 4 levels
#   - Only `-01` is a pick face. `-02`, `-03`, `-04` are reserves.
#   - CC's efficiency=30 on `-03`/`-04` is stale (carried over from old layout).
# This override is applied AFTER the CC efficiency check, so it can demote
# locations that CC still flags as pick faces but physically aren't anymore.
AISLE_PICK_LEVEL_OVERRIDES: dict[str, set[int]] = {
    "DO": {1},  # only level 01 is a pick face in aisle DO
}


def load_cc_locations(path: Path) -> pd.DataFrame:
    """Load CC's exported locations xlsx; return a normalised master frame.

    Output columns:
        location_id           CC's internal id
        location_name         the location code/name string
        cc_product_type       DRY / CHILLED / AMBIENT / A-RK / etc.
        cc_efficiency         CC's pick efficiency 1-30
        is_pick_face          ★ AUTHORITATIVE — based on cc_efficiency >= 21
        cc_capacity           "Single Pallet" / "Multiple Pallets"
        cc_active             True / False
        cc_max_pallets        int
        cc_barcode            location barcode if any
        cc_zone_name          zone (typically null)
        ... plus grammar columns:
        valid                 grammar parse succeeded
        aisle, bay, level, sublevel
        is_split_bay
        position              1 / 2 / 3 (None if grammar can't determine)
        bay_height_mm         750 / 1100 / 1500 / None  (advisory)
        role_by_grammar       grammar-inferred role (advisory)
        parse_reason
    """
    df = pd.read_excel(path, sheet_name=0)

    needed = {"id", "name", "product_type", "efficiency", "active", "capacity"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(
            f"unexpected CC locations export schema. Missing cols: {sorted(missing)}. "
            f"Got: {list(df.columns)}"
        )

    base = pd.DataFrame({
        "location_id": df["id"],
        "location_name": df["name"].astype(str).str.strip(),
        "cc_product_type": df["product_type"],
        "cc_efficiency": pd.to_numeric(df["efficiency"], errors="coerce"),
        "cc_capacity": df["capacity"],
        "cc_max_pallets": pd.to_numeric(df.get("max_pallets"), errors="coerce"),
        "cc_active": df["active"].astype(str).str.strip().str.upper() == "YES",
        "cc_barcode": df.get("barcode"),
        "cc_zone_name": df.get("zone_name"),
    })

    # Authoritative pick-face flag from CC efficiency
    base["is_pick_face"] = (
        base["cc_efficiency"] >= CC_PICK_FACE_MIN_EFFICIENCY
    )

    # Parse names through grammar for position + advisory info
    grammar_df = classify_locations(base["location_name"].tolist())
    # we already have location_name in base; drop grammar's copy
    grammar_df = grammar_df.drop(columns=["location_name"])

    out = pd.concat(
        [base.reset_index(drop=True), grammar_df.reset_index(drop=True)],
        axis=1,
    )

    # Apply aisle-specific pick-face overrides for cases where CC data is
    # stale or physical rules differ from standard grammar.
    for aisle, allowed_levels in AISLE_PICK_LEVEL_OVERRIDES.items():
        mask = (out["aisle"] == aisle) & out["valid"]
        # demote anything in this aisle whose level isn't in the allowed set
        demote = mask & ~out["level"].isin(allowed_levels)
        n_demoted = int((demote & out["is_pick_face"]).sum())
        if n_demoted:
            log.warning(
                "aisle %s override: demoting %d locations from pick-face to "
                "reserve (CC data was stale)", aisle, n_demoted,
            )
        out.loc[demote, "is_pick_face"] = False

    # For non-pick-face locations, blank the position/height (grammar may have
    # guessed pick-face for them e.g. DJ-01-02 in split aisle, but CC says no).
    not_pick = ~out["is_pick_face"]
    out.loc[not_pick, "position"] = pd.NA
    out.loc[not_pick, "bay_height_mm"] = pd.NA

    log.info(
        "loaded %d CC locations: %d pick faces (CC eff >= %d), %d reserve/other",
        len(out), int(out["is_pick_face"].sum()),
        CC_PICK_FACE_MIN_EFFICIENCY,
        int((~out["is_pick_face"]).sum()),
    )
    log.info(
        "grammar parse: %d valid XX-NN-NN[-NN], %d special-purpose names",
        int(out["valid"].sum()), int((~out["valid"]).sum()),
    )

    return out
