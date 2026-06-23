"""Regression guard for dim-template column resolution (AUDIT R6).

Operators hand-edit the capture-sheet headers between captures. The June-2026
sheet renamed three columns ("Inner Pack Qty" -> "Inner Pack Qty per outer",
"Outer Carton Qty per pallet" -> "...for putawsay", "layers per pallet" ->
"total leyers per pallet ...") — the carton-qty rename used to raise a hard
ValueError and stop the whole file loading. These tests lock the tolerant
(exact -> prefix) matching that lets such drift through without silently
grabbing the wrong column.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from analysis.dim_loader import _find_col, load_dimensions

_ROOT = Path(__file__).resolve().parent.parent


# ---------- the matcher ----------

def test_exact_match_wins():
    df = pd.DataFrame(columns=["Outer L (mm)", "Outer W (mm)"])
    assert _find_col(df, "Outer L (mm)") == "Outer L (mm)"


def test_exact_is_case_and_space_insensitive():
    df = pd.DataFrame(columns=["  outer l (MM) "])
    assert _find_col(df, "Outer L (mm)") == "  outer l (MM) "


def test_prefix_match_tolerates_trailing_notes():
    """The real June-2026 drift: a descriptive suffix appended to a header."""
    df = pd.DataFrame(columns=["Inner Pack Qty per outer"])
    assert _find_col(df, "Inner Pack Qty") == "Inner Pack Qty per outer"

    df2 = pd.DataFrame(columns=["Outer Carton Qty per pallet for putawsay"])
    assert (
        _find_col(df2, "Outer Carton Qty per pallet", "Outer Carton Qty")
        == "Outer Carton Qty per pallet for putawsay"
    )


def test_exact_beats_prefix_when_both_present():
    """A precise header must not be shadowed by a longer prefixed one."""
    df = pd.DataFrame(columns=["Outer Carton Qty per pallet for putawsay",
                               "Outer Carton Qty per pallet"])
    assert (
        _find_col(df, "Outer Carton Qty per pallet")
        == "Outer Carton Qty per pallet"
    )


def test_candidate_order_is_respected():
    df = pd.DataFrame(columns=["Outer Carton Qty per pallet for putawsay"])
    # First candidate that matches (in any tier) wins.
    assert (
        _find_col(df, "Outer Carton Qty per pallet", "Outer Carton Qty")
        == "Outer Carton Qty per pallet for putawsay"
    )


def test_no_match_returns_none():
    df = pd.DataFrame(columns=["Something Else"])
    assert _find_col(df, "Outer Weight (kg)") is None


def test_no_false_substring_match():
    """Prefix only — a candidate appearing mid-header must NOT match."""
    df = pd.DataFrame(columns=["Total layers per pallet"])
    # "layers per pallet" is a substring but not a prefix -> no match...
    assert _find_col(df, "layers per pallet") is None
    # ...which is exactly why the loader adds the "total ..." candidate.
    assert _find_col(df, "total layers per pallet") == "Total layers per pallet"


# ---------- end-to-end against the real drifted file ----------

@pytest.mark.skipif(
    not (_ROOT / "dims.ods").exists(),
    reason="dims.ods not present",
)
def test_each_rework_headers_resolve(monkeypatch):
    """The Jun-2026 each-rework relabelled the kept per-each dims "Each * (mm)" and the
    carton-qty column "CT Qty per pallet" (carton/"Outer" dims split out). These must resolve to
    the same normalised columns the write path reads — still mm (÷10 to cm happens at the CC
    boundary, not here)."""
    sheet = pd.DataFrame({
        "Product Code": ["BB-2CH", "AE-2CB"],
        "Each L (mm)": [230, None],          # AE-2CB's carton dims were deleted → blank → skipped
        "Each W (mm)": [140, None],
        "Each H (mm)": [205, None],
        "Each Weight (kg)": [1.3, None],
        "Inner Pack Qty Per CT": [6, 6],
        "CT Qty per pallet": [40, 40],
        "Pallet height 1, 2 or 3": [2, 2],
        "layers per pallet": [5, 5],
    })
    monkeypatch.setattr("analysis.dim_loader.pd.read_excel", lambda *a, **k: sheet)

    df = load_dimensions(Path("ignored.xlsx"))

    row = df.set_index("product_code").loc["BB-2CH"]
    assert (row["outer_l_mm"], row["outer_w_mm"], row["outer_h_mm"]) == (230, 140, 205)
    assert row["outer_weight_kg"] == 1.3
    assert int(df.set_index("product_code").loc["AE-2CB", "cartons_per_pallet"]) == 40
    # BB-2CH is fully measured; AE-2CB (dims deleted) is not → the write path skips it.
    assert bool(row["measurement_complete"]) is True
    assert bool(df.set_index("product_code").loc["AE-2CB", "measurement_complete"]) is False


def test_june_ods_template_loads():
    """The June-2026 ODS (renamed columns) must load, not raise."""
    odf = pytest.importorskip("odf")  # noqa: F841 - just gate on the engine
    df = load_dimensions(_ROOT / "dims.ods")

    assert len(df) == 409
    # required dims resolved
    assert df["outer_l_mm"].notna().all()
    # the previously-fatal carton-qty column now resolves for nearly all rows
    assert df["cartons_per_pallet"].notna().sum() >= 390
    # the renamed inner-pack column resolves (was silently NA before)
    assert df["inner_pack_qty"].notna().sum() >= 400
    # the "total leyers" typo'd layers column resolves
    assert df["layers_per_pallet"].notna().sum() >= 400
