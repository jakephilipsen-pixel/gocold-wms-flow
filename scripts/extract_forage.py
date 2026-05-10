#!/usr/bin/env python3
"""Daily extract for The Forage Company.

Thin wrapper around scripts/extract.py with sensible defaults:
  - 7 days of sale orders (rolling daily pull)
  - 30 days of purchase orders (POs are less frequent)
  - Filter to The Forage Company

For one-off larger backfills, call extract.py directly with --so-days etc.

Examples:
    # Standard daily run
    python scripts/extract_forage.py

    # Larger backfill on first run
    python scripts/extract_forage.py --so-days 90 --po-days 180

    # Just count, don't write
    python scripts/extract_forage.py --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CUSTOMER = "The Forage Company"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--so-days", type=int, default=7,
                   help="days of sale orders (default 7 for daily runs)")
    p.add_argument("--po-days", type=int, default=30,
                   help="days of purchase orders (default 30)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-products", action="store_true",
                   help="skip product pull (faster, dims rarely change)")
    args = p.parse_args()

    extract = Path(__file__).resolve().parent / "extract.py"
    cmd = [
        sys.executable, str(extract),
        "--customer-name", CUSTOMER,
        "--so-days", str(args.so_days),
        "--po-days", str(args.po_days),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.no_products:
        cmd.append("--no-products")

    print(f"running: {' '.join(cmd)}\n")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
