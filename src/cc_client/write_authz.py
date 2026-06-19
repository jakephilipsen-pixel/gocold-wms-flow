"""W2 — cc-write-authz: the write-auth secret check that gates every mutate.

Python analogue of dim-capture-app's `requireSyncKey` (module 12). Fail-closed:

  - no server-side secret configured  -> CartonCloudWriteAuthNotConfigured (503 analogue)
  - caller presents no token           -> CartonCloudWriteAuthFailed (401 analogue)
  - token does not match (const-time)  -> CartonCloudWriteAuthFailed (401 analogue)
  - token matches                      -> proceed (returns None)

The "not configured" check takes precedence over a missing token: a server with no
write secret is the more fundamental refusal. The token compare uses
``hmac.compare_digest`` so a wrong guess cannot be narrowed down by timing.

Holds NO mutating CC verb. Composed in front of ``CartonCloudClient._mutate`` (W1)
by the write surface; on its own it only decides allow/deny.
"""
from __future__ import annotations

import hmac

from .client import CartonCloudError


class CartonCloudWriteAuthNotConfigured(CartonCloudError):
    """No server-side write secret is configured — refuse (503 analogue)."""


class CartonCloudWriteAuthFailed(CartonCloudError):
    """Caller's write-auth token is missing or wrong — refuse (401 analogue)."""


def verify_write_auth(configured_secret: str | None, provided_token: str | None) -> None:
    """Raise unless the caller presented the correct write-auth token.

    Fail-closed and order-sensitive: an unconfigured secret refuses (503 analogue)
    before a missing/empty token is even considered (401 analogue). The match is a
    constant-time compare.
    """
    if not configured_secret:
        raise CartonCloudWriteAuthNotConfigured(
            "write-auth secret not configured (CC_WRITE_SECRET unset/empty); "
            "refusing write"
        )
    if not provided_token:
        raise CartonCloudWriteAuthFailed(
            "write-auth token missing; refusing write"
        )
    if not hmac.compare_digest(str(provided_token), str(configured_secret)):
        raise CartonCloudWriteAuthFailed(
            "write-auth token mismatch; refusing write"
        )
