#!/usr/bin/env python3
"""Run the v2 analysis pipeline: dims + tags + full-pallet filter + slotting.

This is the boss-presentable version. It:
  1. Loads the latest CC extract (SOs, POs, products)
  2. Loads the latest dimension capture (whatever's been measured)
  3. Computes raw velocity, derives tags
  4. Flags full-pallet SO lines (TC chocolate, etc.) and recomputes CLEAN velocity
  5. Re-runs ABC + zoning on the cleaned velocity
  6. Generates slotting recommendations for fully-measured SKUs
  7. Writes a v2 summary that contrasts pre/post-filter and shows what's slotted
     vs awaiting dims

Usage:
    # default: latest dim file in data/dims/
    python scripts/analyze_v2.py

    # specific dim file
    python scripts/analyze_v2.py --dims data/dims/dims_2026-05-11.xlsx

    # tweak full-pallet threshold
    python scripts/analyze_v2.py --pallet-ratio 0.85
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
    apply_tags,
    compute_destinations,
    compute_order_patterns,
    compute_velocity,
    compute_zoning,
    load_dimensions,
    load_latest,
    recommend_slotting,
    run_full_pallet_analysis,
)
from analysis import plots  # noqa: E402

log = logging.getLogger("analyze_v2")


def _latest_dim_file(dims_dir: Path) -> Path | None:
    candidates = sorted(
        dims_dir.glob("dims_*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _write_summary(
    out_dir: Path,
    snap,
    dims,
    raw_vel,
    full_pallet,
    cleaned_metrics,
    patterns,
    zoning,
    destinations,
    slotting,
    pallet_ratio,
) -> Path:
    """Boss-readable summary contrasting raw vs cleaned analysis."""
    so_min, so_max = snap.so_window
    po_min, po_max = snap.po_window

    measured = dims["measurement_complete"].sum()
    total_skus = len(snap.products)

    lines = [
        "# Forage SKU analysis — v2 (with dims + full-pallet filter)",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## Headline",
        "",
        f"- **{measured}** of {total_skus} SKUs have full carton dimensions captured "
        f"({100 * measured / total_skus:.0f}%)",
        f"- **{full_pallet.n_flagged}** SO lines flagged as full-pallet shipments "
        f"(ratio ≥ {pallet_ratio:.0%}, TC brand) and excluded from velocity",
        f"- **{slotting.pickbench_y_count}** SKUs flow through bench (Pickbench=Y), "
        f"**{slotting.pickbench_n_count}** bypass to direct-pallet (Pickbench=N)",
        f"- **{slotting.measured_count}** SKUs have v1 slotting recommendations ready",
        f"- **{slotting.unmeasured_count}** SKUs still awaiting dimensions",
        "",
        "## Window",
        f"- Sale orders: {so_min:%Y-%m-%d} → {so_max:%Y-%m-%d} "
        f"({raw_vel.so_span_days:.0f} days, "
        f"{snap.so_lines['so_id'].nunique():,} orders, {len(snap.so_lines):,} lines)",
        f"- Purchase orders: {po_min:%Y-%m-%d} → {po_max:%Y-%m-%d} "
        f"({raw_vel.po_span_days:.0f} days, "
        f"{snap.po_lines['po_id'].nunique():,} POs)",
        "",
        "## Effect of full-pallet filter",
        "",
        "Comparing raw vs cleaned per-SKU velocity (top SKUs only):",
        "",
        "| Code | Brand | Raw u/d | Clean u/d | Δ | Notes |",
        "|------|-------|---------|-----------|---|-------|",
    ]

    # show change in velocity for SKUs that had full-pallet shipments
    affected = full_pallet.summary_by_sku[
        full_pallet.summary_by_sku["full_pallet_lines"] > 0
    ].head(15)
    for code, row in affected.iterrows():
        raw_upd = raw_vel.sku_metrics.loc[code, "units_per_day"] \
            if code in raw_vel.sku_metrics.index else 0
        clean_upd = cleaned_metrics.loc[code, "units_per_day"] \
            if code in cleaned_metrics.index else 0
        delta = raw_upd - clean_upd
        pct_via_pallet = row["pct_qty_via_full_pallet"]
        lines.append(
            f"| `{code}` | {row['brand']} | {raw_upd:.1f} | {clean_upd:.1f} | "
            f"-{delta:.1f} | {pct_via_pallet:.0f}% of qty was full-pallet |"
        )

    lines.extend([
        "",
        "## Top 10 SKUs by CLEAN velocity (post-filter)",
        "",
        "| Rank | Code | Name | Brand | ABC | Units/day | Pallet qty | Bay |",
        "|------|------|------|-------|-----|-----------|------------|-----|",
    ])
    slotting_lookup = slotting.recommendations.set_index("product_code")
    for i, (code, row) in enumerate(cleaned_metrics.head(10).iterrows(), start=1):
        bay = ""
        pallet_q = ""
        if code in slotting_lookup.index:
            slot_row = slotting_lookup.loc[code]
            if pd.notna(slot_row.get("bay_height_mm")):
                bay = f"{int(slot_row['bay_height_mm'])}mm"
            if pd.notna(slot_row.get("cartons_per_pallet")):
                pallet_q = f"{int(slot_row['cartons_per_pallet'])}"
        brand = str(row.get("brand", "")) if "brand" in row else ""
        lines.append(
            f"| {i} | `{code}` | {str(row.get('product_name', ''))[:38]} | "
            f"{brand} | {row.get('abc_class', '')} | "
            f"{row.get('units_per_day', 0):.1f} | {pallet_q} | {bay} |"
        )

    lines.extend([
        "",
        "## Slotting plan (v1 — measured SKUs only)",
        "",
        f"- **Bench flow** (Pickbench=Y): {slotting.pickbench_y_count} SKUs — "
        "ergonomic shelf assignment, days-of-cover replen",
        f"- **Bypass flow** (Pickbench=N): {slotting.pickbench_n_count} SKUs — "
        "top-bay forklift positions, whole-pallet replen",
        f"- **Unclassified**: {slotting.pickbench_unclassified_count} SKUs — "
        "defaulted to bench logic",
        "",
    ])
    if slotting.measured_count > 0:
        rec = slotting.recommendations
        bench_rec = rec[rec["routing"].isin(["bench", "unclassified"])]
        bypass_rec = rec[rec["routing"] == "bypass"]
        if len(bench_rec) > 0:
            lines.append("**Bench flow bay distribution:**")
            by_bay = bench_rec[bench_rec["bay_height_mm"].notna()].groupby(
                "bay_height_mm").size()
            for bay_h, count in by_bay.items():
                lines.append(f"  - {int(bay_h)}mm bay: {int(count)} SKUs")
            lines.append("")
        if len(bypass_rec) > 0:
            lines.append("**Bypass flow bay distribution:**")
            by_bay = bypass_rec[bypass_rec["bay_height_mm"].notna()].groupby(
                "bay_height_mm").size()
            for bay_h, count in by_bay.items():
                lines.append(f"  - {int(bay_h)}mm bay: {int(count)} SKUs")
            lines.append("")
        lines.append(
            "See `slotting_recommendations.csv` for the full per-SKU plan."
        )
    else:
        lines.append("(no SKUs measured yet — see capture_template.xlsx)")

    lines.extend([
        "",
        "## Order patterns",
        "",
        f"- Median lines per order: {patterns.line_density_summary['50%']:.0f}",
        f"- 90th percentile lines: {patterns.line_density_summary['90%']:.0f}",
        f"- Median units per order: {patterns.qty_summary['50%']:.0f}",
        f"- 90th percentile units: {patterns.qty_summary['90%']:.0f}",
        "",
        "## Destinations",
        "",
    ])
    for _, row in destinations.by_state.head(5).iterrows():
        lines.append(
            f"- {row['delivery_state']}: {row['orders']:,} orders "
            f"({row['pct_of_orders']:.1f}%) across {row['postcodes']} postcodes"
        )

    lines.extend([
        "",
        "## What's next",
        "",
        f"1. **Continue dim capture** for the {slotting.unmeasured_count} unmeasured SKUs",
        "2. Validate v1 slotting recs against operator intuition before importing to CC",
        "3. Once all top 200 SKUs are measured, finalise zoning (currently directional)",
        "4. Define run-sequencing rules from destinations data",
    ])

    p = out_dir / "summary.md"
    p.write_text("\n".join(lines))
    return p


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=Path,
                   default=Path(__file__).resolve().parent.parent / "data" / "raw")
    p.add_argument("--dims", type=Path, default=None,
                   help="path to dimension xlsx (default: latest in data/dims/)")
    p.add_argument("--out", type=Path,
                   default=Path(__file__).resolve().parent.parent / "data" / "processed")
    p.add_argument("--pallet-ratio", type=float, default=0.9,
                   help="qty/pallet ratio above which a line is 'full pallet' (default 0.9)")
    p.add_argument("--top-skus", type=int, default=50,
                   help="SKUs to include in zoning (default 50)")
    args = p.parse_args()

    logging.basicConfig(
        level="INFO",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    global pd
    import pandas as pd_module  # noqa: F401
    globals()["pd"] = pd_module

    print("loading snapshot...")
    snap = load_latest(args.raw)
    print(f"  ✓ {len(snap.so_lines):,} SO lines, "
          f"{len(snap.po_lines):,} PO lines, "
          f"{len(snap.products):,} products")

    dim_path = args.dims or _latest_dim_file(args.out.parent / "dims")
    if dim_path is None or not dim_path.exists():
        print(f"❌ no dim file found. Either pass --dims or drop one in "
              f"{args.out.parent / 'dims'}/", file=sys.stderr)
        return 2
    print(f"loading dims from {dim_path.name}...")
    dims = load_dimensions(dim_path)
    measured = dims["measurement_complete"].sum()
    print(f"  ✓ {measured}/{len(dims)} SKUs fully measured")

    print("computing raw velocity...")
    raw_vel = compute_velocity(snap)
    print(f"  ✓ {len(raw_vel.sku_metrics):,} SKUs (raw)")

    print("applying tags (brand, format, full-pallet flag)...")
    tagged_raw = apply_tags(raw_vel.sku_metrics, dims)
    n_full_pallet_brand_skus = int(tagged_raw["is_full_pallet_brand"].sum())
    print(f"  ✓ tagged. {n_full_pallet_brand_skus} SKUs in full-pallet brands.")

    print(f"flagging full-pallet SO lines (ratio ≥ {args.pallet_ratio:.0%})...")
    full_pallet = run_full_pallet_analysis(
        snap, dims, tagged_raw, ratio=args.pallet_ratio,
    )
    print(f"  ✓ {full_pallet.n_flagged} lines flagged. "
          f"Re-running velocity on cleaned data.")

    cleaned_metrics = apply_tags(full_pallet.cleaned_velocity.sku_metrics, dims)
    cleaned_metrics = cleaned_metrics.sort_values("units_per_day", ascending=False)

    print("computing order patterns (on cleaned data)...")
    # patterns on cleaned snap so the bypass threshold reflects realistic picks
    cleaned_snap = full_pallet.cleaned_velocity  # has cleaned snap implicitly
    # but compute_order_patterns wants a snapshot; reuse the cleaned one we built
    # by recomputing from the dataframe
    from analysis.loaders import Snapshot as _Snap
    so_clean = snap.so_lines.merge(
        full_pallet.flagged_so_lines[["so_id", "product_code", "is_full_pallet_line"]],
        on=["so_id", "product_code"], how="left",
    )
    so_clean = so_clean[so_clean["is_full_pallet_line"].fillna(False) == False].copy()
    so_clean = so_clean.drop(columns=["is_full_pallet_line"], errors="ignore")
    cleaned_snap_for_patterns = _Snap(
        so_lines=so_clean, po_lines=snap.po_lines, products=snap.products,
        so_path=snap.so_path, po_path=snap.po_path, products_path=snap.products_path,
    )
    patterns = compute_order_patterns(cleaned_snap_for_patterns)
    print(f"  ✓ {len(patterns.per_order):,} orders summarised (post-filter)")

    print(f"computing zoning (top {args.top_skus})...")
    zoning = compute_zoning(cleaned_snap_for_patterns, cleaned_metrics,
                            top_n=args.top_skus)
    print(f"  ✓ {zoning.zone_assignment['zone_id'].nunique()} zones")

    print("computing destinations...")
    destinations = compute_destinations(cleaned_snap_for_patterns, cleaned_metrics)
    print(f"  ✓ {len(destinations.by_postcode):,} postcodes, "
          f"{len(destinations.by_customer):,} drop-ship destinations")

    print("generating slotting recommendations...")
    slotting = recommend_slotting(cleaned_metrics, dims)
    print(f"  ✓ {slotting.measured_count} SKUs slotted, "
          f"{slotting.unmeasured_count} awaiting dims")

    # --- write outputs
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out / f"v2_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(exist_ok=True)
    print(f"\nwriting to {out_dir}/")

    # core tables
    cleaned_metrics.to_csv(out_dir / "sku_metrics_cleaned.csv")
    raw_vel.sku_metrics.to_csv(out_dir / "sku_metrics_raw.csv")
    dims.to_csv(out_dir / "dims_loaded.csv", index=False)
    print("  ✓ sku_metrics (raw + cleaned) + dims_loaded")

    # full-pallet analysis
    full_pallet.flagged_so_lines.to_csv(out_dir / "full_pallet_so_lines.csv", index=False)
    full_pallet.summary_by_sku.to_csv(out_dir / "full_pallet_by_sku.csv")
    (out_dir / "full_pallet_meta.json").write_text(json.dumps({
        "ratio_used": full_pallet.ratio_used,
        "n_flagged": full_pallet.n_flagged,
        "brands_targeted": sorted(__import__("analysis").FULL_PALLET_BRANDS),
    }, indent=2))
    print("  ✓ full_pallet_* files")

    # slotting
    slotting.recommendations.to_csv(out_dir / "slotting_recommendations.csv", index=False)
    print("  ✓ slotting_recommendations.csv")

    # zoning + dests + patterns
    zoning.zone_assignment.to_csv(out_dir / "zone_assignment.csv", index=False)
    zoning.lift_matrix.to_csv(out_dir / "cooccurrence_lift.csv")
    (out_dir / "zone_suggestions.md").write_text(zoning.suggestions_md)
    destinations.by_postcode.to_csv(out_dir / "destinations_postcode.csv", index=False)
    destinations.by_state.to_csv(out_dir / "destinations_state.csv", index=False)
    destinations.by_customer.to_csv(out_dir / "destinations_customer.csv", index=False)
    patterns.per_order.to_csv(out_dir / "order_patterns.csv")
    (out_dir / "bypass_threshold.json").write_text(
        json.dumps(patterns.suggested_bypass_threshold, indent=2)
    )
    print("  ✓ zoning + destinations + patterns")

    # plots
    print("rendering plots...")
    plots.velocity_pareto(cleaned_metrics, plots_dir / "velocity_pareto_clean.png")
    plots.velocity_pareto(raw_vel.sku_metrics, plots_dir / "velocity_pareto_raw.png")
    plots.order_density(patterns.per_order, plots_dir / "order_density.png")
    plots.abc_class_breakdown(cleaned_metrics, plots_dir / "abc_breakdown.png")
    plots.lift_heatmap(zoning.lift_matrix, plots_dir / "lift_heatmap.png")
    print("  ✓ 5 plots")

    summary_path = _write_summary(
        out_dir, snap, dims, raw_vel, full_pallet, cleaned_metrics,
        patterns, zoning, destinations, slotting, args.pallet_ratio,
    )
    print(f"  ✓ {summary_path.name}")

    print(f"\n✅ done. open {summary_path}")
    print(f"   slotting plan → {out_dir / 'slotting_recommendations.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
