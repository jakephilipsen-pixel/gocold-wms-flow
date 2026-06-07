"""Tests for plan_waves immediate-stream emission (pallet + unclassified)."""
from __future__ import annotations

import pandas as pd

from analysis.routing import (
    STREAM_BENCH,
    STREAM_PALLET,
    STREAM_UNCLASSIFIED,
    StreamClassification,
    plan_waves,
)


def _classification(rows: list[dict]) -> StreamClassification:
    df = pd.DataFrame(rows)
    return StreamClassification(
        per_order=df,
        counts_by_stream=df["stream"].value_counts(),
        rule_hit_counts=pd.Series(dtype=int),
        threshold_used=0.7,
    )


_TS = "2026-06-07T08:00:00+10:00"


def test_pallet_orders_excluded_by_default():
    c = _classification([
        {"so_id": "p1", "stream": STREAM_PALLET, "total_cartons": 80,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
    ])
    plan = plan_waves(c, run_group_col="predicted_run")
    assert plan.per_wave.empty  # streams 2/3 only, default behaviour


def test_immediate_streams_emit_one_wave_per_run_stream():
    c = _classification([
        {"so_id": "p1", "stream": STREAM_PALLET, "total_cartons": 80,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "p2", "stream": STREAM_PALLET, "total_cartons": 70,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "u1", "stream": STREAM_UNCLASSIFIED, "total_cartons": 10,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "b1", "stream": STREAM_BENCH, "total_cartons": 5,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
    ])
    plan = plan_waves(
        c, run_group_col="predicted_run", include_immediate_streams=True)
    streams = set(plan.per_wave["stream"])
    assert STREAM_PALLET in streams
    assert STREAM_UNCLASSIFIED in streams
    assert STREAM_BENCH in streams
    # the two pallet orders for RUN-A collapse into a single immediate wave
    pallet_waves = plan.per_wave[plan.per_wave["stream"] == STREAM_PALLET]
    assert len(pallet_waves) == 1
    assert pallet_waves.iloc[0]["order_count"] == 2
    assert pallet_waves.iloc[0]["release_reason"] == "immediate"


def test_immediate_pallet_waves_split_by_run():
    # Distinct runs must NOT be merged into one wave: two pallet orders on
    # RUN-A collapse to one wave, RUN-B's order forms its own.
    c = _classification([
        {"so_id": "p1", "stream": STREAM_PALLET, "total_cartons": 80,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "p2", "stream": STREAM_PALLET, "total_cartons": 70,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "p3", "stream": STREAM_PALLET, "total_cartons": 60,
         "ts_packed": _TS, "predicted_run": "RUN-B"},
    ])
    plan = plan_waves(
        c, run_group_col="predicted_run", include_immediate_streams=True)
    pallet_waves = plan.per_wave[plan.per_wave["stream"] == STREAM_PALLET]
    assert len(pallet_waves) == 2
    by_run = pallet_waves.set_index("run_group")["order_count"].to_dict()
    assert by_run == {"RUN-A": 2, "RUN-B": 1}
