"""run_dispatch_job: emits progress, writes a stamped plan, reports status."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from dispatch import runner as mod
from dispatch.runner import DispatchRunSettings, run_dispatch_job

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


def _settings(tmp_path: Path) -> DispatchRunSettings:
    return DispatchRunSettings(
        repo_root=tmp_path, history_days=90, skip_learn=False,
        zones_path=ROOT / "config" / "dispatch_zones.toml")


def _patch(monkeypatch):
    monkeypatch.setattr(mod, "search_consignments",
                        lambda *a, **k: iter(_CONSIGNMENTS))
    monkeypatch.setattr(mod, "search_outbound_orders",
                        lambda *a, **k: iter(_OPEN_ORDERS))
    monkeypatch.setattr(mod.CartonCloudClient, "from_env",
                        staticmethod(lambda: object()))


def test_run_dispatch_job_writes_plan_and_emits(monkeypatch, tmp_path):
    _patch(monkeypatch)
    events = []
    result = run_dispatch_job(_settings(tmp_path), events.append,
                              as_of=date(2026, 6, 5))

    assert result.status == "success"
    assert result.counts["assignments"] == 1
    assert result.counts["runs"] == 1
    base = tmp_path / "data" / "processed" / "dispatch"
    plan_dirs = list(base.iterdir())
    assert len(plan_dirs) == 1
    assert (plan_dirs[0] / "suggested_runs.csv").exists()
    stages = [e.stage for e in events]
    assert "predict" in stages and stages[-1] == "done"
    assert events[-1].level != "error"


def test_run_dispatch_job_dry_run_writes_nothing(monkeypatch, tmp_path):
    _patch(monkeypatch)
    result = run_dispatch_job(_settings(tmp_path), lambda e: None,
                              write=False, as_of=date(2026, 6, 5))
    assert result.out_dir is None
    assert not (tmp_path / "data" / "processed" / "dispatch").exists()
    assert result.counts["assignments"] == 1


def test_run_dispatch_job_no_orders_is_empty(monkeypatch, tmp_path):
    _patch(monkeypatch)
    monkeypatch.setattr(mod, "search_outbound_orders", lambda *a, **k: iter([]))
    result = run_dispatch_job(_settings(tmp_path), lambda e: None,
                              as_of=date(2026, 6, 5))
    assert result.status == "empty"
    assert result.counts["assignments"] == 0
