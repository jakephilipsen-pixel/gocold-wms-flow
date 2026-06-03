"""Tests for the single-run JobManager (src/web/jobs.py)."""
from __future__ import annotations

import time
from pathlib import Path

from web.jobs import JobManager
from wave_runner import ProgressEvent, RunResult, WaveRunSettings


def _fake_pipeline(events, status="success"):
    def run(settings, progress):
        for e in events:
            progress(e)
        return RunResult("stamp", Path("/tmp/run"), {"n_waves": len(events)}, status)
    return run


def _wait(mgr, run_id, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if mgr.get(run_id).done:
            return
        time.sleep(0.01)
    raise AssertionError("job did not finish in time")


def test_start_runs_and_buffers_events(tmp_path):
    events = [ProgressEvent("pull", "pulling"), ProgressEvent("done", "ok", "ok")]
    mgr = JobManager(runner=_fake_pipeline(events))
    run_id = mgr.start(WaveRunSettings(repo_root=tmp_path))
    _wait(mgr, run_id)
    job = mgr.get(run_id)
    assert job.status == "success"
    assert [e.stage for e in job.events] == ["pull", "done"]


def test_second_start_while_active_is_rejected(tmp_path):
    def slow(settings, progress):
        time.sleep(0.3)
        progress(ProgressEvent("done", "ok", "ok"))
        return RunResult("s", Path("/tmp"), {}, "success")
    mgr = JobManager(runner=slow)
    first = mgr.start(WaveRunSettings(repo_root=tmp_path))
    try:
        mgr.start(WaveRunSettings(repo_root=tmp_path))
        assert False, "expected RunInProgressError"
    except mgr.RunInProgressError:
        pass
    _wait(mgr, first)


def test_failed_pipeline_is_captured_not_raised(tmp_path):
    def boom(settings, progress):
        raise RuntimeError("kaboom")
    mgr = JobManager(runner=boom)
    run_id = mgr.start(WaveRunSettings(repo_root=tmp_path))
    _wait(mgr, run_id)
    job = mgr.get(run_id)
    assert job.status == "failed"
    assert "kaboom" in (job.error or "")
