"""M-DIMS-5d — bulk-write captured dims to the Each/Base UoM (live Forage): the engine, CC-mocked.

5c (write to the CT carton UoM) is CLOSED, not written: CC's name-validation trap (every live CT
UoM is named "CT", 2 chars < the 3-char floor) 422s the dims PATCH, and CT names can't be edited
on live master. So the automated dims target is the **Each / Base UoM** (``defaultUnitOfMeasure``),
which every SKU has and whose names are clean (probe: 455/455 valid).

5d reuses the proven M-DIMS-4/5c engine UNCHANGED — the 5a gate, ONE batch hard stop, paced
fail-fast, ``write_and_verify`` + UoM-specific read-back, W4 idempotency, the CC_LIVE_PROMOTION
precondition. The ONLY thing that differs from 5c is the UoM resolver: ``resolve_default_uom``
(the each) instead of ``resolve_ct_uom``. Dims arrive in cm via ``captured_cc_dims_table`` (the
script's concern; here the desired dict is injected directly).

CC is mocked; the live run is Jake's deliberate, armed ``scripts/run_dims_each_bulk.py`` — never
run here, never automatically.
"""
from __future__ import annotations

import time

import httpx
import pytest

from dims_write.bulk import (
    run_each_bulk, format_each_bulk_report, resolve_default_uom, build_bulk_plan,
    find_poisoning_uoms, POISON_SKIP_REASON, BulkReport,
)
from dims_write.live_proving import LiveCandidate
from dims_write.roundtrip import DimsRoundtripRefused
from cc_client.client import CartonCloudClient, _Token
from cc_client import WriteConfig, SANDBOX_CUSTOMER_ID

LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"
SECRET = "each-approval-secret"


# ---------- fixtures: a v8 warehouse-product with a default (each) UoM ----------

def _uom(*, code=None, name="Each", length=None, width=None, height=None, weight=0):
    obj = {"baseQty": 1, "weight": weight, "barcode": "bc", "name": name}
    if code is not None:
        obj["code"] = code
    for k, v in (("length", length), ("width", width), ("height", height)):
        if v is not None:
            obj[k] = v
    return obj


def _product(pid, sku_code, *, uoms, default="EA", customer_id=LIVE_FORAGE_CUSTOMER_ID):
    return {
        "id": pid,
        "customer": {"id": customer_id},
        "details": {"active": True},
        "references": {"code": sku_code},
        "defaultUnitOfMeasure": default,
        "unitOfMeasures": uoms,
    }


def _each(pid, code, **uom_kw):
    """A live SKU whose default (each) UoM is EA."""
    return _product(pid, code, uoms={"EA": _uom(**uom_kw)}, default="EA")


class EachTransport:
    """GET returns the product; PATCH applies the JSON-Patch ops to the addressed UoM unless the
    product's code is in ``fail_codes`` (then the PATCH 200s but does NOT persist → read-back
    mismatch). Records every call."""

    def __init__(self, products, *, persist=True, fail_codes=()):
        self.products = {pid: dict(p) for pid, p in products.items()}
        self.persist = persist
        self.fail_codes = set(fail_codes)
        self.calls = []

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
    def patches(self):
        return [c for c in self.calls if c["method"] == "PATCH"]


def _client(*, write_enabled=True):
    c = CartonCloudClient(client_id="id", client_secret="sec", tenant_id="TENANT",
                          base_url="https://cc.example", write_enabled=write_enabled)
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def _client_with(*raws, persist=True, fail_codes=()):
    c = _client()
    c._http = EachTransport({r["id"]: r for r in raws}, persist=persist, fail_codes=fail_codes)
    return c


def _cfg(*, live_promotion=False, write_enabled=True, secret=SECRET):
    return WriteConfig(
        write_enabled=write_enabled, write_secret=secret,
        customer_allowlist=frozenset({SANDBOX_CUSTOMER_ID}),  # base allowlist stays sandbox-only
        live_promotion=live_promotion,
    )


# ============================================================================
# run_each_bulk — reuses the proven loop; only the resolver (default/each UoM) differs from 5c.
# ============================================================================

def test_run_each_bulk_writes_dims_to_the_default_uom_for_live_skus():
    p1, p2 = _each("c1", "FP-1"), _each("c2", "HI-2")
    client = _client_with(p1, p2)
    desired = {
        "FP-1": {"length": 30.0, "width": 20.0, "height": 10.0, "weight": 5.0},  # cm
        "HI-2": {"length": 25.0, "width": 18.0, "height": 9.0, "weight": 3.0},
    }
    cands = [LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "HI-2")]

    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: True, candidates=cands,
        sleep=lambda s: None, pace_seconds=0,
    )

    assert report.failed is None and report.aborted is False
    assert {w["code"] for w in report.written} == {"FP-1", "HI-2"}
    # every PATCH targeted the EACH (default) UoM specifically.
    assert {c["pid"] for c in client._http.patches} == {"c1", "c2"}
    for c in client._http.patches:
        assert all(op["path"].startswith("/unitOfMeasures/EA/") for op in c["json"])
    assert report.written[0]["after"]["length"] == 30.0, "read-back reflects the written each dims"


def test_run_each_bulk_targets_default_uom_resolver():
    # Guard: 5d uses resolve_default_uom (not the CT resolver) — the each is the target.
    raw = _product("p", "FP-1", uoms={"EA": _uom(), "CT": _uom(name="Carton")}, default="EA")
    assert resolve_default_uom(raw) == "EA"


def test_run_each_bulk_refuses_when_promotion_not_armed_and_never_patches():
    client = _client_with(_each("c1", "FP-1"))
    with pytest.raises(DimsRoundtripRefused):
        run_each_bulk(
            client=client, config=_cfg(live_promotion=False),  # disarmed
            desired_lookup=lambda c: {"length": 30.0, "width": 20.0, "height": 10.0},
            approval_token=SECRET, confirm=lambda plan: True,
            candidates=[LiveCandidate("c1", "FP-1")], sleep=lambda s: None, pace_seconds=0,
        )
    assert client._http.patches == [], "a disarmed 5d run must not PATCH the live id"


def test_run_each_bulk_batch_hard_stop_no_go_writes_nothing():
    client = _client_with(_each("c1", "FP-1"), _each("c2", "HI-2"))
    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True),
        desired_lookup=lambda c: {"length": 30.0, "width": 20.0, "height": 10.0},
        approval_token=SECRET, confirm=lambda plan: False,  # human declines the batch
        candidates=[LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "HI-2")],
        sleep=lambda s: None, pace_seconds=0,
    )
    assert report.aborted is True and report.written == []
    assert client._http.patches == [], "no PATCH may fire without the batch go"


def test_run_each_bulk_fail_fast_keeps_known_good_and_leaves_rest_untouched():
    client = _client_with(_each("c1", "FP-1"), _each("c2", "FP-2"), _each("c3", "FP-3"),
                          fail_codes={"FP-2"})
    desired = {c: {"length": 10.0, "width": 5.0, "height": 3.0, "weight": 1.0}
               for c in ("FP-1", "FP-2", "FP-3")}
    cands = [LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "FP-2"), LiveCandidate("c3", "FP-3")]

    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: True, candidates=cands,
        sleep=lambda s: None, pace_seconds=0,
    )

    assert report.failed is not None and report.failed["code"] == "FP-2"
    assert [w["code"] for w in report.written] == ["FP-1"], "only SKU 1 is known-good"
    assert report.untouched_after_failure == ["FP-3"]
    assert [c["pid"] for c in client._http.patches] == ["c1", "c2"], "SKU 3 never attempted"


def test_run_each_bulk_corrects_preexisting_wrong_dims():
    # The 15 already-dimensioned SKUs: EA already carries the pre-cm 10x value (255), the captured
    # desired is cm (25.5). The idempotent diff sees a change → PATCH corrects it. Not special-cased.
    p = _each("c1", "FP-1", length=255, width=230, height=150, weight=2.2)  # stale mm value on the each
    client = _client_with(p)
    desired = {"FP-1": {"length": 25.5, "width": 23.0, "height": 15.0, "weight": 2.2}}  # cm

    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: True,
        candidates=[LiveCandidate("c1", "FP-1")], sleep=lambda s: None, pace_seconds=0,
    )

    assert [w["code"] for w in report.written] == ["FP-1"]
    assert report.written[0]["before"]["length"] == 255, "saw the stale 10x value"
    assert report.written[0]["after"]["length"] == 25.5, "corrected to cm in place"
    assert len(client._http.patches) == 1


def test_run_each_bulk_idempotent_rerun_zero_patches():
    client = _client_with(_each("c1", "FP-1"), _each("c2", "HI-2"))
    desired = {"FP-1": {"length": 30.0, "width": 20.0, "height": 10.0, "weight": 5.0},
               "HI-2": {"length": 25.0, "width": 18.0, "height": 9.0, "weight": 3.0}}
    cands = [LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "HI-2")]
    kw = dict(config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
              approval_token=SECRET, confirm=lambda plan: True, candidates=cands,
              sleep=lambda s: None, pace_seconds=0)

    r1 = run_each_bulk(client=client, **kw)
    assert len(r1.written) == 2
    after_first = len(client._http.patches)
    assert after_first == 2

    r2 = run_each_bulk(client=client, **kw)  # everything already matches → all no-op
    assert r2.written == []
    assert {x["code"] for x in r2.no_ops} == {"FP-1", "HI-2"}
    assert len(client._http.patches) == after_first, "a clean re-run issues no new PATCH"


def test_run_each_bulk_skips_product_with_no_default_uom():
    # Pathological (probe found 0 of these live) — a product with no default UoM is skipped, not written.
    broken = _product("c1", "FP-1", uoms={"EA": _uom()}, default=None)
    client = _client_with(broken)
    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True),
        desired_lookup=lambda c: {"length": 30.0, "width": 20.0, "height": 10.0},
        approval_token=SECRET, confirm=lambda plan: True,
        candidates=[LiveCandidate("c1", "FP-1")], sleep=lambda s: None, pace_seconds=0,
    )
    assert report.written == []
    assert {s["code"]: s["reason"] for s in report.skipped} == {"FP-1": "no default UoM"}
    assert client._http.patches == []


def test_run_each_bulk_gathers_live_candidates_when_none(monkeypatch):
    seen = {}

    def fake_gather(client):
        seen["called"] = True
        return [LiveCandidate("c1", "FP-1")]

    monkeypatch.setattr("dims_write.bulk.gather_active_live_candidates", fake_gather)
    client = _client_with(_each("c1", "FP-1"))
    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True),
        desired_lookup=lambda c: {"length": 30.0, "width": 20.0, "height": 10.0},
        approval_token=SECRET, confirm=lambda plan: True,
        sleep=lambda s: None, pace_seconds=0,  # candidates omitted → gather
    )
    assert seen.get("called") is True
    assert {w["code"] for w in report.written} == {"FP-1"}


# ============================================================================
# The CT-poison guard — CC validates the WHOLE UoM set on any dims PATCH, so a 2-char CT name
# 422s a write to the EACH too. The each-write must SKIP such SKUs, not fail-fast on them.
# ============================================================================

def _each_with_ct(pid, code, *, ct_name="CT", ea_name="Each"):
    """A live SKU with a valid-named EA (the target) AND a CT sibling whose name may be too short.
    A 2-char CT name poisons the whole-product save — a PATCH to the EA 422s on /unitOfMeasures/CT/name."""
    return _product(pid, code, uoms={"EA": _uom(name=ea_name), "CT": _uom(code="CT", name=ct_name)},
                    default="EA")


def test_find_poisoning_uoms_flags_short_ct_name():
    raw = _each_with_ct("p", "FP-1")  # CT name "CT" (2 chars) < the 3-char floor
    assert find_poisoning_uoms(raw) == [("CT", "CT")]


def test_find_poisoning_uoms_is_general_not_ct_specific():
    # Empty name and 1-char name on a NON-CT UoM are also caught — the rule is name length, not "CT".
    empty = _product("p", "FP-1", uoms={"EA": _uom(name="Each"), "XX": _uom(code="XX", name="")},
                     default="EA")
    one_char = _product("q", "FP-2", uoms={"EA": _uom(name="Each"), "YY": _uom(code="YY", name="Z")},
                        default="EA")
    assert find_poisoning_uoms(empty) == [("XX", "")]
    assert find_poisoning_uoms(one_char) == [("YY", "Z")]


def test_find_poisoning_uoms_none_when_all_names_valid():
    assert find_poisoning_uoms(_each("c1", "FP-1")) == []                          # EA-only, valid
    assert find_poisoning_uoms(_each_with_ct("p", "FP-1", ct_name="Carton")) == []  # CT name valid


def test_run_each_bulk_skips_ct_bearing_sku_and_does_not_fail_fast():
    # The HL-6VA reproduction: an EA-only SKU writes; the CT-bearing SKU (poisoned CT name) is
    # SKIPPED as blocked — NOT attempted, so no 422, no fail-fast, the run completes.
    ok = _each("c1", "FP-1")
    poisoned = _each_with_ct("c2", "HL-6VA")
    ok2 = _each("c3", "FP-9")
    client = _client_with(ok, poisoned, ok2)
    desired = {c: {"length": 30.0, "width": 20.0, "height": 10.0, "weight": 1.0}
               for c in ("FP-1", "HL-6VA", "FP-9")}
    cands = [LiveCandidate("c1", "FP-1"), LiveCandidate("c2", "HL-6VA"), LiveCandidate("c3", "FP-9")]

    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True), desired_lookup=lambda c: desired.get(c),
        approval_token=SECRET, confirm=lambda plan: True, candidates=cands,
        sleep=lambda s: None, pace_seconds=0,
    )

    assert report.failed is None, "the poisoned SKU is skipped, never attempted → no fail-fast"
    assert {w["code"] for w in report.written} == {"FP-1", "FP-9"}
    blocked = {s["code"]: s["reason"] for s in report.skipped}
    assert "HL-6VA" in blocked and "CT" in blocked["HL-6VA"] and "poison" in blocked["HL-6VA"].lower()
    # the poisoned product was never PATCHed.
    assert "c2" not in {c["pid"] for c in client._http.patches}


def test_run_each_bulk_writes_ct_bearing_sku_when_ct_name_is_valid():
    # Name-based, not presence-based: a CT sibling with a VALID name does NOT block the each write,
    # so fixing CT names later auto-unblocks these SKUs without a code change.
    p = _each_with_ct("c1", "FP-1", ct_name="Carton")
    client = _client_with(p)
    report = run_each_bulk(
        client=client, config=_cfg(live_promotion=True),
        desired_lookup=lambda c: {"length": 30.0, "width": 20.0, "height": 10.0},
        approval_token=SECRET, confirm=lambda plan: True,
        candidates=[LiveCandidate("c1", "FP-1")], sleep=lambda s: None, pace_seconds=0,
    )
    assert {w["code"] for w in report.written} == {"FP-1"}
    for c in client._http.patches:
        assert all(op["path"].startswith("/unitOfMeasures/EA/") for op in c["json"])


def test_build_bulk_plan_only_blocks_when_flag_set():
    # The guard is opt-in (each-write passes it). Without the flag, behaviour is unchanged so the
    # CT/sandbox paths are untouched.
    client = _client_with(_each_with_ct("c1", "FP-1"))
    cands = [LiveCandidate("c1", "FP-1")]
    desired = lambda c: {"length": 30.0, "width": 20.0, "height": 10.0}

    unguarded = build_bulk_plan(client, cands, desired, config=_cfg(), uom_resolver=resolve_default_uom)
    assert [i.code for i in unguarded.to_write] == ["FP-1"], "no guard → would still try to write"

    guarded = build_bulk_plan(client, cands, desired, config=_cfg(), uom_resolver=resolve_default_uom,
                              block_on_poisoning_uom=True)
    assert guarded.to_write == []
    assert guarded.skipped[0]["code"] == "FP-1" and "poison" in guarded.skipped[0]["reason"].lower()


# ============================================================================
# The report: 5d must name its scope honestly (each/Base UoM; CT is closed/out-of-scope).
# ============================================================================

def test_format_each_bulk_report_states_scope_and_counts():
    report = BulkReport(
        written=[{"code": "FP-1", "before": {}, "after": {}}],
        no_ops=[{"code": "HI-2", "reason": "already matches"}],
        skipped=[{"code": "BAD", "reason": "no default UoM"}],
        failed=None, aborted=False, untouched_after_failure=[],
    )
    out = format_each_bulk_report(report)
    assert "Each" in out or "each" in out
    assert "1" in out  # written count
    # CT is named as out-of-scope so a reader can't mistake this for the CT write.
    assert "CT" in out
