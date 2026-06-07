"""Regression guard for the read-only seatbelt (AUDIT R5).

The single non-negotiable in CLAUDE.md is: the CartonCloud client must not
mutate production data unless writes are *explicitly* enabled. CartonCloud
shares a backend with SAP-B1; an accidental write is a real-world incident,
not a flaky test. These tests lock that gate in place.

They run fully offline: a fake transport stands in for httpx so we never
touch the network, and a pre-seeded token bypasses OAuth.
"""
from __future__ import annotations

import time

import httpx
import pytest

from cc_client.client import (
    CartonCloudClient,
    CartonCloudError,
    _Token,
)

WRITE_METHODS = ["POST", "PUT", "PATCH", "DELETE"]


class _FakeTransport:
    """Records the last request and returns a canned httpx.Response.

    Substituted for ``client._http`` so no real I/O happens. ``response``
    may be a callable ``(method, url, **kw) -> httpx.Response`` or a static
    Response reused for every call.
    """

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None):
        self.calls.append(
            {"method": method, "url": url, "params": params,
             "json": json, "headers": headers}
        )
        resp = self._response
        if callable(resp):
            resp = resp(method, url, params=params, json=json, headers=headers)
        # httpx requires a request attached for .json()/.is_success access.
        resp.request = httpx.Request(method, url)
        return resp

    def close(self):  # pragma: no cover - parity with httpx.Client
        pass


def _client(write_enabled: bool = False) -> CartonCloudClient:
    c = CartonCloudClient(
        client_id="id",
        client_secret="secret",
        tenant_id="tenant",
        write_enabled=write_enabled,
    )
    # Pre-seed a non-expired token so _ensure_token never hits the network.
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def _ok_json(payload):
    return lambda *a, **k: httpx.Response(200, json=payload)


# ---------- the gate itself ----------

@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_methods_blocked_when_disabled(method):
    """Every non-GET verb must raise *before* any network call."""
    c = _client(write_enabled=False)
    # Fail loudly if the guard lets us reach the transport.
    c._http = _FakeTransport(_ok_json({"should": "not reach"}))

    with pytest.raises(CartonCloudError) as exc:
        c._request(method, "/anything", json={"x": 1})

    assert "write operations disabled" in str(exc.value)
    # The guard must short-circuit: transport never invoked.
    assert c._http.calls == []


def test_write_methods_blocked_is_case_insensitive():
    """Lowercase verbs must not sneak past the upper() check."""
    c = _client(write_enabled=False)
    c._http = _FakeTransport(_ok_json({}))
    with pytest.raises(CartonCloudError):
        c._request("post", "/x", json={})
    assert c._http.calls == []


def test_get_allowed_when_disabled():
    """Reads are always permitted, even with writes off."""
    c = _client(write_enabled=False)
    c._http = _FakeTransport(_ok_json({"ok": True}))

    out = c.get("/products", params={"page": 1})

    assert out == {"ok": True}
    assert len(c._http.calls) == 1
    assert c._http.calls[0]["method"] == "GET"


@pytest.mark.parametrize("method", WRITE_METHODS)
def test_write_methods_allowed_when_enabled(method):
    """With the seatbelt off, writes pass the guard and hit transport."""
    c = _client(write_enabled=True)
    c._http = _FakeTransport(_ok_json({"done": True}))

    r = c._request(method, "/things", json={"x": 1})

    assert r.json() == {"done": True}
    assert c._http.calls[0]["method"] == method


# ---------- the default (the thing most likely to regress) ----------

def test_write_disabled_by_default():
    """A client built with no write flag is read-only — the safe default."""
    c = CartonCloudClient(client_id="id", client_secret="s", tenant_id="t")
    assert c.write_enabled is False


def test_constructor_rejects_missing_credentials():
    """No silent client with blank creds — fail fast."""
    with pytest.raises(ValueError):
        CartonCloudClient(client_id="", client_secret="s", tenant_id="t")


# ---------- from_env parsing of CC_WRITE_ENABLED ----------

@pytest.mark.parametrize(
    "env_val, expected",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("false", False),
        ("1", False),      # only the literal string "true" enables writes
        ("yes", False),
        ("", False),
        (None, False),     # unset
    ],
)
def test_from_env_write_enabled_parsing(monkeypatch, env_val, expected):
    monkeypatch.setenv("CC_CLIENT_ID", "id")
    monkeypatch.setenv("CC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("CC_TENANT_ID", "tenant")
    if env_val is None:
        monkeypatch.delenv("CC_WRITE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("CC_WRITE_ENABLED", env_val)

    c = CartonCloudClient.from_env()
    assert c.write_enabled is expected


# ---------- post_search: a read that uses POST ----------

def test_post_search_restores_write_flag_on_success():
    """post_search flips write_enabled internally but must restore it."""
    c = _client(write_enabled=False)
    # Empty list => generator returns on first page.
    c._http = _FakeTransport(_ok_json([]))

    list(c.post_search("/orders/search", body={"q": 1}))

    assert c.write_enabled is False
    # It really did issue a POST (the read-via-POST pattern).
    assert c._http.calls and c._http.calls[0]["method"] == "POST"


def test_post_search_restores_write_flag_on_error():
    """Even if the request explodes mid-stream, the seatbelt is refastened."""
    c = _client(write_enabled=False)

    def boom(*a, **k):
        raise RuntimeError("transport blew up")

    c._http = _FakeTransport(boom)

    with pytest.raises(RuntimeError):
        list(c.post_search("/orders/search", body={"q": 1}))

    assert c.write_enabled is False
