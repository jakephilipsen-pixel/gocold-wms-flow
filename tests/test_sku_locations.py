"""Regression test for get_sku_locations SOH aggregate dims + parsing.

Root cause (found live 2026-06-05): get_sku_locations asked CC to aggregate
Stock-on-Hand by ``warehouseLocation`` and ``product`` — both rejected with
HTTP 422. CC's valid dimensions are e.g. ``location`` and ``productType``.
On top of that, the location lives under ``item['properties']['location']``,
not ``item['warehouseLocation']``. Either bug alone makes the SOH-based
location fallback return nothing, so wave generation skips every order with
"missing pick location for SKU(s)" — the "no stock locations" symptom.

Runs fully offline: ``get_stock_on_hand`` is monkeypatched so no network.
"""
from __future__ import annotations

import cc_client.queries as queries
from cc_client.queries import get_sku_locations

# A real CC SOH item, captured live under the corrected aggregate dims
# [location, productType, unitOfMeasure].
_REAL_SOH_ITEM = {
    "properties": {
        "location": {
            "id": "43569343-9323-46c1-8973-769774789d70",
            "references": {"numericId": "2", "barcode": "Staging Area"},
            "name": "Staging Area",
        },
        "productType": "AMBIENT",
        "unitOfMeasure": {"type": "EA", "name": "Each"},
        "productStatus": "OK",
    },
    "measures": {"quantity": 27, "quantityFree": 27},
    "type": "ITEM",
    "details": {
        "product": {
            "id": "fde79f2b-c800-487e-8c4a-8a90f846386f",
            "references": {"code": "AE-BAL"},
            "name": "AE - Almond Blackout",
        },
        "unitOfMeasure": {"type": "EA", "name": "Each"},
    },
}

# The set CC's 422 error enumerates as valid aggregateBy dimensions.
_CC_ACCEPTED_DIMS = {
    "productStatus", "productGroup", "productType", "unitOfMeasure",
    "inboundOrder", "batch", "receivedWeek", "sscc", "sapLineNo",
    "expiryDate", "location",
}


def test_requests_only_cc_accepted_aggregate_dims(monkeypatch):
    captured: dict = {}

    def fake_soh(client, *, customer_id, aggregate_by=None, **kw):
        captured["aggregate_by"] = aggregate_by
        return []

    monkeypatch.setattr(queries, "get_stock_on_hand", fake_soh)
    get_sku_locations(client=object(), customer_id="cust")

    assert captured["aggregate_by"] is not None
    bad = set(captured["aggregate_by"]) - _CC_ACCEPTED_DIMS
    assert not bad, f"CC rejects these aggregate dims: {bad}"
    assert "location" in captured["aggregate_by"], "must split by location"


def test_parses_real_soh_item_shape(monkeypatch):
    monkeypatch.setattr(
        queries, "get_stock_on_hand", lambda *a, **k: [_REAL_SOH_ITEM]
    )
    rows = get_sku_locations(client=object(), customer_id="cust")

    assert len(rows) == 1, "real SOH item must not be dropped on parse"
    row = rows[0]
    assert row["product_code"] == "AE-BAL"
    assert row["location_name"] == "Staging Area"
    assert row["location_id"] == "43569343-9323-46c1-8973-769774789d70"
    assert row["qty"] == 27
    assert row["uom_name"] == "Each"


def test_product_code_filter_still_applies(monkeypatch):
    monkeypatch.setattr(
        queries, "get_stock_on_hand", lambda *a, **k: [_REAL_SOH_ITEM]
    )
    # Filtering to a different code yields nothing; to the right code yields it.
    assert get_sku_locations(
        client=object(), customer_id="c", product_codes=["NOPE"]) == []
    assert len(get_sku_locations(
        client=object(), customer_id="c", product_codes=["AE-BAL"])) == 1
