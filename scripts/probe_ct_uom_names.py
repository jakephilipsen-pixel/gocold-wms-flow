#!/usr/bin/env python3
"""M-DIMS-5c probe — read-only CT UoM name-shape census (NO WRITES).

The first armed 5c live run fail-fast halted on SKU #1 (AE-BLA) with a 422:

    {"field":"/unitOfMeasures/CT/name","message":"Must be between 3 and 64 characters."}

ZERO dims written, no bad data landed. The dims payload was fine — CC rejected because
add-ing dimension sub-fields under ``/unitOfMeasures/CT/`` validates the WHOLE CT UoM object,
and that UoM's ``name`` was missing/too short. This probe censuses, READ-ONLY, whether each
live CT UoM has a valid (3–64 char) name, to decide: bad-data exceptions 5c should skip, or a
systemic "set the CT UoM name first" prerequisite before dims can attach.

NO WRITES, NO FLAG. This script never flips ``write_enabled`` and never reads/needs
``CC_LIVE_PROMOTION`` — it issues GETs only (``/warehouse-products/{id}`` under v8) and
inspects the JSON. Safe to run anytime.

    .venv/bin/python3 scripts/probe_ct_uom_names.py
    .venv/bin/python3 scripts/probe_ct_uom_names.py --csv data/dims/ct_uom_census.csv
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
    probe_ct_uom_names,
    format_ct_uom_census,
)

log = logging.getLogger("probe_ct_uom_names")


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

    log.info("scanning active live Forage products for CT UoM name shape (read-only)…")
    census = probe_ct_uom_names(client, pace_seconds=args.pace_seconds)

    print("\n" + format_ct_uom_census(census))

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["code", "product_id", "bucket", "uom", "name", "name_len", "reason"])
            for p in sorted(census.probes, key=lambda x: (x.bucket, x.code)):
                w.writerow([p.code, p.product_id, p.bucket, p.uom, p.name, p.name_len, p.reason])
        print(f"\nfull per-SKU census written to {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
