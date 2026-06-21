"""M-DIMS-4 — sandbox bulk dims loop (soak): the batch logic, CC-mocked.

Generalises the single M-DIMS-3 write to all active sandbox SKUs, reusing the exact
write+verify path (`write_and_verify` → `build_dims_patch` → `_mutate` → read-back).
Safety posture under test (Jake's decisions):

  - ONE batch-level hard stop (no per-SKU prompting); no `go` → zero writes.
  - FAIL-FAST: the first SKU whose write OR read-back verify fails stops the whole run;
    earlier SKUs stay written (known-good), later SKUs are untouched. No rollback.
  - IDEMPOTENT re-run: a second run no-ops every already-correct SKU (zero PATCHes) —
    this is what makes fail-fast safe (re-run after a fix resumes cleanly).
  - rate-limited through W5, paced so a sustained batch never trips the limiter.
  - `assert_sandbox_only` still refuses a non-sandbox allow-list.

CC is mocked; the real soak is a deliberate human run (`scripts/run_dims_bulk_sandbox.py`).
"""
from __future__ import annotations

import time

import httpx
import pytest

from dims_write.bulk import build_bulk_plan, run_sandbox_bulk, BulkPlan, BulkReport
from dims_write.roundtrip import SandboxCandidate, DimsRoundtripRefused
from cc_client.client import CartonCloudClient, _Token
from cc_client import WriteConfig, SANDBOX_CUSTOMER_ID, MutateRateLimiter

# Leak-alarm: the live id is declared here, never in the module.
LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"
SECRET = "bulk-approval-secret"
UOM = "EA"


class Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


class BulkTransport:
    """Many warehouse-products keyed by id. GET returns the product; PATCH applies the
    JSON-Patch ops to the addressed product's UoM (so read-back reflects them) UNLESS
    the product's code is in ``fail_codes`` — then the PATCH 200s but does NOT persist,
    driving a read-back mismatch. Records every call."""

    def __init__(self, products: dict, *, persist: bool = True, fail_codes=()):
        self.products = {pid: dict(p) for pid, p in products.items()}
        self.persist = persist
        self.fail_codes = set(fail_codes)
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        pid = url.rstrip("/").split("/")[-1]
        self.calls.append({"method": method, "url": url, "json": json, "pid": pid})
        prod = self.products.get(pid, {})
        if method == "GET":
            return httpx.Response(200, json=dict(prod))
        if method == "PATCH":
            code = (prod.get("references") or {}).get("code")
            if self.persist and code not in self.fail_codes:
                for op in json:
                    parts = op["path"].strip("/").split("/")
                    target = prod
                    for p in parts[:-1]:
                        target = target.setdefault(p, {})
                    target[parts[-1]] = op["value"]
            return httpx.Response(200, json=dict(prod))
        return httpx.Response(200, json={"ok": True})

    @property
    def patches(self) -> list[dict]:
        return [c for c in self.calls if c["method"] == "PATCH"]


def _product(pid, code, *, customer_id=SANDBOX_CUSTOMER_ID, uom=UOM,
             length=None, width=None, height=None, weight=0):
    # Dims are OMITTED from the UoM when unset (real GET behaviour), present when given.
    uom_obj = {"baseQty": 1, "weight": weight, "barcode": code}
    if length is not None:
        uom_obj["length"] = length
    if width is not None:
        uom_obj["width"] = width
    if height is not None:
        uom_obj["height"] = height
    return {
        "id": pid,
        "customer": {"id": customer_id},
        "details": {"active": True},
        "references": {"code": code},
        "defaultUnitOfMeasure": uom,
        "unitOfMeasures": {uom: uom_obj},
    }


def _client(*, write_enabled=True):
    c = CartonCloudClient(client_id="id", client_secret="sec", tenant_id="TENANT",
                          base_url="https://cc.example", write_enabled=write_enabled)
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def _cfg(*, allowlist=None, write_enabled=True, secret=SECRET):
    return WriteConfig(
        write_enabled=write_enabled, write_secret=secret,
        customer_allowlist=allowlist if allowlist is not None else frozenset({SANDBOX_CUSTOMER_ID}),
    )


def _spy_check(limiter):
    """Count limiter.check calls (prove the batch is rate-limited, not bypassed)."""
    calls = []
    real = limiter.check

    def spy(ep):
        calls.append(ep)
        return real(ep)

    limiter.check = spy
    return calls


def _noop_run_kwargs(desired, cands):
    return dict(
        config=_cfg(), desired_lookup=lambda c: desired.get(c), approval_token=SECRET,
        confirm=lambda plan: True, candidates=cands, sleep=lambda s: None, pace_seconds=0,
    )


# ---------- happy path: all-with-diffs write + verify, paced through the limiter ----------

def test_happy_path_writes_all_with_diffs_paced_through_limiter():
    products = {
        "p1": _product("p1", "sRK-001"),
        "p2": _product("p2", "sRK-002"),
        "p3": _product("p3", "sRK-003"),
    }
    client = _client()
    client._http = BulkTransport(products)
    desired = {
        "sRK-001": {"length": 100, "width": 50, "height": 30, "weight": 1.0},
        "sRK-002": {"length": 200, "width": 60, "height": 40, "weight": 2.0},
        "sRK-003": {"length": 300, "width": 70, "height": 50, "weight": 3.0},
    }
    cands = [SandboxCandidate("p1", "sRK-001"), SandboxCandidate("p2", "sRK-002"),
             SandboxCandidate("p3", "sRK-003")]

    # Tiny 1/min limiter + a clock that PACING advances → proves pacing lets a sustained
    # batch through without tripping the bucket (each pace refills a token). Without the
    # paces, the 2nd write would raise CartonCloudWriteRateLimited.
    clock = Clock()
    limiter = MutateRateLimiter(per_minute=1, now=clock)
    checks = _spy_check(limiter)
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        clock.advance(s)

    seen_plan = []
    report = run_sandbox_bulk(
        client=client, config=_cfg(), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: (seen_plan.append(plan) or True),
        candidates=cands, rate_limiter=limiter, sleep=sleep, pace_seconds=60,
    )

    assert report.failed is None and report.aborted is False
    assert {w["code"] for w in report.written} == {"sRK-001", "sRK-002", "sRK-003"}
    assert report.written[0]["after"]["length"] == 100
    assert len(checks) == 3, "limiter consulted once per write — not bypassed"
    assert len(sleeps) >= 2, "sustained writes are paced between SKUs"
    # the single batch hard stop saw the real plan
    assert len(seen_plan[0].to_write) == 3
    assert seen_plan[0].endpoint == "/warehouse-products/{id}"
    assert seen_plan[0].write_enabled is True
    assert seen_plan[0].allowlist_is_sandbox_only is True


# ---------- idempotent re-run: the property that makes fail-fast safe ----------

def test_idempotent_rerun_no_ops_every_sku_zero_patches():
    products = {"p1": _product("p1", "sRK-001"), "p2": _product("p2", "sRK-002")}
    transport = BulkTransport(products)
    client = _client()
    client._http = transport
    desired = {"sRK-001": {"length": 100, "width": 50, "height": 30, "weight": 1.0},
               "sRK-002": {"length": 200, "width": 60, "height": 40, "weight": 2.0}}
    cands = [SandboxCandidate("p1", "sRK-001"), SandboxCandidate("p2", "sRK-002")]

    r1 = run_sandbox_bulk(client=client, **_noop_run_kwargs(desired, cands))
    assert len(r1.written) == 2
    patches_after_first = len(transport.patches)
    assert patches_after_first == 2

    # second run: everything already matches → all no-op, ZERO new PATCHes
    r2 = run_sandbox_bulk(client=client, **_noop_run_kwargs(desired, cands))
    assert r2.written == []
    assert {n["code"] for n in r2.no_ops} == {"sRK-001", "sRK-002"}
    assert len(transport.patches) == patches_after_first, "the clean re-run issues no new PATCH"


# ---------- fail-fast: stop at first failure, earlier known-good, later untouched ----------

def test_fail_fast_stops_at_first_mismatch_leaves_rest_untouched():
    products = {f"p{i}": _product(f"p{i}", f"sRK-00{i}") for i in range(1, 5)}  # p1..p4
    transport = BulkTransport(products, fail_codes={"sRK-002"})  # SKU 2's PATCH won't persist
    client = _client()
    client._http = transport
    desired = {f"sRK-00{i}": {"length": 100 * i, "width": 50, "height": 30, "weight": 1.0}
               for i in range(1, 5)}
    cands = [SandboxCandidate(f"p{i}", f"sRK-00{i}") for i in range(1, 5)]

    report = run_sandbox_bulk(client=client, **_noop_run_kwargs(desired, cands))

    assert report.failed is not None
    assert report.failed["code"] == "sRK-002"
    assert [w["code"] for w in report.written] == ["sRK-001"], "only SKU 1 is known-good"
    assert report.untouched_after_failure == ["sRK-003", "sRK-004"]
    assert len(transport.patches) == 2, "SKU 1 (ok) + SKU 2 (attempted); 3 & 4 never attempted"


# ---------- NaN weight: write L/W/H, omit weight, do NOT fail the SKU ----------

def test_nan_weight_sku_writes_lwh_omits_weight_and_succeeds():
    products = {"p1": _product("p1", "sRK-001")}
    transport = BulkTransport(products)
    client = _client()
    client._http = transport
    desired = {"sRK-001": {"length": 100, "width": 50, "height": 30, "weight": float("nan")}}
    cands = [SandboxCandidate("p1", "sRK-001")]

    report = run_sandbox_bulk(client=client, **_noop_run_kwargs(desired, cands))

    assert report.failed is None
    assert [w["code"] for w in report.written] == ["sRK-001"]
    ops = transport.patches[0]["json"]
    paths = {op["path"] for op in ops}
    assert paths == {"/unitOfMeasures/EA/length", "/unitOfMeasures/EA/width",
                     "/unitOfMeasures/EA/height"}, "L/W/H written, NaN weight dropped"


# ---------- batch hard stop: no go → zero writes ----------

def test_batch_hard_stop_no_go_writes_nothing():
    products = {"p1": _product("p1", "sRK-001"), "p2": _product("p2", "sRK-002")}
    transport = BulkTransport(products)
    client = _client()
    client._http = transport
    desired = {"sRK-001": {"length": 100, "width": 50, "height": 30, "weight": 1.0},
               "sRK-002": {"length": 200, "width": 60, "height": 40, "weight": 2.0}}
    cands = [SandboxCandidate("p1", "sRK-001"), SandboxCandidate("p2", "sRK-002")]

    report = run_sandbox_bulk(
        client=client, config=_cfg(), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: False,  # human declines the batch
        candidates=cands, sleep=lambda s: None, pace_seconds=0,
    )
    assert report.aborted is True
    assert report.written == []
    assert transport.patches == [], "no PATCH may fire without the batch go"


# ---------- sandbox-only refusal still holds for the batch ----------

def test_refuses_to_start_if_live_id_in_allowlist():
    client = _client()
    client._http = BulkTransport({"p1": _product("p1", "sRK-001")})
    with pytest.raises(DimsRoundtripRefused):
        run_sandbox_bulk(
            client=client,
            config=_cfg(allowlist=frozenset({SANDBOX_CUSTOMER_ID, LIVE_FORAGE_CUSTOMER_ID})),
            desired_lookup=lambda c: {"length": 1, "width": 1, "height": 1},
            approval_token=SECRET, confirm=lambda plan: True,
            candidates=[SandboxCandidate("p1", "sRK-001")],
            sleep=lambda s: None, pace_seconds=0,
        )


# ---------- plan buckets: writable / no-op / skipped ----------

def test_plan_buckets_writable_no_op_and_skipped():
    products = {
        "pw": _product("pw", "sRK-WRITE"),  # empty dims → writable
        "pn": _product("pn", "sRK-NOOP", length=100, width=50, height=30, weight=1.0),  # matches
        "ps": _product("ps", "sRK-SKIP"),  # no captured dims → skipped
    }
    client = _client()
    client._http = BulkTransport(products)
    desired = {
        "sRK-WRITE": {"length": 100, "width": 50, "height": 30, "weight": 1.0},
        "sRK-NOOP": {"length": 100, "width": 50, "height": 30, "weight": 1.0},
        # sRK-SKIP intentionally absent
    }
    cands = [SandboxCandidate("pw", "sRK-WRITE"), SandboxCandidate("pn", "sRK-NOOP"),
             SandboxCandidate("ps", "sRK-SKIP")]

    plan = build_bulk_plan(client, cands, lambda c: desired.get(c), config=_cfg())

    assert [i.code for i in plan.to_write] == ["sRK-WRITE"]
    assert {n["code"] for n in plan.no_ops} == {"sRK-NOOP"}
    assert {s["code"] for s in plan.skipped} == {"sRK-SKIP"}
