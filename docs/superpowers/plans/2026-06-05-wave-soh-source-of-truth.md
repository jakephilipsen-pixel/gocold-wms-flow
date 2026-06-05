# Wave gen: live SOH as source of truth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every wave-pick generation resolve SKU→location from a fresh CartonCloud stock-on-hand pull, never a stale spreadsheet; SKUs SOH can't place ride the wave flagged `unallocated`.

**Architecture:** `get_sku_locations` (already async-polls a live SOH report-run) becomes the sole, mandatory placement source each gen. Its rows are parsed through `locations/grammar.py` into walk-order columns and collapsed to one pick-face location per SKU. `generate_wave_pick_sheets` stops skipping orders with unlocatable SKUs — it emits an `unallocated` pick line instead. The location master xlsx and the assignments CSV are removed from the placement path.

**Tech Stack:** Python 3.11, pandas, pytest, FastAPI/Jinja (console), reportlab (PDF).

Spec: `docs/superpowers/specs/2026-06-05-wave-soh-source-of-truth-design.md`

---

## File map

- **Modify** `src/wave_runner.py` — add `build_sku_locations_from_soh`; rewrite steps 6–8 of `run_wave_generation`; drop `soh_fallback`/`locations_path`/`assignments_path` from the placement path; update `_settings_dict`, manifest, summary.
- **Modify** `src/analysis/wave_picks.py` — new signature (`sku_locations` sole source); unallocated-not-skip; walk-sort pushes unallocated last; summary counts; `unallocated` column.
- **Modify** `src/output/pdf_picksheet.py` — render unallocated lines in a flagged block.
- **Modify** `scripts/generate_waves.py` — remove `--soh-fallback`/`--locations`/`--assignments` flags.
- **Modify** `src/web/app.py`, `src/web/templates/index.html` — remove `soh_fallback` form field/plumbing; surface unallocated count.
- **Tests:** `tests/test_soh_sku_locations.py` (new), `tests/test_wave_consolidation.py`, `tests/test_wave_runner.py`.

Run tests with the venv-safe invocation (per project memory): `python -m pytest …` (never the `bin/pytest` wrapper).

---

### Task 1: SOH rows → one pick-face location per SKU

**Files:**
- Modify: `src/wave_runner.py` (add a module-level helper near the top, after imports)
- Test: `tests/test_soh_sku_locations.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_soh_sku_locations.py`:

```python
"""Unit tests for build_sku_locations_from_soh (SOH -> pick lookup)."""
from __future__ import annotations

import pandas as pd

from wave_runner import build_sku_locations_from_soh


def _row(code, loc, qty=10):
    # Shape returned by cc_client.get_sku_locations.
    return {"product_code": code, "location_name": loc,
            "location_id": f"id-{loc}", "qty": qty, "uom": "EA"}


def test_parses_grammar_into_walk_columns():
    df = build_sku_locations_from_soh([_row("WIDGET", "AA-05-01")])
    row = df.set_index("product_code").loc["WIDGET"]
    assert row["location"] == "AA-05-01"
    assert row["aisle"] == "AA"
    assert int(row["bay"]) == 5
    assert int(row["level"]) == 1


def test_prefers_pick_face_over_reserve():
    # AA-05-03 is reserve (level 3); AA-05-01 is a pick face (level 1).
    df = build_sku_locations_from_soh([
        _row("WIDGET", "AA-05-03"),
        _row("WIDGET", "AA-05-01"),
    ])
    assert df.set_index("product_code").loc["WIDGET", "location"] == "AA-05-01"


def test_lowest_position_wins_among_pick_faces():
    # position 1 (level 01) beats position 2 (level 02).
    df = build_sku_locations_from_soh([
        _row("WIDGET", "AA-05-02"),
        _row("WIDGET", "AA-05-01"),
    ])
    assert df.set_index("product_code").loc["WIDGET", "location"] == "AA-05-01"


def test_reserve_only_sku_still_resolves():
    # No pick face anywhere -> take the reserve (real, live location).
    df = build_sku_locations_from_soh([_row("WIDGET", "AA-05-04")])
    assert df.set_index("product_code").loc["WIDGET", "location"] == "AA-05-04"


def test_one_row_per_sku():
    df = build_sku_locations_from_soh([
        _row("WIDGET", "AA-05-01"),
        _row("WIDGET", "AA-06-01"),
        _row("GADGET", "BB-01-01"),
    ])
    assert sorted(df["product_code"]) == ["GADGET", "WIDGET"]


def test_empty_input_returns_empty_frame_with_columns():
    df = build_sku_locations_from_soh([])
    assert list(df.columns) == [
        "product_code", "location", "aisle", "bay", "level", "sublevel"]
    assert df.empty


def test_unparseable_location_kept_with_na_walk_fields():
    df = build_sku_locations_from_soh([_row("WIDGET", "BULK-FLOOR")])
    row = df.set_index("product_code").loc["WIDGET"]
    assert row["location"] == "BULK-FLOOR"
    assert pd.isna(row["aisle"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_soh_sku_locations.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_sku_locations_from_soh'`.

- [ ] **Step 3: Implement the helper**

In `src/wave_runner.py`, change the grammar/locations import and add the function. Replace the line:

```python
from locations import load_cc_locations
```

with:

```python
from locations.grammar import parse_location_name
```

Then add this module-level function directly below the `ProgressCallback = ...` line (after the dataclasses, before the lazy-loader section):

```python
_SKU_LOC_COLS = ["product_code", "location", "aisle", "bay", "level", "sublevel"]


def build_sku_locations_from_soh(items: list[dict]) -> pd.DataFrame:
    """Collapse live SOH rows into one pick-face location per SKU.

    ``items`` are the dicts returned by ``cc_client.get_sku_locations``
    (``product_code``, ``location_name``, ``location_id``, ``qty``, ``uom``).
    Each location name is parsed through the warehouse grammar to recover
    walk-order structure (aisle/bay/level/sublevel) and pick-face role.

    Selection per SKU (best first):
      1. pick faces before reserve/unknown,
      2. lowest grammar position (1 before 2),
      3. walk order (aisle, bay, level, sublevel).

    A SKU with only reserve locations still resolves to its best reserve —
    that is a real, live location, not ``unallocated``. Returns columns
    ``product_code, location, aisle, bay, level, sublevel`` (one row per SKU).
    """
    if not items:
        return pd.DataFrame(columns=_SKU_LOC_COLS)

    candidates: list[dict] = []
    for it in items:
        code = it.get("product_code")
        name = it.get("location_name")
        if not code or not name:
            continue
        info = parse_location_name(name)
        role_rank = 0 if info.role_by_grammar == "pick_face" else 1
        candidates.append({
            "product_code": code,
            "location": name,
            "aisle": info.aisle,
            "bay": info.bay,
            "level": info.level,
            "sublevel": info.sublevel,
            "_role_rank": role_rank,
            "_position": info.position if info.position is not None else 99,
            "_aisle_sort": info.aisle or "zz",
            "_bay_sort": info.bay if info.bay is not None else 9999,
            "_level_sort": info.level if info.level is not None else 9999,
            "_sub_sort": info.sublevel if info.sublevel is not None else 9999,
        })

    if not candidates:
        return pd.DataFrame(columns=_SKU_LOC_COLS)

    df = pd.DataFrame(candidates)
    df = df.sort_values(
        ["product_code", "_role_rank", "_position",
         "_aisle_sort", "_bay_sort", "_level_sort", "_sub_sort"],
        kind="mergesort",
    )
    best = df.drop_duplicates("product_code", keep="first").reset_index(drop=True)
    return best[_SKU_LOC_COLS]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_soh_sku_locations.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wave_runner.py tests/test_soh_sku_locations.py
git commit -m "feat(wave): build_sku_locations_from_soh — pick-face per SKU from live SOH"
```

---

### Task 2: generate_wave_pick_sheets — unallocated instead of skip

**Files:**
- Modify: `src/analysis/wave_picks.py` (signature ~237; lookup 109–162, 323–331; line loop 386–423; walk-sort 165–204; consolidation 456–492; summary 525–531)
- Test: `tests/test_wave_consolidation.py`

- [ ] **Step 1: Rewrite the consolidation tests for the new contract**

Replace the whole body of `tests/test_wave_consolidation.py` from the `_assignments` helper down to (and including) `test_order_with_unlocatable_sku_is_skipped_whole`, leaving the other tests intact. Apply these edits:

Rename `_assignments` → `_sku_locations` and re-point `_run`:

```python
def _sku_locations():
    return pd.DataFrame([
        {"product_code": "WIDGET", "location": "A-01-1",
         "aisle": "A", "bay": "01", "level": "1", "sublevel": "0"},
        {"product_code": "GADGET", "location": "A-02-1",
         "aisle": "A", "bay": "02", "level": "1", "sublevel": "0"},
        {"product_code": "ZEBRA", "location": "C-09-1",
         "aisle": "C", "bay": "09", "level": "1", "sublevel": "0"},
    ])


def _run(per_order, so_lines, **kw):
    return generate_wave_pick_sheets(
        classification=_classification(per_order),
        so_lines=so_lines,
        sku_locations=_sku_locations(),
        early_release_cartons=10_000,      # keep all orders in one wave
        **kw,
    )
```

Replace `test_order_with_unlocatable_sku_is_skipped_whole` with the new behaviour:

```python
def test_order_with_unlocatable_sku_is_flagged_not_skipped():
    """A SKU with no live location does NOT skip the order — its line rides
    the wave flagged 'unallocated'. The order's other lines pick normally."""
    per_order = pd.DataFrame([
        _order_row(1, "SO-A", cartons=2, lines=2),
        _order_row(2, "SO-B", cartons=1, lines=1),
    ])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 1},
        {"so_id": 1, "product_code": "UNKNOWN", "product_name": "Mystery", "quantity": 1},
        {"so_id": 2, "product_code": "WIDGET", "product_name": "Widget", "quantity": 1},
    ])

    result = _run(per_order, so_lines)

    # No order is skipped for a missing location.
    assert result.skipped_orders.empty
    assert result.summary["n_skus_unallocated"] == 1
    assert result.summary["n_lines_unallocated"] == 1

    sheet = result.sheets[0]
    picks = sheet.pick_lines.set_index("product_code")
    # WIDGET is located and summed across SO-A + SO-B.
    assert picks.loc["WIDGET", "qty_cartons"] == 2
    assert bool(picks.loc["WIDGET", "unallocated"]) is False
    # UNKNOWN rides the wave, flagged, with no real location.
    assert picks.loc["UNKNOWN", "location"] == "UNALLOCATED"
    assert bool(picks.loc["UNKNOWN", "unallocated"]) is True


def test_unallocated_lines_sort_to_the_end_of_the_walk():
    per_order = pd.DataFrame([_order_row(1, "SO-A", cartons=3, lines=2)])
    so_lines = pd.DataFrame([
        {"so_id": 1, "product_code": "UNKNOWN", "product_name": "Mystery", "quantity": 1},
        {"so_id": 1, "product_code": "WIDGET", "product_name": "Widget", "quantity": 2},
    ])
    sheet = _run(per_order, so_lines).sheets[0]
    # WIDGET (located) is walked first; UNKNOWN (unallocated) is last.
    assert list(sheet.pick_lines["product_code"]) == ["WIDGET", "UNKNOWN"]
    assert list(sheet.pick_lines["unallocated"]) == [False, True]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_consolidation.py -v`
Expected: FAIL — `TypeError: generate_wave_pick_sheets() got an unexpected keyword argument 'sku_locations'` (and missing `unallocated` column).

- [ ] **Step 3: Change the signature and lookup**

In `src/analysis/wave_picks.py`, change the function signature (lines ~237–246) to:

```python
def generate_wave_pick_sheets(
    classification: StreamClassification,
    so_lines: pd.DataFrame,
    sku_locations: pd.DataFrame | None = None,
    aisle_walk_order: list[str] | None = None,
    run_group_col: str = "delivery_state",
    early_release_cartons: int | None = None,
) -> WaveGenerationResult:
```

Replace `_build_sku_location_lookup` (lines 109–162) with a single-source version:

```python
def _build_sku_location_lookup(
    sku_locations: pd.DataFrame | None,
) -> pd.DataFrame:
    """Normalise the live SKU -> location frame to the columns the
    generator needs: product_code, location, aisle, bay, level, sublevel."""
    cols = ["product_code", "location", "aisle", "bay", "level", "sublevel"]
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
    return s.drop_duplicates("product_code", keep="first").reset_index(
        drop=True)[cols]
```

Update the call site (lines 323–331) to:

```python
    # Build the SKU -> location lookup once (live SOH only).
    sku_lookup = _build_sku_location_lookup(sku_locations)
    sku_lookup_idx = (
        sku_lookup.set_index("product_code") if not sku_lookup.empty else None
    )
    if sku_lookup.empty:
        log.warning(
            "no live SKU locations provided; every line will be unallocated"
        )
```

- [ ] **Step 4: Replace the per-line skip with unallocated flagging**

Replace the line loop body (lines 386–423, from `missing: list[str] = []` through the `n_orders_skipped += 1 / continue` block that handles `if missing:`) with:

```python
            order_rows: list[dict] = []
            for line in lines.itertuples(index=False):
                code = getattr(line, "product_code", None)
                qty = float(getattr(line, "quantity", 0) or 0)
                if not code or qty <= 0:
                    continue
                loc_row = None
                if sku_lookup_idx is not None and code in sku_lookup_idx.index:
                    loc_row = sku_lookup_idx.loc[code]
                if loc_row is None:
                    # No live location — line still rides the wave, flagged.
                    order_rows.append({
                        "so_id": sid,
                        "product_code": code,
                        "product_name": getattr(line, "product_name", ""),
                        "quantity": qty,
                        "location": "UNALLOCATED",
                        "aisle": pd.NA, "bay": pd.NA,
                        "level": pd.NA, "sublevel": pd.NA,
                        "unallocated": True,
                    })
                    continue
                order_rows.append({
                    "so_id": sid,
                    "product_code": code,
                    "product_name": getattr(line, "product_name", ""),
                    "quantity": qty,
                    "location": loc_row.get("location"),
                    "aisle": loc_row.get("aisle"),
                    "bay": loc_row.get("bay"),
                    "level": loc_row.get("level"),
                    "sublevel": loc_row.get("sublevel"),
                    "unallocated": False,
                })
```

(The empty-order skip above it — `if lines is None or lines.empty:` → `skipped_rows.append(... "reason": "no SO lines in extract" ...)` — stays exactly as is.)

- [ ] **Step 5: Carry `unallocated` through consolidation and sort it last**

In the consolidation `.agg(...)` (lines 458–470) add `unallocated` to the grouped output by adding this aggregation key:

```python
            unallocated=("unallocated", "first"),
```

In `_walk_sort_key` (lines 165–204), make unallocated rows rank last. After `df = df.copy()` add:

```python
    if "unallocated" in df.columns:
        df["_unalloc_rank"] = df["unallocated"].fillna(False).astype(int)
    else:
        df["_unalloc_rank"] = 0
```

Change the `df.sort_values([...])` call to lead with `_unalloc_rank`:

```python
    df = df.sort_values(
        ["_unalloc_rank", "_aisle_rank", "_aisle_tie",
         "_bay_num", "_level_num", "_sublevel_num"],
        kind="mergesort",
    ).reset_index(drop=True)
    return df.drop(columns=[
        "_unalloc_rank", "_aisle_rank", "_aisle_tie",
        "_bay_num", "_level_num", "_sublevel_num"
    ])
```

Add `unallocated` to `ordered_cols` (lines 479–491), at the end:

```python
        ordered_cols = [
            "walk_index", "location", "aisle", "bay", "level", "sublevel",
            "product_code", "product_name", "qty_cartons",
            "cartons_running_total", "contributing_so_refs", "unallocated",
        ]
```

- [ ] **Step 6: Report unallocated counts in the summary**

The summary is assembled per-wave then once at the end (lines 525–531). Track counts while iterating: just before `skipped_df = (` (line 515) compute totals from the built sheets:

```python
    n_lines_unallocated = sum(
        int(s.pick_lines["unallocated"].fillna(False).sum())
        for s in sheets if "unallocated" in s.pick_lines.columns
    )
    n_skus_unallocated = len({
        code
        for s in sheets if "unallocated" in s.pick_lines.columns
        for code in s.pick_lines.loc[
            s.pick_lines["unallocated"].fillna(False), "product_code"]
    })
```

Add both to the `result.summary` dict (lines 525–531):

```python
    result.summary = {
        "n_waves": len(sheets),
        "n_orders_total": n_orders_total,
        "n_orders_skipped": n_orders_skipped,
        "n_pick_lines_total": total_pick_lines,
        "n_lines_unallocated": n_lines_unallocated,
        "n_skus_unallocated": n_skus_unallocated,
        "streams": sorted({s.stream for s in sheets}),
    }
```

Also update the docstring of `generate_wave_pick_sheets` (lines 247–284): drop the `locations`/`assignments` parameter descriptions, describe `sku_locations` as the sole live source, and change step 6 of the "Pipeline" list from "Skip any order whose SKUs can't be located" to "Lines whose SKU has no live location ride the wave flagged ``unallocated`` (sorted last); only genuinely empty orders are skipped."

- [ ] **Step 7: Run the consolidation tests**

Run: `python -m pytest tests/test_wave_consolidation.py -v`
Expected: PASS (all, including the two new ones). The pre-existing `test_walk_index_is_sequential_and_sorted`, `test_same_sku_across_orders_is_summed`, etc. still pass because located rows are unchanged.

- [ ] **Step 8: Commit**

```bash
git add src/analysis/wave_picks.py tests/test_wave_consolidation.py
git commit -m "feat(wave): unallocated pick lines instead of whole-order skip; SOH-only lookup"
```

---

### Task 3: Wire live SOH as mandatory primary in the runner

**Files:**
- Modify: `src/wave_runner.py` (Settings 52–75; `_settings_dict` 264–277; steps 6–9 at 362–408; manifest 437–439)
- Test: `tests/test_wave_runner.py`

- [ ] **Step 1: Update the runner tests for the new contract**

In `tests/test_wave_runner.py`:

Remove the stale assertion in `test_settings_defaults_pull_from_analysis_constants` — delete this line:

```python
    assert s.soh_fallback is False
```

Extend the `fake_cc` fixture so the mandatory SOH pull is stubbed (no network). Replace the fixture body with:

```python
@pytest.fixture
def fake_cc(monkeypatch):
    """Patch the live CC pull + client construction to avoid network."""
    monkeypatch.setattr(
        "wave_runner.CartonCloudClient.from_env",
        classmethod(lambda cls, **kw: object()),
    )
    # SOH is now mandatory every gen — stub it to a single live location so
    # the pipeline runs end-to-end and produces a real wave.
    monkeypatch.setattr(
        "wave_runner.get_sku_locations",
        lambda client, **kw: [
            {"product_code": "SOME-SKU", "location_name": "AA-01-01",
             "location_id": "id-1", "qty": 5, "uom": "EA"},
        ],
    )
    return monkeypatch
```

Add a test that total SOH failure aborts the run:

```python
def test_soh_failure_fails_the_run(tmp_path, fake_cc):
    from cc_client import CartonCloudError
    orders = [_fake_order("SO-1", "SOME-SKU")]
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter(orders),
    )

    def boom(client, **kw):
        raise CartonCloudError("SOH report-run timed out")

    fake_cc.setattr("wave_runner.get_sku_locations", boom)
    events: list[ProgressEvent] = []
    settings = WaveRunSettings(repo_root=_ROOT, out_dir=tmp_path / "waves")
    result = run_wave_generation(settings, events.append)
    assert result.status == "failed"
    assert any(e.level == "error" for e in events)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wave_runner.py -v`
Expected: FAIL — `test_settings_defaults...` fails on the removed attr only if left; `test_soh_failure_fails_the_run` fails because the runner currently has no mandatory SOH path / doesn't fail. (Some may error on `get_sku_locations` patch target not yet primary.)

- [ ] **Step 3: Remove soh_fallback / placement paths from Settings**

In `src/wave_runner.py`, edit `WaveRunSettings` (lines 52–75): delete the `soh_fallback: bool = False` line, and delete `locations_path` and `assignments_path` fields (they no longer feed placement). Keep `raw_dir`, `dims_path`, `rules_path`, `logo_path`, `out_dir`.

Update `_settings_dict` (lines 264–277) — drop the `assignments_path` argument and the `soh_fallback`/`assignments_path` keys:

```python
def _settings_dict(settings, audit_path):
    """Flatten the settings used for a run into a JSON-serialisable dict."""
    return {
        "status": settings.status,
        "customer_name": settings.customer_name,
        "pallet_fraction_threshold": settings.pallet_fraction_threshold,
        "early_release_cartons": settings.early_release_cartons,
        "run_group_col": settings.run_group_col,
        "lines_per_hour": settings.lines_per_hour,
        "placement_source": "live_soh",
        "audit_parquet": str(audit_path),
    }
```

- [ ] **Step 4: Rewrite steps 6–9 of run_wave_generation**

Replace the whole block from step 6 through step 9 (lines 362–408 — the `# 6. locations` / `# 7. assignments` / `# 8. SOH fallback` / `# 9. wave generation` sections) with:

```python
        # 6. live SKU -> location from stock-on-hand (mandatory, fresh).
        emit("locations", "pulling live stock-on-hand for SKU locations…")
        codes = sorted({c for c in so_lines["product_code"].dropna().unique()})
        soh_customer_id = (so_lines.iloc[0]["customer_id"]
                           if "customer_id" in so_lines.columns
                           and len(so_lines) else None)
        if not soh_customer_id:
            raise CartonCloudError(
                "cannot resolve customer_id for SOH pull — no live stock "
                "locations available; refusing to wave from stale data")
        items = get_sku_locations(
            client, customer_id=soh_customer_id, product_codes=codes)
        sku_locations = build_sku_locations_from_soh(items)
        if sku_locations.empty:
            raise CartonCloudError(
                "live SOH returned no SKU locations — refusing to generate a "
                "wave with nothing placed")
        emit("locations",
             f"live SOH resolved {len(sku_locations)} SKU locations "
             f"({len(items)} stock rows)", level="ok")

        # 7. wave generation
        emit("generate", "generating wave pick sheets…")
        result = generate_wave_pick_sheets(
            classification=classification, so_lines=snap.so_lines,
            sku_locations=sku_locations,
            run_group_col=settings.run_group_col,
            early_release_cartons=settings.early_release_cartons)
        emit("generate",
             f"{result.summary['n_waves']} waves, "
             f"{result.summary['n_orders_total']} orders, "
             f"{result.summary['n_lines_unallocated']} unallocated lines, "
             f"{result.summary['n_orders_skipped']} skipped", level="ok")
```

No extra error handling is needed: the SOH block sits inside the outer `try:` of `run_wave_generation` (opens at line ~299), whose `except Exception` (line ~456) already does `emit("done", f"Run failed: …", level="error")` and `return RunResult(stamp, out_dir, {}, "failed", error=str(exc))` (confirmed). So raising `CartonCloudError` here yields `status="failed"` **and** an error-level event — exactly what `test_soh_failure_fails_the_run` asserts.

- [ ] **Step 5: Update the manifest + index calls**

Every `_settings_dict(settings, audit_path, assignments_path)` call now drops the third arg → `_settings_dict(settings, audit_path)`. Fix all occurrences (the empty-orders early return ~322, `_build_index_md` ~435–436, and the manifest dict ~437–439). Remove the now-unused `assignments_path` local and the `# remove assignments_path` references. Add the unallocated counts to the manifest summary if it is composed separately (the `summary` already comes from `result.summary`, so no change needed beyond passing it through).

- [ ] **Step 6: Run the runner tests**

Run: `python -m pytest tests/test_wave_runner.py -v`
Expected: PASS — including `test_run_emits_progress_and_writes_run` (now waves SOME-SKU into a real wave) and `test_soh_failure_fails_the_run`.

- [ ] **Step 7: Commit**

```bash
git add src/wave_runner.py tests/test_wave_runner.py
git commit -m "feat(wave): live SOH is the mandatory, sole placement source each gen"
```

---

### Task 4: CLI flag cleanup

**Files:**
- Modify: `scripts/generate_waves.py` (flags ~64–95)

- [ ] **Step 1: Remove the dead flags**

In `scripts/generate_waves.py`, delete these argument definitions and their `kw[...] = ...` assignments:
- `--locations` (line ~64) and `kw["locations_path"] = args.locations` (~93)
- `--assignments` (line ~67) and `kw["assignments_path"] = args.assignments` (~95)
- `--soh-fallback` (line ~68) and `kw["soh_fallback"] = args.soh_fallback` (~89)

Update the module docstring step "5. Load CC locations + latest SKU assignments." (line ~13) to "5. Pull live SOH for SKU locations (mandatory)."

- [ ] **Step 2: Verify the CLI still builds settings**

Run: `python -m pytest tests/test_wave_runner.py::test_cli_main_builds_settings_and_runs -v`
Expected: PASS (the test only exercises `--early-release-cartons` / `--pallet-fraction-threshold`, which remain).

- [ ] **Step 3: Smoke the parser**

Run: `python scripts/generate_waves.py --help`
Expected: help prints with no `--soh-fallback`/`--locations`/`--assignments`; exits 0.

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_waves.py
git commit -m "chore(wave): drop --soh-fallback/--locations/--assignments CLI flags"
```

---

### Task 5: Console — remove the toggle, surface unallocated

**Files:**
- Modify: `src/web/app.py` (form handler 43–67), `src/web/templates/index.html` (line 27)

- [ ] **Step 1: Update the web smoke test expectation**

In `tests/test_web.py`, find any reference to `soh_fallback` (grep first: `python -m pytest tests/test_web.py -v` to see current state, and `grep -n soh_fallback tests/test_web.py`). If a test posts `soh_fallback`, remove that form field from the POST data. If none references it, no test change is needed — proceed.

- [ ] **Step 2: Remove the form field from the template**

In `src/web/templates/index.html`, delete the `soh_fallback` checkbox (line 27) and its surrounding label/wrapper element (read the few lines around it and remove the whole control, not just the `<input>`).

- [ ] **Step 3: Remove the param from the handler**

In `src/web/app.py`, delete `soh_fallback: bool = Form(False),` from `start_run` (line 51) and the `soh_fallback=soh_fallback` argument in the `WaveRunSettings(...)` construction (line 59).

- [ ] **Step 4: Run the web tests**

Run: `python -m pytest tests/test_web.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py src/web/templates/index.html tests/test_web.py
git commit -m "feat(console): drop SOH-fallback toggle — live SOH always on"
```

---

### Task 6: PDF — flagged unallocated block

**Files:**
- Modify: `src/output/pdf_picksheet.py` (`_pick_lines_table` 394–470; `generate_wave_pdf` pick-lines section 574–585)
- Test: `tests/test_pdf_picksheet.py` (create if absent; otherwise extend)

- [ ] **Step 1: Write a failing test that a PDF with unallocated lines renders**

Check for an existing PDF test: `grep -rl "generate_wave_pdf" tests/`. If none, create `tests/test_pdf_picksheet.py`:

```python
"""The picksheet renders located + unallocated lines without erroring."""
from __future__ import annotations

import pandas as pd

from analysis.wave_picks import WavePickSheet
from analysis.routing import STREAM_BENCH
from output.pdf_picksheet import generate_wave_pdf


def _sheet():
    pick_lines = pd.DataFrame([
        {"walk_index": 1, "location": "AA-01-01", "aisle": "AA", "bay": 1,
         "level": 1, "sublevel": pd.NA, "product_code": "WIDGET",
         "product_name": "Widget", "qty_cartons": 3,
         "cartons_running_total": 3, "contributing_so_refs": "SO-A",
         "unallocated": False},
        {"walk_index": 2, "location": "UNALLOCATED", "aisle": pd.NA,
         "bay": pd.NA, "level": pd.NA, "sublevel": pd.NA,
         "product_code": "MYSTERY", "product_name": "Mystery",
         "qty_cartons": 1, "cartons_running_total": 4,
         "contributing_so_refs": "SO-A", "unallocated": True},
    ])
    orders = pd.DataFrame([{
        "so_id": 1, "so_ref": "SO-A", "customer_name": "Forage",
        "delivery_company": "Shop", "delivery_suburb": "Scoresby",
        "delivery_state": "VIC", "delivery_postcode": "3179",
        "cartons": 4, "lines": 2,
    }])
    return WavePickSheet(
        wave_id="W1", stream=STREAM_BENCH, run_group="VIC",
        receive_date="2026-06-05", orders=orders, pick_lines=pick_lines,
        total_cartons=4, total_lines=2, estimated_walk_distance_m=10.0)


def test_pdf_renders_with_unallocated_lines(tmp_path):
    out = tmp_path / "w1.pdf"
    generate_wave_pdf(_sheet(), out)
    assert out.exists() and out.stat().st_size > 1000
```

(Confirm the `WavePickSheet` constructor field names by reading the dataclass in `src/analysis/wave_picks.py`; adjust the kwargs to match exactly.)

- [ ] **Step 2: Run it to verify current behaviour**

Run: `python -m pytest tests/test_pdf_picksheet.py -v`
Expected: It may PASS already (the current table renders any row) — but the unallocated line is not visually flagged. Proceed to make the flag explicit and add the assertion below. If it FAILS (e.g. `unallocated` attr access), that's the failing state to fix.

- [ ] **Step 3: Split located vs unallocated in the table builder**

In `src/output/pdf_picksheet.py`, make `_pick_lines_table` accept a DataFrame instead of the whole sheet. Change its signature and the loop source:

```python
def _pick_lines_table(pick_lines: pd.DataFrame) -> Table:
```

and replace `for r in sheet.pick_lines.itertuples(index=False):` with `for r in pick_lines.itertuples(index=False):`. Add `import pandas as pd` at the top if not already imported.

In `generate_wave_pdf` pick-lines section (lines 574–585), split the frame and render two tables:

```python
    # ---- pick lines section ----
    story.append(Paragraph(
        "Pick lines &mdash; walk order", styles["section_h"]))
    story.append(Spacer(1, 4 * mm))
    pl = sheet.pick_lines
    if pl.empty:
        story.append(Paragraph(
            "<i>No pick lines for this wave.</i>", styles["body"]))
    else:
        if "unallocated" in pl.columns:
            located = pl[~pl["unallocated"].fillna(False)]
            unalloc = pl[pl["unallocated"].fillna(False)]
        else:
            located, unalloc = pl, pl.iloc[0:0]
        if not located.empty:
            story.append(_pick_lines_table(located))
        if not unalloc.empty:
            story.append(Spacer(1, 6 * mm))
            story.append(Paragraph(
                "&#9888; UNALLOCATED &mdash; no live stock location, "
                "locate manually", styles["callout"]))
            story.append(Spacer(1, 3 * mm))
            story.append(_pick_lines_table(unalloc))
```

(The `callout` style already exists in `_build_styles`. Verify the `_pick_lines_table` is not called elsewhere with a `sheet` arg — grep `_pick_lines_table(`; there is one call site.)

- [ ] **Step 4: Assert the flag block renders**

Extend the test to confirm the unallocated block adds content. `WavePickSheet` is a plain (mutable) `@dataclass` (confirmed — fields: `wave_id, stream, run_group, receive_date, orders, pick_lines, total_cartons, total_lines, estimated_walk_distance_m`), so reassign `pick_lines` directly. Render located-only vs located+unallocated and assert the second PDF is larger:

```python
def test_unallocated_block_adds_content(tmp_path):
    s = _sheet()
    full = tmp_path / "full.pdf"
    generate_wave_pdf(s, full)

    s2 = _sheet()
    s2.pick_lines = s2.pick_lines[~s2.pick_lines["unallocated"]].copy()
    smaller = tmp_path / "located.pdf"
    generate_wave_pdf(s2, smaller)

    assert full.stat().st_size > smaller.stat().st_size
```

- [ ] **Step 5: Run the PDF tests**

Run: `python -m pytest tests/test_pdf_picksheet.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/output/pdf_picksheet.py tests/test_pdf_picksheet.py
git commit -m "feat(picksheet): flagged UNALLOCATED block at foot of the sheet"
```

---

### Task 7: Full suite + shadow note

**Files:** none (verification)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass. Investigate any failure referencing `assignments`, `soh_fallback`, `locations_path`, or `_settings_dict` arity — those are call sites missed in Tasks 2–5.

- [ ] **Step 2: Grep for dangling references**

Run: `grep -rn "soh_fallback\|assignments_path\|locations_path\|load_cc_locations" src/ scripts/`
Expected: no hits in the wave path. (`load_cc_locations` may still be referenced by non-wave code — confirm any remaining hit is unrelated to wave gen before leaving it.)

- [ ] **Step 3: Commit any cleanup**

```bash
git add -A && git commit -m "chore(wave): remove dangling stale-placement references" || echo "nothing to clean"
```

- [ ] **Step 4: Shadow-validate before floor rollout (manual, not a code step)**

Before this replaces the current path on the floor, run one real morning's open orders through `scripts/generate_waves.py` and confirm: (a) the `n_lines_unallocated` count is small and the flagged SKUs are genuinely ones SOH can't place (the known numeric-SKU gap), and (b) the SOH-derived walk order matches the current xlsx-derived route on a sample wave. Record the result before flipping the console over.

---

## Self-review notes

- **Spec coverage:** live-SOH-mandatory (Task 3) · no stale fallback / unallocated-not-skip (Task 2) · walk-order from SOH names (Task 1) · hard-fail on SOH failure (Task 3 Step 4 + test) · pick-face selection (Task 1) · drop xlsx+CSV (Tasks 3–4) · console toggle removed (Task 5) · PDF flag block (Task 6) · shadow note (Task 7 Step 4). All present.
- **Type consistency:** the `sku_locations` frame columns (`product_code, location, aisle, bay, level, sublevel`) are produced by `build_sku_locations_from_soh` (Task 1) and consumed by `_build_sku_location_lookup` (Task 2) — identical. The `unallocated` bool column is created in the line loop (Task 2 Step 4), aggregated (`unallocated=("unallocated","first")`), added to `ordered_cols`, read by the summary (Task 2 Step 6) and the PDF split (Task 6) under the same name throughout.
- **Open verification points flagged inline:** the `run_wave_generation` try/except wrapper (Task 3 Step 4) and the `WavePickSheet` mutability (Task 6 Step 4) must be confirmed against the actual code during execution; both have explicit fallback instructions.
