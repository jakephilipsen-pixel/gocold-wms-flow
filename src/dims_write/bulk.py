"""M-DIMS-4 — sandbox bulk dims loop (soak).

Generalises the single M-DIMS-3 round-trip to all active s-prefixed sandbox SKUs,
reusing the EXACT write+verify path (``write_and_verify`` → ``build_dims_patch`` →
``_mutate`` → read-back). PLAN §4 step 3 / MODULES.md M-DIMS-4 (``dims-sandbox-soak``).

Safety posture (Jake's decisions):
  - ONE batch-level hard stop. The full plan (every writable SKU + its diff) is built
    and shown BEFORE any write; one ``go`` covers the batch — no per-SKU prompting.
  - FAIL-FAST. The first SKU whose write or read-back verify fails stops the run; the
    SKUs already written are known-good (each read-back verified), the rest untouched.
    No rollback — already-written correct dims are harmless. A re-run resumes via W4
    idempotency: the already-correct SKUs no-op.
  - SANDBOX ONLY. ``assert_sandbox_only`` refuses unless the allow-list is exactly the
    sandbox singleton — the live Forage id is necessarily absent. M-DIMS-4 does NOT
    touch the allow-list; live promotion is a separate, separately-approved step.
  - Rate-limited through W5 and PACED: writes are spaced by ``pace_seconds`` so a
    sustained batch stays under the per-endpoint ceiling instead of tripping it (the
    limiter rejects, it does not queue — so the loop, not the limiter, does the waiting).

CC writes ONLY in the deliberate run (``scripts/run_dims_bulk_sandbox.py``), behind the
batch hard stop — never in tests, never automatically.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from cc_client.client import CartonCloudClient, CartonCloudError
from cc_client.write_config import WriteConfig, SANDBOX_CUSTOMER_ID
from cc_client.write_idempotency import compute_diff, ObjectLockRegistry
from cc_client.write_rate_limit import MutateRateLimiter, DEFAULT_CEILING_PER_MIN

from .approve import read_product_for_dims, _is_writable_value, DIM_FIELDS, PRODUCT_PATH
from .roundtrip import (
    assert_sandbox_only,
    gather_active_sandbox_candidates,
    write_and_verify,
    SandboxCandidate,
    DimsRoundtripRefused,
    DimsReadBackMismatch,
)

log = logging.getLogger(__name__)

# Steady interval (seconds per write) that keeps a sustained batch under the limiter
# ceiling. 30/min -> 2.0s/write. The limiter still gates every write; this just spaces
# them so a legitimate soak never trips the bucket.
_DEFAULT_PACE_SECONDS = 60.0 / DEFAULT_CEILING_PER_MIN


@dataclass(frozen=True)
class BulkPlanItem:
    """One writable SKU: its UoM, current CC dims, filtered desired dims, and the diff."""

    product_id: str
    code: str
    uom: str
    current_dims: dict[str, Any]
    desired_dims: dict[str, Any]
    diff: dict[str, Any]


@dataclass(frozen=True)
class BulkPlan:
    """The pre-write plan shown at the single batch hard stop."""

    to_write: list[BulkPlanItem] = field(default_factory=list)
    no_ops: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    endpoint: str = PRODUCT_PATH
    write_enabled: bool = False
    allowlist_is_sandbox_only: bool = False


@dataclass(frozen=True)
class BulkReport:
    """Outcome of a soak run — fully reconstructable from this record + the log."""

    written: list[dict[str, Any]] = field(default_factory=list)
    no_ops: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    failed: dict[str, Any] | None = None
    aborted: bool = False
    untouched_after_failure: list[str] = field(default_factory=list)


def build_bulk_plan(
    client: CartonCloudClient,
    candidates: list[SandboxCandidate],
    desired_lookup: Callable[[str], dict[str, Any] | None],
    *,
    config: WriteConfig,
) -> BulkPlan:
    """Read each candidate (W4 read-before-write) and bucket it: writable / no-op / skipped.

    - no captured desired dims     -> skipped
    - no resolvable default UoM     -> skipped
    - desired == current (no diff)  -> no-op (already correct; never written)
    - otherwise                     -> writable, with NaN/None-filtered desired + the diff

    A missing/NaN weight is dropped (``_is_writable_value``), not a skip: the SKU still
    writes its L/W/H.
    """
    to_write: list[BulkPlanItem] = []
    no_ops: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for cand in candidates:
        desired = desired_lookup(cand.code)
        if not desired:
            skipped.append({"code": cand.code, "reason": "no captured desired dims"})
            continue
        read = read_product_for_dims(client, cand.product_id)
        if not read.uom:
            skipped.append({"code": cand.code, "reason": "no default UoM"})
            continue
        desired_dims = {
            f: desired[f] for f in DIM_FIELDS if f in desired and _is_writable_value(desired[f])
        }
        diff = compute_diff(read.current_dims, desired_dims)
        if not diff:
            no_ops.append({"code": cand.code, "reason": "already matches"})
            continue
        to_write.append(BulkPlanItem(
            product_id=cand.product_id, code=cand.code, uom=read.uom,
            current_dims=read.current_dims, desired_dims=desired_dims, diff=diff,
        ))
    return BulkPlan(
        to_write=to_write, no_ops=no_ops, skipped=skipped, endpoint=PRODUCT_PATH,
        write_enabled=client.write_enabled,
        allowlist_is_sandbox_only=config.customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID}),
    )


def run_sandbox_bulk(
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    desired_lookup: Callable[[str], dict[str, Any] | None],
    approval_token: str | None,
    confirm: Callable[[BulkPlan], bool],
    candidates: list[SandboxCandidate] | None = None,
    rate_limiter: MutateRateLimiter | None = None,
    registry: ObjectLockRegistry | None = None,
    sleep: Callable[[float], None] = time.sleep,
    pace_seconds: float | None = None,
) -> BulkReport:
    """Soak the whole active sandbox set through the gated dims write, fail-fast.

    1. PRECONDITIONS — ``assert_sandbox_only`` + ``write_enabled`` (refuse before any read).
    2. PLAN — read every candidate, bucket writable / no-op / skipped.
    3. BATCH HARD STOP — ``confirm(plan)``; no ``go`` -> abort, zero writes.
    4. LOOP — for each writable SKU: pace, then ``write_and_verify`` through the full gate
       chain. The first write or read-back failure stops the run (fail-fast) and reports
       what is written (known-good) and what is untouched.
    """
    # 1. preconditions — refuse before any read or write.
    assert_sandbox_only(config)
    if not client.write_enabled:
        raise DimsRoundtripRefused("client.write_enabled is False — refusing to start the bulk soak")

    # 2. plan
    cands = candidates if candidates is not None else gather_active_sandbox_candidates(client)
    plan = build_bulk_plan(client, cands, desired_lookup, config=config)

    # 3. batch hard stop — one go covers the whole batch.
    if not confirm(plan):
        log.warning(
            "M-DIMS-4 bulk soak ABORTED at the batch hard stop — no writes (%d would-write)",
            len(plan.to_write),
        )
        return BulkReport(
            written=[], no_ops=plan.no_ops, skipped=plan.skipped, failed=None,
            aborted=True, untouched_after_failure=[i.code for i in plan.to_write],
        )

    # 4. loop — paced, fail-fast.
    limiter = rate_limiter or MutateRateLimiter()
    pace = _DEFAULT_PACE_SECONDS if pace_seconds is None else pace_seconds
    written: list[dict[str, Any]] = []
    for i, item in enumerate(plan.to_write):
        if i > 0 and pace > 0:
            sleep(pace)  # space sustained writes so the limiter never refuses mid-batch
        try:
            after = write_and_verify(
                client=client, config=config, product_id=item.product_id, code=item.code,
                uom=item.uom, desired_dims=item.desired_dims, approval_token=approval_token,
                rate_limiter=limiter, registry=registry,
            )
        except (DimsReadBackMismatch, CartonCloudError) as e:
            untouched = [it.code for it in plan.to_write[i + 1:]]
            log.error(
                "M-DIMS-4 FAIL-FAST at %s (%s): %s | written=%d untouched=%d",
                item.product_id, item.code, e, len(written), len(untouched),
            )
            return BulkReport(
                written=written, no_ops=plan.no_ops, skipped=plan.skipped,
                failed={"code": item.code, "product_id": item.product_id, "error": str(e)},
                aborted=False, untouched_after_failure=untouched,
            )
        written.append({"code": item.code, "before": item.current_dims, "after": after})
        log.info("M-DIMS-4 wrote %s (%s): %s", item.product_id, item.code, after)

    log.info(
        "M-DIMS-4 bulk soak complete — written=%d no-op=%d skipped=%d",
        len(written), len(plan.no_ops), len(plan.skipped),
    )
    return BulkReport(
        written=written, no_ops=plan.no_ops, skipped=plan.skipped, failed=None,
        aborted=False, untouched_after_failure=[],
    )
