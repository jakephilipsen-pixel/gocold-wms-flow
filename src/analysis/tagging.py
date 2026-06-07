"""Auto-tag SKUs by brand + format, supporting manual override via Tag column.

The goal is to derive *structural* tags from existing data (so we don't ask
the warehouse team to enter information that's already in the product code
or name), while leaving a Tag column for *behavioural* overrides (e.g.
"this brand ships as full pallets to specific customers", "this is seasonal").

Derived columns:
    brand        : product code prefix before first '-'  (RK, FT, PC, TC, AE, ...)
    format       : 'BOTTLE' / 'MULTI' / 'CAN' / 'PET' / 'SHOT' / 'LARGE' / 'SMALL'
                   / 'SMALL_BATCH' / etc, parsed from name keywords
    size_category: 'small' / 'medium' / 'large' / 'oversized', from carton cube

Per-SKU behaviour tags (manual or default):
    is_full_pallet_brand : true if brand is known to ship as full pallets
                           (e.g. TC chocolate) — used to filter velocity calc
"""
from __future__ import annotations

import logging
import re

import pandas as pd

log = logging.getLogger(__name__)

# Brand prefixes that we *know* ship as full-pallet orders.
# These are excluded from per-SKU velocity calculation when the shipped qty
# is close to a full pallet (handled in patterns.py).
# Source: Jake (Go Cold ops), May 2026.
FULL_PALLET_BRANDS = {
    "TC",  # chocolate; high inbound, full-pallet outbound to specific customers
}

# Format keywords found in product names. Order matters: more-specific first.
# Returns the first matching tag for each name.
_FORMAT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("SMALL_BATCH", re.compile(r"\*\s*SMALL\s*BATCH\s*\*", re.I)),
    ("BIG_CUT",     re.compile(r"BIG\s*CUT", re.I)),
    ("BOTTLE",      re.compile(r"\*\s*BOTTLE\s*\*", re.I)),
    ("MULTI",       re.compile(r"\*\s*MULTI\s*\*", re.I)),
    ("CAN",         re.compile(r"\*\s*CAN\s*\*", re.I)),
    ("PET",         re.compile(r"\*\s*PET\s*\*", re.I)),
    ("SHOT",        re.compile(r"\*\s*SHOT\s*\*", re.I)),
    ("LARGE",       re.compile(r"\*\s*LARGE\s*\*", re.I)),
    ("SMALL",       re.compile(r"\*\s*SMALL\s*\*", re.I)),
]


def _derive_brand(product_code: object) -> str:
    if not isinstance(product_code, str):
        return ""
    code = product_code.strip()
    if "-" not in code:
        return code  # no separator; whole code is the brand
    return code.split("-", 1)[0].upper()


def _derive_format(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""
    for tag, pat in _FORMAT_PATTERNS:
        if pat.search(name):
            return tag
    return ""


def _derive_size_category(cube_mm3: object) -> str:
    """Bucket carton cube into size categories. Thresholds chosen for the
    Forage range (mostly drinks + crisps + crackers). Easy to retune.

    small      : < 10 L of cube (e.g. shot multipack)
    medium     : 10-25 L  (typical drink multi)
    large      : 25-50 L  (large crisp box, big drink case)
    oversized  : > 50 L   (unusual, manual handling territory)
    """
    if not isinstance(cube_mm3, (int, float)) or pd.isna(cube_mm3) or cube_mm3 <= 0:
        return ""
    litres = cube_mm3 / 1_000_000.0
    if litres < 10:
        return "small"
    if litres < 25:
        return "medium"
    if litres < 50:
        return "large"
    return "oversized"


def apply_tags(
    sku_metrics: pd.DataFrame,
    dims: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach derived brand/format/size tags + full-pallet flag to sku_metrics.

    sku_metrics: per-SKU metrics frame (index = product_code).
    dims:        optional dims frame (from dim_loader); if provided we derive
                 size_category from carton cube and merge the manual Tag.

    Returns a new DataFrame; does not mutate the input.
    """
    out = sku_metrics.copy()
    # ensure product_code is accessible whether it's index or column
    if out.index.name == "product_code" or "product_code" not in out.columns:
        codes = out.index.to_series()
    else:
        codes = out["product_code"]

    out["brand"] = codes.map(_derive_brand)
    out["format"] = out["product_name"].map(_derive_format) if "product_name" in out.columns else ""
    out["is_full_pallet_brand"] = out["brand"].isin(FULL_PALLET_BRANDS)

    if dims is not None and not dims.empty:
        dims_idx = dims.set_index("product_code")
        # size_category from cube
        size_cat = dims_idx["outer_cube_mm3"].map(_derive_size_category)
        out = out.join(size_cat.rename("size_category"), how="left")
        out["size_category"] = out["size_category"].fillna("")
        # manual tag column
        if "tag" in dims_idx.columns:
            out = out.join(dims_idx["tag"].rename("manual_tag"), how="left")
            out["manual_tag"] = out["manual_tag"].fillna("")
        else:
            out["manual_tag"] = ""
    else:
        out["size_category"] = ""
        out["manual_tag"] = ""

    n_full_pallet = int(out["is_full_pallet_brand"].sum())
    log.info(
        "tags applied: %d SKUs, %d in full-pallet brands (%s)",
        len(out), n_full_pallet, ", ".join(sorted(FULL_PALLET_BRANDS)),
    )
    return out
