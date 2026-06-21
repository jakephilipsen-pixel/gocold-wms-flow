"""M-DIMS-2 — dims-shadow approve handler.

The first write *surface*. Shadow mode: read the product's current dims, compute the
diff against the captured local dims, require approval, and run the FULL spine chain —
but inject a *recorder* as the final mutate fn so nothing is written. The whole
production path executes; only the final function pointer is stubbed.

The design contract (WRITE_ENABLEMENT_PLAN §3.1): the approve handler always composes

    rate-limit (W5) → customer-guard (W3) → authz (W2) → idempotent_mutate (W4)

and the ONLY difference between shadow (M-DIMS-2) and live (M-DIMS-3) is the mutate fn
injected into `idempotent_mutate(do_mutate=…)` — a `shadow_mutate_fn` here vs the real
`_mutate` at M-DIMS-3, with no surface rebuild.

Two non-negotiables under test:
  1. **The defining assertion** — a full approve in shadow calls `_mutate` ZERO times,
     and the recorder fires instead. That licenses M-DIMS-3 being a one-value flip.
  2. **Gates engage in shadow** — a non-allow-listed target is refused even though
     nothing writes (the guard isn't bypassed just because the mutate is stubbed).

The current-dims GET is the one real, read-only CC interaction in shadow; it must not
flip `write_enabled` (W4 discipline). Fully offline here: a fake transport stands in
for httpx and a pre-seeded token bypasses OAuth. No real CC write.
"""
from __future__ import annotations

import logging
import time

import httpx
import pytest

from dims_write.approve import (
    approve_dims_write,
    shadow_mutate_fn,
    read_product_for_dims,
    build_dims_patch,
    DimsApproveResult,
    DIM_FIELDS,
)
from cc_client.client import CartonCloudClient, _Token
from cc_client import (
    WriteConfig,
    SANDBOX_CUSTOMER_ID,
    MutateRateLimiter,
    ObjectLockRegistry,
    CartonCloudCustomerNotAllowed,
    CartonCloudWriteAuthFailed,
    CartonCloudWriteAuthNotConfigured,
    CartonCloudWriteRateLimited,
)

# Declared here (not in the module) so a test failure is the alarm if the live id ever
# leaks into the surface — same leak-alarm discipline as W0/W3.
LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"

SECRET = "shadow-approval-secret"


class FakeClock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class FakeProductTransport:
    """Returns a canned product on GET; ok on anything else. Records every call."""

    def __init__(self, product: dict):
        self.product = product
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "json": json, "headers": headers or {}})
        if method == "GET":
            return httpx.Response(200, json=self.product)
        return httpx.Response(200, json={"ok": True})

    @property
    def methods(self) -> list[str]:
        return [c["method"] for c in self.calls]


UOM = "EA"


def _sandbox_product(*, customer_id=SANDBOX_CUSTOMER_ID, uom=UOM, length=100, width=50, height=30, weight=12):
    # Dims hang off the default UoM (api-docs.cartoncloud.com), not the top level.
    return {
        "id": "p1",
        "customer": {"id": customer_id},
        "details": {"active": True},
        "references": {"code": "s-FROZEN-PEAS"},
        "defaultUnitOfMeasure": uom,
        "unitOfMeasures": {
            uom: {"baseQty": 1, "length": length, "width": width, "height": height, "weight": weight},
        },
    }


def _expected_record(diff, *, product_id="p1", uom=UOM):
    """The shape shadow_mutate_fn records — built via the same helper live uses."""
    path, ops, _ = build_dims_patch(product_id, uom, diff)
    return {"product_id": product_id, "uom": uom, "path": path, "ops": ops, "diff": diff}


def _client(*, write_enabled: bool = False) -> CartonCloudClient:
    c = CartonCloudClient(
        client_id="id",
        client_secret="sec",
        tenant_id="TENANT",
        base_url="https://cc.example",
        write_enabled=write_enabled,
    )
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def _spy_mutate(client) -> list:
    """Replace client._mutate with a counting spy; return the calls list."""
    calls: list = []
    real = client._mutate

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    client._mutate = spy
    return calls


def _cfg(*, allowlist=None, secret=SECRET) -> WriteConfig:
    return WriteConfig(
        write_enabled=True,
        write_secret=secret,
        customer_allowlist=allowlist if allowlist is not None else frozenset({SANDBOX_CUSTOMER_ID}),
    )


def _fresh_limiter() -> MutateRateLimiter:
    return MutateRateLimiter(now=FakeClock())


# ---------- THE DEFINING ASSERTION ----------

def test_shadow_approve_runs_full_chain_but_never_calls_mutate():
    # Drive a full approve through the real chain; _mutate must be called ZERO times
    # and the recorder must fire instead. This is what licenses M-DIMS-3 being a flip.
    client = _client()
    transport = FakeProductTransport(_sandbox_product(length=100))
    client._http = transport
    mutate_calls = _spy_mutate(client)

    recorder = shadow_mutate_fn("p1", UOM)
    result = approve_dims_write(
        "p1",
        client=client,
        config=_cfg(),
        desired_dims={"length": 120, "width": 50, "height": 30, "weight": 12},
        mutate_fn=recorder,
        rate_limiter=_fresh_limiter(),
        approval_token=SECRET,
    )

    assert mutate_calls == [], "_mutate must NEVER be called in shadow mode"
    assert "PATCH" not in transport.methods, "no PATCH may reach the transport"
    assert result.no_op is False, "a real diff must drive the recorder"
    assert recorder.records == [_expected_record({"length": 120})], (
        "the recorder fired with the would-PATCH diff"
    )
    assert result.diff == {"length": 120}


# ---------- gates engage in shadow ----------

def test_non_allowlisted_target_refused_in_shadow():
    # The customer-guard refuses a live-Forage target EVEN in shadow, where nothing
    # writes. A gate that only engaged in live mode would go unexercised by the soak.
    client = _client()
    transport = FakeProductTransport(_sandbox_product(customer_id=LIVE_FORAGE_CUSTOMER_ID, length=100))
    client._http = transport
    mutate_calls = _spy_mutate(client)
    recorder = shadow_mutate_fn("p1", UOM)

    with pytest.raises(CartonCloudCustomerNotAllowed):
        approve_dims_write(
            "p1",
            client=client,
            config=_cfg(),
            desired_dims={"length": 120},
            mutate_fn=recorder,
            rate_limiter=_fresh_limiter(),
            approval_token=SECRET,
        )

    assert recorder.records == [], "guard refused → recorder must not fire"
    assert mutate_calls == []
    assert "PATCH" not in transport.methods


def test_rate_limit_is_composed_first():
    # An exhausted limiter refuses BEFORE the read happens (rate-limit precedes the
    # GET in the chain order).
    client = _client()
    transport = FakeProductTransport(_sandbox_product())
    client._http = transport
    recorder = shadow_mutate_fn("p1", UOM)

    limiter = MutateRateLimiter(per_minute=1, now=FakeClock())
    # spend the single token on this endpoint
    limiter.check("/warehouse-products/{id}")

    with pytest.raises(CartonCloudWriteRateLimited):
        approve_dims_write(
            "p1",
            client=client,
            config=_cfg(),
            desired_dims={"length": 120},
            mutate_fn=recorder,
            rate_limiter=limiter,
            approval_token=SECRET,
        )

    assert transport.calls == [], "rate-limit must refuse before the read GET"
    assert recorder.records == []


def test_customer_guard_precedes_authz():
    # Order pin: a target that is BOTH non-allow-listed AND carries a wrong token must
    # raise the GUARD error (customer-guard runs before authz in the chain). If authz
    # ran first this would raise CartonCloudWriteAuthFailed instead.
    client = _client()
    client._http = FakeProductTransport(_sandbox_product(customer_id=LIVE_FORAGE_CUSTOMER_ID))
    recorder = shadow_mutate_fn("p1", UOM)

    with pytest.raises(CartonCloudCustomerNotAllowed):
        approve_dims_write(
            "p1",
            client=client,
            config=_cfg(),
            desired_dims={"length": 120},
            mutate_fn=recorder,
            rate_limiter=_fresh_limiter(),
            approval_token="wrong-token",
        )
    assert recorder.records == []


def test_authz_refuses_wrong_token():
    client = _client()
    client._http = FakeProductTransport(_sandbox_product())
    mutate_calls = _spy_mutate(client)
    recorder = shadow_mutate_fn("p1", UOM)

    with pytest.raises(CartonCloudWriteAuthFailed):
        approve_dims_write(
            "p1",
            client=client,
            config=_cfg(),
            desired_dims={"length": 120},
            mutate_fn=recorder,
            rate_limiter=_fresh_limiter(),
            approval_token="wrong-token",
        )
    assert recorder.records == []
    assert mutate_calls == []


def test_authz_refuses_when_secret_unconfigured():
    client = _client()
    client._http = FakeProductTransport(_sandbox_product())
    recorder = shadow_mutate_fn("p1", UOM)

    with pytest.raises(CartonCloudWriteAuthNotConfigured):
        approve_dims_write(
            "p1",
            client=client,
            config=_cfg(secret=None),  # no write secret → fail-closed
            desired_dims={"length": 120},
            mutate_fn=recorder,
            rate_limiter=_fresh_limiter(),
            approval_token=SECRET,
        )
    assert recorder.records == []


# ---------- the read is real + read-only ----------

@pytest.mark.parametrize("write_enabled", [False, True])
def test_read_path_does_not_flip_write_enabled(write_enabled):
    # The current-dims GET goes through the normal read path; the whole shadow approve
    # must leave write_enabled exactly as it was (W4 discipline). Shadow also works
    # regardless of write_enabled — it never needs write capability.
    client = _client(write_enabled=write_enabled)
    transport = FakeProductTransport(_sandbox_product(length=100))
    client._http = transport
    recorder = shadow_mutate_fn("p1", UOM)

    result = approve_dims_write(
        "p1",
        client=client,
        config=_cfg(),
        desired_dims={"length": 120},
        mutate_fn=recorder,
        rate_limiter=_fresh_limiter(),
        approval_token=SECRET,
    )

    assert client.write_enabled is write_enabled, "the read must not flip write_enabled"
    assert "GET" in transport.methods, "the current-dims read must happen"
    assert recorder.records == [_expected_record({"length": 120})]


# ---------- read-before-write no-op ----------

def test_no_op_when_dims_already_match():
    client = _client()
    client._http = FakeProductTransport(_sandbox_product(length=100, width=50, height=30, weight=12))
    mutate_calls = _spy_mutate(client)
    recorder = shadow_mutate_fn("p1", UOM)

    result = approve_dims_write(
        "p1",
        client=client,
        config=_cfg(),
        desired_dims={"length": 100, "width": 50, "height": 30, "weight": 12},
        mutate_fn=recorder,
        rate_limiter=_fresh_limiter(),
        approval_token=SECRET,
    )

    assert result.no_op is True
    assert result.diff == {}
    assert recorder.records == [], "an empty diff must not even fire the recorder"
    assert mutate_calls == []


# ---------- diff is over dim fields only ----------

def test_diff_is_over_dim_fields_only():
    client = _client()
    client._http = FakeProductTransport(_sandbox_product(length=100, width=50, height=30, weight=12))
    recorder = shadow_mutate_fn("p1", UOM)

    result = approve_dims_write(
        "p1",
        client=client,
        config=_cfg(),
        # extra non-dim keys must be ignored; only height changed among dims
        desired_dims={"length": 100, "width": 50, "height": 45, "weight": 12, "name": "ignore me"},
        mutate_fn=recorder,
        rate_limiter=_fresh_limiter(),
        approval_token=SECRET,
    )

    assert result.diff == {"height": 45}
    assert recorder.records == [_expected_record({"height": 45})]
    assert set(DIM_FIELDS) == {"length", "width", "height", "weight"}


# ---------- the seam is one value: handler treats mutate_fn opaquely ----------

def test_handler_treats_mutate_fn_opaquely():
    # Inject an arbitrary mutate fn (not the recorder); the handler calls it once with
    # the diff and returns its result. This is why swapping recorder↔_mutate at
    # M-DIMS-3 is a single-value change — the handler is agnostic to the mutate fn.
    client = _client()
    client._http = FakeProductTransport(_sandbox_product(length=100))
    seen: list = []

    def custom_fn(diff):
        seen.append(diff)
        return "custom-return"

    result = approve_dims_write(
        "p1",
        client=client,
        config=_cfg(),
        desired_dims={"length": 120},
        mutate_fn=custom_fn,
        rate_limiter=_fresh_limiter(),
        approval_token=SECRET,
    )

    assert seen == [{"length": 120}], "handler calls the injected fn once with the diff"
    assert result.response == "custom-return"


# ---------- result shape ----------

def test_result_shape():
    client = _client()
    client._http = FakeProductTransport(_sandbox_product(customer_id=SANDBOX_CUSTOMER_ID, length=100))
    result = approve_dims_write(
        "p1",
        client=client,
        config=_cfg(),
        desired_dims={"length": 120},
        mutate_fn=shadow_mutate_fn("p1", UOM),
        rate_limiter=_fresh_limiter(),
        approval_token=SECRET,
    )
    assert isinstance(result, DimsApproveResult)
    assert result.product_id == "p1"
    assert result.customer_id == SANDBOX_CUSTOMER_ID
    assert result.diff == {"length": 120}
    assert result.no_op is False


# ---------- shadow recorder logs the would-PATCH ----------

def test_shadow_recorder_logs_would_patch(caplog):
    recorder = shadow_mutate_fn("p1", UOM)
    with caplog.at_level(logging.INFO, logger="dims_write.approve"):
        recorder({"length": 120})
    assert "would PATCH" in caplog.text
    assert "/warehouse-products/p1" in caplog.text
    assert "/unitOfMeasures/EA/length" in caplog.text


# ---------- read adapter resolves customer id + dims ----------

def test_read_product_for_dims_extracts_customer_and_dims():
    client = _client()
    client._http = FakeProductTransport(_sandbox_product(customer_id="cust-x", length=100, width=50, height=30, weight=12))
    read = read_product_for_dims(client, "p1")
    assert read.customer_id == "cust-x"
    assert read.uom == UOM, "default UoM is surfaced for the PATCH target"
    assert read.current_dims == {"length": 100, "width": 50, "height": 30, "weight": 12}
    assert client.write_enabled is False  # read-only
    # the read must run under v8 — that's the schema where L/W/H exist on the UoM
    get_call = next(c for c in client._http.calls if c["method"] == "GET")
    assert get_call["headers"].get("Accept-Version") == "8"


# ---------- package export ----------

def test_exported_from_package():
    from dims_write import (
        approve_dims_write as pkg_approve,
        shadow_mutate_fn as pkg_recorder,
        DimsApproveResult as PkgResult,
    )

    assert pkg_approve is approve_dims_write
    assert pkg_recorder is shadow_mutate_fn
    assert PkgResult is DimsApproveResult
