# Wave Pick Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web console (FastAPI + HTMX + SSE) that lets a Go Cold operator trigger a live wave pick generation run, watch it stream progress, and browse/download the resulting waves — without touching the terminal.

**Architecture:** Lift the pipeline body out of `scripts/generate_waves.py:main()` into a reusable `src/wave_runner.py:run_wave_generation(settings, progress)` shared by the CLI and the web app. A `JobManager` runs that function in a worker thread (the pipeline is blocking httpx/pandas), buffering `ProgressEvent`s for SSE. Viewing reads straight from the run folders on disk (`manifest.json`, per-wave CSVs) — no database.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, Jinja2, HTMX (vendored), Server-Sent Events, pandas, pytest. No Node/SPA build step.

**Spec:** `docs/superpowers/specs/2026-06-04-wave-pick-console-design.md`

---

## File Structure

```
src/wave_runner.py            # NEW — settings/events/result dataclasses + run_wave_generation + moved helpers
src/web/
  __init__.py                 # NEW — empty package marker
  app.py                      # NEW — FastAPI app factory + routes
  jobs.py                     # NEW — JobManager, single-run guard, event buffering
  runs.py                     # NEW — disk readers (list_runs/get_run/get_wave/file_path)
  templates/
    base.html                 # NEW — header, palette, vendored HTMX
    index.html                # NEW — console: settings form + progress target + history
    run_detail.html           # NEW — summary cards, waves table, skipped panel
    wave_detail.html          # NEW — pick lines in walk order + downloads
    _progress.html            # NEW — SSE progress panel partial
    _run_busy.html            # NEW — "run already in progress" partial
  static/
    app.css                   # NEW — palette + layout
    htmx.min.js               # NEW — vendored
    sse.js                    # NEW — vendored HTMX SSE extension
scripts/serve_web.py          # NEW — uvicorn launcher
scripts/generate_waves.py     # MODIFY — thin CLI wrapper over wave_runner
requirements.txt              # MODIFY — add fastapi/uvicorn/jinja2/python-multipart
tests/test_wave_runner.py     # NEW
tests/test_jobs.py            # NEW
tests/test_web.py             # NEW
tests/conftest.py             # already puts src/ on sys.path — reused
```

**Convention note:** Tests import from the `src/` layout (`from wave_runner import ...`, `from web.jobs import ...`) because `tests/conftest.py` already inserts `src/` on `sys.path`. The web app is the package `web` (i.e. `src/web/`); uvicorn target is `web.app:app`.

---

## Task 1: Dependencies + wave_runner dataclasses

**Files:**
- Modify: `requirements.txt`
- Create: `src/wave_runner.py`
- Test: `tests/test_wave_runner.py`

- [ ] **Step 1: Add the web deps to requirements.txt**

Append these lines under the existing deps (before the `# dev / tests` block):

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
jinja2>=3.1.0
python-multipart>=0.0.9   # FastAPI form parsing
```

- [ ] **Step 2: Install them**

Run: `python -m pip install -r requirements.txt`
Expected: installs fastapi, uvicorn, jinja2, python-multipart (and starlette).

(Use `python -m pip`, not the `pip` wrapper — the venv has a stale shebang.)

- [ ] **Step 3: Write the failing test for the dataclasses**

Create `tests/test_wave_runner.py`:

```python
"""Tests for the shared wave-generation core (src/wave_runner.py)."""
from __future__ import annotations

from pathlib import Path

from wave_runner import ProgressEvent, RunResult, WaveRunSettings


def test_settings_defaults_pull_from_analysis_constants():
    s = WaveRunSettings(repo_root=Path("/tmp/repo"))
    assert s.status == "AWAITING_PICK_AND_PACK"
    assert s.customer_name is None
    assert s.pallet_fraction_threshold == 0.70
    assert s.early_release_cartons == 30
    assert s.run_group_col == "delivery_state"
    assert s.soh_fallback is False
    assert s.lines_per_hour == 60


def test_progress_event_levels_default_info():
    e = ProgressEvent(stage="pull", message="pulling orders")
    assert e.level == "info"
    assert e.data == {}


def test_run_result_holds_summary():
    r = RunResult(
        run_id="20260604_081200",
        out_dir=Path("/tmp/run"),
        summary={"n_waves": 3},
        status="success",
    )
    assert r.status == "success"
    assert r.summary["n_waves"] == 3
    assert r.error is None
```

- [ ] **Step 4: Run it to verify it fails**

Run: `python -m pytest tests/test_wave_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wave_runner'`.

- [ ] **Step 5: Create src/wave_runner.py with just the dataclasses**

```python
"""Shared core for wave pick generation.

Both the CLI (``scripts/generate_waves.py``) and the web console
(``src/web/``) call ``run_wave_generation`` so the pipeline lives in one
place. The CLI passes a ``progress`` callback that prints; the web app
passes one that buffers events for SSE.

Read-only against CartonCloud — we generate paperwork, never push back.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from analysis import (
    DEFAULT_AWAITING_STATUS,
    DEFAULT_EARLY_RELEASE_CARTONS,
    DEFAULT_LINES_PER_HOUR,
    DEFAULT_PALLET_FRACTION_THRESHOLD,
)


@dataclass
class WaveRunSettings:
    """Everything ``run_wave_generation`` needs for one run.

    ``repo_root`` anchors the default data/output paths. Explicit path
    fields override the defaults (used by the CLI's flags).
    """
    repo_root: Path
    status: str = DEFAULT_AWAITING_STATUS
    customer_name: str | None = None
    pallet_fraction_threshold: float = DEFAULT_PALLET_FRACTION_THRESHOLD
    early_release_cartons: int = DEFAULT_EARLY_RELEASE_CARTONS
    run_group_col: str = "delivery_state"
    soh_fallback: bool = False
    lines_per_hour: int = DEFAULT_LINES_PER_HOUR
    pallet_ratio: float = 0.9
    # Optional explicit paths; None = resolve from repo_root at run time.
    raw_dir: Path | None = None
    dims_path: Path | None = None
    locations_path: Path | None = None
    rules_path: Path | None = None
    assignments_path: Path | None = None
    logo_path: Path | None = None
    out_dir: Path | None = None


@dataclass
class ProgressEvent:
    """One streamed progress line."""
    stage: str          # machine key: pull / snapshot / dims / route / classify / locations / assignments / generate / write / done
    message: str        # human-readable line
    level: str = "info"  # info / ok / error
    data: dict = field(default_factory=dict)


@dataclass
class RunResult:
    """Outcome of a single ``run_wave_generation`` call."""
    run_id: str
    out_dir: Path
    summary: dict
    status: str          # success / empty / failed
    error: str | None = None


ProgressCallback = Callable[[ProgressEvent], None]
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/test_wave_runner.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt src/wave_runner.py tests/test_wave_runner.py
git commit -m "feat: wave_runner settings/event/result dataclasses + web deps"
```

---

## Task 2: Move the pipeline helpers into wave_runner

Move the private helpers out of `scripts/generate_waves.py` into `wave_runner.py` unchanged, so the core function can use them. The CLI will import them back.

**Files:**
- Modify: `src/wave_runner.py`
- Test: `tests/test_wave_runner.py`

- [ ] **Step 1: Write the failing test for a moved helper**

Add to `tests/test_wave_runner.py`:

```python
def test_latest_file_picks_newest(tmp_path):
    from wave_runner import _latest_file
    old = tmp_path / "dims_2026-05-11.xlsx"
    new = tmp_path / "dims_2026-05-13.xlsx"
    old.write_text("a")
    new.write_text("b")
    import os, time
    os.utime(old, (time.time() - 100, time.time() - 100))
    assert _latest_file(tmp_path, "dims_*.xlsx") == new


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    from wave_runner import _load_dotenv
    env = tmp_path / ".env"
    env.write_text('FOO="bar"\n# comment\nBAZ=qux\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    _load_dotenv(env)
    import os
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_wave_runner.py -k "latest_file or dotenv" -v`
Expected: FAIL with `ImportError: cannot import name '_latest_file'`.

- [ ] **Step 3: Move the helpers into wave_runner.py**

Add these imports at the top of `src/wave_runner.py` (after the existing imports):

```python
import importlib.util
import json
import logging
import os
import sys
from datetime import datetime

import pandas as pd

from analysis import (  # extend the existing analysis import block
    apply_tags,
    classify_streams,
    compute_order_metrics,
    compute_velocity,
    generate_wave_pick_sheets,
    load_consignee_rules,
    load_dimensions,
    load_latest,
    run_full_pallet_analysis,
)
from analysis.loaders import Snapshot
from cc_client import (
    CartonCloudClient,
    CartonCloudError,
    get_sku_locations,
    search_outbound_orders,
)
from locations import load_cc_locations
from output import generate_wave_pdf, write_wave_csvs

log = logging.getLogger("wave_runner")
```

Then move these functions **verbatim** from `scripts/generate_waves.py` into `wave_runner.py` (cut them from the script; they are re-imported in Task 3):
- `_load_dotenv`
- `_latest_file`
- `_latest_assignments`
- `_pull_open_orders` — change its `print(...)` calls to accept and call a `progress` callback (done in Task 3's function; for now move verbatim, keeping `print`).
- `_build_snapshot`
- `_build_index_md`

Also move the `_flatten_outbound_order_lines` bootstrap (the `importlib` block that loads `scripts/extract.py`). Keep it as a module-level load but anchor the path off a passed-in repo_root — replace the top-level execution with a small cached loader:

```python
_flatten_cache: dict = {}


def _get_flatten_fn(repo_root: Path):
    """Lazily load _flatten_outbound_order_lines from scripts/extract.py."""
    if "fn" not in _flatten_cache:
        extract_path = repo_root / "scripts" / "extract.py"
        spec = importlib.util.spec_from_file_location("_extract_mod", extract_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _flatten_cache["fn"] = mod._flatten_outbound_order_lines
    return _flatten_cache["fn"]
```

Update `_pull_open_orders` to take `flatten_fn` as a parameter instead of the module global:

```python
def _pull_open_orders(
    client: CartonCloudClient,
    *,
    status: list[str],
    customer_name: str | None,
    out_path: Path,
    flatten_fn,
) -> pd.DataFrame:
    # ... body unchanged except: rows.extend(flatten_fn(order))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_wave_runner.py -k "latest_file or dotenv" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wave_runner.py tests/test_wave_runner.py
git commit -m "refactor: move wave pipeline helpers into wave_runner"
```

---

## Task 3: Implement run_wave_generation (the core)

**Files:**
- Modify: `src/wave_runner.py`
- Test: `tests/test_wave_runner.py`

- [ ] **Step 1: Write the failing test with a fake CC client**

Add to `tests/test_wave_runner.py`. This uses real fixture data already in the repo (`data/dims/`, `data/locations/`, latest raw parquets) but a fake CC pull so no network is hit:

```python
import pandas as pd
import pytest

from wave_runner import run_wave_generation, WaveRunSettings, ProgressEvent

_ROOT = Path(__file__).resolve().parent.parent


def _fake_order(so_ref, code):
    """Minimal CC order shape that _flatten_outbound_order_lines accepts."""
    return {
        "id": f"id-{so_ref}",
        "customerReference": so_ref,
        "customerName": "The Forage Company",
        "status": "AWAITING_PICK_AND_PACK",
        "items": [
            {"productCode": code, "productName": "Test Product",
             "measures": {"quantity": 5}},
        ],
    }


@pytest.fixture
def fake_cc(monkeypatch):
    """Patch the live CC pull + client construction to avoid network."""
    monkeypatch.setattr(
        "wave_runner.CartonCloudClient.from_env",
        classmethod(lambda cls, **kw: object()),
    )
    return monkeypatch


def test_run_emits_progress_and_writes_run(tmp_path, fake_cc):
    # The exact product code must exist in the latest assignments/locations
    # fixtures; pick one from data/processed/assign_*/assignments.csv.
    orders = [_fake_order("SO-1", "REPLACE_WITH_REAL_SKU")]
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter(orders),
    )
    events: list[ProgressEvent] = []
    settings = WaveRunSettings(repo_root=_ROOT, out_dir=tmp_path / "waves")
    result = run_wave_generation(settings, events.append)

    assert result.status in {"success", "empty"}
    assert [e.stage for e in events][:1] == ["pull"]
    assert any(e.stage == "done" for e in events)
    # the run folder exists with a manifest
    assert (result.out_dir / "manifest.json").exists()


def test_run_with_no_orders_is_empty(tmp_path, fake_cc):
    fake_cc.setattr(
        "wave_runner.search_outbound_orders",
        lambda client, **kw: iter([]),
    )
    events: list[ProgressEvent] = []
    settings = WaveRunSettings(repo_root=_ROOT, out_dir=tmp_path / "waves")
    result = run_wave_generation(settings, events.append)
    assert result.status == "empty"
    assert (result.out_dir / "index.md").exists()
```

> **Note for implementer:** replace `"REPLACE_WITH_REAL_SKU"` with an actual `product_code` present in both the latest `data/processed/assign_*/assignments.csv` and the dims fixture, so the order resolves to a location instead of being skipped. Run `head data/processed/assign_*/assignments.csv` to pick one. If no assignments fixture exists in the test environment, assert `result.status in {"success", "empty"}` and that the run folder is written (the no-location path still produces a valid empty/partial run + manifest).

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_wave_runner.py -k "emits_progress or no_orders" -v`
Expected: FAIL with `ImportError: cannot import name 'run_wave_generation'`.

- [ ] **Step 3: Implement run_wave_generation**

Add to `src/wave_runner.py`. This is the body of the old `main()` with `print(...)` replaced by `progress(ProgressEvent(...))`, the argparse removed, and settings/paths resolved from `WaveRunSettings`:

```python
def run_wave_generation(
    settings: WaveRunSettings,
    progress: ProgressCallback,
) -> RunResult:
    """Run the full wave pick pipeline once. Read-only against CC."""
    repo_root = settings.repo_root
    raw_dir = settings.raw_dir or repo_root / "data" / "raw"
    out_base = settings.out_dir or repo_root / "data" / "processed" / "waves"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_base / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    def emit(stage, message, level="info", **data):
        progress(ProgressEvent(stage=stage, message=message, level=level, data=data))

    try:
        _load_dotenv(repo_root / ".env")
        flatten_fn = _get_flatten_fn(repo_root)
        statuses = [s.strip() for s in settings.status.split(",") if s.strip()]

        # 1. live SO pull
        emit("pull", f"pulling SOs with status {statuses} from CC…")
        client = CartonCloudClient.from_env()
        audit_path = raw_dir / f"so_lines_open_{stamp}.parquet"
        so_lines = _pull_open_orders(
            client, status=statuses, customer_name=settings.customer_name,
            out_path=audit_path, flatten_fn=flatten_fn,
        )
        if so_lines.empty:
            (out_dir / "index.md").write_text(
                f"# Wave Pick Run\n_{datetime.now():%Y-%m-%d %H:%M}_\n\n"
                f"No orders matched status `{settings.status}` "
                f"(customer={settings.customer_name!r}).\n"
            )
            summary = {"n_waves": 0, "n_orders_total": 0,
                       "n_orders_skipped": 0, "n_pick_lines_total": 0}
            (out_dir / "manifest.json").write_text(json.dumps(
                {"generated_at": datetime.now().isoformat(),
                 "settings": _settings_dict(settings, audit_path, None),
                 "summary": summary, "waves": []}, indent=2))
            emit("done", "No open orders to wave.", level="ok", **summary)
            return RunResult(stamp, out_dir, summary, "empty")
        emit("pull", f"pulled {so_lines['so_id'].nunique()} orders → "
                     f"{len(so_lines)} lines", level="ok")

        # 2. snapshot
        snap = _build_snapshot(so_lines, raw_dir)
        emit("snapshot", "snapshot built (live SO + latest PO/products)", level="ok")

        # 3. dims
        dim_path = settings.dims_path or _latest_file(
            repo_root / "data" / "dims", "dims_*.xlsx")
        if not dim_path or not dim_path.exists():
            raise FileNotFoundError("no dim file in data/dims/")
        dims = load_dimensions(dim_path)
        emit("dims", f"dims {int(dims['measurement_complete'].sum())}/"
                     f"{len(dims)} SKUs measured", level="ok")

        # 4. routing
        rules_path = settings.rules_path or _latest_file(
            repo_root / "data" / "routing", "consignee_rules*.csv")
        rules = load_consignee_rules(rules_path)
        raw_vel = compute_velocity(snap)
        apply_tags(raw_vel.sku_metrics, dims)
        full_pallet = run_full_pallet_analysis(
            snap, dims, raw_vel.sku_metrics, ratio=settings.pallet_ratio)
        metrics = compute_order_metrics(snap, dims, full_pallet)
        emit("route", f"{metrics.n_orders:,} orders "
                      f"({metrics.n_orders_with_dims} full dim coverage)", level="ok")

        # 5. classify
        classification = classify_streams(
            metrics, rules,
            pallet_fraction_threshold=settings.pallet_fraction_threshold)
        emit("classify", "streams classified: " + ", ".join(
            f"{k}={int(v)}" for k, v in classification.counts_by_stream.items()),
            level="ok")

        # 6. locations
        loc_path = settings.locations_path or _latest_file(
            repo_root / "data" / "locations", "*.xlsx")
        if not loc_path or not loc_path.exists():
            raise FileNotFoundError("no locations xlsx in data/locations/")
        locations = load_cc_locations(loc_path)
        emit("locations", f"loaded locations from {loc_path.name}", level="ok")

        # 7. assignments
        assignments_df = None
        assignments_path = settings.assignments_path or _latest_assignments(
            repo_root / "data" / "processed")
        if assignments_path and assignments_path.exists():
            assignments_df = pd.read_csv(assignments_path)
            emit("assignments", f"{len(assignments_df)} SKU assignments", level="ok")
        else:
            emit("assignments", "no assignments file found — orders without "
                                "a known location will be skipped", level="info")

        # 8. SOH fallback (optional, off by default)
        fallback_df = None
        if settings.soh_fallback:
            emit("assignments", "pulling SKU→location fallback via SOH…")
            codes = sorted({c for c in so_lines["product_code"].dropna().unique()})
            soh_customer_id = (so_lines.iloc[0]["customer_id"]
                               if "customer_id" in so_lines.columns else None)
            if soh_customer_id:
                try:
                    items = get_sku_locations(
                        client, customer_id=soh_customer_id, product_codes=codes)
                    if items:
                        fallback_df = pd.DataFrame(items).rename(
                            columns={"location_name": "location"})
                        emit("assignments",
                             f"SOH gave {len(fallback_df)} (SKU, location) rows",
                             level="ok")
                except CartonCloudError as exc:
                    emit("assignments", f"SOH fallback failed: {exc}", level="info")

        # 9. wave generation
        emit("generate", "generating wave pick sheets…")
        result = generate_wave_pick_sheets(
            classification=classification, so_lines=snap.so_lines,
            locations=locations, assignments=assignments_df,
            sku_locations_fallback=fallback_df,
            run_group_col=settings.run_group_col,
            early_release_cartons=settings.early_release_cartons)
        emit("generate",
             f"{result.summary['n_waves']} waves, "
             f"{result.summary['n_orders_total']} orders, "
             f"{result.summary['n_orders_skipped']} skipped", level="ok")

        # 10. write outputs
        logo_path = (settings.logo_path
                     if settings.logo_path and Path(settings.logo_path).exists()
                     else None)
        for sheet in result.sheets:
            wave_dir = out_dir / sheet.wave_id
            wave_dir.mkdir(parents=True, exist_ok=True)
            try:
                generate_wave_pdf(
                    sheet, wave_dir / f"{sheet.wave_id}_picksheet.pdf",
                    logo_path=logo_path, lines_per_hour=settings.lines_per_hour)
            except Exception as exc:  # noqa: BLE001
                emit("write", f"PDF failed for {sheet.wave_id}: "
                              f"{type(exc).__name__}: {exc}", level="info")
                continue
            write_wave_csvs(sheet, wave_dir)

        if not result.skipped_orders.empty:
            result.skipped_orders.to_csv(out_dir / "skipped_orders.csv", index=False)

        # 11. index + manifest
        _build_index_md(out_dir, result.sheets, result.skipped_orders,
                        _settings_dict(settings, audit_path, assignments_path))
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "settings": _settings_dict(settings, audit_path, assignments_path),
            "summary": result.summary,
            "waves": [
                {"wave_id": s.wave_id, "stream": s.stream,
                 "run_group": s.run_group,
                 "receive_date": s.receive_date.isoformat() if s.receive_date else None,
                 "total_cartons": s.total_cartons, "total_lines": s.total_lines,
                 "n_orders": len(s.orders),
                 "estimated_walk_m": s.estimated_walk_distance_m}
                for s in result.sheets],
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        emit("done", f"Done — {result.summary['n_waves']} waves written.",
             level="ok", **result.summary)
        return RunResult(stamp, out_dir, result.summary, "success")

    except Exception as exc:  # noqa: BLE001
        log.exception("wave generation failed")
        emit("done", f"Run failed: {type(exc).__name__}: {exc}", level="error")
        return RunResult(stamp, out_dir, {}, "failed", error=str(exc))
```

Add the `_settings_dict` helper and update `_build_index_md`'s signature to take a settings dict instead of an argparse `Namespace`:

```python
def _settings_dict(settings, audit_path, assignments_path):
    return {
        "status": settings.status,
        "customer_name": settings.customer_name,
        "pallet_fraction_threshold": settings.pallet_fraction_threshold,
        "early_release_cartons": settings.early_release_cartons,
        "run_group_col": settings.run_group_col,
        "lines_per_hour": settings.lines_per_hour,
        "soh_fallback": settings.soh_fallback,
        "assignments_path": str(assignments_path) if assignments_path else None,
        "audit_parquet": str(audit_path),
    }
```

In `_build_index_md`, change the parameter from `args: argparse.Namespace` to `cfg: dict` and replace `args.status` → `cfg["status"]`, `args.customer_name` → `cfg["customer_name"]`, `args.pallet_fraction_threshold` → `cfg["pallet_fraction_threshold"]`, `args.early_release_cartons` → `cfg["early_release_cartons"]`, `args.run_group_col` → `cfg["run_group_col"]`, `args.lines_per_hour` → `cfg["lines_per_hour"]`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_wave_runner.py -v`
Expected: PASS. (If the SKU/assignments fixture isn't present, the `success`/`empty` assertion still holds and the manifest is written.)

- [ ] **Step 5: Commit**

```bash
git add src/wave_runner.py tests/test_wave_runner.py
git commit -m "feat: run_wave_generation shared pipeline core with progress events"
```

---

## Task 4: Refactor the CLI to a thin wrapper

**Files:**
- Modify: `scripts/generate_waves.py`
- Test: `tests/test_wave_runner.py`

- [ ] **Step 1: Write the CLI regression test**

Add to `tests/test_wave_runner.py`:

```python
def test_cli_main_builds_settings_and_runs(tmp_path, monkeypatch):
    """The CLI wrapper delegates to run_wave_generation with parsed flags."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_gen_waves", _ROOT / "scripts" / "generate_waves.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    captured = {}

    def fake_run(settings, progress):
        captured["settings"] = settings
        progress(__import__("wave_runner").ProgressEvent("done", "ok", "ok"))
        return __import__("wave_runner").RunResult(
            "stamp", tmp_path, {"n_waves": 0}, "empty")

    monkeypatch.setattr(mod, "run_wave_generation", fake_run)
    monkeypatch.setattr(
        sys := __import__("sys"), "argv",
        ["generate_waves.py", "--early-release-cartons", "25",
         "--pallet-fraction-threshold", "0.65"])
    rc = mod.main()
    assert rc == 0
    assert captured["settings"].early_release_cartons == 25
    assert captured["settings"].pallet_fraction_threshold == 0.65
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_wave_runner.py -k cli_main -v`
Expected: FAIL — the current `main()` doesn't import `run_wave_generation` and still does everything inline.

- [ ] **Step 3: Rewrite scripts/generate_waves.py main() as a thin wrapper**

Replace the body of `scripts/generate_waves.py` so it keeps the argparse surface but delegates. Keep the module docstring and the `sys.path.insert` for `src`. The new content below the docstring:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wave_runner import (  # noqa: E402
    ProgressEvent,
    WaveRunSettings,
    run_wave_generation,
)


def _print_progress(event: ProgressEvent) -> None:
    prefix = {"ok": "  + ", "error": "  ! ", "info": ""}.get(event.level, "")
    print(f"{prefix}{event.message}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", type=str, default=None)
    p.add_argument("--customer-name", type=str, default=None)
    p.add_argument("--raw", type=Path, default=None)
    p.add_argument("--locations", type=Path, default=None)
    p.add_argument("--dims", type=Path, default=None)
    p.add_argument("--rules", type=Path, default=None)
    p.add_argument("--assignments", type=Path, default=None)
    p.add_argument("--soh-fallback", action="store_true")
    p.add_argument("--pallet-ratio", type=float, default=0.9)
    p.add_argument("--pallet-fraction-threshold", type=float, default=None)
    p.add_argument("--early-release-cartons", type=int, default=None)
    p.add_argument("--run-group-col", type=str, default=None)
    p.add_argument("--logo", type=Path,
                   default=repo_root / "assests" / "gocold_logo.png")
    p.add_argument("--lines-per-hour", type=int, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    # Build settings, letting WaveRunSettings defaults fill any None flag.
    kw = dict(repo_root=repo_root)
    if args.status is not None: kw["status"] = args.status
    if args.customer_name is not None: kw["customer_name"] = args.customer_name
    if args.pallet_fraction_threshold is not None:
        kw["pallet_fraction_threshold"] = args.pallet_fraction_threshold
    if args.early_release_cartons is not None:
        kw["early_release_cartons"] = args.early_release_cartons
    if args.run_group_col is not None: kw["run_group_col"] = args.run_group_col
    if args.lines_per_hour is not None: kw["lines_per_hour"] = args.lines_per_hour
    kw["soh_fallback"] = args.soh_fallback
    kw["pallet_ratio"] = args.pallet_ratio
    kw["raw_dir"] = args.raw
    kw["dims_path"] = args.dims
    kw["locations_path"] = args.locations
    kw["rules_path"] = args.rules
    kw["assignments_path"] = args.assignments
    kw["logo_path"] = args.logo
    kw["out_dir"] = args.out
    settings = WaveRunSettings(**kw)

    result = run_wave_generation(settings, _print_progress)
    if result.status == "failed":
        print(f"\nFAILED: {result.error}", file=sys.stderr)
        return 1
    print(f"\nOK. open {result.out_dir / 'index.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the regression test + full suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests, including the CLI wrapper test and pre-existing tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_waves.py tests/test_wave_runner.py
git commit -m "refactor: generate_waves CLI delegates to wave_runner (behaviour unchanged)"
```

---

## Task 5: JobManager

**Files:**
- Create: `src/web/__init__.py` (empty)
- Create: `src/web/jobs.py`
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_jobs.py`:

```python
"""Tests for the single-run JobManager (src/web/jobs.py)."""
from __future__ import annotations

import time
from pathlib import Path

from web.jobs import JobManager
from wave_runner import ProgressEvent, RunResult, WaveRunSettings


def _fake_pipeline(events, status="success"):
    def run(settings, progress):
        for e in events:
            progress(e)
        return RunResult("stamp", Path("/tmp/run"), {"n_waves": len(events)}, status)
    return run


def _wait(mgr, run_id, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if mgr.get(run_id).done:
            return
        time.sleep(0.01)
    raise AssertionError("job did not finish in time")


def test_start_runs_and_buffers_events(tmp_path):
    events = [ProgressEvent("pull", "pulling"), ProgressEvent("done", "ok", "ok")]
    mgr = JobManager(runner=_fake_pipeline(events))
    run_id = mgr.start(WaveRunSettings(repo_root=tmp_path))
    _wait(mgr, run_id)
    job = mgr.get(run_id)
    assert job.status == "success"
    assert [e.stage for e in job.events] == ["pull", "done"]


def test_second_start_while_active_is_rejected(tmp_path):
    def slow(settings, progress):
        time.sleep(0.3)
        progress(ProgressEvent("done", "ok", "ok"))
        return RunResult("s", Path("/tmp"), {}, "success")
    mgr = JobManager(runner=slow)
    first = mgr.start(WaveRunSettings(repo_root=tmp_path))
    try:
        mgr.start(WaveRunSettings(repo_root=tmp_path))
        assert False, "expected RunInProgressError"
    except mgr.RunInProgressError:
        pass
    _wait(mgr, first)


def test_failed_pipeline_is_captured_not_raised(tmp_path):
    def boom(settings, progress):
        raise RuntimeError("kaboom")
    mgr = JobManager(runner=boom)
    run_id = mgr.start(WaveRunSettings(repo_root=tmp_path))
    _wait(mgr, run_id)
    job = mgr.get(run_id)
    assert job.status == "failed"
    assert "kaboom" in (job.error or "")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web'`.

- [ ] **Step 3: Create the package marker and JobManager**

Create empty `src/web/__init__.py`.

Create `src/web/jobs.py`:

```python
"""In-process, single-run job manager for wave generation.

One run at a time — the console serves a single operator, and a live CC
pull is heavy. A second start while a run is active is rejected so a
double-click can't fire two pulls. The pipeline is blocking (sync httpx +
pandas), so it runs in a worker thread; progress events are buffered for
the SSE endpoint to drain.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from wave_runner import (
    ProgressEvent,
    RunResult,
    WaveRunSettings,
    run_wave_generation,
)

Runner = Callable[[WaveRunSettings, Callable[[ProgressEvent], None]], RunResult]


@dataclass
class Job:
    job_id: str
    status: str = "running"          # running / success / empty / failed
    events: list = field(default_factory=list)
    result: RunResult | None = None
    error: str | None = None
    done: bool = False
    run_id: str | None = None        # the on-disk run folder name, once known


class JobManager:
    class RunInProgressError(RuntimeError):
        """Raised when a run is already active."""

    def __init__(self, runner: Runner = run_wave_generation):
        self._runner = runner
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None

    def start(self, settings: WaveRunSettings) -> str:
        with self._lock:
            if self._active is not None:
                raise self.RunInProgressError("a wave run is already in progress")
            job_id = uuid.uuid4().hex[:12]
            self._jobs[job_id] = Job(job_id=job_id)
            self._active = job_id
        threading.Thread(
            target=self._run, args=(job_id, settings), daemon=True,
        ).start()
        return job_id

    def _run(self, job_id: str, settings: WaveRunSettings) -> None:
        job = self._jobs[job_id]

        def progress(event: ProgressEvent) -> None:
            job.events.append(event)

        try:
            result = self._runner(settings, progress)
            job.result = result
            job.status = result.status
            job.run_id = result.run_id
            job.error = result.error
        except Exception as exc:  # noqa: BLE001 — never crash the worker
            job.status = "failed"
            job.error = str(exc)
            job.events.append(
                ProgressEvent("done", f"Run failed: {exc}", "error"))
        finally:
            job.done = True
            with self._lock:
                self._active = None

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    @property
    def active(self) -> bool:
        return self._active is not None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_jobs.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/web/__init__.py src/web/jobs.py tests/test_jobs.py
git commit -m "feat: single-run JobManager with progress buffering"
```

---

## Task 6: Disk readers (runs.py)

**Files:**
- Create: `src/web/runs.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write the failing tests with a fixture run folder**

Create `tests/test_web.py`:

```python
"""Tests for the web layer (disk readers + FastAPI routes)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _make_run(base: Path, run_id: str) -> Path:
    run = base / run_id
    (run / "VIC-bench-01").mkdir(parents=True)
    manifest = {
        "generated_at": "2026-06-04T08:12:00",
        "settings": {"status": "AWAITING_PICK_AND_PACK", "customer_name": None,
                     "pallet_fraction_threshold": 0.65, "early_release_cartons": 25,
                     "run_group_col": "delivery_state", "lines_per_hour": 60,
                     "soh_fallback": False},
        "summary": {"n_waves": 1, "n_orders_total": 22, "n_orders_skipped": 1,
                    "n_pick_lines_total": 3},
        "waves": [{"wave_id": "VIC-bench-01", "stream": "3_wave_bench",
                   "run_group": "VIC", "receive_date": None, "total_cartons": 45,
                   "total_lines": 3, "n_orders": 22, "estimated_walk_m": 240.0}],
    }
    (run / "manifest.json").write_text(json.dumps(manifest))
    pd.DataFrame([
        {"walk_index": 1, "location": "A-01-1-1", "product_code": "FRG-0042",
         "product_name": "Oats", "qty_cartons": 14, "cartons_running_total": 14,
         "contributing_so_refs": "SO-1"},
    ]).to_csv(run / "VIC-bench-01" / "VIC-bench-01_picks.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-1", "customer_name": "Forage", "delivery_state": "VIC",
         "cartons": 14, "lines": 1},
    ]).to_csv(run / "VIC-bench-01" / "VIC-bench-01_orders.csv", index=False)
    pd.DataFrame([
        {"wave_id": "VIC-bench-01", "so_ref": "SO-9",
         "reason": "missing pick location for SKU(s)", "missing_skus": "FRG-9"},
    ]).to_csv(run / "skipped_orders.csv", index=False)
    return run


def test_list_runs_newest_first(tmp_path):
    from web.runs import list_runs
    _make_run(tmp_path, "20260603_080000")
    _make_run(tmp_path, "20260604_081200")
    runs = list_runs(tmp_path)
    assert [r["run_id"] for r in runs] == ["20260604_081200", "20260603_080000"]
    assert runs[0]["n_waves"] == 1


def test_get_run_includes_waves_and_skipped(tmp_path):
    from web.runs import get_run
    _make_run(tmp_path, "20260604_081200")
    run = get_run(tmp_path, "20260604_081200")
    assert run["summary"]["n_orders_total"] == 22
    assert run["waves"][0]["wave_id"] == "VIC-bench-01"
    assert run["skipped"][0]["so_ref"] == "SO-9"


def test_get_wave_reads_pick_and_order_csvs(tmp_path):
    from web.runs import get_wave
    _make_run(tmp_path, "20260604_081200")
    wave = get_wave(tmp_path, "20260604_081200", "VIC-bench-01")
    assert wave["pick_lines"][0]["location"] == "A-01-1-1"
    assert wave["orders"][0]["so_ref"] == "SO-1"


def test_file_path_rejects_traversal(tmp_path):
    from web.runs import file_path
    _make_run(tmp_path, "20260604_081200")
    with pytest.raises(ValueError):
        file_path(tmp_path, "20260604_081200", "VIC-bench-01", "../../secret")
    good = file_path(tmp_path, "20260604_081200", "VIC-bench-01",
                     "VIC-bench-01_picks.csv")
    assert good.exists()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_web.py -k "list_runs or get_run or get_wave or file_path" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web.runs'`.

- [ ] **Step 3: Create src/web/runs.py**

```python
"""Read wave run outputs from disk for the console viewer.

The run folder is the source of truth — manifest.json carries the
summary + per-wave stats, and per-wave CSVs carry the detail. No state
is held between requests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _waves_base(repo_root: Path) -> Path:
    return repo_root / "data" / "processed" / "waves"


def list_runs(base: Path) -> list[dict]:
    """Newest-first list of run summaries. ``base`` is the waves dir."""
    runs = []
    if not base.exists():
        return runs
    for run_dir in sorted(base.iterdir(), reverse=True):
        manifest = run_dir / "manifest.json"
        if not run_dir.is_dir() or not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        s = m.get("summary", {})
        runs.append({
            "run_id": run_dir.name,
            "generated_at": m.get("generated_at", ""),
            "n_waves": s.get("n_waves", 0),
            "n_orders": s.get("n_orders_total", 0),
            "n_skipped": s.get("n_orders_skipped", 0),
            "settings": m.get("settings", {}),
        })
    return runs


def get_run(base: Path, run_id: str) -> dict:
    """Full manifest for one run + parsed skipped_orders."""
    run_dir = base / run_id
    m = json.loads((run_dir / "manifest.json").read_text())
    skipped = []
    skipped_csv = run_dir / "skipped_orders.csv"
    if skipped_csv.exists():
        skipped = pd.read_csv(skipped_csv).fillna("").to_dict("records")
    m["run_id"] = run_id
    m["skipped"] = skipped
    return m


def get_wave(base: Path, run_id: str, wave_id: str) -> dict:
    """Pick lines + orders for one wave, read from its CSVs."""
    wave_dir = base / run_id / wave_id
    picks_csv = wave_dir / f"{wave_id}_picks.csv"
    orders_csv = wave_dir / f"{wave_id}_orders.csv"
    picks = (pd.read_csv(picks_csv).fillna("").to_dict("records")
             if picks_csv.exists() else [])
    orders = (pd.read_csv(orders_csv).fillna("").to_dict("records")
              if orders_csv.exists() else [])
    return {"run_id": run_id, "wave_id": wave_id,
            "pick_lines": picks, "orders": orders}


def file_path(base: Path, run_id: str, wave_id: str, name: str) -> Path:
    """Validated path to a downloadable wave file (guards traversal)."""
    wave_dir = (base / run_id / wave_id).resolve()
    target = (wave_dir / name).resolve()
    if not str(target).startswith(str(wave_dir) + "/"):
        raise ValueError("path traversal rejected")
    if not target.exists():
        raise FileNotFoundError(name)
    return target
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_web.py -k "list_runs or get_run or get_wave or file_path" -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/web/runs.py tests/test_web.py
git commit -m "feat: disk readers for run/wave/file viewing"
```

---

## Task 7: FastAPI app + console page (GET /)

**Files:**
- Create: `src/web/app.py`
- Create: `src/web/templates/base.html`, `index.html`
- Create: `src/web/static/app.css`, `htmx.min.js`, `sse.js`
- Test: `tests/test_web.py`

- [ ] **Step 1: Vendor HTMX + SSE extension**

Run:
```bash
curl -sL https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js -o src/web/static/htmx.min.js
curl -sL https://unpkg.com/htmx-ext-sse@2.2.2/sse.js -o src/web/static/sse.js
```
Expected: two non-empty JS files. Verify: `wc -c src/web/static/htmx.min.js` > 40000.

- [ ] **Step 2: Write the failing route test**

Add to `tests/test_web.py`:

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import web.app as appmod
    app = appmod.create_app(repo_root=tmp_path)
    return TestClient(app)


def test_index_renders_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Wave Pick Console" in r.text
    assert "AWAITING_PICK_AND_PACK" in r.text
    assert 'name="pallet_fraction_threshold"' in r.text


def test_index_lists_existing_runs(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/")
    assert "20260604_081200" in r.text
```

- [ ] **Step 3: Create base.html**

`src/web/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Go Cold · Wave Pick Console</title>
  <link rel="stylesheet" href="/static/app.css">
  <script src="/static/htmx.min.js"></script>
  <script src="/static/sse.js"></script>
</head>
<body>
  <header class="bar">
    <span class="dot"></span>
    <strong>Go Cold</strong> · Wave Pick Console
    <span class="bar-right">Forage · read-only against CartonCloud</span>
  </header>
  <main class="wrap">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 4: Create index.html**

`src/web/templates/index.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="grid">
  <section class="card">
    <h4>New wave run</h4>
    <form hx-post="/runs" hx-target="#progress" hx-swap="innerHTML">
      <label>Status
        <input class="in" name="status" value="AWAITING_PICK_AND_PACK">
      </label>
      <label>Customer (optional)
        <input class="in" name="customer_name" placeholder="The Forage Company">
      </label>
      <label>Pallet fraction threshold
        <input class="in" name="pallet_fraction_threshold" type="number"
               step="0.01" value="0.70">
      </label>
      <label>Early release cartons
        <input class="in" name="early_release_cartons" type="number" value="30">
      </label>
      <label>Run group
        <select class="in" name="run_group_col">
          <option value="delivery_state">delivery_state</option>
          <option value="delivery_postcode">delivery_postcode</option>
        </select>
      </label>
      <button class="btn" type="submit">⚡ Generate waves</button>
    </form>
  </section>
  <div>
    <section class="card mb">
      <h4>Live progress</h4>
      <div id="progress"><p class="muted">No run in progress.</p></div>
    </section>
    <section class="card">
      <h4>Recent runs</h4>
      <table class="tbl">
        <tr><th>Run</th><th>Waves</th><th>Orders</th><th>Skipped</th><th></th></tr>
        {% for run in runs %}
        <tr>
          <td>{{ run.run_id }}</td><td>{{ run.n_waves }}</td>
          <td>{{ run.n_orders }}</td><td>{{ run.n_skipped }}</td>
          <td><a href="/runs/{{ run.run_id }}">View →</a></td>
        </tr>
        {% else %}
        <tr><td colspan="5" class="muted">No runs yet.</td></tr>
        {% endfor %}
      </table>
    </section>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Create app.css**

`src/web/static/app.css` — palette from the spec (blue header, green action, yellow accents):

```css
:root{
  --blue:#1a7fd4; --green:#22b573; --yellow:#ffd23f; --ink:#0f2d4a;
  --line:#e2e8ee; --muted:#6b7a87; --bg:#f4f7f9;
}
*{box-sizing:border-box}
body{margin:0;font-family:ui-sans-serif,system-ui,sans-serif;background:var(--bg);color:var(--ink)}
.bar{background:var(--blue);color:#eaf4ff;padding:12px 20px;display:flex;align-items:center;gap:10px;font-weight:600}
.bar .dot{width:10px;height:10px;border-radius:50%;background:var(--yellow)}
.bar-right{margin-left:auto;font-weight:400;font-size:12px;opacity:.9}
.wrap{max-width:1100px;margin:20px auto;padding:0 16px}
.grid{display:grid;grid-template-columns:320px 1fr;gap:16px}
.card{border:1px solid var(--line);border-radius:8px;padding:14px;background:#fff}
.card h4{margin:0 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.mb{margin-bottom:14px}
label{display:block;font-size:11px;color:var(--muted);margin-bottom:10px}
.in{display:block;width:100%;margin-top:3px;border:1px solid #cdd7df;border-radius:5px;padding:7px 9px;font-size:13px;background:#f8fafb}
.btn{background:var(--green);color:#fff;border:0;border-radius:6px;padding:10px 14px;font-weight:700;font-size:13px;width:100%;cursor:pointer;box-shadow:0 1px 0 #1c9c62}
.btn.sec{background:#eaf4ff;color:var(--blue);box-shadow:none;border:1px solid #cfe2f7;width:auto;margin-right:8px}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.tbl th{text-align:left;color:var(--muted);font-weight:600;border-bottom:2px solid var(--line);padding:7px 8px;font-size:11px;text-transform:uppercase}
.tbl td{border-bottom:1px solid #eef2f5;padding:7px 8px}
.tbl a{color:var(--blue);text-decoration:none;font-weight:600}
.muted{color:var(--muted)}
.log{font-family:ui-monospace,monospace;font-size:12px;line-height:1.7;background:var(--ink);color:#dbeaf8;border-radius:8px;padding:12px 14px}
.log .ok{color:var(--green)} .log .run{color:var(--yellow)} .log .error{color:#ff8f8f}
.cards{display:flex;gap:10px;margin-bottom:14px}
.stat{flex:1;border:1px solid var(--line);border-top:3px solid var(--green);border-radius:8px;padding:10px 12px}
.stat:nth-child(2){border-top-color:var(--blue)} .stat:nth-child(3){border-top-color:var(--yellow)} .stat:nth-child(4){border-top-color:#e0867a}
.stat .n{font-size:22px;font-weight:700} .stat .l{font-size:11px;color:var(--muted);text-transform:uppercase}
.pill{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600}
.pill.bench{background:#e7f0ff;color:var(--blue)} .pill.bypass{background:#fff6da;color:#b07d12} .pill.warn{background:#fdecec;color:#c0392b}
.crumb{font-size:12px;color:var(--muted);margin-bottom:12px}
.crumb a{color:var(--blue);text-decoration:none}
```

- [ ] **Step 6: Create app.py with the factory + index route**

`src/web/app.py`:

```python
"""FastAPI app for the wave pick console.

Server-rendered (Jinja2) + HTMX + SSE. One process, no build step.
``create_app(repo_root)`` is a factory so tests can point it at a tmp dir.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wave_runner import _load_dotenv
from . import runs as runs_mod
from .jobs import JobManager

_HERE = Path(__file__).resolve().parent


def create_app(repo_root: Path | None = None) -> FastAPI:
    repo_root = repo_root or _HERE.parent.parent
    waves_base = repo_root / "data" / "processed" / "waves"
    _load_dotenv(repo_root / ".env")

    app = FastAPI(title="Go Cold Wave Pick Console")
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    templates = Jinja2Templates(directory=str(_HERE / "templates"))
    manager = JobManager()
    app.state.repo_root = repo_root
    app.state.waves_base = waves_base
    app.state.manager = manager
    app.state.templates = templates

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "runs": runs_mod.list_runs(waves_base),
        })

    return app


app = create_app()
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_web.py -k "index" -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Commit**

```bash
git add src/web/app.py src/web/templates/base.html src/web/templates/index.html \
        src/web/static/app.css src/web/static/htmx.min.js src/web/static/sse.js \
        tests/test_web.py
git commit -m "feat: FastAPI app factory + console page with run history"
```

---

## Task 8: POST /runs + SSE progress stream

**Files:**
- Modify: `src/web/app.py`
- Create: `src/web/templates/_progress.html`, `_run_busy.html`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_web.py`:

```python
def test_post_runs_starts_job_and_returns_progress_panel(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import web.app as appmod
    from wave_runner import RunResult, ProgressEvent

    def fake_run(settings, progress):
        progress(ProgressEvent("pull", "pulling", "info"))
        progress(ProgressEvent("done", "done", "ok"))
        return RunResult("20260604_081200", tmp_path, {"n_waves": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake_run
    client = TestClient(app)
    r = client.post("/runs", data={
        "status": "AWAITING_PICK_AND_PACK", "customer_name": "",
        "pallet_fraction_threshold": "0.65", "early_release_cartons": "25",
        "run_group_col": "delivery_state"})
    assert r.status_code == 200
    assert "sse" in r.text.lower()           # the panel wires up an SSE source
    assert "/stream" in r.text


def test_post_runs_rejects_when_active(tmp_path):
    from fastapi.testclient import TestClient
    import web.app as appmod
    import time
    from wave_runner import RunResult, ProgressEvent

    def slow(settings, progress):
        time.sleep(0.3)
        return RunResult("s", tmp_path, {}, "success")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = slow
    client = TestClient(app)
    form = {"status": "X", "customer_name": "", "pallet_fraction_threshold": "0.7",
            "early_release_cartons": "30", "run_group_col": "delivery_state"}
    client.post("/runs", data=form)
    r2 = client.post("/runs", data=form)
    assert "in progress" in r2.text.lower()


def test_stream_emits_events(tmp_path):
    from fastapi.testclient import TestClient
    import web.app as appmod
    from wave_runner import RunResult, ProgressEvent

    def fake_run(settings, progress):
        progress(ProgressEvent("pull", "pulling orders", "info"))
        progress(ProgressEvent("done", "all done", "ok"))
        return RunResult("r", tmp_path, {"n_waves": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake_run
    client = TestClient(app)
    form = {"status": "X", "customer_name": "", "pallet_fraction_threshold": "0.7",
            "early_release_cartons": "30", "run_group_col": "delivery_state"}
    job_id = client.post("/runs", data=form).headers["x-job-id"]
    with client.stream("GET", f"/runs/job/{job_id}/stream") as s:
        body = "".join(chunk for chunk in s.iter_text())
    assert "pulling orders" in body
    assert "event: done" in body
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_web.py -k "post_runs or stream_emits" -v`
Expected: FAIL (route doesn't exist → 404/405).

- [ ] **Step 3: Create the progress partials**

`src/web/templates/_progress.html` — wires HTMX SSE to the stream, swaps each line in:

```html
<div hx-ext="sse" sse-connect="/runs/job/{{ job_id }}/stream" sse-swap="message"
     hx-target="#log" hx-swap="beforeend">
  <div id="log" class="log"></div>
  <div sse-swap="done" hx-swap="beforeend" hx-target="#after"></div>
  <div id="after"></div>
</div>
```

`src/web/templates/_run_busy.html`:

```html
<p class="pill warn">A wave run is already in progress.</p>
<p class="muted">Wait for it to finish before starting another.</p>
```

- [ ] **Step 4: Add the routes to app.py**

Add imports and routes inside `create_app` (after the index route). Add to the top imports:

```python
import json
import time
from fastapi import Form
from fastapi.responses import StreamingResponse
from wave_runner import WaveRunSettings
```

Routes:

```python
    @app.post("/runs", response_class=HTMLResponse)
    def start_run(
        request: Request,
        status: str = Form("AWAITING_PICK_AND_PACK"),
        customer_name: str = Form(""),
        pallet_fraction_threshold: float = Form(0.70),
        early_release_cartons: int = Form(30),
        run_group_col: str = Form("delivery_state"),
    ):
        settings = WaveRunSettings(
            repo_root=repo_root, status=status,
            customer_name=customer_name or None,
            pallet_fraction_threshold=pallet_fraction_threshold,
            early_release_cartons=early_release_cartons,
            run_group_col=run_group_col)
        try:
            job_id = manager.start(settings)
        except JobManager.RunInProgressError:
            return templates.TemplateResponse("_run_busy.html", {"request": request})
        resp = templates.TemplateResponse(
            "_progress.html", {"request": request, "job_id": job_id})
        resp.headers["x-job-id"] = job_id
        return resp

    @app.get("/runs/job/{job_id}/stream")
    def stream(job_id: str):
        def gen():
            sent = 0
            while True:
                job = manager.get(job_id)
                while sent < len(job.events):
                    e = job.events[sent]; sent += 1
                    cls = {"ok": "ok", "error": "error", "info": "run"}.get(e.level, "")
                    html = f'<div class="{cls}">{e.message}</div>'
                    if e.stage == "done":
                        link = (f'<a href="/runs/{job.run_id}">View run →</a>'
                                if job.run_id and job.status != "failed" else "")
                        yield (f"event: done\ndata: <div class='{cls}'>"
                               f"{e.message}</div> {link}\n\n")
                    else:
                        yield f"event: message\ndata: {html}\n\n"
                if job.done and sent >= len(job.events):
                    break
                time.sleep(0.1)
        return StreamingResponse(gen(), media_type="text/event-stream")
```

> **SSE format note:** each event is `event: <name>\ndata: <payload>\n\n`. The data payload here is a one-line HTML fragment HTMX swaps into `#log` (for `message`) or `#after` (for `done`). Keep each `data:` on a single line — newlines inside the payload break the SSE frame.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_web.py -k "post_runs or stream_emits" -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/web/app.py src/web/templates/_progress.html src/web/templates/_run_busy.html tests/test_web.py
git commit -m "feat: POST /runs + SSE progress stream"
```

---

## Task 9: Run detail + wave detail + downloads

**Files:**
- Modify: `src/web/app.py`
- Create: `src/web/templates/run_detail.html`, `wave_detail.html`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_web.py`:

```python
def test_run_detail_page(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200")
    assert r.status_code == 200
    assert "VIC-bench-01" in r.text
    assert "bench" in r.text                 # stream pill
    assert "SO-9" in r.text                   # skipped order


def test_wave_detail_page(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200/waves/VIC-bench-01")
    assert r.status_code == 200
    assert "A-01-1-1" in r.text               # pick line location
    assert "FRG-0042" in r.text


def test_download_picks_csv(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200/files/VIC-bench-01/VIC-bench-01_picks.csv")
    assert r.status_code == 200
    assert "A-01-1-1" in r.text


def test_download_traversal_404(tmp_path, client):
    base = tmp_path / "data" / "processed" / "waves"
    _make_run(base, "20260604_081200")
    r = client.get("/runs/20260604_081200/files/VIC-bench-01/..%2f..%2fmanifest.json")
    assert r.status_code == 404
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_web.py -k "run_detail or wave_detail or download" -v`
Expected: FAIL (routes 404).

- [ ] **Step 3: Create run_detail.html**

`src/web/templates/run_detail.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="crumb"><a href="/">← Console</a> / Run {{ run.run_id }}</div>
<div class="cards">
  <div class="stat"><div class="n">{{ run.summary.n_waves }}</div><div class="l">Waves</div></div>
  <div class="stat"><div class="n">{{ run.summary.n_orders_total }}</div><div class="l">Orders</div></div>
  <div class="stat"><div class="n">{{ run.summary.n_pick_lines_total }}</div><div class="l">Pick lines</div></div>
  <div class="stat"><div class="n">{{ run.summary.n_orders_skipped }}</div><div class="l">Skipped</div></div>
</div>
<section class="card mb">
  <table class="tbl">
    <tr><th>Wave</th><th>Stream</th><th>Run group</th><th>Orders</th><th>Lines</th>
        <th>Cartons</th><th>Walk</th><th>Files</th></tr>
    {% for w in run.waves %}
    {% set kind = "bench" if "bench" in w.stream else "bypass" %}
    <tr>
      <td><a href="/runs/{{ run.run_id }}/waves/{{ w.wave_id }}">{{ w.wave_id }}</a></td>
      <td><span class="pill {{ kind }}">{{ kind }}</span></td>
      <td>{{ w.run_group }}</td><td>{{ w.n_orders }}</td><td>{{ w.total_lines }}</td>
      <td>{{ w.total_cartons }}</td><td>{{ w.estimated_walk_m }} m</td>
      <td>
        <a href="/runs/{{ run.run_id }}/files/{{ w.wave_id }}/{{ w.wave_id }}_picksheet.pdf">PDF</a> ·
        <a href="/runs/{{ run.run_id }}/files/{{ w.wave_id }}/{{ w.wave_id }}_picks.csv">picks</a> ·
        <a href="/runs/{{ run.run_id }}/files/{{ w.wave_id }}/{{ w.wave_id }}_orders.csv">orders</a>
      </td>
    </tr>
    {% endfor %}
  </table>
</section>
{% if run.skipped %}
<section class="card">
  <h4><span class="pill warn">{{ run.skipped|length }} skipped</span> orders — missing pick location</h4>
  <table class="tbl">
    <tr><th>SO ref</th><th>Reason</th><th>Missing SKUs</th></tr>
    {% for s in run.skipped %}
    <tr><td>{{ s.so_ref }}</td><td>{{ s.reason }}</td><td>{{ s.missing_skus }}</td></tr>
    {% endfor %}
  </table>
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Create wave_detail.html**

`src/web/templates/wave_detail.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="crumb">
  <a href="/">← Console</a> / <a href="/runs/{{ wave.run_id }}">Run {{ wave.run_id }}</a>
  / {{ wave.wave_id }}
</div>
<div class="mb">
  <a class="btn sec" href="/runs/{{ wave.run_id }}/files/{{ wave.wave_id }}/{{ wave.wave_id }}_picksheet.pdf">⬇ PDF pick sheet</a>
  <a class="btn sec" href="/runs/{{ wave.run_id }}/files/{{ wave.wave_id }}/{{ wave.wave_id }}_picks.csv">⬇ picks.csv</a>
  <a class="btn sec" href="/runs/{{ wave.run_id }}/files/{{ wave.wave_id }}/{{ wave.wave_id }}_orders.csv">⬇ orders.csv</a>
</div>
<section class="card">
  <table class="tbl">
    <tr><th>Walk #</th><th>Location</th><th>SKU</th><th>Product</th><th>Qty</th>
        <th>Run tot</th><th>Contributing SOs</th></tr>
    {% for p in wave.pick_lines %}
    <tr>
      <td>{{ p.walk_index }}</td><td>{{ p.location }}</td><td>{{ p.product_code }}</td>
      <td>{{ p.product_name }}</td><td>{{ p.qty_cartons }}</td>
      <td>{{ p.cartons_running_total }}</td><td>{{ p.contributing_so_refs }}</td>
    </tr>
    {% endfor %}
  </table>
</section>
{% endblock %}
```

- [ ] **Step 5: Add the routes to app.py**

Add inside `create_app` (after the stream route). Add `from fastapi.responses import FileResponse` and `from fastapi import HTTPException` to imports.

```python
    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(request: Request, run_id: str):
        try:
            run = runs_mod.get_run(waves_base, run_id)
        except (FileNotFoundError, OSError):
            raise HTTPException(status_code=404, detail="run not found")
        return templates.TemplateResponse(
            "run_detail.html", {"request": request, "run": run})

    @app.get("/runs/{run_id}/waves/{wave_id}", response_class=HTMLResponse)
    def wave_detail(request: Request, run_id: str, wave_id: str):
        wave = runs_mod.get_wave(waves_base, run_id, wave_id)
        return templates.TemplateResponse(
            "wave_detail.html", {"request": request, "wave": wave})

    @app.get("/runs/{run_id}/files/{wave_id}/{name}")
    def download(run_id: str, wave_id: str, name: str):
        try:
            path = runs_mod.file_path(waves_base, run_id, wave_id, name)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(path, filename=name)
```

> **Route order note:** define `/runs/{run_id}/waves/{wave_id}` and `/runs/{run_id}/files/...` — these don't collide with `/runs/job/{job_id}/stream` because `job` is a literal segment FastAPI matches before the `{run_id}` param only if declared first. Declare the `/runs/job/...` stream route **before** `/runs/{run_id}` to be safe.

- [ ] **Step 6: Reorder routes**

Ensure in `app.py` the route definition order is: `/`, `/runs` (POST), `/runs/job/{job_id}/stream`, then `/runs/{run_id}`, `/runs/{run_id}/waves/{wave_id}`, `/runs/{run_id}/files/{wave_id}/{name}`. Move the stream route above `run_detail` if needed.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_web.py -v`
Expected: PASS (all web tests).

- [ ] **Step 8: Commit**

```bash
git add src/web/app.py src/web/templates/run_detail.html src/web/templates/wave_detail.html tests/test_web.py
git commit -m "feat: run detail, wave detail, and file downloads"
```

---

## Task 10: Launcher + README + full-suite green

**Files:**
- Create: `scripts/serve_web.py`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Create the uvicorn launcher**

`scripts/serve_web.py`:

```python
#!/usr/bin/env python3
"""Launch the Go Cold wave pick console.

    python scripts/serve_web.py            # http://127.0.0.1:8000
    python scripts/serve_web.py --host 0.0.0.0 --port 8080

Binds 127.0.0.1 by default (single-operator NUC). Read-only against CC.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import uvicorn  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    uvicorn.run("web.app:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test the launcher boots**

Run: `python -c "import sys; sys.path.insert(0,'src'); import web.app; print(type(web.app.app).__name__)"`
Expected: prints `FastAPI`.

- [ ] **Step 3: Add .gitignore entry for the brainstorm dir**

Append to `.gitignore` (if not already present):

```
.superpowers/
```

- [ ] **Step 4: Document the console in README.md**

Add a section to `README.md` under the existing usage docs:

```markdown
## Wave Pick Console (web UI)

A local web console wrapping `scripts/generate_waves.py`. Trigger a live
wave generation run, watch progress stream, and browse/download the
resulting waves.

```bash
python scripts/serve_web.py     # then open http://127.0.0.1:8000
```

Read-only against CartonCloud — it generates paperwork only. Settings
exposed: status, customer, pallet-fraction-threshold, early-release-cartons,
run-group. One run at a time. The CLI (`scripts/generate_waves.py`) still
works unchanged and shares the same pipeline core (`src/wave_runner.py`).
```

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS — all new tests plus the pre-existing `test_dim_loader`, `test_read_only_guard`, `test_wave_consolidation`, `test_weight_estimate`.

- [ ] **Step 6: Manual smoke test (optional, needs live .env)**

Run: `python scripts/serve_web.py` then open `http://127.0.0.1:8000`, click **Generate waves**, confirm the progress log streams and a run appears in history. Stop with Ctrl-C.

- [ ] **Step 7: Commit**

```bash
git add scripts/serve_web.py README.md .gitignore
git commit -m "feat: serve_web launcher + console docs"
```

---

## Self-Review Notes (addressed)

- **Spec coverage:** every spec section maps to a task — shared core/refactor (Tasks 1–4), JobManager single-run + threading (Task 5), disk readers (Task 6), console + form + history (Task 7), live trigger + SSE (Task 8), run/wave detail + downloads (Task 9), launcher/docs/deps (Tasks 1, 10). Error handling (run-active, failure capture, empty run, traversal/404) is covered by tests in Tasks 5, 8, 9.
- **Type consistency:** `WaveRunSettings`, `ProgressEvent(stage,message,level,data)`, `RunResult(run_id,out_dir,summary,status,error)`, `Job(...status/events/done/run_id/error)`, and `JobManager.RunInProgressError` are used consistently across runner, jobs, and app.
- **Read-only / safety:** no `write_enabled` is ever set; generation only writes local paperwork; `127.0.0.1` default bind; SOH fallback stays off (not exposed in the form).
- **CLI regression** is locked by `test_cli_main_builds_settings_and_runs` (Task 4).
