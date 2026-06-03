"""Regression guard for the flagged weight estimator (AUDIT R6).

The estimator feeds cartonisation/dispatch, so the contract is strict:
measured weights pass through untouched, estimates are clearly flagged with
source + confidence, family-median density is preferred over the global
median, and no estimate is ever zero/negative. These tests pin all of that
with hand-built frames whose densities are known exactly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.weight_estimate import (
    CONF_LOW,
    CONF_MEASURED,
    CONF_MEDIUM,
    CONF_NONE,
    SOURCE_FAMILY,
    SOURCE_GLOBAL,
    SOURCE_MEASURED,
    SOURCE_NONE,
    WEIGHT_FLOOR_KG,
    estimate_carton_weights,
    product_family,
)

_L = 1_000_000.0  # 1 litre in mm³


def _row(code, weight, cube_l):
    return {"product_code": code, "outer_weight_kg": weight,
            "outer_cube_mm3": cube_l * _L}


def test_product_family_parsing():
    assert product_family("RK-9LY") == "RK"
    assert product_family("SNK-1BQ") == "SNK"
    assert product_family("NOHYPHEN") == "NOHYPHEN"


def test_measured_weights_pass_through_untouched():
    dims = pd.DataFrame([
        _row("AA-1", 5.0, 2.0),
        _row("AA-2", 3.0, 1.0),
    ])
    out = estimate_carton_weights(dims)

    assert list(out["weight_source"]) == [SOURCE_MEASURED, SOURCE_MEASURED]
    assert list(out["weight_confidence"]) == [CONF_MEASURED, CONF_MEASURED]
    # effective == measured, original column unchanged
    assert list(out["outer_weight_kg_effective"]) == [5.0, 3.0]
    assert list(out["outer_weight_kg"]) == [5.0, 3.0]


def test_family_density_used_when_enough_samples():
    # 3 AA measured, all density 0.5 kg/L -> family median 0.5.
    dims = pd.DataFrame([
        _row("AA-1", 0.5, 1.0),
        _row("AA-2", 1.0, 2.0),
        _row("AA-3", 1.5, 3.0),
        _row("AA-9", np.nan, 4.0),   # missing -> estimate 0.5 * 4 = 2.0
    ])
    out = estimate_carton_weights(dims, min_family_samples=3).set_index("product_code")

    assert out.loc["AA-9", "weight_source"] == SOURCE_FAMILY
    assert out.loc["AA-9", "weight_confidence"] == CONF_MEDIUM
    assert out.loc["AA-9", "outer_weight_kg_effective"] == pytest.approx(2.0)
    assert "family AA" in out.loc["AA-9", "weight_estimate_basis"]


def test_global_fallback_when_family_too_sparse():
    # AA gives a solid family density; BB has a single sample (sparse).
    dims = pd.DataFrame([
        _row("AA-1", 0.5, 1.0),
        _row("AA-2", 0.5, 1.0),
        _row("AA-3", 0.5, 1.0),
        _row("BB-1", 0.5, 1.0),     # lone BB sample
        _row("BB-9", np.nan, 2.0),  # missing -> global median (0.5) * 2 = 1.0
    ])
    out = estimate_carton_weights(dims, min_family_samples=3).set_index("product_code")

    assert out.loc["BB-9", "weight_source"] == SOURCE_GLOBAL
    assert out.loc["BB-9", "weight_confidence"] == CONF_LOW
    assert out.loc["BB-9", "outer_weight_kg_effective"] == pytest.approx(1.0)
    assert "global median" in out.loc["BB-9", "weight_estimate_basis"]


def test_family_median_resists_outliers():
    # One absurdly dense AA carton must not drag the family estimate up;
    # median of densities [0.5, 0.5, 0.5, 50.0] is 0.5.
    dims = pd.DataFrame([
        _row("AA-1", 0.5, 1.0),
        _row("AA-2", 0.5, 1.0),
        _row("AA-3", 0.5, 1.0),
        _row("AA-4", 50.0, 1.0),    # outlier
        _row("AA-9", np.nan, 2.0),  # -> 0.5 * 2 = 1.0, not pulled toward 50
    ])
    out = estimate_carton_weights(dims, min_family_samples=3).set_index("product_code")
    assert out.loc["AA-9", "outer_weight_kg_effective"] == pytest.approx(1.0)


def test_estimate_never_below_floor():
    dims = pd.DataFrame([
        _row("AA-1", 0.5, 1.0),
        _row("AA-2", 0.5, 1.0),
        _row("AA-3", 0.5, 1.0),
        _row("AA-9", np.nan, 0.0001),  # tiny cube -> would be ~0, clamp to floor
    ])
    out = estimate_carton_weights(dims, min_family_samples=3).set_index("product_code")
    assert out.loc["AA-9", "outer_weight_kg_effective"] == WEIGHT_FLOOR_KG


def test_missing_cube_cannot_be_estimated():
    dims = pd.DataFrame([
        _row("AA-1", 0.5, 1.0),
        _row("AA-2", 0.5, 1.0),
        _row("AA-3", 0.5, 1.0),
        {"product_code": "AA-9", "outer_weight_kg": np.nan, "outer_cube_mm3": 0},
    ])
    out = estimate_carton_weights(dims, min_family_samples=3).set_index("product_code")
    assert out.loc["AA-9", "weight_source"] == SOURCE_NONE
    assert out.loc["AA-9", "weight_confidence"] == CONF_NONE
    assert pd.isna(out.loc["AA-9", "outer_weight_kg_effective"])


def test_requires_expected_columns():
    with pytest.raises(ValueError):
        estimate_carton_weights(pd.DataFrame({"product_code": ["X-1"]}))
