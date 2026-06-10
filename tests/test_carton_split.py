"""Unit tests for the each→carton line splitter (carton-aware picks).

73 of Forage's SKUs are each/ctn combos (inner_pack_qty 2–12 eaches per
carton). When an EA line spans one or more full cartons the picker grabs
cartons off the reserve pallet, so the picksheet must say cartons —
these tests pin the conversion maths and the pass-through guarantees.
"""
from __future__ import annotations

import pandas as pd

from analysis.carton_split import PICK_UOM_CARTON, PICK_UOM_EACH, split_lines


def _dims(rows):
    return pd.DataFrame(rows, columns=["product_code", "inner_pack_qty"])


def _lines(rows):
    return pd.DataFrame(
        rows, columns=["so_id", "product_code", "product_name", "quantity"]
    )


def test_exact_multiple_becomes_single_carton_line():
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 24)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 1
    row = out.iloc[0]
    assert row["pick_uom"] == PICK_UOM_CARTON
    assert row["quantity"] == 4
    assert row["qty_eaches"] == 24


def test_remainder_splits_into_ctn_plus_ea():
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 27)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 2
    ctn = out[out["pick_uom"] == PICK_UOM_CARTON].iloc[0]
    ea = out[out["pick_uom"] == PICK_UOM_EACH].iloc[0]
    assert ctn["quantity"] == 4
    assert ctn["qty_eaches"] == 24
    assert ea["quantity"] == 3
    assert pd.isna(ea["qty_eaches"])


def test_under_one_carton_passes_through():
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 5)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH
    assert out.iloc[0]["quantity"] == 5
    assert pd.isna(out.iloc[0]["qty_eaches"])


def test_inner_pack_qty_one_passes_through():
    """334 SKUs have ipq=1 (the each IS the carton) — never converted."""
    out = split_lines(_lines([(1, "FRG-01", "Oats", 24)]), _dims([("FRG-01", 1)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH
    assert out.iloc[0]["quantity"] == 24


def test_sku_missing_from_dims_passes_through():
    out = split_lines(_lines([(1, "MYSTERY", "?", 24)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH


def test_min_full_cartons_raises_the_bar():
    lines = _lines([(1, "FD-BAR", "Bar", 24), (2, "FD-BAR", "Bar", 6)])
    out = split_lines(lines, _dims([("FD-BAR", 6)]), min_full_cartons=2)
    by_so = out.set_index("so_id")
    assert by_so.loc[1, "pick_uom"] == PICK_UOM_CARTON   # 4 ctns >= 2
    assert by_so.loc[2, "pick_uom"] == PICK_UOM_EACH     # 1 ctn < 2


def test_none_or_empty_dims_passes_everything_through():
    lines = _lines([(1, "FD-BAR", "Bar", 24)])
    for dims in (None, pd.DataFrame()):
        out = split_lines(lines, dims)
        assert len(out) == 1
        assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH


def test_other_columns_survive_the_split():
    lines = _lines([(1, "FD-BAR", "Bar", 27)]).assign(so_ref="SO-77", batch="B1")
    out = split_lines(lines, _dims([("FD-BAR", 6)]))
    assert set(out["so_ref"]) == {"SO-77"}
    assert set(out["batch"]) == {"B1"}


def test_fractional_quantity_is_not_converted_and_nothing_is_lost():
    """qty=24.5 @ ipq=6 must NOT silently drop 0.5 EA — line passes through."""
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 24.5)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH
    assert out.iloc[0]["quantity"] == 24.5


def test_fractional_inner_pack_qty_is_not_converted():
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 27)]), _dims([("FD-BAR", 6.4)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH


def test_each_conservation_across_the_split():
    """Invariant: total eaches in == CTN qty_eaches + EA quantities out."""
    lines = _lines([
        (1, "FD-BAR", "Bar", 27),    # 4 CTN (24) + 3 EA
        (1, "TSP-SAR", "Sar", 8),    # 2 CTN (8)
        (1, "FRG-01", "Oats", 9),    # passthrough EA
    ])
    out = split_lines(lines, _dims([("FD-BAR", 6), ("TSP-SAR", 4), ("FRG-01", 1)]))
    eaches_out = (
        out.loc[out["pick_uom"] == PICK_UOM_CARTON, "qty_eaches"].sum()
        + out.loc[out["pick_uom"] == PICK_UOM_EACH, "quantity"].sum()
    )
    assert eaches_out == 27 + 8 + 9


def test_input_row_order_is_preserved():
    """Converted lines stay in place; the EA remainder follows its CTN line."""
    lines = _lines([
        (1, "AAA-01", "A", 2),       # passthrough
        (1, "FD-BAR", "Bar", 27),    # splits in place: CTN then EA
        (1, "ZZZ-09", "Z", 3),       # passthrough
    ])
    out = split_lines(lines, _dims([("FD-BAR", 6)]))
    assert list(out["product_code"]) == ["AAA-01", "FD-BAR", "FD-BAR", "ZZZ-09"]
    assert list(out["pick_uom"]) == ["EA", "CTN", "EA", "EA"]
