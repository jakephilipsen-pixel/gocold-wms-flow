"""W5 — cc-rate-limit: a token-bucket limiter on the mutate path.

The Python analogue of dim-capture-app's `TokenBucket` (module 02 cc-client / 10
cc-resilience), per WRITE_ENABLEMENT_PLAN §0. The ceiling is the **lower** of CC's
documented limits — outbound-order create is ~30/min (brief §6.5) and the
dim-capture-app bucket ran 60/min — so the per-endpoint ceiling is **30/min**.

When the budget is spent the limiter **rejects, it does not queue**: the request is
never sent and the caller gets a typed ``CartonCloudWriteRateLimited``. A continuous
refill (``capacity`` tokens, refilled at ``ceiling/60`` per second, capped at
``capacity``) lets a steady ≤30/min flow while refusing a burst past the bucket.
Buckets are per-endpoint, so exhausting one endpoint can't starve another.

Holds NO mutating CC verb and no httpx — it only decides send/reject. Composed in
front of ``CartonCloudClient._mutate`` (W1) by the write surface; on its own it just
consumes a token or refuses. Thread-safe so a threaded surface (FastAPI) can't race
past the ceiling.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from .client import CartonCloudError

# Lower of CC's ~30/min (outbound-order create, brief §6.5) and the 60/min
# dim-capture-app bucket. Per endpoint.
DEFAULT_CEILING_PER_MIN = 30


class CartonCloudWriteRateLimited(CartonCloudError):
    """The local mutate-path bucket is empty — refuse (request NOT sent).

    Distinct from ``CartonCloudRateLimited``, which means CC itself returned 429
    after retries. This one fires *before* anything is sent, by our own budget.
    """


class TokenBucket:
    """In-memory token bucket. Starts full; refills continuously at
    ``refill_per_sec``, capped at ``capacity``. ``take()`` consumes one token if
    available, else returns ``False`` — the caller turns that into a refusal.

    The clock is injectable (default ``time.monotonic``) so refill is deterministic
    under test and immune to wall-clock jumps in production.
    """

    def __init__(
        self,
        capacity: float,
        refill_per_sec: float,
        *,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = float(capacity)
        self._refill_per_sec = float(refill_per_sec)
        self._now = now
        self._tokens = float(capacity)
        self._last_refill = now()

    def _refill(self) -> None:
        t = self._now()
        elapsed = t - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_sec)
        self._last_refill = t

    def take(self) -> bool:
        self._refill()
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False


class MutateRateLimiter:
    """Per-endpoint token-bucket limiter for the write path.

    Each endpoint gets its own bucket at ``per_minute`` (default 30/min). ``check``
    consumes one token for the endpoint or raises ``CartonCloudWriteRateLimited`` —
    reject, don't queue. Thread-safe: token accounting is guarded so concurrent
    callers can't slip past the ceiling.
    """

    def __init__(
        self,
        *,
        per_minute: int = DEFAULT_CEILING_PER_MIN,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._per_minute = per_minute
        self._refill_per_sec = per_minute / 60.0
        self._now = now
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _bucket_for(self, endpoint: str) -> TokenBucket:
        bucket = self._buckets.get(endpoint)
        if bucket is None:
            bucket = TokenBucket(self._per_minute, self._refill_per_sec, now=self._now)
            self._buckets[endpoint] = bucket
        return bucket

    def check(self, endpoint: str) -> None:
        """Consume one token for ``endpoint`` or refuse. Reject, never queue."""
        with self._lock:
            allowed = self._bucket_for(endpoint).take()
        if not allowed:
            raise CartonCloudWriteRateLimited(
                f"rate limit exceeded for endpoint {endpoint!r} "
                f"({self._per_minute}/min ceiling); refusing write (not queued)"
            )
