#!/usr/bin/env python3
"""M-DIMS-5d probe — read-only Base/Each UoM name-shape census (NO WRITES).

5c (write dims to the CT carton UoM) is dropped from automated scope: CC's name-validation trap
(every CT UoM is named "CT", 2 chars < the 3-char floor) 422s the dims PATCH. Fixing CT names is
a manual CC-UI job. So the automated target moves to the **Each / Base UoM**, which every SKU has.

Before building the each-write, this probe answers the go/no-go question READ-ONLY: across live
Forage, does each SKU's Base UoM carry a valid (3–64 char) name, or would the each-write hit the
SAME trap? Buckets: each-writable / each-blocked / no-each. Also reports how many Base UoMs
already carry dims (a future each-write would no-op those).

NO WRITES, NO FLAG. Issues GETs only (``/warehouse-products/{id}`` under v8) and inspects the
JSON; never flips ``write_enabled``, never reads/needs ``CC_LIVE_PROMOTION``.

    .venv/bin/python3 scripts/probe_each_uom_names.py
    .venv/bin/python3 scripts/probe_each_uom_names.py --csv data/dims/each_uom_census.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

# allow running without installing: src/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cc_client import CartonCloudClient  # noqa: E402
from dims_write import (  # noqa: E402
    probe_each_uom_names,
    format_each_uom_census,
)

log = logging.getLogger("probe_each_uom_names")


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (same convention as the other dims run scripts)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"), help="path to .env (default ./.env)")
    parser.add_argument("--pace-seconds", type=float, default=0.2,
                        help="delay between GETs (politeness; reads aren't hard-capped)")
    parser.add_argument("--csv", type=Path, default=None,
                        help="optional path to write the full per-SKU census as CSV")
    args = parser.parse_args()

    _load_dotenv(args.env)

    # The probe issues GETs only — it never builds or sends a PATCH regardless of
    # whether the client happens to be write-enabled in this shell.
    client = CartonCloudClient.from_env()

    log.info("scanning active live Forage products for Base/Each UoM name shape (read-only)…")
    census = probe_each_uom_names(client, pace_seconds=args.pace_seconds)

    print("\n" + format_each_uom_census(census))

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["code", "product_id", "bucket", "uom", "uom_code", "name", "name_len",
                        "has_dims", "reason"])
            for p in sorted(census.probes, key=lambda x: (x.bucket, x.code)):
                w.writerow([p.code, p.product_id, p.bucket, p.uom, p.uom_code, p.name,
                            p.name_len, p.has_dims, p.reason])
        print(f"\nfull per-SKU census written to {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
