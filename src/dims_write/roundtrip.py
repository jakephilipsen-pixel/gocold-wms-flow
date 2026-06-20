"""M-DIMS-3 — first real CC write (sandbox only): one human-confirmed dims round-trip.

Flips the M-DIMS-2 injection seam from `shadow_mutate_fn` to the real `_mutate`. No
surface rebuild — `approve_dims_write`, the gate chain, and the M-DIMS-2 tests are
unchanged. M-DIMS-3 adds:

  - `live_mutate_fn` — the live `do_mutate`: PATCH /products/{id} via W1's `_mutate`,
    exactly once with the diff. The single value that differs from shadow mode.
  - `assert_sandbox_only` — refuse to start unless writes are enabled, a secret is set,
    and the allow-list is EXACTLY the sandbox singleton (so the live Forage id is
    necessarily absent — asserted positively, without this module ever naming it).
  - target selection — pick an active `s`-prefixed sandbox SKU whose real desired dims
    DIFFER from its current CC dims (an empty diff proves nothing → skip it).
  - `run_sandbox_roundtrip` — the 3-step run: GET current + diff → HARD STOP (human
    "go") → PATCH via the live fn through the full chain → GET again + read-back verify.
    Apply the real dims and leave them in place (PLAN §4.2). A read-back mismatch is a
    hard, loud failure.

CC writes ONLY in the deliberate run (`scripts/run_dims_sandbox_roundtrip.py`), behind
the hard stop — never in tests, never automatically.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from cc_client.client import CartonCloudClient
from cc_client.write_config import WriteConfig, SANDBOX_CUSTOMER_ID
from cc_client.write_idempotency import compute_diff, ObjectLockRegistry
from cc_client.write_rate_limit import MutateRateLimiter
from cc_client.queries import search_warehouse_products

from .approve import (
    approve_dims_write,
    read_product_for_dims,
    DIM_FIELDS,
    PRODUCT_PATH,
)

log = logging.getLogger(__name__)


# ---------- typed run errors ----------

class DimsRoundtripError(Exception):
    """Base for M-DIMS-3 run failures."""


class DimsRoundtripRefused(DimsRoundtripError):
    """Preconditions not met — refuse to start the live round-trip."""


class NoWritableSandboxSku(DimsRoundtripError):
    """No active s-prefixed sandbox SKU had a non-empty diff — nothing to prove."""


class DimsReadBackMismatch(DimsRoundtripError):
    """The PATCH did not land: read-back dims differ from what was written."""


# ---------- the live mutate fn (the one injected value that differs from shadow) ----------

def live_mutate_fn(client: CartonCloudClient, product_id: str) -> Callable[[dict[str, Any]], Any]:
    """The LIVE `do_mutate`: PATCH `/products/{id}` via W1's `_mutate`, once, with the diff.

    Injected in place of `shadow_mutate_fn` — the single value that differs between
    shadow (M-DIMS-2) and live (M-DIMS-3). `idempotent_mutate` calls it once, and only
    when the diff is non-empty. Routes through the double-gated `_mutate`, so an
    un-enabled client still refuses.
    """
    def _fn(diff: dict[str, Any]) -> Any:
        path = PRODUCT_PATH.format(id=product_id)
        log.info("[LIVE] PATCH %s with %s", path, diff)
        resp = client._mutate("PATCH", path, approved=True, json=diff)
        body = resp.json() if hasattr(resp, "json") else resp
        log.info("[LIVE] PATCH %s ok", path)
        return body

    return _fn


# ---------- preconditions: refuse to start unless sandbox-only ----------

def assert_sandbox_only(config: WriteConfig) -> None:
    """Refuse to start unless writes are enabled, a secret is set, and the allow-list
    is EXACTLY the sandbox singleton.

    Requiring the allow-list to equal `{SANDBOX_CUSTOMER_ID}` positively guarantees the
    live Forage id is absent — without this module ever naming it. Any extra id (e.g.
    the live id added for promotion) makes the set unequal and refuses.
    """
    if not config.write_enabled:
        raise DimsRoundtripRefused(
            "write_enabled is False — refusing to start the live sandbox round-trip"
        )
    if not config.write_secret:
        raise DimsRoundtripRefused(
            "CC_WRITE_SECRET not configured — refusing to start the live round-trip"
        )
    if config.customer_allowlist != frozenset({SANDBOX_CUSTOMER_ID}):
        raise DimsRoundtripRefused(
            "allow-list is not sandbox-only — refusing to start the live round-trip. "
            f"Expected exactly the sandbox id; got {sorted(config.customer_allowlist)}. "
            "A non-sandbox-only allow-list (e.g. one containing the live Forage id) is "
            "forbidden for this run; promotion to live is its own separately-approved step."
        )


# ---------- target selection ----------

@dataclass(frozen=True)
class SandboxCandidate:
    """An active s-prefixed sandbox product to consider for the round-trip."""

    product_id: str
    code: str


@dataclass(frozen=True)
class TargetSelection:
    """The chosen SKU: its authoritative current dims, real desired dims, and the diff."""

    product_id: str
    code: str
    current_dims: dict[str, Any]
    desired_dims: dict[str, Any]
    diff: dict[str, Any]


def gather_active_sandbox_candidates(
    client: CartonCloudClient, *, customer_id: str = SANDBOX_CUSTOMER_ID
) -> list[SandboxCandidate]:
    """GET the sandbox customer's active products; keep the `s`-prefixed ones."""
    out: list[SandboxCandidate] = []
    for product in search_warehouse_products(client, customer_id=customer_id, active_only=True):
        code = (product.get("references") or {}).get("code") or product.get("code") or ""
        if not code.lower().startswith("s"):
            continue
        out.append(SandboxCandidate(product_id=product.get("id"), code=code))
    return out


def select_writable_sandbox_sku(
    client: CartonCloudClient,
    candidates: list[SandboxCandidate],
    desired_lookup: Callable[[str], dict[str, Any] | None],
) -> tuple[TargetSelection | None, list[dict[str, Any]]]:
    """Pick the first candidate whose real desired dims DIFFER from its current CC dims.

    Uses the authoritative per-id read (`read_product_for_dims`, the same read path the
    PATCH will diff against) to compute the diff. An empty diff proves nothing, so the
    SKU is skipped and reported; ditto a SKU with no captured desired dims. Returns
    `(selection_or_None, skipped)`.
    """
    skipped: list[dict[str, Any]] = []
    for cand in candidates:
        desired = desired_lookup(cand.code)
        if not desired:
            skipped.append({"code": cand.code, "reason": "no captured desired dims"})
            continue
        read = read_product_for_dims(client, cand.product_id)
        desired_dims = {f: desired[f] for f in DIM_FIELDS if f in desired}
        diff = compute_diff(read.current_dims, desired_dims)
        if not diff:
            log.info("skip %s: empty diff (current already matches desired) — proves nothing", cand.code)
            skipped.append({"code": cand.code, "reason": "empty diff (no-op)"})
            continue
        return (
            TargetSelection(
                product_id=cand.product_id,
                code=cand.code,
                current_dims=read.current_dims,
                desired_dims=desired_dims,
                diff=diff,
            ),
            skipped,
        )
    return None, skipped


# ---------- the run: hard stop, PATCH, read-back verify ----------

@dataclass(frozen=True)
class HardStopInfo:
    """Everything a human needs to decide "go" — printed at the hard stop."""

    product_id: str
    code: str
    current_dims: dict[str, Any]
    desired_dims: dict[str, Any]
    diff: dict[str, Any]
    endpoint: str
    verb: str
    write_enabled: bool
    allowlist_is_sandbox_only: bool


@dataclass(frozen=True)
class RoundtripReport:
    """Outcome of a run — fully reconstructable from the log + this record."""

    product_id: str
    code: str
    current_dims: dict[str, Any]
    desired_dims: dict[str, Any]
    diff: dict[str, Any]
    endpoint: str
    verb: str
    written: bool
    aborted: bool
    landed: bool
    read_back_dims: dict[str, Any] | None = None
    skipped: list[dict[str, Any]] = field(default_factory=list)


def _hard_stop_block(info: HardStopInfo) -> str:
    return (
        "\n================ M-DIMS-3 HARD STOP — confirm before the real PATCH ===========\n"
        f"  SKU            : {info.product_id}  ({info.code})\n"
        f"  current dims   : {info.current_dims}   (read from CC)\n"
        f"  desired dims   : {info.desired_dims}\n"
        f"  exact diff     : {info.diff}\n"
        f"  about to fire  : {info.verb} {info.endpoint}\n"
        f"  write_enabled  : {info.write_enabled}\n"
        f"  sandbox-only   : {info.allowlist_is_sandbox_only}\n"
        "  No PATCH fires until you confirm 'go'.\n"
        "==============================================================================="
    )


def run_sandbox_roundtrip(
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    desired_lookup: Callable[[str], dict[str, Any] | None],
    approval_token: str | None,
    confirm: Callable[[HardStopInfo], bool],
    candidates: list[SandboxCandidate] | None = None,
    rate_limiter: MutateRateLimiter | None = None,
    registry: ObjectLockRegistry | None = None,
) -> RoundtripReport:
    """Run the 3-step sandbox round-trip behind a human hard stop.

    1. Select an active s-prefixed sandbox SKU with a non-empty diff; GET current + diff.
    2. HARD STOP: log the block, call ``confirm(info)``; no PATCH unless it returns True.
    3. On "go": PATCH via the live fn through the full M-DIMS-2 chain, then GET again and
       verify the read-back matches what was written. Leave the dims in place.
    """
    # PRECONDITIONS — refuse before any read or write.
    assert_sandbox_only(config)
    if not client.write_enabled:
        raise DimsRoundtripRefused("client.write_enabled is False — refusing to start")

    # STEP 1 — select + read current + diff.
    cands = candidates if candidates is not None else gather_active_sandbox_candidates(client)
    selection, skipped = select_writable_sandbox_sku(client, cands, desired_lookup)
    if selection is None:
        raise NoWritableSandboxSku(
            "no active s-prefixed sandbox SKU had a non-empty diff "
            f"(skipped={skipped}) — nothing to prove"
        )

    endpoint = PRODUCT_PATH.format(id=selection.product_id)
    info = HardStopInfo(
        product_id=selection.product_id,
        code=selection.code,
        current_dims=selection.current_dims,
        desired_dims=selection.desired_dims,
        diff=selection.diff,
        endpoint=endpoint,
        verb="PATCH",
        write_enabled=client.write_enabled,
        allowlist_is_sandbox_only=config.customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID}),
    )

    # STEP 2 — HARD STOP.
    log.info(_hard_stop_block(info))
    if not confirm(info):
        log.warning("M-DIMS-3 run ABORTED at the hard stop — no PATCH fired (%s)", selection.code)
        return RoundtripReport(
            product_id=selection.product_id, code=selection.code,
            current_dims=selection.current_dims, desired_dims=selection.desired_dims,
            diff=selection.diff, endpoint=endpoint, verb="PATCH",
            written=False, aborted=True, landed=False, skipped=skipped,
        )

    # STEP 3 — PATCH via the live fn through the full chain, then read-back verify.
    log.info("M-DIMS-3 GO — PATCHing %s (%s) with %s", selection.product_id, selection.code, selection.diff)
    approve_dims_write(
        selection.product_id,
        client=client,
        config=config,
        desired_dims=selection.desired_dims,
        mutate_fn=live_mutate_fn(client, selection.product_id),
        rate_limiter=rate_limiter or MutateRateLimiter(),
        approval_token=approval_token,
        registry=registry,
    )

    after = read_product_for_dims(client, selection.product_id)
    mismatched = {
        f: (selection.desired_dims[f], after.current_dims.get(f))
        for f in selection.desired_dims
        if after.current_dims.get(f) != selection.desired_dims[f]
    }
    if mismatched:
        log.error(
            "M-DIMS-3 READ-BACK MISMATCH for %s (%s): wrote %s, read back %s; mismatched=%s",
            selection.product_id, selection.code, selection.desired_dims, after.current_dims, mismatched,
        )
        raise DimsReadBackMismatch(
            f"read-back mismatch for {selection.code}: wrote {selection.desired_dims}, "
            f"read back {after.current_dims}; mismatched fields {mismatched}"
        )

    log.info("M-DIMS-3 LANDED — %s (%s) dims now %s", selection.product_id, selection.code, after.current_dims)
    return RoundtripReport(
        product_id=selection.product_id, code=selection.code,
        current_dims=selection.current_dims, desired_dims=selection.desired_dims,
        diff=selection.diff, endpoint=endpoint, verb="PATCH",
        written=True, aborted=False, landed=True, read_back_dims=after.current_dims, skipped=skipped,
    )
