"""Order pattern analysis: line density, qty distribution, bench-bypass threshold.

The wave-pick vs single-pick decision needs a defensible threshold. Without
carton dims we can't compute "fits a pallet" precisely, but we can compute
units-per-order and lines-per-order distributions and pick a sensible cut
that splits the population cleanly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .loaders import Snapshot


@dataclass
class OrderPatterns:
    per_order: pd.DataFrame  # one row per SO with line count + total qty
    line_density_summary: pd.Series
    qty_summary: pd.Series
    suggested_bypass_threshold: dict[str, float]


def compute_order_patterns(snap: Snapshot) -> OrderPatterns:
    """Build the per-order summary and recommend a bench-bypass threshold."""
    so = snap.so_lines.copy()
    so["quantity"] = pd.to_numeric(so["quantity"], errors="coerce").fillna(0)

    per_order = so.groupby("so_id").agg(
        so_ref=("so_ref", "first"),
        line_count=("product_code", "size"),
        sku_count=("product_code", "nunique"),
        total_units=("quantity", "sum"),
        customer_id=("customer_id", "first"),
        delivery_postcode=("delivery_postcode", "first"),
        delivery_state=("delivery_state", "first"),
        ts_packed=("ts_packed", "first"),
    )

    line_summary = per_order["line_count"].describe(
        percentiles=[0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    )
    qty_summary = per_order["total_units"].describe(
        percentiles=[0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    )

    # bench bypass heuristic: orders >= 90th percentile of units AND >= 90th of
    # lines are "big enough to deserve direct-to-pallet picking".
    # Once we have carton dims we'll replace this with "estimated cube > pallet".
    qty_p90 = float(np.percentile(per_order["total_units"], 90))
    line_p90 = float(np.percentile(per_order["line_count"], 90))
    threshold = {
        "units_p90": qty_p90,
        "lines_p90": line_p90,
        "rule": (
            f"orders with total_units >= {qty_p90:.0f} OR line_count >= {line_p90:.0f} "
            f"are candidates for direct-to-pallet (bypass bench)"
        ),
    }

    return OrderPatterns(
        per_order=per_order,
        line_density_summary=line_summary,
        qty_summary=qty_summary,
        suggested_bypass_threshold=threshold,
    )
