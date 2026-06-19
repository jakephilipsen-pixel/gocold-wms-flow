"""W0 — write-config: the config surface for CartonCloud write enablement.

First module of the write spine (WRITE_ENABLEMENT_PLAN §2). Holds NO mutating CC
verb. It decides, from the environment, whether writes are permitted at all and
which customer ids a write may target. Every default is *closed*:

  - write disabled            — ``CC_WRITE_ENABLED`` unset or != "true"
  - allow-list = sandbox only — the "SANDBOX TEST - FORAGE" customer
  - live Forage is NEVER a default — it enters the allow-list only via an explicit
    ``CC_WRITE_CUSTOMER_ALLOWLIST`` that names it (the live-promotion path).

Sandbox and live Forage share one CC tenant, so the customer-id allow-list is the
boundary that keeps a write off real Forage data. Defaulting to sandbox-only makes
"are we pointed at live?" a single, greppable, auditable fact: either an env line
names the live id, or it doesn't.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# Config-verified, not yet write-proven. A scoped read on 2026-06-20 resolved
# this id to "SANDBOX TEST - FORAGE" in tenant 4906532d-... — see GROUND_TRUTH.md
# for the recorded result. The write-path round-trip proof lands at M-DIMS-3.
SANDBOX_CUSTOMER_ID = "a8dab3f2-defa-433e-87a0-01dee48a2286"


def _default_allowlist() -> frozenset[str]:
    return frozenset({SANDBOX_CUSTOMER_ID})


@dataclass(frozen=True)
class WriteConfig:
    """Immutable snapshot of write-enablement config. Closed by default."""

    write_enabled: bool = False
    write_secret: str | None = None
    customer_allowlist: frozenset[str] = field(default_factory=_default_allowlist)

    def is_customer_allowed(self, customer_id: str) -> bool:
        """True iff a write may target this customer id under this config."""
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
        """
        write_enabled = os.environ.get("CC_WRITE_ENABLED", "").strip().lower() == "true"

        secret = os.environ.get("CC_WRITE_SECRET")
        if secret is not None:
            secret = secret.strip() or None

        raw = os.environ.get("CC_WRITE_CUSTOMER_ALLOWLIST", "")
        ids = frozenset(part.strip() for part in raw.split(",") if part.strip())
        allowlist = ids or _default_allowlist()

        return cls(
            write_enabled=write_enabled,
            write_secret=secret,
            customer_allowlist=allowlist,
        )
