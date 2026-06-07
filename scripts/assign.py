#!/usr/bin/env python3
"""Generate the SKU → location assignment.

Pipeline:
  1. Load latest CC extract (SOs, POs, products) from data/raw/
  2. Load latest dims xlsx from data/dims/
  3. Load latest locations xlsx from data/locations/
  4. Compute velocity, apply tags, filter full-pallet skews
  5. Run greedy SKU → pick-face assignment
  6. Write everything to data/processed/assign_<timestamp>/

Usage:
    python scripts/assign.py

    # or specify files
    python scripts/assign.py --dims data/dims/dims_2026-05-14.xlsx \\
                              --locations data/locations/WarehouseLocations-2026-05-14.xlsx
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analysis import (  # noqa: E402
    apply_tags,
    assign_skus_to_locations,
    compute_velocity,
    load_dimensions,
    load_latest,
    run_full_pallet_analysis,
)
from locations import load_cc_locations  # noqa: E402

log = logging.getLogger("assign")


def _latest_file(dirpath: Path, pattern: str) -> Path | None:
    candidates = sorted(
        dirpath.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parent.parent
    p.add_argument("--raw", type=Path, default=repo_root / "data" / "raw")
    p.add_argument("--dims", type=Path, default=None,
                   help="dim xlsx file (default: latest in data/dims/)")
    p.add_argument("--locations", type=Path, default=None,
                   help="CC locations xlsx (default: latest in data/locations/)")
    p.add_argument("--out", type=Path, default=repo_root / "data" / "processed")
    p.add_argument("--pallet-ratio", type=float, default=0.9)
    args = p.parse_args()

    logging.basicConfig(
        level="INFO",
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 1. CC extract
    print("loading snapshot...")
    snap = load_latest(args.raw)
    print(f"  ✓ {len(snap.so_lines):,} SO lines, {len(snap.products):,} products")

    # 2. dims
    dim_path = args.dims or _latest_file(repo_root / "data" / "dims", "dims_*.xlsx")
    if not dim_path or not dim_path.exists():
        print("❌ no dim file found in data/dims/", file=sys.stderr)
        return 2
    print(f"loading dims from {dim_path.name}...")
    dims = load_dimensions(dim_path)
    print(f"  ✓ {dims['measurement_complete'].sum()}/{len(dims)} SKUs measured")

    # 3. locations
    loc_path = args.locations or _latest_file(
        repo_root / "data" / "locations", "*.xlsx"
    )
    if not loc_path or not loc_path.exists():
        print(
            "❌ no locations file in data/locations/. "
            "Save CC's UI export there as WarehouseLocations-*.xlsx",
            file=sys.stderr,
        )
        return 2
    print(f"loading locations from {loc_path.name}...")
    locations = load_cc_locations(loc_path)
    pf_count = int(locations["is_pick_face"].sum())
    print(f"  ✓ {len(locations)} CC locations, {pf_count} pick faces")

    # 4. velocity + tagging + filter
    print("computing velocity + tags + full-pallet filter...")
    raw_vel = compute_velocity(snap)
    tagged_raw = apply_tags(raw_vel.sku_metrics, dims)
    full_pallet = run_full_pallet_analysis(
        snap, dims, tagged_raw, ratio=args.pallet_ratio,
    )
    cleaned_metrics = apply_tags(full_pallet.cleaned_velocity.sku_metrics, dims)
    cleaned_metrics = cleaned_metrics.sort_values("units_per_day", ascending=False)
    print(f"  ✓ velocity computed, {full_pallet.n_flagged} TC full-pallet lines excluded")

    # 5. assignment
    print("running SKU → pick-face assignment...")
    result = assign_skus_to_locations(cleaned_metrics, dims, locations)
    print(
        f"  ✓ assigned: {len(result.assignments)}, "
        f"unassigned: {len(result.unassigned)}, "
        f"unused pick faces: {len(result.unused)}"
    )

    # 6. write outputs
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out / f"assign_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nwriting to {out_dir}/")

    result.assignments.to_csv(out_dir / "assignments.csv", index=False)
    result.assignments.to_excel(out_dir / "assignments.xlsx", index=False)
    print("  ✓ assignments.csv + .xlsx (THE deliverable)")

    result.coverage.to_csv(out_dir / "coverage.csv", index=False)
    print("  ✓ coverage.csv (supply vs demand by product type × position)")

    result.unassigned.to_csv(out_dir / "unassigned.csv", index=False)
    if len(result.unassigned):
        print(f"  ✓ unassigned.csv ({len(result.unassigned)} SKUs need attention)")
    else:
        print("  ✓ unassigned.csv (empty — everything got placed)")

    result.unused.to_csv(out_dir / "unused_pick_faces.csv", index=False)
    print(f"  ✓ unused_pick_faces.csv ({len(result.unused)} spare slots)")

    # quick text summary
    summary_lines = [
        "# SKU → Location Assignment",
        f"_Generated: {datetime.now():%Y-%m-%d %H:%M}_",
        "",
        "## Headline",
        f"- **{len(result.assignments)}** SKUs assigned to specific pick faces",
        f"- **{len(result.unassigned)}** SKUs could not be placed (see unassigned.csv)",
        f"- **{len(result.unused)}** pick faces left empty / spare",
        "",
        "## Coverage by product type × position",
        "",
        "| Product type | Position | Demand SKUs | Supply pick faces | Surplus/Deficit |",
        "|---|---|---|---|---|",
    ]
    for _, row in result.coverage.iterrows():
        surplus = int(row["surplus_or_deficit"])
        sd = f"+{surplus}" if surplus >= 0 else f"{surplus}"
        summary_lines.append(
            f"| {row['required_product_type']} | "
            f"{int(row['required_position']) if row['required_position'] else '—'} | "
            f"{int(row['demand_skus'])} | {int(row['supply_pick_faces'])} | {sd} |"
        )

    summary_lines.extend([
        "",
        "## Top 10 assignments by velocity",
        "",
        "| Code | Name | u/d | Product type | Pos | Location |",
        "|---|---|---|---|---|---|",
    ])
    for _, row in result.assignments.head(10).iterrows():
        summary_lines.append(
            f"| `{row['product_code']}` | {str(row['product_name'])[:35]} | "
            f"{row['units_per_day']:.1f} | {row['required_product_type']} | "
            f"{row['required_position']} | `{row['assigned_location']}` |"
        )

    if len(result.unassigned):
        summary_lines.extend([
            "",
            "## Unassigned SKUs",
            "",
            "These SKUs need a pick face but supply is short. Either reclassify",
            "them, add more pick faces, or move SKUs out of crowded zones.",
            "",
        ])
        for _, row in result.unassigned.head(20).iterrows():
            summary_lines.append(
                f"- `{row['product_code']}` ({row['units_per_day']:.1f} u/d) — "
                f"{row['reason']}"
            )

    (out_dir / "summary.md").write_text("\n".join(summary_lines))
    print(f"  ✓ summary.md")

    print(f"\n✅ done. open {out_dir / 'summary.md'}")
    print(f"   key file → {out_dir / 'assignments.xlsx'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
