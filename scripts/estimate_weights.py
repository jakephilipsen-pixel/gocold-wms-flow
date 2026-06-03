#!/usr/bin/env python3
"""Emit flagged estimated carton weights for review (AUDIT R6).

Fills the ~128 un-weighed cartons with a *flagged* estimate (density × cube,
family-median where possible) so cartonisation/dispatch has a number to work
with. Measured weights are passed through untouched; every estimated row is
tagged with its source and confidence so a human can review before anything
relies on it.

This is the human-approval gate the project insists on: estimates go to CSV,
never silently into the dim data or CartonCloud.

Usage:
    python scripts/estimate_weights.py
    python scripts/estimate_weights.py --dims dims.ods --out data/dims/weight_estimates.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from analysis.dim_loader import load_dimensions  # noqa: E402
from analysis.weight_estimate import (  # noqa: E402
    estimate_carton_weights,
    summarise,
)


def _latest_dims() -> Path:
    root_ods = ROOT / "dims.ods"
    if root_ods.exists():
        return root_ods
    candidates = sorted((ROOT / "data" / "dims").glob("dims_*.xlsx"))
    if not candidates:
        raise FileNotFoundError(
            "no dims source found (expected dims.ods or data/dims/dims_*.xlsx)"
        )
    return candidates[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dims", type=Path, default=None)
    ap.add_argument(
        "--out", type=Path,
        default=ROOT / "data" / "dims" / "weight_estimates.csv",
    )
    args = ap.parse_args()

    dims_path = args.dims or _latest_dims()
    dims = load_dimensions(dims_path)
    est = estimate_carton_weights(dims)

    cols = [
        "product_code",
        "family",
        "outer_l_mm",
        "outer_w_mm",
        "outer_h_mm",
        "outer_weight_kg",            # measured (blank if un-weighed)
        "outer_weight_kg_effective",  # measured OR estimate
        "weight_source",
        "weight_confidence",
        "weight_estimate_basis",
    ]
    out_df = est[[c for c in cols if c in est.columns]]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out, index=False)

    s = summarise(est)
    print(f"source:   {dims_path.relative_to(ROOT)}")
    print(f"rows:     {s['total']}")
    print("by source:     " + ", ".join(f"{k}={v}" for k, v in s["by_source"].items()))
    print("by confidence: " + ", ".join(f"{k}={v}" for k, v in s["by_confidence"].items()))
    print(f"written:  {args.out.relative_to(ROOT)}")
    print(
        "\nNOTE: 'low'-confidence rows are global-median guesses for families "
        "with no measured cartons (RK/GP/HP). Weigh those before trusting the "
        "estimate downstream."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
