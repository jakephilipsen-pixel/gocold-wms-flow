"""Tests for output.csv_picksheet — specifically that the unallocated flag
survives into picks.csv and is correctly valued for located vs. unallocated
pick lines.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from analysis.wave_picks import WavePickSheet
from output.csv_picksheet import write_wave_csvs


def _make_sheet(wave_id: str = "VIC-bench-01") -> WavePickSheet:
    """Build a minimal WavePickSheet with one located and one unallocated line."""
    pick_lines = pd.DataFrame([
        {
            "walk_index": 1,
            "location": "A-01-1-1",
            "aisle": "A",
            "bay": "01",
            "level": "1",
            "sublevel": "1",
            "product_code": "FRG-0001",
            "product_name": "Oats",
            "qty_cartons": 5,
            "cartons_running_total": 5,
            "contributing_so_refs": "SO-1",
            "unallocated": False,
        },
        {
            "walk_index": 2,
            "location": "UNALLOCATED",
            "aisle": pd.NA,
            "bay": pd.NA,
            "level": pd.NA,
            "sublevel": pd.NA,
            "product_code": "FRG-0099",
            "product_name": "Mystery Item",
            "qty_cartons": 2,
            "cartons_running_total": 7,
            "contributing_so_refs": "SO-2",
            "unallocated": True,
        },
    ])
    orders = pd.DataFrame([
        {
            "so_id": "SO-1",
            "so_ref": "SO-1",
            "customer_name": "Forage",
            "delivery_company": "",
            "delivery_suburb": "Scoresby",
            "delivery_state": "VIC",
            "delivery_postcode": "3179",
            "cartons": 5,
            "lines": 1,
        },
    ])
    return WavePickSheet(
        wave_id=wave_id,
        stream="3_wave_bench",
        run_group="VIC",
        receive_date=date(2026, 6, 5),
        orders=orders,
        pick_lines=pick_lines,
        total_cartons=7,
        total_lines=2,
        estimated_walk_distance_m=10.0,
    )


def test_unallocated_column_present_in_picks_csv(tmp_path: Path) -> None:
    """The unallocated flag must survive write_wave_csvs into picks.csv."""
    sheet = _make_sheet()
    paths = write_wave_csvs(sheet, tmp_path)

    result = pd.read_csv(paths.picks)
    assert "unallocated" in result.columns, (
        "picks.csv is missing the 'unallocated' column"
    )


def test_unallocated_values_correct_in_picks_csv(tmp_path: Path) -> None:
    """Located line must be False; unallocated line must be True."""
    sheet = _make_sheet()
    paths = write_wave_csvs(sheet, tmp_path)

    result = pd.read_csv(paths.picks)
    located_row = result[result["product_code"] == "FRG-0001"].iloc[0]
    unalloc_row = result[result["product_code"] == "FRG-0099"].iloc[0]

    assert located_row["unallocated"] == False, (  # noqa: E712
        "located line should have unallocated=False"
    )
    assert unalloc_row["unallocated"] == True, (  # noqa: E712
        "unallocated line should have unallocated=True"
    )
    assert unalloc_row["location"] == "UNALLOCATED"


def test_picks_csv_column_order_ends_with_unallocated(tmp_path: Path) -> None:
    """unallocated should be the final column in picks.csv."""
    sheet = _make_sheet()
    paths = write_wave_csvs(sheet, tmp_path)

    result = pd.read_csv(paths.picks)
    assert result.columns[-1] == "unallocated", (
        f"Expected 'unallocated' as last column; got '{result.columns[-1]}'"
    )


def test_picks_csv_no_crash_when_unallocated_absent(tmp_path: Path) -> None:
    """If pick_lines happens to lack the unallocated column, reindex fills NaN
    rather than raising KeyError — frame must still be written."""
    sheet = _make_sheet()
    sheet.pick_lines = sheet.pick_lines.drop(columns=["unallocated"])
    paths = write_wave_csvs(sheet, tmp_path)

    result = pd.read_csv(paths.picks)
    # Column present (reindex adds it), all values are NaN.
    assert "unallocated" in result.columns
    assert result["unallocated"].isna().all()
