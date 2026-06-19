"""W1 — cc-mutate-core: the single guarded write entry point on the client.

`_mutate()` is the ONLY place in the Python client allowed to issue a non-GET
business write. It is double-gated (``write_enabled`` AND a per-call ``approved``
token), issues the request exactly ONCE (no auto-retry — that would risk a
double-apply on a non-idempotent write), and converts a timeout into a typed
error. It deliberately does NOT use the ``post_search``/report-run trick of
flipping ``write_enabled`` inside a ``finally`` — the write is gated explicitly.

Fully offline: a fake transport stands in for httpx and a pre-seeded token
bypasses OAuth. No real CC write happens here (WRITE_ENABLEMENT_PLAN §2.1).
"""
from __future__ import annotations

import time

import httpx
import pytest

from cc_client.client import (
    CartonCloudClient,
    CartonCloudError,
    CartonCloudTimeout,
    CartonCloudWriteRefused,
    _Token,
)


class FakeTransport:
    """Records each request; returns a canned response or raises."""

    def __init__(self, *, response: httpx.Response | None = None, raises: Exception | None = None):
        self._response = response
        self._raises = raises
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        self.calls.append(
            {"method": method, "url": url, "json": json, "headers": headers, "timeout": timeout}
        )
        if self._raises is not None:
            raise self._raises
        return self._response


def _client(*, write_enabled: bool) -> CartonCloudClient:
    c = CartonCloudClient(
        client_id="id",
        client_secret="sec",
        tenant_id="TENANT",
        base_url="https://cc.example",
        write_enabled=write_enabled,
    )
    # pre-seed a valid token so _ensure_token() never hits the network
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def _ok() -> httpx.Response:
    return httpx.Response(200, json={"id": "p1"})


# ---------- the double-gate refuses, and never touches the network ----------

def test_refuses_when_write_disabled():
    c = _client(write_enabled=False)
    c._http = FakeTransport(response=_ok())
    with pytest.raises(CartonCloudWriteRefused):
        c._mutate("PATCH", "/products/p1", approved=True, json={"length": 1})
    assert c._http.calls == []  # refused before any request


def test_refuses_when_not_approved():
    c = _client(write_enabled=True)
    c._http = FakeTransport(response=_ok())
    with pytest.raises(CartonCloudWriteRefused):
        c._mutate("PATCH", "/products/p1", approved=False, json={"length": 1})
    assert c._http.calls == []


def test_refuses_when_both_gates_closed():
    c = _client(write_enabled=False)
    c._http = FakeTransport(response=_ok())
    with pytest.raises(CartonCloudWriteRefused):
        c._mutate("POST", "/products", approved=False, json={})
    assert c._http.calls == []


def test_refused_mutate_never_opens_the_write_flag():
    # No transient flip: a gate-closed client stays closed across the call.
    c = _client(write_enabled=False)
    c._http = FakeTransport(response=_ok())
    with pytest.raises(CartonCloudWriteRefused):
        c._mutate("PATCH", "/products/p1", approved=True)
    assert c.write_enabled is False


# ---------- double-gate open: issues exactly once ----------

def test_issues_once_when_double_gated_open():
    c = _client(write_enabled=True)
    c._http = FakeTransport(response=_ok())
    r = c._mutate("PATCH", "/products/p1", approved=True, json={"length": 100})

    assert r.status_code == 200
    assert len(c._http.calls) == 1  # exactly one request
    call = c._http.calls[0]
    assert call["method"] == "PATCH"
    assert call["url"] == "https://cc.example/tenants/TENANT/products/p1"
    assert call["json"] == {"length": 100}
    assert call["timeout"] == CartonCloudClient.MUTATE_TIMEOUT
    assert call["headers"]["Authorization"] == "Bearer tok"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["headers"]["Accept-Version"] == CartonCloudClient.ACCEPT_VERSION


def test_successful_mutate_leaves_write_flag_unchanged():
    c = _client(write_enabled=True)
    c._http = FakeTransport(response=_ok())
    c._mutate("PATCH", "/products/p1", approved=True, json={"length": 1})
    assert c.write_enabled is True


def test_non_tenant_scoped_url():
    c = _client(write_enabled=True)
    c._http = FakeTransport(response=_ok())
    c._mutate("POST", "/some/path", approved=True, tenant_scoped=False, json={})
    assert c._http.calls[0]["url"] == "https://cc.example/some/path"


# ---------- single-shot: no auto-retry on writes ----------

def test_no_retry_on_server_error():
    # _request retries 5xx; _mutate must NOT — a retried write can double-apply.
    c = _client(write_enabled=True)
    c._http = FakeTransport(response=httpx.Response(500, text="boom"))
    with pytest.raises(CartonCloudError):
        c._mutate("POST", "/products", approved=True, json={})
    assert len(c._http.calls) == 1  # issued once, not retried


def test_non_success_status_raises():
    c = _client(write_enabled=True)
    c._http = FakeTransport(response=httpx.Response(422, text="bad dims"))
    with pytest.raises(CartonCloudError):
        c._mutate("PATCH", "/products/p1", approved=True, json={"length": -1})
    assert len(c._http.calls) == 1


# ---------- 12s timeout -> typed error, issued once ----------

def test_timeout_becomes_typed_error_issued_once():
    c = _client(write_enabled=True)
    c._http = FakeTransport(raises=httpx.TimeoutException("slow"))
    with pytest.raises(CartonCloudTimeout):
        c._mutate("PATCH", "/products/p1", approved=True, json={"length": 1})
    assert len(c._http.calls) == 1  # no retry storm on timeout


def test_network_error_becomes_typed_error():
    c = _client(write_enabled=True)
    c._http = FakeTransport(raises=httpx.ConnectError("no route"))
    with pytest.raises(CartonCloudError):
        c._mutate("POST", "/products", approved=True, json={})
    assert len(c._http.calls) == 1


# ---------- typed errors exported from the package root ----------

def test_typed_errors_exported_from_package():
    from cc_client import CartonCloudTimeout as PkgTimeout
    from cc_client import CartonCloudWriteRefused as PkgRefused

    assert PkgTimeout is CartonCloudTimeout
    assert PkgRefused is CartonCloudWriteRefused
