"""W0 — write-config: the config surface for CartonCloud write enablement.

First module of the write spine (WRITE_ENABLEMENT_PLAN §2). Holds NO mutating CC
verb. It decides, from the environment, whether writes are permitted at all and
which customer ids a write may target. Every default is *closed*:

  - write disabled            — ``CC_WRITE_ENABLED`` unset or != "true"
  - allow-list = sandbox only — the "SANDBOX TEST - FORAGE" customer
  - live promotion DISARMED   — ``CC_LIVE_PROMOTION`` unset or != "true"

Sandbox and live Forage share one CC tenant, so the customer-id allow-list is the
boundary that keeps a write off real Forage data. Defaulting to sandbox-only makes
"are we pointed at live?" a single, greppable, auditable fact.

**Live promotion (M-DIMS-5a).** The live Forage id is writable ONLY when the single,
standalone ``CC_LIVE_PROMOTION=true`` flag is armed — never by allow-list membership.
``is_customer_allowed`` gates the live id *solely* on that flag, so the live id cannot
be smuggled in via ``CC_WRITE_CUSTOMER_ALLOWLIST``; the allow-list stays sandbox-only
and the promotion is one reversible line of env intent (set it / clear it).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# Config-verified, not yet write-proven. A scoped read on 2026-06-20 resolved
# this id to "SANDBOX TEST - FORAGE" in tenant 4906532d-... — see GROUND_TRUTH.md
# for the recorded result. The write-path round-trip proof lands at M-DIMS-3.
SANDBOX_CUSTOMER_ID = "a8dab3f2-defa-433e-87a0-01dee48a2286"

# The live Forage customer id. Named here deliberately for M-DIMS-5a: it is the single
# explicit promotion target, and ``is_customer_allowed`` must compare against it to gate
# it behind ``CC_LIVE_PROMOTION``. It is NEVER in any default allow-list (the only id the
# guard treats specially); a write reaches it ONLY when the flag is armed.
LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"


def _default_allowlist() -> frozenset[str]:
    return frozenset({SANDBOX_CUSTOMER_ID})


@dataclass(frozen=True)
class WriteConfig:
    """Immutable snapshot of write-enablement config. Closed by default."""

    write_enabled: bool = False
    write_secret: str | None = None
    customer_allowlist: frozenset[str] = field(default_factory=_default_allowlist)
    live_promotion: bool = False

    def is_customer_allowed(self, customer_id: str) -> bool:
        """True iff a write may target this customer id under this config.

        The live Forage id is gated SOLELY by ``live_promotion`` — never by allow-list
        membership — so it cannot be smuggled in via ``CC_WRITE_CUSTOMER_ALLOWLIST``.
        Every other id is pure allow-list membership.
        """
        if customer_id == LIVE_FORAGE_CUSTOMER_ID:
            return self.live_promotion
        return customer_id in self.customer_allowlist

    @classmethod
    def from_env(cls) -> "WriteConfig":
        """Build from ``CC_WRITE_*`` env vars, failing closed on absent/empty.

        - ``CC_WRITE_ENABLED``: only the literal "true" (case/space-insensitive)
          opens writes; anything else (incl. "1"/"yes"/"") stays closed.
        - ``CC_WRITE_SECRET``: loaded if non-empty, else ``None``.
        - ``CC_WRITE_CUSTOMER_ALLOWLIST``: comma-separated ids, whitespace-trimmed,
          empties dropped. Unset or all-empty falls back to sandbox-only — an
          empty value never means "allow everything".
        - ``CC_LIVE_PROMOTION``: only the literal "true" (case/space-insensitive) arms
          live promotion; anything else (incl. "1"/"yes"/"") stays disarmed. This is the
          one line of intent that makes the live Forage id writable.
        """
        write_enabled = os.environ.get("CC_WRITE_ENABLED", "").strip().lower() == "true"

        secret = os.environ.get("CC_WRITE_SECRET")
        if secret is not None:
            secret = secret.strip() or None

        raw = os.environ.get("CC_WRITE_CUSTOMER_ALLOWLIST", "")
        ids = frozenset(part.strip() for part in raw.split(",") if part.strip())
        allowlist = ids or _default_allowlist()

        live_promotion = os.environ.get("CC_LIVE_PROMOTION", "").strip().lower() == "true"

        return cls(
            write_enabled=write_enabled,
            write_secret=secret,
            customer_allowlist=allowlist,
            live_promotion=live_promotion,
        )
