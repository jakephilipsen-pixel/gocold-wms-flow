"""The picksheet renders located + unallocated lines without erroring."""
from __future__ import annotations

from datetime import date

import pandas as pd

from analysis.wave_picks import WavePickSheet
from analysis.routing import STREAM_BENCH
from output.pdf_picksheet import generate_wave_pdf


def _pdf_text(path) -> bytes:
    """Crude reportlab content-stream extractor (ASCII85+Flate)."""
    import base64
    import re
    import zlib

    raw = path.read_bytes()
    out = b""
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        try:
            out += zlib.decompress(base64.a85decode(m.group(1).strip(), adobe=True))
        except Exception:
            continue
    return out


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


def test_pdf_renders_carton_pick_lines(tmp_path):
    """PDF renders CTN pick lines with each-equivalents and reserve flags."""
    pick_lines = pd.DataFrame([
        {"walk_index": 1, "location": "AB-04-03", "aisle": "AB", "bay": 4,
         "level": 3, "sublevel": None, "product_code": "FD-BAR",
         "product_name": "Choc Bar 6pk", "pick_uom": "CTN",
         "qty_cartons": 4, "qty_eaches": 24, "cartons_running_total": 4,
         "contributing_so_refs": "SO-1", "unallocated": False,
         "reserve_unavailable": True, "qty_short": False},
        {"walk_index": 2, "location": "AA-01-01", "aisle": "AA", "bay": 1,
         "level": 1, "sublevel": None, "product_code": "FD-BAR",
         "product_name": "Choc Bar 6pk", "pick_uom": "EA",
         "qty_cartons": 3, "qty_eaches": pd.NA, "cartons_running_total": 7,
         "contributing_so_refs": "SO-1", "unallocated": False,
         "reserve_unavailable": False, "qty_short": False},
    ])
    orders = pd.DataFrame([
        {"so_ref": "SO-1", "customer_name": "Forage",
         "delivery_company": "Shop", "delivery_suburb": "Scoresby",
         "delivery_state": "VIC", "delivery_postcode": "3179",
         "cartons": 7, "lines": 2},
    ])
    sheet = WavePickSheet(
        wave_id="W-CTN", stream="3_wave_bench", run_group="VIC",
        receive_date=None, orders=orders, pick_lines=pick_lines,
        total_cartons=7, total_lines=2, estimated_walk_distance_m=10.0,
    )
    out = tmp_path / "w.pdf"
    generate_wave_pdf(sheet, out)
    assert out.exists()
    assert out.stat().st_size > 1000

    text = _pdf_text(out)
    assert b"4 CTN" in text
    assert b"24 EA" in text
    assert b"NO RESERVE" in text
    assert b"CHECK QTY" not in text   # qty_short False on both rows


def test_csv_roundtripped_nan_flags_render_no_markers(tmp_path):
    """Float NaN flags (CSV round-trip of absent bools) must not render warning markers."""
    pick_lines = pd.DataFrame([
        {"walk_index": 1, "location": "AB-04-03", "aisle": "AB", "bay": 4,
         "level": 3, "sublevel": None, "product_code": "FD-BAR",
         "product_name": "Choc Bar 6pk", "pick_uom": "CTN",
         "qty_cartons": 4, "qty_eaches": 24, "cartons_running_total": 4,
         "contributing_so_refs": "SO-1", "unallocated": False,
         "reserve_unavailable": float("nan"), "qty_short": float("nan")},
        {"walk_index": 2, "location": "AA-01-01", "aisle": "AA", "bay": 1,
         "level": 1, "sublevel": None, "product_code": "FD-BAR",
         "product_name": "Choc Bar 6pk", "pick_uom": "EA",
         "qty_cartons": 3, "qty_eaches": pd.NA, "cartons_running_total": 7,
         "contributing_so_refs": "SO-1", "unallocated": False,
         "reserve_unavailable": float("nan"), "qty_short": float("nan")},
    ])
    orders = pd.DataFrame([
        {"so_ref": "SO-1", "customer_name": "Forage",
         "delivery_company": "Shop", "delivery_suburb": "Scoresby",
         "delivery_state": "VIC", "delivery_postcode": "3179",
         "cartons": 7, "lines": 2},
    ])
    sheet = WavePickSheet(
        wave_id="W-NAN", stream="3_wave_bench", run_group="VIC",
        receive_date=None, orders=orders, pick_lines=pick_lines,
        total_cartons=7, total_lines=2, estimated_walk_distance_m=10.0,
    )
    out = tmp_path / "w_nan.pdf"
    generate_wave_pdf(sheet, out)
    assert out.exists()
    text = _pdf_text(out)
    assert b"NO RESERVE" not in text
    assert b"CHECK QTY" not in text
