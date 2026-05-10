"""Destination geographic analysis — input for run sequencing.

We compute postcode + state distributions of orders and identify natural
clusters. We don't try to do route optimisation here; that's a downstream
problem requiring road-network data and vehicle constraints. This pass is
"where do orders actually go" so we know what runs to design.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .loaders import Snapshot


@dataclass
class DestinationAnalysis:
    by_postcode: pd.DataFrame
    by_state: pd.DataFrame
    by_customer: pd.DataFrame


def compute_destinations(snap: Snapshot, sku_metrics: pd.DataFrame) -> DestinationAnalysis:
    so = snap.so_lines.copy()
    so["quantity"] = pd.to_numeric(so["quantity"], errors="coerce").fillna(0)

    # we want unique-order-level data, not per-line, so dedupe on so_id
    orders = so.drop_duplicates("so_id")[
        ["so_id", "customer_id", "customer_name",
         "delivery_postcode", "delivery_state", "delivery_suburb",
         "delivery_company", "ts_packed"]
    ].copy()

    # also pre-aggregate units per order
    units_per_order = so.groupby("so_id")["quantity"].sum().rename("order_units")
    orders = orders.merge(units_per_order, left_on="so_id", right_index=True, how="left")

    # by postcode
    by_postcode = (
        orders.groupby(["delivery_state", "delivery_postcode"])
        .agg(
            orders=("so_id", "nunique"),
            unique_destinations=("delivery_company", "nunique"),
            total_units=("order_units", "sum"),
        )
        .reset_index()
        .sort_values("orders", ascending=False)
    )
    total_orders = orders["so_id"].nunique()
    by_postcode["pct_of_orders"] = (
        by_postcode["orders"] / total_orders * 100
    ).round(2)
    by_postcode["cumulative_pct"] = (
        by_postcode["pct_of_orders"].cumsum().round(2)
    )

    # by state
    by_state = (
        orders.groupby("delivery_state")
        .agg(
            orders=("so_id", "nunique"),
            postcodes=("delivery_postcode", "nunique"),
            destinations=("delivery_company", "nunique"),
            total_units=("order_units", "sum"),
        )
        .reset_index()
        .sort_values("orders", ascending=False)
    )
    by_state["pct_of_orders"] = (
        by_state["orders"] / total_orders * 100
    ).round(2)

    # by customer (drop-ship destination, not Forage as billing customer)
    by_customer = (
        orders.groupby(["delivery_company", "delivery_suburb",
                        "delivery_state", "delivery_postcode"])
        .agg(
            orders=("so_id", "nunique"),
            total_units=("order_units", "sum"),
        )
        .reset_index()
        .sort_values("orders", ascending=False)
    )

    return DestinationAnalysis(
        by_postcode=by_postcode,
        by_state=by_state,
        by_customer=by_customer,
    )
