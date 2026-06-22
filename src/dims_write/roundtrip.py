"""M-DIMS-3 — first real CC write (sandbox only): one human-confirmed dims round-trip.

Flips the M-DIMS-2 injection seam from `shadow_mutate_fn` to the real `_mutate`. No
surface rebuild — `approve_dims_write`, the gate chain, and the M-DIMS-2 tests are
unchanged. M-DIMS-3 adds:

  - `live_mutate_fn` — the live `do_mutate`: PATCH /warehouse-products/{id} (v8) via
    W1's `_mutate`, exactly once with the diff. The single value that differs from shadow.
  - `assert_write_target_allowed` (M-DIMS-5a) — refuse to start unless writes are enabled,
    a secret is set, and the base allow-list is EXACTLY the sandbox singleton. The live
    Forage id is writable only when `CC_LIVE_PROMOTION` is armed (gated per-write in W3),
    never via the allow-list; an armed run is permitted but logs a loud WARNING.
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
from typing import Any, Callable, Mapping

from cc_client.client import CartonCloudClient
from cc_client.write_config import WriteConfig, SANDBOX_CUSTOMER_ID
from cc_client.write_idempotency import compute_diff, ObjectLockRegistry
from cc_client.write_rate_limit import MutateRateLimiter
from cc_client.queries import search_warehouse_products

from .approve import (
    approve_dims_write,
    read_product_for_dims,
    build_dims_patch,
    _is_writable_value,
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

def live_mutate_fn(
    client: CartonCloudClient, product_id: str, uom: str
) -> Callable[[dict[str, Any]], Any]:
    """The LIVE `do_mutate`: PATCH `/warehouse-products/{id}` via W1's `_mutate`, once.

    Injected in place of `shadow_mutate_fn` — the single value that differs between
    shadow (M-DIMS-2) and live (M-DIMS-3). Builds the JSON-Patch body with the SAME
    `build_dims_patch` helper shadow uses, so what shadow previewed is what fires.
    `idempotent_mutate` calls it once, only when the diff is non-empty. Routes through
    the double-gated `_mutate`, so an un-enabled client still refuses.
    """
    def _fn(diff: dict[str, Any]) -> Any:
        path, ops, headers = build_dims_patch(product_id, uom, diff)
        log.info("[LIVE] PATCH %s with %s", path, ops)
        resp = client._mutate("PATCH", path, approved=True, json=ops, headers=headers)
        body = resp.json() if hasattr(resp, "json") else resp
        log.info("[LIVE] PATCH %s ok", path)
        return body

    return _fn


# ---------- shared write+verify: one SKU through the chain, then read-back ----------

def write_and_verify(
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    product_id: str,
    code: str,
    uom: str,
    desired_dims: dict[str, Any],
    approval_token: str | None,
    rate_limiter: MutateRateLimiter,
    registry: ObjectLockRegistry | None = None,
) -> dict[str, Any]:
    """Write one SKU's dims through the full gate chain, then GET and verify the land.

    The single write+verify both M-DIMS-3 (one SKU) and M-DIMS-4 (the bulk soak) use —
    same wire shape, same guarantees. Runs ``approve_dims_write`` (rate-limit → read →
    customer-guard → authz → idempotent-mutate, the live ``_mutate`` injected), then
    re-reads and compares. Returns the read-back current dims on success; raises
    ``DimsReadBackMismatch`` if any written field didn't land. ``desired_dims`` must be
    pre-filtered (no NaN/None) so the read-back only checks what was actually sent.

    Both the diff baseline (``approve_dims_write``'s read) and the read-back read the SAME
    ``uom`` the PATCH targets — so for M-DIMS-5c the verify confirms the dims landed on the
    CARTON (CT) UoM specifically, not merely that *some* dim changed. For the each/sandbox path
    ``uom`` is the default UoM, so this is unchanged from M-DIMS-3/4/5b.
    """
    approve_dims_write(
        product_id,
        client=client,
        config=config,
        desired_dims=desired_dims,
        mutate_fn=live_mutate_fn(client, product_id, uom),
        rate_limiter=rate_limiter,
        approval_token=approval_token,
        registry=registry,
        read_uom=uom,
    )
    after = read_product_for_dims(client, product_id, uom=uom)
    mismatched = {
        f: (desired_dims[f], after.current_dims.get(f))
        for f in desired_dims
        if after.current_dims.get(f) != desired_dims[f]
    }
    if mismatched:
        log.error(
            "READ-BACK MISMATCH for %s (%s): wrote %s, read back %s; mismatched=%s",
            product_id, code, desired_dims, after.current_dims, mismatched,
        )
        raise DimsReadBackMismatch(
            f"read-back mismatch for {code}: wrote {desired_dims}, "
            f"read back {after.current_dims}; mismatched fields {mismatched}"
        )
    return after.current_dims


# ---------- preconditions: the named write gate (M-DIMS-5a) ----------

def assert_write_target_allowed(config: WriteConfig) -> None:
    """Refuse to start a write run unless the config is in a sanctioned shape.

    The named live gate (M-DIMS-5a), replacing the former ``assert_sandbox_only``. Refuses
    unless writes are enabled, a secret is set, and the **base allow-list is EXACTLY the
    sandbox singleton**. The live Forage id is NEVER admitted via the allow-list — it
    becomes writable only by arming ``CC_LIVE_PROMOTION`` (gated per-write in W3's
    ``is_customer_allowed``). So requiring ``customer_allowlist == {SANDBOX_CUSTOMER_ID}``
    still holds in BOTH modes, and you cannot promote by editing the allow-list.

    When ``live_promotion`` is armed the live id is writable this run; the gate permits it
    but logs a loud WARNING so an armed run is unmistakable in the record. Default-closed:
    with the flag clear, this is exactly the old sandbox-only behaviour.
    """
    if not config.write_enabled:
        raise DimsRoundtripRefused(
            "write_enabled is False — refusing to start the write run"
        )
    if not config.write_secret:
        raise DimsRoundtripRefused(
            "CC_WRITE_SECRET not configured — refusing to start the write run"
        )
    if config.customer_allowlist != frozenset({SANDBOX_CUSTOMER_ID}):
        raise DimsRoundtripRefused(
            "base allow-list is not the sandbox singleton — refusing to start the write run. "
            f"Expected exactly the sandbox id; got {sorted(config.customer_allowlist)}. "
            "Live promotion is via CC_LIVE_PROMOTION=true, NEVER by editing the allow-list."
        )
    if config.live_promotion:
        log.warning(
            "LIVE PROMOTION ARMED (CC_LIVE_PROMOTION=true) — the live Forage id is WRITABLE "
            "this run. This is the deliberate, reversible promotion; clear the flag to re-close."
        )


# ---------- target selection ----------

@dataclass(frozen=True)
class SandboxCandidate:
    """An active s-prefixed sandbox product to consider for the round-trip."""

    product_id: str
    code: str


@dataclass(frozen=True)
class TargetSelection:
    """The chosen SKU: its UoM, authoritative current dims, real desired dims, diff."""

    product_id: str
    code: str
    uom: str
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
        if not read.uom:
            log.info("skip %s: no default unit-of-measure to write dims onto", cand.code)
            skipped.append({"code": cand.code, "reason": "no default UoM"})
            continue
        # Drop unset/NaN desired values (e.g. ~31% of SKUs lack captured weight) so the
        # diff — and the PATCH — never carries a non-finite value.
        desired_dims = {
            f: desired[f] for f in DIM_FIELDS if f in desired and _is_writable_value(desired[f])
        }
        diff = compute_diff(read.current_dims, desired_dims)
        if not diff:
            log.info("skip %s: empty diff (current already matches desired) — proves nothing", cand.code)
            skipped.append({"code": cand.code, "reason": "empty diff (no-op)"})
            continue
        return (
            TargetSelection(
                product_id=cand.product_id,
                code=cand.code,
                uom=read.uom,
                current_dims=read.current_dims,
                desired_dims=desired_dims,
                diff=diff,
            ),
            skipped,
        )
    return None, skipped


# ---------- desired-dims lookup: sandbox mirror code → captured base code ----------

def sandbox_desired_lookup(
    captured: Mapping[str, dict[str, Any]],
) -> Callable[[str], dict[str, Any] | None]:
    """Build a desired-dims lookup for sandbox SKUs from a captured-dims table.

    The capture template is keyed by the **base** Forage SKU code (e.g. ``RK-001``),
    but the sandbox customer's SKUs are ``s``-prefixed mirrors (``sRK-001``) —
    GROUND_TRUTH §5: active sandbox codes ``sRK-/sGP-/sHL-/sRD-/sTC-`` mirror base codes
    ``RK-/GP-/HL-/RD-/TC-``. So resolve a sandbox code by trying it **directly** first,
    then by stripping a **single** leading ``s`` — case-insensitively, because at least
    one real mirror (``SAE-TOT`` → base ``AE-TOT``) capitalises the prefix. Direct-lookup
    precedence keeps this safe for genuine base codes that start with ``S`` (e.g.
    ``SNK-*``): they hit directly and are never stripped.

    NOTE (confirm before the live run): the ``s``-prefix correspondence is inferred from
    GROUND_TRUTH §5, not a documented transform. The M-DIMS-3 hard stop prints the real
    CC current dims for the chosen SKU, which is the final human check that the mapped
    desired dims belong to that SKU.
    """
    def _lookup(code: str) -> dict[str, Any] | None:
        base = resolve_base_code(code, captured)
        return captured[base] if base is not None else None

    return _lookup


def resolve_base_code(
    code: str, captured: Mapping[str, dict[str, Any]]
) -> str | None:
    """Resolve a CC SKU code to its captured-table base code, or ``None``.

    The single source of the sandbox-mirror strip logic (shared by ``sandbox_desired_lookup``
    and M-DIMS-5b's live mapping display). Try the code **directly** first — so a genuine
    base code that starts with ``S`` (``SNK-*``) hits itself and is never stripped — then
    strip a **single** leading ``s``/``S`` (case-insensitive: ``SAE-TOT`` → ``AE-TOT``).
    Returning the resolved *key* (not just the dims) lets a caller show which base code a
    live SKU mapped to — the mapping decision M-DIMS-5b puts in front of a human.
    """
    if code in captured:
        return code
    if code[:1] in ("s", "S") and code[1:] in captured:
        return code[1:]
    return None


# ---------- the run: hard stop, PATCH, read-back verify ----------

@dataclass(frozen=True)
class HardStopInfo:
    """Everything a human needs to decide "go" — printed at the hard stop."""

    product_id: str
    code: str
    uom: str
    current_dims: dict[str, Any]
    desired_dims: dict[str, Any]
    diff: dict[str, Any]
    endpoint: str
    verb: str
    body: list[dict[str, Any]]
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
        f"  SKU            : {info.product_id}  ({info.code})  UoM={info.uom}\n"
        f"  current dims   : {info.current_dims}   (read from CC, unset reads as None)\n"
        f"  desired dims   : {info.desired_dims}   (mm L/W/H, kg weight — units unconfirmed)\n"
        f"  exact diff     : {info.diff}\n"
        f"  about to fire  : {info.verb} {info.endpoint}\n"
        f"  request body   : {info.body}\n"
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
    assert_write_target_allowed(config)
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

    # Build the exact PATCH the live fn will fire, so the hard stop shows it verbatim.
    endpoint, body, _ = build_dims_patch(selection.product_id, selection.uom, selection.diff)
    info = HardStopInfo(
        product_id=selection.product_id,
        code=selection.code,
        uom=selection.uom,
        current_dims=selection.current_dims,
        desired_dims=selection.desired_dims,
        diff=selection.diff,
        endpoint=endpoint,
        verb="PATCH",
        body=body,
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
    after_dims = write_and_verify(
        client=client,
        config=config,
        product_id=selection.product_id,
        code=selection.code,
        uom=selection.uom,
        desired_dims=selection.desired_dims,
        approval_token=approval_token,
        rate_limiter=rate_limiter or MutateRateLimiter(),
        registry=registry,
    )

    log.info("M-DIMS-3 LANDED — %s (%s) dims now %s", selection.product_id, selection.code, after_dims)
    return RoundtripReport(
        product_id=selection.product_id, code=selection.code,
        current_dims=selection.current_dims, desired_dims=selection.desired_dims,
        diff=selection.diff, endpoint=endpoint, verb="PATCH",
        written=True, aborted=False, landed=True, read_back_dims=after_dims, skipped=skipped,
    )
