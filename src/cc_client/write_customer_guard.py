"""W3 — cc-write-customer-guard: the §0 guard rail, the most safety-critical check.

The single most safety-critical check in the whole write path (WRITE_ENABLEMENT_PLAN
§2.3). Sandbox and live Forage share ONE CC tenant, so the same OAuth2 client that can
PATCH a sandbox product can physically reach a live Forage product — there is **no
tenant boundary protecting live data.** The customer-id allow-list is the only thing
standing between a test write and a real Forage product.

So this guard refuses **independently of every other gate**. Before any mutate, resolve
the target object's customer id and assert it is in the allow-list
(``WriteConfig.is_customer_allowed``). Not in the list → refuse loudly, logging the
offending id. A live-Forage-id target is refused even with ``write_enabled=True``, a
valid auth token, and ``approved=True`` — every other gate open, this one still stops it.

Fail-closed: a blank/None customer id, or an empty allow-list, refuses. An empty
allow-list never means "allow everything"; only a positive membership clears the guard.

**"Allow-listed" is NOT "intended target."** The guard gates by *customer id*, not by
active-status: an allow-listed sandbox customer admits ALL its products (1111 in the
sandbox — only 46 active ``s``-prefixed, ~1065 inactive/archived ``ZZ*`` legacy SKUs,
see GROUND_TRUTH §5). Choosing a *known-active* SKU within an allowed customer is
M-DIMS-3's concern, NOT this guard's. This guard only proves the target's *customer*
cleared the boundary.

Holds NO mutating CC verb, no httpx, no ``write_enabled`` toggle — a pure decision
function. Composed in front of ``CartonCloudClient._mutate`` (W1) by the write surface
as guard → authz (W2) → _mutate; on its own it only decides allow/deny.
"""
from __future__ import annotations

import logging

from .client import CartonCloudError
from .write_config import WriteConfig

log = logging.getLogger(__name__)


class CartonCloudCustomerNotAllowed(CartonCloudError):
    """The target object's customer id is not in the write allow-list — refuse."""


def verify_customer_allowed(customer_id: str | None, config: WriteConfig) -> None:
    """Raise unless the target's resolved customer id is in the allow-list.

    Fail-closed: a blank/None id, or an empty allow-list, refuses. Refuses loudly —
    the offending customer id is logged at WARNING and named in the exception. Returns
    ``None`` on the one allow path (customer is positively allow-listed).

    Independent of every other gate (write_enabled, auth token, approval): this guard
    decides purely on customer id, so it stops a live-Forage target even with all
    other gates open.
    """
    if not customer_id or not str(customer_id).strip():
        log.warning(
            "cc-write-customer-guard: REFUSED write — blank/missing target customer "
            "id (cannot clear a positive allow-list); refusing"
        )
        raise CartonCloudCustomerNotAllowed(
            "target customer id is blank/missing; refusing write"
        )

    if not config.is_customer_allowed(customer_id):
        log.warning(
            "cc-write-customer-guard: REFUSED write — target customer id %r is not in "
            "the write allow-list; refusing",
            customer_id,
        )
        raise CartonCloudCustomerNotAllowed(
            f"target customer id {customer_id!r} is not in the write allow-list; "
            "refusing write"
        )
