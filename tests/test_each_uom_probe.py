"""M-DIMS-5d probe — read-only Base/Each UoM name-shape census, CC-mocked.

5c (write dims to the CT carton UoM) is dropped from automated scope: CC's name-validation trap
(every CT UoM is named "CT", 2 chars < the 3-char floor) 422s the dims PATCH. The automated
target moves to the Each/Base UoM. Before building the each-write, this probe checks — read-only
— whether the Base UoMs carry valid names or would hit the SAME trap. No writes anywhere: the
census uses GETs only and never flips ``write_enabled``.
"""
from __future__ import annotations

import time

import httpx

from dims_write.each_probe import (
    classify_each_uom,
    resolve_base_uom,
    probe_each_uom_names,
    EachUomProbe,
    EachUomCensus,
    BUCKET_WRITABLE,
    BUCKET_BLOCKED,
    BUCKET_NO_EACH,
)
from dims_write.uom_name import UOM_NAME_MIN_CHARS
from dims_write.live_proving import LiveCandidate
from cc_client.client import CartonCloudClient, _Token

LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"


def _uom(*, code=None, name=None, length=None, width=None, height=None):
    obj = {"baseQty": 1, "weight": 0, "barcode": "bc"}
    if code is not None:
        obj["code"] = code
    if name is not None:
        obj["name"] = name
    for k, v in (("length", length), ("width", width), ("height", height)):
        if v is not None:
            obj[k] = v
    return obj


def _product(pid, sku_code, *, uoms, default="EA"):
    return {
        "id": pid,
        "customer": {"id": LIVE_FORAGE_CUSTOMER_ID},
        "details": {"active": True},
        "references": {"code": sku_code},
        "defaultUnitOfMeasure": default,
        "unitOfMeasures": uoms,
    }


# ---------- resolve_base_uom ----------

def test_resolve_base_uom_returns_default_uom_object():
    raw = _product("p", "FP-1", uoms={"EA": _uom(name="Each"), "CT": _uom(name="Carton")}, default="EA")
    uom_id, obj = resolve_base_uom(raw)
    assert uom_id == "EA"
    assert obj["name"] == "Each"


def test_resolve_base_uom_none_when_default_missing_from_uoms():
    raw = _product("p", "FP-1", uoms={"EA": _uom()}, default="NOPE")
    assert resolve_base_uom(raw) == (None, {})


# ---------- classify_each_uom ----------

def test_each_with_valid_name_is_writable():
    raw = _product("p", "FP-1", uoms={"EA": _uom(name="Each")}, default="EA")
    probe = classify_each_uom("FP-1", "p", raw)
    assert probe.bucket == BUCKET_WRITABLE
    assert probe.uom == "EA"
    assert probe.uom_code == "EA"
    assert probe.has_dims is False


def test_each_with_short_name_is_blocked():
    # The exact CT trap, but on the each: a 2-char name fails CC's 3-char floor.
    raw = _product("p", "FP-2", uoms={"EA": _uom(name="EA")}, default="EA")
    probe = classify_each_uom("FP-2", "p", raw)
    assert probe.bucket == BUCKET_BLOCKED
    assert probe.name_len == 2
    assert probe.name_len < UOM_NAME_MIN_CHARS


def test_each_with_missing_name_is_blocked():
    raw = _product("p", "FP-3", uoms={"EA": _uom()}, default="EA")
    probe = classify_each_uom("FP-3", "p", raw)
    assert probe.bucket == BUCKET_BLOCKED
    assert "missing" in probe.reason


def test_no_default_uom_is_no_each():
    raw = _product("p", "FP-4", uoms={"EA": _uom(name="Each")}, default=None)
    probe = classify_each_uom("FP-4", "p", raw)
    assert probe.bucket == BUCKET_NO_EACH
    assert probe.uom is None


def test_has_dims_true_when_base_uom_already_carries_lwh():
    raw = _product("p", "FP-5", uoms={"EA": _uom(name="Each", length=30, width=20, height=10)}, default="EA")
    probe = classify_each_uom("FP-5", "p", raw)
    assert probe.has_dims is True
    assert probe.bucket == BUCKET_WRITABLE


def test_uom_code_falls_back_to_id_under_uuid_keying():
    raw = _product(
        "p", "FP-6",
        uoms={"u-ea": _uom(code="EA", name="Each")},
        default="u-ea",
    )
    probe = classify_each_uom("FP-6", "p", raw)
    assert probe.uom == "u-ea"
    assert probe.uom_code == "EA"


# ---------- probe_each_uom_names — read-only census ----------

class _GetOnlyTransport:
    """GET returns the product; ANY non-GET fails the test (the probe must never write)."""

    def __init__(self, products):
        self.products = {pid: dict(p) for pid, p in products.items()}
        self.calls = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url})
        assert method == "GET", f"probe must be read-only, got {method}"
        pid = url.rstrip("/").split("/")[-1]
        return httpx.Response(200, json=dict(self.products.get(pid, {})))


def _client_with(*raws):
    c = CartonCloudClient(client_id="id", client_secret="sec", tenant_id="T",
                          base_url="https://cc.example", write_enabled=False)
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    c._http = _GetOnlyTransport({r["id"]: r for r in raws})
    return c


def test_census_buckets_a_mixed_cohort_and_only_GETs():
    raws = [
        _product("p1", "FP-1", uoms={"EA": _uom(name="Each")}, default="EA"),           # writable
        _product("p2", "FP-2", uoms={"EA": _uom(name="EA")}, default="EA"),             # blocked (short)
        _product("p3", "FP-3", uoms={"EA": _uom()}, default="EA"),                      # blocked (missing)
        _product("p4", "FP-4", uoms={"EA": _uom(name="Each")}, default="GONE"),         # no-each
    ]
    client = _client_with(*raws)
    cands = [LiveCandidate(product_id=r["id"], code=r["references"]["code"]) for r in raws]

    census = probe_each_uom_names(client, candidates=cands, pace_seconds=0.0)

    assert isinstance(census, EachUomCensus)
    assert len(census.each_writable) == 1
    assert len(census.each_blocked) == 2
    assert len(census.no_each) == 1
    assert {p.code for p in census.each_blocked} == {"FP-2", "FP-3"}
    assert all(c["method"] == "GET" for c in client._http.calls)
    assert len(client._http.calls) == len(cands)


def test_census_does_not_require_write_enabled():
    raw = _product("p1", "FP-1", uoms={"EA": _uom(name="Each")}, default="EA")
    client = _client_with(raw)
    assert client.write_enabled is False
    census = probe_each_uom_names(
        client, candidates=[LiveCandidate(product_id="p1", code="FP-1")], pace_seconds=0.0
    )
    assert len(census.each_writable) == 1
