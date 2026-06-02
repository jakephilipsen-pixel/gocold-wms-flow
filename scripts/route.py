#!/usr/bin/env python3
"""Classify open SOs into pick streams and plan wave releases.

Pipeline:
  1. Load latest CC extract (SOs, POs, products) from data/raw/
  2. Load latest dims xlsx from data/dims/
  3. Load consignee rules CSV (optional, from data/routing/consignee_rules.csv)
  4. Compute velocity + tags + full-pallet line flags (reuses existing logic)
  5. Roll SO lines into per-order metrics with cube + pallet-fraction
  6. Classify each order into stream 1/2/3 + unclassified
  7. Build consignee profile (annotation template for next round of rules)
  8. Plan wave releases for streams 2 + 3
  9. Write everything to data/processed/route_<timestamp>/

The first run produces a consignee_profile.xlsx you annotate, save to
data/routing/consignee_rules.csv, and re-run to see the annotated streams.

Usage:
    python scripts/route.py

    # with explicit inputs
    python scripts/route.py --dims data/dims/dims_2026-05-14.xlsx \\
                            --rules data/routing/consignee_rules.csv

    # tune the pallet-fraction threshold
    python scripts/route.py --pallet-fraction-threshold 0.65

    # tune the wave early-release rule
    python scripts/route.py --early-release-cartons 25
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, time as dt_time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analysis import (  # noqa: E402
    apply_tags,
    compute_velocity,
    load_dimensions,
    load_latest,
    run_full_pallet_analysis,
)
from analysis.routing import (  # noqa: E402
    DEFAULT_EARLY_RELEASE_CARTONS,
    DEFAULT_PALLET_FRACTION_THRESHOLD,
    DEFAULT_WAVE_CUTOFF,
    STREAM_BENCH,
    STREAM_BYPASS,
    STREAM_PALLET,
    STREAM_UNCLASSIFIED,
    build_consignee_profile,
    classify_streams,
    compute_order_metrics,
    load_consignee_rules,
    plan_waves,
)

log = logging.getLogger("route")


def _latest_file(dirpath: Path, pattern: str) -> Path | None:
    candidates = sorted(
        dirpath.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _parse_time_hhmm(s: str) -> dt_time:
    """Accept HH:MM and return a datetime.time."""
    hh, mm = s.split(":")
    return dt_time(int(hh), int(mm))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parent.parent
    p.add_argument("--raw", type=Path, default=repo_root / "data" / "raw")
    p.add_argument(
        "--dims", type=Path, default=None,
        help="dim xlsx file (default: latest in data/dims/)",
    )
    p.add_argument(
        "--rules", type=Path, default=None,
        help=(
            "consignee rules CSV (default: data/routing/consignee_rules.csv "
            "if present, otherwise no rules applied)"
        ),
    )
    p.add_argument("--out", type=Path, default=repo_root / "data" / "processed")
    p.add_argument(
        "--pallet-ratio", type=float, default=0.9,
        help="threshold for full_pallet line detection (existing analysis)",
    )
    p.add_argument(
        "--pallet-fraction-threshold", type=float,
        default=DEFAULT_PALLET_FRACTION_THRESHOLD,
        help=(
            "order-level pallet_fraction at or above which an order is "
            "classified as Stream 1 (pick-to-pallet). Default 0.70."
        ),
    )
    p.add_argument(
        "--early-release-cartons", type=int,
        default=DEFAULT_EARLY_RELEASE_CARTONS,
        help=(
            "wave releases early once accumulated cartons hits this. "
            "Default 30."
        ),
    )
    p.add_argument(
        "--cutoff", type=_parse_time_hhmm,
        default=DEFAULT_WAVE_CUTOFF,
        help="final wave cutoff (HH:MM, Melbourne local). Default 13:00.",
    )
    p.add_argument(
        "--run-group-col", type=str, default="delivery_state",
        help=(
            "column in per-order frame used to group waves by delivery run "
            "(default: delivery_state). Use a 'delivery_run' column once "
            "you've added one to the extract."
        ),
    )
    args = p.parse_args()

    logging.basicConfig(
        level="INFO",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 1. CC extract
    print("loading snapshot...")
    snap = load_latest(args.raw)
    print(f"  + {len(snap.so_lines):,} SO lines, {len(snap.products):,} products")

    # 2. dims
    dim_path = args.dims or _latest_file(repo_root / "data" / "dims", "dims_*.xlsx")
    if not dim_path or not dim_path.exists():
        print("ERROR: no dim file found in data/dims/", file=sys.stderr)
        return 2
    print(f"loading dims from {dim_path.name}...")
    dims = load_dimensions(dim_path)
    measured = int(dims["measurement_complete"].sum())
    print(f"  + {measured}/{len(dims)} SKUs measured")

    # 3. consignee rules (optional)
    rules_path = args.rules or _latest_file(
        repo_root / "data" / "routing", "consignee_rules*.csv"
    )
    if rules_path and rules_path.exists():
        print(f"loading consignee rules from {rules_path.name}...")
    else:
        print("no consignee rules yet (first run produces the profile template)")
    rules = load_consignee_rules(rules_path)
    print(f"  + {len(rules)} consignee rules loaded")

    # 4. velocity + tags + full-pallet line flags (reuses existing logic)
    print("computing velocity + tags + full-pallet line flags...")
    raw_vel = compute_velocity(snap)
    tagged_raw = apply_tags(raw_vel.sku_metrics, dims)
    full_pallet = run_full_pallet_analysis(
        snap, dims, tagged_raw, ratio=args.pallet_ratio,
    )
    print(f"  + {full_pallet.n_flagged} full-pallet lines flagged")

    # 5. per-order metrics with cube + pallet-fraction
    print("rolling SO lines into per-order metrics...")
    metrics = compute_order_metrics(snap, dims, full_pallet)
    print(
        f"  + {metrics.n_orders:,} orders ("
        f"{metrics.n_orders_with_dims} full dim coverage, "
        f"{metrics.n_orders_partial_dims} partial)"
    )

    # 6. stream classification
    print(
        f"classifying streams (pallet_fraction_threshold="
        f"{args.pallet_fraction_threshold:.2f})..."
    )
    classification = classify_streams(
        metrics, rules,
        pallet_fraction_threshold=args.pallet_fraction_threshold,
    )
    counts = classification.counts_by_stream
    print(
        "  + " + ", ".join(
            f"{stream}={int(counts.get(stream, 0))}"
            for stream in (STREAM_PALLET, STREAM_BYPASS, STREAM_BENCH, STREAM_UNCLASSIFIED)
        )
    )

    # 7. consignee profile (annotation template)
    print("building consignee profile (annotation template)...")
    profile = build_consignee_profile(classification)
    print(f"  + {len(profile.profile)} distinct consignees")

    # 8. wave planning for streams 2 + 3
    print(
        f"planning waves (cutoff={args.cutoff.strftime('%H:%M')}, "
        f"early_release={args.early_release_cartons} cartons, "
        f"run_group={args.run_group_col})..."
    )
    waves = plan_waves(
        classification,
        cutoff=args.cutoff,
        early_release_cartons=args.early_release_cartons,
        run_group_col=args.run_group_col,
    )
    n_waves = len(waves.per_wave)
    print(f"  + {n_waves} waves over {len(waves.per_order_assignment)} orders")

    # 9. write outputs
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out / f"route_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nwriting to {out_dir}/")

    # order streams
    order_streams_cols = [
        "so_id", "so_ref", "stream", "stream_reason", "rule_fired",
        "customer_name", "delivery_company", "delivery_company_norm",
        "delivery_state", "delivery_postcode", "delivery_suburb",
        "ts_packed",
        "line_count", "sku_count", "total_cartons",
        "pallet_fraction_cube", "pallet_fraction_positions", "pallet_fraction",
        "has_pickbench_sku", "all_direct_skus", "has_unknown_pickbench",
        "has_full_pallet_line", "full_pallet_line_count",
        "cartons_with_dims", "cartons_missing_dims", "dims_coverage",
    ]
    order_streams_cols = [
        c for c in order_streams_cols if c in classification.per_order.columns
    ]
    order_streams = classification.per_order[order_streams_cols]
    order_streams.to_csv(out_dir / "order_streams.csv", index=False)
    order_streams.to_excel(out_dir / "order_streams.xlsx", index=False)
    print("  + order_streams.csv + .xlsx (one row per SO with stream assignment)")

    # consignee profile - the annotation template
    profile.profile.to_excel(
        out_dir / "consignee_profile.xlsx", index=False,
    )
    profile.profile.to_csv(out_dir / "consignee_profile.csv", index=False)
    print(
        "  + consignee_profile.xlsx + .csv (annotate "
        "override_stream / min_cartons_override, save as "
        "data/routing/consignee_rules.csv, re-run route.py)"
    )

    # wave plan
    if not waves.per_wave.empty:
        waves.per_wave.to_csv(out_dir / "wave_schedule.csv", index=False)
        waves.per_order_assignment.to_csv(
            out_dir / "wave_order_assignment.csv", index=False
        )
        print(
            "  + wave_schedule.csv (per-wave summary) + "
            "wave_order_assignment.csv (order -> wave)"
        )
    else:
        print("  ~ no waves to write (no stream 2/3 orders)")

    # text summary
    summary_lines = _build_summary(
        classification, profile, waves, metrics,
        args.pallet_fraction_threshold,
    )
    (out_dir / "summary.md").write_text("\n".join(summary_lines))
    print("  + summary.md")

    print(f"\nOK. open {out_dir / 'summary.md'}")
    print(f"   key files: order_streams.xlsx, consignee_profile.xlsx")
    return 0


def _build_summary(
    classification,
    profile,
    waves,
    metrics,
    threshold: float,
) -> list[str]:
    counts = classification.counts_by_stream
    rule_counts = classification.rule_hit_counts
    total = int(counts.sum()) if not counts.empty else 0

    lines = [
        "# Order Routing & Wave Plan",
        f"_Generated: {datetime.now():%Y-%m-%d %H:%M}_",
        "",
        "## Headline",
        f"- **{total:,}** orders classified",
        f"- pallet_fraction threshold: **{threshold:.2f}**",
        f"- wave cutoff: **{waves.cutoff_used.strftime('%H:%M')}** "
        f"(Melbourne local)",
        f"- early release threshold: **{waves.early_release_cartons} cartons**",
        "",
        "## Stream mix",
        "",
        "| Stream | Orders | % |",
        "|---|---:|---:|",
    ]
    for stream in (STREAM_PALLET, STREAM_BYPASS, STREAM_BENCH, STREAM_UNCLASSIFIED):
        n = int(counts.get(stream, 0))
        pct = 100.0 * n / total if total else 0.0
        lines.append(f"| `{stream}` | {n:,} | {pct:.1f}% |")
    lines.extend([
        "",
        "## Which rule fired most",
        "",
        "| Rule | Times fired |",
        "|---|---:|",
    ])
    for rule, n in rule_counts.items():
        lines.append(f"| {rule} | {int(n):,} |")

    lines.extend([
        "",
        "## Dim coverage",
        f"- Orders fully dim-covered: **{metrics.n_orders_with_dims:,}** / "
        f"{metrics.n_orders:,}",
        f"- Orders partially dim-covered: **{metrics.n_orders_partial_dims:,}**",
        f"- Pallet-fraction method tally: "
        f"{metrics.pallet_fraction_method_summary}",
    ])

    if not profile.profile.empty:
        lines.extend([
            "",
            "## Top 15 consignees by order count",
            "",
            "| Consignee | State | Orders | Cartons (median / p90) | "
            "Pallet frac (median / p90) | Auto-S1 % |",
            "|---|---|---:|---|---|---:|",
        ])
        for _, row in profile.profile.head(15).iterrows():
            lines.append(
                f"| {row['delivery_company']} | {row['state_main']} | "
                f"{int(row['orders']):,} | "
                f"{row['cartons_median']:.1f} / {row['cartons_p90']:.1f} | "
                f"{row['pallet_frac_median']:.2f} / "
                f"{row['pallet_frac_p90']:.2f} | "
                f"{row['pct_orders_stream_1']:.1f}% |"
            )
        lines.extend([
            "",
            "## Next step",
            "",
            "1. Open `consignee_profile.xlsx`.",
            "2. For each consignee that should always go pallet-pick "
            "(e.g. Coles/Woolies VIC/NSW chocolate), set "
            "`override_stream` = `1_pallet_pick`.",
            "3. For consignees with a hard carton trigger (e.g. Adelaide "
            ">= 20 cartons = pallet), set `min_cartons_override` to that "
            "number.",
            "4. Save the annotated sheet as "
            "`data/routing/consignee_rules.csv` (CSV, not xlsx).",
            "5. Re-run `python scripts/route.py` to see the updated mix.",
        ])

    if not waves.per_wave.empty:
        lines.extend([
            "",
            "## Wave plan (top 15 by total cartons)",
            "",
            "| Wave | Date | Run group | Stream | Orders | Cartons | Release |",
            "|---|---|---|---|---:|---:|---|",
        ])
        top_waves = waves.per_wave.sort_values(
            "total_cartons", ascending=False
        ).head(15)
        for _, row in top_waves.iterrows():
            lines.append(
                f"| `{row['wave_id']}` | {row['receive_date']} | "
                f"{row['run_group']} | "
                f"`{row['stream']}` | "
                f"{int(row['order_count'])} | "
                f"{row['total_cartons']:.0f} | "
                f"{row['release_reason']} |"
            )

    return lines


if __name__ == "__main__":
    sys.exit(main())
