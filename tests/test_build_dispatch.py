"""Integration: run_dispatch builds a plan from fixture pulls (offline)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from dispatch import runner as mod
from dispatch.runner import run_dispatch

ROOT = Path(__file__).resolve().parent.parent

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


def test_run_dispatch_builds_plan(monkeypatch):
    monkeypatch.setattr(mod, "search_consignments",
                        lambda *a, **k: iter(_CONSIGNMENTS))
    monkeypatch.setattr(mod, "search_outbound_orders",
                        lambda *a, **k: iter(_OPEN_ORDERS))

    plan = run_dispatch(
        client=object(),
        zones_path=ROOT / "config" / "dispatch_zones.toml",
        history_days=90, as_of=date(2026, 6, 5))

    assert len(plan.assignments) == 1
    assert plan.assignments[0].predicted_run == "West-Tue"
