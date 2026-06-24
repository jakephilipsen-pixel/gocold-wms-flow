"""Captured-dims → CartonCloud unit boundary (M-DIMS units fix → METRES, 24 Jun 2026).

The capture template measures cartons in MILLIMETRES; CartonCloud's UoM length/width/height
are METRES (Jake, confirmed against the CC UI volume field 24 Jun 2026 — a carton reading
~1200 m³ means the linear dims were stored 1000× too large; this supersedes BOTH the earlier
"mm" assumption AND the 23 Jun "cm" read that PR #26 wrongly encoded as ÷10). So at the ONE
boundary where captured dims become the values PATCHed to CC, L/W/H are divided by 1000 and
weight (kg) is left alone. These tests pin that conversion and the fully-measured filter that
all the dims-write scripts share.
"""
from __future__ import annotations

import math

import pandas as pd

from dims_write.capture import mm_to_m, captured_cc_dims_table, MM_PER_METRE


def test_mm_per_metre_is_1000():
    assert MM_PER_METRE == 1000.0


def test_mm_to_m_divides_by_1000():
    assert mm_to_m(255) == 0.255
    assert mm_to_m(1000) == 1.0
    assert mm_to_m(247) == 0.247
    assert mm_to_m(0) == 0.0


def test_mm_to_m_passes_through_none_and_nan():
    assert mm_to_m(None) is None
    assert mm_to_m(float("nan")) is None


def _df(rows):
    return pd.DataFrame(rows)


def test_table_converts_lwh_to_m_and_keeps_weight_kg():
    df = _df([
        {"product_code": "RK-001", "outer_l_mm": 255, "outer_w_mm": 230,
         "outer_h_mm": 150, "outer_weight_kg": 2.2},
    ])
    table = captured_cc_dims_table(df)
    assert table["RK-001"] == {"length": 0.255, "width": 0.23, "height": 0.15, "weight": 2.2}


def test_table_drops_rows_missing_any_lwh():
    df = _df([
        {"product_code": "FULL", "outer_l_mm": 300, "outer_w_mm": 200,
         "outer_h_mm": 100, "outer_weight_kg": 1.0},
        {"product_code": "NO-H", "outer_l_mm": 300, "outer_w_mm": 200,
         "outer_h_mm": float("nan"), "outer_weight_kg": 1.0},
    ])
    table = captured_cc_dims_table(df)
    assert "FULL" in table
    assert "NO-H" not in table


def test_table_keeps_row_with_missing_weight_only():
    # Weight is ~69% populated; a missing weight must NOT drop the SKU — L/W/H still write.
    df = _df([
        {"product_code": "NO-WT", "outer_l_mm": 300, "outer_w_mm": 200,
         "outer_h_mm": 100, "outer_weight_kg": float("nan")},
    ])
    table = captured_cc_dims_table(df)
    assert table["NO-WT"]["length"] == 0.3
    assert table["NO-WT"]["weight"] is None or math.isnan(table["NO-WT"]["weight"])
