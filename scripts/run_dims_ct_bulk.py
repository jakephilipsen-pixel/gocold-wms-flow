#!/usr/bin/env python3
"""M-DIMS-5c — bulk-write captured CARTON dims to the CT carton UoM (live Forage).

Jake's deliberate, ARMED run. Writes the captured carton/outer dims to the **CT carton
unit-of-measure** of every active live Forage SKU that has one (~81). This exists because
5b found ~88 SKUs carry a carton UoM and a blind "write to the default UoM" would
mis-dimension the EACH on every one (the AE-2CB finding). 5c is CT-only by decision:

  - IN : live Forage SKUs with a CT UoM -> carton dims written to the CT UoM.
  - OUT: the ~367 EA-only SKUs (each = default, handled elsewhere) and the 7 CTN/PLT no-EA
         SKUs (a different shape, deferred to a later milestone). Both fall out cleanly as
         "skipped: no CT UoM" — there is NO fall-through to the each, and no guessing at CTN.

Reuse, don't fork: every write goes through the proven M-DIMS-4 bulk loop unchanged — the 5a
gate, ONE batch hard stop, paced fail-fast, write_and_verify + read-back (now verifying the CT
UoM specifically), W4 idempotency. Only the target customer (live) and the UoM resolver (CT)
differ.

Arm the gate in your shell FIRST (the 5a flag — nothing else opens the live id):

    export CC_WRITE_ENABLED=true
    export CC_WRITE_SECRET=...            # or rely on .env
    export CC_LIVE_PROMOTION=true         # ⚠ opens the live Forage write gate
    .venv/bin/python3 scripts/run_dims_ct_bulk.py --dims-path data/dims/dims_2026-05-13.xlsx
    # ...then, when done:
    unset CC_LIVE_PROMOTION               # the script LOUDLY reminds + exits non-zero if you forget

Disarmed, the script is a safe PREVIEW: it builds + prints the full plan (every CT SKU -> its
resolved CT UoM id -> carton dims -> diff) and writes nothing. Armed, it shows ONE batch hard
stop with that same plan and requires a single `go` before any PATCH; then fail-fast per SKU.

KNOWN-PARTIAL by design: this writes the CARTON (CT) dims only. The each-level (Base UoM) dims
for these SKUs stay EMPTY — that is 5d's job (each capture via the app), not 5c's.
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
    build_bulk_plan,
    run_ct_bulk,
    resolve_ct_uom,
    format_ct_bulk_report,
    sandbox_desired_lookup,
    gather_active_live_candidates,
    finalize_exit,
    BulkPlan,
    DimsRoundtripError,
)
from analysis.dim_loader import load_dimensions  # noqa: E402

log = logging.getLogger("dims_ct_bulk")


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (same convention as the other dims run scripts)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _captured_table(dims_path: Path) -> dict[str, dict]:
    """Captured CARTON/outer dims keyed by base Forage code (fully-measured L/W/H only).

    The same table 5a/5b use. These are OUTER carton dims (mm L/W/H, kg weight) — exactly what
    belongs on the CT carton UoM. Only SKUs with full L/W/H are offered; a missing/NaN weight is
    handled downstream (written without weight, not skipped).
    """
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


def _render_plan(plan: BulkPlan) -> str:
    """The full plan: each CT SKU -> its resolved CT UoM id -> carton dims -> diff.

    Shown both as the disarmed PREVIEW and as the armed batch hard stop, so a human sees the
    UoM resolution for ALL CT SKUs before any write.
    """
    lines = [
        "",
        "=" * 80,
        "  M-DIMS-5c BATCH HARD STOP — LIVE FORAGE — review the CT-UoM resolution for ALL",
        "=" * 80,
        f"  CT SKUs to write : {len(plan.to_write)}   (each -> its resolved CT UoM id -> carton dims -> diff)",
    ]
    for item in plan.to_write:
        lines.append(f"     {item.code:<14} CT-uom={item.uom:<12} dims={item.desired_dims}  diff={item.diff}")
    n_no_ct = sum(1 for s in plan.skipped if s.get("reason") == "no CT UoM")
    other = [(s["code"], s["reason"]) for s in plan.skipped if s.get("reason") != "no CT UoM"]
    lines += [
        f"  already-correct (no-op) : {len(plan.no_ops)}",
        f"  skipped — no CT UoM     : {n_no_ct}  (the ~367 each-only + 7 CTN/PLT SKUs — NOT 5c's job)",
    ]
    if other:
        lines.append(f"  skipped — other         : {other}")
    lines += [
        f"  endpoint : PATCH {plan.endpoint}  (per SKU, Accept-Version 8)",
        f"  write_enabled : {plan.write_enabled}    sandbox-base allow-list : {plan.allowlist_is_sandbox_only}",
        "  The live id is writable ONLY because CC_LIVE_PROMOTION is armed; W3 re-checks it per write.",
        "  Fail-fast: the first write/verify failure stops the run; earlier SKUs stay written (known-good).",
        "  Each-level (Base UoM) dims for these SKUs stay EMPTY — that's 5d, not 5c.",
        "=" * 80,
    ]
    return "\n".join(lines)


def _confirm(plan: BulkPlan) -> bool:
    """Print the ONE batch hard stop and require a single `go` for the whole batch."""
    print(_render_plan(plan))
    if not plan.to_write:
        print("  Nothing to write (all no-op / skipped). Aborting.")
        return False
    answer = input(
        f"Type 'go' to write CT carton dims to {len(plan.to_write)} LIVE Forage SKUs "
        "(anything else aborts): "
    ).strip()
    return answer == "go"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims-path", required=True, type=Path, help="captured dims template (.xlsx)")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="path to .env (default ./.env)")
    args = parser.parse_args()

    _load_dotenv(args.env)
    exit_code = 0
    try:
        client = CartonCloudClient.from_env()
        config = WriteConfig.from_env()
        # Captured carton dims keyed by base code; live codes ARE base codes (resolve_base_code
        # direct-matches them — the s-strip branch simply never fires for live FP-/HI-/AE- codes).
        desired_lookup = sandbox_desired_lookup(_captured_table(args.dims_path))

        if not config.live_promotion:
            # PREVIEW ONLY — build + print the plan read-only (GETs only), write nothing.
            plan = build_bulk_plan(
                client, gather_active_live_candidates(client), desired_lookup,
                config=config, uom_resolver=resolve_ct_uom, no_uom_reason="no CT UoM",
            )
            print(_render_plan(plan))
            print("\nPREVIEW ONLY — CC_LIVE_PROMOTION is not armed, so nothing was written.")
            print("Review the CT-UoM resolution above; if it looks right, `export CC_LIVE_PROMOTION=true` and re-run.")
            return 0

        # ARMED. The approval token (W2) is prompted so a human holding the secret approves —
        # never read from a flag/history. The live gate + CT resolution happen inside run_ct_bulk.
        approval_token = getpass("Write-auth approval token (CC_WRITE_SECRET): ")
        report = run_ct_bulk(
            client=client, config=config, desired_lookup=desired_lookup,
            approval_token=approval_token, confirm=_confirm,
        )

        if report.aborted:
            print("\nABORTED at the batch hard stop — nothing written.")
            exit_code = 1
        else:
            print("\n" + format_ct_bulk_report(report))
            if report.failed:
                print(f"\n  fix the cause and re-run — the {len(report.written)} written SKUs will no-op (idempotent).")
                exit_code = 1
            else:
                print("\n  ✅ all CT-cohort writable SKUs landed + read-back verified on the CT UoM.")
                exit_code = 0

    except DimsRoundtripError as e:
        print(f"\n❌ 5c bulk refused/failed to start: {e}", file=sys.stderr)
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
