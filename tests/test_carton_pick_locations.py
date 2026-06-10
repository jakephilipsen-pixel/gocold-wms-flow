"""Carton-aware location selection + consolidation in wave generation.

CTN lines must route to the largest-qty reserve; EA lines keep the
pick-face-first behaviour; the two never merge into one pick row.
Scaffold mirrors tests/test_wave_consolidation.py.
"""
from __future__ import annotations

import pandas as pd

from analysis.routing import STREAM_BENCH, StreamClassification
from analysis.wave_picks import generate_wave_pick_sheets

_TS = "2026-06-11T10:00:00+10:00"


def _classification(per_order):
    return StreamClassification(
        per_order=per_order,
        counts_by_stream=pd.Series(dtype=int),
        rule_hit_counts=pd.Series(dtype=int),
        threshold_used=0.0,
    )


def _order_row(so_id, so_ref):
    return {
        "so_id": so_id, "so_ref": so_ref, "stream": STREAM_BENCH,
        "total_cartons": 5, "line_count": 2, "ts_packed": _TS,
        "delivery_state": "VIC", "customer_name": "The Forage Company",
        "delivery_company": f"Shop {so_ref}", "delivery_suburb": "Scoresby",
        "delivery_postcode": "3179",
    }


def _sku_locations():
    """FD-BAR: pick face + two reserves (AB-04-03 holds the most).
    PFONLY: stock at the pick face only."""
    return pd.DataFrame([
        {"product_code": "FD-BAR", "location": "AA-01-01", "aisle": "AA",
         "bay": 1, "level": 1, "sublevel": None, "role": "pick_face", "qty": 30},
        {"product_code": "FD-BAR", "location": "AA-01-03", "aisle": "AA",
         "bay": 1, "level": 3, "sublevel": None, "role": "reserve", "qty": 60},
        {"product_code": "FD-BAR", "location": "AB-04-03", "aisle": "AB",
         "bay": 4, "level": 3, "sublevel": None, "role": "reserve", "qty": 120},
        {"product_code": "PFONLY", "location": "AA-02-01", "aisle": "AA",
         "bay": 2, "level": 1, "sublevel": None, "role": "pick_face", "qty": 50},
    ])


def _run(so_lines):
    per_order = pd.DataFrame([_order_row(1, "SO-A")])
    return generate_wave_pick_sheets(
        classification=_classification(per_order),
        so_lines=so_lines,
        sku_locations=_sku_locations(),
        early_release_cartons=10_000,
    )


def _line(code, qty, pick_uom, qty_eaches=None):
    return {"so_id": 1, "product_code": code, "product_name": code,
            "quantity": qty, "pick_uom": pick_uom,
            "qty_eaches": qty_eaches if qty_eaches is not None else pd.NA}


def test_ctn_line_routes_to_largest_reserve():
    res = _run(pd.DataFrame([_line("FD-BAR", 4, "CTN", 24)]))
    picks = res.sheets[0].pick_lines
    assert len(picks) == 1
    row = picks.iloc[0]
    assert row["location"] == "AB-04-03"
    assert row["pick_uom"] == "CTN"
    assert row["qty_cartons"] == 4
    assert row["qty_eaches"] == 24
    assert not row["reserve_unavailable"]


def test_ea_line_keeps_pick_face():
    res = _run(pd.DataFrame([_line("FD-BAR", 3, "EA")]))
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AA-01-01"
    assert row["pick_uom"] == "EA"


def test_ctn_and_ea_of_same_sku_stay_separate_rows():
    res = _run(pd.DataFrame([
        _line("FD-BAR", 4, "CTN", 24),
        _line("FD-BAR", 3, "EA"),
    ]))
    picks = res.sheets[0].pick_lines
    assert len(picks) == 2
    assert set(picks["pick_uom"]) == {"CTN", "EA"}
    assert set(picks["location"]) == {"AB-04-03", "AA-01-01"}


def test_pick_face_only_sku_falls_back_with_flag():
    res = _run(pd.DataFrame([_line("PFONLY", 2, "CTN", 12)]))
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AA-02-01"
    assert bool(row["reserve_unavailable"]) is True
    assert res.summary["n_carton_picks_no_reserve"] == 1


def test_reserve_short_of_stock_is_flagged():
    # needs 240 eaches; biggest reserve holds 120
    res = _run(pd.DataFrame([_line("FD-BAR", 40, "CTN", 240)]))
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AB-04-03"
    assert bool(row["qty_short"]) is True


def test_summary_counts_carton_lines():
    res = _run(pd.DataFrame([
        _line("FD-BAR", 4, "CTN", 24),
        _line("FD-BAR", 3, "EA"),
    ]))
    assert res.summary["n_lines_carton_pick"] == 1
    assert res.summary["n_carton_picks_no_reserve"] == 0


def test_legacy_frames_without_uom_or_role_still_work():
    """Zero-breakage guarantee: no pick_uom column + no role/qty column
    must reproduce today's behaviour (first location, EA, no flags)."""
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "FD-BAR",
         "product_name": "Bar", "quantity": 5},
    ])
    sku_locations = pd.DataFrame([
        {"product_code": "FD-BAR", "location": "AA-01-01", "aisle": "AA",
         "bay": 1, "level": 1, "sublevel": None},
    ])
    per_order = pd.DataFrame([_order_row(1, "SO-A")])
    res = generate_wave_pick_sheets(
        classification=_classification(per_order),
        so_lines=so_lines, sku_locations=sku_locations,
        early_release_cartons=10_000,
    )
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AA-01-01"
    assert row["pick_uom"] == "EA"
    assert row["qty_cartons"] == 5
    assert res.summary["n_lines_carton_pick"] == 0
