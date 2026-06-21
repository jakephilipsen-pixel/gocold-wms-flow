#!/usr/bin/env python3
"""M-DIMS-5b — first live Forage writes, human dims-verified (the proving run).

Jake's deliberate, eyes-on run. Writes captured dims to a DELIBERATE FEW real Forage SKUs
(one per prefix shape) so a human catches any mapping error on 3–5 SKUs before 5c writes
hundreds. Reuses the proven M-DIMS-3 write path unchanged.

Arm the gate in your shell FIRST (the 5a flag — nothing else opens the live id):

    export CC_WRITE_ENABLED=true
    export CC_WRITE_SECRET=...            # or rely on .env
    export CC_LIVE_PROMOTION=true         # ⚠ opens the live Forage write gate
    .venv/bin/python3 scripts/run_dims_live_proving.py --dims-path data/dims/dims_2026-05-13.xlsx
    # ...then, when done:
    unset CC_LIVE_PROMOTION               # the script LOUDLY reminds + exits non-zero if you forget

Flow: print the full plan (SKU → mapped base code → desired dims) BEFORE any write; then,
per SKU, GET current live dims, show current vs desired + the diff, and require you to
**type the SKU code back** to write it (a bare `go` or a wrong code SKIPS — writing nothing).
On any doubt, skip: a flagged SKU is a mapping signal, not a write. After the run: disarm.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from getpass import getpass
from pathlib import Path

# allow running without installing: src/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cc_client import CartonCloudClient, WriteConfig  # noqa: E402
from dims_write import (  # noqa: E402
    build_live_proving_plan,
    run_live_proving,
    finalize_exit,
    LiveHardStopInfo,
    LiveProvingPlan,
    LiveProvingRefused,
    DimsRoundtripError,
)
from analysis.dim_loader import load_dimensions  # noqa: E402

log = logging.getLogger("dims_live_proving")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _captured_table(dims_path: Path) -> dict[str, dict]:
    """Captured dims keyed by base Forage code (fully-measured L/W/H only); same as 5a/5b."""
    df = load_dimensions(dims_path)
    table: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = str(row["product_code"]).strip()
        dims = {
            "length": row.get("outer_l_mm"), "width": row.get("outer_w_mm"),
            "height": row.get("outer_h_mm"), "weight": row.get("outer_weight_kg"),
        }
        if all(v is not None and v == v for v in (dims["length"], dims["width"], dims["height"])):
            table[code] = dims
    return table


def _print_plan(plan: LiveProvingPlan) -> None:
    print("\n================ M-DIMS-5b PLAN — mapping decisions, BEFORE any write =========")
    print(f"  selected (one per prefix shape): {len(plan.selected)}")
    for t in plan.selected:
        arrow = f"{t.code} → {t.base_code}" + ("  (uppercase-S strip)" if t.code != t.base_code and t.base_code in t.code else "")
        print(f"     {arrow:<34} desired {t.desired_dims}")
    if plan.unresolvable:
        print(f"  unresolvable (reported, NOT written): {[u['code'] for u in plan.unresolvable]}")
    print("  Eyeball each code → base mapping NOW. If a mapping looks wrong, skip that SKU at its hard stop.")
    print("==============================================================================")


def _confirm(info: LiveHardStopInfo) -> str:
    """Per-SKU hard stop. Show current vs desired + the diff, then require the SKU code typed back."""
    print("\n---------------- M-DIMS-5b LIVE SKU — confirm by typing its code ----------------")
    print(f"  live SKU       : {info.code}   (mapped from captured base {info.base_code})")
    print(f"  current (live) : {info.current_dims}   (read from CC; unset reads as None)")
    print(f"  desired        : {info.desired_dims}   (mm L/W/H, kg weight)")
    print(f"  diff (to write): {info.diff}")
    print(f"  about to fire  : PATCH {info.endpoint}  (UoM {info.uom}, Accept-Version 8)")
    print("  Does this base-code mapping and these dims belong to THIS SKU? If unsure, skip.")
    return input(f"  To WRITE, type the SKU code exactly  →  {info.code}  : ")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims-path", required=True, type=Path, help="captured dims template (.xlsx)")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="path to .env (default ./.env)")
    parser.add_argument("--max", type=int, default=5, help="max SKUs to prove (default 5)")
    args = parser.parse_args()

    _load_dotenv(args.env)
    exit_code = 0
    try:
        client = CartonCloudClient.from_env()
        config = WriteConfig.from_env()
        captured = _captured_table(args.dims_path)

        # Read-only: build + print the plan (mapping decisions visible BEFORE any write).
        plan = build_live_proving_plan(client, captured, max_total=args.max)
        _print_plan(plan)
        if not plan.selected:
            print("\nNothing to prove (no resolvable live SKUs selected). Exiting.")
            return 0

        if not config.live_promotion:
            print("\nPREVIEW ONLY — CC_LIVE_PROMOTION is not armed, so nothing will be written.")
            print("Review the plan above; if it looks right, `export CC_LIVE_PROMOTION=true` and re-run.")
            return 0

        # The approval token (W2) is prompted so a human holding the secret approves.
        approval_token = getpass("Write-auth approval token (CC_WRITE_SECRET): ")

        report = run_live_proving(
            client=client, config=config, plan=plan,
            approval_token=approval_token, confirm=_confirm,
        )

        print("\n=== M-DIMS-5b proving result (the go/no-go evidence for 5c) ===")
        print(f"  WRITTEN + verified ({len(report.written)}):")
        for w in report.written:
            print(f"     {w['code']}  (base {w['base_code']})  → {w['after']}")
        print(f"  SKIPPED ({len(report.skipped)}) — each is a mapping signal, not a write:")
        for s in report.skipped:
            print(f"     {s['code']}: {s['reason']}")
        if report.unresolvable:
            print(f"  UNRESOLVABLE ({len(report.unresolvable)}): {[u['code'] for u in report.unresolvable]}")
        print("  → If every written mapping looked right and nothing surprised you, that's the 5c go.")
        # The go/no-go is human-judged from this report, so a clean run exits 0; the only thing
        # that forces non-zero below is a still-armed flag (the structural safeguard).
        exit_code = 0

    except LiveProvingRefused as e:
        print(f"\n❌ refused to start: {e}", file=sys.stderr)
        exit_code = 1
    except DimsRoundtripError as e:
        print(f"\n❌ proving run error: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        # Structural still-armed safeguard: on EVERY exit path, if CC_LIVE_PROMOTION is still
        # armed, force a non-zero code + a loud reminder. The process can never exit 0 armed.
        exit_code, reminder = finalize_exit(os.environ, exit_code)
        if reminder:
            print(reminder, file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
