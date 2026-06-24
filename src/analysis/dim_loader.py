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
    """Resolve a column name tolerantly across template revisions.

    Operators hand-edit these capture-sheet headers between captures (e.g.
    "Inner Pack Qty" became "Inner Pack Qty per outer", and "Outer Carton
    Qty per pallet" picked up a "...for putawsay" suffix). We match in two
    widening tiers so trailing descriptive text doesn't break the loader:
      1. exact (case-insensitive, trimmed)
      2. header *starts with* a candidate (tolerates trailing notes)
    Candidates are tried in order; within a tier, the first column (in sheet
    order) to match wins. Prefix matching only runs when no exact match
    exists, so well-formed templates are unaffected.
    """
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    # tier 1: exact
    for cand in candidates:
        match = cols_lower.get(cand.lower().strip())
        if match is not None:
            return match
    # tier 2: prefix (header begins with the candidate)
    for cand in candidates:
        needle = cand.lower().strip()
        for low, orig in cols_lower.items():
            if low.startswith(needle):
                return orig
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


# Logical output column -> ordered candidate headers (tolerant exact->prefix match). The single
# source of truth for column resolution, shared by load_dimensions and the preflight validator so
# the validator reports the SAME mapping the write path actually reads.
CAPTURE_COLUMN_CANDIDATES: dict[str, tuple[str, ...]] = {
    "outer_l_mm": ("Each L (mm)", "Outer L (mm)"),
    "outer_w_mm": ("Each W (mm)", "Outer W (mm)"),
    "outer_h_mm": ("Each H (mm)", "Outer H (mm)"),
    "outer_weight_kg": ("Each Weight (kg)", "Outer Weight (kg)"),
    "inner_pack_qty": ("Inner Pack Qty",),
    "cartons_per_pallet": ("CT Qty per pallet", "Outer Carton Qty per pallet", "Outer Carton Qty"),
    # observed June-2026 template carries the operator's "leyers" typo:
    "layers_per_pallet": ("layers per pallet", "Layers Per Pallet",
                          "total leyers per pallet", "total layers per pallet"),
    "pallet_tihi": ("Pallet TI x HI",),
    "pallet_height_bucket": ("Pallet height 1, 2 or 3", "Pallet Height", "Pallet Height Bucket"),
    "pickbench": ("Pickbench for repack (Y/N)", "Pickbench (Y/N)", "Pickbench"),
    "tag": ("Tag",),
    "notes": ("Notes",),
    "measured_by": ("Measured By",),
    "date_measured": ("Date Measured",),
}

# The logical columns load_dimensions hard-requires (their absence raises). L/W/H drive the write;
# cartons-per-pallet drives slotting — a sheet without them is unusable, so the loader refuses it.
REQUIRED_CAPTURE_COLUMNS: tuple[str, ...] = (
    "outer_l_mm", "outer_w_mm", "outer_h_mm", "cartons_per_pallet",
)


def read_capture_sheet(path: Path) -> pd.DataFrame:
    """Read the raw 'SKU Capture' sheet (header on row 4), keeping only rows with a Product Code.

    The single entry point both ``load_dimensions`` and the read-only preflight validator use, so
    they see exactly the same rows — no conversion, no column resolution, just the raw frame.
    """
    df = pd.read_excel(path, sheet_name="SKU Capture", header=3)
    return df[df["Product Code"].notna()].copy()


def resolve_capture_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """Map each logical capture column to the actual sheet header (tolerant), or None if absent.

    Wraps ``_find_col`` over ``CAPTURE_COLUMN_CANDIDATES`` once, so ``load_dimensions`` and the
    preflight ``capture_validate`` tool resolve columns identically.
    """
    return {logical: _find_col(df, *cands) for logical, cands in CAPTURE_COLUMN_CANDIDATES.items()}


def load_dimensions(path: Path) -> pd.DataFrame:
    """Load capture template; return normalised per-SKU dimension data.

    Output columns:
        product_code, outer_l_mm, outer_w_mm, outer_h_mm, outer_weight_kg,
        inner_pack_qty, cartons_per_pallet, layers_per_pallet, cartons_per_layer,
        outer_cube_mm3, pickbench, pallet_height_bucket, bay_height_mm,
        tag, measured_by, date_measured, measurement_complete
    """
    df = read_capture_sheet(path)

    # Resolve column names from the single shared candidate table (tolerates v1/v2 templates and
    # the Jun-2026 each-rework), so the preflight validator reports the same mapping. Still mm —
    # values are divided to metres at the CC write boundary, not here.
    cols = resolve_capture_columns(df)
    col_l = cols["outer_l_mm"]
    col_w = cols["outer_w_mm"]
    col_h = cols["outer_h_mm"]
    col_weight = cols["outer_weight_kg"]
    col_inner = cols["inner_pack_qty"]
    col_cpp = cols["cartons_per_pallet"]
    col_layers = cols["layers_per_pallet"]
    col_tihi = cols["pallet_tihi"]
    col_height_bucket = cols["pallet_height_bucket"]
    col_pickbench = cols["pickbench"]
    col_tag = cols["tag"]
    col_notes = cols["notes"]
    col_measured_by = cols["measured_by"]
    col_date = cols["date_measured"]

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
