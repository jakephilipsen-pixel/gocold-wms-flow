# Run-grouped, stream-split wave picking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wave generator group picks by predicted delivery run and produce pick-to-pallet paperwork, routing dispatch-flagged and high-cube orders to the pallet stream — the ASAP paperwork loop.

**Architecture:** Build on the existing `src/analysis/routing.py` (3-stream model + cube classification already present). Add a small `dispatch_link` bridge that joins `build_dispatch`'s `suggested_runs.csv`/`review.csv` onto the per-order frame; add one classification rule (R2b: dispatch-flagged → pallet); teach `plan_waves` to also emit immediate waves for the pallet (`1_pallet_pick`) and unclassified (`0_unclassified`) streams so the existing sheet machinery prints them; wire it through `wave_runner`, the CLI, and the console; add a cube-threshold calibration script.

**Tech Stack:** Python 3.11+ (run via `.venv/bin/python`), pandas, pytest. Read-only against CartonCloud throughout.

**Source of truth:** `docs/superpowers/specs/2026-06-07-run-grouped-two-stream-wave-picking-design.md`

**Conventions:**
- Run everything with `.venv/bin/python -m pytest ...` (the venv's bin shims point at a stale path — see project memory).
- Australian English, no emojis, no placeholders (house style).
- `src/` is on `sys.path` via `tests/conftest.py`, so imports are `from analysis... import ...`.

---

### Task 1: `dispatch_link` — bridge dispatch runs onto the per-order frame

**Files:**
- Create: `src/analysis/dispatch_link.py`
- Create: `tests/test_dispatch_link.py`
- Modify: `src/analysis/__init__.py` (export the new symbols)

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_link.py`:

```python
"""Tests for the dispatch->wave run bridge (src/analysis/dispatch_link.py)."""
from __future__ import annotations

import pandas as pd

from analysis.dispatch_link import (
    FLAGGED_DISPATCH,
    attach_dispatch_runs,
    find_latest_dispatch_plan,
    load_dispatch_link,
)


def _write_plan(plan_dir, suggested_rows, review_rows):
    plan_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        suggested_rows,
        columns=["so_ref", "so_id", "predicted_run", "confidence", "flag"],
    ).to_csv(plan_dir / "suggested_runs.csv", index=False)
    pd.DataFrame(
        review_rows,
        columns=["so_ref", "so_id", "predicted_run", "confidence", "flag"],
    ).to_csv(plan_dir / "review.csv", index=False)


def test_find_latest_dispatch_plan_picks_newest_stamp(tmp_path):
    base = tmp_path / "data" / "processed" / "dispatch"
    _write_plan(base / "20260606_010000", [], [])
    _write_plan(base / "20260607_010000", [], [])
    (base / "20260605_nope").mkdir(parents=True)  # no suggested_runs.csv
    latest = find_latest_dispatch_plan(tmp_path)
    assert latest == base / "20260607_010000"


def test_find_latest_returns_none_when_absent(tmp_path):
    assert find_latest_dispatch_plan(tmp_path) is None


def test_load_dispatch_link_merges_suggested_and_review(tmp_path):
    plan = tmp_path / "p"
    _write_plan(
        plan,
        suggested_rows=[["SO-1", "id-1", "RUN-A", 0.95, "stable"]],
        review_rows=[["SO-2", "id-2", "RUN-B", 0.40, "mixed"],
                     ["SO-3", "id-3", None, 0.0, "no_address"]],
    )
    link = load_dispatch_link(plan)
    assert set(link.columns) == {
        "so_id", "predicted_run", "dispatch_flag", "confidence"}
    assert len(link) == 3
    row2 = link.loc[link["so_id"] == "id-2"].iloc[0]
    assert row2["predicted_run"] == "RUN-B"
    assert row2["dispatch_flag"] == "mixed"


def test_attach_marks_missing_orders_no_run(tmp_path):
    plan = tmp_path / "p"
    _write_plan(
        plan,
        suggested_rows=[["SO-1", "id-1", "RUN-A", 0.95, "stable"]],
        review_rows=[],
    )
    link = load_dispatch_link(plan)
    per_order = pd.DataFrame({"so_id": ["id-1", "id-9"], "so_ref": ["SO-1", "SO-9"]})
    out = attach_dispatch_runs(per_order, link)
    assert out.loc[out["so_id"] == "id-1", "predicted_run"].iloc[0] == "RUN-A"
    assert out.loc[out["so_id"] == "id-1", "dispatch_flag"].iloc[0] == "stable"
    # id-9 not in plan -> no_run on both
    assert out.loc[out["so_id"] == "id-9", "predicted_run"].iloc[0] == "no_run"
    assert out.loc[out["so_id"] == "id-9", "dispatch_flag"].iloc[0] == "no_run"
    assert "no_run" in FLAGGED_DISPATCH  # missing orders route to pallet


def test_attach_with_empty_link_marks_all_no_run():
    per_order = pd.DataFrame({"so_id": ["id-1"], "so_ref": ["SO-1"]})
    out = attach_dispatch_runs(per_order, pd.DataFrame())
    assert out["predicted_run"].iloc[0] == "no_run"
    assert out["dispatch_flag"].iloc[0] == "no_run"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_link.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.dispatch_link'`.

- [ ] **Step 3: Write the implementation**

Create `src/analysis/dispatch_link.py`:

```python
"""Bridge dispatch run-prediction into the wave pipeline.

The dispatch builder (scripts/build_dispatch.py / src/dispatch) writes a plan
per run to ``data/processed/dispatch/<stamp>/`` with:

  * ``suggested_runs.csv`` - own-fleet assignments
    (columns: so_ref, so_id, predicted_run, confidence, flag)
  * ``review.csv`` - low-confidence orders needing dispatcher attention
    (same columns; flag in {mixed, new_address, stale, no_address})

We load both, key by ``so_id``, and attach ``predicted_run`` + ``dispatch_flag``
onto the per-order frame so wave generation can group by run and route flagged
orders to the pallet stream. Read-only: we only read CSVs the dispatch step
already wrote; we never touch CartonCloud.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Dispatch flags meaning "don't trust the run - build it to a pallet".
# ``no_run`` is our own sentinel for orders absent from the dispatch plan.
FLAGGED_DISPATCH = frozenset(
    {"mixed", "new_address", "stale", "no_address", "no_run"}
)

_LINK_COLS = ["so_id", "predicted_run", "dispatch_flag", "confidence"]


def find_latest_dispatch_plan(repo_root: Path) -> Path | None:
    """Return the most recent ``data/processed/dispatch/<stamp>/`` dir.

    Only considers dirs that actually contain a ``suggested_runs.csv`` (a
    half-written plan dir is ignored). Returns ``None`` when there is none.
    """
    base = Path(repo_root) / "data" / "processed" / "dispatch"
    if not base.exists():
        return None
    candidates = sorted(
        (d for d in base.iterdir()
         if d.is_dir() and (d / "suggested_runs.csv").exists()),
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def load_dispatch_link(plan_dir: Path) -> pd.DataFrame:
    """Load ``suggested_runs.csv`` + ``review.csv`` into one so_id->run frame.

    Returns columns: ``so_id, predicted_run, dispatch_flag, confidence``.
    Suggested (own-fleet) rows take precedence over review rows if an id
    appears in both. Returns an empty frame (correct columns) if neither file
    exists or both are empty.
    """
    plan_dir = Path(plan_dir)
    frames: list[pd.DataFrame] = []
    for name in ("suggested_runs.csv", "review.csv"):
        path = plan_dir / name
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if df.empty:
            continue
        df = df.rename(columns={"flag": "dispatch_flag"})
        for col in _LINK_COLS:
            if col not in df.columns:
                df[col] = pd.NA
        df["so_id"] = df["so_id"].astype(str)
        frames.append(df[_LINK_COLS])
    if not frames:
        return pd.DataFrame(columns=_LINK_COLS)
    link = pd.concat(frames, ignore_index=True)
    return link.drop_duplicates("so_id", keep="first").reset_index(drop=True)


def attach_dispatch_runs(
    per_order: pd.DataFrame, link: pd.DataFrame
) -> pd.DataFrame:
    """Add ``predicted_run`` + ``dispatch_flag`` columns to a per-order frame.

    Orders absent from the dispatch plan (or when the link is empty) get
    ``predicted_run="no_run"`` and ``dispatch_flag="no_run"`` so they group
    under a ``no_run`` bucket and route to the pallet stream — never dropped.
    """
    out = per_order.copy()
    out["so_id"] = out["so_id"].astype(str)
    if link is None or link.empty:
        out["predicted_run"] = "no_run"
        out["dispatch_flag"] = "no_run"
        return out
    out = out.merge(link, on="so_id", how="left")
    out["predicted_run"] = out["predicted_run"].fillna("no_run")
    out["dispatch_flag"] = out["dispatch_flag"].fillna("no_run")
    return out
```

- [ ] **Step 4: Export from the analysis package**

In `src/analysis/__init__.py`, after the `from .full_pallet import (...)` block, add:

```python
from .dispatch_link import (
    FLAGGED_DISPATCH,
    attach_dispatch_runs,
    find_latest_dispatch_plan,
    load_dispatch_link,
)
```

And add to the `__all__` list (near the full_pallet entries):

```python
    "FLAGGED_DISPATCH", "find_latest_dispatch_plan",
    "load_dispatch_link", "attach_dispatch_runs",
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_link.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add src/analysis/dispatch_link.py tests/test_dispatch_link.py src/analysis/__init__.py
git commit -m "feat(wave): dispatch_link - join predicted runs onto per-order frame

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `classify_streams` rule R2b — dispatch-flagged orders route to pallet

**Files:**
- Modify: `src/analysis/routing.py` (add import + rule in `classify_streams`)
- Create: `tests/test_classify_streams.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_classify_streams.py`:

```python
"""Tests for stream classification, focused on the dispatch-flag rule (R2b)."""
from __future__ import annotations

import pandas as pd

from analysis.routing import (
    STREAM_BENCH,
    STREAM_PALLET,
    OrderMetricsResult,
    classify_streams,
)

_NO_RULES = pd.DataFrame(
    columns=["delivery_company_norm", "override_stream",
             "min_cartons_override", "notes"]
)


def _metrics(rows: list[dict]) -> OrderMetricsResult:
    """Build a minimal per-order frame with the columns classify_streams reads."""
    base = {
        "delivery_company_norm": "ACME",
        "total_cartons": 5,
        "has_full_pallet_line": False,
        "full_pallet_line_count": 0,
        "pallet_fraction": 0.1,
        "has_unknown_pickbench": False,
        "has_pickbench_sku": True,   # -> would be bench without other rules
        "all_direct_skus": False,
    }
    df = pd.DataFrame([{**base, **r} for r in rows])
    return OrderMetricsResult(
        per_order=df, n_orders=len(df), n_orders_with_dims=len(df),
        n_orders_partial_dims=0, pallet_fraction_method_summary={},
    )


def test_dispatch_flagged_order_routes_to_pallet():
    for flag in ("mixed", "new_address", "stale", "no_address", "no_run"):
        m = _metrics([{"dispatch_flag": flag}])
        res = classify_streams(m, _NO_RULES)
        assert res.per_order["stream"].iloc[0] == STREAM_PALLET, flag
        assert res.per_order["rule_fired"].iloc[0] == "R2b_dispatch_flagged"


def test_stable_flag_does_not_force_pallet():
    m = _metrics([{"dispatch_flag": "stable"}])
    res = classify_streams(m, _NO_RULES)
    # falls through to the normal bench rule (has_pickbench_sku=True)
    assert res.per_order["stream"].iloc[0] == STREAM_BENCH


def test_missing_dispatch_flag_column_is_harmless():
    # No dispatch_flag column at all -> behaves exactly as before (bench).
    m = _metrics([{}])
    res = classify_streams(m, _NO_RULES)
    assert res.per_order["stream"].iloc[0] == STREAM_BENCH
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_classify_streams.py -q`
Expected: FAIL — `test_dispatch_flagged_order_routes_to_pallet` fails because the order currently classifies as `STREAM_BENCH` (R6), not `STREAM_PALLET`.

- [ ] **Step 3: Add the import**

In `src/analysis/routing.py`, near the other relative imports (after `from .full_pallet import FullPalletAnalysis`), add:

```python
from .dispatch_link import FLAGGED_DISPATCH
```

- [ ] **Step 4: Add rule R2b in `classify_streams`**

In `src/analysis/routing.py`, inside the `for row in df.itertuples(index=False):` loop in `classify_streams`, immediately AFTER the R2 block (the `# R2: min_cartons threshold via consignee rule` block that ends with `continue`) and BEFORE the `# R3: any line flagged as full pallet` block, insert:

```python
        # R2b: dispatch flagged this order's run as untrustworthy (or it was
        # absent from the plan) -> build it to a pallet, don't risk the bench.
        dispatch_flag = getattr(row, "dispatch_flag", None)
        if isinstance(dispatch_flag, str) and dispatch_flag in FLAGGED_DISPATCH:
            streams.append(STREAM_PALLET)
            reasons.append(f"dispatch flag '{dispatch_flag}' -> pallet")
            rules_fired.append("R2b_dispatch_flagged")
            continue
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_classify_streams.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/analysis/routing.py tests/test_classify_streams.py
git commit -m "feat(wave): classify_streams R2b - dispatch-flagged orders -> pallet

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `plan_waves` — emit immediate waves for pallet + unclassified streams

**Files:**
- Modify: `src/analysis/routing.py` (`plan_waves`)
- Create: `tests/test_plan_waves_immediate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_plan_waves_immediate.py`:

```python
"""Tests for plan_waves immediate-stream emission (pallet + unclassified)."""
from __future__ import annotations

import pandas as pd

from analysis.routing import (
    STREAM_BENCH,
    STREAM_PALLET,
    STREAM_UNCLASSIFIED,
    StreamClassification,
    plan_waves,
)


def _classification(rows: list[dict]) -> StreamClassification:
    df = pd.DataFrame(rows)
    return StreamClassification(
        per_order=df,
        counts_by_stream=df["stream"].value_counts(),
        rule_hit_counts=pd.Series(dtype=int),
        threshold_used=0.7,
    )


_TS = "2026-06-07T08:00:00+10:00"


def test_pallet_orders_excluded_by_default():
    c = _classification([
        {"so_id": "p1", "stream": STREAM_PALLET, "total_cartons": 80,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
    ])
    plan = plan_waves(c, run_group_col="predicted_run")
    assert plan.per_wave.empty  # streams 2/3 only, default behaviour


def test_immediate_streams_emit_one_wave_per_run_stream():
    c = _classification([
        {"so_id": "p1", "stream": STREAM_PALLET, "total_cartons": 80,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "p2", "stream": STREAM_PALLET, "total_cartons": 70,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "u1", "stream": STREAM_UNCLASSIFIED, "total_cartons": 10,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
        {"so_id": "b1", "stream": STREAM_BENCH, "total_cartons": 5,
         "ts_packed": _TS, "predicted_run": "RUN-A"},
    ])
    plan = plan_waves(
        c, run_group_col="predicted_run", include_immediate_streams=True)
    streams = set(plan.per_wave["stream"])
    assert STREAM_PALLET in streams
    assert STREAM_UNCLASSIFIED in streams
    assert STREAM_BENCH in streams
    # the two pallet orders for RUN-A collapse into a single immediate wave
    pallet_waves = plan.per_wave[plan.per_wave["stream"] == STREAM_PALLET]
    assert len(pallet_waves) == 1
    assert pallet_waves.iloc[0]["order_count"] == 2
    assert pallet_waves.iloc[0]["release_reason"] == "immediate"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_plan_waves_immediate.py -q`
Expected: FAIL — `plan_waves() got an unexpected keyword argument 'include_immediate_streams'`.

- [ ] **Step 3: Replace `plan_waves` with the immediate-stream-aware version**

In `src/analysis/routing.py`, replace the entire `plan_waves` function body with the following (keeps streams 2/3 behaviour identical when `include_immediate_streams=False`):

```python
def plan_waves(
    classification: StreamClassification,
    cutoff: dt_time = DEFAULT_WAVE_CUTOFF,
    early_release_cartons: int = DEFAULT_EARLY_RELEASE_CARTONS,
    run_group_col: str = "delivery_state",
    include_immediate_streams: bool = False,
) -> WavePlan:
    """Group wave-eligible orders into release waves.

    Streams 2 + 3 (bypass / bench) accumulate FIFO by ts_packed within each
    (received_date, run_group, stream) group; a wave releases when accumulated
    cartons cross early_release_cartons, and leftovers form a final cutoff wave.

    When ``include_immediate_streams`` is True, streams 1 (pallet) + 0
    (unclassified) also emit ONE wave per (received_date, run_group, stream)
    with no accumulation (``release_reason="immediate"``) so the sheet
    generator produces pick-to-pallet paperwork for them. When False (default),
    they are excluded - preserving the historical streams-2/3-only behaviour.

    run_group_col defaults to delivery_state; pass "predicted_run" to group by
    the dispatch-predicted delivery run.
    """
    df = classification.per_order
    if df.empty:
        return WavePlan(
            per_wave=pd.DataFrame(),
            per_order_assignment=pd.DataFrame(),
            cutoff_used=cutoff,
            early_release_cartons=early_release_cartons,
        )

    work = df.copy()

    # received_date for grouping - use ts_packed (the timestamp we have),
    # localised to Melbourne for the cutoff comparison.
    ts = pd.to_datetime(work["ts_packed"], errors="coerce", utc=True)
    try:
        ts_local = ts.dt.tz_convert("Australia/Melbourne")
    except (TypeError, AttributeError):
        ts_local = ts
    work["receive_date"] = ts_local.dt.date

    if run_group_col not in work.columns:
        log.warning(
            "run_group_col %r not in per_order; falling back to delivery_state",
            run_group_col,
        )
        run_group_col = "delivery_state"

    waves_per_order_rows: list[dict] = []
    waves_summary_rows: list[dict] = []
    group_keys = ["receive_date", run_group_col, "stream"]

    # --- streams 2 + 3: accumulate with early-release + cutoff ---
    eligible = work[work["stream"].isin([STREAM_BYPASS, STREAM_BENCH])].copy()
    if not eligible.empty:
        eligible = eligible.sort_values(
            ["receive_date", run_group_col, "stream", "ts_packed"]
        ).reset_index(drop=True)
        for keys, group in eligible.groupby(group_keys, sort=False, dropna=False):
            receive_date, run_group, stream = keys
            accumulated = 0.0
            wave_idx = 1
            wave_orders: list[dict] = []
            for row in group.itertuples(index=False):
                wave_orders.append({
                    "so_id": row.so_id,
                    "cartons": float(row.total_cartons),
                    "ts_packed": row.ts_packed,
                })
                accumulated += float(row.total_cartons)
                if accumulated >= early_release_cartons:
                    wave_id = _make_wave_id(
                        receive_date, run_group, stream, wave_idx)
                    _emit_wave(
                        wave_id, receive_date, run_group, stream, wave_idx,
                        wave_orders, "early_release",
                        waves_per_order_rows, waves_summary_rows,
                    )
                    wave_orders = []
                    accumulated = 0.0
                    wave_idx += 1
            if wave_orders:
                wave_id = _make_wave_id(
                    receive_date, run_group, stream, wave_idx)
                _emit_wave(
                    wave_id, receive_date, run_group, stream, wave_idx,
                    wave_orders, "cutoff_release",
                    waves_per_order_rows, waves_summary_rows,
                )

    # --- streams 1 + 0: one immediate wave per (date, run, stream) ---
    if include_immediate_streams:
        immediate = work[
            work["stream"].isin([STREAM_PALLET, STREAM_UNCLASSIFIED])
        ].copy()
        if not immediate.empty:
            immediate = immediate.sort_values(
                ["receive_date", run_group_col, "stream", "ts_packed"]
            ).reset_index(drop=True)
            for keys, group in immediate.groupby(
                group_keys, sort=False, dropna=False
            ):
                receive_date, run_group, stream = keys
                wave_orders = [{
                    "so_id": row.so_id,
                    "cartons": float(row.total_cartons),
                    "ts_packed": row.ts_packed,
                } for row in group.itertuples(index=False)]
                wave_id = _make_wave_id(receive_date, run_group, stream, 1)
                _emit_wave(
                    wave_id, receive_date, run_group, stream, 1,
                    wave_orders, "immediate",
                    waves_per_order_rows, waves_summary_rows,
                )

    per_order_df = pd.DataFrame(waves_per_order_rows)
    per_wave_df = pd.DataFrame(waves_summary_rows)

    log.info(
        "planned %d waves across %d orders (cutoff=%s, early=%d cartons, "
        "immediate=%s)",
        len(per_wave_df), len(per_order_df),
        cutoff.strftime("%H:%M"), early_release_cartons,
        include_immediate_streams,
    )

    return WavePlan(
        per_wave=per_wave_df,
        per_order_assignment=per_order_df,
        cutoff_used=cutoff,
        early_release_cartons=early_release_cartons,
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_plan_waves_immediate.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the existing suite to confirm no regression in streams 2/3**

Run: `.venv/bin/python -m pytest tests/test_wave_consolidation.py tests/test_wave_runner.py -q`
Expected: PASS (the refactor is behaviour-preserving for `include_immediate_streams=False`). If `test_wave_runner.py` fails here, that is expected and fixed in Task 5 — note it and continue.

- [ ] **Step 6: Commit**

```bash
git add src/analysis/routing.py tests/test_plan_waves_immediate.py
git commit -m "feat(wave): plan_waves emits immediate pallet/unclassified waves

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `generate_wave_pick_sheets` — pass `include_immediate_streams` through

**Files:**
- Modify: `src/analysis/wave_picks.py` (`generate_wave_pick_sheets`)
- Create: `tests/test_wave_picks_pallet_sheets.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_wave_picks_pallet_sheets.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_wave_picks_pallet_sheets.py -q`
Expected: FAIL — `generate_wave_pick_sheets() got an unexpected keyword argument 'include_immediate_streams'`.

- [ ] **Step 3: Add the parameter and pass it through**

In `src/analysis/wave_picks.py`, change the `generate_wave_pick_sheets` signature to add the new keyword (after `early_release_cartons`):

```python
def generate_wave_pick_sheets(
    classification: StreamClassification,
    so_lines: pd.DataFrame,
    sku_locations: pd.DataFrame | None = None,
    aisle_walk_order: list[str] | None = None,
    run_group_col: str = "delivery_state",
    early_release_cartons: int | None = None,
    include_immediate_streams: bool = False,
) -> WaveGenerationResult:
```

Then, in the same function, find the `plan_kwargs` block:

```python
    plan_kwargs: dict = {"run_group_col": run_group_col}
    if early_release_cartons is not None:
        plan_kwargs["early_release_cartons"] = early_release_cartons
    wave_plan = plan_waves(classification, **plan_kwargs)
```

and insert the passthrough before the `plan_waves` call:

```python
    plan_kwargs: dict = {"run_group_col": run_group_col}
    if early_release_cartons is not None:
        plan_kwargs["early_release_cartons"] = early_release_cartons
    plan_kwargs["include_immediate_streams"] = include_immediate_streams
    wave_plan = plan_waves(classification, **plan_kwargs)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_wave_picks_pallet_sheets.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/analysis/wave_picks.py tests/test_wave_picks_pallet_sheets.py
git commit -m "feat(wave): generate_wave_pick_sheets threads include_immediate_streams

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `wave_runner` — link runs, default to predicted_run, pallet sheets on, clean-fail

**Files:**
- Modify: `src/wave_runner.py` (`WaveRunSettings`, `run_wave_generation`, `_settings_dict`)
- Modify: `tests/test_wave_runner.py` (defaults test + 3 e2e tests + a new run-grouping test)

- [ ] **Step 1: Update the defaults test and add a dispatch-plan fixture (failing)**

In `tests/test_wave_runner.py`:

(a) Change the defaults assertion:

```python
    assert s.run_group_col == "predicted_run"
```

and add two lines to the same test (`test_settings_defaults_pull_from_analysis_constants`):

```python
    assert s.include_pallet_sheets is True
    assert s.dispatch_plan_dir is None
```

(b) Add this helper near the top of the file (after `_ROOT = ...`):

```python
def _write_dispatch_plan(dir_path, rows):
    """Write a minimal suggested_runs.csv so wave_runner can link runs.

    rows: list of (so_id, predicted_run, flag) tuples.
    """
    import pandas as pd
    dir_path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [(f"ref-{sid}", sid, run, 0.9, flag) for sid, run, flag in rows],
        columns=["so_ref", "so_id", "predicted_run", "confidence", "flag"],
    ).to_csv(dir_path / "suggested_runs.csv", index=False)
```

(c) Update the three e2e tests to provide a dispatch plan dir. The fake order
`_fake_order("SO-1", ...)` has CC id `id-SO-1`; the real flattener sets `so_id`
to that id. Map it to a run so the order links cleanly. In
`test_run_emits_progress_and_writes_run`, replace the `settings = ...` line with:

```python
    plan_dir = tmp_path / "dispatch"
    _write_dispatch_plan(plan_dir, [("id-SO-1", "RUN-A", "stable")])
    settings = WaveRunSettings(
        repo_root=_ROOT, out_dir=tmp_path / "waves",
        dispatch_plan_dir=plan_dir)
```

Apply the identical two-line change (build `plan_dir`, pass `dispatch_plan_dir=plan_dir`)
to `test_soh_failure_fails_the_run`. For `test_run_with_no_orders_is_empty`,
the run exits at the empty-orders branch before run-linking, so add the same
`plan_dir` + `dispatch_plan_dir=plan_dir` for safety/consistency.

(d) Add a new test that proves run-grouping + clean-fail:

```python
def test_run_grouping_requires_a_dispatch_plan(tmp_path, fake_cc):
    orders = [_fake_order("SO-1", "SOME-SKU")]
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter(orders),
    )
    events: list[ProgressEvent] = []
    # predicted_run grouping but NO dispatch plan anywhere -> clean fail.
    settings = WaveRunSettings(
        repo_root=tmp_path, out_dir=tmp_path / "waves",
        dispatch_plan_dir=tmp_path / "does-not-exist")
    result = run_wave_generation(settings, events.append)
    assert result.status == "failed"
    assert any("dispatch plan" in e.message.lower()
               for e in events if e.level == "error")
```

> Note: this test sets `repo_root=tmp_path` so `find_latest_dispatch_plan`
> finds nothing (no `data/processed/dispatch/`), forcing the clean-fail path.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_wave_runner.py -q`
Expected: FAIL — defaults test fails (`run_group_col` still `delivery_state`), new test errors (`WaveRunSettings` has no `dispatch_plan_dir`).

- [ ] **Step 3: Add the new settings fields**

In `src/wave_runner.py`, in `WaveRunSettings`, change the `run_group_col` default and add two fields:

```python
    run_group_col: str = "predicted_run"
```

and, after the `out_dir: Path | None = None` line, add:

```python
    dispatch_plan_dir: Path | None = None
    include_pallet_sheets: bool = True
```

- [ ] **Step 4: Add the import**

In `src/wave_runner.py`, in the `from analysis import (...)` block, add these names (keep alphabetical-ish grouping with the others):

```python
    attach_dispatch_runs,
    find_latest_dispatch_plan,
    load_dispatch_link,
```

- [ ] **Step 5: Wire run-linking into `run_wave_generation`**

In `src/wave_runner.py`, immediately AFTER the line:

```python
        metrics = compute_order_metrics(snap, dims, full_pallet)
```

and BEFORE the `emit("route", ...)` call, insert:

```python
        # 4b. link dispatch-predicted runs onto the per-order frame so we can
        # group by run and route flagged orders to the pallet stream.
        plan_dir = settings.dispatch_plan_dir or find_latest_dispatch_plan(
            repo_root)
        if plan_dir is not None and plan_dir.exists():
            link = load_dispatch_link(plan_dir)
            metrics.per_order = attach_dispatch_runs(metrics.per_order, link)
            emit("route", f"linked runs from dispatch plan {plan_dir.name} "
                          f"({len(link)} mapped orders)", level="ok")
        elif settings.run_group_col == "predicted_run":
            raise CartonCloudError(
                "no dispatch plan found (run build_dispatch first) — refusing "
                "to wave by predicted_run without run grouping")
        else:
            # delivery_state grouping without a plan: no flags available.
            metrics.per_order["dispatch_flag"] = "no_plan"
```

> `"no_plan"` is deliberately NOT in `FLAGGED_DISPATCH`, so the legacy
> delivery_state path classifies exactly as before.

- [ ] **Step 6: Pass the pallet-sheets flag into generation**

In `src/wave_runner.py`, update the `generate_wave_pick_sheets(...)` call (step 7 in the function) to add the new keyword:

```python
        result = generate_wave_pick_sheets(
            classification=classification, so_lines=snap.so_lines,
            sku_locations=sku_locations,
            run_group_col=settings.run_group_col,
            early_release_cartons=settings.early_release_cartons,
            include_immediate_streams=settings.include_pallet_sheets)
```

- [ ] **Step 7: Record the new settings in the manifest**

In `src/wave_runner.py`, in `_settings_dict`, add two entries to the returned dict (alongside `run_group_col`):

```python
        "dispatch_plan_dir": str(settings.dispatch_plan_dir)
        if settings.dispatch_plan_dir else None,
        "include_pallet_sheets": settings.include_pallet_sheets,
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_wave_runner.py -q`
Expected: PASS (all tests in the file, including the new clean-fail test).

- [ ] **Step 9: Commit**

```bash
git add src/wave_runner.py tests/test_wave_runner.py
git commit -m "feat(wave): group by predicted_run, link dispatch plan, pallet sheets on

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: index measure-list + runs×streams roll-up

**Files:**
- Modify: `src/wave_runner.py` (`_build_index_md` signature + call site, compute measure-list)
- Modify: `tests/test_wave_runner.py` (assert the measure-list section appears)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wave_runner.py`:

```python
def test_index_lists_skus_to_measure(tmp_path, fake_cc):
    # SOME-SKU is not in the real dims file -> it should appear in the
    # "SKUs to measure" section of index.md.
    orders = [_fake_order("SO-1", "SOME-SKU")]
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter(orders),
    )
    plan_dir = tmp_path / "dispatch"
    _write_dispatch_plan(plan_dir, [("id-SO-1", "RUN-A", "stable")])
    settings = WaveRunSettings(
        repo_root=_ROOT, out_dir=tmp_path / "waves",
        dispatch_plan_dir=plan_dir)
    result = run_wave_generation(settings, [].append)
    index = (result.out_dir / "index.md").read_text()
    assert "SKUs to measure" in index
    assert "SOME-SKU" in index
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_wave_runner.py::test_index_lists_skus_to_measure -q`
Expected: FAIL — `index.md` has no "SKUs to measure" section.

- [ ] **Step 3: Compute the measure-list and pass it to the index builder**

In `src/wave_runner.py`, change the `_build_index_md` signature to accept the list:

```python
def _build_index_md(
    out_dir: Path,
    sheets: list,
    skipped: pd.DataFrame,
    cfg: dict,
    skus_to_measure: list[str] | None = None,
) -> None:
```

At the END of `_build_index_md` (after the existing skipped-orders block, before the file is written — locate the final `(out_dir / "index.md").write_text(...)` and insert before it), add:

```python
    if skus_to_measure:
        lines.extend([
            "",
            f"## {len(skus_to_measure)} SKU(s) to measure",
            "",
            "These SKUs appear on today's orders but have no captured carton "
            "dims, so their orders could not be cube-classified and rode the "
            "pallet sheets. Capture dims to let them classify normally.",
            "",
            "| SKU |",
            "|---|",
            *[f"| `{sku}` |" for sku in skus_to_measure],
        ])
```

> If `_build_index_md` builds its string differently (e.g. returns early), keep
> the rule: append the section to the `lines` list before it is joined/written.

- [ ] **Step 4: Compute the list at the call site**

In `run_wave_generation`, just BEFORE the `_build_index_md(...)` call (step 9), add:

```python
        measured = set(
            dims.loc[dims["measurement_complete"] == True, "product_code"]  # noqa: E712
            .astype(str)
        )
        order_skus = set(snap.so_lines["product_code"].dropna().astype(str))
        skus_to_measure = sorted(order_skus - measured)
```

and update the call to pass it:

```python
        _build_index_md(out_dir, result.sheets, result.skipped_orders,
                        _settings_dict(settings, audit_path),
                        skus_to_measure=skus_to_measure)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_wave_runner.py::test_index_lists_skus_to_measure -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wave_runner.py tests/test_wave_runner.py
git commit -m "feat(wave): index.md lists SKUs-to-measure (cube-uncertain orders)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: CLI + console wiring

**Files:**
- Modify: `scripts/generate_waves.py` (add `--dispatch-plan`)
- Modify: `src/web/app.py` (default `run_group_col` form value → `predicted_run`)
- Modify: `tests/test_web.py` (assert the form default)

- [ ] **Step 1: Add the CLI flag**

In `scripts/generate_waves.py`, in the argparse block (near `--run-group-col`), add:

```python
    p.add_argument("--dispatch-plan", type=Path, default=None,
                   help="dispatch plan dir (data/processed/dispatch/<stamp>/); "
                        "default = latest")
```

and in the settings-building block (where other `if args.X is not None:` lines are), add:

```python
    if args.dispatch_plan is not None:
        kw["dispatch_plan_dir"] = args.dispatch_plan
```

- [ ] **Step 2: Update the console form default (write the failing test first)**

In `tests/test_web.py`, find the test that renders the index form (it checks the form HTML). Add an assertion that the run-group default is now `predicted_run`. If an existing assertion checks for `delivery_state` as the selected/default value, change it to `predicted_run`. Add:

```python
def test_index_form_defaults_to_predicted_run(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "predicted_run" in resp.text
```

> `client` is the existing FastAPI TestClient fixture in `tests/test_web.py`;
> reuse whatever fixture the neighbouring tests use.

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_web.py::test_index_form_defaults_to_predicted_run -q`
Expected: FAIL if the template/Form default is still `delivery_state`.

- [ ] **Step 4: Change the form default**

In `src/web/app.py`, change the run handler's form default:

```python
        run_group_col: str = Form("predicted_run"),
```

If the HTML template (`src/web/templates/`) hardcodes a `delivery_state` default
in an input/select for run grouping, update that default value to
`predicted_run` so the rendered page matches.

- [ ] **Step 5: Run the web tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_web.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_waves.py src/web/app.py src/web/templates tests/test_web.py
git commit -m "feat(wave): CLI --dispatch-plan + console defaults to predicted_run

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: cube-threshold calibration script

**Files:**
- Create: `scripts/calibrate_pallet_cube.py`
- Create: `tests/test_calibrate_pallet_cube.py`

- [ ] **Step 1: Write the failing test for the pure helper**

Create `tests/test_calibrate_pallet_cube.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_calibrate_pallet_cube.py -q`
Expected: FAIL — script does not exist.

- [ ] **Step 3: Write the calibration script**

Create `scripts/calibrate_pallet_cube.py`:

```python
"""Recommend a pallet-cube threshold (pallet_fraction) from real order data.

The pallet stream trigger (routing.classify_streams R4) fires when an order's
``pallet_fraction`` (cube sum / a pallet's usable cube) crosses a threshold.
Carton COUNT is noisy; cube is the honest signal. This script computes the
distribution of ``pallet_fraction_cube`` over a snapshot so the operator can
set the default where real pallet picks (~60-90 cartons) actually fall.

Read-only. Uses a local snapshot + dims; touches no network.

Usage:
    .venv/bin/python scripts/calibrate_pallet_cube.py [--raw DIR] [--dims FILE]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import sys
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from analysis import (  # noqa: E402
    compute_order_metrics,
    compute_velocity,
    apply_tags,
    load_dimensions,
    load_latest,
    run_full_pallet_analysis,
)


def recommend_threshold(per_order: pd.DataFrame) -> dict:
    """Summarise pallet_fraction_cube and recommend a threshold.

    The recommendation is the 90th percentile of non-trivial orders (fraction
    >= 0.05), rounded to 2 dp - a defensible "this order is pallet-sized"
    knee. The operator can override; this is a starting point, not a law.
    """
    frac = pd.to_numeric(
        per_order["pallet_fraction_cube"], errors="coerce"
    ).dropna()
    nontrivial = frac[frac >= 0.05]
    pct = lambda s, p: float(np.percentile(s, p)) if len(s) else float("nan")
    rec_basis = nontrivial if len(nontrivial) else frac
    return {
        "n_orders": int(len(frac)),
        "p50": round(pct(frac, 50), 3),
        "p75": round(pct(frac, 75), 3),
        "p90": round(pct(frac, 90), 3),
        "p95": round(pct(frac, 95), 3),
        "recommended_threshold": round(pct(rec_basis, 90), 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=_ROOT / "data" / "raw")
    ap.add_argument("--dims", type=Path, default=None)
    args = ap.parse_args()

    snap = load_latest(args.raw)
    dim_path = args.dims or sorted(
        (_ROOT / "data" / "dims").glob("dims_*.xlsx"))[-1]
    dims = load_dimensions(dim_path)
    vel = compute_velocity(snap)
    apply_tags(vel.sku_metrics, dims)
    fp = run_full_pallet_analysis(snap, dims, vel.sku_metrics)
    metrics = compute_order_metrics(snap, dims, fp)

    rec = recommend_threshold(metrics.per_order)
    print("Pallet-cube calibration")
    print("-----------------------")
    for k, v in rec.items():
        print(f"  {k:>22}: {v}")
    print()
    print(f"Set --pallet-fraction-threshold {rec['recommended_threshold']} "
          f"(currently default 0.70).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_calibrate_pallet_cube.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/calibrate_pallet_cube.py tests/test_calibrate_pallet_cube.py
git commit -m "feat(wave): pallet-cube threshold calibration script

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Full-suite green + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all prior tests plus the new ones (≥ 129 + new). If anything in `test_web_dispatch.py` / `test_dispatch_*` broke, it should not have (no dispatch-side code changed); investigate any failure before proceeding.

- [ ] **Step 2: Confirm the read-only guard is still green**

Run: `.venv/bin/python -m pytest tests/test_read_only_guard.py -q`
Expected: PASS — the non-negotiable (CC read-only) is intact.

- [ ] **Step 3: Calibrate the threshold against real data (manual, optional but recommended)**

Run: `.venv/bin/python scripts/calibrate_pallet_cube.py`
Expected: prints the cube-fraction distribution + a recommended `--pallet-fraction-threshold`. Note the value; set it as the console/CLI default in a follow-up if it differs materially from 0.70.

- [ ] **Step 4: Manual end-to-end smoke (requires live CC creds + a dispatch plan)**

```bash
# 1. build a dispatch plan (read-only)
.venv/bin/python scripts/build_dispatch.py
# 2. generate run-grouped, stream-split waves (reads the latest plan)
.venv/bin/python scripts/generate_waves.py
```

Expected: `data/processed/waves/<stamp>/` contains per-(run,stream) wave dirs
including `..._S1_...` pallet sheets; `index.md` shows runs × streams and a
"SKUs to measure" section. Read-only — no CC writes.

- [ ] **Step 5: Finalise the branch**

Use the `superpowers:finishing-a-development-branch` skill to decide merge/PR.

---

## Plan self-review notes

- **Spec coverage:** dispatch join (T1), group-by-run (T5), flagged→pallet (T2), pallet paperwork (T3+T4), cube-uncertain rides pallet + measure-list (T3 routes `0_unclassified` immediate, T6 lists SKUs), keep-cube-threshold + calibrate (T8), CLI/console (T7), read-only + clean-fail (T5/T9). All spec sections map to a task.
- **No new cube knob:** reuses existing `pallet_fraction_threshold` per the revised spec; T8 calibrates rather than adds.
- **Behaviour preservation:** `plan_waves` refactor (T3) is identical for `include_immediate_streams=False`; the only intended default change is `run_group_col` → `predicted_run` (T5), with its test fallout fixed in the same task.
- **Type consistency:** `predicted_run` / `dispatch_flag` column names, `FLAGGED_DISPATCH`, `include_immediate_streams` / `include_pallet_sheets`, and stream constants (`STREAM_PALLET` etc.) are used identically across tasks.
```
