"""M-DIMS-5b — first live Forage writes, human dims-verified: the engine, CC-mocked.

5b is the PROVING run: it confirms the inferred captured-dims→live-SKU mapping is right on
real Forage data before 5c writes hundreds. The read-back verify proves a write *landed*; it
cannot prove the dims are *right for the SKU* — so a human eyeballs 3–5 SKUs and confirms each
by TYPING THE SKU CODE back (not a bare `go`). It reuses the proven M-DIMS-3 write path
(`write_and_verify`) unchanged; 5b adds only live target selection + the verification UX.

The two safety-critical behaviours under the heaviest test here:
  1. the per-SKU confirm requires the typed code to MATCH the SKU being written — a wrong
     code, a bare `go`, or empty input must NOT PATCH (the match lives in the engine, not
     the script's hope);
  2. the still-armed-at-exit safeguard is structural — `finalize_exit` forces a non-zero exit
     and a loud reminder whenever CC_LIVE_PROMOTION is still set, so no path exits 0 silently
     armed.

CC is mocked; the real proving run is Jake's deliberate, eyes-on `scripts/run_dims_live_proving.py`.
"""
from __future__ import annotations

import logging
import time

import httpx
import pytest

from dims_write.live_proving import (
    gather_active_live_candidates,
    select_live_proving_targets,
    build_live_proving_plan,
    run_live_proving,
    disarm_reminder,
    finalize_exit,
    LiveCandidate,
    LiveTarget,
    LiveProvingPlan,
    LiveHardStopInfo,
    LiveProvingReport,
    LiveProvingRefused,
)
from cc_client.client import CartonCloudClient, _Token
from cc_client import WriteConfig, SANDBOX_CUSTOMER_ID
from cc_client.write_config import LIVE_FORAGE_CUSTOMER_ID

SECRET = "live-approval-secret"
UOM = "EA"


class LiveTransport:
    """Live warehouse-products keyed by id. GET returns the product; PATCH applies the
    JSON-Patch ops to the addressed product's UoM so read-back reflects them. Records calls."""

    def __init__(self, products: dict):
        self.products = {pid: dict(p) for pid, p in products.items()}
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        pid = url.rstrip("/").split("/")[-1]
        self.calls.append({"method": method, "url": url, "json": json, "pid": pid})
        prod = self.products.get(pid, {})
        if method == "GET":
            return httpx.Response(200, json=dict(prod))
        if method == "PATCH":
            if json:
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


def _live_product(pid, code, *, uom=UOM, length=None, width=None, height=None, weight=0):
    # A real Forage product: customer = the LIVE id. Dims OMITTED when unset (live has none yet).
    uom_obj = {"baseQty": 1, "weight": weight, "barcode": code}
    for k, v in (("length", length), ("width", width), ("height", height)):
        if v is not None:
            uom_obj[k] = v
    return {
        "id": pid,
        "customer": {"id": LIVE_FORAGE_CUSTOMER_ID},
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


def _armed_cfg():
    # write_enabled + secret + default sandbox base allow-list + CC_LIVE_PROMOTION armed.
    return WriteConfig(write_enabled=True, write_secret=SECRET, live_promotion=True)


def _disarmed_cfg():
    return WriteConfig(write_enabled=True, write_secret=SECRET, live_promotion=False)


# Captured dims keyed by BASE Forage code (what load_dimensions produces). Live codes are the
# base codes themselves (FP-/HI-/AE-); a live uppercase-S code maps via the strip (SAE→AE-TOT).
CAPTURED = {
    "FP-1234": {"length": 300, "width": 200, "height": 100, "weight": 2.0},
    "HI-5678": {"length": 250, "width": 180, "height": 90, "weight": 1.5},
    "AE-TOT": {"length": 330, "width": 270, "height": 280, "weight": 10.8},
    "AE-9": {"length": 120, "width": 110, "height": 60, "weight": 0.5},
}


# ---------- still-armed-at-exit safeguard (structural) ----------

def test_disarm_reminder_is_loud_when_still_armed():
    msg = disarm_reminder({"CC_LIVE_PROMOTION": "true"})
    assert msg is not None
    assert "ARMED" in msg and "unset CC_LIVE_PROMOTION" in msg


@pytest.mark.parametrize("env", [{}, {"CC_LIVE_PROMOTION": "false"}, {"CC_LIVE_PROMOTION": ""}])
def test_disarm_reminder_quiet_when_disarmed(env):
    assert disarm_reminder(env) is None


def test_finalize_exit_forces_nonzero_when_still_armed():
    # The structural safeguard: a still-armed env can NEVER yield a 0 (silent-success) exit.
    code, msg = finalize_exit({"CC_LIVE_PROMOTION": "true"}, 0)
    assert code >= 3 and msg is not None, "armed-at-exit must force a non-zero code + a loud msg"
    code2, msg2 = finalize_exit({"CC_LIVE_PROMOTION": "true"}, 1)
    assert code2 >= 3 and msg2 is not None


def test_finalize_exit_passes_through_when_disarmed():
    assert finalize_exit({}, 0) == (0, None)
    assert finalize_exit({"CC_LIVE_PROMOTION": "false"}, 2) == (2, None)


# ---------- target selection: cover the prefix shapes, report unresolvable ----------

def test_select_covers_prefix_shapes_and_reports_unresolvable():
    cands = [
        LiveCandidate("p-fp", "FP-1234"),
        LiveCandidate("p-hi", "HI-5678"),
        LiveCandidate("p-ae", "AE-9"),
        LiveCandidate("p-sae", "SAE-TOT"),   # uppercase-S mirror → strip → AE-TOT
        LiveCandidate("p-zz", "ZZ-999"),      # no captured base → unresolvable
    ]
    plan = select_live_proving_targets(cands, CAPTURED, max_total=5)

    by_code = {t.code: t for t in plan.selected}
    assert set(by_code) == {"FP-1234", "HI-5678", "AE-9", "SAE-TOT"}, "one per prefix shape"
    assert by_code["FP-1234"].base_code == "FP-1234", "direct-match branch"
    assert by_code["SAE-TOT"].base_code == "AE-TOT", "uppercase-S strip branch on a real code"
    assert by_code["SAE-TOT"].desired_dims == CAPTURED["AE-TOT"]
    assert any(u["code"] == "ZZ-999" for u in plan.unresolvable)
    assert "ZZ-999" not in by_code, "an unresolvable SKU is never selected for write"


def test_build_plan_gathers_then_selects(monkeypatch):
    # build_plan gathers active LIVE candidates (search scoped to the live customer) then selects.
    seen_kwargs = {}

    def fake_search(client, **kw):
        seen_kwargs.update(kw)
        return iter([
            {"id": "p-fp", "references": {"code": "FP-1234"}},
            {"id": "p-zz", "references": {"code": "ZZ-999"}},
        ])

    monkeypatch.setattr("dims_write.live_proving.search_warehouse_products", fake_search)
    plan = build_live_proving_plan(_client(), CAPTURED)

    assert seen_kwargs.get("customer_id") == LIVE_FORAGE_CUSTOMER_ID, "gather is scoped to LIVE Forage"
    assert seen_kwargs.get("active_only") is True
    assert [t.code for t in plan.selected] == ["FP-1234"]
    assert any(u["code"] == "ZZ-999" for u in plan.unresolvable)


# ---------- the run respects the 5a gate (don't re-prove it) ----------

def test_run_refuses_when_promotion_not_armed():
    # 5b is a live run; without CC_LIVE_PROMOTION armed it must refuse — and NEVER _mutate.
    client = _client()
    transport = LiveTransport({"p-fp": _live_product("p-fp", "FP-1234")})
    client._http = transport
    plan = LiveProvingPlan(
        selected=[LiveTarget("p-fp", "FP-1234", "FP-1234", CAPTURED["FP-1234"])],
        unresolvable=[],
    )
    with pytest.raises(LiveProvingRefused):
        run_live_proving(client=client, config=_disarmed_cfg(), plan=plan,
                         approval_token=SECRET, confirm=lambda info: "FP-1234")
    assert transport.patches == [], "a disarmed run must not PATCH the live id"


def test_run_logs_live_promotion_armed_warning(caplog):
    client = _client()
    client._http = LiveTransport({"p-fp": _live_product("p-fp", "FP-1234")})
    plan = LiveProvingPlan(selected=[], unresolvable=[])
    with caplog.at_level(logging.WARNING, logger="dims_write.roundtrip"):
        run_live_proving(client=client, config=_armed_cfg(), plan=plan,
                         approval_token=SECRET, confirm=lambda info: "")
    assert "LIVE PROMOTION ARMED" in caplog.text


# ---------- the per-SKU confirm: typed code MUST match the SKU being written ----------

def _one_target_plan():
    return LiveProvingPlan(
        selected=[LiveTarget("p-fp", "FP-1234", "FP-1234", CAPTURED["FP-1234"])],
        unresolvable=[],
    )


def test_correct_code_typed_writes_the_live_sku():
    client = _client()
    transport = LiveTransport({"p-fp": _live_product("p-fp", "FP-1234")})
    client._http = transport

    report = run_live_proving(client=client, config=_armed_cfg(), plan=_one_target_plan(),
                              approval_token=SECRET, confirm=lambda info: "FP-1234")

    assert len(transport.patches) == 1, "exactly one live PATCH"
    assert transport.patches[0]["pid"] == "p-fp"
    assert [w["code"] for w in report.written] == ["FP-1234"]
    assert report.written[0]["after"]["length"] == 300, "read-back reflects the written dims"


def test_wrong_code_typed_does_not_patch():
    client = _client()
    transport = LiveTransport({"p-fp": _live_product("p-fp", "FP-1234")})
    client._http = transport

    # Operator types a DIFFERENT real SKU code — must not write the one on screen.
    report = run_live_proving(client=client, config=_armed_cfg(), plan=_one_target_plan(),
                              approval_token=SECRET, confirm=lambda info: "FP-9999")

    assert transport.patches == [], "a mismatched confirm must NOT PATCH"
    assert report.written == []
    assert report.skipped and report.skipped[0]["code"] == "FP-1234"


def test_bare_go_does_not_patch():
    # The whole point of 5b's confirm: a muscle-memory `go` (which worked in the sandbox soak)
    # must NOT pass here — it isn't the SKU code.
    client = _client()
    transport = LiveTransport({"p-fp": _live_product("p-fp", "FP-1234")})
    client._http = transport
    report = run_live_proving(client=client, config=_armed_cfg(), plan=_one_target_plan(),
                              approval_token=SECRET, confirm=lambda info: "go")
    assert transport.patches == [], "a bare 'go' must NOT pass the per-SKU confirm"
    assert report.written == []


@pytest.mark.parametrize("typed", ["", "   ", "fp-1234"])
def test_empty_or_miscased_confirm_does_not_patch(typed):
    # Empty/blank never confirms; case must match exactly (codes are uppercase) — a near-miss
    # is a skip, not a write.
    client = _client()
    transport = LiveTransport({"p-fp": _live_product("p-fp", "FP-1234")})
    client._http = transport
    report = run_live_proving(client=client, config=_armed_cfg(), plan=_one_target_plan(),
                              approval_token=SECRET, confirm=lambda info: typed)
    assert transport.patches == [], f"confirm {typed!r} must NOT PATCH"


def test_per_sku_confirm_is_independent_no_batch():
    # Three SKUs; the operator confirms #1 and #3 correctly, fat-fingers #2. Only #1 and #3
    # write — proving the confirm is per-SKU (one at a time), with NO batch `go`.
    client = _client()
    transport = LiveTransport({
        "p1": _live_product("p1", "FP-1"),
        "p2": _live_product("p2", "HI-2"),
        "p3": _live_product("p3", "AE-9"),
    })
    client._http = transport
    plan = LiveProvingPlan(selected=[
        LiveTarget("p1", "FP-1", "FP-1", {"length": 10, "width": 10, "height": 10}),
        LiveTarget("p2", "HI-2", "HI-2", {"length": 20, "width": 20, "height": 20}),
        LiveTarget("p3", "AE-9", "AE-9", CAPTURED["AE-9"]),
    ], unresolvable=[])

    typed_by_code = {"FP-1": "FP-1", "HI-2": "WRONG", "AE-9": "AE-9"}
    report = run_live_proving(client=client, config=_armed_cfg(), plan=plan,
                              approval_token=SECRET, confirm=lambda info: typed_by_code[info.code])

    assert {w["code"] for w in report.written} == {"FP-1", "AE-9"}
    assert [c["pid"] for c in transport.patches] == ["p1", "p3"], "only the matched SKUs PATCH"
    assert any(s["code"] == "HI-2" for s in report.skipped)


def test_confirm_receives_the_full_mapping_info():
    # The hard-stop info handed to the operator carries the mapping decision + the diff.
    client = _client()
    client._http = LiveTransport({"p-sae": _live_product("p-sae", "SAE-TOT")})
    plan = LiveProvingPlan(
        selected=[LiveTarget("p-sae", "SAE-TOT", "AE-TOT", CAPTURED["AE-TOT"])],
        unresolvable=[],
    )
    seen = []
    run_live_proving(client=client, config=_armed_cfg(), plan=plan, approval_token=SECRET,
                     confirm=lambda info: (seen.append(info) or ""))
    info = seen[0]
    assert info.code == "SAE-TOT" and info.base_code == "AE-TOT"
    assert info.current_dims["length"] is None  # live has no dims yet
    assert info.desired_dims == CAPTURED["AE-TOT"]
    assert info.diff["length"] == 330
    assert info.endpoint == "/warehouse-products/p-sae"


def test_report_carries_unresolvable_and_armed_flag():
    client = _client()
    client._http = LiveTransport({"p-fp": _live_product("p-fp", "FP-1234")})
    plan = LiveProvingPlan(
        selected=[LiveTarget("p-fp", "FP-1234", "FP-1234", CAPTURED["FP-1234"])],
        unresolvable=[{"code": "ZZ-999", "reason": "no captured base code"}],
    )
    report = run_live_proving(client=client, config=_armed_cfg(), plan=plan,
                              approval_token=SECRET, confirm=lambda info: "FP-1234")
    assert report.unresolvable == [{"code": "ZZ-999", "reason": "no captured base code"}]
    assert report.promotion_was_armed is True


# ---------- package export ----------

def test_exported_from_package():
    from dims_write import run_live_proving as pkg_run, build_live_proving_plan as pkg_plan
    assert pkg_run is run_live_proving
    assert pkg_plan is build_live_proving_plan
