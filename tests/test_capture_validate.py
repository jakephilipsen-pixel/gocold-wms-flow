"""Read-only pre-flight validator for the carton-dim capture sheet.

Confirms an edited sheet PARSES through the real loader before any metres bulk uses it: header
drift surfaces as a clear error (not a silent mis-read), and a value that looks like cm/metres in
the mm sheet is flagged. No CartonCloud, no network — the sheet read is monkeypatched.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.capture_validate import validate_capture_sheet, format_validation


def _patch_sheet(monkeypatch, rows: dict):
    monkeypatch.setattr("analysis.dim_loader.pd.read_excel", lambda *a, **k: pd.DataFrame(rows))


GOOD = {
    "Product Code": ["FP-1", "FP-2", "FP-3"],
    "Outer L (mm)": [255, 300, None],          # FP-3 missing L -> partial
    "Outer W (mm)": [230, 200, 150],
    "Outer H (mm)": [150, 100, 90],
    "Outer Weight (kg)": [2.2, 1.0, None],
    "Outer Carton Qty per pallet": [40, 50, 60],
    "Inner Pack Qty": [6, 6, 6],
    "layers per pallet": [5, 5, 5],
}


def test_validate_good_sheet_loads_with_counts_and_mapping(monkeypatch):
    _patch_sheet(monkeypatch, GOOD)
    v = validate_capture_sheet(Path("ignored.xlsx"))
    assert v.loads is True
    assert v.error is None
    assert v.total_skus == 3
    assert v.fully_measured == 2          # FP-1, FP-2 (FP-3 missing L)
    assert v.partial_or_empty == 1
    assert v.column_mapping["outer_l_mm"] == "Outer L (mm)"
    assert v.column_mapping["cartons_per_pallet"] == "Outer Carton Qty per pallet"
    assert v.flags == []


def test_validate_missing_required_column_reports_error_and_headers(monkeypatch):
    _patch_sheet(monkeypatch, {
        "Product Code": ["FP-1"],
        "Outer L (mm)": [255], "Outer W (mm)": [230], "Outer H (mm)": [150],
    })
    v = validate_capture_sheet(Path("ignored.xlsx"))
    assert v.loads is False
    assert "cartons-per-pallet" in v.error          # the real loader's message, surfaced plainly
    assert "Outer L (mm)" in v.headers_found
    # the mapping still shows what DID resolve, so Jake sees L/W/H were fine and only cpp is missing
    assert v.column_mapping["outer_l_mm"] == "Outer L (mm)"
    assert v.column_mapping["cartons_per_pallet"] is None


def test_validate_missing_product_code_column(monkeypatch):
    _patch_sheet(monkeypatch, {"Foo": [1, 2]})
    v = validate_capture_sheet(Path("ignored.xlsx"))
    assert v.loads is False
    assert "Product Code" in v.error


def test_validate_flags_metres_value_in_mm_sheet(monkeypatch):
    # FP-1's dims are in METRES (0.255) — a unit mix-up; ÷1000 at the boundary would write them
    # 1000x too small. They must be flagged. FP-2's real mm values must NOT be flagged.
    _patch_sheet(monkeypatch, {
        "Product Code": ["FP-1", "FP-2"],
        "Outer L (mm)": [0.255, 300],
        "Outer W (mm)": [0.23, 200],
        "Outer H (mm)": [0.15, 100],
        "Outer Carton Qty per pallet": [40, 50],
        "layers per pallet": [5, 5],
    })
    v = validate_capture_sheet(Path("ignored.xlsx"))
    assert v.loads is True
    flagged = {(f.product_code, f.column) for f in v.flags}
    assert ("FP-1", "outer_l_mm") in flagged
    assert ("FP-1", "outer_w_mm") in flagged
    assert ("FP-1", "outer_h_mm") in flagged
    assert all(f.product_code != "FP-2" for f in v.flags)


def test_validate_flags_non_numeric_dim(monkeypatch):
    _patch_sheet(monkeypatch, {
        "Product Code": ["FP-1"],
        "Outer L (mm)": ["tbc"],            # someone typed text into a dim cell
        "Outer W (mm)": [230],
        "Outer H (mm)": [150],
        "Outer Carton Qty per pallet": [40],
        "layers per pallet": [5],
    })
    v = validate_capture_sheet(Path("ignored.xlsx"))
    assert v.loads is True
    flags = {(f.product_code, f.column): f for f in v.flags}
    assert ("FP-1", "outer_l_mm") in flags
    assert "non-numeric" in flags[("FP-1", "outer_l_mm")].issue.lower()


def test_blank_dims_are_not_flagged(monkeypatch):
    # A blank cell is "unmeasured", not "suspicious" — it must count as partial, not raise a flag.
    _patch_sheet(monkeypatch, {
        "Product Code": ["FP-1"],
        "Outer L (mm)": [None], "Outer W (mm)": [None], "Outer H (mm)": [None],
        "Outer Carton Qty per pallet": [40],
        "layers per pallet": [5],
    })
    v = validate_capture_sheet(Path("ignored.xlsx"))
    assert v.loads is True
    assert v.flags == []
    assert v.fully_measured == 0
    assert v.partial_or_empty == 1


def test_format_validation_renders_mapping_and_counts(monkeypatch):
    _patch_sheet(monkeypatch, GOOD)
    out = format_validation(validate_capture_sheet(Path("x.xlsx")))
    assert "outer_l_mm" in out
    assert "Outer L (mm)" in out          # the resolved mapping is shown
    assert "3" in out                     # total SKUs


def test_format_validation_shows_error_when_not_loading(monkeypatch):
    _patch_sheet(monkeypatch, {
        "Product Code": ["FP-1"],
        "Outer L (mm)": [255], "Outer W (mm)": [230], "Outer H (mm)": [150],
    })
    out = format_validation(validate_capture_sheet(Path("x.xlsx")))
    assert "cartons-per-pallet" in out
    assert "missing" in out.lower() or "does not load" in out.lower()
