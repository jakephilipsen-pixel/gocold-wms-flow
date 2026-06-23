"""Captured-dims → CartonCloud unit boundary (M-DIMS units fix, 23 Jun 2026).

The capture template measures cartons in MILLIMETRES; CartonCloud's UoM length/width/height
are CENTIMETRES (Jake, confirmed against the CC UI 23 Jun 2026). So at the ONE boundary where
captured dims become the values PATCHed to CC, L/W/H are divided by 10 and weight (kg) is left
alone. These tests pin that conversion and the fully-measured filter that all the dims-write
scripts share.
"""
from __future__ import annotations

import math

import pandas as pd

from dims_write.capture import mm_to_cm, captured_cc_dims_table, MM_PER_CM


def test_mm_per_cm_is_ten():
    assert MM_PER_CM == 10.0


def test_mm_to_cm_divides_by_ten():
    assert mm_to_cm(255) == 25.5
    assert mm_to_cm(1000) == 100.0
    assert mm_to_cm(247) == 24.7
    assert mm_to_cm(0) == 0.0


def test_mm_to_cm_passes_through_none_and_nan():
    assert mm_to_cm(None) is None
    assert mm_to_cm(float("nan")) is None


def _df(rows):
    return pd.DataFrame(rows)


def test_table_converts_lwh_to_cm_and_keeps_weight_kg():
    df = _df([
        {"product_code": "RK-001", "outer_l_mm": 255, "outer_w_mm": 230,
         "outer_h_mm": 150, "outer_weight_kg": 2.2},
    ])
    table = captured_cc_dims_table(df)
    assert table["RK-001"] == {"length": 25.5, "width": 23.0, "height": 15.0, "weight": 2.2}


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
    assert table["NO-WT"]["length"] == 30.0
    assert table["NO-WT"]["weight"] is None or math.isnan(table["NO-WT"]["weight"])
