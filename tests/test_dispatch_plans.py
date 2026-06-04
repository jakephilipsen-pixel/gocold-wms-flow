from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

_COLS = ["so_ref", "so_id", "predicted_run", "confidence", "flag", "reason",
         "alternatives", "full_address", "street", "suburb", "state", "postcode"]


def _make_plan(base: Path, stamp: str) -> Path:
    d = base / stamp
    d.mkdir(parents=True)
    pd.DataFrame([
        {"so_ref": "SO-1", "so_id": "1", "predicted_run": "West-Tue",
         "confidence": 1.0, "flag": "stable", "reason": "r", "alternatives": "",
         "full_address": "1 A St, Scoresby VIC 3179", "street": "1 A St",
         "suburb": "Scoresby", "state": "VIC", "postcode": "3179"},
        {"so_ref": "SO-2", "so_id": "2", "predicted_run": "West-Tue",
         "confidence": 0.9, "flag": "stable", "reason": "r", "alternatives": "",
         "full_address": "2 B St, Scoresby VIC 3170", "street": "2 B St",
         "suburb": "Scoresby", "state": "VIC", "postcode": "3170"},
    ], columns=_COLS).to_csv(d / "suggested_runs.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-3", "so_id": "3", "predicted_run": "",
         "confidence": 0.0, "flag": "new_address",
         "reason": "no history; zone=Metro Melbourne", "alternatives": "",
         "full_address": "9 New Rd, Geelong VIC 3220", "street": "9 New Rd",
         "suburb": "Geelong", "state": "VIC", "postcode": "3220"},
    ], columns=_COLS).to_csv(d / "review.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-4", "so_id": "4", "predicted_run": "", "confidence": 1.0,
         "flag": "carrier", "reason": "carrier order (TollExpress)",
         "alternatives": "", "full_address": "x", "street": "x", "suburb": "x",
         "state": "VIC", "postcode": "3000"},
    ], columns=_COLS).to_csv(d / "carriers_TollExpress.csv", index=False)
    (d / "summary.md").write_text("# Dispatch run prediction summary\n")
    return d


def test_list_plans_newest_first_with_counts(tmp_path):
    from web_dispatch.plans import list_plans
    _make_plan(tmp_path, "20260604_080000")
    _make_plan(tmp_path, "20260605_093000")
    plans = list_plans(tmp_path)
    assert [p["stamp"] for p in plans] == ["20260605_093000", "20260604_080000"]
    p = plans[0]
    assert p["n_assignments"] == 2
    assert p["n_runs"] == 1
    assert p["n_review"] == 1
    assert p["n_carriers"] == 1
    assert p["generated_at"].startswith("2026-06-05")


def test_get_plan_groups_runs_and_lists_review(tmp_path):
    from web_dispatch.plans import get_plan
    _make_plan(tmp_path, "20260605_093000")
    plan = get_plan(tmp_path, "20260605_093000")
    assert plan["runs"][0]["run"] == "West-Tue"
    assert plan["runs"][0]["n_stops"] == 2
    assert 0.94 <= plan["runs"][0]["avg_confidence"] <= 0.96
    assert plan["review"][0]["flag"] == "new_address"
    assert "TollExpress" in plan["carriers"]
    assert "suggested_runs.csv" in plan["files"]
    assert plan["summary_md"].startswith("# Dispatch")


def test_get_run_filters_and_sorts_by_postcode(tmp_path):
    from web_dispatch.plans import get_run
    _make_plan(tmp_path, "20260605_093000")
    run = get_run(tmp_path, "20260605_093000", "West-Tue")
    assert [s["postcode"] for s in run["stops"]] == ["3170", "3179"]


def test_file_path_guards_traversal(tmp_path):
    from web_dispatch.plans import file_path
    _make_plan(tmp_path, "20260605_093000")
    with pytest.raises(ValueError):
        file_path(tmp_path, "20260605_093000", "../../secret")
    good = file_path(tmp_path, "20260605_093000", "suggested_runs.csv")
    assert good.exists()
