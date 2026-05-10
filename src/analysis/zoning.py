"""Co-occurrence analysis and zone suggestions.

Approach:
  1. Restrict to top-N SKUs by units shipped (N=50 by default). Full 460x460
     matrix is mostly zeros; the action is in the head.
  2. Build SKU-by-SKU co-occurrence: count of orders containing both A and B.
  3. Normalise by min(orders_with_A, orders_with_B) -> "lift": how often does
     B appear when A does. 1.0 = always together, 0.0 = never.
  4. Cluster on the lift matrix using simple greedy grouping. Sophisticated
     graph methods (Louvain etc) are overkill for ~50 nodes and obscure the
     reasoning.

Output: a SKU-to-zone assignment that groups frequent-co-pickers together.
WITHOUT carton dimensions, this is directional — physical bay assignments
require dim data so we know what fits where.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .loaders import Snapshot

log = logging.getLogger(__name__)


@dataclass
class ZoningResult:
    top_skus: list[str]
    cooccurrence_count: pd.DataFrame   # raw counts (lower triangle filled)
    lift_matrix: pd.DataFrame          # normalised, symmetric
    zone_assignment: pd.DataFrame      # SKU -> zone_id with sku metrics
    suggestions_md: str                # human-readable summary


def _build_cooccurrence(
    so_lines: pd.DataFrame, top_skus: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build pairwise co-occurrence count + lift matrix on top_skus."""
    sub = so_lines[so_lines["product_code"].isin(top_skus)].copy()

    # one-hot: rows = orders, cols = SKUs, values = 1 if SKU on order
    presence = (
        sub.assign(present=1)
        .pivot_table(
            index="so_id",
            columns="product_code",
            values="present",
            aggfunc="max",
            fill_value=0,
        )
        # ensure all top_skus are columns even if they happen to have 0 presence in window
        .reindex(columns=top_skus, fill_value=0)
    )

    # co-occurrence count = P^T P (each cell = orders containing both SKUs)
    arr = presence.values.astype(np.int32)
    cooc = arr.T @ arr
    cooc_df = pd.DataFrame(cooc, index=top_skus, columns=top_skus)

    # lift: cooc(A,B) / min(cooc(A,A), cooc(B,B))
    diag = np.diag(cooc).astype(float)
    # use outer min via broadcasting
    min_diag = np.minimum.outer(diag, diag)
    with np.errstate(divide="ignore", invalid="ignore"):
        lift = np.where(min_diag > 0, cooc / min_diag, 0.0)
    np.fill_diagonal(lift, 1.0)
    lift_df = pd.DataFrame(lift, index=top_skus, columns=top_skus)

    return cooc_df, lift_df


def _greedy_cluster(
    lift_df: pd.DataFrame,
    threshold: float = 0.40,
    target_zone_size: int = 8,
) -> dict[str, int]:
    """Greedy clustering: seed with highest-volume SKU, grow zone by adding
    the highest-lift unclaimed neighbour until target_zone_size is reached
    or no neighbour passes the lift threshold.

    threshold=0.40 means "B appears with A on at least 40% of A's orders"
    (or vice versa, whichever side is smaller). Tunable.

    Returns dict {sku -> zone_id}. SKUs that don't cluster cleanly land
    in their own singleton zone.
    """
    skus = list(lift_df.index)
    assigned: dict[str, int] = {}
    zone_id = 0

    # iterate skus in input order (already sorted by volume desc upstream)
    for seed in skus:
        if seed in assigned:
            continue
        zone_id += 1
        assigned[seed] = zone_id
        members = [seed]

        while len(members) < target_zone_size:
            # for each unclaimed candidate, score = max lift to any current member
            unclaimed = [s for s in skus if s not in assigned]
            if not unclaimed:
                break
            scores = lift_df.loc[unclaimed, members].max(axis=1)
            best = scores.idxmax()
            best_score = float(scores.loc[best])
            if best_score < threshold:
                break
            assigned[best] = zone_id
            members.append(best)

    return assigned


def compute_zoning(
    snap: Snapshot,
    sku_metrics: pd.DataFrame,
    top_n: int = 50,
    lift_threshold: float = 0.40,
    target_zone_size: int = 8,
) -> ZoningResult:
    """Top-down zoning: cluster the top-N SKUs by co-occurrence."""
    # take top_n by units_per_day
    top_skus = (
        sku_metrics
        .sort_values("units_per_day", ascending=False)
        .head(top_n)
        .index.tolist()
    )
    log.info("computing co-occurrence for top %d SKUs", len(top_skus))

    cooc_df, lift_df = _build_cooccurrence(snap.so_lines, top_skus)
    assignment_dict = _greedy_cluster(
        lift_df, threshold=lift_threshold, target_zone_size=target_zone_size,
    )

    rows = []
    for sku, zone in sorted(assignment_dict.items(), key=lambda kv: (kv[1], kv[0])):
        m = sku_metrics.loc[sku] if sku in sku_metrics.index else None
        rows.append({
            "product_code": sku,
            "zone_id": zone,
            "product_name": m["product_name"] if m is not None else "",
            "abc_class": m["abc_class"] if m is not None else "",
            "units_per_day": m["units_per_day"] if m is not None else np.nan,
            "lines_per_day": m["lines_per_day"] if m is not None else np.nan,
            "type": m["type"] if m is not None else "",
        })
    zone_df = pd.DataFrame(rows)

    # readable summary
    lines = [
        f"# Zoning suggestions (top {len(top_skus)} SKUs by units/day)",
        "",
        f"- Lift threshold: {lift_threshold} "
        f"(B is grouped with A if B appears on ≥{int(lift_threshold * 100)}% "
        f"of A's orders, or vice versa)",
        f"- Target zone size: {target_zone_size} SKUs",
        f"- Total zones: {zone_df['zone_id'].nunique()}",
        "",
        "## Zones",
    ]
    for zid, group in zone_df.groupby("zone_id"):
        members = group.sort_values("units_per_day", ascending=False)
        lines.append(f"\n### Zone {zid} ({len(members)} SKUs, "
                     f"{members['units_per_day'].sum():.0f} units/day total)")
        for _, row in members.iterrows():
            lines.append(
                f"  - **{row['product_code']}** {row['product_name'][:40]:<40} "
                f"({row['type']}, {row['abc_class']}-class, "
                f"{row['units_per_day']:.0f} u/d)"
            )

    return ZoningResult(
        top_skus=top_skus,
        cooccurrence_count=cooc_df,
        lift_matrix=lift_df,
        zone_assignment=zone_df,
        suggestions_md="\n".join(lines),
    )
