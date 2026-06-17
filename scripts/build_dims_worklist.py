#!/usr/bin/env python3
"""Build the dims completion worklist.

Reads CartonCloud's live active Forage products (READ-ONLY) and joins them
against locally captured carton dims, then writes a highlighted xlsx listing
exactly what still needs measuring:
  - inner SKUs (inner-pack-qty == 1): captured dims already are each-level
  - carton SKUs (> 1): each-level L/W/H highlighted for physical measurement
  - unknown / not-captured / weight-pending: flagged

CC stays read-only. Nothing is written back to CC by this script.

Usage:
    .venv/bin/python scripts/build_dims_worklist.py \
        --dims data/dims/dims_2026-05-13.xlsx \
        --out  data/dims/dims_worklist_<date>.xlsx

If --out is omitted, writes data/dims/dims_worklist.xlsx.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# repo-root import shim (mirrors scripts/extract.py)
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from analysis.dim_loader import load_dimensions  # noqa: E402
from analysis.dims_worklist import build_worklist, captured_not_in_cc  # noqa: E402
from analysis.dims_worklist_xlsx import write_worklist_xlsx  # noqa: E402
from analysis.dims_measuring_sheet import (  # noqa: E402
    partition_measuring,
    write_measuring_sheet,
)
from cc_client import CartonCloudClient, search_warehouse_products  # noqa: E402

log = logging.getLogger("build_dims_worklist")

# The Forage Company (canonical, per CLAUDE.md). The CC client is NOT
# customer-scoped — it sees the whole tenant (~3700 products) — so the
# worklist must filter to Forage explicitly or it fills with other
# customers' SKUs.
FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (mirrors scripts/smoke_test.py)."""
    if not path.exists():
        return
    import os
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dims", type=Path,
                   default=_ROOT / "data/dims/dims_2026-05-13.xlsx",
                   help="captured dims capture sheet (default: May 2026 sheet)")
    # NB: outputs live in data/dims/worklists/ (a subdir), NOT directly in
    # data/dims/. The wave pipeline globs data/dims/dims_*.xlsx for the capture
    # sheet (wave_runner._latest_file), so a "dims_*.xlsx" written here would be
    # mistaken for a capture sheet and break wave generation. The subdir keeps
    # these out of that non-recursive glob.
    p.add_argument("--out", type=Path,
                   default=_ROOT / "data/dims/worklists/dims_worklist.xlsx",
                   help="output worklist xlsx path")
    p.add_argument("--customer-id", type=str, default=FORAGE_CUSTOMER_ID,
                   help="CC customer UUID to scope products to "
                        "(default: The Forage Company)")
    p.add_argument("--measuring-sheet", type=Path,
                   default=_ROOT / "data/dims/worklists/dims_measuring_sheet.xlsx",
                   help="output trimmed print-friendly measuring sheet "
                        "(only rows needing work; set to '' to skip)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _load_dotenv(_ROOT / ".env")

    log.info("loading captured dims from %s", args.dims)
    dims_df = load_dimensions(args.dims)

    log.info("pulling active Forage products from CartonCloud (read-only)…")
    client = CartonCloudClient.from_env()
    products = list(search_warehouse_products(client, customer_id=args.customer_id))
    log.info("  %d active products (customer %s)", len(products), args.customer_id)

    wl = build_worklist(dims_df, products)
    orphans = captured_not_in_cc(dims_df, products)

    # summary
    counts = wl["kind"].value_counts().to_dict()
    log.info("worklist rows: %d", len(wl))
    log.info("  inner (complete)         : %d", counts.get("inner", 0))
    log.info("  carton (each-fill needed): %d", counts.get("carton", 0))
    log.info("  unknown (resolve ipq)    : %d", counts.get("unknown", 0))
    log.info("  weight pending           : %d", int(wl["weight_pending"].sum()))
    log.info("  no carton UoM in CC      : %d", int(wl["no_carton_uom"].sum()))
    log.info("  not captured locally     : %d", int(wl["not_captured"].sum()))
    if orphans:
        log.info("  captured but NOT in CC (%d): %s", len(orphans), ", ".join(orphans))

    write_worklist_xlsx(wl, args.out)
    log.info("wrote %s", args.out)

    if str(args.measuring_sheet):
        groups = partition_measuring(wl)
        log.info("measuring sheet groups:")
        log.info("  measure each unit (carton): %d", len(groups["measure_each"]))
        log.info("  full capture (unknown)    : %d", len(groups["full_capture"]))
        log.info("  weigh only (inner no wt)  : %d", len(groups["weigh_only"]))
        write_measuring_sheet(groups, args.measuring_sheet)
        log.info("wrote %s", args.measuring_sheet)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
