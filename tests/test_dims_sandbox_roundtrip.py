"""M-DIMS-3 — first real CC write (sandbox only): the round-trip logic, CC-mocked.

M-DIMS-3 flips the M-DIMS-2 injection seam from `shadow_mutate_fn` to the real
`_mutate`. The handler, gate chain, and M-DIMS-2 tests are unchanged — so these tests
cover ONLY the new logic (per the build instruction, don't duplicate the gate tests):

  - the live mutate fn calls `_mutate` exactly once with the diff;
  - the run refuses to start unless the allow-list is exactly sandbox-only (live id
    present → refuse);
  - target selection skips an empty-diff SKU (it proves nothing) and picks one with a
    real, non-empty diff;
  - read-back mismatch is a hard failure (raises), not a warning.

CC is mocked here — the real write happens only in the deliberate, human-confirmed run
(`scripts/run_dims_sandbox_roundtrip.py`), never in tests.
"""
from __future__ import annotations

import time

import httpx
import pytest

from dims_write.roundtrip import (
    live_mutate_fn,
    assert_sandbox_only,
    select_writable_sandbox_sku,
    run_sandbox_roundtrip,
    SandboxCandidate,
    HardStopInfo,
    DimsRoundtripRefused,
    NoWritableSandboxSku,
    DimsReadBackMismatch,
)
from cc_client.client import CartonCloudClient, CartonCloudWriteRefused, _Token
from cc_client import WriteConfig, SANDBOX_CUSTOMER_ID

# Leak-alarm: the live id is declared here, never in the module.
LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"

SECRET = "live-approval-secret"


class StatefulProductTransport:
    """GET returns current product; PATCH (optionally) persists the new dims so a
    later GET reflects them. Records every call. `freeze_reads=True` makes the PATCH
    NOT persist — to drive a read-back mismatch."""

    def __init__(self, product: dict, *, persist_patch: bool = True):
        self.product = dict(product)
        self.persist_patch = persist_patch
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "json": json})
        if method == "GET":
            return httpx.Response(200, json=dict(self.product))
        if method == "PATCH":
            if self.persist_patch and json:
                self.product.update(json)
            return httpx.Response(200, json=dict(self.product))
        return httpx.Response(200, json={"ok": True})

    @property
    def methods(self) -> list[str]:
        return [c["method"] for c in self.calls]


def _sandbox_product(*, customer_id=SANDBOX_CUSTOMER_ID, code="s-FROZEN-PEAS",
                     length=100, width=50, height=30, weight=12):
    return {
        "id": "p1",
        "customer": {"id": customer_id},
        "details": {"active": True},
        "references": {"code": code},
        "length": length, "width": width, "height": height, "weight": weight,
    }


def _client(*, write_enabled: bool = True) -> CartonCloudClient:
    c = CartonCloudClient(
        client_id="id", client_secret="sec", tenant_id="TENANT",
        base_url="https://cc.example", write_enabled=write_enabled,
    )
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def _cfg(*, allowlist=None, write_enabled=True, secret=SECRET) -> WriteConfig:
    return WriteConfig(
        write_enabled=write_enabled,
        write_secret=secret,
        customer_allowlist=allowlist if allowlist is not None else frozenset({SANDBOX_CUSTOMER_ID}),
    )


# ---------- the live mutate fn: calls _mutate exactly once with the diff ----------

def test_live_mutate_fn_calls_mutate_once_with_diff():
    client = _client(write_enabled=True)
    transport = StatefulProductTransport(_sandbox_product())
    client._http = transport

    fn = live_mutate_fn(client, "p1")
    resp = fn({"length": 120})

    patches = [c for c in transport.calls if c["method"] == "PATCH"]
    assert len(patches) == 1, "exactly one PATCH"
    assert patches[0]["json"] == {"length": 120}, "carries the diff verbatim"
    assert patches[0]["url"].endswith("/tenants/TENANT/products/p1")
    assert resp["length"] == 120


def test_live_mutate_fn_routes_through_the_gated_mutate():
    # Proves it goes through W1's double-gated _mutate: a write-disabled client refuses
    # (no raw PATCH leaks past the gate).
    client = _client(write_enabled=False)
    client._http = StatefulProductTransport(_sandbox_product())
    fn = live_mutate_fn(client, "p1")
    with pytest.raises(CartonCloudWriteRefused):
        fn({"length": 120})


# ---------- refuse to start unless allow-list is exactly sandbox-only ----------

def test_refuses_to_start_if_live_id_in_allowlist():
    cfg = _cfg(allowlist=frozenset({SANDBOX_CUSTOMER_ID, LIVE_FORAGE_CUSTOMER_ID}))
    with pytest.raises(DimsRoundtripRefused):
        assert_sandbox_only(cfg)


def test_refuses_to_start_if_allowlist_is_only_live():
    cfg = _cfg(allowlist=frozenset({LIVE_FORAGE_CUSTOMER_ID}))
    with pytest.raises(DimsRoundtripRefused):
        assert_sandbox_only(cfg)


def test_refuses_to_start_if_write_disabled():
    with pytest.raises(DimsRoundtripRefused):
        assert_sandbox_only(_cfg(write_enabled=False))


def test_refuses_to_start_if_secret_unconfigured():
    with pytest.raises(DimsRoundtripRefused):
        assert_sandbox_only(_cfg(secret=None))


def test_passes_when_sandbox_only_and_enabled_and_secret():
    # Exactly the sandbox singleton, enabled, secret set → no raise.
    assert assert_sandbox_only(_cfg()) is None


# ---------- target selection: skip empty-diff, pick a real diff ----------

def test_selection_skips_empty_diff_and_picks_real_diff():
    client = _client()
    # p-empty already matches desired → empty diff → must be skipped.
    # p-real differs → chosen.
    products = {
        "p-empty": _sandbox_product(code="s-EMPTY", length=100, width=50, height=30, weight=12),
        "p-real": _sandbox_product(code="s-REAL", length=100, width=50, height=30, weight=12),
    }

    def fake_get(path, **kw):
        pid = path.split("/")[-1]
        return products[pid]

    client.get = fake_get  # type: ignore[assignment]

    desired = {
        "s-EMPTY": {"length": 100, "width": 50, "height": 30, "weight": 12},  # identical
        "s-REAL": {"length": 140, "width": 50, "height": 30, "weight": 12},   # length differs
    }
    candidates = [
        SandboxCandidate(product_id="p-empty", code="s-EMPTY"),
        SandboxCandidate(product_id="p-real", code="s-REAL"),
    ]

    selection, skipped = select_writable_sandbox_sku(
        client, candidates, lambda code: desired.get(code)
    )
    assert selection is not None
    assert selection.product_id == "p-real"
    assert selection.diff == {"length": 140}
    assert any(s["code"] == "s-EMPTY" for s in skipped), "empty-diff SKU reported as skipped"


def test_selection_returns_none_when_no_sku_has_a_diff():
    client = _client()
    prod = _sandbox_product(code="s-ONLY", length=100, width=50, height=30, weight=12)
    client.get = lambda path, **kw: prod  # type: ignore[assignment]
    candidates = [SandboxCandidate(product_id="p1", code="s-ONLY")]
    selection, skipped = select_writable_sandbox_sku(
        client, candidates, lambda code: {"length": 100, "width": 50, "height": 30, "weight": 12}
    )
    assert selection is None
    assert skipped and skipped[0]["code"] == "s-ONLY"


def test_selection_skips_sku_with_no_captured_dims():
    client = _client()
    client.get = lambda path, **kw: _sandbox_product(code="s-X")  # type: ignore[assignment]
    candidates = [SandboxCandidate(product_id="p1", code="s-X")]
    selection, skipped = select_writable_sandbox_sku(client, candidates, lambda code: None)
    assert selection is None
    assert skipped[0]["reason"]


# ---------- the 3-step run: hard stop, PATCH, read-back verify ----------

def _desired_lookup(code):
    return {"length": 140, "width": 50, "height": 30, "weight": 12}


def _run(client, *, confirm, persist_patch=True, candidates=None):
    return run_sandbox_roundtrip(
        client=client,
        config=_cfg(),
        desired_lookup=_desired_lookup,
        approval_token=SECRET,
        confirm=confirm,
        candidates=candidates or [SandboxCandidate(product_id="p1", code="s-FROZEN-PEAS")],
    )


def test_hard_stop_no_confirm_fires_no_patch():
    client = _client(write_enabled=True)
    transport = StatefulProductTransport(_sandbox_product(length=100))
    client._http = transport

    report = _run(client, confirm=lambda info: False)  # human declines

    assert report.aborted is True
    assert report.written is False
    assert "PATCH" not in transport.methods, "no PATCH may fire without confirmation"


def test_confirm_receives_full_hard_stop_info():
    client = _client(write_enabled=True)
    client._http = StatefulProductTransport(_sandbox_product(length=100))
    seen: list[HardStopInfo] = []

    def confirm(info):
        seen.append(info)
        return False

    _run(client, confirm=confirm)
    info = seen[0]
    assert info.product_id == "p1"
    assert info.code == "s-FROZEN-PEAS"
    assert info.current_dims["length"] == 100
    assert info.desired_dims["length"] == 140
    assert info.diff == {"length": 140}
    assert info.verb == "PATCH"
    assert info.endpoint == "/products/p1"
    assert info.write_enabled is True
    assert info.allowlist_is_sandbox_only is True


def test_go_patches_once_and_verifies_read_back_landed():
    client = _client(write_enabled=True)
    transport = StatefulProductTransport(_sandbox_product(length=100), persist_patch=True)
    client._http = transport

    report = _run(client, confirm=lambda info: True)

    patches = [c for c in transport.calls if c["method"] == "PATCH"]
    assert len(patches) == 1, "exactly one real PATCH"
    assert patches[0]["json"] == {"length": 140}
    assert report.written is True
    assert report.aborted is False
    assert report.landed is True
    assert report.read_back_dims["length"] == 140, "read-back reflects the written value"


def test_read_back_mismatch_is_a_hard_failure():
    client = _client(write_enabled=True)
    # PATCH does NOT persist → the read-back still shows the old value → mismatch.
    transport = StatefulProductTransport(_sandbox_product(length=100), persist_patch=False)
    client._http = transport

    with pytest.raises(DimsReadBackMismatch):
        _run(client, confirm=lambda info: True)


def test_run_refuses_when_no_writable_sku():
    client = _client(write_enabled=True)
    client._http = StatefulProductTransport(_sandbox_product(length=140))  # already matches desired
    with pytest.raises(NoWritableSandboxSku):
        _run(client, confirm=lambda info: True)


def test_run_refuses_to_start_if_not_sandbox_only():
    client = _client(write_enabled=True)
    client._http = StatefulProductTransport(_sandbox_product(length=100))
    with pytest.raises(DimsRoundtripRefused):
        run_sandbox_roundtrip(
            client=client,
            config=_cfg(allowlist=frozenset({SANDBOX_CUSTOMER_ID, LIVE_FORAGE_CUSTOMER_ID})),
            desired_lookup=_desired_lookup,
            approval_token=SECRET,
            confirm=lambda info: True,
            candidates=[SandboxCandidate(product_id="p1", code="s-FROZEN-PEAS")],
        )


# ---------- package export ----------

def test_exported_from_package():
    from dims_write import (
        live_mutate_fn as pkg_live,
        run_sandbox_roundtrip as pkg_run,
        assert_sandbox_only as pkg_assert,
    )
    assert pkg_live is live_mutate_fn
    assert pkg_run is run_sandbox_roundtrip
    assert pkg_assert is assert_sandbox_only
