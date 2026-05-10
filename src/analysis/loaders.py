"""Load the most recent extract parquet snapshots from data/raw/.

Picks the latest timestamp by file mtime so we don't have to think about
which snapshot we're using. Validates schemas so we fail fast with a
useful error if the columns we need aren't there.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """The three dataframes the analysis needs, plus where they came from."""
    so_lines: pd.DataFrame
    po_lines: pd.DataFrame
    products: pd.DataFrame
    so_path: Path
    po_path: Path
    products_path: Path

    @property
    def so_window(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        ts = pd.to_datetime(self.so_lines["ts_packed"], errors="coerce", utc=True)
        return ts.min(), ts.max()

    @property
    def po_window(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        ts = pd.to_datetime(self.po_lines["arrival_date"], errors="coerce")
        return ts.min(), ts.max()


def _latest(raw_dir: Path, prefix: str) -> Path:
    """Return the most recently modified parquet matching prefix_*.parquet."""
    candidates = sorted(
        raw_dir.glob(f"{prefix}_*.parquet"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"no {prefix}_*.parquet found in {raw_dir}. "
            f"run scripts/extract_forage.py first."
        )
    return candidates[0]


_REQUIRED_SO_COLS = {
    "so_id", "so_ref", "product_code", "product_name",
    "quantity", "ts_packed", "delivery_postcode", "delivery_suburb",
    "delivery_state",
}
_REQUIRED_PO_COLS = {
    "po_id", "po_ref", "product_code", "quantity",
    "arrival_date", "item_status",
}
_REQUIRED_PRODUCT_COLS = {
    "product_id", "product_code", "name", "type", "active",
}


def _validate(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{label} parquet missing required columns: {sorted(missing)}"
        )


def load_latest(raw_dir: Path) -> Snapshot:
    """Load the most recent SO/PO/products parquet snapshots from raw_dir."""
    so_path = _latest(raw_dir, "so_lines")
    po_path = _latest(raw_dir, "po_lines")
    products_path = _latest(raw_dir, "products")

    log.info("loading SO lines from %s", so_path.name)
    so_lines = pd.read_parquet(so_path)
    _validate(so_lines, _REQUIRED_SO_COLS, "so_lines")

    log.info("loading PO lines from %s", po_path.name)
    po_lines = pd.read_parquet(po_path)
    _validate(po_lines, _REQUIRED_PO_COLS, "po_lines")

    log.info("loading products from %s", products_path.name)
    products = pd.read_parquet(products_path)
    _validate(products, _REQUIRED_PRODUCT_COLS, "products")

    # quantity should be numeric; cast if loaded as object
    so_lines["quantity"] = pd.to_numeric(so_lines["quantity"], errors="coerce")
    po_lines["quantity"] = pd.to_numeric(po_lines["quantity"], errors="coerce")

    return Snapshot(
        so_lines=so_lines,
        po_lines=po_lines,
        products=products,
        so_path=so_path,
        po_path=po_path,
        products_path=products_path,
    )
