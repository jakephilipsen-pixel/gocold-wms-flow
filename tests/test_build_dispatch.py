"""Integration: orchestrator produces a plan from fixture pulls (offline)."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_orchestrator():
    p = ROOT / "scripts" / "build_dispatch.py"
    spec = importlib.util.spec_from_file_location("_build_dispatch", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CONSIGNMENTS = [
    {"details": {"deliver": {"address": {"lines": ["1 A St"],
     "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}},
     "runsheet": {"name": "RS-1", "date": "2026-06-03"},
     "deliveryRun": {"name": "West-Tue"}}}
    for _ in range(3)
]
_OPEN_ORDERS = [
    {"id": "SO9", "references": {"customer": "SO-9"},
     "details": {"deliver": {"address": {"lines": ["1 A St"],
      "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}}}}
]


def test_run_dispatch_builds_plan(monkeypatch, tmp_path):
    mod = _load_orchestrator()
    monkeypatch.setattr(mod, "search_consignments",
                        lambda *a, **k: iter(_CONSIGNMENTS))
    monkeypatch.setattr(mod, "search_outbound_orders",
                        lambda *a, **k: iter(_OPEN_ORDERS))
    monkeypatch.setattr(mod, "CartonCloudClient",
                        type("C", (), {"from_env": staticmethod(lambda: object())}))

    plan = mod.run_dispatch(
        client=object(),
        zones_path=ROOT / "config" / "dispatch_zones.toml",
        history_days=90, as_of=date(2026, 6, 5))

    assert len(plan.assignments) == 1
    assert plan.assignments[0].predicted_run == "West-Tue"
