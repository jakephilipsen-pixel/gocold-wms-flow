"""High-level query helpers for the data extraction we actually need.

Wraps raw client.post_search calls with friendly Python signatures and
date helpers. Keep this layer thin — it's just convenience over the
generic search API.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any, Iterator

from .client import CartonCloudClient, CartonCloudError

log = logging.getLogger(__name__)


def _iso(d: date | datetime | str) -> str:
    """Format a date/datetime for CC search comparisons (ISO 8601)."""
    if isinstance(d, str):
        return d
    if isinstance(d, datetime):
        return d.isoformat()
    return f"{d.isoformat()}T00:00:00+00:00"


def _and_text(field_value: str, value: str, method: str = "EQUAL_TO") -> dict:
    return {
        "type": "TextComparisonCondition",
        "field": {"type": "ValueField", "value": field_value},
        "value": {"type": "ValueField", "value": value},
        "method": method,
    }


def _date_range_condition(
    pointer: str,
    from_date: date | datetime | str | None,
    to_date: date | datetime | str | None,
) -> list[dict]:
    """Build search conditions for an ISO timestamp range.

    Uses JsonField pointers like /timestamps/packed/time.
    """
    conds: list[dict] = []
    if from_date is not None:
        conds.append({
            "type": "TextComparisonCondition",
            "field": {"type": "JsonField", "pointer": pointer},
            "value": {"type": "ValueField", "value": _iso(from_date)},
            "method": "GREATER_THAN_OR_EQUAL_TO",
        })
    if to_date is not None:
        conds.append({
            "type": "TextComparisonCondition",
            "field": {"type": "JsonField", "pointer": pointer},
            "value": {"type": "ValueField", "value": _iso(to_date)},
            "method": "LESS_THAN_OR_EQUAL_TO",
        })
    return conds


def search_outbound_orders(
    client: CartonCloudClient,
    *,
    packed_from: date | datetime | str | None = None,
    packed_to: date | datetime | str | None = None,
    customer_name: str | None = None,
    status: list[str] | None = None,
    page_size: int = 100,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate sale orders, optionally filtered by pack date, customer, or status.

    Returns full order objects including items[] with measures.quantity per line.

    ``status`` is a list of CC status codes (e.g. ``["AWAITING_PICK_AND_PACK"]``).
    Multiple values are OR-ed together. Use this to pull open orders that
    haven't been packed yet — those have no packed timestamp so the date
    filter wouldn't catch them.
    """
    conds: list[dict] = []
    conds.extend(_date_range_condition(
        "/timestamps/packed/time", packed_from, packed_to,
    ))
    if customer_name:
        conds.append(_and_text("customerName", customer_name, "EQUAL_TO"))
    if status:
        # CC rejects "status" as a ValueField but accepts /status as a
        # JsonField pointer (verified live, 2026-05-17).
        status_conds = [
            {
                "type": "TextComparisonCondition",
                "field": {"type": "JsonField", "pointer": "/status"},
                "value": {"type": "ValueField", "value": s},
                "method": "EQUAL_TO",
            }
            for s in status
        ]
        if len(status_conds) == 1:
            conds.append(status_conds[0])
        else:
            conds.append({
                "type": "OrCondition",
                "conditions": status_conds,
            })

    if not conds:
        # safety: CC search may reject empty conditions; force at least one
        raise ValueError(
            "must supply at least one filter (date range, customer, or status)"
        )

    body = {"condition": {"type": "AndCondition", "conditions": conds}}
    yield from client.post_search(
        "/outbound-orders/search",
        body,
        page_size=page_size,
        max_pages=max_pages,
    )


def search_inbound_orders(
    client: CartonCloudClient,
    *,
    arrival_from: date | datetime | str | None = None,
    arrival_to: date | datetime | str | None = None,
    customer_name: str | None = None,
    page_size: int = 100,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate purchase orders, filtered by arrival date and/or customer.

    arrivalDate uses ValueField (per docs), not JsonField pointer.
    """
    conds: list[dict] = []
    if arrival_from:
        conds.append({
            "type": "TextComparisonCondition",
            "field": {"type": "ValueField", "value": "arrivalDate"},
            "value": {"type": "ValueField", "value": _iso(arrival_from)[:10]},
            "method": "GREATER_THAN_OR_EQUAL_TO",
        })
    if arrival_to:
        conds.append({
            "type": "TextComparisonCondition",
            "field": {"type": "ValueField", "value": "arrivalDate"},
            "value": {"type": "ValueField", "value": _iso(arrival_to)[:10]},
            "method": "LESS_THAN_OR_EQUAL_TO",
        })
    if customer_name:
        conds.append(_and_text("customerName", customer_name, "EQUAL_TO"))
    if not conds:
        raise ValueError(
            "must supply at least one filter (date range or customer)"
        )

    body = {"condition": {"type": "AndCondition", "conditions": conds}}
    yield from client.post_search(
        "/inbound-orders/search",
        body,
        page_size=page_size,
        max_pages=max_pages,
    )


def search_warehouse_products(
    client: CartonCloudClient,
    *,
    customer_id: str | None = None,
    active_only: bool = True,
    page_size: int = 100,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate warehouse products. Returns full product incl. unitOfMeasures dims.

    This is what gives us carton dimensions (length/width/height/weight per UoM).
    """
    conds: list[dict] = []
    if customer_id:
        conds.append({
            "type": "TextComparisonCondition",
            "field": {"type": "JsonField", "pointer": "/customer/id"},
            "value": {"type": "ValueField", "value": customer_id},
            "method": "EQUAL_TO",
        })
    if active_only:
        conds.append({
            "type": "BooleanComparisonCondition",
            "field": {"type": "JsonField", "pointer": "/details/active"},
            "value": {"type": "ValueField", "value": "true"},
            "method": "EQUAL_TO",
        })

    # CC search requires a condition; if no filter, fall back to all-active.
    if not conds:
        conds.append({
            "type": "BooleanComparisonCondition",
            "field": {"type": "JsonField", "pointer": "/details/active"},
            "value": {"type": "ValueField", "value": "true"},
            "method": "EQUAL_TO",
        })

    body = {"condition": {"type": "AndCondition", "conditions": conds}}
    yield from client.post_search(
        "/warehouse-products/search",
        body,
        page_size=page_size,
        max_pages=max_pages,
    )


def get_stock_on_hand(
    client: CartonCloudClient,
    *,
    customer_id: str,
    aggregate_by: list[str] | None = None,
    poll_interval: float = 10.0,
    max_wait: float = 300.0,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Run a Stock-on-Hand report and block until complete, then collect all pages.

    SOH is async: POST creates a report run, then we poll GET until status is
    SUCCESS or FAILED. Returns the list of stock items.
    """
    aggregate_by = aggregate_by or [
        "productType", "inboundOrder", "unitOfMeasure", "productStatus",
    ]
    # POST is technically a write; allow temporarily for report runs.
    original_write = client.write_enabled
    client.write_enabled = True
    try:
        run = client._request(
            "POST",
            "/report-runs",
            json={
                "type": "STOCK_ON_HAND",
                "parameters": {
                    "pageSize": page_size,
                    "customer": {"id": customer_id},
                    "aggregateBy": aggregate_by,
                },
            },
        ).json()
    finally:
        client.write_enabled = original_write

    run_id = run["id"]
    log.info("started SOH report run %s", run_id)

    waited = 0.0
    delay = poll_interval
    while True:
        time.sleep(delay)
        waited += delay
        status_resp = client.get(f"/report-runs/{run_id}")
        status = status_resp.get("status")
        if status == "SUCCESS":
            break
        if status == "FAILED":
            raise CartonCloudError(
                f"SOH report run {run_id} failed: {status_resp}"
            )
        if waited >= max_wait:
            raise CartonCloudError(
                f"SOH report run {run_id} timed out after {max_wait}s"
            )
        # exponential backoff capped at 80s per CC docs recommendation
        delay = min(delay * 2, 80.0)

    # collect all pages of items
    items = list(status_resp.get("items", []))
    page = 2
    while True:
        page_resp = client.get(
            f"/report-runs/{run_id}",
            params={"page": page, "size": page_size},
        )
        page_items = page_resp.get("items", [])
        if not page_items:
            break
        items.extend(page_items)
        total_pages = page_resp.get("totalPages") or page_resp.get("Total-Pages")
        if total_pages and page >= int(total_pages):
            break
        if len(page_items) < page_size:
            break
        page += 1
    return items


def get_sku_locations(
    client: CartonCloudClient,
    *,
    customer_id: str,
    product_codes: list[str] | None = None,
    poll_interval: float = 10.0,
    max_wait: float = 300.0,
) -> list[dict[str, Any]]:
    """Resolve current SKU -> location bindings via CC stock-on-hand.

    Returns a list of ``{product_code, location_name, location_id, qty, uom}``
    dicts — one row per (product, location, unit-of-measure) bucket that
    SOH reports stock in. Use this as a fallback when an explicit
    assignment file isn't available for a SKU.

    ``product_codes`` is an optional filter — if supplied, only rows
    matching one of those codes are returned. CC's SOH endpoint doesn't
    support per-SKU filtering at the report level, so we filter
    client-side after fetching.

    Aggregates by ``location`` + ``productType`` so we get one row per
    location/product pair. (CC rejects ``warehouseLocation``/``product`` as
    aggregate dimensions with HTTP 422 — the accepted set is productStatus,
    productGroup, productType, unitOfMeasure, inboundOrder, batch,
    receivedWeek, sscc, sapLineNo, expiryDate, location.) Costs one SOH
    report run; uses the existing ``get_stock_on_hand`` plumbing (which polls
    until the report is SUCCESS) so it inherits its rate-limit and retry
    behaviour.
    """
    items = get_stock_on_hand(
        client,
        customer_id=customer_id,
        aggregate_by=["location", "productType", "unitOfMeasure"],
        poll_interval=poll_interval,
        max_wait=max_wait,
    )

    wanted = set(product_codes) if product_codes else None
    out: list[dict[str, Any]] = []
    for item in items:
        # SOH item shapes vary across CC versions; pull defensively. The
        # aggregated shape nests the SKU under details.product and the
        # location/uom under properties.* (verified live 2026-06-05).
        props = item.get("properties") or {}
        product = item.get("details", {}).get("product") or item.get("product") or {}
        product_code = (product.get("references") or {}).get("code") or product.get(
            "code"
        )
        if not product_code:
            continue
        if wanted is not None and product_code not in wanted:
            continue

        location = (
            props.get("location")
            or item.get("warehouseLocation")
            or item.get("location")
            or item.get("details", {}).get("warehouseLocation")
            or {}
        )
        location_name = (
            location.get("name")
            or (location.get("references") or {}).get("barcode")
            or location.get("code")
        )
        location_id = location.get("id")
        if not location_name and not location_id:
            continue

        uom = (
            props.get("unitOfMeasure")
            or item.get("unitOfMeasure")
            or item.get("details", {}).get("unitOfMeasure")
            or {}
        )
        measures = item.get("measures") or item.get("quantity") or {}
        qty = (
            measures.get("quantity")
            if isinstance(measures, dict)
            else measures
        )

        out.append({
            "product_code": product_code,
            "location_name": location_name,
            "location_id": location_id,
            "qty": qty,
            "uom_name": uom.get("name") or uom.get("type"),
        })
    log.info(
        "get_sku_locations: %d SOH rows mapped to %d unique SKUs across %d locations",
        len(out),
        len({r["product_code"] for r in out}),
        len({r["location_name"] for r in out if r["location_name"]}),
    )
    return out


def search_warehouse_locations(
    client: CartonCloudClient,
    *,
    warehouse_name: str | None = None,
    page_size: int = 100,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate warehouse locations. Returns location objects with bay/level/etc.

    May not be exposed on the public API — if so this raises CartonCloudError
    and the caller should fall back to the UI XLS export workflow.
    """
    conds: list[dict] = []
    if warehouse_name:
        conds.append({
            "type": "TextComparisonCondition",
            "field": {"type": "JsonField", "pointer": "/warehouse/name"},
            "value": {"type": "ValueField", "value": warehouse_name},
            "method": "EQUAL_TO",
        })

    # CC search requires a non-empty condition tree. If we have no filters,
    # match all by checking a field that always exists.
    if not conds:
        conds.append({
            "type": "TextComparisonCondition",
            "field": {"type": "JsonField", "pointer": "/type"},
            "value": {"type": "ValueField", "value": ""},
            "method": "NOT_EQUAL_TO",
        })

    body = {"condition": {"type": "AndCondition", "conditions": conds}}
    yield from client.post_search(
        "/warehouse-locations/search",
        body,
        page_size=page_size,
        max_pages=max_pages,
    )


def search_consignments(
    client: CartonCloudClient,
    *,
    run_sheet_date_from: date | datetime | str,
    page_size: int = 100,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate consignments whose run sheet is dated on/after a cutoff.

    Consignments are CC's source of truth for "what address went on what
    run": each carries the delivery address plus ``details.runsheet`` and
    ``details.deliveryRun``. ``runSheetDate`` is a ValueField search taking
    an ISO date (YYYY-MM-DD). Read-only despite the POST verb, like the
    other search helpers.
    """
    body = {
        "condition": {
            "type": "AndCondition",
            "conditions": [
                {
                    "type": "TextComparisonCondition",
                    "field": {"type": "ValueField", "value": "runSheetDate"},
                    "value": {
                        "type": "ValueField",
                        "value": _iso(run_sheet_date_from)[:10],
                    },
                    "method": "GREATER_THAN_OR_EQUAL_TO",
                }
            ],
        }
    }
    yield from client.post_search(
        "/consignments/search",
        body,
        page_size=page_size,
        max_pages=max_pages,
    )
