"""Tests for the dispatch->wave run bridge (src/analysis/dispatch_link.py)."""
from __future__ import annotations

import pandas as pd

from analysis.dispatch_link import (
    FLAGGED_DISPATCH,
    attach_dispatch_runs,
    find_latest_dispatch_plan,
    load_dispatch_link,
)


def _write_plan(plan_dir, suggested_rows, review_rows):
    plan_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        suggested_rows,
        columns=["so_ref", "so_id", "predicted_run", "confidence", "flag"],
    ).to_csv(plan_dir / "suggested_runs.csv", index=False)
    pd.DataFrame(
        review_rows,
        columns=["so_ref", "so_id", "predicted_run", "confidence", "flag"],
    ).to_csv(plan_dir / "review.csv", index=False)


def test_find_latest_dispatch_plan_picks_newest_stamp(tmp_path):
    base = tmp_path / "data" / "processed" / "dispatch"
    _write_plan(base / "20260606_010000", [], [])
    _write_plan(base / "20260607_010000", [], [])
    (base / "20260605_nope").mkdir(parents=True)  # no suggested_runs.csv
    latest = find_latest_dispatch_plan(tmp_path)
    assert latest == base / "20260607_010000"


def test_find_latest_returns_none_when_absent(tmp_path):
    assert find_latest_dispatch_plan(tmp_path) is None


def test_load_dispatch_link_merges_suggested_and_review(tmp_path):
    plan = tmp_path / "p"
    _write_plan(
        plan,
        suggested_rows=[["SO-1", "id-1", "RUN-A", 0.95, "stable"]],
        review_rows=[["SO-2", "id-2", "RUN-B", 0.40, "mixed"],
                     ["SO-3", "id-3", None, 0.0, "no_address"]],
    )
    link = load_dispatch_link(plan)
    assert set(link.columns) == {
        "so_id", "predicted_run", "dispatch_flag", "confidence"}
    assert len(link) == 3
    row2 = link.loc[link["so_id"] == "id-2"].iloc[0]
    assert row2["predicted_run"] == "RUN-B"
    assert row2["dispatch_flag"] == "mixed"


def test_attach_marks_missing_orders_no_run(tmp_path):
    plan = tmp_path / "p"
    _write_plan(
        plan,
        suggested_rows=[["SO-1", "id-1", "RUN-A", 0.95, "stable"]],
        review_rows=[],
    )
    link = load_dispatch_link(plan)
    per_order = pd.DataFrame({"so_id": ["id-1", "id-9"], "so_ref": ["SO-1", "SO-9"]})
    out = attach_dispatch_runs(per_order, link)
    assert out.loc[out["so_id"] == "id-1", "predicted_run"].iloc[0] == "RUN-A"
    assert out.loc[out["so_id"] == "id-1", "dispatch_flag"].iloc[0] == "stable"
    # id-9 not in plan -> no_run on both
    assert out.loc[out["so_id"] == "id-9", "predicted_run"].iloc[0] == "no_run"
    assert out.loc[out["so_id"] == "id-9", "dispatch_flag"].iloc[0] == "no_run"
    assert "no_run" in FLAGGED_DISPATCH  # missing orders route to pallet


def test_attach_with_empty_link_marks_all_no_run():
    per_order = pd.DataFrame({"so_id": ["id-1"], "so_ref": ["SO-1"]})
    out = attach_dispatch_runs(per_order, pd.DataFrame())
    assert out["predicted_run"].iloc[0] == "no_run"
    assert out["dispatch_flag"].iloc[0] == "no_run"


def test_load_dispatch_link_suggested_wins_over_review(tmp_path):
    plan = tmp_path / "p"
    _write_plan(
        plan,
        suggested_rows=[["SO-1", "id-1", "RUN-A", 0.95, "stable"]],
        review_rows=[["SO-1", "id-1", "RUN-Z", 0.20, "mixed"]],
    )
    link = load_dispatch_link(plan)
    assert len(link) == 1
    row = link.iloc[0]
    assert row["predicted_run"] == "RUN-A"
    assert row["dispatch_flag"] == "stable"
