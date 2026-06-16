from __future__ import annotations

import pandas as pd

from analysis.dims_worklist import (
    build_worklist,
    captured_not_in_cc,
    WORKLIST_COLUMNS,
    _classify,
)


def _dims(rows):
    """Build a load_dimensions-shaped frame from dicts."""
    cols = ["product_code", "outer_l_mm", "outer_w_mm", "outer_h_mm",
            "outer_weight_kg", "inner_pack_qty"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows], columns=cols)


def _prod(code, name, uoms):
    return {"id": f"id-{code}", "references": {"code": code},
            "name": name, "unitOfMeasures": uoms}


def test_classify_inner_carton_unknown():
    assert _classify(1) == "inner"
    assert _classify(12) == "carton"
    assert _classify(float("nan")) == "unknown"
    assert _classify(None) == "unknown"
    assert _classify(0) == "unknown"


def test_inner_sku_maps_to_each_uom():
    dims = _dims([{"product_code": "AE-BLA", "outer_l_mm": 50, "outer_w_mm": 40,
                   "outer_h_mm": 30, "outer_weight_kg": 0.2, "inner_pack_qty": 1}])
    prods = [_prod("AE-BLA", "Dark Blackout",
                   {"EA": {"baseQty": 1}, "PLT": {"baseQty": 576}})]
    wl = build_worklist(dims, prods)
    row = wl.iloc[0]
    assert list(wl.columns) == WORKLIST_COLUMNS
    assert row["kind"] == "inner"
    assert row["carton_uom_code"] == "EA"     # inner → the baseQty==1 measure
    assert row["ea_uom_code"] == "EA"
    assert row["cc_product_id"] == "id-AE-BLA"
    assert bool(row["no_carton_uom"]) is False


def test_carton_sku_matches_baseqty_to_innerpack():
    dims = _dims([{"product_code": "BX-12", "outer_l_mm": 300, "outer_w_mm": 200,
                   "outer_h_mm": 150, "outer_weight_kg": 6.0, "inner_pack_qty": 12}])
    prods = [_prod("BX-12", "Box of 12",
                   {"EA": {"baseQty": 1}, "CT": {"baseQty": 12}, "PLT": {"baseQty": 576}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["kind"] == "carton"
    assert row["carton_uom_code"] == "CT"
    assert row["carton_baseqty"] == 12
    assert row["ea_uom_code"] == "EA"


def test_no_carton_uom_flag_when_baseqty_absent():
    # ipq=6 but no UoM has baseQty 6 → cannot locate carton measure
    dims = _dims([{"product_code": "ODD", "outer_l_mm": 1, "outer_w_mm": 1,
                   "outer_h_mm": 1, "outer_weight_kg": 1, "inner_pack_qty": 6}])
    prods = [_prod("ODD", "Odd", {"EA": {"baseQty": 1}, "CT": {"baseQty": 12}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["carton_uom_code"] == ""
    assert bool(row["no_carton_uom"]) is True


def test_code_match_is_trim_and_case_insensitive():
    dims = _dims([{"product_code": " ae-bla ", "outer_l_mm": 1, "outer_w_mm": 1,
                   "outer_h_mm": 1, "outer_weight_kg": 1, "inner_pack_qty": 1}])
    prods = [_prod("AE-BLA", "x", {"EA": {"baseQty": 1}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["kind"] == "inner"
    assert row["not_captured"] == False  # matched despite whitespace/case


def test_weight_pending_when_weight_missing():
    dims = _dims([{"product_code": "NOWT", "outer_l_mm": 10, "outer_w_mm": 10,
                   "outer_h_mm": 10, "outer_weight_kg": float("nan"),
                   "inner_pack_qty": 1}])
    prods = [_prod("NOWT", "no weight", {"EA": {"baseQty": 1}})]
    row = build_worklist(dims, prods).iloc[0]
    assert bool(row["weight_pending"]) is True


def test_cc_product_without_captured_dims_is_not_captured_and_unknown():
    dims = _dims([])  # nothing captured
    prods = [_prod("NEW-SKU", "brand new", {"EA": {"baseQty": 1}})]
    row = build_worklist(dims, prods).iloc[0]
    assert bool(row["not_captured"]) is True
    assert row["kind"] == "unknown"
    assert bool(row["ipq_unknown"]) is True
    assert bool(row["weight_pending"]) is True


def test_blank_inner_pack_qty_is_unknown():
    dims = _dims([{"product_code": "BLANK", "outer_l_mm": 1, "outer_w_mm": 1,
                   "outer_h_mm": 1, "outer_weight_kg": 1,
                   "inner_pack_qty": float("nan")}])
    prods = [_prod("BLANK", "x", {"EA": {"baseQty": 1}, "CT": {"baseQty": 12}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["kind"] == "unknown"
    assert bool(row["ipq_unknown"]) is True
    assert bool(row["no_carton_uom"]) is False  # unknown kind doesn't demand a carton UoM


def test_captured_not_in_cc_lists_orphans():
    dims = _dims([
        {"product_code": "IN-CC", "outer_l_mm": 1, "outer_w_mm": 1, "outer_h_mm": 1,
         "outer_weight_kg": 1, "inner_pack_qty": 1},
        {"product_code": "GONE", "outer_l_mm": 1, "outer_w_mm": 1, "outer_h_mm": 1,
         "outer_weight_kg": 1, "inner_pack_qty": 1},
    ])
    prods = [_prod("IN-CC", "x", {"EA": {"baseQty": 1}})]
    assert captured_not_in_cc(dims, prods) == ["GONE"]


def test_row_count_equals_cc_product_count():
    dims = _dims([])
    prods = [_prod("A", "a", {"EA": {"baseQty": 1}}),
             _prod("B", "b", {"EA": {"baseQty": 1}})]
    assert len(build_worklist(dims, prods)) == 2
