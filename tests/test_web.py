"""Tests for the web layer (disk readers + FastAPI routes)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _make_run(base: Path, run_id: str) -> Path:
    run = base / run_id
    (run / "VIC-bench-01").mkdir(parents=True)
    manifest = {
        "generated_at": "2026-06-04T08:12:00",
        "settings": {"status": "AWAITING_PICK_AND_PACK", "customer_name": None,
                     "pallet_fraction_threshold": 0.65, "early_release_cartons": 25,
                     "run_group_col": "delivery_state", "lines_per_hour": 60,
                     "soh_fallback": False},
        "summary": {"n_waves": 1, "n_orders_total": 22, "n_orders_skipped": 1,
                    "n_pick_lines_total": 3},
        "waves": [{"wave_id": "VIC-bench-01", "stream": "3_wave_bench",
                   "run_group": "VIC", "receive_date": None, "total_cartons": 45,
                   "total_lines": 3, "n_orders": 22, "estimated_walk_m": 240.0}],
    }
    (run / "manifest.json").write_text(json.dumps(manifest))
    pd.DataFrame([
        {"walk_index": 1, "location": "A-01-1-1", "product_code": "FRG-0042",
         "product_name": "Oats", "qty_cartons": 14, "cartons_running_total": 14,
         "contributing_so_refs": "SO-1"},
    ]).to_csv(run / "VIC-bench-01" / "VIC-bench-01_picks.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-1", "customer_name": "Forage", "delivery_state": "VIC",
         "cartons": 14, "lines": 1},
    ]).to_csv(run / "VIC-bench-01" / "VIC-bench-01_orders.csv", index=False)
    pd.DataFrame([
        {"wave_id": "VIC-bench-01", "so_ref": "SO-9",
         "reason": "missing pick location for SKU(s)", "missing_skus": "FRG-9"},
    ]).to_csv(run / "skipped_orders.csv", index=False)
    return run


def test_list_runs_newest_first(tmp_path):
    from web.runs import list_runs
    _make_run(tmp_path, "20260603_080000")
    _make_run(tmp_path, "20260604_081200")
    runs = list_runs(tmp_path)
    assert [r["run_id"] for r in runs] == ["20260604_081200", "20260603_080000"]
    assert runs[0]["n_waves"] == 1


def test_get_run_includes_waves_and_skipped(tmp_path):
    from web.runs import get_run
    _make_run(tmp_path, "20260604_081200")
    run = get_run(tmp_path, "20260604_081200")
    assert run["summary"]["n_orders_total"] == 22
    assert run["waves"][0]["wave_id"] == "VIC-bench-01"
    assert run["skipped"][0]["so_ref"] == "SO-9"


def test_get_wave_reads_pick_and_order_csvs(tmp_path):
    from web.runs import get_wave
    _make_run(tmp_path, "20260604_081200")
    wave = get_wave(tmp_path, "20260604_081200", "VIC-bench-01")
    assert wave["pick_lines"][0]["location"] == "A-01-1-1"
    assert wave["orders"][0]["so_ref"] == "SO-1"


def test_file_path_rejects_traversal(tmp_path):
    from web.runs import file_path
    _make_run(tmp_path, "20260604_081200")
    with pytest.raises(ValueError):
        file_path(tmp_path, "20260604_081200", "VIC-bench-01", "../../secret")
    good = file_path(tmp_path, "20260604_081200", "VIC-bench-01",
                     "VIC-bench-01_picks.csv")
    assert good.exists()
