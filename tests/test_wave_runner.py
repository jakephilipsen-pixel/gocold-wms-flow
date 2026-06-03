"""Tests for the shared wave-generation core (src/wave_runner.py)."""
from __future__ import annotations

from pathlib import Path

from wave_runner import ProgressEvent, RunResult, WaveRunSettings


def test_settings_defaults_pull_from_analysis_constants():
    s = WaveRunSettings(repo_root=Path("/tmp/repo"))
    assert s.status == "AWAITING_PICK_AND_PACK"
    assert s.customer_name is None
    assert s.pallet_fraction_threshold == 0.70
    assert s.early_release_cartons == 30
    assert s.run_group_col == "delivery_state"
    assert s.soh_fallback is False
    assert s.lines_per_hour == 60
    assert s.pallet_ratio == 0.9


def test_progress_event_levels_default_info():
    e = ProgressEvent(stage="pull", message="pulling orders")
    assert e.level == "info"
    assert e.data == {}


def test_run_result_holds_summary():
    r = RunResult(
        run_id="20260604_081200",
        out_dir=Path("/tmp/run"),
        summary={"n_waves": 3},
        status="success",
    )
    assert r.status == "success"
    assert r.summary["n_waves"] == 3
    assert r.error is None


def test_latest_file_picks_newest(tmp_path):
    from wave_runner import _latest_file
    old = tmp_path / "dims_2026-05-11.xlsx"
    new = tmp_path / "dims_2026-05-13.xlsx"
    old.write_text("a")
    new.write_text("b")
    import os, time
    os.utime(old, (time.time() - 100, time.time() - 100))
    assert _latest_file(tmp_path, "dims_*.xlsx") == new


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    from wave_runner import _load_dotenv
    env = tmp_path / ".env"
    env.write_text('FOO="bar"\n# comment\nBAZ=qux\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    _load_dotenv(env)
    import os
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"
