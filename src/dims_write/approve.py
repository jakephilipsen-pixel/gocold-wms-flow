"""M-DIMS-2 — the dims-shadow approve handler.

The first write *surface*, ported natively into the W0–W5 spine (M-DIMS-1 Route B).
It composes the full gate chain once and is mode-agnostic: shadow vs live differ ONLY
by the mutate fn injected into ``idempotent_mutate(do_mutate=…)``
(WRITE_ENABLEMENT_PLAN §3.1):

    rate-limit (W5) → read (GET) → customer-guard (W3) → authz (W2) → idempotent_mutate (W4)

- **Shadow (M-DIMS-2):** inject ``shadow_mutate_fn(product_id)`` — it logs
  ``"would PATCH /products/{id} with {diff}"`` and records; ``_mutate`` is never called.
- **Live (M-DIMS-3):** inject a fn that calls W1's real ``_mutate``, behind
  ``write_enabled`` + the sandbox allow-list — no surface rebuild.

The current-dims GET is the one real, read-only CC interaction in shadow. It goes
through the normal read path (``client.get``) and never flips ``write_enabled`` — the
same discipline as the W4 diff read. GET and PATCH share ``/products/{id}`` so the dims
read are the dims written; units are mm (L/W/H) / kg (weight), no conversion
(dim-capture-app carry-over).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from cc_client.client import CartonCloudClient
from cc_client.write_config import WriteConfig
from cc_client.write_authz import verify_write_auth
from cc_client.write_customer_guard import verify_customer_allowed
from cc_client.write_idempotency import idempotent_mutate, ObjectLockRegistry
from cc_client.write_rate_limit import MutateRateLimiter

log = logging.getLogger(__name__)

# The CC product dim fields, in mm (L/W/H) and kg (weight). No conversion.
DIM_FIELDS = ("length", "width", "height", "weight")

# GET current dims and PATCH new dims share this path (M-DIMS-1 carry-over).
PRODUCT_PATH = "/products/{id}"


@dataclass(frozen=True)
class ProductDimsRead:
    """The one read: the target's customer id (for the guard) + its current dims."""

    customer_id: str | None
    current_dims: dict[str, Any]
    raw: dict[str, Any]


def read_product_for_dims(client: CartonCloudClient, product_id: str) -> ProductDimsRead:
    """GET the product and pull out its customer id and current dims.

    A plain read through ``client.get`` — it never flips ``write_enabled``. The shape
    (top-level dim fields, ``customer.id``) is verified against the real sandbox at
    M-DIMS-3's read-back step.
    """
    raw = client.get(PRODUCT_PATH.format(id=product_id))
    customer_id = (raw.get("customer") or {}).get("id")
    current_dims = {field: raw.get(field) for field in DIM_FIELDS}
    return ProductDimsRead(customer_id=customer_id, current_dims=current_dims, raw=raw)


def shadow_mutate_fn(product_id: str, *, sink: Callable[[str], None] | None = None):
    """Build the SHADOW mutate fn for a product: log + record, never write.

    Injected as ``do_mutate`` in shadow mode. It receives the diff (the would-PATCH
    body), logs ``"would PATCH /products/{id} with {diff}"`` and appends to
    ``.records``. M-DIMS-3 swaps this single value for the real ``_mutate``.
    """
    records: list[dict[str, Any]] = []

    def _recorder(diff: dict[str, Any]) -> dict[str, Any]:
        message = f"[SHADOW] would PATCH {PRODUCT_PATH.format(id=product_id)} with {diff}"
        (sink or log.info)(message)
        records.append({"product_id": product_id, "diff": diff})
        return {"shadow": True, "product_id": product_id, "would_patch": diff}

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
) -> DimsApproveResult:
    """Run the full spine chain for a dims write, then apply ``mutate_fn``.

    Mode-agnostic: ``mutate_fn`` is the only thing that differs between shadow and
    live. The chain order is fixed —
    rate-limit → read → customer-guard → authz → idempotent_mutate — so every gate
    engages regardless of what ``mutate_fn`` does (a refused gate raises before the
    mutate fn is ever reached).
    """
    ep = endpoint or PRODUCT_PATH

    # 1. rate-limit (W5) — reject before doing anything, including the read.
    rate_limiter.check(ep)

    # 2. the one real, read-only GET — resolves customer id + current dims.
    read = read_product_for_dims(client, product_id)

    # 3. customer-guard (W3) — refuse a non-allow-listed target, EVEN in shadow.
    verify_customer_allowed(read.customer_id, config)

    # 4. authz (W2) — require the write-auth secret + a matching approval token.
    verify_write_auth(config.write_secret, approval_token)

    # 5. idempotent_mutate (W4) — diff vs the already-read current (one GET total);
    #    empty diff no-ops; otherwise the injected mutate fn fires with the diff.
    desired = {field: desired_dims[field] for field in DIM_FIELDS if field in desired_dims}
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
