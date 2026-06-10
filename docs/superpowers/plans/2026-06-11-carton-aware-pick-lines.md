# Carton-Aware Pick Lines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert each-denominated SO lines that span full cartons into carton picks routed to reserve locations, so picksheets match what pickers physically do.

**Architecture:** A new pure-pandas splitter (`carton_split.py`) expands convertible lines into CTN + EA-remainder lines before wave generation. The SOH→location helper in `wave_runner.py` stops collapsing to one location per SKU and instead returns all candidates tagged with role (pick face / reserve) and qty. `wave_picks.py` selects a location per line — EA lines keep today's pick-face-first behaviour, CTN lines go to the largest-qty reserve — and consolidates by (location, SKU, pick_uom). CSV/PDF outputs and the picks console surface the new columns and counts.

**Tech Stack:** Python 3.14 venv (`.venv/bin/python` — bin wrappers have stale shebangs, always use `.venv/bin/python -m pytest`), pandas, FastAPI/Jinja2, reportlab.

**Spec:** `docs/superpowers/specs/2026-06-11-carton-aware-pick-lines-design.md`

**Backwards-compatibility invariant (zero-breakage rule):** every change is additive. SO-line frames without `pick_uom` and location frames without `role`/`qty` must flow through `generate_wave_pick_sheets` exactly as today. The full existing test suite must stay green after every task.

---

### Task 1: Each→carton line splitter

**Files:**
- Create: `src/analysis/carton_split.py`
- Modify: `src/analysis/__init__.py`
- Test: `tests/test_carton_split.py` (create)

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_carton_split.py`:

```python
"""Unit tests for the each→carton line splitter (carton-aware picks).

73 of Forage's SKUs are each/ctn combos (inner_pack_qty 2–12). When an
EA line spans one or more full cartons the picker grabs cartons off the
reserve pallet, so the picksheet must say cartons — these tests pin the
conversion maths and the pass-through guarantees.
"""
from __future__ import annotations

import pandas as pd

from analysis.carton_split import PICK_UOM_CARTON, PICK_UOM_EACH, split_lines


def _dims(rows):
    return pd.DataFrame(rows, columns=["product_code", "inner_pack_qty"])


def _lines(rows):
    return pd.DataFrame(
        rows, columns=["so_id", "product_code", "product_name", "quantity"]
    )


def test_exact_multiple_becomes_single_carton_line():
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 24)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 1
    row = out.iloc[0]
    assert row["pick_uom"] == PICK_UOM_CARTON
    assert row["quantity"] == 4
    assert row["qty_eaches"] == 24


def test_remainder_splits_into_ctn_plus_ea():
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 27)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 2
    ctn = out[out["pick_uom"] == PICK_UOM_CARTON].iloc[0]
    ea = out[out["pick_uom"] == PICK_UOM_EACH].iloc[0]
    assert ctn["quantity"] == 4
    assert ctn["qty_eaches"] == 24
    assert ea["quantity"] == 3
    assert pd.isna(ea["qty_eaches"])


def test_under_one_carton_passes_through():
    out = split_lines(_lines([(1, "FD-BAR", "Bar", 5)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH
    assert out.iloc[0]["quantity"] == 5
    assert pd.isna(out.iloc[0]["qty_eaches"])


def test_inner_pack_qty_one_passes_through():
    """334 SKUs have ipq=1 (the each IS the carton) — never converted."""
    out = split_lines(_lines([(1, "FRG-01", "Oats", 24)]), _dims([("FRG-01", 1)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH
    assert out.iloc[0]["quantity"] == 24


def test_sku_missing_from_dims_passes_through():
    out = split_lines(_lines([(1, "MYSTERY", "?", 24)]), _dims([("FD-BAR", 6)]))
    assert len(out) == 1
    assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH


def test_min_full_cartons_raises_the_bar():
    lines = _lines([(1, "FD-BAR", "Bar", 24), (2, "FD-BAR", "Bar", 6)])
    out = split_lines(lines, _dims([("FD-BAR", 6)]), min_full_cartons=2)
    by_so = out.set_index("so_id")
    assert by_so.loc[1, "pick_uom"] == PICK_UOM_CARTON   # 4 ctns >= 2
    assert by_so.loc[2, "pick_uom"] == PICK_UOM_EACH     # 1 ctn < 2


def test_none_or_empty_dims_passes_everything_through():
    lines = _lines([(1, "FD-BAR", "Bar", 24)])
    for dims in (None, pd.DataFrame()):
        out = split_lines(lines, dims)
        assert len(out) == 1
        assert out.iloc[0]["pick_uom"] == PICK_UOM_EACH


def test_other_columns_survive_the_split():
    lines = _lines([(1, "FD-BAR", "Bar", 27)]).assign(so_ref="SO-77", batch="B1")
    out = split_lines(lines, _dims([("FD-BAR", 6)]))
    assert set(out["so_ref"]) == {"SO-77"}
    assert set(out["batch"]) == {"B1"}
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_carton_split.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.carton_split'`

- [ ] **Step 1.3: Write the implementation**

Create `src/analysis/carton_split.py`:

```python
"""Split each-denominated SO lines into carton picks + each remainders.

Forage orders everything in eaches in CartonCloud, but 73 SKUs are
each/carton combos (``inner_pack_qty`` of 2–12 eaches per carton). When
an EA line spans at least ``min_full_cartons`` full cartons the picker
physically pulls cartons off the reserve pallet, so the picksheet line
must say cartons and point at the reserve — not the pick face.

``split_lines`` is pure (no I/O): it returns the input frame with two
extra columns and convertible lines expanded:

  * ``pick_uom``  — "CTN" for converted carton lines, "EA" otherwise
  * ``qty_eaches`` — original each-count covered by a CTN line (for
    "4 CTN (24 EA)" display); NA on EA lines

On CTN lines ``quantity`` is the carton count; on EA lines it remains
the each count (a remainder line carries ``quantity % inner_pack_qty``).
Lines pass through untouched when the SKU has ``inner_pack_qty`` <= 1,
is absent from dims, or the qty is under the threshold.
"""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

PICK_UOM_CARTON = "CTN"
PICK_UOM_EACH = "EA"


def split_lines(
    so_lines: pd.DataFrame,
    dims: pd.DataFrame | None,
    min_full_cartons: int = 1,
) -> pd.DataFrame:
    """Return ``so_lines`` with pick_uom / qty_eaches, splitting combo
    lines that span at least ``min_full_cartons`` full cartons."""
    out = so_lines.copy()
    out["pick_uom"] = PICK_UOM_EACH
    out["qty_eaches"] = pd.NA
    if (
        out.empty
        or dims is None
        or dims.empty
        or "inner_pack_qty" not in dims.columns
    ):
        return out

    ipq_map = (
        dims.dropna(subset=["product_code"])
        .drop_duplicates("product_code")
        .set_index("product_code")["inner_pack_qty"]
    )
    qty = pd.to_numeric(out["quantity"], errors="coerce").fillna(0)
    ipq = pd.to_numeric(out["product_code"].map(ipq_map), errors="coerce")

    threshold = max(int(min_full_cartons), 1)
    convertible = (ipq > 1) & (qty >= ipq * threshold)
    if not convertible.any():
        return out

    combo = out[convertible].copy()
    full_ctns = (qty[convertible] // ipq[convertible]).astype(int)
    rem = (qty[convertible] % ipq[convertible]).astype(int)

    ctn = combo.copy()
    ctn["quantity"] = full_ctns.astype(float)
    ctn["pick_uom"] = PICK_UOM_CARTON
    ctn["qty_eaches"] = (full_ctns * ipq[convertible]).astype(int)

    remainder = combo[rem > 0].copy()
    remainder["quantity"] = rem[rem > 0].astype(float)
    remainder["pick_uom"] = PICK_UOM_EACH
    remainder["qty_eaches"] = pd.NA

    result = pd.concat([out[~convertible], ctn, remainder], ignore_index=True)
    log.info(
        "carton split: %d/%d lines converted to carton picks "
        "(%d with each remainders, min_full_cartons=%d)",
        len(ctn), len(out), len(remainder), threshold,
    )
    return result
```

- [ ] **Step 1.4: Export from the analysis package**

In `src/analysis/__init__.py`, after the line `from .dim_loader import load_dimensions` add:

```python
from .carton_split import PICK_UOM_CARTON, PICK_UOM_EACH, split_lines
```

and in `__all__`, after the `"load_dimensions",` entry add:

```python
    "PICK_UOM_CARTON", "PICK_UOM_EACH", "split_lines",
```

- [ ] **Step 1.5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_carton_split.py -v`
Expected: 8 passed

- [ ] **Step 1.6: Commit**

```bash
git add src/analysis/carton_split.py src/analysis/__init__.py tests/test_carton_split.py
git commit -m "feat(waves): each→carton line splitter for combo SKUs"
```

---

### Task 2: SOH location candidates (all locations per SKU, role + qty)

**Files:**
- Modify: `src/wave_runner.py:105-157` (`_SKU_LOC_COLS`, `build_sku_locations_from_soh`)
- Test: `tests/test_soh_location_candidates.py` (create)

- [ ] **Step 2.1: Write the failing tests**

Create `tests/test_soh_location_candidates.py`:

```python
"""SOH rows → per-SKU location candidates with role + qty.

The carton-aware picker needs every live location per SKU (pick faces
AND reserves), not just the single best one. Grammar refresher:
AA-01-01 / AA-01-02 are pick faces; AA-01-03+ is reserve.
"""
from __future__ import annotations

import pandas as pd

from wave_runner import build_sku_location_candidates, build_sku_locations_from_soh


def _items():
    return [
        {"product_code": "FD-BAR", "location_name": "AA-01-03",
         "location_id": "x1", "qty": 120, "uom_name": "Each"},
        {"product_code": "FD-BAR", "location_name": "AA-01-01",
         "location_id": "x2", "qty": 18, "uom_name": "Each"},
        {"product_code": "FD-BAR", "location_name": "AB-02-03",
         "location_id": "x3", "qty": 60, "uom_name": "Each"},
    ]


def test_candidates_keep_every_location_best_first():
    df = build_sku_location_candidates(_items())
    assert len(df) == 3
    assert df.iloc[0]["location"] == "AA-01-01"          # pick face leads
    assert df.iloc[0]["role"] == "pick_face"
    assert df.iloc[0]["qty"] == 18
    assert list(df["role"][1:]) == ["reserve", "reserve"]
    assert {"product_code", "location", "aisle", "bay", "level",
            "sublevel", "role", "qty"} <= set(df.columns)


def test_single_location_wrapper_unchanged():
    df = build_sku_locations_from_soh(_items())
    assert len(df) == 1
    assert df.iloc[0]["location"] == "AA-01-01"


def test_unparseable_location_treated_as_reserve():
    items = [{"product_code": "X", "location_name": "FLOOR-STAGING",
              "location_id": "y", "qty": 5, "uom_name": "Each"}]
    df = build_sku_location_candidates(items)
    assert len(df) == 1
    assert df.iloc[0]["role"] == "reserve"


def test_empty_items_returns_empty_frame():
    df = build_sku_location_candidates([])
    assert df.empty
    assert "role" in df.columns and "qty" in df.columns
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_soh_location_candidates.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_sku_location_candidates'`

- [ ] **Step 2.3: Implement**

In `src/wave_runner.py`, directly below the `_SKU_LOC_COLS = [...]` line (line 105), add:

```python
_SKU_CAND_COLS = [
    "product_code", "location", "aisle", "bay", "level", "sublevel",
    "role", "qty",
]


def build_sku_location_candidates(items: list[dict]) -> pd.DataFrame:
    """Every live SOH location per SKU, best-first within each SKU.

    Per-SKU ordering mirrors the old single-pick selection: pick faces
    before reserve, lowest grammar position, then walk order. ``role``
    is 'pick_face' or 'reserve' — grammar-unknown names collapse to
    'reserve' (if it isn't a known pick face, treat it as forklift
    territory). ``qty`` is the SOH stock figure for that (SKU, location)
    bucket in the customer's ordering UOM (eaches for Forage).
    """
    if not items:
        return pd.DataFrame(columns=_SKU_CAND_COLS)

    candidates: list[dict] = []
    for it in items:
        code = it.get("product_code")
        name = it.get("location_name")
        if not code or not name:
            continue
        info = parse_location_name(name)
        is_pick_face = info.role_by_grammar == "pick_face"
        candidates.append({
            "product_code": code,
            "location": name,
            "aisle": info.aisle,
            "bay": info.bay,
            "level": info.level,
            "sublevel": info.sublevel,
            "role": "pick_face" if is_pick_face else "reserve",
            "qty": pd.to_numeric(it.get("qty"), errors="coerce"),
            "_role_rank": 0 if is_pick_face else 1,
            "position": info.position,
        })

    if not candidates:
        return pd.DataFrame(columns=_SKU_CAND_COLS)

    df = pd.DataFrame(candidates)
    df = df.sort_values(
        ["product_code", "_role_rank", "position",
         "aisle", "bay", "level", "sublevel"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    return df[_SKU_CAND_COLS]
```

Then replace the body of `build_sku_locations_from_soh` (keep its docstring, summarised) so it delegates:

```python
def build_sku_locations_from_soh(items: list[dict]) -> pd.DataFrame:
    """Collapse live SOH rows into one best location per SKU.

    Thin wrapper over ``build_sku_location_candidates`` kept for callers
    that only want the single-location view (selection rules documented
    there). Returns ``_SKU_LOC_COLS`` — one row per SKU.
    """
    cands = build_sku_location_candidates(items)
    if cands.empty:
        return pd.DataFrame(columns=_SKU_LOC_COLS)
    return (
        cands.drop_duplicates("product_code", keep="first")
        .reset_index(drop=True)[_SKU_LOC_COLS]
    )
```

Delete the now-dead loop body of the old implementation (the `candidates` building and sort previously inside `build_sku_locations_from_soh`).

- [ ] **Step 2.4: Run new + existing SOH tests**

Run: `.venv/bin/python -m pytest tests/test_soh_location_candidates.py tests/test_soh_sku_locations.py tests/test_wave_runner.py -v`
Expected: all pass (the wrapper preserves the old contract)

- [ ] **Step 2.5: Commit**

```bash
git add src/wave_runner.py tests/test_soh_location_candidates.py
git commit -m "feat(waves): expose all SOH locations per SKU with role + qty"
```

---

### Task 3: Per-line location selection + (SKU, pick_uom) consolidation

**Files:**
- Modify: `src/analysis/wave_picks.py` (lookup ~111–128, line loop ~305–401, consolidation ~434–472, summary ~262–303 & 495–524, `_empty_pick_lines` ~80–94)
- Test: `tests/test_carton_pick_locations.py` (create)

- [ ] **Step 3.1: Write the failing tests**

Create `tests/test_carton_pick_locations.py`:

```python
"""Carton-aware location selection + consolidation in wave generation.

CTN lines must route to the largest-qty reserve; EA lines keep the
pick-face-first behaviour; the two never merge into one pick row.
Scaffold mirrors tests/test_wave_consolidation.py.
"""
from __future__ import annotations

import pandas as pd

from analysis.routing import STREAM_BENCH, StreamClassification
from analysis.wave_picks import generate_wave_pick_sheets

_TS = "2026-06-11T10:00:00+10:00"


def _classification(per_order):
    return StreamClassification(
        per_order=per_order,
        counts_by_stream=pd.Series(dtype=int),
        rule_hit_counts=pd.Series(dtype=int),
        threshold_used=0.0,
    )


def _order_row(so_id, so_ref):
    return {
        "so_id": so_id, "so_ref": so_ref, "stream": STREAM_BENCH,
        "total_cartons": 5, "line_count": 2, "ts_packed": _TS,
        "delivery_state": "VIC", "customer_name": "The Forage Company",
        "delivery_company": f"Shop {so_ref}", "delivery_suburb": "Scoresby",
        "delivery_postcode": "3179",
    }


def _sku_locations():
    """FD-BAR: pick face + two reserves (AB-04-03 holds the most).
    PFONLY: stock at the pick face only."""
    return pd.DataFrame([
        {"product_code": "FD-BAR", "location": "AA-01-01", "aisle": "AA",
         "bay": 1, "level": 1, "sublevel": None, "role": "pick_face", "qty": 30},
        {"product_code": "FD-BAR", "location": "AA-01-03", "aisle": "AA",
         "bay": 1, "level": 3, "sublevel": None, "role": "reserve", "qty": 60},
        {"product_code": "FD-BAR", "location": "AB-04-03", "aisle": "AB",
         "bay": 4, "level": 3, "sublevel": None, "role": "reserve", "qty": 120},
        {"product_code": "PFONLY", "location": "AA-02-01", "aisle": "AA",
         "bay": 2, "level": 1, "sublevel": None, "role": "pick_face", "qty": 50},
    ])


def _run(so_lines):
    per_order = pd.DataFrame([_order_row(1, "SO-A")])
    return generate_wave_pick_sheets(
        classification=_classification(per_order),
        so_lines=so_lines,
        sku_locations=_sku_locations(),
        early_release_cartons=10_000,
    )


def _line(code, qty, pick_uom, qty_eaches=None):
    return {"so_id": 1, "product_code": code, "product_name": code,
            "quantity": qty, "pick_uom": pick_uom,
            "qty_eaches": qty_eaches if qty_eaches is not None else pd.NA}


def test_ctn_line_routes_to_largest_reserve():
    res = _run(pd.DataFrame([_line("FD-BAR", 4, "CTN", 24)]))
    picks = res.sheets[0].pick_lines
    assert len(picks) == 1
    row = picks.iloc[0]
    assert row["location"] == "AB-04-03"
    assert row["pick_uom"] == "CTN"
    assert row["qty_cartons"] == 4
    assert row["qty_eaches"] == 24
    assert not row["reserve_unavailable"]


def test_ea_line_keeps_pick_face():
    res = _run(pd.DataFrame([_line("FD-BAR", 3, "EA")]))
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AA-01-01"
    assert row["pick_uom"] == "EA"


def test_ctn_and_ea_of_same_sku_stay_separate_rows():
    res = _run(pd.DataFrame([
        _line("FD-BAR", 4, "CTN", 24),
        _line("FD-BAR", 3, "EA"),
    ]))
    picks = res.sheets[0].pick_lines
    assert len(picks) == 2
    assert set(picks["pick_uom"]) == {"CTN", "EA"}
    assert set(picks["location"]) == {"AB-04-03", "AA-01-01"}


def test_pick_face_only_sku_falls_back_with_flag():
    res = _run(pd.DataFrame([_line("PFONLY", 2, "CTN", 12)]))
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AA-02-01"
    assert bool(row["reserve_unavailable"]) is True
    assert res.summary["n_carton_picks_no_reserve"] == 1


def test_reserve_short_of_stock_is_flagged():
    # needs 240 eaches; biggest reserve holds 120
    res = _run(pd.DataFrame([_line("FD-BAR", 40, "CTN", 240)]))
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AB-04-03"
    assert bool(row["qty_short"]) is True


def test_summary_counts_carton_lines():
    res = _run(pd.DataFrame([
        _line("FD-BAR", 4, "CTN", 24),
        _line("FD-BAR", 3, "EA"),
    ]))
    assert res.summary["n_lines_carton_pick"] == 1
    assert res.summary["n_carton_picks_no_reserve"] == 0


def test_legacy_frames_without_uom_or_role_still_work():
    """Zero-breakage guarantee: no pick_uom column + no role/qty column
    must reproduce today's behaviour (first location, EA, no flags)."""
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "FD-BAR",
         "product_name": "Bar", "quantity": 5},
    ])
    sku_locations = pd.DataFrame([
        {"product_code": "FD-BAR", "location": "AA-01-01", "aisle": "AA",
         "bay": 1, "level": 1, "sublevel": None},
    ])
    per_order = pd.DataFrame([_order_row(1, "SO-A")])
    res = generate_wave_pick_sheets(
        classification=_classification(per_order),
        so_lines=so_lines, sku_locations=sku_locations,
        early_release_cartons=10_000,
    )
    row = res.sheets[0].pick_lines.iloc[0]
    assert row["location"] == "AA-01-01"
    assert row["pick_uom"] == "EA"
    assert row["qty_cartons"] == 5
    assert res.summary["n_lines_carton_pick"] == 0
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_carton_pick_locations.py -v`
Expected: FAIL — KeyError on `pick_uom` / missing summary keys

- [ ] **Step 3.3: Implement in `src/analysis/wave_picks.py`**

(a) Add to the imports block (after the `.routing` import):

```python
from .carton_split import PICK_UOM_CARTON, PICK_UOM_EACH
```

(b) Replace `_empty_pick_lines` column list with:

```python
    return pd.DataFrame(columns=[
        "walk_index",
        "location",
        "aisle",
        "bay",
        "level",
        "sublevel",
        "product_code",
        "product_name",
        "pick_uom",
        "qty_cartons",
        "qty_eaches",
        "cartons_running_total",
        "contributing_so_refs",
        "unallocated",
        "reserve_unavailable",
        "qty_short",
    ])
```

(c) Replace `_build_sku_location_lookup` (lines 111–128) with a version that keeps every candidate row and defaults `role`/`qty`:

```python
def _build_sku_location_lookup(
    sku_locations: pd.DataFrame | None,
) -> pd.DataFrame:
    """Normalise the live SKU -> location frame, keeping EVERY candidate
    location per SKU (rows must arrive best-first — pick faces, then
    walk order, as ``build_sku_location_candidates`` produces). Frames
    without ``role``/``qty`` (legacy single-location callers) get
    defaults of 'unknown'/NA — selection treats unknown as reserve."""
    cols = ["product_code", "location", "aisle", "bay", "level",
            "sublevel", "role", "qty"]
    if sku_locations is None or sku_locations.empty:
        return pd.DataFrame(columns=cols)
    s = sku_locations.copy()
    if "assigned_location" in s.columns and "location" not in s.columns:
        s = s.rename(columns={"assigned_location": "location"})
    if "location" not in s.columns:
        raise ValueError("sku_locations must include a 'location' column")
    for c in ("aisle", "bay", "level", "sublevel"):
        if c not in s.columns:
            s[c] = pd.NA
    if "role" not in s.columns:
        s["role"] = "unknown"
    if "qty" not in s.columns:
        s["qty"] = pd.NA
    return s.reset_index(drop=True)[cols]
```

(d) Add a selection helper directly below it:

```python
def _select_location(
    cands: pd.DataFrame, pick_uom: str, needed_eaches: float | None
) -> tuple[pd.Series, dict]:
    """Choose the location row for one pick line.

    EA lines take the head row (today's pick-face-first behaviour).
    CTN lines take the non-pick-face row with the most stock — first
    occurrence wins ties, preserving walk order — falling back to the
    head row flagged ``reserve_unavailable`` when the SKU has no
    reserve stock. ``qty_short`` marks a reserve known to hold fewer
    eaches than the line needs.
    """
    flags = {"reserve_unavailable": False, "qty_short": False}
    if pick_uom != PICK_UOM_CARTON:
        return cands.iloc[0], flags
    reserves = cands[cands["role"] != "pick_face"]
    if reserves.empty:
        flags["reserve_unavailable"] = True
        return cands.iloc[0], flags
    qty = pd.to_numeric(reserves["qty"], errors="coerce")
    best_label = qty.fillna(-1.0).idxmax()
    row = reserves.loc[best_label]
    best_qty = qty.loc[best_label]
    if (
        needed_eaches is not None
        and pd.notna(best_qty)
        and best_qty < needed_eaches
    ):
        flags["qty_short"] = True
    return row, flags
```

(e) In `generate_wave_pick_sheets`, after `so_lines = so_lines.copy()` / quantity coercion (~line 324), default the new columns:

```python
    if "pick_uom" not in so_lines.columns:
        so_lines["pick_uom"] = PICK_UOM_EACH
    if "qty_eaches" not in so_lines.columns:
        so_lines["qty_eaches"] = pd.NA
```

(f) Replace the single-row index (lines 306–309) with per-SKU groups:

```python
    sku_lookup = _build_sku_location_lookup(sku_locations)
    sku_groups: dict = (
        {code: g for code, g in sku_lookup.groupby("product_code", sort=False)}
        if not sku_lookup.empty else {}
    )
```

(g) Replace the per-line body (lines 369–401) with:

```python
            for line in lines.itertuples(index=False):
                code = getattr(line, "product_code", None)
                qty = float(getattr(line, "quantity", 0) or 0)
                if not code or qty <= 0:
                    continue
                pick_uom = str(getattr(line, "pick_uom", "") or PICK_UOM_EACH)
                qty_eaches = getattr(line, "qty_eaches", None)
                base = {
                    "so_id": sid,
                    "product_code": code,
                    "product_name": getattr(line, "product_name", ""),
                    "quantity": qty,
                    "pick_uom": pick_uom,
                    "qty_eaches": qty_eaches,
                }
                cands = sku_groups.get(code)
                if cands is None:
                    # No live location — line still rides the wave, flagged.
                    order_rows.append({
                        **base,
                        "location": "UNALLOCATED",
                        "aisle": pd.NA, "bay": pd.NA,
                        "level": pd.NA, "sublevel": pd.NA,
                        "unallocated": True,
                        "reserve_unavailable": False,
                        "qty_short": False,
                    })
                    continue
                needed = (
                    float(qty_eaches)
                    if qty_eaches is not None and pd.notna(qty_eaches)
                    else None
                )
                loc_row, flags = _select_location(cands, pick_uom, needed)
                order_rows.append({
                    **base,
                    "location": loc_row.get("location"),
                    "aisle": loc_row.get("aisle"),
                    "bay": loc_row.get("bay"),
                    "level": loc_row.get("level"),
                    "sublevel": loc_row.get("sublevel"),
                    "unallocated": False,
                    **flags,
                })
```

(h) Replace the consolidation groupby (lines 436–449) with:

```python
        consolidated = picks_df.groupby(
            ["location", "product_code", "pick_uom"], dropna=False, sort=False
        ).agg(
            product_name=("product_name", "first"),
            aisle=("aisle", "first"),
            bay=("bay", "first"),
            level=("level", "first"),
            sublevel=("sublevel", "first"),
            qty_cartons=("quantity", "sum"),
            qty_eaches=("qty_eaches", lambda s: (
                int(pd.to_numeric(s, errors="coerce").sum())
                if pd.to_numeric(s, errors="coerce").notna().any()
                else pd.NA
            )),
            contributing_so_refs=("so_ref", lambda s: ", ".join(
                sorted({x for x in s if x})
            )),
            unallocated=("unallocated", "first"),
            reserve_unavailable=("reserve_unavailable", "max"),
            qty_short=("qty_short", "max"),
        ).reset_index()
```

(i) Replace `ordered_cols` (lines 458–471) with:

```python
        ordered_cols = [
            "walk_index",
            "location",
            "aisle",
            "bay",
            "level",
            "sublevel",
            "product_code",
            "product_name",
            "pick_uom",
            "qty_cartons",
            "qty_eaches",
            "cartons_running_total",
            "contributing_so_refs",
            "unallocated",
            "reserve_unavailable",
            "qty_short",
        ]
```

(j) After the `n_skus_unallocated` computation (~line 504), add:

```python
    n_lines_carton_pick = sum(
        int((s.pick_lines["pick_uom"] == PICK_UOM_CARTON).sum())
        for s in sheets if "pick_uom" in s.pick_lines.columns
    )
    n_carton_picks_no_reserve = sum(
        int(s.pick_lines["reserve_unavailable"].fillna(False).sum())
        for s in sheets if "reserve_unavailable" in s.pick_lines.columns
    )
```

and add to `result.summary`:

```python
        "n_lines_carton_pick": n_lines_carton_pick,
        "n_carton_picks_no_reserve": n_carton_picks_no_reserve,
```

(k) Add `"n_lines_carton_pick": 0, "n_carton_picks_no_reserve": 0,` to each of the three early-return summary dicts (lines 264–271, 276–283, 295–302).

- [ ] **Step 3.4: Run new + all wave tests**

Run: `.venv/bin/python -m pytest tests/test_carton_pick_locations.py tests/test_wave_consolidation.py tests/test_wave_picks_pallet_sheets.py tests/test_plan_waves_immediate.py tests/test_make_wave_id.py -v`
Expected: all pass — the legacy-frame test and the existing consolidation suite are the zero-breakage proof

- [ ] **Step 3.5: Commit**

```bash
git add src/analysis/wave_picks.py tests/test_carton_pick_locations.py
git commit -m "feat(waves): route CTN lines to reserve locations, consolidate by (SKU, pick_uom)"
```

---

### Task 4: CSV + PDF picksheet output

**Files:**
- Modify: `src/output/csv_picksheet.py:40-53`
- Modify: `src/output/pdf_picksheet.py` (`_pick_lines_table` ~397–473, `_unallocated_table` ~476–530)
- Test: `tests/test_csv_picksheet.py`, `tests/test_pdf_picksheet.py` (extend both)

- [ ] **Step 4.1: Write the failing CSV test**

Append to `tests/test_csv_picksheet.py` (reuse the file's existing sheet-builder helpers; if it builds `WavePickSheet` inline, mirror that pattern):

```python
def test_picks_csv_carries_carton_columns(tmp_path):
    from analysis.wave_picks import WavePickSheet
    from output.csv_picksheet import write_wave_csvs
    import pandas as pd

    pick_lines = pd.DataFrame([
        {"walk_index": 1, "location": "AB-04-03", "aisle": "AB", "bay": 4,
         "level": 3, "sublevel": None, "product_code": "FD-BAR",
         "product_name": "Choc Bar 6pk", "pick_uom": "CTN",
         "qty_cartons": 4, "qty_eaches": 24, "cartons_running_total": 4,
         "contributing_so_refs": "SO-1", "unallocated": False,
         "reserve_unavailable": False, "qty_short": False},
    ])
    orders = pd.DataFrame([
        {"so_ref": "SO-1", "customer_name": "Forage",
         "delivery_company": "Shop", "delivery_suburb": "Scoresby",
         "delivery_state": "VIC", "delivery_postcode": "3179",
         "cartons": 4, "lines": 1},
    ])
    sheet = WavePickSheet(
        wave_id="W-CTN", stream="3_wave_bench", run_group="VIC",
        receive_date=None, orders=orders, pick_lines=pick_lines,
        total_cartons=4, total_lines=1, estimated_walk_distance_m=5.0,
    )
    paths = write_wave_csvs(sheet, tmp_path)
    out = pd.read_csv(paths.picks)
    assert "pick_uom" in out.columns
    assert out.iloc[0]["pick_uom"] == "CTN"
    assert out.iloc[0]["qty_eaches"] == 24
    assert "reserve_unavailable" in out.columns
    assert "qty_short" in out.columns
```

- [ ] **Step 4.2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_csv_picksheet.py -v`
Expected: new test FAILS (`pick_uom` not in columns); existing tests pass

- [ ] **Step 4.3: Update the CSV column list**

In `src/output/csv_picksheet.py`, replace `picks_cols` with:

```python
    picks_cols = [
        "walk_index",
        "location",
        "aisle",
        "bay",
        "level",
        "sublevel",
        "product_code",
        "product_name",
        "pick_uom",
        "qty_cartons",
        "qty_eaches",
        "cartons_running_total",
        "contributing_so_refs",
        "unallocated",
        "reserve_unavailable",
        "qty_short",
    ]
```

(`reindex` already fills the new columns with NaN for old frames — no other change needed.)

- [ ] **Step 4.4: Write the failing PDF test**

Append to `tests/test_pdf_picksheet.py` (copy the sheet/orders scaffold from the existing tests at the top of that file — only the pick_lines rows differ):

```python
def test_pdf_renders_carton_pick_lines(tmp_path):
    import pandas as pd
    from analysis.wave_picks import WavePickSheet
    from output.pdf_picksheet import generate_wave_pdf

    pick_lines = pd.DataFrame([
        {"walk_index": 1, "location": "AB-04-03", "aisle": "AB", "bay": 4,
         "level": 3, "sublevel": None, "product_code": "FD-BAR",
         "product_name": "Choc Bar 6pk", "pick_uom": "CTN",
         "qty_cartons": 4, "qty_eaches": 24, "cartons_running_total": 4,
         "contributing_so_refs": "SO-1", "unallocated": False,
         "reserve_unavailable": True, "qty_short": False},
        {"walk_index": 2, "location": "AA-01-01", "aisle": "AA", "bay": 1,
         "level": 1, "sublevel": None, "product_code": "FD-BAR",
         "product_name": "Choc Bar 6pk", "pick_uom": "EA",
         "qty_cartons": 3, "qty_eaches": pd.NA, "cartons_running_total": 7,
         "contributing_so_refs": "SO-1", "unallocated": False,
         "reserve_unavailable": False, "qty_short": False},
    ])
    orders = pd.DataFrame([
        {"so_ref": "SO-1", "customer_name": "Forage",
         "delivery_company": "Shop", "delivery_suburb": "Scoresby",
         "delivery_state": "VIC", "delivery_postcode": "3179",
         "cartons": 7, "lines": 2},
    ])
    sheet = WavePickSheet(
        wave_id="W-CTN", stream="3_wave_bench", run_group="VIC",
        receive_date=None, orders=orders, pick_lines=pick_lines,
        total_cartons=7, total_lines=2, estimated_walk_distance_m=10.0,
    )
    out = tmp_path / "w.pdf"
    generate_wave_pdf(sheet, out)
    assert out.exists()
    assert out.stat().st_size > 1000
```

(If `generate_wave_pdf` in the existing tests is called with extra kwargs, match that call signature.)

- [ ] **Step 4.5: Update the PDF qty + location cells**

In `src/output/pdf_picksheet.py`, inside `_pick_lines_table`'s row loop (currently lines 409–430), replace the location and qty cells. The loop body becomes:

```python
    for r in pick_lines.itertuples(index=False):
        pick_uom = str(getattr(r, "pick_uom", "") or "")
        qty_eaches = getattr(r, "qty_eaches", None)
        if pick_uom == "CTN":
            eaches = (
                f"<br/><font size=7>({int(qty_eaches)} EA)</font>"
                if qty_eaches is not None and pd.notna(qty_eaches) else ""
            )
            qty_html = f"<b>{int(r.qty_cartons):,} CTN</b>{eaches}"
        else:
            qty_html = f"<b>{int(r.qty_cartons):,}</b>"
        loc_html = _esc(r.location)
        if bool(getattr(r, "reserve_unavailable", False) or False):
            loc_html += "<br/><font size=6>NO RESERVE — PICK FACE</font>"
        if bool(getattr(r, "qty_short", False) or False):
            loc_html += "<br/><font size=6>CHECK QTY AT LOCATION</font>"
        rows.append([
            _wrap_cell(
                f"<b>{int(r.walk_index)}</b>",
                THEME.body_font_bold, 12, "center",
            ),
            _wrap_cell(loc_html, THEME.mono_font, 11, "center"),
            _wrap_cell(_esc(r.product_code), THEME.body_font_bold, 9),
            _wrap_cell(_esc(r.product_name), THEME.body_font, 9),
            _wrap_cell(qty_html, THEME.body_font_bold, 13, "center"),
            _wrap_cell(
                f"{int(r.cartons_running_total):,}",
                THEME.body_font, 9, "center",
            ),
            _wrap_cell(_esc(r.contributing_so_refs), THEME.body_font, 8),
            _wrap_cell("", THEME.body_font, 9),
        ])
```

Note on the flag guards: `getattr(...) or False` collapses `pd.NA`/NaN to `False` before `bool()` — `bool(pd.NA)` raises.

Widen the Qty column to fit "12 CTN": in `_pick_lines_table`'s `col_widths`, change `46 * mm` (description) to `40 * mm` and `14 * mm` (qty) to `20 * mm`.

Apply the same qty-cell logic in `_unallocated_table`'s row loop (replacing the plain `qty_cartons` cell at lines 502–505), and change its `col_widths` `63 * mm` (description) to `57 * mm` and `14 * mm` (qty) to `20 * mm`.

- [ ] **Step 4.6: Run output tests**

Run: `.venv/bin/python -m pytest tests/test_csv_picksheet.py tests/test_pdf_picksheet.py -v`
Expected: all pass (old frames hit the `getattr` defaults — unchanged rendering)

- [ ] **Step 4.7: Commit**

```bash
git add src/output/csv_picksheet.py src/output/pdf_picksheet.py tests/test_csv_picksheet.py tests/test_pdf_picksheet.py
git commit -m "feat(output): show CTN picks with each-equivalents and reserve flags on picksheets"
```

---

### Task 5: Pipeline integration in wave_runner

**Files:**
- Modify: `src/wave_runner.py` (`WaveRunSettings` ~55–77, `_settings_dict` ~330–349, steps 6–7 in `run_wave_generation` ~453–486)

- [ ] **Step 5.1: Add the setting**

In `WaveRunSettings`, after `run_group_col: str = "predicted_run"` add:

```python
    min_full_cartons: int = 1
```

In `_settings_dict`'s returned dict, after `"run_group_col": settings.run_group_col,` add:

```python
        "min_full_cartons": settings.min_full_cartons,
```

- [ ] **Step 5.2: Use candidates + the splitter in the pipeline**

In `run_wave_generation` step 6, change:

```python
        sku_locations = build_sku_locations_from_soh(items)
```
to:
```python
        sku_locations = build_sku_location_candidates(items)
```
and the success emit to report unique SKUs (the frame now has multiple rows per SKU):
```python
        emit("locations",
             f"live SOH resolved {sku_locations['product_code'].nunique()} "
             f"SKUs across {len(sku_locations)} locations "
             f"({len(items)} stock rows)", level="ok")
```

Add `split_lines` to the existing `from analysis import (...)` block at the top of the file (alphabetical position, after `run_full_pallet_analysis` — no local imports). Then replace step 7's `generate_wave_pick_sheets` call block with:

```python
        # 7. wave generation (each→carton split first: combo-SKU lines
        # spanning full cartons become CTN picks routed to reserve).
        emit("generate", "generating wave pick sheets…")
        wave_so_lines = split_lines(
            snap.so_lines, dims, min_full_cartons=settings.min_full_cartons)
        n_ctn_lines = int((wave_so_lines["pick_uom"] == "CTN").sum())
        if n_ctn_lines:
            emit("generate",
                 f"{n_ctn_lines} each-lines converted to carton picks "
                 f"(min_full_cartons={settings.min_full_cartons})", level="ok")
        result = generate_wave_pick_sheets(
            classification=classification, so_lines=wave_so_lines,
            sku_locations=sku_locations,
            run_group_col=settings.run_group_col,
            early_release_cartons=settings.early_release_cartons,
            include_immediate_streams=settings.include_pallet_sheets)
        emit("generate",
             f"{result.summary['n_waves']} waves, "
             f"{result.summary['n_orders_total']} orders, "
             f"{result.summary['n_lines_carton_pick']} carton-pick lines "
             f"({result.summary['n_carton_picks_no_reserve']} no-reserve), "
             f"{result.summary['n_lines_unallocated']} unallocated lines, "
             f"{result.summary['n_orders_skipped']} skipped", level="ok")
```

Classification (step 4–5) still consumes the **unsplit** `snap.so_lines` — stream routing is order-level and must not change.

- [ ] **Step 5.3: Run the wave_runner + full wave test set**

Run: `.venv/bin/python -m pytest tests/test_wave_runner.py tests/test_soh_location_candidates.py tests/test_soh_sku_locations.py tests/test_carton_pick_locations.py -v`
Expected: all pass. If a `test_wave_runner.py` test asserts on the old `"live SOH resolved N SKU locations"` emit text or on `_settings_dict` keys, update that assertion to the new message/keys — extend, don't delete.

- [ ] **Step 5.4: Commit**

```bash
git add src/wave_runner.py tests/
git commit -m "feat(waves): wire carton split + location candidates into the wave pipeline"
```

---

### Task 6: Picks console — form param + summary counts

**Files:**
- Modify: `src/web/app.py:43-57`
- Modify: `src/web/templates/index.html:17-19`
- Modify: `src/web/runs.py:32-42`
- Modify: `src/web/templates/run_detail.html:4-10`
- Test: `tests/test_web.py` (extend)

- [ ] **Step 6.1: Write the failing tests**

Append to `tests/test_web.py`:

```python
def test_index_form_has_min_full_cartons(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="min_full_cartons"' in r.text


def test_post_runs_passes_min_full_cartons(tmp_path):
    from fastapi.testclient import TestClient
    import web.app as appmod
    from wave_runner import RunResult

    seen = {}

    def fake_run(settings, progress):
        seen["min_full_cartons"] = settings.min_full_cartons
        return RunResult("r", tmp_path, {"n_waves": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake_run
    client = TestClient(app)
    client.post("/runs", data={
        "status": "X", "customer_name": "",
        "pallet_fraction_threshold": "0.51", "early_release_cartons": "30",
        "run_group_col": "delivery_state", "min_full_cartons": "2"})
    import time
    time.sleep(0.2)  # job thread
    assert seen["min_full_cartons"] == 2


def test_run_detail_shows_carton_pick_stat(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    run = _make_run(base, "20260611_090000")
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["summary"]["n_lines_carton_pick"] = 4
    manifest["summary"]["n_carton_picks_no_reserve"] = 1
    (run / "manifest.json").write_text(json.dumps(manifest))
    r = client.get("/runs/20260611_090000")
    assert r.status_code == 200
    assert "Carton picks" in r.text


def test_list_runs_surfaces_carton_counts(tmp_path):
    from web.runs import list_runs
    run = _make_run(tmp_path, "20260611_090000")
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["summary"]["n_lines_carton_pick"] = 4
    manifest["summary"]["n_carton_picks_no_reserve"] = 1
    (run / "manifest.json").write_text(json.dumps(manifest))
    runs = list_runs(tmp_path)
    assert runs[0]["n_lines_carton_pick"] == 4
    assert runs[0]["n_carton_picks_no_reserve"] == 1
```

- [ ] **Step 6.2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_web.py -v -k "min_full_cartons or carton"`
Expected: 4 FAIL

- [ ] **Step 6.3: Implement**

`src/web/app.py` — in `start_run`, after `early_release_cartons: int = Form(30),` add:

```python
        min_full_cartons: int = Form(1),
```

and in the `WaveRunSettings(...)` construction, after `early_release_cartons=early_release_cartons,` add:

```python
            min_full_cartons=min_full_cartons,
```

`src/web/templates/index.html` — after the "Early release cartons" label (line 19) add:

```html
      <label>Min full cartons (each→carton split)
        <input class="in" name="min_full_cartons" type="number" value="1" min="1">
      </label>
```

`src/web/runs.py` — in `list_runs`'s appended dict, after the `n_skus_unallocated` line add:

```python
            "n_lines_carton_pick": s.get("n_lines_carton_pick", 0),
            "n_carton_picks_no_reserve": s.get("n_carton_picks_no_reserve", 0),
```

`src/web/templates/run_detail.html` — after the "Unallocated lines" stat tile (line 9) add:

```html
  <div class="stat"><div class="n">{{ run.summary.n_lines_carton_pick or 0 }}</div><div class="l">Carton picks</div></div>
  <div class="stat"><div class="n">{{ run.summary.n_carton_picks_no_reserve or 0 }}</div><div class="l">No reserve</div></div>
```

(`or 0` keeps pre-feature manifests rendering.)

- [ ] **Step 6.4: Run the web suite**

Run: `.venv/bin/python -m pytest tests/test_web.py -v`
Expected: all pass

- [ ] **Step 6.5: Commit**

```bash
git add src/web/app.py src/web/templates/index.html src/web/templates/run_detail.html src/web/runs.py tests/test_web.py
git commit -m "feat(console): min_full_cartons control + carton-pick counts on picks console"
```

---

### Task 7: Full-suite regression + live shadow validation

**Files:** none created (validation only)

- [ ] **Step 7.1: Run the entire test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: ALL pass. Any failure here is a zero-breakage violation — fix before proceeding, never skip.

- [ ] **Step 7.2: Live regression diff (requires CC creds + open orders; run on the laptop/NUC during the day)**

```bash
.venv/bin/python scripts/generate_waves.py 2>&1 | tee /tmp/wave_ctn_run.log
```

Then verify, against the newest `data/processed/waves/<stamp>/`:
1. `manifest.json` → `summary.n_lines_carton_pick` is in the single digits (analysis says ~9 lines/day) and `settings.min_full_cartons` is recorded.
2. Open one wave's `*_picks.csv`: every row with `pick_uom == "EA"` has a location identical to what yesterday's run gave the same SKU (spot-check 5 SKUs).
3. Every `pick_uom == "CTN"` row points at a level-03+ (reserve) location unless `reserve_unavailable` is true.
4. Eyeball TSP-SAR / FD-BAR lines on the PDF — qty shows as `N CTN (M EA)`.
5. Show a printed sheet to the pick team before relying on it: do the CTN locations match where they actually pull cartons from?

- [ ] **Step 7.3: Final commit + branch wrap-up**

Use the superpowers:finishing-a-development-branch skill (merge/PR decision per house workflow).

---

## Self-review notes

- **Spec coverage:** splitter → Task 1; per-line reserve routing + flags → Task 3; (SKU, pick_uom) consolidation → Task 3(h); picksheet display + summary counts → Tasks 4, 3(j); console param + counts → Task 6; edge table (UNALLOCATED unchanged, qty_short, reserve_unavailable, ipq missing) → Tasks 1, 3; regression validation → Task 7. CC write-back is out of scope per spec.
- **Type consistency:** `pick_uom` is `"CTN"`/`"EA"` (constants from `carton_split`); `qty_eaches` is nullable Int (pd.NA on EA lines); flags are bools; `role` is `'pick_face'|'reserve'|'unknown'` with selection treating non-pick_face as reserve.
- **Known judgement call:** classification keeps consuming unsplit lines (order streams unchanged) — deliberate, documented in Task 5.2.
