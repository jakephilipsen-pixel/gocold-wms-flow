"""M-DIMS-5c probe — read-only CT UoM name-shape census, CC-mocked.

The first armed 5c live run fail-fast halted on SKU #1 (AE-BLA) with a 422:
``{"field":"/unitOfMeasures/CT/name","message":"Must be between 3 and 64 characters."}`` —
ZERO dims written. The dims payload was fine; CC rejected because add-ing dimension
sub-fields under ``/unitOfMeasures/CT/`` makes it validate the WHOLE CT UoM object, and that
UoM's ``name`` was missing/too short. This probe censuses, READ-ONLY, whether each live CT
UoM has a valid (3–64 char) name — to decide bad-data-exception vs systemic-prerequisite.

No writes anywhere: the census uses GETs only and never flips ``write_enabled``.
"""
from __future__ import annotations

import time

import httpx

from dims_write.ct_probe import (
    classify_ct_uom,
    ct_uom_name,
    probe_ct_uom_names,
    CtUomProbe,
    CtUomCensus,
    CT_NAME_MIN_CHARS,
    CT_NAME_MAX_CHARS,
)
from dims_write.live_proving import LiveCandidate
from cc_client.client import CartonCloudClient, _Token

LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"


def _uom(*, code=None, name=None):
    obj = {"baseQty": 1, "weight": 0, "barcode": "bc"}
    if code is not None:
        obj["code"] = code
    if name is not None:
        obj["name"] = name
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


# ---------- classify_ct_uom — the pure bucketing logic ----------

def test_no_ct_uom_is_bucketed_no_ct():
    raw = _product("p", "FP-1", uoms={"EA": _uom()})
    probe = classify_ct_uom("FP-1", "p", raw)
    assert probe.bucket == "no-ct"
    assert probe.uom is None


def test_ct_uom_with_valid_name_is_complete():
    raw = _product("p", "FP-1", uoms={"EA": _uom(), "CT": _uom(name="Carton of 12")})
    probe = classify_ct_uom("FP-1", "p", raw)
    assert probe.bucket == "ct-complete"
    assert probe.uom == "CT"
    assert probe.name == "Carton of 12"
    assert probe.name_len == len("Carton of 12")


def test_ct_uom_with_missing_name_is_incomplete():
    # AE-BLA's actual failure: the CT UoM exists but carries no `name` key.
    raw = _product("p", "AE-BLA", uoms={"EA": _uom(), "CT": _uom()})
    probe = classify_ct_uom("AE-BLA", "p", raw)
    assert probe.bucket == "ct-incomplete"
    assert probe.uom == "CT"
    assert probe.name is None
    assert probe.name_len is None
    assert "missing" in probe.reason


def test_ct_uom_with_too_short_name_is_incomplete():
    raw = _product("p", "FP-2", uoms={"CT": _uom(name="CT"), "EA": _uom()})
    probe = classify_ct_uom("FP-2", "p", raw)
    assert probe.bucket == "ct-incomplete"
    assert probe.name_len == 2
    assert probe.name_len < CT_NAME_MIN_CHARS


def test_ct_uom_with_empty_name_is_incomplete():
    raw = _product("p", "FP-3", uoms={"CT": _uom(name=""), "EA": _uom()})
    probe = classify_ct_uom("FP-3", "p", raw)
    assert probe.bucket == "ct-incomplete"
    assert probe.name_len == 0


def test_ct_uom_with_overlong_name_is_incomplete():
    long = "x" * (CT_NAME_MAX_CHARS + 1)
    raw = _product("p", "FP-4", uoms={"CT": _uom(name=long), "EA": _uom()})
    probe = classify_ct_uom("FP-4", "p", raw)
    assert probe.bucket == "ct-incomplete"
    assert probe.name_len == CT_NAME_MAX_CHARS + 1


def test_name_at_exact_boundaries_is_complete():
    for n in (CT_NAME_MIN_CHARS, CT_NAME_MAX_CHARS):
        raw = _product("p", "FP-B", uoms={"CT": _uom(name="x" * n)})
        assert classify_ct_uom("FP-B", "p", raw).bucket == "ct-complete"


def test_ct_uom_name_reads_the_resolved_uom_under_uuid_keying():
    # Shape B: UoMs keyed by uuid; the CT object carries its code + name.
    raw = _product(
        "p", "FP-5",
        uoms={"u-ea": _uom(code="EA", name="Each"),
              "u-ct": _uom(code="CT", name="Carton")},
        default="u-ea",
    )
    assert ct_uom_name(raw, "u-ct") == "Carton"
    assert classify_ct_uom("FP-5", "p", raw).bucket == "ct-complete"


# ---------- probe_ct_uom_names — the read-only census over candidates ----------

class _GetOnlyTransport:
    """GET returns the product; ANY non-GET fails the test (the probe must never write)."""

    def __init__(self, products):
        self.products = {pid: dict(p) for pid, p in products.items()}
        self.calls = []

    def request(self, method, url, *, params=None, json=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers})
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
        _product("p1", "FP-1", uoms={"EA": _uom()}),                       # no-ct
        _product("p2", "FP-2", uoms={"EA": _uom(), "CT": _uom(name="Carton of 6")}),  # complete
        _product("p3", "AE-BLA", uoms={"EA": _uom(), "CT": _uom()}),       # incomplete (missing name)
        _product("p4", "FP-4", uoms={"CT": _uom(name="CT")}),             # incomplete (short)
    ]
    client = _client_with(*raws)
    cands = [LiveCandidate(product_id=r["id"], code=r["references"]["code"]) for r in raws]

    census = probe_ct_uom_names(client, candidates=cands, pace_seconds=0.0)

    assert isinstance(census, CtUomCensus)
    assert len(census.no_ct) == 1
    assert len(census.ct_complete) == 1
    assert len(census.ct_incomplete) == 2
    assert {p.code for p in census.ct_incomplete} == {"AE-BLA", "FP-4"}
    # never wrote: only GETs were issued, one per candidate.
    assert all(c["method"] == "GET" for c in client._http.calls)
    assert len(client._http.calls) == len(cands)


def test_census_is_read_only_does_not_require_write_enabled():
    raw = _product("p1", "FP-1", uoms={"CT": _uom(name="Carton")})
    client = _client_with(raw)
    assert client.write_enabled is False
    census = probe_ct_uom_names(
        client, candidates=[LiveCandidate(product_id="p1", code="FP-1")], pace_seconds=0.0
    )
    assert len(census.ct_complete) == 1
