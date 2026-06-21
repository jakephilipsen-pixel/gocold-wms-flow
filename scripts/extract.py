#!/usr/bin/env python3
"""Pull SO / PO / Product data from CartonCloud to local Parquet.

Run this after smoke_test.py passes. Output goes to data/raw/ for
the analysis notebooks to consume. Use --dry-run to count records
without writing files.

Examples:
    # last 30 days of sale orders + last 90 days of purchase orders + all products
    python scripts/extract.py --so-days 30 --po-days 90

    # dry run, just print counts
    python scripts/extract.py --so-days 7 --po-days 7 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cc_client import (  # noqa: E402
    CartonCloudClient,
    CartonCloudError,
    search_inbound_orders,
    search_outbound_orders,
    search_warehouse_products,
)

log = logging.getLogger("extract")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _flatten_outbound_order_lines(order: dict) -> list[dict]:
    """Explode an outbound order into one row per line item.

    This is the layout that's actually useful for slotting/velocity analysis:
    one row per (so_ref, sku, qty) so we can groupby SKU.
    """
    items = order.get("items") or []
    if not items:
        return []
    base = {
        "so_id": order.get("id"),
        "so_ref": (order.get("references") or {}).get("customer"),
        "so_numeric_id": (order.get("references") or {}).get("numericId"),
        "status": order.get("status"),
        "customer_id": (order.get("customer") or {}).get("id"),
        "customer_name": (order.get("customer") or {}).get("name"),
        "warehouse_name": (order.get("warehouse") or {}).get("name"),
    }
    details = order.get("details") or {}
    deliver = details.get("deliver") or {}
    addr = deliver.get("address") or {}
    base.update({
        "delivery_required_date": deliver.get("requiredDate"),
        "delivery_company": addr.get("companyName"),
        "delivery_suburb": addr.get("suburb"),
        "delivery_state": (addr.get("state") or {}).get("code") if isinstance(addr.get("state"), dict) else addr.get("state"),
        "delivery_postcode": addr.get("postcode"),
        "urgent": details.get("urgent"),
    })
    timestamps = order.get("timestamps") or {}
    for k in ("created", "modified", "packed", "dispatched"):
        ts = (timestamps.get(k) or {}).get("time")
        base[f"ts_{k}"] = ts

    rows = []
    for item in items:
        product = (item.get("details") or {}).get("product") or {}
        uom = (item.get("details") or {}).get("unitOfMeasure") or {}
        measures = item.get("measures") or {}
        props = item.get("properties") or {}
        rows.append({
            **base,
            "product_id": product.get("id"),
            "product_code": (product.get("references") or {}).get("code"),
            "product_name": product.get("name"),
            "uom_type": uom.get("type"),
            "uom_name": uom.get("name"),
            "quantity": measures.get("quantity"),
            "batch": props.get("batch"),
            "expiry_date": props.get("expiryDate"),
        })
    return rows


def _flatten_inbound_order_lines(order: dict) -> list[dict]:
    items = order.get("items") or []
    if not items:
        return []
    details = order.get("details") or {}
    base = {
        "po_id": order.get("id"),
        "po_ref": (order.get("references") or {}).get("customer"),
        "po_numeric_id": (order.get("references") or {}).get("numericId"),
        "status": order.get("status"),
        "customer_id": (order.get("customer") or {}).get("id"),
        "customer_name": (order.get("customer") or {}).get("name"),
        "arrival_date": details.get("arrivalDate"),
        "urgent": details.get("urgent"),
    }
    rows = []
    for item in items:
        product = (item.get("details") or {}).get("product") or {}
        uom = (item.get("details") or {}).get("unitOfMeasure") or {}
        measures = item.get("measures") or {}
        props = item.get("properties") or {}
        rows.append({
            **base,
            "product_id": product.get("id"),
            "product_code": (product.get("references") or {}).get("code"),
            "product_name": product.get("name"),
            "uom_type": uom.get("type"),
            "quantity": measures.get("quantity"),
            "item_status": item.get("status"),
            "batch": props.get("batch"),
            "expiry_date": props.get("expiryDate"),
        })
    return rows


def _flatten_product(product: dict) -> dict:
    """One row per SKU with carton/unit/pallet dimensions if present."""
    uoms = product.get("unitOfMeasures") or {}
    out = {
        "product_id": product.get("id"),
        "product_code": (product.get("references") or {}).get("code"),
        "name": product.get("name"),
        "description": product.get("description"),
        "type": product.get("type"),
        "default_uom": product.get("defaultUnitOfMeasure"),
        "active": (product.get("details") or {}).get("active"),
        "customer_id": (product.get("customer") or {}).get("id"),
    }
    for uom_name in ("units", "cartons", "pallets"):
        u = uoms.get(uom_name) or {}
        out[f"{uom_name}_baseQty"] = u.get("baseQty")
        out[f"{uom_name}_weight"] = u.get("weight")
        out[f"{uom_name}_length"] = u.get("length")
        out[f"{uom_name}_width"] = u.get("width")
        out[f"{uom_name}_height"] = u.get("height")
        out[f"{uom_name}_barcode"] = u.get("barcode")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--so-days", type=int, default=30,
                   help="days of sale orders to pull (by packed timestamp)")
    p.add_argument("--po-days", type=int, default=90,
                   help="days of purchase orders to pull (by arrival date)")
    p.add_argument("--customer-name", type=str, default=None,
                   help="optional: filter by customer name (exact match)")
    p.add_argument("--products", action="store_true", default=True,
                   help="also pull warehouse products (default on)")
    p.add_argument("--no-products", dest="products", action="store_false")
    p.add_argument("--out", type=Path,
                   default=Path(__file__).resolve().parent.parent / "data" / "raw")
    p.add_argument("--dry-run", action="store_true",
                   help="just count, don't write files")
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
        print("pandas required: pip install pandas pyarrow httpx", file=sys.stderr)
        return 2

    client = CartonCloudClient.from_env()
    today = date.today()
    so_from = today - timedelta(days=args.so_days)
    po_from = today - timedelta(days=args.po_days)

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- Sale orders
    print(f"pulling sale orders packed since {so_from}...")
    so_lines: list[dict] = []
    so_count = 0
    try:
        for order in search_outbound_orders(
            client,
            packed_from=so_from,
            packed_to=today,
            customer_name=args.customer_name,
        ):
            so_count += 1
            so_lines.extend(_flatten_outbound_order_lines(order))
            if so_count % 100 == 0:
                log.info("  ...%d orders, %d lines so far", so_count, len(so_lines))
    except CartonCloudError as e:
        print(f"❌ sale order extract failed: {e}", file=sys.stderr)
        return 1
    print(f"  ✓ {so_count} orders → {len(so_lines)} line items")

    # --- Purchase orders
    print(f"pulling purchase orders arriving since {po_from}...")
    po_lines: list[dict] = []
    po_count = 0
    try:
        for order in search_inbound_orders(
            client,
            arrival_from=po_from,
            arrival_to=today,
            customer_name=args.customer_name,
        ):
            po_count += 1
            po_lines.extend(_flatten_inbound_order_lines(order))
    except CartonCloudError as e:
        print(f"❌ purchase order extract failed: {e}", file=sys.stderr)
        return 1
    print(f"  ✓ {po_count} purchase orders → {len(po_lines)} line items")

    # --- Products
    products: list[dict] = []
    if args.products:
        # Orders filter by customer *name*, but the product search filters by
        # customer *id*. Resolve name→id once so the customer name stays the
        # single source of truth (no hardcoded UUID to drift). If no customer
        # is set, fall back to the tenant-wide active pull.
        customer_id: str | None = None
        if args.customer_name:
            try:
                customers = client.get("/customers")
            except CartonCloudError as e:
                print(f"❌ couldn't list customers to resolve "
                      f"{args.customer_name!r}: {e}", file=sys.stderr)
                return 1
            match = next(
                (c for c in customers
                 if c.get("name") == args.customer_name),
                None,
            )
            if match is None:
                print(f"❌ customer {args.customer_name!r} not found — refusing "
                      f"to pull tenant-wide products. Check the name against "
                      f"smoke_test output.", file=sys.stderr)
                return 1
            customer_id = match.get("id")
            print(f"pulling warehouse products (active) for "
                  f"{args.customer_name!r} ({customer_id})...")
        else:
            print("pulling warehouse products (active, tenant-wide)...")
        try:
            for prod in search_warehouse_products(client, customer_id=customer_id):
                products.append(_flatten_product(prod))
        except CartonCloudError as e:
            print(f"❌ product extract failed: {e}", file=sys.stderr)
            return 1
        print(f"  ✓ {len(products)} active products")

    if args.dry_run:
        print("\n--dry-run: not writing files")
        return 0

    # --- Persist
    if so_lines:
        df = pd.DataFrame(so_lines)
        out = args.out / f"so_lines_{stamp}.parquet"
        df.to_parquet(out, index=False)
        print(f"  wrote {out} ({len(df)} rows)")
    if po_lines:
        df = pd.DataFrame(po_lines)
        out = args.out / f"po_lines_{stamp}.parquet"
        df.to_parquet(out, index=False)
        print(f"  wrote {out} ({len(df)} rows)")
    if products:
        df = pd.DataFrame(products)
        out = args.out / f"products_{stamp}.parquet"
        df.to_parquet(out, index=False)
        print(f"  wrote {out} ({len(df)} rows)")
        # sanity check: how many have carton dims?
        if "cartons_length" in df.columns:
            with_dims = df[
                df["cartons_length"].notna()
                & df["cartons_width"].notna()
                & df["cartons_height"].notna()
            ]
            print(
                f"  → {len(with_dims)}/{len(df)} products have full carton dims "
                f"({100 * len(with_dims) / len(df):.1f}%)"
            )

    # write a small manifest of what we just pulled
    manifest = {
        "extracted_at": datetime.now().isoformat(),
        "so_window_from": so_from.isoformat(),
        "so_window_to": today.isoformat(),
        "po_window_from": po_from.isoformat(),
        "po_window_to": today.isoformat(),
        "customer_filter": args.customer_name,
        "so_orders": so_count,
        "so_lines": len(so_lines),
        "po_orders": po_count,
        "po_lines": len(po_lines),
        "products": len(products),
    }
    (args.out / f"manifest_{stamp}.json").write_text(
        json.dumps(manifest, indent=2)
    )
    print(f"\n✅ done. manifest at {args.out / f'manifest_{stamp}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
