"""Tests for the web layer (disk readers + FastAPI routes)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import pytest


def _make_run(base: Path, run_id: str) -> Path:
    run = base / run_id
    (run / "VIC-bench-01").mkdir(parents=True)
    manifest = {
        "generated_at": "2026-06-04T08:12:00",
        "settings": {"status": "AWAITING_PICK_AND_PACK", "customer_name": None,
                     "pallet_fraction_threshold": 0.65, "early_release_cartons": 25,
                     "run_group_col": "delivery_state", "lines_per_hour": 60,
                     },
        "summary": {"n_waves": 1, "n_orders_total": 22, "n_orders_skipped": 1,
                    "n_pick_lines_total": 3, "n_lines_unallocated": 2,
                    "n_skus_unallocated": 1},
        "waves": [{"wave_id": "VIC-bench-01", "stream": "3_wave_bench",
                   "run_group": "VIC", "receive_date": None, "total_cartons": 45,
                   "total_lines": 3, "n_orders": 22, "estimated_walk_m": 240.0}],
    }
    (run / "manifest.json").write_text(json.dumps(manifest))
    pd.DataFrame([
        {"walk_index": 1, "location": "A-01-1-1", "product_code": "FRG-0042",
         "product_name": "Oats", "qty_cartons": 14, "cartons_running_total": 14,
         "contributing_so_refs": "SO-1"},
    ]).to_csv(run / "VIC-bench-01" / "VIC-bench-01_picks.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-1", "customer_name": "Forage", "delivery_state": "VIC",
         "cartons": 14, "lines": 1},
    ]).to_csv(run / "VIC-bench-01" / "VIC-bench-01_orders.csv", index=False)
    pd.DataFrame([
        {"wave_id": "VIC-bench-01", "so_ref": "SO-9",
         "reason": "missing pick location for SKU(s)", "missing_skus": "FRG-9"},
    ]).to_csv(run / "skipped_orders.csv", index=False)
    return run


def test_list_runs_newest_first(tmp_path):
    from web.runs import list_runs
    _make_run(tmp_path, "20260603_080000")
    _make_run(tmp_path, "20260604_081200")
    runs = list_runs(tmp_path)
    assert [r["run_id"] for r in runs] == ["20260604_081200", "20260603_080000"]
    assert runs[0]["n_waves"] == 1
    # Fix 2: unallocated counts surfaced in list_runs
    assert runs[0]["n_lines_unallocated"] == 2
    assert runs[0]["n_skus_unallocated"] == 1


def test_get_run_includes_waves_and_skipped(tmp_path):
    from web.runs import get_run
    _make_run(tmp_path, "20260604_081200")
    run = get_run(tmp_path, "20260604_081200")
    assert run["summary"]["n_orders_total"] == 22
    assert run["waves"][0]["wave_id"] == "VIC-bench-01"
    assert run["skipped"][0]["so_ref"] == "SO-9"


def test_get_wave_reads_pick_and_order_csvs(tmp_path):
    from web.runs import get_wave
    _make_run(tmp_path, "20260604_081200")
    wave = get_wave(tmp_path, "20260604_081200", "VIC-bench-01")
    assert wave["pick_lines"][0]["location"] == "A-01-1-1"
    assert wave["orders"][0]["so_ref"] == "SO-1"


def test_file_path_rejects_traversal(tmp_path):
    from web.runs import file_path
    _make_run(tmp_path, "20260604_081200")
    with pytest.raises(ValueError):
        file_path(tmp_path, "20260604_081200", "VIC-bench-01", "../../secret")
    good = file_path(tmp_path, "20260604_081200", "VIC-bench-01",
                     "VIC-bench-01_picks.csv")
    assert good.exists()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import web.app as appmod
    app = appmod.create_app(repo_root=tmp_path)
    return TestClient(app)


def test_index_renders_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Wave Pick Console" in r.text
    assert "AWAITING_PICK_AND_PACK" in r.text
    assert 'name="pallet_fraction_threshold"' in r.text


def test_index_lists_existing_runs(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/")
    assert "20260604_081200" in r.text


def test_post_runs_starts_job_and_returns_progress_panel(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import web.app as appmod
    from wave_runner import RunResult, ProgressEvent

    def fake_run(settings, progress):
        progress(ProgressEvent("pull", "pulling", "info"))
        progress(ProgressEvent("done", "done", "ok"))
        return RunResult("20260604_081200", tmp_path, {"n_waves": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake_run
    client = TestClient(app)
    r = client.post("/runs", data={
        "status": "AWAITING_PICK_AND_PACK", "customer_name": "",
        "pallet_fraction_threshold": "0.65", "early_release_cartons": "25",
        "run_group_col": "delivery_state"})
    assert r.status_code == 200
    assert "sse" in r.text.lower()           # the panel wires up an SSE source
    assert "/stream" in r.text


def test_index_shows_soh_always_live(client):
    r = client.get("/")
    assert 'name="soh_fallback"' not in r.text
    assert "no stale fallback" in r.text



def test_post_runs_rejects_when_active(tmp_path):
    from fastapi.testclient import TestClient
    import web.app as appmod
    import time
    from wave_runner import RunResult, ProgressEvent

    def slow(settings, progress):
        time.sleep(0.3)
        return RunResult("s", tmp_path, {}, "success")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = slow
    client = TestClient(app)
    form = {"status": "X", "customer_name": "", "pallet_fraction_threshold": "0.7",
            "early_release_cartons": "30", "run_group_col": "delivery_state"}
    client.post("/runs", data=form)
    r2 = client.post("/runs", data=form)
    assert "in progress" in r2.text.lower()


def test_stream_emits_events(tmp_path):
    from fastapi.testclient import TestClient
    import web.app as appmod
    from wave_runner import RunResult, ProgressEvent

    def fake_run(settings, progress):
        progress(ProgressEvent("pull", "pulling orders", "info"))
        progress(ProgressEvent("done", "all done", "ok"))
        return RunResult("r", tmp_path, {"n_waves": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake_run
    client = TestClient(app)
    form = {"status": "X", "customer_name": "", "pallet_fraction_threshold": "0.7",
            "early_release_cartons": "30", "run_group_col": "delivery_state"}
    job_id = client.post("/runs", data=form).headers["x-job-id"]
    with client.stream("GET", f"/runs/job/{job_id}/stream") as s:
        body = "".join(chunk for chunk in s.iter_text())
    assert "pulling orders" in body
    assert "event: done" in body


def test_run_detail_page(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200")
    assert r.status_code == 200
    assert "VIC-bench-01" in r.text
    assert "bench" in r.text                 # stream pill
    assert "SO-9" in r.text                   # skipped order
    assert "Unallocated lines" in r.text      # Fix 2: unallocated stat tile


def test_wave_detail_page(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200/waves/VIC-bench-01")
    assert r.status_code == 200
    assert "A-01-1-1" in r.text               # pick line location
    assert "FRG-0042" in r.text


def test_download_picks_csv(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200/files/VIC-bench-01/VIC-bench-01_picks.csv")
    assert r.status_code == 200
    assert "A-01-1-1" in r.text


def test_download_traversal_404(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200/files/VIC-bench-01/..%2f..%2fmanifest.json")
    assert r.status_code == 404


def test_index_form_defaults_to_predicted_run(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "predicted_run" in resp.text
