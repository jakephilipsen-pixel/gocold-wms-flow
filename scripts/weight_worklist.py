#!/usr/bin/env python3
"""Emit the carton-weight capture worklist (AUDIT R6).

Outer L/W/H are 100% captured, but outer *weight* sits at ~281/409 SKUs —
the remaining ~128 cartons have never been weighed, and that data exists
nowhere digital (not in the dim sheets, not in CartonCloud's empty
``cartons_weight`` field). Weight-based cartonisation and dispatch-load
maths need it, so the gap has to be closed on the floor with the scale.

This script does the one thing software *can* do here: produce a tight,
prioritised list of exactly which SKUs still need weighing, highest pick
velocity first, so the operator weighs the cartons that matter most before
the long tail. It reads the latest dim capture file, finds blank weights,
and joins the velocity columns the capture sheet already carries.

Read-only. Writes a single CSV; touches nothing in CartonCloud.

Usage:
    python scripts/weight_worklist.py
    python scripts/weight_worklist.py --dims dims.ods --out data/dims/weight_worklist.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from analysis.dim_loader import _find_col, load_dimensions  # noqa: E402


def _latest_dims() -> Path:
    """Pick the most recent dims source: prefer the live root ``dims.ods``,
    else the newest ``data/dims/dims_*.xlsx``."""
    root_ods = ROOT / "dims.ods"
    if root_ods.exists():
        return root_ods
    candidates = sorted((ROOT / "data" / "dims").glob("dims_*.xlsx"))
    if not candidates:
        raise FileNotFoundError(
            "no dims source found (expected dims.ods or data/dims/dims_*.xlsx)"
        )
    return candidates[-1]


def _velocity_columns(path: Path) -> pd.DataFrame:
    """Pull the velocity/priority context the capture sheet already holds.

    Returns product_code + units_per_day + abc + priority (blank-safe).
    """
    raw = pd.read_excel(path, sheet_name="SKU Capture", header=3)
    raw = raw[raw["Product Code"].notna()].copy()
    code = _find_col(raw, "Product Code")
    units = _find_col(raw, "Units/day", "Units per day")
    abc = _find_col(raw, "ABC", "ABC – velocity", "ABC - velocity")
    prio = _find_col(raw, "Priority")
    out = pd.DataFrame({"product_code": raw[code].astype(str).str.strip()})
    out["units_per_day"] = (
        pd.to_numeric(raw[units], errors="coerce") if units else pd.NA
    )
    out["abc"] = raw[abc].astype(str).str.strip() if abc else ""
    out["priority"] = (
        pd.to_numeric(raw[prio], errors="coerce") if prio else pd.NA
    )
    return out


def build_worklist(dims_path: Path) -> pd.DataFrame:
    dims = load_dimensions(dims_path)
    missing = dims[dims["outer_weight_kg"].isna()].copy()

    vel = _velocity_columns(dims_path)
    missing = missing.merge(vel, on="product_code", how="left")

    cols = [
        "product_code",
        "units_per_day",
        "abc",
        "priority",
        "outer_l_mm",
        "outer_w_mm",
        "outer_h_mm",
        "inner_pack_qty",
    ]
    worklist = missing[[c for c in cols if c in missing.columns]].copy()
    # Highest pick velocity first; unknown velocity sorts last.
    worklist = worklist.sort_values(
        "units_per_day", ascending=False, na_position="last"
    ).reset_index(drop=True)
    worklist.insert(0, "weigh_order", range(1, len(worklist) + 1))
    return worklist


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dims", type=Path, default=None,
        help="dim capture file (default: latest dims.ods / data/dims/dims_*.xlsx)",
    )
    ap.add_argument(
        "--out", type=Path,
        default=ROOT / "data" / "dims" / "weight_worklist.csv",
        help="output CSV path",
    )
    args = ap.parse_args()

    dims_path = args.dims or _latest_dims()
    dims = load_dimensions(dims_path)
    total = len(dims)
    have = int(dims["outer_weight_kg"].notna().sum())

    worklist = build_worklist(dims_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    worklist.to_csv(args.out, index=False)

    print(f"source:   {dims_path.relative_to(ROOT)}")
    print(f"coverage: {have}/{total} weighed ({100 * have / total:.1f}%)")
    print(f"to weigh: {len(worklist)} SKUs")
    print(f"written:  {args.out.relative_to(ROOT)}")
    if not worklist.empty and "abc" in worklist.columns:
        by_abc = worklist["abc"].replace("", "?").value_counts().sort_index()
        print("by ABC:   " + ", ".join(f"{k}={v}" for k, v in by_abc.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
