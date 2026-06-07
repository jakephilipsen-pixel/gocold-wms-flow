"""Tests for stream classification, focused on the dispatch-flag rule (R2b)."""
from __future__ import annotations

import pandas as pd

from analysis.routing import (
    STREAM_BENCH,
    STREAM_PALLET,
    OrderMetricsResult,
    classify_streams,
)

_NO_RULES = pd.DataFrame(
    columns=["delivery_company_norm", "override_stream",
             "min_cartons_override", "notes"]
)


def _metrics(rows: list[dict]) -> OrderMetricsResult:
    """Build a minimal per-order frame with the columns classify_streams reads."""
    base = {
        "delivery_company_norm": "ACME",
        "total_cartons": 5,
        "has_full_pallet_line": False,
        "full_pallet_line_count": 0,
        "pallet_fraction": 0.1,
        "has_unknown_pickbench": False,
        "has_pickbench_sku": True,   # -> would be bench without other rules
        "all_direct_skus": False,
    }
    df = pd.DataFrame([{**base, **r} for r in rows])
    return OrderMetricsResult(
        per_order=df, n_orders=len(df), n_orders_with_dims=len(df),
        n_orders_partial_dims=0, pallet_fraction_method_summary={},
    )


def test_dispatch_flagged_order_routes_to_pallet():
    for flag in ("mixed", "new_address", "stale", "no_address", "no_run"):
        m = _metrics([{"dispatch_flag": flag}])
        res = classify_streams(m, _NO_RULES)
        assert res.per_order["stream"].iloc[0] == STREAM_PALLET, flag
        assert res.per_order["rule_fired"].iloc[0] == "R2b_dispatch_flagged"


def test_stable_flag_does_not_force_pallet():
    m = _metrics([{"dispatch_flag": "stable"}])
    res = classify_streams(m, _NO_RULES)
    # falls through to the normal bench rule (has_pickbench_sku=True)
    assert res.per_order["stream"].iloc[0] == STREAM_BENCH


def test_missing_dispatch_flag_column_is_harmless():
    # No dispatch_flag column at all -> behaves exactly as before (bench).
    m = _metrics([{}])
    res = classify_streams(m, _NO_RULES)
    assert res.per_order["stream"].iloc[0] == STREAM_BENCH
