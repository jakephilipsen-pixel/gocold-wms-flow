"""Regression guard for wave pick consolidation (AUDIT R5).

The wave generator's core promise to the picker: within one wave, the same
SKU picked for several orders collapses to ONE walk-down-the-page line with
the quantities summed and the contributing order refs listed. Get this wrong
and the floor either double-picks or short-picks — exactly the breakage
CLAUDE.md says we cannot ship.

These tests drive ``generate_wave_pick_sheets`` with tiny hand-built frames
(no API, no files) and assert the consolidation maths and the whole-order
skip behaviour.
"""
from __future__ import annotations

import pandas as pd
import pytest

from analysis.routing import STREAM_BENCH, StreamClassification
from analysis.wave_picks import generate_wave_pick_sheets

# Same packed timestamp/day + same delivery_state + same stream => the two
# orders land in a single wave (with early_release high enough not to split).
_TS = "2026-05-17T10:00:00+10:00"


def _classification(per_order: pd.DataFrame) -> StreamClassification:
    return StreamClassification(
        per_order=per_order,
        counts_by_stream=pd.Series(dtype=int),
        rule_hit_counts=pd.Series(dtype=int),
        threshold_used=0.0,
    )


def _order_row(so_id, so_ref, cartons, lines):
    return {
        "so_id": so_id,
        "so_ref": so_ref,
        "stream": STREAM_BENCH,
        "total_cartons": cartons,
        "line_count": lines,
        "ts_packed": _TS,
        "delivery_state": "VIC",
        "customer_name": "The Forage Company",
        "delivery_company": f"Shop {so_ref}",
        "delivery_suburb": "Scoresby",
        "delivery_postcode": "3179",
    }


def _sku_locations():
    return pd.DataFrame([
        {"product_code": "WIDGET", "location": "A-01-1",
         "aisle": "A", "bay": "01", "level": "1", "sublevel": "0"},
        {"product_code": "GADGET", "location": "A-02-1",
         "aisle": "A", "bay": "02", "level": "1", "sublevel": "0"},
        {"product_code": "ZEBRA", "location": "C-09-1",
         "aisle": "C", "bay": "09", "level": "1", "sublevel": "0"},
    ])


def _run(per_order, so_lines, **kw):
    return generate_wave_pick_sheets(
        classification=_classification(per_order),
        so_lines=so_lines,
        sku_locations=_sku_locations(),
        early_release_cartons=10_000,      # keep all orders in one wave
        **kw,
    )


def test_same_sku_across_orders_is_summed():
    """WIDGET in two orders -> one line, qty summed, both refs listed."""
    per_order = pd.DataFrame([
        _order_row(1, "SO-A", cartons=7, lines=2),
        _order_row(2, "SO-B", cartons=3, lines=1),
    ])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 5},
        {"so_id": 1, "product_code": "GADGET", "product_name": "Gadget", "quantity": 2},
        {"so_id": 2, "product_code": "WIDGET", "product_name": "Widget", "quantity": 3},
    ])

    result = _run(per_order, so_lines)

    assert len(result.sheets) == 1
    sheet = result.sheets[0]
    picks = sheet.pick_lines.set_index("product_code")

    # WIDGET: 5 + 3 = 8, contributed by both orders.
    assert picks.loc["WIDGET", "qty_cartons"] == 8
    refs = picks.loc["WIDGET", "contributing_so_refs"]
    assert set(r.strip() for r in refs.split(",")) == {"SO-A", "SO-B"}

    # GADGET: single order, untouched.
    assert picks.loc["GADGET", "qty_cartons"] == 2
    assert picks.loc["GADGET", "contributing_so_refs"] == "SO-A"


def test_distinct_skus_stay_separate_rows():
    per_order = pd.DataFrame([_order_row(1, "SO-A", cartons=4, lines=2)])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 1},
        {"so_id": 1, "product_code": "GADGET", "product_name": "Gadget", "quantity": 3},
    ])

    sheet = _run(per_order, so_lines).sheets[0]

    assert set(sheet.pick_lines["product_code"]) == {"WIDGET", "GADGET"}
    assert len(sheet.pick_lines) == 2


def test_totals_match_consolidated_lines():
    per_order = pd.DataFrame([
        _order_row(1, "SO-A", cartons=7, lines=2),
        _order_row(2, "SO-B", cartons=3, lines=1),
    ])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 5},
        {"so_id": 1, "product_code": "GADGET", "product_name": "Gadget", "quantity": 2},
        {"so_id": 2, "product_code": "WIDGET", "product_name": "Widget", "quantity": 3},
    ])

    sheet = _run(per_order, so_lines).sheets[0]

    # 8 WIDGET + 2 GADGET = 10 cartons across 2 consolidated lines.
    assert sheet.total_cartons == 10
    assert sheet.total_lines == 2
    assert int(sheet.pick_lines["qty_cartons"].sum()) == sheet.total_cartons


def test_walk_index_is_sequential_and_sorted():
    """Picks are pre-numbered 1..N in aisle walk order."""
    per_order = pd.DataFrame([_order_row(1, "SO-A", cartons=3, lines=2)])
    so_lines = pd.DataFrame([
        # ZEBRA is aisle C, WIDGET aisle A — output must put A before C.
        {"so_id": 1, "product_code": "ZEBRA", "product_name": "Zebra", "quantity": 1},
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 2},
    ])

    sheet = _run(per_order, so_lines).sheets[0]

    assert list(sheet.pick_lines["walk_index"]) == [1, 2]
    assert list(sheet.pick_lines["aisle"]) == ["A", "C"]
    # Running total accumulates in walk order: 2 then 2+1.
    assert list(sheet.pick_lines["cartons_running_total"]) == [2, 3]


def test_order_with_unlocatable_sku_is_flagged_not_skipped():
    """A SKU with no live location does NOT skip the order — its line rides
    the wave flagged 'unallocated'. The order's other lines pick normally."""
    per_order = pd.DataFrame([
        _order_row(1, "SO-A", cartons=2, lines=2),
        _order_row(2, "SO-B", cartons=1, lines=1),
    ])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 1},
        {"so_id": 1, "product_code": "UNKNOWN", "product_name": "Mystery", "quantity": 1},
        {"so_id": 2, "product_code": "WIDGET", "product_name": "Widget", "quantity": 1},
    ])

    result = _run(per_order, so_lines)

    # No order is skipped for a missing location.
    assert result.skipped_orders.empty
    assert result.summary["n_skus_unallocated"] == 1
    assert result.summary["n_lines_unallocated"] == 1

    sheet = result.sheets[0]
    picks = sheet.pick_lines.set_index("product_code")
    # WIDGET is located and summed across SO-A + SO-B.
    assert picks.loc["WIDGET", "qty_cartons"] == 2
    assert bool(picks.loc["WIDGET", "unallocated"]) is False
    # UNKNOWN rides the wave, flagged, with no real location.
    assert picks.loc["UNKNOWN", "location"] == "UNALLOCATED"
    assert bool(picks.loc["UNKNOWN", "unallocated"]) is True


def test_unallocated_lines_sort_to_the_end_of_the_walk():
    per_order = pd.DataFrame([_order_row(1, "SO-A", cartons=3, lines=2)])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "UNKNOWN", "product_name": "Mystery", "quantity": 1},
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 2},
    ])
    sheet = _run(per_order, so_lines).sheets[0]
    # WIDGET (located) is walked first; UNKNOWN (unallocated) is last.
    assert list(sheet.pick_lines["product_code"]) == ["WIDGET", "UNKNOWN"]
    assert list(sheet.pick_lines["unallocated"]) == [False, True]


def test_zero_and_negative_quantities_are_dropped():
    """Junk qty lines never produce a pick instruction."""
    per_order = pd.DataFrame([_order_row(1, "SO-A", cartons=2, lines=2)])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 2},
        {"so_id": 1, "product_code": "GADGET", "product_name": "Gadget", "quantity": 0},
    ])

    sheet = _run(per_order, so_lines).sheets[0]

    assert list(sheet.pick_lines["product_code"]) == ["WIDGET"]
