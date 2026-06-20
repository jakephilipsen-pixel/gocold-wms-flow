"""W4 — cc-write-idempotency: per-object serialisation + read-before-write diff.

The Python analogue of dim-capture-app's `pg_advisory_xact_lock` (module 13). The
Python side has no Postgres, so we provide the *equivalent guarantee* in-process, not
a port of advisory-lock code (WRITE_ENABLEMENT_PLAN §2.4):

  - **Serialise:** concurrent mutates to the SAME object id run one-at-a-time (a
    blocking per-object lock — the loser waits and completes, never drops its write).
    Different object ids are independent and run in parallel.
  - **Read-before-write diff:** fetch the object's current CC state, compute the diff
    against the desired payload, and if the diff is empty → **no-op, no PATCH**. A
    non-empty diff issues exactly one mutate, carrying only the changed fields.

The read is a GET (allowed) issued *before* deciding to write — and it must NOT flip
``write_enabled`` (that flag stays exactly as it was across the read and the no-op).

Fully offline: pure functions, threads, and a fake transport stand in for httpx with a
pre-seeded token. No real CC write happens here.
"""
from __future__ import annotations

import threading
import time

import httpx
import pytest

from cc_client.write_idempotency import (
    compute_diff,
    serialise_object,
    ObjectLockRegistry,
    idempotent_mutate,
    IdempotentWriteResult,
)
from cc_client.client import CartonCloudClient, _Token


# ---------- compute_diff: the read-before-write correctness check ----------

def test_diff_empty_when_state_matches():
    assert compute_diff({"length": 100, "width": 50}, {"length": 100, "width": 50}) == {}


def test_diff_contains_only_changed_fields():
    diff = compute_diff({"length": 100, "width": 50}, {"length": 120, "width": 50})
    assert diff == {"length": 120}


def test_diff_includes_field_absent_from_current():
    diff = compute_diff({"length": 100}, {"length": 100, "weight": 12})
    assert diff == {"weight": 12}


def test_diff_ignores_extra_fields_in_current():
    # Current CC object has many fields; we only care about the ones we want to set.
    diff = compute_diff(
        {"length": 100, "width": 50, "name": "Frozen Peas", "status": "active"},
        {"length": 100},
    )
    assert diff == {}


def test_diff_detects_all_changed():
    diff = compute_diff({"length": 100, "width": 50}, {"length": 120, "width": 60})
    assert diff == {"length": 120, "width": 60}


# ---------- per-object lock: concurrent SAME-id mutates serialise ----------

def test_concurrent_mutates_to_same_id_serialise():
    reg = ObjectLockRegistry()
    n = 8
    active = 0
    max_active = 0
    start = threading.Barrier(n)

    def worker():
        nonlocal active, max_active
        start.wait()  # force all threads to contend at once
        with serialise_object("prod-1", registry=reg):
            # All mutations of these counters happen under the object lock; if the
            # lock works, only one thread is ever inside, so max_active stays 1.
            active += 1
            max_active = max(max_active, active)
            time.sleep(0.02)
            active -= 1

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert max_active == 1, "same-id mutates must not overlap"


# ---------- per-object lock: DIFFERENT ids run in parallel (keyed, not global) ----------

def test_different_ids_do_not_serialise():
    reg = ObjectLockRegistry()
    n = 6
    active = 0
    max_active = 0
    guard = threading.Lock()  # genuinely concurrent now → guard the test counters
    start = threading.Barrier(n)

    def worker(i):
        nonlocal active, max_active
        start.wait()
        with serialise_object(f"prod-{i}", registry=reg):
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with guard:
                active -= 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert max_active == n, "different ids must run concurrently, not serialise"


def test_registry_returns_same_lock_per_id():
    reg = ObjectLockRegistry()
    assert reg.lock_for("a") is reg.lock_for("a")
    assert reg.lock_for("a") is not reg.lock_for("b")


def test_lock_released_after_exception():
    # A failing critical section must release the lock — else the object deadlocks.
    reg = ObjectLockRegistry()
    with pytest.raises(ValueError):
        with serialise_object("p1", registry=reg):
            raise ValueError("boom")
    acquired = reg.lock_for("p1").acquire(timeout=1)
    assert acquired, "lock must be free after an exception in the critical section"
    reg.lock_for("p1").release()


# ---------- idempotent_mutate: empty diff is a no-op (no PATCH) ----------

def test_noop_when_diff_empty_never_calls_do_mutate():
    called: list = []
    result = idempotent_mutate(
        "p1",
        read_current=lambda: {"length": 100, "width": 50},
        desired={"length": 100, "width": 50},
        do_mutate=lambda diff: called.append(diff),
    )
    assert isinstance(result, IdempotentWriteResult)
    assert result.mutated is False
    assert result.diff == {}
    assert result.response is None
    assert called == [], "an empty diff must not issue a mutate"


def test_nonempty_diff_calls_do_mutate_once_with_diff_only():
    calls: list = []

    def do_mutate(diff):
        calls.append(diff)
        return "patched"

    result = idempotent_mutate(
        "p1",
        read_current=lambda: {"length": 100, "width": 50},
        desired={"length": 120, "width": 50},
        do_mutate=do_mutate,
    )
    assert result.mutated is True
    assert result.diff == {"length": 120}
    assert result.response == "patched"
    assert calls == [{"length": 120}], "mutate must carry only the changed fields, once"


def test_idempotent_mutate_releases_lock_on_mutate_error():
    reg = ObjectLockRegistry()

    def boom(diff):
        raise RuntimeError("patch failed")

    with pytest.raises(RuntimeError):
        idempotent_mutate(
            "p1",
            read_current=lambda: {"l": 1},
            desired={"l": 2},
            do_mutate=boom,
            registry=reg,
        )
    # A failed PATCH must not leave the object permanently locked.
    assert reg.lock_for("p1").acquire(timeout=1)
    reg.lock_for("p1").release()


# ---------- integration with the real client (mock transport) ----------

class RecordingTransport:
    """Returns canned current state on GET; ok on any write. Records every call."""

    def __init__(self, current_state: dict):
        self.current = current_state
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "json": json})
        if method == "GET":
            return httpx.Response(200, json=self.current)
        return httpx.Response(200, json={"ok": True})


def _client(*, write_enabled: bool) -> CartonCloudClient:
    c = CartonCloudClient(
        client_id="id",
        client_secret="sec",
        tenant_id="TENANT",
        base_url="https://cc.example",
        write_enabled=write_enabled,
    )
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def test_noop_issues_no_patch_and_does_not_flip_write_enabled():
    c = _client(write_enabled=True)
    transport = RecordingTransport(current_state={"length": 100, "width": 50})
    c._http = transport

    result = idempotent_mutate(
        "p1",
        read_current=lambda: c.get("/products/p1"),
        desired={"length": 100, "width": 50},
        do_mutate=lambda diff: c._mutate("PATCH", "/products/p1", approved=True, json=diff),
    )

    assert result.mutated is False
    methods = [call["method"] for call in transport.calls]
    assert "GET" in methods, "read-before-write must issue the GET"
    assert "PATCH" not in methods, "an empty diff must not PATCH"
    assert c.write_enabled is True, "the read must NOT flip write_enabled"


def test_diff_issues_single_patch_with_changed_fields_only():
    c = _client(write_enabled=True)
    transport = RecordingTransport(current_state={"length": 100, "width": 50})
    c._http = transport

    result = idempotent_mutate(
        "p1",
        read_current=lambda: c.get("/products/p1"),
        desired={"length": 120, "width": 50},
        do_mutate=lambda diff: c._mutate("PATCH", "/products/p1", approved=True, json=diff),
    )

    assert result.mutated is True
    assert result.diff == {"length": 120}
    patches = [call for call in transport.calls if call["method"] == "PATCH"]
    assert len(patches) == 1, "exactly one PATCH"
    assert patches[0]["json"] == {"length": 120}, "PATCH carries only the diff"
    assert c.write_enabled is True


def test_read_does_not_flip_write_enabled_when_disabled():
    # Even with writes disabled, the read path is a plain GET and stays read-only;
    # the no-op decision needs no write capability at all.
    c = _client(write_enabled=False)
    transport = RecordingTransport(current_state={"length": 100})
    c._http = transport

    result = idempotent_mutate(
        "p1",
        read_current=lambda: c.get("/products/p1"),
        desired={"length": 100},
        do_mutate=lambda diff: c._mutate("PATCH", "/products/p1", approved=True, json=diff),
    )
    assert result.mutated is False
    assert c.write_enabled is False


# ---------- package export ----------

def test_exported_from_package():
    from cc_client import (
        compute_diff as pkg_diff,
        serialise_object as pkg_serialise,
        ObjectLockRegistry as PkgRegistry,
        idempotent_mutate as pkg_mutate,
        IdempotentWriteResult as PkgResult,
    )

    assert pkg_diff is compute_diff
    assert pkg_serialise is serialise_object
    assert PkgRegistry is ObjectLockRegistry
    assert pkg_mutate is idempotent_mutate
    assert PkgResult is IdempotentWriteResult
