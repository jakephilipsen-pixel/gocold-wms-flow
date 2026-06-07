"""_make_wave_id must produce filesystem-safe single-segment ids.

run_group is now a free-text delivery-run label (predicted_run), and the
wave_id is used directly as a directory name + filename prefix downstream,
so unsafe characters like '/' must not survive.
"""
from __future__ import annotations

import datetime as dt

from analysis.routing import _make_wave_id


def test_wave_id_slugifies_unsafe_run_group():
    wid = _make_wave_id(dt.date(2026, 6, 8), "North / West", "1_pallet_pick", 1)
    # no path separator or spaces survive
    assert "/" not in wid
    assert "\\" not in wid
    assert " " not in wid
    assert wid.endswith("_S1_W01")


def test_wave_id_handles_none_run_group():
    wid = _make_wave_id(dt.date(2026, 6, 8), None, "3_wave_bench", 2)
    assert "UNK" in wid
    assert wid.endswith("_S3_W02")


def test_wave_id_preserves_clean_labels():
    wid = _make_wave_id(dt.date(2026, 6, 8), "VIC", "2_wave_bypass", 1)
    assert wid == "2026-06-08_VIC_S2_W01"


def test_wave_id_collapses_repeated_unsafe_chars():
    wid = _make_wave_id(dt.date(2026, 6, 8), "A // B  C", "1_pallet_pick", 1)
    # runs of unsafe chars collapse, no leading/trailing dashes in the segment
    assert "//" not in wid
    assert "  " not in wid
    assert wid.endswith("_S1_W01")
