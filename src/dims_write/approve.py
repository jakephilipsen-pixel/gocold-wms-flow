"""M-DIMS-2 — the dims-shadow approve handler.

The first write *surface*, ported natively into the W0–W5 spine (M-DIMS-1 Route B).
It composes the full gate chain once and is mode-agnostic: shadow vs live differ ONLY
by the mutate fn injected into ``idempotent_mutate(do_mutate=…)``
(WRITE_ENABLEMENT_PLAN §3.1):

    rate-limit (W5) → read (GET) → customer-guard (W3) → authz (W2) → idempotent_mutate (W4)

- **Shadow (M-DIMS-2):** inject ``shadow_mutate_fn(product_id, uom)`` — it logs
  ``"would PATCH /warehouse-products/{id} with {ops}"`` and records; ``_mutate`` is
  never called.
- **Live (M-DIMS-3):** inject a fn that calls W1's real ``_mutate``, behind
  ``write_enabled`` + the sandbox allow-list — no surface rebuild.

The current-dims GET is the one real, read-only CC interaction in shadow. It goes
through the normal read path (``client.get``) and never flips ``write_enabled`` — the
same discipline as the W4 diff read. GET and PATCH share ``/warehouse-products/{id}``
(under ``Accept-Version: 8``) so the dims read are the dims written; units are mm
(L/W/H) / kg (weight), no conversion (dim-capture-app carry-over).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from cc_client.client import CartonCloudClient
from cc_client.write_config import WriteConfig
from cc_client.write_authz import verify_write_auth
from cc_client.write_customer_guard import verify_customer_allowed
from cc_client.write_idempotency import idempotent_mutate, ObjectLockRegistry
from cc_client.write_rate_limit import MutateRateLimiter

log = logging.getLogger(__name__)

# The CC product dim fields, in mm (L/W/H) and kg (weight). No conversion.
DIM_FIELDS = ("length", "width", "height", "weight")

# Dims live on the warehouse-product's unit-of-measure (api-docs.cartoncloud.com):
# GET/PATCH share /warehouse-products/{id}; the dim fields hang off
# unitOfMeasures.{uom}, and GET OMITS them when unset (so the read pulls from the
# default UoM, not the top level). The earlier "/products/{id}" + top-level-dims
# shape was the LEGACY app-API contract and 404s here ("Invalid product id").
PRODUCT_PATH = "/warehouse-products/{id}"

# CC accepts RFC-6902 JSON Patch on warehouse-products; Content-Type must declare it.
JSON_PATCH_CONTENT_TYPE = "application/json-patch+json"

# L/W/H are UoM fields ONLY in the warehouse-products v8 schema (per CC api docs). Under
# the client default (v1) those fields don't exist, so a v1 PATCH 200s but SILENTLY DROPS
# length/width/height (confirmed live 21 Jun 2026 — only `weight`, a v1 field, persisted).
# So the dims read AND write must both run under v8.
WP_ACCEPT_VERSION = "8"


def _is_writable_value(v: Any) -> bool:
    """Drop unset/NaN dims so we never PATCH a non-finite value (CC rejects NaN).

    Captured weight is ~69% populated, so a desired dict can carry ``NaN`` weight;
    ``json`` would serialise that to invalid ``NaN`` and CC would reject the whole
    PATCH. ``weight == 0`` is legitimate and kept.
    """
    if v is None:
        return False
    if isinstance(v, float) and not math.isfinite(v):
        return False
    return True


def build_dims_patch(
    product_id: str, uom: str, diff: Mapping[str, Any]
) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    """Build the (path, JSON-Patch body, headers) for a UoM dims PATCH.

    The single place that knows CC's dims-write wire shape, so shadow and live send
    the *identical* thing. ``diff`` is the flat ``{dim: value}`` of changed fields
    (from ``idempotent_mutate``); each becomes a ``replace`` op at
    ``/unitOfMeasures/{uom}/{dim}``. Values are written as captured (mm L/W/H, kg
    weight) — no conversion.
    """
    if not uom:
        raise ValueError("cannot build a dims PATCH without a target unit-of-measure")
    path = PRODUCT_PATH.format(id=product_id)
    # `add`, not `replace`: a freshly-captured SKU has UNSET dims (GET omits them), and
    # RFC-6902 `replace` 422s on a path that doesn't yet exist ("Path not exists").
    # `add` creates the member when absent and replaces it when present — correct for
    # both an empty SKU and a re-run.
    ops = [
        {"op": "add", "path": f"/unitOfMeasures/{uom}/{field}", "value": value}
        for field, value in diff.items()
    ]
    return path, ops, {
        "Content-Type": JSON_PATCH_CONTENT_TYPE,
        "Accept-Version": WP_ACCEPT_VERSION,
    }


@dataclass(frozen=True)
class ProductDimsRead:
    """The one read: the target's customer id (guard), default UoM, + current dims."""

    customer_id: str | None
    uom: str | None
    current_dims: dict[str, Any]
    raw: dict[str, Any]


def dims_for_uom(raw: Mapping[str, Any], uom: str | None) -> dict[str, Any]:
    """Pull L/W/H/weight off ``unitOfMeasures.{uom}``; unset (or an absent UoM) reads as None.

    The single place that extracts a *named* UoM's dims, so the diff baseline and the read-back
    can both read the SAME UoM the PATCH targets (M-DIMS-5c). A GET omits unset dims, so a
    freshly-captured UoM reads ``{length: None, ...}`` — exactly the empty state a first write
    fills — and an absent UoM reads all-None (so a read-back against the wrong UoM can never
    false-pass).
    """
    uom_obj = (raw.get("unitOfMeasures") or {}).get(uom) or {}
    return {field: uom_obj.get(field) for field in DIM_FIELDS}


def read_product_for_dims(
    client: CartonCloudClient, product_id: str, *, uom: str | None = None
) -> ProductDimsRead:
    """GET the warehouse-product and pull its customer id, target UoM, and that UoM's dims.

    A plain read through ``client.get`` — it never flips ``write_enabled``. ``uom`` selects
    WHICH UoM's dims to read: ``None`` (default) reads the product's ``defaultUnitOfMeasure`` —
    the unchanged M-DIMS-3/4/5b behaviour (the each). M-DIMS-5c passes the resolved CT UoM id so
    the diff baseline and the read-back follow the CARTON UoM, never the each. ``customer.id``
    (top-level) always drives the customer-guard, independent of which UoM is read. Confirmed
    against the real sandbox at M-DIMS-3's read-back step.
    """
    raw = client.get(PRODUCT_PATH.format(id=product_id), headers={"Accept-Version": WP_ACCEPT_VERSION})
    customer_id = (raw.get("customer") or {}).get("id")
    target = uom if uom is not None else raw.get("defaultUnitOfMeasure")
    current_dims = dims_for_uom(raw, target)
    return ProductDimsRead(customer_id=customer_id, uom=target, current_dims=current_dims, raw=raw)


def shadow_mutate_fn(product_id: str, uom: str, *, sink: Callable[[str], None] | None = None):
    """Build the SHADOW mutate fn for a product: log + record, never write.

    Injected as ``do_mutate`` in shadow mode. It receives the diff (changed dims) and
    builds the *exact* PATCH that live would send via ``build_dims_patch`` — so a shadow
    run previews the real ``PATCH /warehouse-products/{id}`` JSON-Patch body verbatim. It
    logs that and appends to ``.records``; M-DIMS-3 swaps this single value for the real
    ``_mutate``.
    """
    records: list[dict[str, Any]] = []

    def _recorder(diff: dict[str, Any]) -> dict[str, Any]:
        path, ops, _ = build_dims_patch(product_id, uom, diff)
        (sink or log.info)(f"[SHADOW] would PATCH {path} with {ops}")
        records.append({"product_id": product_id, "uom": uom, "path": path, "ops": ops, "diff": diff})
        return {"shadow": True, "product_id": product_id, "uom": uom, "would_patch": ops}

    _recorder.records = records  # type: ignore[attr-defined]
    return _recorder


@dataclass(frozen=True)
class DimsApproveResult:
    """Outcome of a dims approve: the resolved target, the diff, and what ran."""

    product_id: str
    customer_id: str | None
    diff: dict[str, Any]
    no_op: bool          # True iff the diff was empty (mutate fn not called)
    response: Any        # whatever the injected mutate fn returned; None on no-op


def approve_dims_write(
    product_id: str,
    *,
    client: CartonCloudClient,
    config: WriteConfig,
    desired_dims: dict[str, Any],
    mutate_fn: Callable[[dict[str, Any]], Any],
    rate_limiter: MutateRateLimiter,
    approval_token: str | None,
    registry: ObjectLockRegistry | None = None,
    endpoint: str | None = None,
    read_uom: str | None = None,
) -> DimsApproveResult:
    """Run the full spine chain for a dims write, then apply ``mutate_fn``.

    Mode-agnostic: ``mutate_fn`` is the only thing that differs between shadow and
    live. The chain order is fixed —
    rate-limit → read → customer-guard → authz → idempotent_mutate — so every gate
    engages regardless of what ``mutate_fn`` does (a refused gate raises before the
    mutate fn is ever reached).

    ``read_uom`` selects the UoM the diff baseline is read from: ``None`` (default) reads the
    product's default UoM — the unchanged each/sandbox behaviour — while M-DIMS-5c passes the
    resolved CT UoM id so the no-op/diff decision is made against the CARTON UoM's current dims,
    not the each's (else a SKU whose CT already matches but whose empty each differs would
    re-PATCH forever).
    """
    ep = endpoint or PRODUCT_PATH

    # 1. rate-limit (W5) — reject before doing anything, including the read.
    rate_limiter.check(ep)

    # 2. the one real, read-only GET — resolves customer id + current dims (of read_uom, or default).
    read = read_product_for_dims(client, product_id, uom=read_uom)

    # 3. customer-guard (W3) — refuse a non-allow-listed target, EVEN in shadow.
    verify_customer_allowed(read.customer_id, config)

    # 4. authz (W2) — require the write-auth secret + a matching approval token.
    verify_write_auth(config.write_secret, approval_token)

    # 5. idempotent_mutate (W4) — diff vs the already-read current (one GET total);
    #    empty diff no-ops; otherwise the injected mutate fn fires with the diff.
    desired = {
        field: desired_dims[field]
        for field in DIM_FIELDS
        if field in desired_dims and _is_writable_value(desired_dims[field])
    }
    result = idempotent_mutate(
        product_id,
        read_current=lambda: read.current_dims,
        desired=desired,
        do_mutate=mutate_fn,
        registry=registry,
    )

    return DimsApproveResult(
        product_id=product_id,
        customer_id=read.customer_id,
        diff=result.diff,
        no_op=not result.mutated,
        response=result.response,
    )
