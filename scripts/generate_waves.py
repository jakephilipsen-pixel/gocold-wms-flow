#!/usr/bin/env python3
"""Generate operator-ready wave pick sheets from live open CartonCloud SOs.

Pipeline:
  1. Pull live outbound orders in ``AWAITING_PICK_AND_PACK`` status from
     CC (no stale parquet — open orders move fast).
  2. Save the pull to ``data/raw/so_lines_open_<timestamp>.parquet`` as
     an audit trail.
  3. Build a working Snapshot from the live SO pull + the most recent
     PO/products parquets in ``data/raw/``.
  4. Run routing (velocity -> tags -> full_pallet -> order_metrics ->
     classify_streams), reusing the existing pipeline.
  5. Load CC locations + latest SKU assignments.
  6. Call ``generate_wave_pick_sheets``.
  7. For each wave, write PDF + picks CSV + orders CSV into
     ``data/processed/waves/<timestamp>/<wave_id>/``.
  8. Write a top-level ``index.md`` listing every wave with quick stats.

Read-only against CC — we generate paperwork. The operator creates the
wave in CC manually using the SO list we hand them.

Usage:
    python scripts/generate_waves.py

    # tune routing params
    python scripts/generate_waves.py --pallet-fraction-threshold 0.65 \\
                                     --early-release-cartons 25

    # custom logo
    python scripts/generate_waves.py --logo path/to/logo.png

    # different status (default: AWAITING_PICK_AND_PACK)
    python scripts/generate_waves.py --status AWAITING_PICK_AND_PACK

    # restrict to one customer
    python scripts/generate_waves.py --customer-name "The Forage Company"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analysis import (  # noqa: E402
    DEFAULT_AWAITING_STATUS,
    DEFAULT_EARLY_RELEASE_CARTONS,
    DEFAULT_LINES_PER_HOUR,
    DEFAULT_PALLET_FRACTION_THRESHOLD,
    apply_tags,
    classify_streams,
    compute_order_metrics,
    compute_velocity,
    generate_wave_pick_sheets,
    load_consignee_rules,
    load_dimensions,
    load_latest,
    run_full_pallet_analysis,
)
from analysis.loaders import Snapshot  # noqa: E402
from cc_client import (  # noqa: E402
    CartonCloudClient,
    CartonCloudError,
    get_sku_locations,
    search_outbound_orders,
)
from locations import load_cc_locations  # noqa: E402
from output import generate_wave_pdf, write_wave_csvs  # noqa: E402

log = logging.getLogger("generate_waves")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parent.parent

    p.add_argument(
        "--status", type=str, default=DEFAULT_AWAITING_STATUS,
        help=(
            "CC outbound-order status to wave (comma-separated for "
            "multiple). Default: AWAITING_PICK_AND_PACK."
        ),
    )
    p.add_argument(
        "--customer-name", type=str, default=None,
        help="optional CC customer name (exact match)",
    )

    p.add_argument("--raw", type=Path, default=repo_root / "data" / "raw")
    p.add_argument(
        "--locations", type=Path, default=None,
        help="CC locations xlsx (default: latest in data/locations/)",
    )
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
    p.add_argument(
        "--assignments", type=Path, default=None,
        help=(
            "SKU -> location assignments CSV (default: latest in "
            "data/processed/assign_*/assignments.csv)"
        ),
    )
    p.add_argument(
        "--soh-fallback", action="store_true",
        help=(
            "if a SKU has no assignment, query CC stock-on-hand for its "
            "current location. Off by default (one extra report-run per "
            "call, can take 30-60s)."
        ),
    )

    p.add_argument(
        "--pallet-ratio", type=float, default=0.9,
        help="threshold for full_pallet line detection (existing analysis)",
    )
    p.add_argument(
        "--pallet-fraction-threshold", type=float,
        default=DEFAULT_PALLET_FRACTION_THRESHOLD,
    )
    p.add_argument(
        "--early-release-cartons", type=int,
        default=DEFAULT_EARLY_RELEASE_CARTONS,
    )
    p.add_argument(
        "--run-group-col", type=str, default="delivery_state",
    )

    p.add_argument(
        "--logo", type=Path,
        default=repo_root / "assests" / "gocold_logo.png",
        help="Go Cold logo for the PDF cover. Skipped gracefully if missing.",
    )
    p.add_argument(
        "--lines-per-hour", type=int, default=DEFAULT_LINES_PER_HOUR,
        help="pick rate assumption for time-to-pick estimate",
    )

    p.add_argument(
        "--out", type=Path, default=repo_root / "data" / "processed" / "waves",
        help="output base directory",
    )

    args = p.parse_args()

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _load_dotenv(repo_root / ".env")

    # 1. live SO pull
    statuses = [s.strip() for s in args.status.split(",") if s.strip()]
    client = CartonCloudClient.from_env()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = args.raw / f"so_lines_open_{stamp}.parquet"
    so_lines = _pull_open_orders(
        client,
        status=statuses,
        customer_name=args.customer_name,
        out_path=audit_path,
    )

    if so_lines.empty:
        print("no open orders to wave. exiting.")
        out_dir = args.out / stamp
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.md").write_text(
            f"# Wave Pick Run\n_{datetime.now():%Y-%m-%d %H:%M}_\n\n"
            f"No orders matched status `{args.status}` "
            f"(customer={args.customer_name!r}).\n"
        )
        return 0

    # 2. snapshot (live SO + latest PO + products)
    snap = _build_snapshot(so_lines, args.raw)

    # 3. dims
    dim_path = args.dims or _latest_file(repo_root / "data" / "dims", "dims_*.xlsx")
    if not dim_path or not dim_path.exists():
        print("ERROR: no dim file in data/dims/", file=sys.stderr)
        return 2
    print(f"loading dims from {dim_path.name}...")
    dims = load_dimensions(dim_path)
    print(f"  + {int(dims['measurement_complete'].sum())}/{len(dims)} SKUs measured")

    # 4. routing pipeline
    rules_path = args.rules or _latest_file(
        repo_root / "data" / "routing", "consignee_rules*.csv"
    )
    rules = load_consignee_rules(rules_path)
    print(f"loaded {len(rules)} consignee rules")

    print("computing velocity + tags + full-pallet flags...")
    raw_vel = compute_velocity(snap)
    apply_tags(raw_vel.sku_metrics, dims)
    full_pallet = run_full_pallet_analysis(
        snap, dims, raw_vel.sku_metrics, ratio=args.pallet_ratio,
    )

    print("rolling SO lines into per-order metrics...")
    metrics = compute_order_metrics(snap, dims, full_pallet)
    print(
        f"  + {metrics.n_orders:,} orders "
        f"({metrics.n_orders_with_dims} full dim coverage)"
    )

    print(
        f"classifying streams "
        f"(pallet_fraction_threshold={args.pallet_fraction_threshold:.2f})..."
    )
    classification = classify_streams(
        metrics, rules,
        pallet_fraction_threshold=args.pallet_fraction_threshold,
    )
    for stream, n in classification.counts_by_stream.items():
        print(f"  + {stream}: {int(n)}")

    # 5. locations
    loc_path = args.locations or _latest_file(
        repo_root / "data" / "locations", "*.xlsx"
    )
    if not loc_path or not loc_path.exists():
        print("ERROR: no locations xlsx in data/locations/", file=sys.stderr)
        return 2
    print(f"loading locations from {loc_path.name}...")
    locations = load_cc_locations(loc_path)

    # 6. assignments (optional but strongly recommended)
    assignments_df: pd.DataFrame | None = None
    assignments_path = args.assignments or _latest_assignments(
        repo_root / "data" / "processed"
    )
    if assignments_path and assignments_path.exists():
        print(f"loading assignments from {assignments_path}")
        assignments_df = pd.read_csv(assignments_path)
        print(f"  + {len(assignments_df)} SKU assignments")
    else:
        print(
            "no assignments file found — relying solely on SOH fallback "
            "(if enabled) or skipping orders without locations"
        )

    # 7. SOH fallback (optional, expensive)
    fallback_df: pd.DataFrame | None = None
    if args.soh_fallback:
        print("pulling SKU -> location fallback via SOH...")
        # restrict to SKUs that actually appear in the open orders, both to
        # cut report-run time AND to keep the fallback tight
        codes = sorted({c for c in so_lines["product_code"].dropna().unique()})
        # SOH requires a customer; if no --customer-name given, fall back
        # to the customer of the first open order.
        soh_customer_id = (
            so_lines.iloc[0]["customer_id"]
            if "customer_id" in so_lines.columns
            else None
        )
        if not soh_customer_id:
            print("  ! cannot run SOH fallback without a customer_id")
        else:
            try:
                items = get_sku_locations(
                    client,
                    customer_id=soh_customer_id,
                    product_codes=codes,
                )
                if items:
                    fb = pd.DataFrame(items)
                    fb = fb.rename(columns={"location_name": "location"})
                    fallback_df = fb
                    print(
                        f"  + SOH gave us {len(fb)} (SKU, location) rows "
                        f"covering {fb['product_code'].nunique()} SKUs"
                    )
                else:
                    print("  ! SOH returned no items")
            except CartonCloudError as exc:
                print(f"  ! SOH fallback failed: {exc}")

    # 8. wave pick generation
    print("generating wave pick sheets...")
    result = generate_wave_pick_sheets(
        classification=classification,
        so_lines=snap.so_lines,
        locations=locations,
        assignments=assignments_df,
        sku_locations_fallback=fallback_df,
        run_group_col=args.run_group_col,
        early_release_cartons=args.early_release_cartons,
    )
    print(
        f"  + {result.summary['n_waves']} waves, "
        f"{result.summary['n_orders_total']} orders, "
        f"{result.summary['n_orders_skipped']} skipped, "
        f"{result.summary['n_pick_lines_total']} pick lines"
    )

    # 9. write outputs
    out_dir = args.out / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nwriting waves to {out_dir}/")

    logo_path = args.logo if args.logo and Path(args.logo).exists() else None
    if args.logo and not logo_path:
        print(f"  ! logo not found at {args.logo}; PDFs will skip the logo")

    for sheet in result.sheets:
        wave_dir = out_dir / sheet.wave_id
        wave_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = wave_dir / f"{sheet.wave_id}_picksheet.pdf"
        try:
            generate_wave_pdf(
                sheet, pdf_path, logo_path=logo_path,
                lines_per_hour=args.lines_per_hour,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"  ! PDF generation failed for wave {sheet.wave_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        write_wave_csvs(sheet, wave_dir)
        print(
            f"  + {sheet.wave_id}: {sheet.total_lines} lines, "
            f"{sheet.total_cartons} cartons"
        )

    # 10. skipped report
    if not result.skipped_orders.empty:
        skipped_path = out_dir / "skipped_orders.csv"
        result.skipped_orders.to_csv(skipped_path, index=False)
        print(
            f"  + {len(result.skipped_orders)} skipped orders -> "
            f"{skipped_path.name}"
        )

    # 11. index + run manifest
    _build_index_md(out_dir, result.sheets, result.skipped_orders, args)
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "settings": {
            "status": args.status,
            "customer_name": args.customer_name,
            "pallet_fraction_threshold": args.pallet_fraction_threshold,
            "early_release_cartons": args.early_release_cartons,
            "run_group_col": args.run_group_col,
            "lines_per_hour": args.lines_per_hour,
            "assignments_path": str(assignments_path)
                if assignments_path else None,
            "soh_fallback": args.soh_fallback,
            "logo_used": str(logo_path) if logo_path else None,
            "audit_parquet": str(audit_path),
        },
        "summary": result.summary,
        "waves": [
            {
                "wave_id": s.wave_id,
                "stream": s.stream,
                "run_group": s.run_group,
                "receive_date": s.receive_date.isoformat() if s.receive_date else None,
                "total_cartons": s.total_cartons,
                "total_lines": s.total_lines,
                "n_orders": len(s.orders),
                "estimated_walk_m": s.estimated_walk_distance_m,
            }
            for s in result.sheets
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nOK. open {out_dir / 'index.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
