"""SOH rows → per-SKU location candidates with role + qty.

The carton-aware picker needs every live location per SKU (pick faces
AND reserves), not just the single best one. Grammar refresher:
AA-01-01 / AA-01-02 are pick faces; AA-01-03+ is reserve.
"""
from __future__ import annotations

from wave_runner import build_sku_location_candidates, build_sku_locations_from_soh


def _items():
    return [
        {"product_code": "FD-BAR", "location_name": "AA-01-03",
         "location_id": "x1", "qty": 120, "uom_name": "Each"},
        {"product_code": "FD-BAR", "location_name": "AA-01-01",
         "location_id": "x2", "qty": 18, "uom_name": "Each"},
        {"product_code": "FD-BAR", "location_name": "AB-02-03",
         "location_id": "x3", "qty": 60, "uom_name": "Each"},
    ]


def test_candidates_keep_every_location_best_first():
    df = build_sku_location_candidates(_items())
    assert len(df) == 3
    assert df.iloc[0]["location"] == "AA-01-01"          # pick face leads
    assert df.iloc[0]["role"] == "pick_face"
    assert df.iloc[0]["qty"] == 18
    assert list(df["role"][1:]) == ["reserve", "reserve"]
    assert {"product_code", "location", "aisle", "bay", "level",
            "sublevel", "role", "qty"} <= set(df.columns)
    assert df["location"].tolist() == ["AA-01-01", "AA-01-03", "AB-02-03"]
    assert df["qty"].dtype == "float64"


def test_single_location_wrapper_unchanged():
    df = build_sku_locations_from_soh(_items())
    assert len(df) == 1
    assert df.iloc[0]["location"] == "AA-01-01"


def test_unparseable_location_treated_as_reserve():
    items = [{"product_code": "X", "location_name": "FLOOR-STAGING",
              "location_id": "y", "qty": 5, "uom_name": "Each"}]
    df = build_sku_location_candidates(items)
    assert len(df) == 1
    assert df.iloc[0]["role"] == "reserve"


def test_empty_items_returns_empty_frame():
    df = build_sku_location_candidates([])
    assert df.empty
    assert "role" in df.columns and "qty" in df.columns


def test_unparseable_qty_coerces_to_nan_not_object():
    items = [{"product_code": "X", "location_name": "AA-01-01",
              "location_id": "y", "qty": "n/a", "uom_name": "Each"}]
    df = build_sku_location_candidates(items)
    assert df["qty"].dtype == "float64"
    assert df["qty"].isna().all()
