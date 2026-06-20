"""W5 — cc-rate-limit: a token-bucket limiter on the mutate path.

The Python analogue of dim-capture-app's `TokenBucket` (module 02 cc-client / 10
cc-resilience). The discipline (WRITE_ENABLEMENT_PLAN §0): ≤ the lower of CC's
documented ceilings — outbound-order create is ~30/min (brief §6.5) and the
dim-capture-app bucket ran 60/min — so the per-endpoint ceiling is **30/min**. When
the budget is spent the limiter **rejects, it does not queue**: the request is never
sent, the caller gets a typed error.

A continuous refill (capacity tokens, refilled at ceiling/60 per second, capped at
capacity) means a steady ≤30/min flows but a burst past the bucket is refused. Buckets
are per-endpoint, so exhausting one endpoint can't starve another.

Fully offline: a fake monotonic clock makes refill deterministic. No httpx, no real
CC write. This module holds no mutating verb — it only decides send/reject.
"""
from __future__ import annotations

import threading

import pytest

from cc_client.write_rate_limit import (
    TokenBucket,
    MutateRateLimiter,
    CartonCloudWriteRateLimited,
    DEFAULT_CEILING_PER_MIN,
)
from cc_client.client import CartonCloudError, CartonCloudRateLimited


class FakeClock:
    """Deterministic monotonic clock in seconds."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ---------- the ceiling is the LOWER of 30/min and 60/min ----------

def test_default_ceiling_is_thirty_per_minute():
    # Lower of CC ~30/min (outbound create) and 60/min (dim-capture-app bucket).
    assert DEFAULT_CEILING_PER_MIN == 30


def test_limiter_uses_the_thirty_per_minute_ceiling_by_default():
    clock = FakeClock()
    limiter = MutateRateLimiter(now=clock)
    # 30 sends in a frozen instant succeed; the 31st is rejected.
    for _ in range(30):
        limiter.check("/products/{id}")
    with pytest.raises(CartonCloudWriteRateLimited):
        limiter.check("/products/{id}")


# ---------- TokenBucket unit ----------

def test_bucket_starts_full():
    clock = FakeClock()
    bucket = TokenBucket(capacity=3, refill_per_sec=0.5, now=clock)
    assert bucket.take() is True
    assert bucket.take() is True
    assert bucket.take() is True
    assert bucket.take() is False  # empty now


def test_bucket_refills_continuously_capped_at_capacity():
    clock = FakeClock()
    bucket = TokenBucket(capacity=2, refill_per_sec=0.5, now=clock)
    assert bucket.take() and bucket.take()
    assert bucket.take() is False              # drained
    clock.advance(2.0)                          # 2s * 0.5/s = 1 token
    assert bucket.take() is True
    assert bucket.take() is False              # only one refilled


def test_bucket_refill_never_exceeds_capacity():
    clock = FakeClock()
    bucket = TokenBucket(capacity=2, refill_per_sec=0.5, now=clock)
    assert bucket.take() and bucket.take()
    clock.advance(10_000)                       # would refill thousands, capped at 2
    assert bucket.take() and bucket.take()
    assert bucket.take() is False


# ---------- limiter rejects past ceiling, refills correctly ----------

def test_rejects_when_spent_and_does_not_consume_future_budget():
    clock = FakeClock()
    limiter = MutateRateLimiter(per_minute=30, now=clock)
    for _ in range(30):
        limiter.check("ep")
    # Spent: rejected, and the rejection itself doesn't queue or block.
    with pytest.raises(CartonCloudWriteRateLimited):
        limiter.check("ep")
    # 30/min = one token every 2s. Advance 2s → exactly one more allowed.
    clock.advance(2.0)
    limiter.check("ep")                          # succeeds
    with pytest.raises(CartonCloudWriteRateLimited):
        limiter.check("ep")                      # spent again


def test_steady_rate_at_ceiling_keeps_flowing():
    clock = FakeClock()
    limiter = MutateRateLimiter(per_minute=30, now=clock)
    for _ in range(30):
        limiter.check("ep")                      # drain the burst
    # At 30/min, one token frees every 2s; pacing at that rate never rejects.
    for _ in range(10):
        clock.advance(2.0)
        limiter.check("ep")


# ---------- per-endpoint isolation ----------

def test_buckets_are_per_endpoint():
    clock = FakeClock()
    limiter = MutateRateLimiter(per_minute=30, now=clock)
    for _ in range(30):
        limiter.check("endpoint-A")
    with pytest.raises(CartonCloudWriteRateLimited):
        limiter.check("endpoint-A")              # A spent
    # B has its own full budget — unaffected.
    for _ in range(30):
        limiter.check("endpoint-B")
    with pytest.raises(CartonCloudWriteRateLimited):
        limiter.check("endpoint-B")


# ---------- reject, do not queue: the offending endpoint is named ----------

def test_rejection_names_the_endpoint_and_is_typed():
    clock = FakeClock()
    limiter = MutateRateLimiter(per_minute=1, now=clock)
    limiter.check("/products/p1")
    with pytest.raises(CartonCloudWriteRateLimited) as exc:
        limiter.check("/products/p1")
    assert "/products/p1" in str(exc.value)


# ---------- typed: subclasses CartonCloudError, distinct from transport 429 ----------

def test_exception_subclasses_carton_cloud_error():
    assert issubclass(CartonCloudWriteRateLimited, CartonCloudError)


def test_local_limiter_error_is_distinct_from_transport_429():
    # CartonCloudRateLimited means "CC returned 429 after retries"; the local limiter
    # refusing BEFORE sending is a different condition — don't conflate them.
    assert CartonCloudWriteRateLimited is not CartonCloudRateLimited
    assert not issubclass(CartonCloudWriteRateLimited, CartonCloudRateLimited)


# ---------- thread-safety: concurrent checks never exceed the ceiling ----------

def test_concurrent_checks_never_exceed_ceiling():
    clock = FakeClock()                          # frozen: no refill during the race
    limiter = MutateRateLimiter(per_minute=30, now=clock)
    n = 64
    granted = 0
    guard = threading.Lock()
    start = threading.Barrier(n)

    def worker():
        nonlocal granted
        start.wait()
        try:
            limiter.check("ep")
        except CartonCloudWriteRateLimited:
            return
        with guard:
            granted += 1

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert granted == 30, f"exactly the ceiling may pass, got {granted}"


# ---------- package export ----------

def test_exported_from_package():
    from cc_client import (
        TokenBucket as PkgBucket,
        MutateRateLimiter as PkgLimiter,
        CartonCloudWriteRateLimited as PkgErr,
        DEFAULT_CEILING_PER_MIN as pkg_ceiling,
    )

    assert PkgBucket is TokenBucket
    assert PkgLimiter is MutateRateLimiter
    assert PkgErr is CartonCloudWriteRateLimited
    assert pkg_ceiling == DEFAULT_CEILING_PER_MIN
