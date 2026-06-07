#!/usr/bin/env python3
"""Helper: analyse pallet_fraction distribution from a route run.

Reads order_streams.csv from the most recent route_*/ folder, prints
percentile / histogram stats, and saves a percentile plot under
data/processed/route_tuning/.

Read-only on CC data; writes only local PNG/CSV.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

log = logging.getLogger("tune_threshold")


def _latest_route_dir(processed: Path) -> Path:
    candidates = sorted(
        processed.glob("route_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no route_*/ folders in {processed}")
    return candidates[0]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parent.parent
    p.add_argument("--processed", type=Path, default=repo_root / "data" / "processed")
    p.add_argument("--out", type=Path, default=repo_root / "data" / "processed" / "route_tuning")
    args = p.parse_args()

    logging.basicConfig(
        level="INFO",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    src = _latest_route_dir(args.processed)
    order_streams = pd.read_csv(src / "order_streams.csv")
    print(f"loaded {len(order_streams)} orders from {src.name}")

    pf = order_streams["pallet_fraction"].astype(float)
    pf_cube = order_streams["pallet_fraction_cube"].astype(float)
    pf_pos = order_streams["pallet_fraction_positions"].astype(float)

    args.out.mkdir(parents=True, exist_ok=True)

    print("\n--- pallet_fraction distribution ---")
    print(pf.describe(percentiles=[0.10, 0.25, 0.5, 0.75, 0.80, 0.85, 0.90, 0.95]))

    print("\n--- counts above thresholds ---")
    print(f"{'thr':>5}  {'n_S1':>5}  {'%':>6}")
    for thr in (0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00):
        n = int((pf >= thr).sum())
        pct = 100.0 * n / len(pf)
        print(f"{thr:>5.2f}  {n:>5d}  {pct:>5.1f}%")

    print("\n--- by stream ---")
    by_stream = order_streams.groupby("stream")["pallet_fraction"].describe(
        percentiles=[0.5, 0.9]
    )
    print(by_stream)

    # ------ percentile (ECDF) plot ------
    fig, ax = plt.subplots(figsize=(9, 5.5))
    sorted_pf = np.sort(pf.dropna().values)
    ecdf = np.arange(1, len(sorted_pf) + 1) / len(sorted_pf)
    ax.plot(sorted_pf, ecdf * 100.0, color="#1f4e79", lw=2, label="pallet_fraction")
    for thr in (0.50, 0.60, 0.70, 0.80):
        ax.axvline(thr, color="grey", lw=0.7, ls=":")
        ax.text(
            thr + 0.005, 1, f"{thr:.2f}",
            color="grey", fontsize=8, rotation=90, va="bottom",
        )
    ax.set_xlim(0, max(2.0, sorted_pf.max() * 1.05))
    ax.set_xlabel("pallet_fraction (max of cube + position methods)")
    ax.set_ylabel("percentile of orders <= x")
    ax.set_title("Order pallet_fraction ECDF — find the knee")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out_png = args.out / "pallet_fraction_ecdf.png"
    fig.savefig(out_png, dpi=120)
    plt.close(fig)
    print(f"\nwrote {out_png}")

    # ------ zoomed histogram in the 0.3-1.0 band ------
    fig, ax = plt.subplots(figsize=(9, 5.5))
    mask = (pf >= 0.0) & (pf <= 1.5)
    ax.hist(pf[mask], bins=30, color="#3a73b3", edgecolor="white")
    for thr in (0.50, 0.60, 0.70, 0.80):
        ax.axvline(thr, color="red", lw=0.7, ls="--")
        ax.text(thr + 0.005, ax.get_ylim()[1] * 0.95, f"{thr:.2f}", fontsize=8, color="red")
    ax.set_xlabel("pallet_fraction")
    ax.set_ylabel("orders")
    ax.set_title("Histogram of pallet_fraction (clipped to <= 1.5)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out_png2 = args.out / "pallet_fraction_hist.png"
    fig.savefig(out_png2, dpi=120)
    plt.close(fig)
    print(f"wrote {out_png2}")

    # ------ threshold sweep counts table ------
    rows = []
    for thr in [round(0.30 + 0.05 * i, 2) for i in range(0, 15)]:
        n = int((pf >= thr).sum())
        rows.append({"threshold": thr, "n_above": n, "pct": round(100.0 * n / len(pf), 1)})
    sweep = pd.DataFrame(rows)
    sweep.to_csv(args.out / "threshold_sweep.csv", index=False)
    print(f"wrote {args.out / 'threshold_sweep.csv'}")

    # ------ method divergence (used in T4 too, but we surface here) ------
    div = (pf_cube.fillna(0) - pf_pos.fillna(0)).abs()
    print("\ncube vs position |divergence|:")
    print(div.describe(percentiles=[0.5, 0.9, 0.95, 0.99]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
