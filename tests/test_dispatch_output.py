from __future__ import annotations

import pandas as pd

from dispatch.output import write_dispatch_plan
from dispatch.predict import DispatchPlan, RunAssignment


def _plan():
    af = {"full_address": "1 A St, Scoresby VIC 3179", "street": "1 A St",
          "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}
    return DispatchPlan(
        assignments=[RunAssignment("1", "SO-1", "West-Tue", 1.0, "stable",
                                   "reason", [], af)],
        carriers={"TollExpress": [RunAssignment("2", "SO-2", None, 1.0,
                                                 "carrier", "carrier", [], af)]},
        review=[RunAssignment("3", "SO-3", None, 0.0, "new_address",
                              "no history; zone=Metro Melbourne", [], af)],
    )


def test_writes_all_outputs(tmp_path):
    write_dispatch_plan(_plan(), tmp_path)
    assert (tmp_path / "suggested_runs.csv").exists()
    assert (tmp_path / "review.csv").exists()
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "carriers_TollExpress.csv").exists()
    assert (tmp_path / "run_West-Tue.xlsx").exists()

    df = pd.read_csv(tmp_path / "suggested_runs.csv")
    assert list(df["predicted_run"]) == ["West-Tue"]
    assert "confidence" in df.columns


def test_summary_flags_review_count(tmp_path):
    write_dispatch_plan(_plan(), tmp_path)
    text = (tmp_path / "summary.md").read_text()
    assert "1" in text and "review" in text.lower()
