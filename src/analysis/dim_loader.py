"""Load filled-in carton-dimension capture templates back into structured data.

Supports two template versions:
  v1 (May 2026, original): cols include "Outer Carton Qty", "Pickbench (Y/N)",
       "Pallet TI x HI", "Notes" with "X layers per pallet" inside notes
  v2 (May 2026, updated):  cols include "Outer Carton Qty per pallet",
       "Pickbench for repack (Y/N)", "Pallet height 1, 2 or 3" (operator
       bay assignment), "layers per pallet" as a dedicated column

Returns one normalised DataFrame regardless of template version.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Pickbench routing values (case-insensitive, whitespace-trimmed).
_PICKBENCH_YES = {"Y", "YES", "TRUE", "1"}
_PICKBENCH_NO = {"N", "NO", "FALSE", "0"}

# Regexes for parsing free-text fields
_LAYERS_RE = re.compile(r"(\d+)\s*layers?\s*per\s*pallet", re.IGNORECASE)
_TIHI_RE = re.compile(r"^\s*(\d+)\s*[x×*]\s*(\d+)\s*$", re.IGNORECASE)

# Operator-defined pallet height bucket → maximum stack height in millimetres.
# The physical rack has two configs:
#   Config A (pos 3): single full-height bay, floor to 1500mm beam, single pallet.
#   Config B (pos 1+2): split bay with a beam at 800mm. Pos 1 sits on floor up to
#       800mm; pos 2's pallet sits ON the 800mm beam with 1100mm of locked stack
#       height above (next beam is at 3000mm but the 1100mm cap is enforced by
#       operator process, not by structure).
# Source: Jake (Go Cold ops), May 2026.
PALLET_HEIGHT_TO_BAY_MM = {1: 800, 2: 1100, 3: 1500}


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first column name from `candidates` present in df."""
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        match = cols_lower.get(cand.lower().strip())
        if match is not None:
            return match
    return None


def _parse_layers_from_value(raw: object) -> int | None:
    """Pull layer count from a single value that may be int, "N", "N layers per pallet", etc."""
    if pd.isna(raw):
        return None
    s = str(raw).strip()
    if not s:
        return None
    # plain int?
    try:
        n = int(float(s))
        if 1 <= n <= 50:
            return n
    except (ValueError, TypeError):
        pass
    # regex match on "N layers per pallet"
    m = _LAYERS_RE.search(s)
    if m:
        return int(m.group(1))
    return None


def _parse_ti(ti_hi: object) -> int | None:
    """Pull TI (base cartons per layer) from a 'TI x HI' string."""
    if pd.isna(ti_hi):
        return None
    m = _TIHI_RE.match(str(ti_hi))
    return int(m.group(1)) if m else None


def _parse_pickbench(raw: object) -> bool | None:
    """Parse pickbench Y/N column. True/False/None."""
    if pd.isna(raw):
        return None
    val = str(raw).strip().upper()
    if not val:
        return None
    if val in _PICKBENCH_YES:
        return True
    if val in _PICKBENCH_NO:
        return False
    log.warning("unrecognised pickbench value %r — treating as unclassified", raw)
    return None


def _parse_pallet_height_bucket(raw: object) -> int | None:
    """Parse the 1/2/3 operator height bucket."""
    if pd.isna(raw):
        return None
    try:
        n = int(float(str(raw).strip()))
        if n in (1, 2, 3):
            return n
    except (ValueError, TypeError):
        pass
    return None


def load_dimensions(path: Path) -> pd.DataFrame:
    """Load capture template; return normalised per-SKU dimension data.

    Output columns:
        product_code, outer_l_mm, outer_w_mm, outer_h_mm, outer_weight_kg,
        inner_pack_qty, cartons_per_pallet, layers_per_pallet, cartons_per_layer,
        outer_cube_mm3, pickbench, pallet_height_bucket, bay_height_mm,
        tag, measured_by, date_measured, measurement_complete
    """
    df = pd.read_excel(path, sheet_name="SKU Capture", header=3)
    df = df[df["Product Code"].notna()].copy()

    # Resolve column names (tolerate v1/v2 templates)
    col_l = _find_col(df, "Outer L (mm)")
    col_w = _find_col(df, "Outer W (mm)")
    col_h = _find_col(df, "Outer H (mm)")
    col_weight = _find_col(df, "Outer Weight (kg)")
    col_inner = _find_col(df, "Inner Pack Qty")
    col_cpp = _find_col(
        df, "Outer Carton Qty per pallet", "Outer Carton Qty",
    )
    col_layers = _find_col(df, "layers per pallet", "Layers Per Pallet")
    col_tihi = _find_col(df, "Pallet TI x HI")
    col_height_bucket = _find_col(
        df, "Pallet height 1, 2 or 3", "Pallet Height", "Pallet Height Bucket",
    )
    col_pickbench = _find_col(
        df, "Pickbench for repack (Y/N)", "Pickbench (Y/N)", "Pickbench",
    )
    col_tag = _find_col(df, "Tag")
    col_notes = _find_col(df, "Notes")
    col_measured_by = _find_col(df, "Measured By")
    col_date = _find_col(df, "Date Measured")

    required = {"L": col_l, "W": col_w, "H": col_h, "cartons-per-pallet": col_cpp}
    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise ValueError(
            f"capture template missing required columns: {missing}. "
            f"got: {list(df.columns)}"
        )

    out = pd.DataFrame({
        "product_code": df["Product Code"].astype(str).str.strip(),
        "outer_l_mm": pd.to_numeric(df[col_l], errors="coerce"),
        "outer_w_mm": pd.to_numeric(df[col_w], errors="coerce"),
        "outer_h_mm": pd.to_numeric(df[col_h], errors="coerce"),
        "outer_weight_kg": pd.to_numeric(df[col_weight], errors="coerce") if col_weight else pd.NA,
        "inner_pack_qty": pd.to_numeric(df[col_inner], errors="coerce") if col_inner else pd.NA,
        "cartons_per_pallet": pd.to_numeric(df[col_cpp], errors="coerce"),
    })

    # layers_per_pallet: prefer dedicated column, else parse from Notes, else from TI x HI
    if col_layers:
        out["layers_per_pallet"] = [
            _parse_layers_from_value(v) for v in df[col_layers]
        ]
    elif col_notes:
        out["layers_per_pallet"] = [
            _parse_layers_from_value(v) for v in df[col_notes]
        ]
    elif col_tihi:
        # legacy: TI x HI → HI is the layer count
        out["layers_per_pallet"] = [
            (_TIHI_RE.match(str(v)).group(2) if pd.notna(v) and _TIHI_RE.match(str(v)) else None)
            for v in df[col_tihi]
        ]
        out["layers_per_pallet"] = pd.to_numeric(
            out["layers_per_pallet"], errors="coerce"
        ).astype("Int64")
    else:
        out["layers_per_pallet"] = pd.NA

    out["ti_base_count"] = (
        [_parse_ti(v) for v in df[col_tihi]] if col_tihi else None
    )

    out["cartons_per_layer"] = (
        out["cartons_per_pallet"] / out["layers_per_pallet"]
    ).round().astype("Int64")

    out["outer_cube_mm3"] = (
        out["outer_l_mm"] * out["outer_w_mm"] * out["outer_h_mm"]
    )

    # pickbench routing
    if col_pickbench:
        out["pickbench"] = df[col_pickbench].map(_parse_pickbench)
    else:
        out["pickbench"] = None

    # operator-assigned pallet height bucket → bay height
    if col_height_bucket:
        out["pallet_height_bucket"] = df[col_height_bucket].map(
            _parse_pallet_height_bucket
        )
        out["bay_height_mm"] = out["pallet_height_bucket"].map(
            PALLET_HEIGHT_TO_BAY_MM
        ).astype("Int64")
    else:
        out["pallet_height_bucket"] = pd.NA
        out["bay_height_mm"] = pd.NA

    # tag (manual override / grouping)
    if col_tag:
        out["tag"] = df[col_tag].astype(str).str.strip().replace(
            {"nan": "", "None": ""}
        )
    else:
        out["tag"] = ""

    out["measured_by"] = (
        df[col_measured_by].astype(str).str.strip().replace({"nan": ""})
        if col_measured_by else ""
    )
    out["date_measured"] = (
        pd.to_datetime(df[col_date], errors="coerce")
        if col_date else pd.NaT
    )

    out["measurement_complete"] = (
        out["outer_l_mm"].notna()
        & out["outer_w_mm"].notna()
        & out["outer_h_mm"].notna()
        & out["cartons_per_pallet"].notna()
    )

    out = out.reset_index(drop=True)

    # stats
    n_complete = int(out["measurement_complete"].sum())
    n_pb_y = int((out["pickbench"] == True).sum())  # noqa: E712
    n_pb_n = int((out["pickbench"] == False).sum())  # noqa: E712
    n_pb_blank = int(out["pickbench"].isna().sum())
    n_height_assigned = int(out["pallet_height_bucket"].notna().sum())
    log.info(
        "loaded dims for %d SKUs from %s (%d fully measured, %d partial/empty)",
        len(out), path.name, n_complete, len(out) - n_complete,
    )
    log.info(
        "pickbench routing: %d Y / %d N / %d unclassified",
        n_pb_y, n_pb_n, n_pb_blank,
    )
    log.info(
        "operator-assigned bay heights: %d/%d SKUs (rest will await assignment)",
        n_height_assigned, len(out),
    )
    return out
