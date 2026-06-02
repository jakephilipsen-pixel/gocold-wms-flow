"""Per-SKU velocity, frequency, and inbound metrics.

Produces one comprehensive row per SKU with everything slotting needs to
make a decision (modulo carton dimensions, which come later).

Key metrics:
  - units_per_day        : total qty shipped / span in days  (volume metric)
  - lines_per_day        : SO line count / span in days       (frequency metric)
  - orders_per_day       : distinct SO count / span           (touch frequency)
  - abc_class            : A/B/C cut on cumulative units
  - abc_freq_class       : same cut on cumulative lines       (cross-check)
  - po_qty_median        : typical inbound carton qty per arrival
  - po_qty_p90           : 90th percentile inbound qty
  - po_arrivals          : count of distinct PO arrivals in window
  - days_of_cover_typ    : po_qty_median / units_per_day      (sanity check)
  - customer_concentration : Herfindahl-style index 0-1; high = few customers dominate
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .loaders import Snapshot

log = logging.getLogger(__name__)


@dataclass
class VelocityResult:
    sku_metrics: pd.DataFrame  # one row per SKU with all metrics
    so_span_days: float
    po_span_days: float
    abc_thresholds: dict[str, float]  # cumulative-pct cuts used for A/B/C


def _abc_classify(
    df: pd.DataFrame, value_col: str, label_col: str = "abc_class"
) -> pd.Series:
    """Pareto cut: A = top 80% cumulative, B = next 15%, C = last 5%.

    Standard slotting practice. The exact cut points are conservative
    defaults; `velocity_pareto.png` lets the user see the curve and
    re-cut by eye if needed.
    """
    sorted_df = df.sort_values(value_col, ascending=False)
    total = sorted_df[value_col].sum()
    if total == 0:
        return pd.Series("Z", index=df.index)
    cumpct = sorted_df[value_col].cumsum() / total

    classes = pd.Series("C", index=sorted_df.index)
    classes.loc[cumpct <= 0.80] = "A"
    classes.loc[(cumpct > 0.80) & (cumpct <= 0.95)] = "B"
    return classes.reindex(df.index)


def _customer_concentration(group: pd.DataFrame) -> float:
    """Herfindahl index over customer_id share of qty for this SKU.

    Returns 0 (perfectly spread) to 1 (one customer = 100%).
    Useful for spotting SKUs that only one customer buys (de-prioritise
    in shared zones) vs SKUs everyone buys (high-touch real estate).
    """
    by_cust = group.groupby("customer_id")["quantity"].sum()
    total = by_cust.sum()
    if total <= 0:
        return float("nan")
    shares = by_cust / total
    return float((shares ** 2).sum())


def compute_velocity(snap: Snapshot) -> VelocityResult:
    """Compute the full per-SKU metrics table from the snapshot."""
    so = snap.so_lines.copy()
    po = snap.po_lines.copy()
    products = snap.products.copy()

    # window spans (used to convert totals to per-day rates)
    so["ts_packed"] = pd.to_datetime(so["ts_packed"], errors="coerce", utc=True)
    so_span = max(
        (so["ts_packed"].max() - so["ts_packed"].min()).days, 1
    )
    po["arrival_date"] = pd.to_datetime(po["arrival_date"], errors="coerce")
    po_span = max(
        (po["arrival_date"].max() - po["arrival_date"].min()).days, 1
    )

    # --- outbound aggregates per SKU
    so_clean = so[so["product_code"].notna() & so["quantity"].notna()].copy()
    by_sku_so = so_clean.groupby("product_code").agg(
        units_total=("quantity", "sum"),
        lines_total=("so_id", "size"),
        orders_total=("so_id", "nunique"),
        product_name_first=("product_name", "first"),
    )
    by_sku_so["units_per_day"] = by_sku_so["units_total"] / so_span
    by_sku_so["lines_per_day"] = by_sku_so["lines_total"] / so_span
    by_sku_so["orders_per_day"] = by_sku_so["orders_total"] / so_span

    # avg qty per pick line (small = piece-pick, large = case-pick)
    by_sku_so["units_per_line_avg"] = (
        by_sku_so["units_total"] / by_sku_so["lines_total"]
    )

    # customer concentration per SKU
    log.info("computing customer concentration for %d SKUs", len(by_sku_so))
    conc = (
        so_clean.groupby("product_code")
        .apply(_customer_concentration, include_groups=False)
        .rename("customer_concentration")
    )
    by_sku_so = by_sku_so.join(conc)

    # --- inbound aggregates per SKU (only OK / received-good lines)
    po_clean = po[
        po["product_code"].notna()
        & po["quantity"].notna()
        & ~po["item_status"].isin(["LOST", "MISSING", "DAMAGED", "DAMAGED_BY_CARRIER"])
    ].copy()
    by_sku_po = po_clean.groupby("product_code").agg(
        po_qty_total=("quantity", "sum"),
        po_qty_median=("quantity", "median"),
        po_qty_p90=("quantity", lambda s: float(np.percentile(s, 90)) if len(s) else np.nan),
        po_arrivals=("po_id", "nunique"),
    )
    by_sku_po["po_arrivals_per_month"] = (
        by_sku_po["po_arrivals"] / (po_span / 30.0)
    )

    # --- merge: outer join so we see SKUs that exist on one side but not the other
    metrics = by_sku_so.join(by_sku_po, how="outer")

    # join product master (type, name fallback). dedupe products on
    # product_code first — CC has been known to emit duplicate rows for
    # the same SKU and we'd break the join otherwise.
    products_idx = (
        products.drop_duplicates(subset=["product_code"], keep="first")
        .set_index("product_code")[["name", "type", "default_uom"]]
        .rename(columns={"name": "product_name_master"})
    )
    metrics = metrics.join(products_idx)
    metrics["product_name"] = (
        metrics["product_name_master"].fillna(metrics["product_name_first"])
    )
    metrics = metrics.drop(
        columns=["product_name_master", "product_name_first"], errors="ignore"
    )

    # ABC classification: by units_per_day (volume-driven, per Jake's call)
    metrics["abc_class"] = _abc_classify(
        metrics.fillna({"units_per_day": 0}), "units_per_day"
    )
    # cross-check class on frequency, useful for spotting volume/freq mismatches
    metrics["abc_freq_class"] = _abc_classify(
        metrics.fillna({"lines_per_day": 0}), "lines_per_day"
    )

    # days-of-cover: rough sanity ratio
    metrics["days_of_cover_typ"] = (
        metrics["po_qty_median"] / metrics["units_per_day"]
    ).replace([np.inf, -np.inf], np.nan)

    # priority rank for measurement: by units_per_day desc
    metrics = metrics.sort_values("units_per_day", ascending=False)
    metrics["measure_priority"] = range(1, len(metrics) + 1)

    # surface column ordering
    cols_first = [
        "measure_priority", "product_name", "type",
        "abc_class", "abc_freq_class",
        "units_per_day", "lines_per_day", "orders_per_day",
        "units_per_line_avg",
        "po_qty_median", "po_qty_p90", "po_arrivals", "po_arrivals_per_month",
        "days_of_cover_typ", "customer_concentration",
        "units_total", "lines_total", "orders_total", "po_qty_total",
        "default_uom",
    ]
    metrics = metrics[[c for c in cols_first if c in metrics.columns]]

    abc_thresholds = {"A_top": 0.80, "B_top": 0.95}

    return VelocityResult(
        sku_metrics=metrics,
        so_span_days=float(so_span),
        po_span_days=float(po_span),
        abc_thresholds=abc_thresholds,
    )
