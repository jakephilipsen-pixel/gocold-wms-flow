#!/usr/bin/env python3
"""Pull current Warehouse Locations from CartonCloud → local parquet + xlsx.

This is a probe + extractor for the warehouse-locations endpoint. If the
endpoint isn't exposed on the public API for this tenant, the script
fails cleanly and tells you to use the UI XLS export instead.

Output:
    data/raw/locations_<timestamp>.parquet  — for downstream analysis
    data/raw/locations_<timestamp>.xlsx     — human-readable, Go Cold themed

Usage:
    python scripts/extract_locations.py

    # specify warehouse if you have multiple
    python scripts/extract_locations.py --warehouse "Default"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cc_client import (  # noqa: E402
    CartonCloudClient,
    CartonCloudError,
    search_warehouse_locations,
)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _flatten_location(loc: dict) -> dict:
    """One row per location. We extract every field that looks useful."""
    refs = loc.get("references") or {}
    details = loc.get("details") or {}
    warehouse = loc.get("warehouse") or {}
    return {
        "location_id": loc.get("id"),
        "name": loc.get("name") or refs.get("name"),
        "code": refs.get("code"),
        "barcode": refs.get("barcode"),
        "type": loc.get("type"),
        "warehouse_name": warehouse.get("name"),
        "warehouse_id": warehouse.get("id"),
        "bay": details.get("bay"),
        "level": details.get("level"),
        "depth": details.get("depth"),
        "row": details.get("row"),
        "pick_efficiency": details.get("pickEfficiency"),
        "is_pick_face": (
            details.get("pickEfficiency") is not None
            and details.get("pickEfficiency") >= 21
        ),
        "allowed_product_types": ",".join(
            (details.get("productTypes") or [])
        ),
        "active": details.get("active"),
        # raw blob retained for any field we missed
        "raw_json": json.dumps(loc, default=str),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--warehouse", default=None,
                   help="optional warehouse name filter")
    p.add_argument("--out", type=Path,
                   default=Path(__file__).resolve().parent.parent / "data" / "raw")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    repo_root = Path(__file__).resolve().parent.parent
    _load_dotenv(repo_root / ".env")

    try:
        import pandas as pd  # type: ignore
    except ImportError:
        print("pandas required", file=sys.stderr)
        return 2

    client = CartonCloudClient.from_env()
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"probing /warehouse-locations/search on tenant {client.tenant_id[:8]}...")
    locations: list[dict] = []
    try:
        for loc in search_warehouse_locations(
            client, warehouse_name=args.warehouse,
        ):
            locations.append(_flatten_location(loc))
            if len(locations) % 500 == 0:
                print(f"  ...{len(locations)} locations so far")
    except CartonCloudError as e:
        msg = str(e)
        print(f"\n❌ locations endpoint failed: {msg[:300]}", file=sys.stderr)
        if "404" in msg or "not found" in msg.lower():
            print(
                "\nThe warehouse-locations API endpoint isn't exposed for\n"
                "your tenant. Fall back to the UI export:\n"
                "  1. CC web app → Warehouse → Warehouse Locations\n"
                "  2. More → Export to XLS\n"
                "  3. Save the file, share it with me and I'll parse it.\n",
                file=sys.stderr,
            )
        elif "role" in msg.lower() or "401" in msg or "403" in msg:
            print(
                "\nLooks like a permission issue. The API client may need\n"
                "an additional role for warehouse locations access.\n"
                "Check the role list in CC admin and try again.\n",
                file=sys.stderr,
            )
        return 1

    print(f"  ✓ pulled {len(locations)} locations")

    if args.dry_run:
        print("--dry-run: not writing files")
        return 0

    if not locations:
        print("(no locations returned — nothing to write)")
        return 0

    df = pd.DataFrame(locations)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parquet_path = args.out / f"locations_{stamp}.parquet"
    df.to_parquet(parquet_path, index=False)
    print(f"  wrote {parquet_path}")

    # Also save a human-readable xlsx without the raw_json blob
    display = df.drop(columns=["raw_json"], errors="ignore")
    xlsx_path = args.out / f"locations_{stamp}.xlsx"
    display.to_excel(xlsx_path, index=False)
    print(f"  wrote {xlsx_path}")

    # Quick summary
    print("\nSummary:")
    print(f"  total locations: {len(df)}")
    if "is_pick_face" in df.columns:
        pf = int(df["is_pick_face"].sum())
        print(f"  pick faces (pickEfficiency 21-30): {pf}")
        print(f"  reserve locations (pickEfficiency 1-20): {len(df) - pf}")
    if "warehouse_name" in df.columns:
        print(
            "  by warehouse: "
            + ", ".join(
                f"{w}={n}" for w, n in df["warehouse_name"]
                .value_counts(dropna=False).items()
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
