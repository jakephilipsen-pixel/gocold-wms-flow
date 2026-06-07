"""Recommend a pallet-cube threshold (pallet_fraction) from real order data.

The pallet stream trigger (routing.classify_streams R4) fires when an order's
``pallet_fraction`` (cube sum / a pallet's usable cube) crosses a threshold.
Carton COUNT is noisy; cube is the honest signal. This script computes the
distribution of ``pallet_fraction_cube`` over a snapshot so the operator can
set the default where real pallet picks (~60-90 cartons) actually fall.

Read-only. Uses a local snapshot + dims; touches no network.

Usage:
    .venv/bin/python scripts/calibrate_pallet_cube.py [--raw DIR] [--dims FILE]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import sys
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from analysis import (  # noqa: E402
    compute_order_metrics,
    compute_velocity,
    apply_tags,
    load_dimensions,
    load_latest,
    run_full_pallet_analysis,
)


def recommend_threshold(per_order: pd.DataFrame) -> dict:
    """Summarise pallet_fraction_cube and recommend a threshold.

    The recommendation is the 90th percentile of non-trivial orders (fraction
    >= 0.05), rounded to 2 dp - a defensible "this order is pallet-sized"
    knee. The operator can override; this is a starting point, not a law.
    """
    frac = pd.to_numeric(
        per_order["pallet_fraction_cube"], errors="coerce"
    ).dropna()
    nontrivial = frac[frac >= 0.05]
    pct = lambda s, p: float(np.percentile(s, p)) if len(s) else float("nan")
    rec_basis = nontrivial if len(nontrivial) else frac
    return {
        "n_orders": int(len(frac)),
        "p50": round(pct(frac, 50), 3),
        "p75": round(pct(frac, 75), 3),
        "p90": round(pct(frac, 90), 3),
        "p95": round(pct(frac, 95), 3),
        "recommended_threshold": round(pct(rec_basis, 90), 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=_ROOT / "data" / "raw")
    ap.add_argument("--dims", type=Path, default=None)
    args = ap.parse_args()

    snap = load_latest(args.raw)
    dim_path = args.dims or sorted(
        (_ROOT / "data" / "dims").glob("dims_*.xlsx"))[-1]
    dims = load_dimensions(dim_path)
    raw_vel = compute_velocity(snap)
    apply_tags(raw_vel.sku_metrics, dims)
    full_pallet = run_full_pallet_analysis(snap, dims, raw_vel.sku_metrics)
    metrics = compute_order_metrics(snap, dims, full_pallet)

    rec = recommend_threshold(metrics.per_order)
    print("Pallet-cube calibration")
    print("-----------------------")
    for k, v in rec.items():
        print(f"  {k:>22}: {v}")
    print()
    print(f"Set --pallet-fraction-threshold {rec['recommended_threshold']} "
          f"(currently default 0.70).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
