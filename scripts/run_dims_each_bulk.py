#!/usr/bin/env python3
"""M-DIMS-5d — bulk-write captured dims to the Each/Base UoM (live Forage).

The automated dims pipeline. M-DIMS-5c (write to the CT carton UoM) is CLOSED, not written: CC
rejects CT dims because the CT UoM name ("CT", 2 chars) fails its 3–64 char rule, and CT names
can't be edited on live master. So dims go to the **Each / Base UoM** (`defaultUnitOfMeasure`) —
every live Forage SKU has one, and the probe found all 455 names valid, so the each accepts dims
cleanly. Dims are written in **metres** (`captured_cc_dims_table` converts the mm capture ÷1000).

Reuse, don't fork: every write goes through the proven M-DIMS-4/5c bulk loop unchanged — the 5a
gate, ONE batch hard stop, paced fail-fast, write_and_verify + read-back (of the each UoM), W4
idempotency, the CC_LIVE_PROMOTION precondition. Only the UoM resolver differs (the each, not CT).

The 15 SKUs that already carry each dims are NOT special-cased: where a stored value differs from
the captured metres desired (e.g. a stale wrong-magnitude `255` vs `0.255`), the idempotent diff PATCHes it
to the correct metres value; where it matches, it no-ops.

Arm the gate in your shell FIRST (the 5a flag — nothing else opens the live id):

    export CC_WRITE_ENABLED=true
    export CC_WRITE_SECRET=...            # or rely on .env
    export CC_LIVE_PROMOTION=true         # ⚠ opens the live Forage write gate
    .venv/bin/python3 scripts/run_dims_each_bulk.py --dims-path data/dims/dims_2026-05-13.xlsx
    # ...then, when done:
    unset CC_LIVE_PROMOTION               # the script LOUDLY reminds + exits non-zero if you forget

Disarmed, the script is a safe PREVIEW: it builds + prints the full plan (every SKU -> its each
UoM id -> metres dims -> diff) and writes nothing. Armed, it shows ONE batch hard stop with that same
plan and requires a single `go` before any PATCH; then fail-fast per SKU.

FIRST RUN should be a deliberate few-SKU metres test: pass `--only FP-1,HI-2` to restrict the cohort,
eyeball those SKUs in CC to confirm the dims landed in metres, THEN drop `--only` for the bulk.
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
    run_each_bulk,
    resolve_default_uom,
    POISON_SKIP_REASON,
    format_each_bulk_report,
    sandbox_desired_lookup,
    captured_cc_dims_table,
    gather_active_live_candidates,
    finalize_exit,
    BulkPlan,
    DimsRoundtripError,
)
from analysis.dim_loader import load_dimensions  # noqa: E402

log = logging.getLogger("dims_each_bulk")


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
    """Captured dims keyed by base Forage code (fully-measured L/W/H only), in CC units (metres/kg).

    Same table 5a/5b/5c use — `captured_cc_dims_table` converts the mm capture columns to
    metres (CC's unit). Only SKUs with full L/W/H are offered; a missing/NaN weight is handled
    downstream (written without weight, not skipped).
    """
    return captured_cc_dims_table(load_dimensions(dims_path))


def _filter_only(candidates: list, only: set[str] | None) -> list:
    """Restrict the gathered candidates to an explicit code set (the deliberate few-SKU test)."""
    if not only:
        return candidates
    return [c for c in candidates if c.code in only]


def _render_plan(plan: BulkPlan, *, scoped: bool) -> str:
    """The full plan: each SKU -> its resolved each (default) UoM id -> metres dims -> diff.

    Shown both as the disarmed PREVIEW and as the armed batch hard stop, so a human sees the
    each-UoM resolution + the metres dims for ALL targeted SKUs before any write.
    """
    lines = [
        "",
        "=" * 80,
        "  M-DIMS-5d BATCH HARD STOP — LIVE FORAGE — Each/Base UoM dims (metres) for ALL",
        "=" * 80,
    ]
    if scoped:
        lines.append("  ⚠ SCOPED RUN (--only): a deliberate subset, NOT the full cohort.")
    lines.append(
        f"  SKUs to write : {len(plan.to_write)}   (each -> its default UoM id -> metres dims -> diff)"
    )
    for item in plan.to_write:
        lines.append(f"     {item.code:<14} each-uom={item.uom:<12} dims={item.desired_dims}  diff={item.diff}")
    n_no_each = sum(1 for s in plan.skipped if s.get("reason") == "no default UoM")
    blocked = [s for s in plan.skipped if str(s.get("reason", "")).startswith(POISON_SKIP_REASON)]
    other = [s for s in plan.skipped
             if s.get("reason") != "no default UoM" and not str(s.get("reason", "")).startswith(POISON_SKIP_REASON)]
    lines += [
        f"  already-correct (no-op) : {len(plan.no_ops)}",
        f"  name-poisoned (skipped — invalid UoM name blocks save) : {len(blocked)}  (fix the UoM name in CC to unblock)",
        f"  skipped — no default UoM : {n_no_each}  (none expected live — the probe found 0)",
    ]
    if blocked:
        for s in sorted(blocked, key=lambda x: x["code"])[:20]:
            lines.append(f"      {s['code']:<16} {s['reason']}")
    if other:
        lines.append(f"  skipped — other (no captured dims) : {len(other)}")
    lines += [
        f"  endpoint : PATCH {plan.endpoint}  (per SKU, Accept-Version 8)",
        f"  write_enabled : {plan.write_enabled}    sandbox-base allow-list : {plan.allowlist_is_sandbox_only}",
        "  Dims are in METRES (captured mm ÷1000). Eyeball a few in CC to confirm metres before bulk.",
        "  The live id is writable ONLY because CC_LIVE_PROMOTION is armed; W3 re-checks it per write.",
        "  Fail-fast: the first write/verify failure stops the run; earlier SKUs stay written (known-good).",
        "  Already-dimensioned SKUs (incl. any stale wrong-magnitude each) are corrected in place by the diff.",
        "=" * 80,
    ]
    return "\n".join(lines)


def _confirm_factory(scoped: bool):
    """Build the ONE batch hard stop; require a single `go` for the whole batch."""
    def _confirm(plan: BulkPlan) -> bool:
        print(_render_plan(plan, scoped=scoped))
        if not plan.to_write:
            print("  Nothing to write (all no-op / skipped). Aborting.")
            return False
        answer = input(
            f"Type 'go' to write Each/Base UoM dims (metres) to {len(plan.to_write)} LIVE Forage SKUs "
            "(anything else aborts): "
        ).strip()
        return answer == "go"
    return _confirm


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dims-path", required=True, type=Path, help="captured dims template (.xlsx)")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="path to .env (default ./.env)")
    parser.add_argument("--only", type=str, default=None,
                        help="comma-separated SKU codes to restrict the run (the deliberate few-SKU metres test)")
    args = parser.parse_args()

    only = {c.strip() for c in args.only.split(",") if c.strip()} if args.only else None
    scoped = bool(only)

    _load_dotenv(args.env)
    exit_code = 0
    try:
        client = CartonCloudClient.from_env()
        config = WriteConfig.from_env()
        # Captured dims keyed by base code; live codes ARE base codes (resolve_base_code
        # direct-matches them — the s-strip branch never fires for live FP-/HI-/AE- codes).
        desired_lookup = sandbox_desired_lookup(_captured_table(args.dims_path))
        candidates = _filter_only(gather_active_live_candidates(client), only)
        if scoped and not candidates:
            print(f"\n❌ --only matched no active live SKUs: {sorted(only)}", file=sys.stderr)
            return 1

        if not config.live_promotion:
            # PREVIEW ONLY — build + print the plan read-only (GETs only), write nothing.
            plan = build_bulk_plan(
                client, candidates, desired_lookup,
                config=config, uom_resolver=resolve_default_uom, no_uom_reason="no default UoM",
                block_on_poisoning_uom=True,
            )
            print(_render_plan(plan, scoped=scoped))
            print("\nPREVIEW ONLY — CC_LIVE_PROMOTION is not armed, so nothing was written.")
            print("Review the each-UoM resolution + metres dims above; if right, `export CC_LIVE_PROMOTION=true` and re-run.")
            return 0

        # ARMED. The approval token (W2) is prompted so a human holding the secret approves —
        # never read from a flag/history. The live gate + each resolution happen inside run_each_bulk.
        approval_token = getpass("Write-auth approval token (CC_WRITE_SECRET): ")
        report = run_each_bulk(
            client=client, config=config, desired_lookup=desired_lookup,
            approval_token=approval_token, confirm=_confirm_factory(scoped), candidates=candidates,
        )

        if report.aborted:
            print("\nABORTED at the batch hard stop — nothing written.")
            exit_code = 1
        else:
            print("\n" + format_each_bulk_report(report))
            if report.failed:
                print(f"\n  fix the cause and re-run — the {len(report.written)} written SKUs will no-op (idempotent).")
                exit_code = 1
            else:
                print("\n  ✅ all targeted SKUs landed + read-back verified on the each (Base) UoM, in metres.")
                exit_code = 0

    except DimsRoundtripError as e:
        print(f"\n❌ 5d bulk refused/failed to start: {e}", file=sys.stderr)
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
