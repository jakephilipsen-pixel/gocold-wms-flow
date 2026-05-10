"""Plotting helpers — save charts to PNG, no display required.

Uses matplotlib (already a pandas transitive dep). Keeps chart styling
consistent and the calling code simple. We avoid seaborn to keep the dep
footprint tight.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# pyplot import is delayed inside functions so import-time cost is paid
# only when we actually make charts. Saves analysis-script startup time.


def velocity_pareto(
    sku_metrics: pd.DataFrame, out_path: Path, top_n: int = 200
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sku_metrics.sort_values("units_per_day", ascending=False).head(top_n)
    cumpct = df["units_per_day"].cumsum() / sku_metrics["units_per_day"].sum() * 100

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.bar(range(len(df)), df["units_per_day"], color="#0096CC", alpha=0.7)
    ax1.set_xlabel("SKU rank (by units/day)")
    ax1.set_ylabel("Units shipped per day", color="#0096CC")
    ax1.tick_params(axis="y", labelcolor="#0096CC")

    ax2 = ax1.twinx()
    ax2.plot(range(len(df)), cumpct.values, color="#003366", linewidth=2)
    ax2.axhline(80, color="#00C452", linestyle="--", alpha=0.7, label="A/B cut (80%)")
    ax2.axhline(95, color="#FFA500", linestyle="--", alpha=0.7, label="B/C cut (95%)")
    ax2.set_ylabel("Cumulative % of total volume", color="#003366")
    ax2.tick_params(axis="y", labelcolor="#003366")
    ax2.set_ylim(0, 105)
    ax2.legend(loc="lower right")

    ax1.set_title(f"SKU velocity Pareto curve (top {top_n} of {len(sku_metrics)} SKUs)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def order_density(per_order: pd.DataFrame, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # lines per order
    line_max = int(np.percentile(per_order["line_count"], 99))
    axes[0].hist(
        per_order["line_count"].clip(upper=line_max),
        bins=min(50, line_max), color="#0096CC", alpha=0.8,
    )
    axes[0].axvline(
        per_order["line_count"].median(), color="#003366",
        linestyle="--", label=f"median: {per_order['line_count'].median():.0f}",
    )
    axes[0].axvline(
        np.percentile(per_order["line_count"], 90), color="#00C452",
        linestyle="--", label=f"90th pct: {np.percentile(per_order['line_count'], 90):.0f}",
    )
    axes[0].set_xlabel(f"Lines per order (clipped at 99th pct = {line_max})")
    axes[0].set_ylabel("Number of orders")
    axes[0].set_title("Order line density")
    axes[0].legend()

    # units per order
    qty_max = int(np.percentile(per_order["total_units"], 99))
    axes[1].hist(
        per_order["total_units"].clip(upper=qty_max),
        bins=50, color="#00C452", alpha=0.8,
    )
    axes[1].axvline(
        per_order["total_units"].median(), color="#003366",
        linestyle="--", label=f"median: {per_order['total_units'].median():.0f}",
    )
    axes[1].axvline(
        np.percentile(per_order["total_units"], 90), color="#0096CC",
        linestyle="--", label=f"90th pct: {np.percentile(per_order['total_units'], 90):.0f}",
    )
    axes[1].set_xlabel(f"Units per order (clipped at 99th pct = {qty_max})")
    axes[1].set_ylabel("Number of orders")
    axes[1].set_title("Order quantity distribution")
    axes[1].legend()

    fig.suptitle("Order patterns — bench bypass threshold candidates", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def abc_class_breakdown(sku_metrics: pd.DataFrame, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = sku_metrics["abc_class"].value_counts().reindex(["A", "B", "C"]).fillna(0)
    units = (
        sku_metrics.groupby("abc_class")["units_per_day"]
        .sum()
        .reindex(["A", "B", "C"])
        .fillna(0)
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    colors = ["#00C452", "#0096CC", "#003366"]

    axes[0].bar(counts.index, counts.values, color=colors)
    axes[0].set_title("SKU count by ABC class")
    axes[0].set_ylabel("Number of SKUs")
    for i, v in enumerate(counts.values):
        axes[0].text(i, v, f" {int(v)}", ha="center", va="bottom")

    axes[1].bar(units.index, units.values, color=colors)
    axes[1].set_title("Units/day by ABC class")
    axes[1].set_ylabel("Total units shipped per day")
    for i, v in enumerate(units.values):
        axes[1].text(i, v, f" {v:.0f}", ha="center", va="bottom")

    fig.suptitle("ABC classification summary", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def lift_heatmap(lift_df: pd.DataFrame, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(lift_df.values, cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(range(len(lift_df)))
    ax.set_yticks(range(len(lift_df)))
    ax.set_xticklabels(lift_df.columns, rotation=90, fontsize=7)
    ax.set_yticklabels(lift_df.index, fontsize=7)
    fig.colorbar(im, ax=ax, label="Co-occurrence lift (0=never, 1=always)")
    ax.set_title(f"SKU co-occurrence lift — top {len(lift_df)} SKUs")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
