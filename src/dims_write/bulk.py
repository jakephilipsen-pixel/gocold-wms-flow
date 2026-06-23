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
  - SANDBOX ONLY. ``assert_write_target_allowed`` refuses unless the base allow-list is
    exactly the sandbox singleton. M-DIMS-4 does NOT arm ``CC_LIVE_PROMOTION``, so the live
    Forage id stays unwritable; live promotion is a separate, separately-approved step.
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
from typing import Any, Callable, Mapping

from cc_client.client import CartonCloudClient, CartonCloudError
from cc_client.write_config import WriteConfig, SANDBOX_CUSTOMER_ID
from cc_client.write_idempotency import compute_diff, ObjectLockRegistry
from cc_client.write_rate_limit import MutateRateLimiter, DEFAULT_CEILING_PER_MIN

from .approve import read_product_for_dims, dims_for_uom, _is_writable_value, DIM_FIELDS, PRODUCT_PATH
from .roundtrip import (
    assert_write_target_allowed,
    gather_active_sandbox_candidates,
    write_and_verify,
    SandboxCandidate,
    DimsRoundtripRefused,
    DimsReadBackMismatch,
)
from .live_proving import gather_active_live_candidates

log = logging.getLogger(__name__)

# Steady interval (seconds per write) that keeps a sustained batch under the limiter
# ceiling. 30/min -> 2.0s/write. The limiter still gates every write; this just spaces
# them so a legitimate soak never trips the bucket.
_DEFAULT_PACE_SECONDS = 60.0 / DEFAULT_CEILING_PER_MIN

# M-DIMS-5c — the carton unit-of-measure code. CT is Forage's carton UoM; CTN/PLT are NOT CT
# (the 7 CTN/PLT no-EA SKUs are a different, deferred shape — they must not resolve as CT).
CARTON_UOM_CODE = "CT"


# ---------- target-UoM resolvers: (product) -> uom_id | None (the only thing 5c changes) ----------

def resolve_default_uom(raw: Mapping[str, Any]) -> str | None:
    """Target-UoM resolver for the each/default path (M-DIMS-3/4/5b): the product's default UoM.

    Passed by the existing sandbox/each bulk path, so generalising the engine on a resolver
    leaves that path byte-for-byte unchanged (it still targets ``defaultUnitOfMeasure``).
    """
    return raw.get("defaultUnitOfMeasure")


def resolve_ct_uom(raw: Mapping[str, Any]) -> str | None:
    """Target-UoM resolver for M-DIMS-5c: the **id** of the UoM coded ``CT``, else ``None``.

    Resolved from the product's actual UoM list at runtime — find the UoM whose code is ``CT``
    and return its id (the key the dims PATCH path uses), NEVER a hardcoded id. A UoM's code is
    its explicit ``code`` field when present, else the map key (the v8 keyed-by-code vs
    keyed-by-id shapes both resolve). Matches ``CT`` EXACTLY (case-insensitive) so ``CTN``,
    ``PLT`` and ``EA`` never resolve — the CTN/PLT-only SKUs fall out as "no CT UoM" by
    decision. ``None`` means the caller skips the SKU: there is NO fall-through to the
    default/each UoM (writing carton dims onto the each is exactly the AE-2CB mistake 5c fixes).
    """
    for uom_id, obj in (raw.get("unitOfMeasures") or {}).items():
        code = (obj or {}).get("code") or uom_id
        if str(code).strip().upper() == CARTON_UOM_CODE:
            return uom_id
    return None


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
    uom_resolver: Callable[[Mapping[str, Any]], str | None] = resolve_default_uom,
    no_uom_reason: str = "no default UoM",
) -> BulkPlan:
    """Read each candidate (W4 read-before-write) and bucket it: writable / no-op / skipped.

    - no captured desired dims       -> skipped
    - ``uom_resolver`` returns None  -> skipped with ``no_uom_reason``
    - desired == current (no diff)   -> no-op (already correct; never written)
    - otherwise                      -> writable, with NaN/None-filtered desired + the diff

    ``uom_resolver(product) -> uom_id | None`` is the ONLY thing 5c changes: the each/sandbox
    path passes ``resolve_default_uom`` (the default UoM, unchanged M-DIMS-4 behaviour), while
    M-DIMS-5c passes ``resolve_ct_uom`` so the plan targets the CARTON (CT) UoM. A SKU the
    resolver can't place is skipped with ``no_uom_reason`` (5c: ``"no CT UoM"``) — there is NO
    fall-through to the each (the AE-2CB mistake). The diff baseline and the plan item's UoM are
    both that resolved UoM, so the no-op decision is made against the UoM that will be written.

    A missing/NaN weight is dropped (``_is_writable_value``), not a skip: the SKU still writes
    its L/W/H.
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
        target_uom = uom_resolver(read.raw)
        if not target_uom:
            skipped.append({"code": cand.code, "reason": no_uom_reason})
            continue
        current_dims = dims_for_uom(read.raw, target_uom)
        desired_dims = {
            f: desired[f] for f in DIM_FIELDS if f in desired and _is_writable_value(desired[f])
        }
        diff = compute_diff(current_dims, desired_dims)
        if not diff:
            no_ops.append({"code": cand.code, "reason": "already matches"})
            continue
        to_write.append(BulkPlanItem(
            product_id=cand.product_id, code=cand.code, uom=target_uom,
            current_dims=current_dims, desired_dims=desired_dims, diff=diff,
        ))
    return BulkPlan(
        to_write=to_write, no_ops=no_ops, skipped=skipped, endpoint=PRODUCT_PATH,
        write_enabled=client.write_enabled,
        allowlist_is_sandbox_only=config.customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID}),
    )


def _run_bulk(
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    gather: Callable[[], list],
    candidates: list | None,
    desired_lookup: Callable[[str], dict[str, Any] | None],
    uom_resolver: Callable[[Mapping[str, Any]], str | None],
    no_uom_reason: str,
    require_live_promotion: bool,
    approval_token: str | None,
    confirm: Callable[[BulkPlan], bool],
    rate_limiter: MutateRateLimiter | None,
    registry: ObjectLockRegistry | None,
    sleep: Callable[[float], None],
    pace_seconds: float | None,
    label: str,
) -> BulkReport:
    """The proven bulk loop, shared by the sandbox/each soak (M-DIMS-4) and the CT carton bulk
    (M-DIMS-5c). The ONLY things a caller varies are injected: which customer to ``gather``, the
    ``uom_resolver`` (each-default vs CT) + its ``no_uom_reason``, and whether
    ``require_live_promotion``. Everything else — the 5a gate, the single batch hard stop, paced
    fail-fast, ``write_and_verify`` + UoM-specific read-back, W4 idempotency — is identical, so
    5c reuses the soak rather than forking it.

    1. PRECONDITIONS — ``assert_write_target_allowed`` + ``write_enabled`` (+ live-promotion when
       the caller writes the live id); refuse before any read.
    2. PLAN — read every candidate, bucket writable / no-op / skipped via ``uom_resolver``.
    3. BATCH HARD STOP — ``confirm(plan)``; no ``go`` -> abort, zero writes.
    4. LOOP — per writable SKU: pace, then ``write_and_verify`` through the full gate chain. The
       first write or read-back failure stops the run (fail-fast) and reports what is written
       (known-good) and what is untouched.
    """
    # 1. preconditions — refuse before any read or write.
    assert_write_target_allowed(config)
    if not client.write_enabled:
        raise DimsRoundtripRefused("client.write_enabled is False — refusing to start the bulk soak")
    if require_live_promotion and not config.live_promotion:
        raise DimsRoundtripRefused(
            f"{label} writes the LIVE Forage id — CC_LIVE_PROMOTION=true must be armed; "
            "refusing to start"
        )

    # 2. plan
    cands = candidates if candidates is not None else gather()
    plan = build_bulk_plan(
        client, cands, desired_lookup, config=config,
        uom_resolver=uom_resolver, no_uom_reason=no_uom_reason,
    )

    # 3. batch hard stop — one go covers the whole batch.
    if not confirm(plan):
        log.warning(
            "%s bulk ABORTED at the batch hard stop — no writes (%d would-write)",
            label, len(plan.to_write),
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
                "%s FAIL-FAST at %s (%s): %s | written=%d untouched=%d",
                label, item.product_id, item.code, e, len(written), len(untouched),
            )
            return BulkReport(
                written=written, no_ops=plan.no_ops, skipped=plan.skipped,
                failed={"code": item.code, "product_id": item.product_id, "error": str(e)},
                aborted=False, untouched_after_failure=untouched,
            )
        written.append({"code": item.code, "before": item.current_dims, "after": after})
        log.info("%s wrote %s (%s): %s", label, item.product_id, item.code, after)

    log.info(
        "%s bulk complete — written=%d no-op=%d skipped=%d",
        label, len(written), len(plan.no_ops), len(plan.skipped),
    )
    return BulkReport(
        written=written, no_ops=plan.no_ops, skipped=plan.skipped, failed=None,
        aborted=False, untouched_after_failure=[],
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
    """M-DIMS-4 — soak the whole active SANDBOX set through the gated dims write, fail-fast.

    Writes each SKU's captured dims to its DEFAULT (each) UoM. Does NOT arm live promotion, so
    the live Forage id stays unwritable. A thin wrapper over ``_run_bulk`` with the each
    resolver — behaviourally identical to the original M-DIMS-4 soak.
    """
    return _run_bulk(
        client=client, config=config,
        gather=lambda: gather_active_sandbox_candidates(client),
        candidates=candidates, desired_lookup=desired_lookup,
        uom_resolver=resolve_default_uom, no_uom_reason="no default UoM",
        require_live_promotion=False,
        approval_token=approval_token, confirm=confirm,
        rate_limiter=rate_limiter, registry=registry, sleep=sleep, pace_seconds=pace_seconds,
        label="M-DIMS-4",
    )


def run_ct_bulk(
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    desired_lookup: Callable[[str], dict[str, Any] | None],
    approval_token: str | None,
    confirm: Callable[[BulkPlan], bool],
    candidates: list | None = None,
    rate_limiter: MutateRateLimiter | None = None,
    registry: ObjectLockRegistry | None = None,
    sleep: Callable[[float], None] = time.sleep,
    pace_seconds: float | None = None,
) -> BulkReport:
    """M-DIMS-5c — bulk-write captured CARTON dims to the CT UoM of every active LIVE Forage SKU
    that has one.

    Generalises the M-DIMS-4 soak by injecting (a) the LIVE Forage customer (gathered; the live
    id is writable per 5a only because the run is armed) and (b) the CT UoM resolver. CT-only by
    decision: a SKU with no CT UoM is skipped ``"no CT UoM"`` — NO fall-through to the each (the
    AE-2CB mistake), no guessing at CTN — so the 7 CTN/PLT no-EA SKUs fall out here naturally.
    Requires ``CC_LIVE_PROMOTION`` armed (W3 re-checks it on every write); the whole proven path
    — gate chain, ``write_and_verify``, UoM-specific read-back, fail-fast, W5 pacing, W4
    idempotency — is unchanged. The captured each-level (Base UoM) dims for these SKUs stay
    EMPTY: that is 5d's job, not 5c's.
    """
    return _run_bulk(
        client=client, config=config,
        gather=lambda: gather_active_live_candidates(client),
        candidates=candidates, desired_lookup=desired_lookup,
        uom_resolver=resolve_ct_uom, no_uom_reason="no CT UoM",
        require_live_promotion=True,
        approval_token=approval_token, confirm=confirm,
        rate_limiter=rate_limiter, registry=registry, sleep=sleep, pace_seconds=pace_seconds,
        label="M-DIMS-5c",
    )


def run_each_bulk(
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    desired_lookup: Callable[[str], dict[str, Any] | None],
    approval_token: str | None,
    confirm: Callable[[BulkPlan], bool],
    candidates: list | None = None,
    rate_limiter: MutateRateLimiter | None = None,
    registry: ObjectLockRegistry | None = None,
    sleep: Callable[[float], None] = time.sleep,
    pace_seconds: float | None = None,
) -> BulkReport:
    """M-DIMS-5d — bulk-write captured dims to the Each/Base UoM of every active LIVE Forage SKU.

    The automated dims pipeline after M-DIMS-5c (the CT carton-UoM write) was CLOSED: CC's
    name-validation trap (every live CT UoM is named "CT", 2 chars < the 3-char floor) 422s a CT
    dims PATCH, and CT names can't be edited on live master. So the target is the **Each / Base
    UoM** (``defaultUnitOfMeasure``) — every SKU has one, and the probe found all 455 names valid,
    so the each accepts dims cleanly.

    This is the SAME engine as 5c (``_run_bulk``): the 5a gate, ONE batch hard stop, paced
    fail-fast, ``write_and_verify`` + read-back of the targeted UoM, W4 idempotency, and the
    ``CC_LIVE_PROMOTION`` precondition (the live id is writable only when armed; W3 re-checks per
    write). The ONLY difference from 5c is the resolver: ``resolve_default_uom`` (the each), not
    ``resolve_ct_uom``. A product with no default UoM (none live, per the probe) is skipped, never
    written. Dims arrive in cm via ``captured_cc_dims_table`` (the script's concern).

    The 15 SKUs that already carry Base-UoM dims are NOT special-cased: where a stored value (e.g.
    a pre-cm 10× ``255``) differs from the captured cm desired (``25.5``), the W4 diff is non-empty
    and the SKU PATCHes to the correct cm value — the bulk run corrects them for free; where it
    already matches, it no-ops.
    """
    return _run_bulk(
        client=client, config=config,
        gather=lambda: gather_active_live_candidates(client),
        candidates=candidates, desired_lookup=desired_lookup,
        uom_resolver=resolve_default_uom, no_uom_reason="no default UoM",
        require_live_promotion=True,
        approval_token=approval_token, confirm=confirm,
        rate_limiter=rate_limiter, registry=registry, sleep=sleep, pace_seconds=pace_seconds,
        label="M-DIMS-5d",
    )


def format_each_bulk_report(report: BulkReport) -> str:
    """Render the M-DIMS-5d result — the Each/Base UoM dims write — with its scope named honestly.

    The cohort is every live Forage SKU with a default UoM (= written + no-op + failed +
    untouched-after-failure); the probe found that to be all of them, so unlike 5c there is no
    large "no UoM" skip group. States, as a tested fact, that this writes the EACH and that the CT
    carton UoM is OUT of scope (CLOSED — CC name-validation + the no-edit-on-master policy), so a
    reader can never mistake a green each-write for the CT write that was dropped.
    """
    n_written = len(report.written)
    n_failed = 1 if report.failed else 0
    cohort = n_written + len(report.no_ops) + n_failed + len(report.untouched_after_failure)
    n_no_each = sum(1 for s in report.skipped if s.get("reason") == "no default UoM")

    lines = [
        "=== M-DIMS-5d — Each/Base UoM dims bulk result ===",
        f"  Each cohort (live Forage SKUs WITH a default UoM) : {cohort}",
        f"  dims written + verified on the each this run      : {n_written} of {cohort}",
        f"  already-correct (no-op)                           : {len(report.no_ops)}",
        f"  skipped — no default UoM (none expected live)     : {n_no_each}",
    ]
    if report.aborted:
        lines.append("  ABORTED at the batch hard stop — nothing written.")
    if report.failed:
        lines.append(f"  FAILED (fail-fast) at {report.failed['code']}: {report.failed.get('error', '')}")
        lines.append(f"     untouched after the failure: {report.untouched_after_failure}")
    lines += [
        "",
        "  SCOPE — read this honestly:",
        "    - dims are written to the EACH / Base UoM (defaultUnitOfMeasure), in cm.",
        "    - the CT carton UoM is OUT of scope (CLOSED): CC rejects CT dims because the CT UoM "
        "name fails validation, and CT names are not edited on live master.",
        "    - SKUs that already carried each dims are corrected in place by the idempotent diff "
        "(e.g. a stale 10× value → the captured cm value), not special-cased.",
    ]
    return "\n".join(lines)


def format_ct_bulk_report(report: BulkReport) -> str:
    """Render the M-DIMS-5c result so the deliberately-PARTIAL state cannot read as "done".

    Spells out, as a tested fact: how many CT SKUs got carton dims this run vs the CT cohort;
    that the each-level (Base UoM) dims for those SKUs are still EMPTY pending 5d; and that the
    CTN/PLT no-EA SKUs are deferred and unhandled by 5c. The CT cohort = the live Forage SKUs
    that HAVE a CT UoM = written + no-op + failed + untouched-after-failure. The ``no CT UoM``
    skips (the ~367 each-only + 7 CTN/PLT groups) are NOT part of the cohort — they are 5c's
    out-of-scope, surfaced so they are a written known-fact rather than something that looks done.
    """
    n_written = len(report.written)
    n_failed = 1 if report.failed else 0
    cohort = n_written + len(report.no_ops) + n_failed + len(report.untouched_after_failure)
    n_no_ct = sum(1 for s in report.skipped if s.get("reason") == "no CT UoM")

    lines = [
        "=== M-DIMS-5c — CT carton-dims bulk result ===",
        f"  CT cohort (live Forage SKUs WITH a CT UoM) : {cohort}",
        f"  CT carton dims written + verified this run : {n_written} of {cohort}",
        f"  already-correct (no-op)                    : {len(report.no_ops)}",
        f"  skipped — no CT UoM (NOT 5c's job)         : {n_no_ct}",
    ]
    if report.aborted:
        lines.append("  ABORTED at the batch hard stop — nothing written.")
    if report.failed:
        lines.append(f"  FAILED (fail-fast) at {report.failed['code']}: {report.failed.get('error', '')}")
        lines.append(f"     untouched after the failure: {report.untouched_after_failure}")
    lines += [
        "",
        "  KNOWN-PARTIAL STATE — do NOT read this as 'dims done':",
        f"    - CT carton dims written for {n_written} of {cohort} CT SKUs (the rest are "
        "no-op / failed / untouched, per the counts above).",
        f"    - each-level (Base UoM) dims for these {cohort} SKUs are still EMPTY — that is "
        "5d's job (each capture via the app), NOT written by 5c.",
        "    - the CTN/PLT no-EA SKUs (no CT UoM) are DEFERRED and unhandled by 5c — they fall "
        "out in the 'no CT UoM' skip list above, never assumed into 5d.",
    ]
    return "\n".join(lines)
