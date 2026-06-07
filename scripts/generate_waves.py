#!/usr/bin/env python3
"""Generate operator-ready wave pick sheets from live open CartonCloud SOs.

Pipeline:
  1. Pull live outbound orders in ``AWAITING_PICK_AND_PACK`` status from
     CC (no stale parquet — open orders move fast).
  2. Save the pull to ``data/raw/so_lines_open_<timestamp>.parquet`` as
     an audit trail.
  3. Build a working Snapshot from the live SO pull + the most recent
     PO/products parquets in ``data/raw/``.
  4. Run routing (velocity -> tags -> full_pallet -> order_metrics ->
     classify_streams), reusing the existing pipeline.
  5. Pull live SKU locations from CC stock-on-hand (mandatory — no stale
     fallback).
  6. Call ``generate_wave_pick_sheets``.
  7. For each wave, write PDF + picks CSV + orders CSV into
     ``data/processed/waves/<timestamp>/<wave_id>/``.
  8. Write a top-level ``index.md`` listing every wave with quick stats.

Read-only against CC — we generate paperwork. The operator creates the
wave in CC manually using the SO list we hand them.

Usage:
    python scripts/generate_waves.py

    # tune routing params
    python scripts/generate_waves.py --pallet-fraction-threshold 0.65 \\
                                     --early-release-cartons 25

    # custom logo
    python scripts/generate_waves.py --logo path/to/logo.png

    # different status (default: AWAITING_PICK_AND_PACK)
    python scripts/generate_waves.py --status AWAITING_PICK_AND_PACK

    # restrict to one customer
    python scripts/generate_waves.py --customer-name "The Forage Company"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wave_runner import (  # noqa: E402
    ProgressEvent,
    WaveRunSettings,
    run_wave_generation,
)


def _print_progress(event: ProgressEvent) -> None:
    prefix = {"ok": "  + ", "error": "  ! ", "info": ""}.get(event.level, "")
    print(f"{prefix}{event.message}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", type=str, default=None)
    p.add_argument("--customer-name", type=str, default=None)
    p.add_argument("--raw", type=Path, default=None)
    p.add_argument("--dims", type=Path, default=None)
    p.add_argument("--rules", type=Path, default=None)
    p.add_argument("--pallet-ratio", type=float, default=0.9)
    p.add_argument("--pallet-fraction-threshold", type=float, default=None)
    p.add_argument("--early-release-cartons", type=int, default=None)
    p.add_argument("--run-group-col", type=str, default=None)
    p.add_argument("--dispatch-plan", type=Path, default=None,
                   help="dispatch plan dir (data/processed/dispatch/<stamp>/); "
                        "default = latest")
    p.add_argument("--logo", type=Path,
                   default=repo_root / "assests" / "gocold_logo.png")
    p.add_argument("--lines-per-hour", type=int, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    # Build settings, letting WaveRunSettings defaults fill any None flag.
    kw = dict(repo_root=repo_root)
    if args.status is not None: kw["status"] = args.status
    if args.customer_name is not None: kw["customer_name"] = args.customer_name
    if args.pallet_fraction_threshold is not None:
        kw["pallet_fraction_threshold"] = args.pallet_fraction_threshold
    if args.early_release_cartons is not None:
        kw["early_release_cartons"] = args.early_release_cartons
    if args.run_group_col is not None: kw["run_group_col"] = args.run_group_col
    if args.dispatch_plan is not None: kw["dispatch_plan_dir"] = args.dispatch_plan
    if args.lines_per_hour is not None: kw["lines_per_hour"] = args.lines_per_hour
    kw["pallet_ratio"] = args.pallet_ratio
    kw["raw_dir"] = args.raw
    kw["dims_path"] = args.dims
    kw["rules_path"] = args.rules
    kw["logo_path"] = args.logo
    kw["out_dir"] = args.out
    settings = WaveRunSettings(**kw)

    result = run_wave_generation(settings, _print_progress)
    if result.status == "failed":
        print(f"\nFAILED: {result.error}", file=sys.stderr)
        return 1
    print(f"\nOK. open {result.out_dir / 'index.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
