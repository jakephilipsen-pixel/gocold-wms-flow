"""M-DIMS-5c — bulk-write carton dims to the CT carton UoM: the engine, CC-mocked.

5c generalises the proven M-DIMS-4 bulk soak so it writes the captured CARTON/outer dims
to a SKU's **CT carton unit-of-measure** (not the each/default), for the active live Forage
SKUs that carry one. This exists because 5b found ~88 SKUs carry a carton UoM and a blind
"write to the default UoM" would mis-dimension the EACH on every one (the AE-2CB finding).

Reuse, don't fork (same discipline as 5b changing only target selection): the gate chain,
``write_and_verify``, read-back, fail-fast and W5 pacing are all unchanged. The ONLY new
logic is UoM selection — a resolver ``(product) -> uom_id | None`` that finds the UoM coded
``CT`` and returns its id. A SKU with no CT UoM is skipped and reported; there is NO
fall-through to the each/default UoM (that is the mistake 5c fixes) and no guessing at CTN.

Scope under test:
  - IN : the live Forage SKUs that have a CT carton UoM — write carton dims to the CT UoM.
  - OUT: the EA-only SKUs (each handled elsewhere) and the CTN/PLT no-EA SKUs (a different
         shape, deliberately deferred). Both must fall out cleanly as "skipped: no CT UoM".

CC is mocked; the live bulk run is Jake's deliberate, armed ``scripts/run_dims_ct_bulk.py`` —
never run here, never automatically.
"""
from __future__ import annotations

import time

import httpx
import pytest

from dims_write.bulk import resolve_ct_uom, resolve_default_uom
from dims_write.approve import read_product_for_dims, dims_for_uom, approve_dims_write
from dims_write.roundtrip import write_and_verify, DimsRoundtripRefused
from dims_write.bulk import build_bulk_plan, run_ct_bulk, format_ct_bulk_report, BulkReport
from dims_write.live_proving import LiveCandidate
from cc_client.client import CartonCloudClient, _Token
from cc_client import WriteConfig, SANDBOX_CUSTOMER_ID, MutateRateLimiter

# Leak-alarm: the live id is declared here in the test, never assumed by the module under test.
LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"
SECRET = "ct-approval-secret"


# ---------- fixtures: a v8 warehouse-product with one or more UoMs ----------

def _uom(*, code=None, length=None, width=None, height=None, weight=0, barcode="bc"):
    """A v8 unit-of-measure object. ``code`` is set only for the keyed-by-uuid shape;
    dims are OMITTED when unset (real GET behaviour for a freshly-captured SKU)."""
    obj = {"baseQty": 1, "weight": weight, "barcode": barcode}
    if code is not None:
        obj["code"] = code
    for k, v in (("length", length), ("width", width), ("height", height)):
        if v is not None:
            obj[k] = v
    return obj


def _product(pid, sku_code, *, uoms, default, customer_id=LIVE_FORAGE_CUSTOMER_ID):
    """A warehouse-product as read under Accept-Version 8: dims hang off unitOfMeasures.{uom}."""
    return {
        "id": pid,
        "customer": {"id": customer_id},
        "details": {"active": True},
        "references": {"code": sku_code},
        "defaultUnitOfMeasure": default,
        "unitOfMeasures": uoms,
    }


class CtTransport:
    """Warehouse-products keyed by id. GET returns the product; PATCH applies the JSON-Patch
    ops to the addressed UoM (so a UoM-aware read-back reflects them) UNLESS the product's code
    is in ``fail_codes`` — then the PATCH 200s but does NOT persist, driving a read-back
    mismatch. Records every call (incl. headers, to prove Accept-Version 8)."""

    def __init__(self, products, *, persist=True, fail_codes=()):
        self.products = {pid: dict(p) for pid, p in products.items()}
        self.persist = persist
        self.fail_codes = set(fail_codes)
        self.calls = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        pid = url.rstrip("/").split("/")[-1]
        self.calls.append({"method": method, "url": url, "json": json, "pid": pid, "headers": headers})
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
    def patches(self):
        return [c for c in self.calls if c["method"] == "PATCH"]


def _client(*, write_enabled=True):
    c = CartonCloudClient(client_id="id", client_secret="sec", tenant_id="TENANT",
                          base_url="https://cc.example", write_enabled=write_enabled)
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def _client_returning(raw):
    c = _client()
    c._http = CtTransport({raw["id"]: raw})
    return c


def _client_with(*raws, persist=True, fail_codes=()):
    c = _client()
    c._http = CtTransport({r["id"]: r for r in raws}, persist=persist, fail_codes=fail_codes)
    return c


def _cfg(*, allowlist=None, write_enabled=True, secret=SECRET, live_promotion=False):
    return WriteConfig(
        write_enabled=write_enabled, write_secret=secret,
        customer_allowlist=allowlist if allowlist is not None else frozenset({SANDBOX_CUSTOMER_ID}),
        live_promotion=live_promotion,
    )


# ============================================================================
# The resolver — the ONLY new logic. Find the UoM coded CT; return its id.
# ============================================================================

def test_resolve_ct_uom_returns_ct_key_when_uoms_are_keyed_by_code():
    # Shape A: unitOfMeasures keyed directly by the UoM code (EA/CT).
    raw = _product("p", "FP-1", uoms={"EA": _uom(), "CT": _uom(length=300)}, default="EA")
    assert resolve_ct_uom(raw) == "CT"


def test_resolve_ct_uom_returns_id_not_code_when_uoms_are_keyed_by_uuid():
    # Shape B: keyed by an opaque id, the code lives in the object. The resolver must return
    # the ID (the key the PATCH path uses), found BY the code — never a hardcoded "CT".
    raw = _product(
        "p", "FP-1",
        uoms={"u-ea": _uom(code="EA"), "u-ct": _uom(code="CT", length=300)},
        default="u-ea",
    )
    assert resolve_ct_uom(raw) == "u-ct"


def test_resolve_ct_uom_returns_none_when_each_only():
    raw = _product("p", "FP-1", uoms={"EA": _uom()}, default="EA")
    assert resolve_ct_uom(raw) is None


def test_resolve_ct_uom_returns_none_for_ctn_only_never_matches_ctn_as_ct():
    # The 7 deferred SKUs carry CTN/PLT, not CT. CTN must NOT be mistaken for CT — they fall
    # out here naturally as "no CT UoM", which is exactly how 5c defers them.
    raw = _product("p", "FP-1", uoms={"CTN": _uom(length=300), "PLT": _uom()}, default="CTN")
    assert resolve_ct_uom(raw) is None


def test_resolve_ct_uom_ignores_ea_and_plt_when_a_ct_is_present():
    raw = _product(
        "p", "FP-1",
        uoms={"EA": _uom(), "CT": _uom(length=300), "PLT": _uom()},
        default="EA",
    )
    assert resolve_ct_uom(raw) == "CT"


def test_resolve_default_uom_returns_default_unit_of_measure():
    # The each/sandbox path passes this resolver — it must keep returning the default UoM id.
    raw = _product("p", "FP-1", uoms={"EA": _uom(), "CT": _uom()}, default="EA")
    assert resolve_default_uom(raw) == "EA"


# ============================================================================
# UoM-aware read: the diff baseline + read-back must follow the TARGET UoM, not the default.
# ============================================================================

def test_read_product_for_dims_defaults_to_default_uom():
    # No uom arg → reads the default UoM's dims. This is the unchanged M-DIMS-3/4/5b behaviour.
    raw = _product("p", "FP-1",
                   uoms={"EA": _uom(length=10, width=11, height=12, weight=1.0),
                         "CT": _uom(length=300, width=200, height=100, weight=5.0)},
                   default="EA")
    read = read_product_for_dims(_client_returning(raw), "p")
    assert read.uom == "EA"
    assert read.current_dims == {"length": 10, "width": 11, "height": 12, "weight": 1.0}


def test_read_product_for_dims_reads_a_specific_uom_when_asked():
    raw = _product("p", "FP-1",
                   uoms={"EA": _uom(length=10, width=11, height=12, weight=1.0),
                         "CT": _uom(length=300, width=200, height=100, weight=5.0)},
                   default="EA")
    read = read_product_for_dims(_client_returning(raw), "p", uom="CT")
    assert read.uom == "CT"
    assert read.current_dims == {"length": 300, "width": 200, "height": 100, "weight": 5.0}


def test_dims_for_uom_pulls_named_uom_and_omits_unset_as_none():
    raw = _product("p", "FP-1", uoms={"EA": _uom(), "CT": _uom(length=300)}, default="EA")
    # CT carries only length; the rest read as None (GET omits unset dims). weight defaults to 0.
    assert dims_for_uom(raw, "CT") == {"length": 300, "width": None, "height": None, "weight": 0}
    # an absent UoM → every dim None (so a read-back against a wrong/absent UoM can't false-pass).
    assert dims_for_uom(raw, "NOPE") == {"length": None, "width": None, "height": None, "weight": None}


def test_approve_dims_write_diffs_against_the_read_uom_not_the_default():
    # CT already holds the desired carton dims; EA (default) is empty. With read_uom='CT' the
    # diff baseline is the CT dims → empty diff → NO mutate. (Diffing the empty default would
    # wrongly fire a write — the idempotency bug 5c must avoid.)
    raw = _product("p", "FP-1",
                   uoms={"EA": _uom(), "CT": _uom(length=300, width=200, height=100, weight=5.0)},
                   default="EA", customer_id=SANDBOX_CUSTOMER_ID)
    fired = []
    result = approve_dims_write(
        "p", client=_client_returning(raw), config=_cfg(),
        desired_dims={"length": 300, "width": 200, "height": 100, "weight": 5.0},
        mutate_fn=lambda diff: fired.append(diff),
        rate_limiter=MutateRateLimiter(), approval_token=SECRET, read_uom="CT",
    )
    assert result.no_op is True
    assert fired == [], "diff baseline must be the CT UoM dims — a matching CT no-ops"


def test_approve_dims_write_default_read_uom_still_diffs_against_default_uom():
    # Same product, no read_uom → baseline is the empty default EA → the full desired set is the
    # diff and the mutate fires. Proves read_uom genuinely chooses the baseline UoM.
    raw = _product("p", "FP-1",
                   uoms={"EA": _uom(), "CT": _uom(length=300, width=200, height=100, weight=5.0)},
                   default="EA", customer_id=SANDBOX_CUSTOMER_ID)
    fired = []
    approve_dims_write(
        "p", client=_client_returning(raw), config=_cfg(),
        desired_dims={"length": 300, "width": 200, "height": 100, "weight": 5.0},
        mutate_fn=lambda diff: (fired.append(diff) or {"ok": True}),
        rate_limiter=MutateRateLimiter(), approval_token=SECRET,  # no read_uom → default EA
    )
    assert fired and fired[0] == {"length": 300, "width": 200, "height": 100, "weight": 5.0}, \
        "against the empty EA baseline the full desired set is the diff"


# ============================================================================
# write_and_verify: the PATCH targets the CT UoM id, and the read-back verifies THAT UoM.
# ============================================================================

def test_write_and_verify_targets_and_reads_back_the_ct_uom_not_the_each():
    # EA (default) empty, CT empty. Write carton dims to CT. The PATCH must target the CT id,
    # and the read-back must verify the CT UoM — while the each (EA) stays empty. Were the
    # read-back to check EA (the default), it would raise DimsReadBackMismatch, so SUCCESS here
    # IS the proof the verify is UoM-specific.
    raw = _product("p", "FP-1", uoms={"EA": _uom(), "CT": _uom()}, default="EA",
                   customer_id=SANDBOX_CUSTOMER_ID)
    client = _client_returning(raw)
    desired = {"length": 300, "width": 200, "height": 100, "weight": 5.0}

    after = write_and_verify(
        client=client, config=_cfg(), product_id="p", code="FP-1", uom="CT",
        desired_dims=desired, approval_token=SECRET, rate_limiter=MutateRateLimiter(),
    )

    ops = client._http.patches[0]["json"]
    assert {op["path"] for op in ops} == {
        "/unitOfMeasures/CT/length", "/unitOfMeasures/CT/width",
        "/unitOfMeasures/CT/height", "/unitOfMeasures/CT/weight",
    }, "the PATCH must target the CT UoM id, not the default/each"
    assert after == desired, "read-back reflects the CT dims"
    assert client._http.products["p"]["unitOfMeasures"]["EA"] == {"baseQty": 1, "weight": 0, "barcode": "bc"}, \
        "the each (EA) UoM was never written — 5c writes the carton UoM only"


def test_write_and_verify_uses_the_resolved_ct_id_in_the_patch_path():
    # Keyed-by-id shape: the PATCH path must carry the resolved CT *id* (u-ct), not the code.
    raw = _product("p", "FP-1",
                   uoms={"u-ea": _uom(code="EA"), "u-ct": _uom(code="CT")},
                   default="u-ea", customer_id=SANDBOX_CUSTOMER_ID)
    client = _client_returning(raw)
    write_and_verify(
        client=client, config=_cfg(), product_id="p", code="FP-1", uom="u-ct",
        desired_dims={"length": 300, "width": 200, "height": 100},
        approval_token=SECRET, rate_limiter=MutateRateLimiter(),
    )
    ops = client._http.patches[0]["json"]
    assert ops and all(op["path"].startswith("/unitOfMeasures/u-ct/") for op in ops)


# ============================================================================
# build_bulk_plan generalised on a uom_resolver: CT writable, everything-else "no CT UoM".
# ============================================================================

def test_build_bulk_plan_ct_resolver_buckets_writable_noop_and_skips_non_ct():
    pw = _product("pw", "FP-1", uoms={"EA": _uom(), "CT": _uom()}, default="EA")  # empty CT → writable
    pn = _product("pn", "FP-2",
                  uoms={"EA": _uom(), "CT": _uom(length=300, width=200, height=100, weight=5.0)},
                  default="EA")  # CT already matches → no-op
    pe = _product("pe", "FP-3", uoms={"EA": _uom()}, default="EA")  # EA-only → no CT UoM
    pc = _product("pc", "FP-4", uoms={"CTN": _uom(length=1), "PLT": _uom()}, default="CTN")  # CTN/PLT → no CT UoM
    client = _client_with(pw, pn, pe, pc)
    desired = {
        "FP-1": {"length": 300, "width": 200, "height": 100, "weight": 5.0},
        "FP-2": {"length": 300, "width": 200, "height": 100, "weight": 5.0},
        "FP-3": {"length": 10, "width": 10, "height": 10},  # captured, but the SKU has no CT UoM
        "FP-4": {"length": 20, "width": 20, "height": 20},  # captured, but the SKU has no CT UoM
    }
    cands = [LiveCandidate("pw", "FP-1"), LiveCandidate("pn", "FP-2"),
             LiveCandidate("pe", "FP-3"), LiveCandidate("pc", "FP-4")]

    plan = build_bulk_plan(client, cands, lambda c: desired.get(c), config=_cfg(live_promotion=True),
                           uom_resolver=resolve_ct_uom, no_uom_reason="no CT UoM")

    # writable: only the CT SKU whose CT is empty — and it targets the resolved CT UoM id.
    assert [i.code for i in plan.to_write] == ["FP-1"]
    assert plan.to_write[0].uom == "CT"
    assert plan.to_write[0].current_dims == {"length": None, "width": None, "height": None, "weight": 0}
    assert plan.to_write[0].diff == {"length": 300, "width": 200, "height": 100, "weight": 5.0}
    # no-op: the CT already matches (idempotency baseline is the CT UoM, not the empty each).
    assert {n["code"] for n in plan.no_ops} == {"FP-2"}
    # skipped: the EA-only AND the CTN/PLT SKU both fall out cleanly as "no CT UoM" — never written.
    assert {s["code"]: s["reason"] for s in plan.skipped} == {"FP-3": "no CT UoM", "FP-4": "no CT UoM"}


def test_build_bulk_plan_default_resolver_unchanged_targets_default_uom():
    # Passing the default resolver explicitly must reproduce the M-DIMS-4 each behaviour:
    # write to the default UoM, skip reason "no default UoM".
    pw = _product("pw", "sRK-1", uoms={"EA": _uom()}, default="EA", customer_id=SANDBOX_CUSTOMER_ID)
    pnouom = _product("pnouom", "sRK-2", uoms={}, default=None, customer_id=SANDBOX_CUSTOMER_ID)
    client = _client_with(pw, pnouom)
    desired = {"sRK-1": {"length": 10, "width": 11, "height": 12, "weight": 1.0},
               "sRK-2": {"length": 10, "width": 11, "height": 12}}
    cands = [LiveCandidate("pw", "sRK-1"), LiveCandidate("pnouom", "sRK-2")]

    plan = build_bulk_plan(client, cands, lambda c: desired.get(c), config=_cfg())

    assert [i.code for i in plan.to_write] == ["sRK-1"]
    assert plan.to_write[0].uom == "EA"
    assert {s["code"]: s["reason"] for s in plan.skipped} == {"sRK-2": "no default UoM"}


# ============================================================================
# run_ct_bulk — the 5c live entry. Reuses the proven loop; only live customer + CT resolver
# + the CC_LIVE_PROMOTION precondition differ.
# ============================================================================

def _ct(pid, code):
    """A live SKU that HAS a CT carton UoM (both EA and CT empty)."""
    return _product(pid, code, uoms={"EA": _uom(), "CT": _uom()}, default="EA")


def test_run_ct_bulk_writes_ct_skus_and_skips_each_only_and_ctn():
    pc1 = _ct("c1", "FP-1")
    pc2 = _ct("c2", "HI-2")
    pea = _product("e1", "FP-9", uoms={"EA": _uom()}, default="EA")                  # the 367 each-only group
    pctn = _product("k1", "FP-7", uoms={"CTN": _uom(), "PLT": _uom()}, default="CTN")  # the 7 CTN/PLT no-EA group
    client = _client_with(pc1, pc2, pea, pctn)
    desired = {
        "FP-1": {"length": 300, "width": 200, "height": 100, "weight": 5.0},
        "HI-2": {"length": 250, "width": 180, "height": 90, "weight": 3.0},
        "FP-9": {"length": 10, "width": 10, "height": 10},
        "FP-7": {"length": 20, "width": 20, "height": 20},
    }
    cands = [LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "HI-2"),
             LiveCandidate("e1", "FP-9"), LiveCandidate("k1", "FP-7")]

    report = run_ct_bulk(
        client=client, config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: True, candidates=cands,
        sleep=lambda s: None, pace_seconds=0,
    )

    assert report.failed is None and report.aborted is False
    assert {w["code"] for w in report.written} == {"FP-1", "HI-2"}
    # every PATCH targeted the CT UoM specifically — never the each/CTN/PLT.
    assert {c["pid"] for c in client._http.patches} == {"c1", "c2"}
    for c in client._http.patches:
        assert all(op["path"].startswith("/unitOfMeasures/CT/") for op in c["json"])
    # the 367 each-only and the 7 CTN/PLT SKUs fall out cleanly as 'no CT UoM' — never written.
    assert {s["code"]: s["reason"] for s in report.skipped} == {"FP-9": "no CT UoM", "FP-7": "no CT UoM"}
    assert report.written[0]["after"]["length"] == 300, "read-back reflects the written CT dims"


def test_run_ct_bulk_refuses_when_promotion_not_armed_and_never_patches():
    client = _client_with(_ct("c1", "FP-1"))
    with pytest.raises(DimsRoundtripRefused):
        run_ct_bulk(
            client=client, config=_cfg(live_promotion=False),  # disarmed
            desired_lookup=lambda c: {"length": 300, "width": 200, "height": 100},
            approval_token=SECRET, confirm=lambda plan: True,
            candidates=[LiveCandidate("c1", "FP-1")], sleep=lambda s: None, pace_seconds=0,
        )
    assert client._http.patches == [], "a disarmed 5c run must not PATCH the live id"


def test_run_ct_bulk_batch_hard_stop_no_go_writes_nothing():
    client = _client_with(_ct("c1", "FP-1"), _ct("c2", "HI-2"))
    report = run_ct_bulk(
        client=client, config=_cfg(live_promotion=True),
        desired_lookup=lambda c: {"length": 300, "width": 200, "height": 100},
        approval_token=SECRET, confirm=lambda plan: False,  # human declines the batch
        candidates=[LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "HI-2")],
        sleep=lambda s: None, pace_seconds=0,
    )
    assert report.aborted is True and report.written == []
    assert client._http.patches == [], "no PATCH may fire without the batch go"


def test_run_ct_bulk_fail_fast_keeps_known_good_and_leaves_rest_untouched():
    # FP-2's CT PATCH won't persist → read-back mismatch stops the run at #2, fail-fast.
    client = _client_with(_ct("c1", "FP-1"), _ct("c2", "FP-2"), _ct("c3", "FP-3"),
                          fail_codes={"FP-2"})
    desired = {c: {"length": 100, "width": 50, "height": 30, "weight": 1.0}
               for c in ("FP-1", "FP-2", "FP-3")}
    cands = [LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "FP-2"), LiveCandidate("c3", "FP-3")]

    report = run_ct_bulk(
        client=client, config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: True, candidates=cands,
        sleep=lambda s: None, pace_seconds=0,
    )

    assert report.failed is not None and report.failed["code"] == "FP-2"
    assert [w["code"] for w in report.written] == ["FP-1"], "only SKU 1 is known-good"
    assert report.untouched_after_failure == ["FP-3"]
    assert [c["pid"] for c in client._http.patches] == ["c1", "c2"], "SKU 3 never attempted"


def test_run_ct_bulk_idempotent_rerun_zero_patches():
    client = _client_with(_ct("c1", "FP-1"), _ct("c2", "HI-2"))
    desired = {"FP-1": {"length": 300, "width": 200, "height": 100, "weight": 5.0},
               "HI-2": {"length": 250, "width": 180, "height": 90, "weight": 3.0}}
    cands = [LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "HI-2")]
    kw = dict(config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
              approval_token=SECRET, confirm=lambda plan: True, candidates=cands,
              sleep=lambda s: None, pace_seconds=0)

    r1 = run_ct_bulk(client=client, **kw)
    assert len(r1.written) == 2
    after_first = len(client._http.patches)
    assert after_first == 2

    r2 = run_ct_bulk(client=client, **kw)  # everything already matches → all no-op
    assert r2.written == []
    assert {x["code"] for x in r2.no_ops} == {"FP-1", "HI-2"}
    assert len(client._http.patches) == after_first, "a clean re-run issues no new PATCH"


def test_run_ct_bulk_gathers_live_candidates_when_none(monkeypatch):
    # candidates=None → 5c gathers ACTIVE LIVE Forage SKUs (the live gatherer, not the sandbox one).
    seen = {}

    def fake_gather(client):
        seen["called"] = True
        return [LiveCandidate("c1", "FP-1")]

    monkeypatch.setattr("dims_write.bulk.gather_active_live_candidates", fake_gather)
    client = _client_with(_ct("c1", "FP-1"))
    report = run_ct_bulk(
        client=client, config=_cfg(live_promotion=True),
        desired_lookup=lambda c: {"length": 300, "width": 200, "height": 100},
        approval_token=SECRET, confirm=lambda plan: True,
        sleep=lambda s: None, pace_seconds=0,  # candidates omitted → gather
    )
    assert seen.get("called") is True
    assert {w["code"] for w in report.written} == {"FP-1"}


# ============================================================================
# The known-partial report: 5c must NOT look complete. The caveats are a tested fact.
# ============================================================================

def test_format_ct_bulk_report_states_the_known_partial_state():
    report = BulkReport(
        written=[{"code": "FP-1", "before": {}, "after": {}},
                 {"code": "HI-2", "before": {}, "after": {}}],
        no_ops=[{"code": "AE-3", "reason": "already matches"}],
        skipped=[{"code": "FP-9", "reason": "no CT UoM"},
                 {"code": "FP-7", "reason": "no CT UoM"},
                 {"code": "FP-0", "reason": "no captured desired dims"}],
        failed=None, aborted=False, untouched_after_failure=[],
    )
    text = format_ct_bulk_report(report)

    # CT cohort = written(2) + no_op(1) + failed(0) + untouched(0) = 3; written 2 of 3.
    assert "written for 2 of 3" in text
    # the each-level (Base UoM) dims for the cohort are still EMPTY, pending 5d.
    assert "Base UoM" in text and "EMPTY" in text and "5d" in text
    # the CTN/PLT no-EA SKUs are deferred and explicitly unhandled by 5c.
    assert "deferred" in text.lower() and "unhandled by 5c" in text.lower()
    # the 'no CT UoM' skip group is surfaced (the 367 each-only + 7 CTN/PLT live here).
    assert "no CT UoM" in text


def test_format_ct_bulk_report_cohort_counts_failed_and_untouched():
    # fail-fast mid-run: the cohort still counts the failed SKU + everything left untouched.
    report = BulkReport(
        written=[{"code": "FP-1", "after": {}}],
        no_ops=[],
        skipped=[{"code": "X", "reason": "no CT UoM"}],
        failed={"code": "FP-2", "product_id": "c2", "error": "read-back mismatch"},
        aborted=False, untouched_after_failure=["FP-3", "FP-4"],
    )
    text = format_ct_bulk_report(report)
    # cohort = 1 written + 0 no-op + 1 failed + 2 untouched = 4.
    assert "written for 1 of 4" in text
    assert "FP-2" in text, "the fail-fast SKU is named so the partial state is auditable"


# ============================================================================
# Package export
# ============================================================================

def test_exported_from_package():
    from dims_write import (
        run_ct_bulk as pkg_run,
        resolve_ct_uom as pkg_res,
        resolve_default_uom as pkg_def,
        format_ct_bulk_report as pkg_fmt,
    )
    assert pkg_run is run_ct_bulk
    assert pkg_res is resolve_ct_uom
    assert pkg_def is resolve_default_uom
    assert pkg_fmt is format_ct_bulk_report
