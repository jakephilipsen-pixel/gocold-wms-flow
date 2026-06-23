#!/usr/bin/env python3
"""M-DIMS-3 shadow validation — preview the corrected dims PATCH, write NOTHING.

Runs the SAME candidate gather + writable-SKU selection the live sandbox round-trip
uses, then drives the full gate chain (`approve_dims_write`) with the M-DIMS-2
`shadow_mutate_fn` recorder injected in place of the live `_mutate`. So it prints the
exact ``PATCH /warehouse-products/{id}`` JSON-Patch body the live run would fire — and
sends nothing to CartonCloud.

Read-only against CC: one GET per candidate until a writable SKU is found, then one
more GET inside the chain. No PATCH is ever issued (the recorder never calls `_mutate`).

    python scripts/run_dims_shadow_validate.py --dims-path data/dims/dims_2026-05-13.xlsx

Use this to confirm the write *shape* (endpoint, UoM target, JSON-Patch ops, diff)
before the human-gated live run in `scripts/run_dims_sandbox_roundtrip.py`.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# allow running without installing: src/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cc_client import CartonCloudClient, WriteConfig, MutateRateLimiter  # noqa: E402
from dims_write import (  # noqa: E402
    approve_dims_write,
    shadow_mutate_fn,
    gather_active_sandbox_candidates,
    select_writable_sandbox_sku,
    sandbox_desired_lookup,
    captured_cc_dims_table,
)
from analysis.dim_loader import load_dimensions  # noqa: E402

log = logging.getLogger("dims_shadow_validate")


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
    """Sandbox SKU code → captured {length,width,height,weight} in CC units (cm / kg).

    Identical to the live round-trip's lookup so shadow selects the SAME SKU live would.
    `captured_cc_dims_table` converts the mm capture columns to centimetres (CC's unit) and
    offers only fully-measured SKUs (L/W/H present).
    """
    table = captured_cc_dims_table(load_dimensions(dims_path))
    return sandbox_desired_lookup(table)


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

    print("\n================ M-DIMS-3 SHADOW VALIDATE — no CC write will occur ============")

    candidates = gather_active_sandbox_candidates(client)
    print(f"  active s-prefixed sandbox candidates : {len(candidates)}")

    selection, skipped = select_writable_sandbox_sku(client, candidates, desired_lookup)
    if selection is None:
        print(f"  no writable sandbox SKU (skipped={skipped})")
        print("==============================================================================")
        return 1

    print(f"  selected SKU   : {selection.code}  ({selection.product_id})  UoM={selection.uom}")
    print(f"  current dims   : {selection.current_dims}   (read from CC, unset reads as None)")
    print(f"  desired dims   : {selection.desired_dims}   (mm L/W/H, kg weight — units unconfirmed)")
    print(f"  exact diff     : {selection.diff}")

    # Drive the FULL gate chain with the recorder injected — same path as live, no write.
    # The approval token comes from the env secret so authz (W2) engages without a prompt;
    # the recorder never calls _mutate, so nothing is written regardless.
    recorder = shadow_mutate_fn(selection.product_id, selection.uom)
    result = approve_dims_write(
        selection.product_id,
        client=client,
        config=config,
        desired_dims=selection.desired_dims,
        mutate_fn=recorder,
        rate_limiter=MutateRateLimiter(),
        approval_token=config.write_secret,
    )

    print("\n  WOULD PATCH (shadow — NOT sent to CartonCloud):")
    for rec in recorder.records:
        print(f"    {rec['path']}")
        for op in rec["ops"]:
            print(f"      {op}")
    if not recorder.records:
        print("    (none — diff was empty)")

    print(f"\n  no_op={result.no_op}  diff={result.diff}")
    print("  ✅ shadow validate complete — CC untouched. Run run_dims_sandbox_roundtrip.py to write.")
    print("==============================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
