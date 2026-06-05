"""Tests for the shared wave-generation core (src/wave_runner.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from wave_runner import (
    ProgressEvent,
    RunResult,
    WaveRunSettings,
    run_wave_generation,
)

_ROOT = Path(__file__).resolve().parent.parent


def test_settings_defaults_pull_from_analysis_constants():
    s = WaveRunSettings(repo_root=Path("/tmp/repo"))
    assert s.status == "AWAITING_PICK_AND_PACK"
    assert s.customer_name is None
    assert s.pallet_fraction_threshold == 0.70
    assert s.early_release_cartons == 30
    assert s.run_group_col == "delivery_state"
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


# ---------------------------------------------------------------------------
# run_wave_generation — end-to-end against the real pipeline (no network).
# ---------------------------------------------------------------------------


def _fake_order(so_ref, code):
    """A minimal CC outbound order shaped to feed the REAL flattener.

    Mirrors exactly the keys ``scripts/extract.py:_flatten_outbound_order_lines``
    reads, so it explodes into one usable per-line row (so_id, product_code,
    quantity, customer_id, delivery_* …). The order has no resolvable pick
    location in this environment (no assignments file), so it is skipped by the
    wave generator — but the pipeline still runs end-to-end and writes a
    manifest.
    """
    return {
        "id": f"id-{so_ref}",
        "status": "AWAITING_PICK_AND_PACK",
        "references": {"customer": so_ref, "numericId": "999001"},
        "customer": {
            "id": "d4810e1e-91ab-43ed-b68e-b72bd858b122",
            "name": "The Forage Company",
        },
        "warehouse": {"name": "Default"},
        "details": {
            "urgent": False,
            "deliver": {
                "requiredDate": "2026-06-05",
                "address": {
                    "companyName": "Test Co",
                    "suburb": "Scoresby",
                    "state": {"code": "VIC"},
                    "postcode": "3179",
                },
            },
        },
        "timestamps": {
            "created": {"time": "2026-06-04T08:00:00+10:00"},
            "modified": {"time": "2026-06-04T08:05:00+10:00"},
            "packed": {"time": None},
            "dispatched": {"time": None},
        },
        "items": [
            {
                "details": {
                    "product": {
                        "id": f"prod-{code}",
                        "references": {"code": code},
                        "name": f"Product {code}",
                    },
                    "unitOfMeasure": {"type": "EA", "name": "Each"},
                },
                "measures": {"quantity": 5},
                "properties": {"batch": "20271002", "expiryDate": "2027-10-02"},
            }
        ],
    }


@pytest.fixture
def fake_cc(monkeypatch):
    """Patch the live CC pull + client construction to avoid network."""
    monkeypatch.setattr(
        "wave_runner.CartonCloudClient.from_env",
        classmethod(lambda cls, **kw: object()),
    )
    # SOH is now mandatory every gen — stub it to a single live location so
    # the pipeline runs end-to-end and produces a real wave.
    monkeypatch.setattr(
        "wave_runner.get_sku_locations",
        lambda client, **kw: [
            {"product_code": "SOME-SKU", "location_name": "AA-01-01",
             "location_id": "id-1", "qty": 5, "uom": "EA"},
        ],
    )
    return monkeypatch


def test_run_emits_progress_and_writes_run(tmp_path, fake_cc):
    orders = [_fake_order("SO-1", "SOME-SKU")]
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter(orders),
    )
    events: list[ProgressEvent] = []
    settings = WaveRunSettings(repo_root=_ROOT, out_dir=tmp_path / "waves")
    result = run_wave_generation(settings, events.append)

    assert result.status in {"success", "empty"}
    assert [e.stage for e in events][:1] == ["pull"]
    assert any(e.stage == "done" for e in events)
    assert (result.out_dir / "manifest.json").exists()


def test_run_with_no_orders_is_empty(tmp_path, fake_cc):
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter([]),
    )
    events: list[ProgressEvent] = []
    settings = WaveRunSettings(repo_root=_ROOT, out_dir=tmp_path / "waves")
    result = run_wave_generation(settings, events.append)
    assert result.status == "empty"
    assert (result.out_dir / "index.md").exists()
    assert (result.out_dir / "manifest.json").exists()


def test_soh_failure_fails_the_run(tmp_path, fake_cc):
    from cc_client import CartonCloudError
    orders = [_fake_order("SO-1", "SOME-SKU")]
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter(orders),
    )

    def boom(client, **kw):
        raise CartonCloudError("SOH report-run timed out")

    fake_cc.setattr("wave_runner.get_sku_locations", boom)
    events: list[ProgressEvent] = []
    settings = WaveRunSettings(repo_root=_ROOT, out_dir=tmp_path / "waves")
    result = run_wave_generation(settings, events.append)
    assert result.status == "failed"
    assert any(e.level == "error" for e in events)


def test_cli_main_builds_settings_and_runs(tmp_path, monkeypatch):
    """The CLI wrapper delegates to run_wave_generation with parsed flags."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "_gen_waves", _ROOT / "scripts" / "generate_waves.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    captured = {}

    def fake_run(settings, progress):
        captured["settings"] = settings
        progress(ProgressEvent("done", "ok", "ok"))
        return RunResult("stamp", tmp_path, {"n_waves": 0}, "empty")

    monkeypatch.setattr(mod, "run_wave_generation", fake_run)
    monkeypatch.setattr(
        sys, "argv",
        ["generate_waves.py", "--early-release-cartons", "25",
         "--pallet-fraction-threshold", "0.65"])
    rc = mod.main()
    assert rc == 0
    assert captured["settings"].early_release_cartons == 25
    assert captured["settings"].pallet_fraction_threshold == 0.65
