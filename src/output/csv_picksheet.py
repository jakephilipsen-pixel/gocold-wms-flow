"""Machine-readable CSV companions for each wave pick sheet.

Two files per wave:

  ``<wave_id>_picks.csv``
      One row per consolidated pick line — location, SKU, total qty,
      contributing SO refs. Useful for the bench team to scan-confirm.

  ``<wave_id>_orders.csv``
      One row per order in the wave — so_ref, customer, destination.
      This is what the operator pastes into CC's wave creation flow.

The CSVs intentionally mirror the columns visible on the PDF so any
discrepancy is obvious. Numeric columns are integers (no floats) to
match how CC's UI presents them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from analysis.wave_picks import WavePickSheet

log = logging.getLogger(__name__)


@dataclass
class WaveCsvPaths:
    """The two CSV paths written for a single wave."""
    picks: Path
    orders: Path


def write_wave_csvs(sheet: WavePickSheet, out_dir: Path) -> WaveCsvPaths:
    """Write the picks + orders CSVs for ``sheet`` into ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    picks_cols = [
        "walk_index",
        "location",
        "aisle",
        "bay",
        "level",
        "sublevel",
        "product_code",
        "product_name",
        "qty_cartons",
        "cartons_running_total",
        "contributing_so_refs",
    ]
    picks_path = out_dir / f"{sheet.wave_id}_picks.csv"
    picks_view = sheet.pick_lines.reindex(columns=picks_cols)
    picks_view.to_csv(picks_path, index=False)

    orders_cols = [
        "so_ref",
        "customer_name",
        "delivery_company",
        "delivery_suburb",
        "delivery_state",
        "delivery_postcode",
        "cartons",
        "lines",
    ]
    orders_path = out_dir / f"{sheet.wave_id}_orders.csv"
    orders_view = sheet.orders.reindex(columns=orders_cols)
    orders_view.to_csv(orders_path, index=False)

    log.info(
        "wrote CSVs for wave %s (%d pick lines, %d orders)",
        sheet.wave_id, len(picks_view), len(orders_view),
    )
    return WaveCsvPaths(picks=picks_path, orders=orders_path)
