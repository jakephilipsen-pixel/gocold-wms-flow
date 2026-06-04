from __future__ import annotations

import pytest

from dispatch.predict import DispatchPlan, RunAssignment
from dispatch.sinks import CartonCloudSink, FileSink


def _plan():
    return DispatchPlan(assignments=[RunAssignment(
        "1", "SO-1", "West-Tue", 1.0, "stable", "reason", [], {})])


def test_file_sink_writes_and_reports_ok(tmp_path):
    results = FileSink(tmp_path).apply(_plan())
    assert (tmp_path / "suggested_runs.csv").exists()
    assert all(r.ok for r in results)


def test_cartoncloud_sink_refuses_without_both_flags():
    # Default: read-only — must refuse.
    with pytest.raises(PermissionError):
        CartonCloudSink(write_enabled=False, dispatch_write_approved=False).apply(_plan())
    with pytest.raises(PermissionError):
        CartonCloudSink(write_enabled=True, dispatch_write_approved=False).apply(_plan())
    with pytest.raises(PermissionError):
        CartonCloudSink(write_enabled=False, dispatch_write_approved=True).apply(_plan())
