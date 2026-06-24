#!/usr/bin/env python3
"""M-DIMS-4 — sandbox bulk dims soak: write captured dims to ALL active sandbox SKUs.

The deliberate, human-confirmed run. Generalises the single M-DIMS-3 round-trip to the
whole active sandbox set via ``run_sandbox_bulk``: build the full plan, show ONE batch
hard stop, require a single ``go``, then write + read-back verify each SKU — FAIL-FAST on
the first failure, PACED so the rate limiter is never tripped. SANDBOX ONLY
(``assert_write_target_allowed`` refuses any non-sandbox base allow-list; this script
does NOT arm ``CC_LIVE_PROMOTION``, so the live Forage id stays unwritable).

    python scripts/run_dims_bulk_sandbox.py --dims-path data/dims/dims_2026-05-13.xlsx

Re-runnable: SKUs already written no-op (W4 idempotency), so after a fail-fast stop you
fix the cause and re-run to resume. Preview with ``run_dims_shadow_validate.py`` first.
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
    run_sandbox_bulk,
    sandbox_desired_lookup,
    captured_cc_dims_table,
    BulkPlan,
    DimsRoundtripError,
)
from analysis.dim_loader import load_dimensions  # noqa: E402

log = logging.getLogger("dims_bulk_sandbox")


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (same convention as scripts/run_dims_sandbox_roundtrip.py)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _build_desired_lookup(dims_path: Path):
    """Sandbox SKU code → captured {length,width,height,weight} in CC units (metres / kg).

    Same lookup the single round-trip uses; `captured_cc_dims_table` converts the mm capture
    columns to metres (CC's unit) and offers only fully-measured SKUs (L/W/H present).
    Missing/NaN weight is handled downstream (written without weight, not skipped).
    """
    table = captured_cc_dims_table(load_dimensions(dims_path))
    return sandbox_desired_lookup(table)


def _confirm(plan: BulkPlan) -> bool:
    """Print the ONE batch hard stop and require a single ``go`` for the whole batch."""
    print("\n================ M-DIMS-4 BULK HARD STOP — one 'go' covers the batch =========")
    print(f"  to write       : {len(plan.to_write)} SKUs")
    for item in plan.to_write:
        print(f"     {item.code:<12} UoM={item.uom}  {item.diff}")
    print(f"  no-op (match)  : {len(plan.no_ops)}")
    print(f"  skipped        : {len(plan.skipped)}  ({[s['code'] for s in plan.skipped]})")
    print(f"  endpoint       : PATCH {plan.endpoint}  (per SKU, Accept-Version 8)")
    print(f"  write_enabled  : {plan.write_enabled}")
    print(f"  sandbox-only   : {plan.allowlist_is_sandbox_only}")
    print("  Fail-fast: the first write/verify failure stops the run; earlier SKUs stay written.")
    print("==============================================================================")
    if not plan.to_write:
        print("  Nothing to write (all no-op/skipped). Aborting.")
        return False
    answer = input(f"Type 'go' to write {len(plan.to_write)} sandbox SKUs (anything else aborts): ").strip()
    return answer == "go"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims-path", required=True, type=Path, help="captured dims template (.xlsx)")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="path to .env (default ./.env)")
    args = parser.parse_args()

    _load_dotenv(args.env)

    client = CartonCloudClient.from_env()
    config = WriteConfig.from_env()
    desired_lookup = _build_desired_lookup(args.dims_path)

    # The approval token (authz, W2) is prompted so a human who holds the secret approves —
    # never read from a flag/history. Sandbox-only is asserted inside run_sandbox_bulk.
    approval_token = getpass("Write-auth approval token (CC_WRITE_SECRET): ")

    try:
        report = run_sandbox_bulk(
            client=client,
            config=config,
            desired_lookup=desired_lookup,
            approval_token=approval_token,
            confirm=_confirm,
        )
    except DimsRoundtripError as e:
        print(f"\n❌ bulk soak refused/failed to start: {e}", file=sys.stderr)
        return 1

    if report.aborted:
        print("\nABORTED at the batch hard stop — nothing written.")
        return 1

    print("\n=== M-DIMS-4 bulk soak result ===")
    print(f"  written : {len(report.written)}")
    print(f"  no-op   : {len(report.no_ops)}")
    print(f"  skipped : {len(report.skipped)}")
    if report.failed:
        print(f"  ❌ FAILED at {report.failed['code']}: {report.failed['error']}")
        print(f"     untouched after failure: {report.untouched_after_failure}")
        print(f"     fix the cause and re-run — the {len(report.written)} written SKUs will no-op.")
        return 1
    print("  ✅ all writable SKUs landed + read-back verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
