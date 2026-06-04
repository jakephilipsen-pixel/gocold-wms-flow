from __future__ import annotations

from datetime import date

from dispatch.history import compute_run_history, load_model, save_model


def _rec(key, run, run_date):
    return {"address_key": key, "run": run, "run_date": run_date}


def test_recent_run_outranks_older_for_same_address():
    recs = [
        _rec("a", "West-Tue", "2026-06-03"),   # recent
        _rec("a", "West-Tue", "2026-06-01"),
        _rec("a", "Old-Run", "2026-04-01"),    # stale
    ]
    model = compute_run_history(recs, as_of=date(2026, 6, 5), half_life_days=30)
    cands = model.by_address["a"]
    assert cands[0].run == "West-Tue"
    assert cands[0].n == 2
    assert cands[0].score > cands[1].score
    assert cands[0].last_seen == date(2026, 6, 3)


def test_records_without_run_or_key_are_skipped():
    recs = [_rec("", "X", "2026-06-03"), _rec("a", "", "2026-06-03")]
    model = compute_run_history(recs, as_of=date(2026, 6, 5))
    assert model.by_address == {}


def test_model_round_trips_through_parquet(tmp_path):
    recs = [_rec("a", "West-Tue", "2026-06-03")]
    model = compute_run_history(recs, as_of=date(2026, 6, 5))
    p = tmp_path / "m.parquet"
    save_model(model, p)
    loaded = load_model(p)
    assert loaded.by_address["a"][0].run == "West-Tue"
    assert loaded.by_address["a"][0].last_seen == date(2026, 6, 3)
