"""Tests for the dispatch console (routes + SSE)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_COLS = ["so_ref", "so_id", "predicted_run", "confidence", "flag", "reason",
         "alternatives", "full_address", "street", "suburb", "state", "postcode"]


def _make_plan(base: Path, stamp: str) -> Path:
    d = base / stamp
    d.mkdir(parents=True)
    pd.DataFrame([
        {"so_ref": "SO-1", "so_id": "1", "predicted_run": "West-Tue",
         "confidence": 1.0, "flag": "stable", "reason": "r", "alternatives": "",
         "full_address": "1 A St, Scoresby VIC 3179", "street": "1 A St",
         "suburb": "Scoresby", "state": "VIC", "postcode": "3179"},
    ], columns=_COLS).to_csv(d / "suggested_runs.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-3", "so_id": "3", "predicted_run": "", "confidence": 0.0,
         "flag": "new_address", "reason": "no history; zone=Geelong",
         "alternatives": "", "full_address": "9 New Rd, Geelong VIC 3220",
         "street": "9 New Rd", "suburb": "Geelong", "state": "VIC",
         "postcode": "3220"},
    ], columns=_COLS).to_csv(d / "review.csv", index=False)
    (d / "summary.md").write_text("# Dispatch run prediction summary\n")
    (d / "run_West-Tue.xlsx").write_bytes(b"PK\x03\x04stub")
    return d


def _client(tmp_path):
    from fastapi.testclient import TestClient
    import web_dispatch.app as appmod
    return appmod, TestClient(appmod.create_app(repo_root=tmp_path))


def test_index_renders_build_form(tmp_path):
    _, client = _client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "Dispatch Run Console" in r.text
    assert 'name="history_days"' in r.text
    assert 'name="skip_learn"' in r.text


def test_index_lists_plans_with_review_count(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/")
    assert "20260605_093000" in r.text


def test_post_build_starts_job_and_returns_progress(tmp_path):
    from dispatch.runner import DispatchRunResult
    appmod, _ = _client(tmp_path)

    def fake(settings, emit, **kw):
        from dispatch.runner import DispatchProgressEvent
        emit(DispatchProgressEvent("learn", "learning"))
        emit(DispatchProgressEvent("done", "done", "ok", {"stamp": "S1"}))
        return DispatchRunResult("S1", tmp_path, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake
    from fastapi.testclient import TestClient
    client = TestClient(app)
    r = client.post("/build", data={"history_days": "90"})
    assert r.status_code == 200
    assert "sse" in r.text.lower()
    assert "/build/job/" in r.text and "/stream" in r.text


def test_post_build_passes_skip_learn(tmp_path):
    from dispatch.runner import DispatchRunResult
    import time
    appmod, _ = _client(tmp_path)
    captured: dict = {}

    def fake(settings, emit, **kw):
        captured["skip_learn"] = settings.skip_learn
        captured["history_days"] = settings.history_days
        return DispatchRunResult("S", None, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake
    from fastapi.testclient import TestClient
    client = TestClient(app)

    def _wait(job_id):
        for _ in range(200):
            if app.state.manager.get(job_id).done:
                return
            time.sleep(0.01)
        raise AssertionError("job did not finish")

    jid = client.post("/build", data={"history_days": "45",
                                      "skip_learn": "true"}).headers["x-job-id"]
    _wait(jid)
    assert captured["skip_learn"] is True
    assert captured["history_days"] == 45

    captured.clear()
    jid = client.post("/build", data={"history_days": "90"}).headers["x-job-id"]
    _wait(jid)
    assert captured["skip_learn"] is False


def test_post_build_rejects_when_active(tmp_path):
    from dispatch.runner import DispatchRunResult
    import time
    appmod, _ = _client(tmp_path)

    def slow(settings, emit, **kw):
        time.sleep(0.3)
        return DispatchRunResult("S", tmp_path, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = slow
    from fastapi.testclient import TestClient
    client = TestClient(app)
    client.post("/build", data={"history_days": "90"})
    r2 = client.post("/build", data={"history_days": "90"})
    assert "in progress" in r2.text.lower()


def test_stream_emits_events_with_plan_link(tmp_path):
    from dispatch.runner import DispatchRunResult, DispatchProgressEvent
    appmod, _ = _client(tmp_path)

    def fake(settings, emit, **kw):
        emit(DispatchProgressEvent("learn", "learning"))
        emit(DispatchProgressEvent("done", "all done", "ok", {"stamp": "S1"}))
        return DispatchRunResult("S1", tmp_path, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake
    from fastapi.testclient import TestClient
    client = TestClient(app)
    job_id = client.post("/build", data={"history_days": "90"}).headers["x-job-id"]
    with client.stream("GET", f"/build/job/{job_id}/stream") as s:
        body = "".join(chunk for chunk in s.iter_text())
    assert "learning" in body
    assert "event: done" in body
    assert "/plans/S1" in body


def test_plan_detail_shows_runs_and_review(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000")
    assert r.status_code == 200
    assert "West-Tue" in r.text          # predicted run
    assert "new_address" in r.text       # review flag
    assert "Geelong" in r.text           # review reason/zone


def test_plan_detail_missing_404(tmp_path):
    _, client = _client(tmp_path)
    r = client.get("/plans/nope")
    assert r.status_code == 404


def test_run_detail_lists_stops(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000/runs/West-Tue")
    assert r.status_code == 200
    assert "1 A St" in r.text
    assert "Scoresby" in r.text


def test_run_detail_missing_plan_404(tmp_path):
    _, client = _client(tmp_path)
    r = client.get("/plans/nope/runs/West-Tue")
    assert r.status_code == 404


def test_download_suggested_csv(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000/files/suggested_runs.csv")
    assert r.status_code == 200
    assert "West-Tue" in r.text


def test_download_traversal_404(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000/files/..%2f..%2fsecret")
    assert r.status_code == 404
