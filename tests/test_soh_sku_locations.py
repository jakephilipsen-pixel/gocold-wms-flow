"""Unit tests for build_sku_locations_from_soh (SOH -> pick lookup)."""
from __future__ import annotations

import pandas as pd

from wave_runner import build_sku_locations_from_soh


def _row(code, loc, qty=10):
    # Shape returned by cc_client.get_sku_locations.
    return {"product_code": code, "location_name": loc,
            "location_id": f"id-{loc}", "qty": qty, "uom": "EA"}


def test_parses_grammar_into_walk_columns():
    df = build_sku_locations_from_soh([_row("WIDGET", "AA-05-01")])
    row = df.set_index("product_code").loc["WIDGET"]
    assert row["location"] == "AA-05-01"
    assert row["aisle"] == "AA"
    assert int(row["bay"]) == 5
    assert int(row["level"]) == 1


def test_prefers_pick_face_over_reserve():
    # AA-05-03 is reserve (level 3); AA-05-01 is a pick face (level 1).
    df = build_sku_locations_from_soh([
        _row("WIDGET", "AA-05-03"),
        _row("WIDGET", "AA-05-01"),
    ])
    assert df.set_index("product_code").loc["WIDGET", "location"] == "AA-05-01"


def test_lowest_position_wins_among_pick_faces():
    # position 1 (level 01) beats position 2 (level 02).
    df = build_sku_locations_from_soh([
        _row("WIDGET", "AA-05-02"),
        _row("WIDGET", "AA-05-01"),
    ])
    assert df.set_index("product_code").loc["WIDGET", "location"] == "AA-05-01"


def test_reserve_only_sku_still_resolves():
    # No pick face anywhere -> take the reserve (real, live location).
    df = build_sku_locations_from_soh([_row("WIDGET", "AA-05-04")])
    assert df.set_index("product_code").loc["WIDGET", "location"] == "AA-05-04"


def test_one_row_per_sku():
    df = build_sku_locations_from_soh([
        _row("WIDGET", "AA-05-01"),
        _row("WIDGET", "AA-06-01"),
        _row("GADGET", "BB-01-01"),
    ])
    assert sorted(df["product_code"]) == ["GADGET", "WIDGET"]


def test_empty_input_returns_empty_frame_with_columns():
    df = build_sku_locations_from_soh([])
    assert list(df.columns) == [
        "product_code", "location", "aisle", "bay", "level", "sublevel"]
    assert df.empty


def test_unparseable_location_kept_with_na_walk_fields():
    df = build_sku_locations_from_soh([_row("WIDGET", "BULK-FLOOR")])
    row = df.set_index("product_code").loc["WIDGET"]
    assert row["location"] == "BULK-FLOOR"
    assert pd.isna(row["aisle"])
