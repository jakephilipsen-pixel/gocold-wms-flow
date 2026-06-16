# Dims Completion Worklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CC-authoritative dims completion worklist xlsx that pre-fills captured carton dims, classifies each SKU as inner/carton/unknown by inner-pack-qty, and highlights only the genuine gaps for Jake to measure (~73 multi-pack SKUs + 2 unknowns, not ~412).

**Architecture:** A pure builder (`src/analysis/dims_worklist.py`) joins CC's live active product list against locally captured dims (reusing `analysis.dim_loader.load_dimensions`), classifies by inner-pack-qty, and emits a tidy DataFrame plus a reconciliation of captured-but-not-in-CC codes. A separate styled-xlsx writer turns that DataFrame into a highlighted workbook. A thin orchestrator script (`scripts/build_dims_worklist.py`) wires env + read-only CC client + IO. This is Part 1 of the spec; the CC write/sync (Part 2) is out of scope here.

**Tech Stack:** Python 3.11+, pandas, openpyxl, the existing `src/cc_client` (read-only OAuth2), pytest.

**Spec:** `docs/superpowers/specs/2026-06-17-dims-completion-worklist-and-cc-sync-design.md`

**Deviations from spec (deliberate, DRY):**
- The spec names a new parser `src/dims/capture_sheet.py`. We **reuse the existing `src/analysis/dim_loader.load_dimensions`** instead — it already parses this exact sheet (tolerant header matching, returns `product_code`, `outer_l/w/h_mm`, `outer_weight_kg`, `inner_pack_qty`). No new parser is built.
- The spec lists flags `baseqty_ne_innerpack` and `no_carton_uom`. Under the `baseQty == inner-pack-qty` matching rule these are the **same condition**, so they consolidate into one flag, `no_carton_uom`. We add two genuinely-useful flags the CC-authoritative source implies: `not_captured` (CC product with no local dims) and a separate `captured_not_in_cc` reconciliation list.

**Environment note:** the project venv has a stale shebang — always invoke as `.venv/bin/python -m pytest …`, never the `pytest`/`python` wrappers.

---

## File structure

| File | Responsibility |
|---|---|
| Create `src/analysis/dims_worklist.py` | Pure builder: `build_worklist(dims_df, products) -> DataFrame`, `captured_not_in_cc(dims_df, products) -> list[str]`, `WORKLIST_COLUMNS`. No IO, no styling, no live CC. |
| Create `src/analysis/dims_worklist_xlsx.py` | `write_worklist_xlsx(df, path)` — openpyxl styling + gap highlighting. |
| Create `scripts/build_dims_worklist.py` | Orchestrator: load `.env`, read-only CC client, fetch products, `load_dimensions`, build, write, log summary + reconciliation. |
| Create `tests/test_dims_worklist.py` | Unit tests for builder + reconciliation (in-memory DataFrames + fake product dicts; no live CC). |
| Create `tests/test_dims_worklist_xlsx.py` | Tests the writer produces a workbook with expected sheet/headers and highlights the expected cells. |

**Data contracts:**

`load_dimensions(path)` returns a DataFrame with (among others): `product_code` (str), `outer_l_mm`, `outer_w_mm`, `outer_h_mm`, `outer_weight_kg`, `inner_pack_qty` (numeric, may be NaN).

A CC product dict (from `search_warehouse_products`) looks like:
```python
{
  "id": "55811cf3-...",
  "references": {"code": "AE-BLA"},
  "name": "AE - Dark Blackout",
  "unitOfMeasures": {
    "EA": {"baseQty": 1, ...},
    "CT": {"baseQty": 12, ...},
    "PLT": {"baseQty": 576, ...},
  },
}
```

`build_worklist` output columns (exact order = `WORKLIST_COLUMNS`):
```
product_code, product_name, kind, cc_product_id,
carton_uom_code, carton_baseqty, ea_uom_code,
inner_pack_qty, outer_l_mm, outer_w_mm, outer_h_mm, outer_weight_kg,
each_l_mm, each_w_mm, each_h_mm,
no_carton_uom, weight_pending, ipq_unknown, not_captured
```

Classification (`kind`) from `inner_pack_qty`: `1 → "inner"`, `>1 → "carton"`, NaN/missing/≤0 → `"unknown"`.

---

## Task 1: Builder — classification + match + carton-UoM identification

**Files:**
- Create: `src/analysis/dims_worklist.py`
- Test: `tests/test_dims_worklist.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dims_worklist.py
from __future__ import annotations

import math
import pandas as pd

from analysis.dims_worklist import (
    build_worklist,
    captured_not_in_cc,
    WORKLIST_COLUMNS,
    _classify,
)


def _dims(rows):
    """Build a load_dimensions-shaped frame from dicts."""
    cols = ["product_code", "outer_l_mm", "outer_w_mm", "outer_h_mm",
            "outer_weight_kg", "inner_pack_qty"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows], columns=cols)


def _prod(code, name, uoms):
    return {"id": f"id-{code}", "references": {"code": code},
            "name": name, "unitOfMeasures": uoms}


def test_classify_inner_carton_unknown():
    assert _classify(1) == "inner"
    assert _classify(12) == "carton"
    assert _classify(float("nan")) == "unknown"
    assert _classify(None) == "unknown"
    assert _classify(0) == "unknown"


def test_inner_sku_maps_to_each_uom():
    dims = _dims([{"product_code": "AE-BLA", "outer_l_mm": 50, "outer_w_mm": 40,
                   "outer_h_mm": 30, "outer_weight_kg": 0.2, "inner_pack_qty": 1}])
    prods = [_prod("AE-BLA", "Dark Blackout",
                   {"EA": {"baseQty": 1}, "PLT": {"baseQty": 576}})]
    wl = build_worklist(dims, prods)
    row = wl.iloc[0]
    assert list(wl.columns) == WORKLIST_COLUMNS
    assert row["kind"] == "inner"
    assert row["carton_uom_code"] == "EA"     # inner → the baseQty==1 measure
    assert row["ea_uom_code"] == "EA"
    assert row["cc_product_id"] == "id-AE-BLA"
    assert bool(row["no_carton_uom"]) is False


def test_carton_sku_matches_baseqty_to_innerpack():
    dims = _dims([{"product_code": "BX-12", "outer_l_mm": 300, "outer_w_mm": 200,
                   "outer_h_mm": 150, "outer_weight_kg": 6.0, "inner_pack_qty": 12}])
    prods = [_prod("BX-12", "Box of 12",
                   {"EA": {"baseQty": 1}, "CT": {"baseQty": 12}, "PLT": {"baseQty": 576}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["kind"] == "carton"
    assert row["carton_uom_code"] == "CT"
    assert row["carton_baseqty"] == 12
    assert row["ea_uom_code"] == "EA"


def test_no_carton_uom_flag_when_baseqty_absent():
    # ipq=6 but no UoM has baseQty 6 → cannot locate carton measure
    dims = _dims([{"product_code": "ODD", "outer_l_mm": 1, "outer_w_mm": 1,
                   "outer_h_mm": 1, "outer_weight_kg": 1, "inner_pack_qty": 6}])
    prods = [_prod("ODD", "Odd", {"EA": {"baseQty": 1}, "CT": {"baseQty": 12}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["carton_uom_code"] == ""
    assert bool(row["no_carton_uom"]) is True


def test_code_match_is_trim_and_case_insensitive():
    dims = _dims([{"product_code": " ae-bla ", "outer_l_mm": 1, "outer_w_mm": 1,
                   "outer_h_mm": 1, "outer_weight_kg": 1, "inner_pack_qty": 1}])
    prods = [_prod("AE-BLA", "x", {"EA": {"baseQty": 1}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["kind"] == "inner"
    assert row["not_captured"] == False  # matched despite whitespace/case
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dims_worklist.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.dims_worklist'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/analysis/dims_worklist.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dims_worklist.py -q`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/analysis/dims_worklist.py tests/test_dims_worklist.py
git commit -m "feat(dims): worklist builder — kind classification + carton-UoM match"
```

---

## Task 2: Builder — flags, NaN handling, and reconciliation

**Files:**
- Modify: `tests/test_dims_worklist.py` (add cases)
- (No source change expected — `build_worklist`/`captured_not_in_cc` already implement these; this task locks the behaviour with tests. If a test fails, fix the source minimally.)

- [ ] **Step 1: Write the failing/guard tests**

```python
# append to tests/test_dims_worklist.py

def test_weight_pending_when_weight_missing():
    dims = _dims([{"product_code": "NOWT", "outer_l_mm": 10, "outer_w_mm": 10,
                   "outer_h_mm": 10, "outer_weight_kg": float("nan"),
                   "inner_pack_qty": 1}])
    prods = [_prod("NOWT", "no weight", {"EA": {"baseQty": 1}})]
    row = build_worklist(dims, prods).iloc[0]
    assert bool(row["weight_pending"]) is True


def test_cc_product_without_captured_dims_is_not_captured_and_unknown():
    dims = _dims([])  # nothing captured
    prods = [_prod("NEW-SKU", "brand new", {"EA": {"baseQty": 1}})]
    row = build_worklist(dims, prods).iloc[0]
    assert bool(row["not_captured"]) is True
    assert row["kind"] == "unknown"
    assert bool(row["ipq_unknown"]) is True
    assert bool(row["weight_pending"]) is True


def test_blank_inner_pack_qty_is_unknown():
    dims = _dims([{"product_code": "BLANK", "outer_l_mm": 1, "outer_w_mm": 1,
                   "outer_h_mm": 1, "outer_weight_kg": 1,
                   "inner_pack_qty": float("nan")}])
    prods = [_prod("BLANK", "x", {"EA": {"baseQty": 1}, "CT": {"baseQty": 12}})]
    row = build_worklist(dims, prods).iloc[0]
    assert row["kind"] == "unknown"
    assert bool(row["ipq_unknown"]) is True
    assert bool(row["no_carton_uom"]) is False  # unknown kind doesn't demand a carton UoM


def test_captured_not_in_cc_lists_orphans():
    dims = _dims([
        {"product_code": "IN-CC", "outer_l_mm": 1, "outer_w_mm": 1, "outer_h_mm": 1,
         "outer_weight_kg": 1, "inner_pack_qty": 1},
        {"product_code": "GONE", "outer_l_mm": 1, "outer_w_mm": 1, "outer_h_mm": 1,
         "outer_weight_kg": 1, "inner_pack_qty": 1},
    ])
    prods = [_prod("IN-CC", "x", {"EA": {"baseQty": 1}})]
    assert captured_not_in_cc(dims, prods) == ["GONE"]


def test_row_count_equals_cc_product_count():
    dims = _dims([])
    prods = [_prod("A", "a", {"EA": {"baseQty": 1}}),
             _prod("B", "b", {"EA": {"baseQty": 1}})]
    assert len(build_worklist(dims, prods)) == 2
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_dims_worklist.py -q`
Expected: PASS (all Task 1 + Task 2 tests, 10 total). If any fail, fix `dims_worklist.py` minimally and re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dims_worklist.py src/analysis/dims_worklist.py
git commit -m "test(dims): lock worklist flags, NaN handling, CC reconciliation"
```

---

## Task 3: Styled xlsx writer with gap highlighting

**Files:**
- Create: `src/analysis/dims_worklist_xlsx.py`
- Test: `tests/test_dims_worklist_xlsx.py`

Highlighting rules (encoded in the writer):
- **carton** rows: `each_l_mm`/`each_w_mm`/`each_h_mm` cells get the **yellow fill** (`FFFFE0`) — these are the fill task.
- any row with `weight_pending`: the `outer_weight_kg` cell gets the **yellow fill**.
- **unknown** rows: the `inner_pack_qty` cell **and** the three each cells get the yellow fill (resolve + measure).
- **inner** rows: each cells get a **grey fill** (`D9D9D9`) and the literal text `= captured` (do not fill — captured dims already are the each dims).
- Header row: dark Go Cold fill `1F2937`, white bold Arial, frozen panes below header and right of `product_name`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dims_worklist_xlsx.py
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from analysis.dims_worklist import build_worklist, WORKLIST_COLUMNS
from analysis.dims_worklist_xlsx import write_worklist_xlsx

_YELLOW = "FFFFE0"
_GREY = "D9D9D9"


def _dims(rows):
    cols = ["product_code", "outer_l_mm", "outer_w_mm", "outer_h_mm",
            "outer_weight_kg", "inner_pack_qty"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows], columns=cols)


def _prod(code, name, uoms):
    return {"id": f"id-{code}", "references": {"code": code},
            "name": name, "unitOfMeasures": uoms}


def _col_letter(name):
    # 1-based column index of a worklist column → its each-row cell address helper
    return WORKLIST_COLUMNS.index(name) + 1


def _build(tmp_path) -> Path:
    dims = _dims([
        {"product_code": "INNER1", "outer_l_mm": 50, "outer_w_mm": 40, "outer_h_mm": 30,
         "outer_weight_kg": 0.2, "inner_pack_qty": 1},
        {"product_code": "CART12", "outer_l_mm": 300, "outer_w_mm": 200, "outer_h_mm": 150,
         "outer_weight_kg": 6.0, "inner_pack_qty": 12},
        {"product_code": "NOWT", "outer_l_mm": 10, "outer_w_mm": 10, "outer_h_mm": 10,
         "outer_weight_kg": float("nan"), "inner_pack_qty": 1},
    ])
    prods = [
        _prod("INNER1", "an inner", {"EA": {"baseQty": 1}}),
        _prod("CART12", "a carton", {"EA": {"baseQty": 1}, "CT": {"baseQty": 12}}),
        _prod("NOWT", "no weight", {"EA": {"baseQty": 1}}),
    ]
    wl = build_worklist(dims, prods)
    out = tmp_path / "worklist.xlsx"
    write_worklist_xlsx(wl, out)
    return out


def test_writes_workbook_with_headers(tmp_path):
    out = _build(tmp_path)
    assert out.exists()
    ws = load_workbook(out).active
    # row 1 is exactly the worklist header; data starts at row 2
    first_row = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    assert first_row == WORKLIST_COLUMNS


def _fill_hex(cell):
    rgb = cell.fill.fgColor.rgb
    return None if rgb is None else str(rgb)[-6:]


def test_carton_each_cells_highlighted_yellow(tmp_path):
    out = _build(tmp_path)
    ws = load_workbook(out).active
    # data rows start at row 2 (row 1 = header). CART12 is the 2nd data row → row 3.
    r = 3
    for col_name in ("each_l_mm", "each_w_mm", "each_h_mm"):
        cell = ws.cell(row=r, column=_col_letter(col_name))
        assert _fill_hex(cell) == _YELLOW


def test_inner_each_cells_greyed_with_captured_marker(tmp_path):
    out = _build(tmp_path)
    ws = load_workbook(out).active
    r = 2  # INNER1 = first data row
    cell = ws.cell(row=r, column=_col_letter("each_l_mm"))
    assert _fill_hex(cell) == _GREY
    assert cell.value == "= captured"


def test_weight_pending_cell_highlighted(tmp_path):
    out = _build(tmp_path)
    ws = load_workbook(out).active
    r = 4  # NOWT = third data row
    cell = ws.cell(row=r, column=_col_letter("outer_weight_kg"))
    assert _fill_hex(cell) == _YELLOW
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dims_worklist_xlsx.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.dims_worklist_xlsx'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/analysis/dims_worklist_xlsx.py
"""Render a dims worklist DataFrame to a highlighted xlsx.

Row 1 is the header (= WORKLIST_COLUMNS); data starts at row 2. Cells that
need operator action are filled yellow; inner rows' each-cells are greyed and
marked "= captured" so they are visibly not-for-fill.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from analysis.dims_worklist import WORKLIST_COLUMNS

_HEADER_BG = "1F2937"      # Go Cold dark
_YELLOW = "FFFFE0"          # needs fill / resolve
_GREY = "D9D9D9"            # not-for-fill (inner each cells)
_EACH_COLS = ("each_l_mm", "each_w_mm", "each_h_mm")

_yellow_fill = PatternFill("solid", fgColor=_YELLOW)
_grey_fill = PatternFill("solid", fgColor=_GREY)
_header_fill = PatternFill("solid", fgColor=_HEADER_BG)


def _col_idx(name: str) -> int:
    return WORKLIST_COLUMNS.index(name) + 1


def _cell_value(v: object):
    """openpyxl can't write pandas NA/NaN — coerce to None."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def write_worklist_xlsx(df: pd.DataFrame, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Dims Worklist"

    # header
    for j, name in enumerate(WORKLIST_COLUMNS, start=1):
        c = ws.cell(row=1, column=j, value=name)
        c.font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
        c.fill = _header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = max(12, len(name) + 2)

    # data
    for i, (_, row) in enumerate(df.iterrows()):
        r = i + 2
        for name in WORKLIST_COLUMNS:
            ws.cell(row=r, column=_col_idx(name), value=_cell_value(row[name]))

        kind = row["kind"]
        # each cells
        if kind == "carton":
            for name in _EACH_COLS:
                ws.cell(row=r, column=_col_idx(name)).fill = _yellow_fill
        elif kind == "inner":
            for name in _EACH_COLS:
                cell = ws.cell(row=r, column=_col_idx(name))
                cell.value = "= captured"
                cell.fill = _grey_fill
        else:  # unknown → resolve ipq + measure each
            ws.cell(row=r, column=_col_idx("inner_pack_qty")).fill = _yellow_fill
            for name in _EACH_COLS:
                ws.cell(row=r, column=_col_idx(name)).fill = _yellow_fill

        # weight gap
        if bool(row["weight_pending"]):
            ws.cell(row=r, column=_col_idx("outer_weight_kg")).fill = _yellow_fill

    ws.freeze_panes = "C2"  # freeze header row + code/name columns
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dims_worklist_xlsx.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/analysis/dims_worklist_xlsx.py tests/test_dims_worklist_xlsx.py
git commit -m "feat(dims): styled worklist xlsx writer with gap highlighting"
```

---

## Task 4: Orchestrator script

**Files:**
- Create: `scripts/build_dims_worklist.py`
- (No new unit test — this is IO/wiring; it is exercised by the live run in Task 5. Keep all logic in the tested modules.)

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Build the dims completion worklist.

Reads CartonCloud's live active Forage products (READ-ONLY) and joins them
against locally captured carton dims, then writes a highlighted xlsx listing
exactly what still needs measuring:
  - inner SKUs (inner-pack-qty == 1): captured dims already are each-level
  - carton SKUs (> 1): each-level L/W/H highlighted for physical measurement
  - unknown / not-captured / weight-pending: flagged

CC stays read-only. Nothing is written back to CC by this script.

Usage:
    .venv/bin/python scripts/build_dims_worklist.py \
        --dims data/dims/dims_2026-05-13.xlsx \
        --out  data/dims/dims_worklist_<date>.xlsx

If --out is omitted, writes data/dims/dims_worklist.xlsx.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# repo-root import shim (mirrors scripts/extract.py)
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from analysis.dim_loader import load_dimensions  # noqa: E402
from analysis.dims_worklist import build_worklist, captured_not_in_cc  # noqa: E402
from analysis.dims_worklist_xlsx import write_worklist_xlsx  # noqa: E402
from cc_client import CartonCloudClient  # noqa: E402
from cc_client.queries import search_warehouse_products  # noqa: E402

log = logging.getLogger("build_dims_worklist")


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (mirrors scripts/smoke_test.py)."""
    if not path.exists():
        return
    import os
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dims", type=Path,
                   default=_ROOT / "data/dims/dims_2026-05-13.xlsx",
                   help="captured dims capture sheet (default: May 2026 sheet)")
    p.add_argument("--out", type=Path,
                   default=_ROOT / "data/dims/dims_worklist.xlsx",
                   help="output worklist xlsx path")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _load_dotenv(_ROOT / ".env")

    log.info("loading captured dims from %s", args.dims)
    dims_df = load_dimensions(args.dims)

    log.info("pulling active Forage products from CartonCloud (read-only)…")
    client = CartonCloudClient.from_env()
    products = list(search_warehouse_products(client))
    log.info("  %d active products", len(products))

    wl = build_worklist(dims_df, products)
    orphans = captured_not_in_cc(dims_df, products)

    # summary
    counts = wl["kind"].value_counts().to_dict()
    log.info("worklist rows: %d", len(wl))
    log.info("  inner (complete)         : %d", counts.get("inner", 0))
    log.info("  carton (each-fill needed): %d", counts.get("carton", 0))
    log.info("  unknown (resolve ipq)    : %d", counts.get("unknown", 0))
    log.info("  weight pending           : %d", int(wl["weight_pending"].sum()))
    log.info("  no carton UoM in CC      : %d", int(wl["no_carton_uom"].sum()))
    log.info("  not captured locally     : %d", int(wl["not_captured"].sum()))
    if orphans:
        log.info("  captured but NOT in CC (%d): %s", len(orphans), ", ".join(orphans))

    write_worklist_xlsx(wl, args.out)
    log.info("wrote %s", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify it imports cleanly (no live call yet)**

Run: `.venv/bin/python -c "import ast; ast.parse(open('scripts/build_dims_worklist.py').read()); print('syntax ok')"`
Expected: `syntax ok`

Run: `.venv/bin/python scripts/build_dims_worklist.py --help`
Expected: argparse help text prints, exit 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_dims_worklist.py
git commit -m "feat(dims): build_dims_worklist orchestrator (read-only CC)"
```

---

## Task 5: Live run + sanity check + hand-off

**Files:** none (produces `data/dims/dims_worklist_2026-06-17.xlsx`).

- [ ] **Step 1: Confirm CC auth is green**

Run: `.venv/bin/python scripts/smoke_test.py`
Expected: `✅ smoke test passed`.

- [ ] **Step 2: Run the builder against live CC (read-only)**

Run:
```bash
.venv/bin/python scripts/build_dims_worklist.py \
  --dims data/dims/dims_2026-05-13.xlsx \
  --out  data/dims/dims_worklist_2026-06-17.xlsx
```
Expected summary roughly matches the design's measured split:
- inner (complete) ≈ **334**
- carton (each-fill needed) ≈ **73**
- unknown ≈ **2** (the blank-ipq rows) **plus** any CC products with no captured dims
- the `captured but NOT in CC` line lists any orphaned local codes

If the inner/carton counts are wildly off (e.g. 0 cartons), STOP — it signals a code-match or column-resolution problem; investigate before handing the sheet over.

- [ ] **Step 3: Eyeball the workbook**

Open `data/dims/dims_worklist_2026-06-17.xlsx` and confirm:
- row 1 headers, frozen below; data from row 2
- a known multi-pack SKU shows yellow each-L/W/H cells
- a known 1:1 SKU shows grey `= captured` each cells
- any missing-weight SKU shows a yellow weight cell

- [ ] **Step 4: Run the full suite (no regressions)**

Run: `.venv/bin/python -m pytest -q`
Expected: all green (existing 194 + the new worklist tests).

- [ ] **Step 5: Commit the generated worklist + hand off**

```bash
git add data/dims/dims_worklist_2026-06-17.xlsx
git commit -m "chore(dims): generated dims completion worklist 2026-06-17"
```

Then tell Jake: worklist ready at `data/dims/dims_worklist_2026-06-17.xlsx`; fill the yellow each-L/W/H cells for the ~73 carton SKUs (+ resolve the unknown-ipq rows and any pending weights), and hand it back to trigger Part 2 (the gated CC sync).

---

## Self-review

**Spec coverage:**
- CC-authoritative row set → Task 1/4 (`build_worklist` iterates products; script fetches active products). ✔
- Pre-fill captured dims, blank+highlight gaps → Task 1 (pre-fill) + Task 3 (highlight). ✔
- inner/carton/unknown classification by inner-pack-qty → Task 1 (`_classify`), Task 2 (unknown/blank). ✔
- Carton-UoM = baseQty == inner-pack-qty; flag when absent → Task 1 (`_find_uom_by_baseqty`, `no_carton_uom`). ✔
- Each-fill only for carton rows; inners marked `= captured`; unknown highlights ipq+each → Task 3. ✔
- Each weight derived (not a fill column) → not in worklist by construction (no each-weight column); documented. ✔
- Flags weight_pending / ipq_unknown / no_carton_uom → Tasks 1–2. ✔ (`baseqty_ne_innerpack` consolidated into `no_carton_uom`, noted up top.)
- Reuse dim_loader instead of new capture_sheet.py → noted as deviation; Task 4 imports `load_dimensions`. ✔
- Read-only CC; no writes in Part 1 → script uses default read-only client; no PATCH anywhere. ✔
- Tests use mock/in-memory data, no live CC in suite → Tasks 1–3. ✔ Live read only in Task 5.

**Placeholder scan:** no TBD/TODO; all code blocks complete. The one soft spot — the deliberately-awkward header-introspection line in Task 3's first test — is called out with explicit instruction to simplify to the `first_row == WORKLIST_COLUMNS` assertion.

**Type consistency:** `WORKLIST_COLUMNS`, `build_worklist`, `captured_not_in_cc`, `_classify`, `_find_uom_by_baseqty`, `write_worklist_xlsx(df, path)`, fills `_YELLOW`/`_GREY` used consistently across module + both test files + script.

**Scope:** single subsystem (worklist export), one coherent plan, produces a usable artefact. Part 2 explicitly excluded.
