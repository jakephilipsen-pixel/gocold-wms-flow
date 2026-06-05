"""The picksheet renders located + unallocated lines without erroring."""
from __future__ import annotations

from datetime import date

import pandas as pd

from analysis.wave_picks import WavePickSheet
from analysis.routing import STREAM_BENCH
from output.pdf_picksheet import generate_wave_pdf


def _sheet():
    pick_lines = pd.DataFrame([
        {"walk_index": 1, "location": "AA-01-01", "aisle": "AA", "bay": 1,
         "level": 1, "sublevel": pd.NA, "product_code": "WIDGET",
         "product_name": "Widget", "qty_cartons": 3,
         "cartons_running_total": 3, "contributing_so_refs": "SO-A",
         "unallocated": False},
        {"walk_index": 2, "location": "UNALLOCATED", "aisle": pd.NA,
         "bay": pd.NA, "level": pd.NA, "sublevel": pd.NA,
         "product_code": "MYSTERY", "product_name": "Mystery",
         "qty_cartons": 1, "cartons_running_total": 4,
         "contributing_so_refs": "SO-A", "unallocated": True},
    ])
    orders = pd.DataFrame([{
        "so_id": 1, "so_ref": "SO-A", "customer_name": "Forage",
        "delivery_company": "Shop", "delivery_suburb": "Scoresby",
        "delivery_state": "VIC", "delivery_postcode": "3179",
        "cartons": 4, "lines": 2,
    }])
    return WavePickSheet(
        wave_id="W1", stream=STREAM_BENCH, run_group="VIC",
        receive_date=date(2026, 6, 5), orders=orders, pick_lines=pick_lines,
        total_cartons=4, total_lines=2, estimated_walk_distance_m=10.0)


def test_pdf_renders_with_unallocated_lines(tmp_path):
    out = tmp_path / "w1.pdf"
    generate_wave_pdf(_sheet(), out)
    assert out.exists() and out.stat().st_size > 1000


def test_unallocated_block_adds_content(tmp_path):
    s = _sheet()
    full = tmp_path / "full.pdf"
    generate_wave_pdf(s, full)

    s2 = _sheet()
    s2.pick_lines = s2.pick_lines[~s2.pick_lines["unallocated"]].copy()
    s2.total_lines = len(s2.pick_lines)
    s2.total_cartons = int(s2.pick_lines["qty_cartons"].sum())
    smaller = tmp_path / "located.pdf"
    generate_wave_pdf(s2, smaller)

    assert full.stat().st_size > smaller.stat().st_size
