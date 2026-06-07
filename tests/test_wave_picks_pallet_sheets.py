"""generate_wave_pick_sheets must produce sheets for the pallet stream when
include_immediate_streams=True."""
from __future__ import annotations

import pandas as pd

from analysis.routing import STREAM_PALLET, StreamClassification
from analysis.wave_picks import generate_wave_pick_sheets


def test_pallet_stream_produces_a_sheet_when_immediate_enabled():
    per_order = pd.DataFrame([{
        "so_id": "p1", "so_ref": "SO-1", "customer_name": "Forage",
        "delivery_company": "Acme", "delivery_suburb": "Scoresby",
        "delivery_state": "VIC", "delivery_postcode": "3179",
        "stream": STREAM_PALLET, "total_cartons": 80,
        "ts_packed": "2026-06-07T08:00:00+10:00", "predicted_run": "RUN-A",
    }])
    classification = StreamClassification(
        per_order=per_order,
        counts_by_stream=per_order["stream"].value_counts(),
        rule_hit_counts=pd.Series(dtype=int), threshold_used=0.7,
    )
    so_lines = pd.DataFrame([{
        "so_id": "p1", "so_ref": "SO-1", "product_code": "SKU-1",
        "product_name": "Thing", "quantity": 80,
    }])
    sku_locations = pd.DataFrame([{
        "product_code": "SKU-1", "location": "AA-01-01",
        "aisle": "AA", "bay": "01", "level": "01", "sublevel": "01",
    }])

    # Without the flag: no pallet sheet.
    off = generate_wave_pick_sheets(
        classification, so_lines, sku_locations=sku_locations,
        run_group_col="predicted_run")
    assert off.summary["n_waves"] == 0

    # With the flag: one pallet sheet for RUN-A.
    on = generate_wave_pick_sheets(
        classification, so_lines, sku_locations=sku_locations,
        run_group_col="predicted_run", include_immediate_streams=True)
    assert on.summary["n_waves"] == 1
    sheet = on.sheets[0]
    assert sheet.stream == STREAM_PALLET
    assert sheet.run_group == "RUN-A"
    assert sheet.total_cartons == 80
