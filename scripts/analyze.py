#!/usr/bin/env python3
"""Run the full velocity / pattern / zoning / destination analysis.

Reads the most recent extract from data/raw/, writes results to
data/processed/<timestamp>/. Designed to be re-runnable: each run
produces a fresh timestamped folder so old analyses are preserved.

Usage:
    # full run with defaults
    python scripts/analyze.py

    # tweak zone params
    python scripts/analyze.py --top-skus 80 --lift 0.35 --zone-size 6

    # specify a different raw dir or output dir
    python scripts/analyze.py --raw data/raw --out data/processed

What gets written:
    summary.md                 -- human-readable interpretation
    sku_metrics.csv            -- one row per SKU with all metrics
    sku_metrics.parquet        -- same, parquet for downstream use
    capture_template.xlsx      -- carton-dim entry sheet, Go Cold themed
    order_patterns.csv         -- one row per SO with line/qty totals
    bypass_threshold.json      -- bench-bypass threshold recommendation
    zone_assignment.csv        -- top-N SKU -> zone_id mapping
    zone_suggestions.md        -- human-readable zoning narrative
    cooccurrence_lift.csv      -- full lift matrix (top-N x top-N)
    destinations_postcode.csv  -- orders by postcode
    destinations_state.csv     -- orders by state
    destinations_customer.csv  -- orders by drop-ship customer
    plots/
        velocity_pareto.png
        order_density.png
        abc_breakdown.png
        lift_heatmap.png
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analysis import (  # noqa: E402
    compute_destinations,
    compute_order_patterns,
    compute_velocity,
    compute_zoning,
    load_latest,
)
from analysis import plots  # noqa: E402
from analysis.capture_template import write_capture_template  # noqa: E402

log = logging.getLogger("analyze")


def _write_summary(
    out_dir: Path,
    snap,
    vel,
    patterns,
    zoning,
    destinations,
) -> Path:
    """Emit the human-readable summary.md."""
    so_min, so_max = snap.so_window
    po_min, po_max = snap.po_window
    n_skus = len(vel.sku_metrics)
    abc_counts = vel.sku_metrics["abc_class"].value_counts()
    top10 = vel.sku_metrics.head(10)

    lines = [
        "# Forage SKU analysis — summary",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## Window",
        f"- Sale orders: {so_min:%Y-%m-%d} → {so_max:%Y-%m-%d} "
        f"({vel.so_span_days:.0f} days)",
        f"- Purchase orders: {po_min:%Y-%m-%d} → {po_max:%Y-%m-%d} "
        f"({vel.po_span_days:.0f} days)",
        f"- SOs analysed: {snap.so_lines['so_id'].nunique():,}",
        f"- SO line items: {len(snap.so_lines):,}",
        f"- POs analysed: {snap.po_lines['po_id'].nunique():,}",
        f"- Active products: {len(snap.products):,}",
        "",
        "## Velocity",
        f"- SKUs with shipping activity: {n_skus:,}",
        f"- A-class (top 80% volume): {int(abc_counts.get('A', 0))} SKUs",
        f"- B-class (next 15% volume): {int(abc_counts.get('B', 0))} SKUs",
        f"- C-class (last 5% volume): {int(abc_counts.get('C', 0))} SKUs",
        "",
        "### Top 10 SKUs by units/day",
        "",
        "| Rank | Code | Name | ABC | Units/day | Lines/day | Orders/day |",
        "|------|------|------|-----|-----------|-----------|------------|",
    ]
    for i, (code, row) in enumerate(top10.iterrows(), start=1):
        lines.append(
            f"| {i} | `{code}` | {str(row.get('product_name', ''))[:40]} | "
            f"{row.get('abc_class', '')} | {row.get('units_per_day', 0):.1f} | "
            f"{row.get('lines_per_day', 0):.2f} | {row.get('orders_per_day', 0):.2f} |"
        )

    lines.extend([
        "",
        "## Order patterns",
        "",
        "Line count per order:",
        f"- median: {patterns.line_density_summary['50%']:.0f}",
        f"- 90th percentile: {patterns.line_density_summary['90%']:.0f}",
        f"- 99th percentile: {patterns.line_density_summary['99%']:.0f}",
        "",
        "Total units per order:",
        f"- median: {patterns.qty_summary['50%']:.0f}",
        f"- 90th percentile: {patterns.qty_summary['90%']:.0f}",
        f"- 99th percentile: {patterns.qty_summary['99%']:.0f}",
        "",
        "### Bench bypass threshold (provisional, refines once carton dims arrive)",
        f"- {patterns.suggested_bypass_threshold['rule']}",
        "",
        "## Destinations",
        f"- States with deliveries: {len(destinations.by_state)}",
        f"- Unique postcodes: {len(destinations.by_postcode):,}",
        f"- Unique drop-ship customers: {len(destinations.by_customer):,}",
        "",
        "Top 5 states by order count:",
    ])
    for _, row in destinations.by_state.head(5).iterrows():
        lines.append(
            f"- {row['delivery_state']}: {row['orders']:,} orders "
            f"({row['pct_of_orders']:.1f}%) across "
            f"{row['postcodes']} postcodes"
        )

    lines.extend([
        "",
        "## Zoning",
        f"- Analysed top {len(zoning.top_skus)} SKUs by volume",
        f"- Suggested zones: {zoning.zone_assignment['zone_id'].nunique()}",
        "- See `zone_suggestions.md` for the per-zone breakdown.",
        "- These groupings are **directional** — they say which SKUs *should* "
        "be near each other based on co-pick frequency. Final bay placement "
        "needs carton dimensions (Track B).",
        "",
        "## What's blocked / what's next",
        "",
        "1. **Carton dimensions** are 0/460 in CC. The capture template "
        "`capture_template.xlsx` is ready for the warehouse team to fill "
        "in, sorted by measurement priority.",
        "2. Once dims are in, slotting math runs (cube vs bay capacity, replen "
        "rules, true bench bypass threshold based on pallet fit, not just qty).",
        "3. Run sequencing needs a separate convo about how runs are currently "
        "defined and what road clusters make sense for these postcodes.",
    ])

    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(lines))
    return summary_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path,
                   default=Path(__file__).resolve().parent.parent / "data" / "raw")
    p.add_argument("--out", type=Path,
                   default=Path(__file__).resolve().parent.parent / "data" / "processed")
    p.add_argument("--top-skus", type=int, default=50,
                   help="number of SKUs to include in zoning analysis (default 50)")
    p.add_argument("--lift", type=float, default=0.40,
                   help="co-occurrence lift threshold for zoning (default 0.40)")
    p.add_argument("--zone-size", type=int, default=8,
                   help="target SKUs per zone (default 8)")
    args = p.parse_args()

    logging.basicConfig(
        level="INFO",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("loading snapshot...")
    snap = load_latest(args.raw)
    print(f"  ✓ {len(snap.so_lines):,} SO lines, "
          f"{len(snap.po_lines):,} PO lines, "
          f"{len(snap.products):,} products")

    print("computing velocity metrics...")
    vel = compute_velocity(snap)
    print(f"  ✓ {len(vel.sku_metrics):,} SKUs classified "
          f"(span: {vel.so_span_days:.0f} SO days, {vel.po_span_days:.0f} PO days)")

    print("computing order patterns...")
    patterns = compute_order_patterns(snap)
    print(f"  ✓ {len(patterns.per_order):,} orders summarised")

    print(f"computing zoning (top {args.top_skus}, lift={args.lift})...")
    zoning = compute_zoning(
        snap, vel.sku_metrics,
        top_n=args.top_skus,
        lift_threshold=args.lift,
        target_zone_size=args.zone_size,
    )
    print(f"  ✓ {zoning.zone_assignment['zone_id'].nunique()} zones suggested")

    print("computing destinations...")
    destinations = compute_destinations(snap, vel.sku_metrics)
    print(f"  ✓ {len(destinations.by_postcode):,} postcodes, "
          f"{len(destinations.by_customer):,} drop-ship destinations")

    # --- write outputs to a timestamped dir
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    print(f"\nwriting to {out_dir}/")

    vel.sku_metrics.to_csv(out_dir / "sku_metrics.csv")
    vel.sku_metrics.to_parquet(out_dir / "sku_metrics.parquet")
    print("  ✓ sku_metrics.csv + .parquet")

    write_capture_template(vel.sku_metrics, out_dir / "capture_template.xlsx")
    print("  ✓ capture_template.xlsx (Go Cold themed)")

    patterns.per_order.to_csv(out_dir / "order_patterns.csv")
    (out_dir / "bypass_threshold.json").write_text(
        json.dumps(patterns.suggested_bypass_threshold, indent=2)
    )
    print("  ✓ order_patterns.csv + bypass_threshold.json")

    zoning.zone_assignment.to_csv(out_dir / "zone_assignment.csv", index=False)
    zoning.cooccurrence_count.to_csv(out_dir / "cooccurrence_count.csv")
    zoning.lift_matrix.to_csv(out_dir / "cooccurrence_lift.csv")
    (out_dir / "zone_suggestions.md").write_text(zoning.suggestions_md)
    print("  ✓ zone_assignment.csv + cooccurrence_*.csv + zone_suggestions.md")

    destinations.by_postcode.to_csv(out_dir / "destinations_postcode.csv", index=False)
    destinations.by_state.to_csv(out_dir / "destinations_state.csv", index=False)
    destinations.by_customer.to_csv(out_dir / "destinations_customer.csv", index=False)
    print("  ✓ destinations_*.csv")

    print("rendering plots...")
    plots.velocity_pareto(vel.sku_metrics, plots_dir / "velocity_pareto.png")
    plots.order_density(patterns.per_order, plots_dir / "order_density.png")
    plots.abc_class_breakdown(vel.sku_metrics, plots_dir / "abc_breakdown.png")
    plots.lift_heatmap(zoning.lift_matrix, plots_dir / "lift_heatmap.png")
    print("  ✓ 4 plots saved")

    summary_path = _write_summary(out_dir, snap, vel, patterns, zoning, destinations)
    print(f"  ✓ {summary_path.name}")

    print(f"\n✅ done. open {summary_path} for the readable overview.")
    print(f"   capture template → {out_dir / 'capture_template.xlsx'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
