"""W4 — cc-write-idempotency: per-object serialisation + read-before-write diff.

The Python analogue of dim-capture-app's `pg_advisory_xact_lock` (module 13). The
Python side has no Postgres, so this provides the *equivalent guarantee* in-process,
not a port of advisory-lock code (WRITE_ENABLEMENT_PLAN §2.4):

  - **Serialise** — concurrent mutates to the SAME object id run one-at-a-time via a
    blocking per-object lock (the loser waits and completes, never drops its write).
    Different object ids hold different locks and run in parallel.
  - **Read-before-write diff** — fetch the object's current CC state, diff it against
    the desired payload; an empty diff is a **no-op** (no mutate issued), and a
    non-empty diff issues exactly one mutate carrying only the changed fields.

This module holds NO mutating CC verb and no httpx: the read (a GET) and the write
(W1's ``_mutate``) are injected callables, so the only sanctioned write path stays
W1. The read is issued *before* deciding to write and, being a plain GET through
``_request``, never flips ``write_enabled``. Composed in front of ``_mutate`` by the
write surface; on its own it only serialises and decides mutate/no-op.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping


def compute_diff(current: Mapping[str, Any], desired: Mapping[str, Any]) -> dict[str, Any]:
    """Return the fields of ``desired`` whose value differs from ``current``.

    Only keys present in ``desired`` are considered — extra fields on the current CC
    object are ignored. An empty result means the desired state already holds, so no
    write is needed (the read-before-write no-op).
    """
    return {
        key: value
        for key, value in desired.items()
        if key not in current or current[key] != value
    }


class ObjectLockRegistry:
    """Lazily-created, per-object-id locks. Same id → same lock → serialised.

    The single-process analogue of an advisory lock keyed by object id. A class (not
    module globals) so each surface — and each test — can hold an isolated registry.
    """

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def lock_for(self, object_id: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(object_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[object_id] = lock
            return lock


# Default process-wide registry for callers that don't inject their own.
_DEFAULT_REGISTRY = ObjectLockRegistry()


@contextmanager
def serialise_object(
    object_id: str, *, registry: ObjectLockRegistry | None = None
) -> Iterator[None]:
    """Block until this object id's lock is held, run the body, then release.

    Blocking (not try-lock): a concurrent caller for the same id waits its turn and
    then completes — it never silently drops its write. The lock is always released,
    even if the body raises.
    """
    reg = registry or _DEFAULT_REGISTRY
    lock = reg.lock_for(object_id)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


@dataclass(frozen=True)
class IdempotentWriteResult:
    """Outcome of an idempotent mutate: whether it wrote, the diff, the response."""

    mutated: bool
    diff: dict[str, Any]
    response: Any  # None on a no-op


def idempotent_mutate(
    object_id: str,
    *,
    read_current: Callable[[], Mapping[str, Any]],
    desired: Mapping[str, Any],
    do_mutate: Callable[[dict[str, Any]], Any],
    registry: ObjectLockRegistry | None = None,
) -> IdempotentWriteResult:
    """Serialise on ``object_id``, then read-before-write: no-op on an empty diff.

    Under the object's lock: read the current state, compute the diff against
    ``desired``; if empty, return a no-op (``do_mutate`` is never called). Otherwise
    call ``do_mutate`` once with the diff (changed fields only) and return its result.

    ``read_current`` should be a GET (read-only — it must not flip ``write_enabled``);
    ``do_mutate`` should be W1's ``_mutate``. Both are injected so this module holds no
    mutating verb of its own.
    """
    with serialise_object(object_id, registry=registry):
        current = read_current()
        diff = compute_diff(current, desired)
        if not diff:
            return IdempotentWriteResult(mutated=False, diff={}, response=None)
        response = do_mutate(diff)
        return IdempotentWriteResult(mutated=True, diff=diff, response=response)
