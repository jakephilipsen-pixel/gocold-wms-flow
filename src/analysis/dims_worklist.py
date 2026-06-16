"""Build a CC-authoritative dims completion worklist.

Joins CartonCloud's live active product list against locally captured carton
dims (analysis.dim_loader) and classifies each SKU by inner-pack-qty:
  - inner   (ipq == 1): captured dims ARE each-level; complete, no fill needed
  - carton  (ipq  > 1): captured dims are the outer carton; each-level L/W/H
                        must be physically measured (the fill task)
  - unknown (ipq blank / not captured / <= 0): cannot classify; flagged

Pure data only — no IO, no styling, no live CC. Styling lives in
dims_worklist_xlsx.write_worklist_xlsx; IO/fetch in scripts/build_dims_worklist.py.
"""
from __future__ import annotations

import math

import pandas as pd

WORKLIST_COLUMNS = [
    "product_code", "product_name", "kind", "cc_product_id",
    "carton_uom_code", "carton_baseqty", "ea_uom_code",
    "inner_pack_qty", "outer_l_mm", "outer_w_mm", "outer_h_mm", "outer_weight_kg",
    "each_l_mm", "each_w_mm", "each_h_mm",
    "no_carton_uom", "weight_pending", "ipq_unknown", "not_captured",
]


def _norm(code: object) -> str:
    return str(code).strip().upper()


def _classify(ipq: object) -> str:
    if ipq is None or (isinstance(ipq, float) and math.isnan(ipq)) or pd.isna(ipq):
        return "unknown"
    try:
        v = float(ipq)
    except (TypeError, ValueError):
        return "unknown"
    if v == 1:
        return "inner"
    if v > 1:
        return "carton"
    return "unknown"


def _baseqty(uom: object) -> float | None:
    if not isinstance(uom, dict):
        return None
    try:
        return float(uom.get("baseQty"))
    except (TypeError, ValueError):
        return None


def _find_uom_by_baseqty(uoms: dict, target: object) -> str | None:
    """Return the UoM code whose baseQty == target, or None if 0 or >1 match."""
    if target is None or pd.isna(target):
        return None
    matches = [code for code, u in (uoms or {}).items()
               if _baseqty(u) == float(target)]
    return matches[0] if len(matches) == 1 else None


def build_worklist(dims_df: pd.DataFrame, products: list[dict]) -> pd.DataFrame:
    """Join CC products (authoritative row set) against captured dims."""
    dims_by_code: dict[str, pd.Series] = {}
    for _, r in dims_df.iterrows():
        dims_by_code[_norm(r["product_code"])] = r

    rows: list[dict] = []
    for p in products:
        code = _norm((p.get("references") or {}).get("code"))
        if not code:
            continue
        uoms = p.get("unitOfMeasures") or {}
        d = dims_by_code.get(code)
        has_dims = d is not None
        ipq = d["inner_pack_qty"] if has_dims else pd.NA
        kind = _classify(ipq)

        ea = _find_uom_by_baseqty(uoms, 1)
        if kind == "inner":
            carton_uom = ea
        elif kind == "carton":
            carton_uom = _find_uom_by_baseqty(uoms, ipq)
        else:
            carton_uom = None
        carton_baseqty = _baseqty(uoms.get(carton_uom)) if carton_uom else pd.NA

        weight = d["outer_weight_kg"] if has_dims else pd.NA

        rows.append({
            "product_code": code,
            "product_name": p.get("name", "") or "",
            "kind": kind,
            "cc_product_id": p.get("id", "") or "",
            "carton_uom_code": carton_uom or "",
            "carton_baseqty": carton_baseqty,
            "ea_uom_code": ea or "",
            "inner_pack_qty": ipq,
            "outer_l_mm": d["outer_l_mm"] if has_dims else pd.NA,
            "outer_w_mm": d["outer_w_mm"] if has_dims else pd.NA,
            "outer_h_mm": d["outer_h_mm"] if has_dims else pd.NA,
            "outer_weight_kg": weight,
            "each_l_mm": pd.NA,
            "each_w_mm": pd.NA,
            "each_h_mm": pd.NA,
            "no_carton_uom": kind in ("inner", "carton") and carton_uom is None,
            "weight_pending": (not has_dims) or pd.isna(weight),
            "ipq_unknown": kind == "unknown",
            "not_captured": not has_dims,
        })

    return pd.DataFrame(rows, columns=WORKLIST_COLUMNS)


def captured_not_in_cc(dims_df: pd.DataFrame, products: list[dict]) -> list[str]:
    """Captured product codes that have no matching active CC product."""
    cc_codes = {_norm((p.get("references") or {}).get("code")) for p in products}
    captured = {_norm(c) for c in dims_df["product_code"]}
    return sorted(captured - cc_codes - {""})
