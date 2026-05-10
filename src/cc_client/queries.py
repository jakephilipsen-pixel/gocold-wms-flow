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
    page_size: int = 100,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate sale orders, optionally filtered by pack date range and customer.

    Returns full order objects including items[] with measures.quantity per line.
    """
    conds: list[dict] = []
    conds.extend(_date_range_condition(
        "/timestamps/packed/time", packed_from, packed_to,
    ))
    if customer_name:
        conds.append(_and_text("customerName", customer_name, "EQUAL_TO"))

    if not conds:
        # safety: CC search may reject empty conditions; force at least one
        raise ValueError(
            "must supply at least one filter (date range or customer)"
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
