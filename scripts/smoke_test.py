#!/usr/bin/env python3
"""Smoke test for Go Cold's CartonCloud connection.

Run this BEFORE any data extraction. Verifies:
  1. Credentials in .env are loaded
  2. OAuth2 token endpoint is reachable
  3. Token is accepted (we can hit /uaa/userinfo)
  4. The CC_TENANT_ID actually exists for this client
  5. We can do a tiny read against the tenant (1 product)

Exits 0 on success, non-zero on any failure with a human-readable error.

Usage:
    cp .env.example .env
    # edit .env with your real CC_CLIENT_ID, CC_CLIENT_SECRET, CC_TENANT_ID
    python scripts/smoke_test.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# allow running without installing: src/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cc_client import (  # noqa: E402
    CartonCloudClient,
    CartonCloudAuthError,
    CartonCloudError,
    search_warehouse_products,
)


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader so we don't need python-dotenv as a dep."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    repo_root = Path(__file__).resolve().parent.parent
    _load_dotenv(repo_root / ".env")

    missing = [
        v for v in ("CC_CLIENT_ID", "CC_CLIENT_SECRET", "CC_TENANT_ID")
        if not os.environ.get(v)
    ]
    if missing:
        print(f"❌ missing env vars: {', '.join(missing)}", file=sys.stderr)
        print("   copy .env.example to .env and fill in values", file=sys.stderr)
        return 2

    print("step 1: auth + token...")
    try:
        client = CartonCloudClient.from_env()
    except ValueError as e:
        print(f"❌ config error: {e}", file=sys.stderr)
        return 2

    try:
        info = client.me()
    except CartonCloudAuthError as e:
        print(f"❌ auth failed: {e}", file=sys.stderr)
        print("   check CC_CLIENT_ID / CC_CLIENT_SECRET", file=sys.stderr)
        return 1
    except CartonCloudError as e:
        print(f"❌ couldn't reach CC: {e}", file=sys.stderr)
        return 1

    print(f"   ✓ authenticated as {info.get('name')} <{info.get('email')}>")

    print("step 2: tenant access...")
    tenants = info.get("tenants", [])
    tenant_ids = {t["id"] for t in tenants}
    if client.tenant_id not in tenant_ids:
        print(
            f"❌ CC_TENANT_ID={client.tenant_id} not in your accessible tenants",
            file=sys.stderr,
        )
        print("   accessible tenants:", file=sys.stderr)
        for t in tenants:
            print(f"     - {t['id']}  {t.get('name')}", file=sys.stderr)
        return 1
    selected_name = next(
        (t.get("name") for t in tenants if t["id"] == client.tenant_id),
        "(unknown)",
    )
    print(f"   ✓ tenant {client.tenant_id} ({selected_name}) accessible")

    print("step 3: tiny read (1 warehouse product)...")
    try:
        first = next(
            search_warehouse_products(client, page_size=1, max_pages=1),
            None,
        )
    except CartonCloudError as e:
        print(f"❌ search failed: {e}", file=sys.stderr)
        print("   API key may lack required role (WMS Add/Edit Product)", file=sys.stderr)
        return 1

    if first is None:
        print("   ⚠ no products returned (active=true filter)")
        print("     this might mean your customer hasn't loaded products yet,")
        print("     or this API client lacks read access to the customer.")
    else:
        print(
            f"   ✓ got product: {first.get('name')!r} "
            f"(code={first.get('references', {}).get('code')})"
        )
        uoms = first.get("unitOfMeasures") or {}
        cartons = uoms.get("cartons") or {}
        if cartons.get("length") and cartons.get("width") and cartons.get("height"):
            print(
                f"     carton dims present: "
                f"{cartons['length']} × {cartons['width']} × {cartons['height']}"
            )
        else:
            print("     ⚠ no carton dims on this product (will need data entry)")

    print("step 4: customer discovery (find The Forage Company)...")
    try:
        customers = client.get("/customers")
    except CartonCloudError as e:
        print(f"   ⚠ couldn't list customers: {e}")
        print("     API client may lack 'Add Customer' or 'WMS Create Jobs' role")
        customers = []

    if customers:
        print(f"   ✓ {len(customers)} customers visible to this API client:")
        forage_match = None
        for c in customers:
            name = c.get("name", "")
            cid = c.get("id", "")
            print(f"     - {name!r}  ({cid})")
            if "forage" in name.lower():
                forage_match = c
        if forage_match:
            print(
                f"\n   → likely Forage match: {forage_match['name']!r}"
            )
            print(
                f"     update CUSTOMER in scripts/extract_forage.py if the "
                f"name differs from 'The Forage Company'"
            )
        else:
            print("\n   ⚠ no customer with 'forage' in the name")

    print("\n✅ smoke test passed. you can now run extracts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
