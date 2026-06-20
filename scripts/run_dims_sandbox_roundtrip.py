#!/usr/bin/env python3
"""M-DIMS-3 — the deliberate, human-confirmed first real CC write (sandbox only).

THIS SCRIPT ISSUES A REAL `PATCH /products/{id}` against the sandbox customer — but
only after a HARD STOP that prints the exact change and waits for you to type `go`.
It refuses to start unless the allow-list is EXACTLY sandbox-only (the live Forage id
must be absent), writes are enabled, and a write secret is configured.

It applies the SKU's real captured desired dims and LEAVES them in place (PLAN §4.2 /
M-DIMS-3): the captured dims are the genuine measurements, so landing them on an active
`s`-prefixed sandbox mirror is correct, not a value to restore.

Usage (run deliberately, never as part of CI):
    # .env must have CC_* creds, CC_WRITE_ENABLED=true, CC_WRITE_SECRET=...,
    # and CC_WRITE_CUSTOMER_ALLOWLIST unset or = the sandbox id ONLY.
    python scripts/run_dims_sandbox_roundtrip.py --dims-path data/dims/<capture>.xlsx

The run is fully logged. A read-back mismatch is a hard failure (non-zero exit).
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
    run_sandbox_roundtrip,
    DimsRoundtripError,
    HardStopInfo,
)
from analysis.dim_loader import load_dimensions  # noqa: E402


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (same convention as scripts/smoke_test.py)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _build_desired_lookup(dims_path: Path):
    """code → {length,width,height,weight} from the captured dims (mm / kg, no conversion)."""
    df = load_dimensions(dims_path)
    table: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = str(row["product_code"]).strip()
        dims = {
            "length": row.get("outer_l_mm"),
            "width": row.get("outer_w_mm"),
            "height": row.get("outer_h_mm"),
            "weight": row.get("outer_weight_kg"),
        }
        # only offer fully-measured SKUs as desired targets
        if all(v is not None and v == v for v in (dims["length"], dims["width"], dims["height"])):
            table[code] = dims
    return lambda code: table.get(code)


def _confirm(info: HardStopInfo) -> bool:
    """Print the hard-stop block and require the operator to type 'go'."""
    print(
        "\n================ M-DIMS-3 HARD STOP — confirm before the real PATCH ===========\n"
        f"  SKU            : {info.product_id}  ({info.code})\n"
        f"  current dims   : {info.current_dims}   (read from CC)\n"
        f"  desired dims   : {info.desired_dims}\n"
        f"  exact diff     : {info.diff}\n"
        f"  about to fire  : {info.verb} {info.endpoint}\n"
        f"  write_enabled  : {info.write_enabled}\n"
        f"  sandbox-only   : {info.allowlist_is_sandbox_only}\n"
        "==============================================================================="
    )
    answer = input("Type 'go' to issue the real PATCH (anything else aborts): ").strip()
    return answer == "go"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims-path", required=True, type=Path, help="captured dims capture template (.xlsx)")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="path to .env (default ./.env)")
    args = parser.parse_args()

    _load_dotenv(args.env)

    # write_enabled is read from CC_WRITE_ENABLED by from_env; the run refuses to start
    # unless it (and sandbox-only) hold.
    client = CartonCloudClient.from_env()
    config = WriteConfig.from_env()
    desired_lookup = _build_desired_lookup(args.dims_path)

    # The approval token must match CC_WRITE_SECRET (authz, W2). Prompt for it so a human
    # who holds the secret is the one approving — never read it from a flag/history.
    approval_token = getpass("Write-auth approval token (CC_WRITE_SECRET): ")

    try:
        report = run_sandbox_roundtrip(
            client=client,
            config=config,
            desired_lookup=desired_lookup,
            approval_token=approval_token,
            confirm=_confirm,
        )
    except DimsRoundtripError as exc:
        logging.error("M-DIMS-3 run failed: %s", exc)
        return 2

    if report.aborted:
        print("\nAborted at the hard stop — no PATCH fired.")
        return 0

    print(
        f"\nLANDED: {report.code} ({report.product_id}) — "
        f"dims now {report.read_back_dims} (was {report.current_dims}, diff {report.diff})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
