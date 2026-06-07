"""Tests for the pallet-cube calibration helper."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "_calib", _ROOT / "scripts" / "calibrate_pallet_cube.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_recommend_threshold_from_fractions():
    mod = _load_module()
    per_order = pd.DataFrame({"pallet_fraction_cube": [0.05, 0.1, 0.2, 0.8, 0.9, 1.1]})
    rec = mod.recommend_threshold(per_order)
    assert "p50" in rec and "p90" in rec
    assert "recommended_threshold" in rec
    assert 0.0 < rec["recommended_threshold"] <= 1.5
