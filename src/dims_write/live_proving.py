"""M-DIMS-5b — first live Forage writes, human dims-verified (the proving run).

5b confirms the inferred captured-dims→live-SKU mapping is correct on REAL Forage data
before 5c writes hundreds. The read-back verify (reused from M-DIMS-3) proves a write
*landed*; it cannot prove the dims are *right for that SKU* — so 5b puts the mapping in
front of a human on 3–5 SKUs and makes them confirm each by **typing the SKU code back**.

Reuse, don't fork: every write goes through the proven ``write_and_verify`` (M-DIMS-3)
unchanged. 5b adds only (a) live target selection across the prefix shapes and (b) the
verification UX — no new write machinery.

Two safety-critical behaviours live HERE (not in the script), so they are tested:
  - **Per-SKU confirm match.** ``run_live_proving`` calls ``confirm(info) -> str`` and writes
    the SKU only when the returned string EQUALS ``target.code``. A wrong code, a bare ``go``
    (muscle-memory from the sandbox soak), or empty input therefore cannot PATCH — the match
    is engine logic, not the script's hope.
  - **Still-armed-at-exit.** ``finalize_exit`` forces a non-zero exit + a loud reminder
    whenever ``CC_LIVE_PROMOTION`` is still set, so no exit path returns 0 silently armed.

Gate: a run requires the 5a gate (``assert_write_target_allowed`` — enabled + secret + base
allow-list sandbox-only, and the loud ``LIVE PROMOTION ARMED`` warning) AND
``CC_LIVE_PROMOTION`` armed. The live id is written only because the flag is armed; W3's
customer-guard re-checks it on every write (reused, unchanged).

CC writes ONLY in the deliberate run (``scripts/run_dims_live_proving.py``), per SKU behind
the typed-code confirm — never in tests, never automatically.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from cc_client.client import CartonCloudClient
from cc_client.write_config import WriteConfig, LIVE_FORAGE_CUSTOMER_ID
from cc_client.write_idempotency import compute_diff, ObjectLockRegistry
from cc_client.write_rate_limit import MutateRateLimiter
from cc_client.queries import search_warehouse_products

from .approve import read_product_for_dims, _is_writable_value, DIM_FIELDS, PRODUCT_PATH
from .roundtrip import (
    assert_write_target_allowed,
    write_and_verify,
    resolve_base_code,
    DimsRoundtripError,
)

log = logging.getLogger(__name__)


class LiveProvingRefused(DimsRoundtripError):
    """Preconditions not met — refuse to start the live proving run."""


# ---------- data ----------

@dataclass(frozen=True)
class LiveCandidate:
    """An active live Forage product considered for the proving run."""

    product_id: str
    code: str


@dataclass(frozen=True)
class LiveTarget:
    """A selected live SKU + the mapping decision: which captured base code it resolved to."""

    product_id: str
    code: str
    base_code: str
    desired_dims: dict[str, Any]


@dataclass(frozen=True)
class LiveProvingPlan:
    """The plan shown BEFORE any write: selected SKUs (code→base→desired) + unresolvable ones."""

    selected: list[LiveTarget] = field(default_factory=list)
    unresolvable: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LiveHardStopInfo:
    """Everything the human eyeballs before confirming one live SKU by typing its code."""

    product_id: str
    code: str
    base_code: str
    uom: str
    current_dims: dict[str, Any]
    desired_dims: dict[str, Any]
    diff: dict[str, Any]
    endpoint: str


@dataclass(frozen=True)
class LiveProvingReport:
    """Outcome of a proving run — the go/no-go evidence for 5c."""

    written: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    unresolvable: list[dict[str, Any]] = field(default_factory=list)
    promotion_was_armed: bool = False


# ---------- live target selection (deliberate, covers the mapping's risk surface) ----------

def gather_active_live_candidates(client: CartonCloudClient) -> list[LiveCandidate]:
    """GET the LIVE Forage customer's active products. Unlike the sandbox gatherer, keep ALL
    of them (no ``s``-prefix filter) — live codes are the base codes (FP-/HI-/AE-)."""
    out: list[LiveCandidate] = []
    for product in search_warehouse_products(
        client, customer_id=LIVE_FORAGE_CUSTOMER_ID, active_only=True
    ):
        code = (product.get("references") or {}).get("code") or product.get("code") or ""
        if code:
            out.append(LiveCandidate(product_id=product.get("id"), code=code))
    return out


def _desired_from_base(base_code: str, captured: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """The writable desired dims for a base code: L/W/H always, weight only if finite (drop NaN)."""
    src = captured[base_code]
    return {f: src[f] for f in DIM_FIELDS if f in src and _is_writable_value(src[f])}


def _prefix(code: str) -> str:
    """The prefix shape used to bucket SKUs — the segment before the first '-' (FP, HI, AE, SAE)."""
    return code.split("-", 1)[0]


def select_live_proving_targets(
    candidates: list[LiveCandidate],
    captured: Mapping[str, dict[str, Any]],
    *,
    max_total: int = 5,
) -> LiveProvingPlan:
    """Pick a deliberate few that cover the mapping's risk surface — one resolvable SKU per
    prefix shape (so the direct-match AND strip branches are exercised on real codes), NOT
    "first N". A candidate that doesn't resolve to a captured base is reported (not selected),
    and the next of that prefix is tried.

    Deterministic (sorted by code) so the plan is reproducible at the hard stop.
    """
    selected: list[LiveTarget] = []
    unresolvable: list[dict[str, Any]] = []
    by_prefix: dict[str, list[LiveCandidate]] = {}
    for cand in sorted(candidates, key=lambda c: c.code):
        by_prefix.setdefault(_prefix(cand.code), []).append(cand)

    for prefix in sorted(by_prefix):
        chosen: LiveTarget | None = None
        for cand in by_prefix[prefix]:
            base = resolve_base_code(cand.code, captured)
            if base is None:
                unresolvable.append({"code": cand.code, "reason": "no captured base code"})
                continue
            chosen = LiveTarget(
                product_id=cand.product_id, code=cand.code, base_code=base,
                desired_dims=_desired_from_base(base, captured),
            )
            break  # one representative per prefix shape
        if chosen is not None:
            selected.append(chosen)

    return LiveProvingPlan(selected=selected[:max_total], unresolvable=unresolvable)


def build_live_proving_plan(
    client: CartonCloudClient,
    captured: Mapping[str, dict[str, Any]],
    *,
    candidates: list[LiveCandidate] | None = None,
    max_total: int = 5,
) -> LiveProvingPlan:
    """Read-only: gather active live candidates (unless supplied) and select the proving set.
    Building/printing the plan needs no write flag — the mapping is visible before any write."""
    cands = candidates if candidates is not None else gather_active_live_candidates(client)
    return select_live_proving_targets(cands, captured, max_total=max_total)


# ---------- the still-armed-at-exit safeguard (structural, testable) ----------

_DISARM_BANNER = (
    "\n" + "=" * 78 + "\n"
    "  ⚠  CC_LIVE_PROMOTION IS STILL ARMED — the live Forage write gate is OPEN.\n"
    "     Disarm it NOW so no later run can write live by accident:\n"
    "         unset CC_LIVE_PROMOTION\n"
    + "=" * 78
)


def disarm_reminder(env: Mapping[str, str]) -> str | None:
    """Return a loud reminder iff ``CC_LIVE_PROMOTION`` is still armed in ``env``, else None."""
    if str(env.get("CC_LIVE_PROMOTION", "")).strip().lower() == "true":
        return _DISARM_BANNER
    return None


def finalize_exit(env: Mapping[str, str], run_exit_code: int) -> tuple[int, str | None]:
    """Combine the run's exit code with the still-armed safeguard.

    If the flag is still armed, force a non-zero "still armed" code (≥3) and return the loud
    reminder — so a process can NEVER exit 0 silently armed, on ANY path (success/skip/abort/
    exception), when the caller runs this in a ``finally``.
    """
    msg = disarm_reminder(env)
    if msg is not None:
        return max(run_exit_code, 3), msg
    return run_exit_code, None


# ---------- the run: per-SKU, typed-code confirm, reuse write_and_verify ----------

def run_live_proving(
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    plan: LiveProvingPlan,
    approval_token: str | None,
    confirm: Callable[[LiveHardStopInfo], str],
    rate_limiter: MutateRateLimiter | None = None,
    registry: ObjectLockRegistry | None = None,
) -> LiveProvingReport:
    """Walk the plan ONE live SKU at a time behind a typed-code confirm; reuse ``write_and_verify``.

    1. ``assert_write_target_allowed`` (5a gate; logs the loud LIVE PROMOTION ARMED warning).
    2. Require ``CC_LIVE_PROMOTION`` armed — a live run is meaningless (and W3 would refuse the
       live id) without it; refuse early so nothing is typed in vain.
    3. Per selected SKU: GET current live dims (confirms live auth/endpoint), build the hard-stop
       info, call ``confirm`` → only PATCH when the typed string EQUALS the SKU code. A
       mismatch/empty/`go` is a skip (no write), recorded with the reason. On match, write +
       read-back verify via the proven path and leave the dims in place.
    """
    # 1. the 5a gate (enabled + secret + sandbox-base allow-list; warns loudly if armed).
    assert_write_target_allowed(config)
    # 2. 5b is a LIVE run — require the flag (W3 would refuse the live id otherwise).
    if not config.live_promotion:
        raise LiveProvingRefused(
            "M-DIMS-5b is a LIVE run — CC_LIVE_PROMOTION=true must be armed; refusing to start"
        )

    limiter = rate_limiter or MutateRateLimiter()
    written: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for target in plan.selected:
        read = read_product_for_dims(client, target.product_id)  # GET live dims; confirms auth
        if not read.uom:
            skipped.append({"code": target.code, "reason": "no default UoM"})
            continue
        diff = compute_diff(read.current_dims, target.desired_dims)
        if not diff:
            skipped.append({"code": target.code, "reason": "no-op: live already matches desired"})
            continue

        info = LiveHardStopInfo(
            product_id=target.product_id, code=target.code, base_code=target.base_code,
            uom=read.uom, current_dims=read.current_dims, desired_dims=target.desired_dims,
            diff=diff, endpoint=PRODUCT_PATH.format(id=target.product_id),
        )
        typed = (confirm(info) or "").strip()
        if typed != target.code:
            log.warning(
                "M-DIMS-5b SKIP %s — confirm did not match the SKU code (typed %r); writing nothing",
                target.code, typed,
            )
            skipped.append({
                "code": target.code,
                "reason": f"confirm mismatch: typed {typed!r} != SKU code {target.code!r}",
            })
            continue

        log.info("M-DIMS-5b GO %s (mapped base %s) — PATCHing live with %s",
                 target.code, target.base_code, diff)
        after = write_and_verify(
            client=client, config=config, product_id=target.product_id, code=target.code,
            uom=read.uom, desired_dims=target.desired_dims, approval_token=approval_token,
            rate_limiter=limiter, registry=registry,
        )
        written.append({"code": target.code, "base_code": target.base_code, "after": after})
        log.info("M-DIMS-5b WROTE %s (mapped %s): %s", target.code, target.base_code, after)

    return LiveProvingReport(
        written=written, skipped=skipped, unresolvable=plan.unresolvable, promotion_was_armed=True,
    )
