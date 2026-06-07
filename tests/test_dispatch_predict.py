from __future__ import annotations

from datetime import date

from dispatch.history import RunCandidate, RunHistoryModel
from dispatch.predict import predict_runs
from dispatch.zones import ZoneConfig, ZoneRule


def _model(by_address):
    from datetime import datetime
    return RunHistoryModel(by_address=by_address, window_days=90,
                           half_life_days=30, generated_at=datetime(2026, 6, 5))


_ZONES = ZoneConfig(zones=[ZoneRule("Metro Melbourne", "VIC", [(3000, 3207)])],
                    fallback="Unzoned")


def _order(so_id, suburb, postcode, state="VIC"):
    return {"so_id": so_id, "so_ref": f"SO-{so_id}",
            "address": {"lines": [f"{so_id} A St"], "suburb": suburb,
                        "state": state, "postcode": postcode}}


def test_stable_address_goes_to_assignments():
    key = "1 a st scoresby vic 3179"
    model = _model({key: [RunCandidate("West-Tue", 9.0, 9, date(2026, 6, 3))]})
    plan = predict_runs([_order("1", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5))
    assert len(plan.assignments) == 1
    a = plan.assignments[0]
    assert a.predicted_run == "West-Tue"
    assert a.flag == "stable"
    assert a.confidence == 1.0
    assert plan.review == []


def test_mixed_address_goes_to_review_with_alternatives():
    key = "2 a st scoresby vic 3179"
    model = _model({key: [RunCandidate("West-Tue", 5.0, 5, date(2026, 6, 3)),
                          RunCandidate("West-Wed", 4.0, 4, date(2026, 6, 2))]})
    plan = predict_runs([_order("2", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5))
    assert plan.assignments == []
    r = plan.review[0]
    assert r.flag == "mixed"
    assert r.predicted_run == "West-Tue"
    assert "West-Wed" in r.alternatives


def test_new_address_uses_zone_fallback_and_review():
    model = _model({})
    plan = predict_runs([_order("3", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5))
    r = plan.review[0]
    assert r.flag == "new_address"
    assert r.predicted_run is None
    assert "Metro Melbourne" in r.reason


def test_stale_address_flagged():
    key = "4 a st scoresby vic 3179"
    model = _model({key: [RunCandidate("West-Tue", 1.0, 1, date(2026, 4, 1))]})
    plan = predict_runs([_order("4", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5), stale_days=30)
    assert plan.review[0].flag == "stale"


def test_missing_address_flagged_no_address():
    order = {"so_id": "5", "so_ref": "SO-5", "address": None}
    plan = predict_runs([order], _model({}), _ZONES, as_of=date(2026, 6, 5))
    assert plan.review[0].flag == "no_address"


def test_carrier_order_split_out():
    order = _order("6", "Scoresby", "3179")
    order["carrier"] = "TollExpress"
    plan = predict_runs([order], _model({}), _ZONES, as_of=date(2026, 6, 5),
                        carrier_rule=lambda o: o.get("carrier"))
    assert "TollExpress" in plan.carriers
    assert plan.assignments == [] and plan.review == []
