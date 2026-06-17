from __future__ import annotations

import pandas as pd

from analysis.dims_worklist import WORKLIST_COLUMNS
from analysis.dims_measuring_sheet import partition_measuring, GROUP_ORDER


def _wl(rows):
    """Build a worklist-shaped frame; unspecified columns default to NA."""
    return pd.DataFrame(
        [{c: r.get(c, pd.NA) for c in WORKLIST_COLUMNS} for r in rows],
        columns=WORKLIST_COLUMNS,
    )


def test_groups_are_non_overlapping_and_complete():
    wl = _wl([
        {"product_code": "CARTON1", "kind": "carton", "weight_pending": False},
        {"product_code": "UNK1", "kind": "unknown", "weight_pending": True},
        {"product_code": "INNER_NOWT", "kind": "inner", "weight_pending": True},
        {"product_code": "INNER_DONE", "kind": "inner", "weight_pending": False},
    ])
    g = partition_measuring(wl)
    assert set(g.keys()) == set(GROUP_ORDER)
    assert list(g["measure_each"]["product_code"]) == ["CARTON1"]
    assert list(g["full_capture"]["product_code"]) == ["UNK1"]
    assert list(g["weigh_only"]["product_code"]) == ["INNER_NOWT"]
    # complete inner row appears in NO group
    total = sum(len(df) for df in g.values())
    assert total == 3  # INNER_DONE excluded


def test_carton_always_measure_each_even_if_weight_present():
    wl = _wl([{"product_code": "C", "kind": "carton", "weight_pending": False}])
    g = partition_measuring(wl)
    assert len(g["measure_each"]) == 1
    assert len(g["weigh_only"]) == 0


def test_rows_sorted_by_product_code():
    wl = _wl([
        {"product_code": "ZZ", "kind": "carton", "weight_pending": False},
        {"product_code": "AA", "kind": "carton", "weight_pending": False},
    ])
    g = partition_measuring(wl)
    assert list(g["measure_each"]["product_code"]) == ["AA", "ZZ"]


def test_empty_worklist_yields_empty_groups():
    g = partition_measuring(_wl([]))
    assert set(g.keys()) == set(GROUP_ORDER)
    assert all(df.empty for df in g.values())
