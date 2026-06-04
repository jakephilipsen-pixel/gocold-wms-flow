# Dispatch Dashboard (runs.rolodex-ai.com) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dispatcher-facing web console at runs.rolodex-ai.com that triggers the dispatch run-prediction pipeline with live progress and browses the predicted runs, review queue, and per-run manifests — read-only against CartonCloud.

**Architecture:** A new self-contained FastAPI app `src/web_dispatch/` mirroring the live `src/web/` picks console (Jinja2 + HTMX + SSE, one process). A shared build core `src/dispatch/runner.py` (extracted from `scripts/build_dispatch.py`) is called by both the CLI and the web job manager. CartonCloud is never mutated; a future write-back lives behind the existing `CartonCloudSink` seam.

**Tech Stack:** Python 3.11+ (venv is 3.14), FastAPI, uvicorn, Jinja2, HTMX, pandas, openpyxl. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-05-dispatch-dashboard-design.md`

---

## Conventions for every task

- **Run tests with `.venv/bin/python -m pytest`** — the venv bin wrappers have a stale shebang, so always invoke `python -m`, never bare `pytest`/`python`.
- `src/` is on `sys.path` via `tests/conftest.py`, so tests import bare package names (`from dispatch.runner import ...`, `from web_dispatch.app import create_app`).
- House style: Australian English (normalise, behaviour), production-ready, no placeholders, READ-ONLY (never set `write_enabled`).
- Commit messages end with the trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- Baseline before starting: full suite is green at **96 tests**.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/dispatch/runner.py` (create) | `DispatchRunSettings`, `DispatchProgressEvent`, `DispatchRunResult`, `run_dispatch` (moved), `run_dispatch_job` |
| `scripts/build_dispatch.py` (rewrite) | Thin CLI delegating to `run_dispatch_job` |
| `tests/test_build_dispatch.py` (rewrite) | Re-point integration test at `dispatch.runner.run_dispatch` |
| `tests/test_dispatch_runner.py` (create) | `run_dispatch_job` events + write + status |
| `src/web_dispatch/__init__.py` (create) | package marker |
| `src/web_dispatch/plans.py` (create) | Disk reader: `list_plans`, `get_plan`, `get_run`, `file_path` |
| `tests/test_dispatch_plans.py` (create) | Disk-reader tests |
| `src/web_dispatch/jobs.py` (create) | `JobManager` (copied/retyped from `web/jobs.py`) |
| `src/web_dispatch/app.py` (create) | `create_app` factory + routes |
| `src/web_dispatch/static/{app.css,htmx.min.js,sse.js}` (copy) | assets from picks |
| `src/web_dispatch/templates/{base,index,_progress,_run_busy,plan_detail,run_detail}.html` (create) | views |
| `scripts/serve_web_dispatch.py` (create) | uvicorn launcher on :8078 |
| `tests/test_web_dispatch.py` (create) | route/integration tests |
| `docs/dispatch-dashboard-deploy.md` (create) | tunnel + systemd checklist |
| `CLAUDE.md` (modify) | record the new capability |

Dependency order: 1 (runner) → 2 (plans reader) → 3 (app skeleton: index/build/stream) → 4 (plan/run detail + download) → 5 (launcher + deploy doc + docs + full suite).

---

## Task 1: Shared build core `dispatch/runner.py` + thin CLI

Extract the orchestration from `scripts/build_dispatch.py` into a reusable, progress-emitting core in the `dispatch` package (mirrors the `generate_waves → wave_runner` precedent). `run_dispatch` moves verbatim into the package; `run_dispatch_job` wraps it with events + a `FileSink` write + a result. The CLI becomes thin. The existing integration test re-points to the new location.

**Files:**
- Create: `src/dispatch/runner.py`
- Rewrite: `scripts/build_dispatch.py`
- Rewrite: `tests/test_build_dispatch.py`
- Test: `tests/test_dispatch_runner.py`

- [ ] **Step 1: Write the new runner test**

Create `tests/test_dispatch_runner.py`:

```python
"""run_dispatch_job: emits progress, writes a stamped plan, reports status."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from dispatch import runner as mod
from dispatch.runner import DispatchRunSettings, run_dispatch_job

ROOT = Path(__file__).resolve().parent.parent

_CONSIGNMENTS = [
    {"details": {"deliver": {"address": {"lines": ["1 A St"],
     "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}},
     "runsheet": {"name": "RS-1", "date": "2026-06-03"},
     "deliveryRun": {"name": "West-Tue"}}}
    for _ in range(3)
]
_OPEN_ORDERS = [
    {"id": "SO9", "references": {"customer": "SO-9"},
     "details": {"deliver": {"address": {"lines": ["1 A St"],
      "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}}}}
]


def _settings(tmp_path: Path) -> DispatchRunSettings:
    return DispatchRunSettings(
        repo_root=tmp_path, history_days=90, skip_learn=False,
        zones_path=ROOT / "config" / "dispatch_zones.toml")


def _patch(monkeypatch):
    monkeypatch.setattr(mod, "search_consignments",
                        lambda *a, **k: iter(_CONSIGNMENTS))
    monkeypatch.setattr(mod, "search_outbound_orders",
                        lambda *a, **k: iter(_OPEN_ORDERS))
    monkeypatch.setattr(mod.CartonCloudClient, "from_env",
                        staticmethod(lambda: object()))


def test_run_dispatch_job_writes_plan_and_emits(monkeypatch, tmp_path):
    _patch(monkeypatch)
    events = []
    result = run_dispatch_job(_settings(tmp_path), events.append,
                              as_of=date(2026, 6, 5))

    assert result.status == "success"
    assert result.counts["assignments"] == 1
    assert result.counts["runs"] == 1
    # a stamped plan dir was written with the suggested runs CSV
    base = tmp_path / "data" / "processed" / "dispatch"
    plan_dirs = list(base.iterdir())
    assert len(plan_dirs) == 1
    assert (plan_dirs[0] / "suggested_runs.csv").exists()
    # progress was reported, ending in a non-error done event
    stages = [e.stage for e in events]
    assert "predict" in stages and stages[-1] == "done"
    assert events[-1].level != "error"


def test_run_dispatch_job_dry_run_writes_nothing(monkeypatch, tmp_path):
    _patch(monkeypatch)
    result = run_dispatch_job(_settings(tmp_path), lambda e: None,
                              write=False, as_of=date(2026, 6, 5))
    assert result.out_dir is None
    assert not (tmp_path / "data" / "processed" / "dispatch").exists()
    assert result.counts["assignments"] == 1


def test_run_dispatch_job_no_orders_is_empty(monkeypatch, tmp_path):
    _patch(monkeypatch)
    monkeypatch.setattr(mod, "search_outbound_orders", lambda *a, **k: iter([]))
    result = run_dispatch_job(_settings(tmp_path), lambda e: None,
                              as_of=date(2026, 6, 5))
    assert result.status == "empty"
    assert result.counts["assignments"] == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch.runner'`.

- [ ] **Step 3: Create `src/dispatch/runner.py`**

```python
"""Dispatch run build core — learn → predict → write, with progress events.

READ-ONLY against CartonCloud. Shared by the CLI (scripts/build_dispatch.py)
and the web console (src/web_dispatch). Mirrors wave_runner: a settings
dataclass in, progress events + a result out. ``run_dispatch`` is the pure
learn-or-load-then-predict step; ``run_dispatch_job`` adds env loading, the
file write, progress reporting, and a structured result.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from cc_client import (
    CartonCloudClient,
    search_consignments,
    search_outbound_orders,
)

from .consignments import parse_consignment
from .history import compute_run_history, load_model, save_model
from .predict import DispatchPlan, predict_runs
from .sinks import FileSink
from .zones import load_zone_config

log = logging.getLogger(__name__)

DEFAULT_STATUS = ["AWAITING_PICK_AND_PACK", "PACKED"]


@dataclass
class DispatchRunSettings:
    """Everything ``run_dispatch_job`` needs for one build.

    ``repo_root`` anchors output (``data/processed/dispatch/<stamp>/``) and the
    model cache. ``zones_path`` / ``model_path`` override the repo-relative
    defaults (tests point ``zones_path`` at the real config while writing
    output to a tmp dir).
    """
    repo_root: Path
    history_days: int = 90
    skip_learn: bool = False
    zones_path: Path | None = None
    model_path: Path | None = None

    def resolved_zones_path(self) -> Path:
        return self.zones_path or self.repo_root / "config" / "dispatch_zones.toml"

    def resolved_model_path(self) -> Path:
        return (self.model_path
                or self.repo_root / "data" / "dispatch" / "run_history.parquet")


@dataclass
class DispatchProgressEvent:
    """One streamed progress line."""
    stage: str            # learn | predict | write | done
    message: str
    level: str = "info"   # info | ok | error
    data: dict = field(default_factory=dict)


@dataclass
class DispatchRunResult:
    """Outcome of a single ``run_dispatch_job`` call."""
    stamp: str
    out_dir: Path | None
    counts: dict          # assignments / carriers / review / runs
    status: str           # success | empty | failed
    error: str | None = None


ProgressCallback = Callable[[DispatchProgressEvent], None]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _open_order_stops(client) -> list[dict]:
    """Pull open orders and reduce to {so_id, so_ref, address}."""
    stops = []
    for o in search_outbound_orders(client, status=DEFAULT_STATUS):
        addr = ((o.get("details") or {}).get("deliver") or {}).get("address")
        stops.append({"so_id": o.get("id"),
                      "so_ref": (o.get("references") or {}).get("customer"),
                      "address": addr})
    return stops


def run_dispatch(*, client, zones_path: Path, history_days: int,
                 as_of: date | None = None, model_path: Path | None = None,
                 skip_learn: bool = False) -> DispatchPlan:
    """Learn (or load) the model, pull open orders, predict. Returns the plan."""
    as_of = as_of or date.today()
    if skip_learn and model_path and model_path.exists():
        model = load_model(model_path)
        log.info("loaded cached model from %s", model_path)
    else:
        cutoff = (as_of - timedelta(days=history_days)).isoformat()
        records = [parse_consignment(c)
                   for c in search_consignments(client, run_sheet_date_from=cutoff)]
        model = compute_run_history(records, as_of=as_of,
                                    window_days=history_days)
        if model_path:
            save_model(model, model_path)
            log.info("cached model → %s", model_path)

    zones = load_zone_config(zones_path)
    stops = _open_order_stops(client)
    return predict_runs(stops, model, zones, as_of=as_of)


def run_dispatch_job(
    settings: DispatchRunSettings,
    emit: ProgressCallback,
    *,
    write: bool = True,
    as_of: date | None = None,
) -> DispatchRunResult:
    """Full build: learn → predict → (optionally) write. READ-ONLY against CC.

    Emits coarse progress events and returns a structured result. ``write=False``
    is the CLI --dry-run path (no files). On error, emits an error ``done``
    event and returns ``status="failed"`` rather than raising, so a web worker
    can record it cleanly.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    counts = {"assignments": 0, "carriers": 0, "review": 0, "runs": 0}
    try:
        _load_dotenv(settings.repo_root / ".env")
        emit(DispatchProgressEvent(
            "learn",
            f"Building predictions from {settings.history_days}d of "
            f"consignment history…"))
        client = CartonCloudClient.from_env()       # write_enabled=False
        plan = run_dispatch(
            client=client,
            zones_path=settings.resolved_zones_path(),
            history_days=settings.history_days,
            model_path=settings.resolved_model_path(),
            skip_learn=settings.skip_learn,
            as_of=as_of)

        counts = {
            "assignments": len(plan.assignments),
            "carriers": sum(len(v) for v in plan.carriers.values()),
            "review": len(plan.review),
            "runs": len({a.predicted_run for a in plan.assignments}),
        }
        emit(DispatchProgressEvent(
            "predict",
            f"Predicted {counts['assignments']} stable across "
            f"{counts['runs']} runs · {counts['review']} review · "
            f"{counts['carriers']} carrier", "ok", counts))

        out_dir: Path | None = None
        if write:
            out_dir = (settings.repo_root / "data" / "processed" / "dispatch"
                       / stamp)
            FileSink(out_dir).apply(plan)
            emit(DispatchProgressEvent(
                "write", f"Wrote plan {stamp}", "ok", {"stamp": stamp}))

        status = ("success"
                  if any(counts[k] for k in ("assignments", "review", "carriers"))
                  else "empty")
        emit(DispatchProgressEvent(
            "done",
            f"Done — {counts['assignments']} assigned, "
            f"{counts['review']} to review", "ok", {"stamp": stamp}))
        return DispatchRunResult(stamp, out_dir, counts, status)
    except Exception as exc:  # noqa: BLE001 — report, don't crash the worker
        log.exception("dispatch build failed")
        emit(DispatchProgressEvent("done", f"Build failed: {exc}", "error"))
        return DispatchRunResult(stamp, None, counts, "failed", str(exc))
```

- [ ] **Step 4: Run the runner test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_runner.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Rewrite `scripts/build_dispatch.py` as a thin CLI**

Replace the entire file with:

```python
"""Build today's dispatch run predictions from CC consignment history.

READ-ONLY. learn → predict → write files. CartonCloud is never mutated.
Delegates to dispatch.runner.run_dispatch_job (shared with the web console).

    python3 scripts/build_dispatch.py                 # learn + predict + write
    python3 scripts/build_dispatch.py --skip-learn    # reuse cached model
    python3 scripts/build_dispatch.py --history-days 90
    python3 scripts/build_dispatch.py --dry-run       # summary only, no files
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dispatch.runner import (  # noqa: E402
    DispatchRunSettings,
    run_dispatch_job,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history-days", type=int, default=90)
    ap.add_argument("--skip-learn", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zones-config", type=Path, default=None)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    settings = DispatchRunSettings(
        repo_root=ROOT, history_days=args.history_days,
        skip_learn=args.skip_learn, zones_path=args.zones_config)

    def emit(e) -> None:
        print(f"[{e.level}] {e.message}")

    result = run_dispatch_job(settings, emit, write=not args.dry_run)
    print(f"status={result.status} assignments={result.counts['assignments']} "
          f"carriers={result.counts['carriers']} review={result.counts['review']}")
    if args.dry_run:
        print("(dry run — no files written)")
    elif result.out_dir is not None:
        print(f"wrote → {result.out_dir}")
    return 0 if result.status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Rewrite `tests/test_build_dispatch.py` to target `dispatch.runner`**

`run_dispatch` now lives in the package, so the integration test imports it from there (same fixtures and assertions, no script loading):

```python
"""Integration: run_dispatch builds a plan from fixture pulls (offline)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from dispatch import runner as mod
from dispatch.runner import run_dispatch

ROOT = Path(__file__).resolve().parent.parent

_CONSIGNMENTS = [
    {"details": {"deliver": {"address": {"lines": ["1 A St"],
     "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}},
     "runsheet": {"name": "RS-1", "date": "2026-06-03"},
     "deliveryRun": {"name": "West-Tue"}}}
    for _ in range(3)
]
_OPEN_ORDERS = [
    {"id": "SO9", "references": {"customer": "SO-9"},
     "details": {"deliver": {"address": {"lines": ["1 A St"],
      "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}}}}
]


def test_run_dispatch_builds_plan(monkeypatch):
    monkeypatch.setattr(mod, "search_consignments",
                        lambda *a, **k: iter(_CONSIGNMENTS))
    monkeypatch.setattr(mod, "search_outbound_orders",
                        lambda *a, **k: iter(_OPEN_ORDERS))

    plan = run_dispatch(
        client=object(),
        zones_path=ROOT / "config" / "dispatch_zones.toml",
        history_days=90, as_of=date(2026, 6, 5))

    assert len(plan.assignments) == 1
    assert plan.assignments[0].predicted_run == "West-Tue"
```

- [ ] **Step 7: Verify the whole suite + both scripts parse**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — **99 tests** (96 baseline; the rewritten `test_build_dispatch.py` keeps its single test, and `test_dispatch_runner.py` adds 3 → 96 + 3 = 99).
Run: `.venv/bin/python -c "import ast; ast.parse(open('scripts/build_dispatch.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 8: Commit**

```bash
git add src/dispatch/runner.py scripts/build_dispatch.py tests/test_build_dispatch.py tests/test_dispatch_runner.py
git commit -m "feat(dispatch): extract run core into dispatch.runner with progress events

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Plan disk reader `web_dispatch/plans.py`

Pure functions over a plan directory (`data/processed/dispatch/<stamp>/`). No held state — the stamped dir is the source of truth. Columns written by `dispatch/output.py`: `so_ref, so_id, predicted_run, confidence, flag, reason, alternatives, full_address, street, suburb, state, postcode`.

**Files:**
- Create: `src/web_dispatch/__init__.py`
- Create: `src/web_dispatch/plans.py`
- Test: `tests/test_dispatch_plans.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_plans.py`:

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

_COLS = ["so_ref", "so_id", "predicted_run", "confidence", "flag", "reason",
         "alternatives", "full_address", "street", "suburb", "state", "postcode"]


def _make_plan(base: Path, stamp: str) -> Path:
    d = base / stamp
    d.mkdir(parents=True)
    pd.DataFrame([
        {"so_ref": "SO-1", "so_id": "1", "predicted_run": "West-Tue",
         "confidence": 1.0, "flag": "stable", "reason": "r", "alternatives": "",
         "full_address": "1 A St, Scoresby VIC 3179", "street": "1 A St",
         "suburb": "Scoresby", "state": "VIC", "postcode": "3179"},
        {"so_ref": "SO-2", "so_id": "2", "predicted_run": "West-Tue",
         "confidence": 0.9, "flag": "stable", "reason": "r", "alternatives": "",
         "full_address": "2 B St, Scoresby VIC 3170", "street": "2 B St",
         "suburb": "Scoresby", "state": "VIC", "postcode": "3170"},
    ], columns=_COLS).to_csv(d / "suggested_runs.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-3", "so_id": "3", "predicted_run": "",
         "confidence": 0.0, "flag": "new_address",
         "reason": "no history; zone=Metro Melbourne", "alternatives": "",
         "full_address": "9 New Rd, Geelong VIC 3220", "street": "9 New Rd",
         "suburb": "Geelong", "state": "VIC", "postcode": "3220"},
    ], columns=_COLS).to_csv(d / "review.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-4", "so_id": "4", "predicted_run": "", "confidence": 1.0,
         "flag": "carrier", "reason": "carrier order (TollExpress)",
         "alternatives": "", "full_address": "x", "street": "x", "suburb": "x",
         "state": "VIC", "postcode": "3000"},
    ], columns=_COLS).to_csv(d / "carriers_TollExpress.csv", index=False)
    (d / "summary.md").write_text("# Dispatch run prediction summary\n")
    return d


def test_list_plans_newest_first_with_counts(tmp_path):
    from web_dispatch.plans import list_plans
    _make_plan(tmp_path, "20260604_080000")
    _make_plan(tmp_path, "20260605_093000")
    plans = list_plans(tmp_path)
    assert [p["stamp"] for p in plans] == ["20260605_093000", "20260604_080000"]
    p = plans[0]
    assert p["n_assignments"] == 2
    assert p["n_runs"] == 1
    assert p["n_review"] == 1
    assert p["n_carriers"] == 1
    assert p["generated_at"].startswith("2026-06-05")


def test_get_plan_groups_runs_and_lists_review(tmp_path):
    from web_dispatch.plans import get_plan
    _make_plan(tmp_path, "20260605_093000")
    plan = get_plan(tmp_path, "20260605_093000")
    assert plan["runs"][0]["run"] == "West-Tue"
    assert plan["runs"][0]["n_stops"] == 2
    assert 0.94 <= plan["runs"][0]["avg_confidence"] <= 0.96
    assert plan["review"][0]["flag"] == "new_address"
    assert "TollExpress" in plan["carriers"]
    assert "suggested_runs.csv" in plan["files"]
    assert plan["summary_md"].startswith("# Dispatch")


def test_get_run_filters_and_sorts_by_postcode(tmp_path):
    from web_dispatch.plans import get_run
    _make_plan(tmp_path, "20260605_093000")
    run = get_run(tmp_path, "20260605_093000", "West-Tue")
    assert [s["postcode"] for s in run["stops"]] == ["3170", "3179"]


def test_file_path_guards_traversal(tmp_path):
    from web_dispatch.plans import file_path
    _make_plan(tmp_path, "20260605_093000")
    with pytest.raises(ValueError):
        file_path(tmp_path, "20260605_093000", "../../secret")
    good = file_path(tmp_path, "20260605_093000", "suggested_runs.csv")
    assert good.exists()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_plans.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_dispatch'`.

- [ ] **Step 3: Create the package + reader**

Create `src/web_dispatch/__init__.py`:

```python
"""Go Cold dispatch run console — read-only web view over dispatch plans."""
```

Create `src/web_dispatch/plans.py`:

```python
"""Read dispatch plan outputs from disk for the console viewer.

A plan is one ``data/processed/dispatch/<stamp>/`` directory written by
dispatch.output.write_dispatch_plan. No state is held between requests — the
directory is the source of truth.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

_SUGGESTED = "suggested_runs.csv"
_REVIEW = "review.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a plan CSV as strings (keeps postcode/so_id intact). Empty on miss."""
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def _stamp_to_iso(stamp: str) -> str:
    try:
        return datetime.strptime(stamp, "%Y%m%d_%H%M%S").isoformat(
            sep=" ", timespec="minutes")
    except ValueError:
        return stamp


def _n_runs(df: pd.DataFrame) -> int:
    if df.empty or "predicted_run" not in df.columns:
        return 0
    return int(df["predicted_run"].replace("", pd.NA).dropna().nunique())


def list_plans(base: Path) -> list[dict]:
    """Newest-first list of plan summaries. ``base`` is the dispatch dir."""
    plans: list[dict] = []
    if not base.exists():
        return plans
    for d in sorted(base.iterdir(), reverse=True):
        if not d.is_dir() or not (d / _SUGGESTED).exists():
            continue
        suggested = _read_csv(d / _SUGGESTED)
        review = _read_csv(d / _REVIEW)
        n_carriers = sum(len(_read_csv(c))
                         for c in d.glob("carriers_*.csv"))
        plans.append({
            "stamp": d.name,
            "generated_at": _stamp_to_iso(d.name),
            "n_assignments": int(len(suggested)),
            "n_runs": _n_runs(suggested),
            "n_review": int(len(review)),
            "n_carriers": int(n_carriers),
        })
    return plans


def get_plan(base: Path, stamp: str) -> dict:
    """Parsed plan: runs (grouped), review rows, carriers, files, summary."""
    d = base / stamp
    if not d.is_dir() or not (d / _SUGGESTED).exists():
        raise FileNotFoundError(stamp)

    suggested = _read_csv(d / _SUGGESTED)
    runs: list[dict] = []
    if not suggested.empty and "predicted_run" in suggested.columns:
        conf = pd.to_numeric(suggested["confidence"], errors="coerce")
        suggested = suggested.assign(_conf=conf)
        for run, g in suggested.groupby("predicted_run", sort=True):
            runs.append({
                "run": run,
                "n_stops": int(len(g)),
                "avg_confidence": round(float(g["_conf"].mean()), 3),
            })

    review = _read_csv(d / _REVIEW).to_dict("records")

    carriers: dict[str, list[dict]] = {}
    for c in sorted(d.glob("carriers_*.csv")):
        name = c.stem[len("carriers_"):]
        carriers[name] = _read_csv(c).to_dict("records")

    summary_md = ""
    summary_path = d / "summary.md"
    if summary_path.exists():
        summary_md = summary_path.read_text()

    files = sorted(p.name for p in d.iterdir() if p.is_file())

    return {"stamp": stamp, "runs": runs, "review": review,
            "carriers": carriers, "files": files, "summary_md": summary_md}


def get_run(base: Path, stamp: str, run: str) -> dict:
    """Stops for one predicted run, sorted by postcode."""
    d = base / stamp
    suggested = _read_csv(d / _SUGGESTED)
    stops: list[dict] = []
    if not suggested.empty and "predicted_run" in suggested.columns:
        sel = suggested[suggested["predicted_run"] == run]
        sel = sel.sort_values("postcode")
        stops = sel.to_dict("records")
    return {"stamp": stamp, "run": run, "stops": stops}


def file_path(base: Path, stamp: str, name: str) -> Path:
    """Validated path to a downloadable plan file (guards traversal)."""
    plan_dir = (base / stamp).resolve()
    target = (plan_dir / name).resolve()
    if not str(target).startswith(str(plan_dir) + "/"):
        raise ValueError("path traversal rejected")
    if not target.exists():
        raise FileNotFoundError(name)
    return target
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_plans.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/web_dispatch/__init__.py src/web_dispatch/plans.py tests/test_dispatch_plans.py
git commit -m "feat(web_dispatch): plan disk reader (list/get plan, runs, downloads)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: App skeleton — index, build, SSE stream

Copy the picks job manager + static assets, write the app factory with the index page, the `POST /build` trigger, and the SSE progress stream. Defer plan/run detail to Task 4.

**Files:**
- Create: `src/web_dispatch/jobs.py`
- Create: `src/web_dispatch/app.py`
- Create: `src/web_dispatch/static/{app.css,htmx.min.js,sse.js}` (copied)
- Create: `src/web_dispatch/templates/{base,index,_progress,_run_busy}.html`
- Test: `tests/test_web_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_dispatch.py`:

```python
"""Tests for the dispatch console (routes + SSE)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_COLS = ["so_ref", "so_id", "predicted_run", "confidence", "flag", "reason",
         "alternatives", "full_address", "street", "suburb", "state", "postcode"]


def _make_plan(base: Path, stamp: str) -> Path:
    d = base / stamp
    d.mkdir(parents=True)
    pd.DataFrame([
        {"so_ref": "SO-1", "so_id": "1", "predicted_run": "West-Tue",
         "confidence": 1.0, "flag": "stable", "reason": "r", "alternatives": "",
         "full_address": "1 A St, Scoresby VIC 3179", "street": "1 A St",
         "suburb": "Scoresby", "state": "VIC", "postcode": "3179"},
    ], columns=_COLS).to_csv(d / "suggested_runs.csv", index=False)
    pd.DataFrame([
        {"so_ref": "SO-3", "so_id": "3", "predicted_run": "", "confidence": 0.0,
         "flag": "new_address", "reason": "no history; zone=Geelong",
         "alternatives": "", "full_address": "9 New Rd, Geelong VIC 3220",
         "street": "9 New Rd", "suburb": "Geelong", "state": "VIC",
         "postcode": "3220"},
    ], columns=_COLS).to_csv(d / "review.csv", index=False)
    (d / "summary.md").write_text("# Dispatch run prediction summary\n")
    (d / "run_West-Tue.xlsx").write_bytes(b"PK\x03\x04stub")
    return d


def _client(tmp_path):
    from fastapi.testclient import TestClient
    import web_dispatch.app as appmod
    return appmod, TestClient(appmod.create_app(repo_root=tmp_path))


def test_index_renders_build_form(tmp_path):
    _, client = _client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "Dispatch Run Console" in r.text
    assert 'name="history_days"' in r.text
    assert 'name="skip_learn"' in r.text


def test_index_lists_plans_with_review_count(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/")
    assert "20260605_093000" in r.text


def test_post_build_starts_job_and_returns_progress(tmp_path):
    from dispatch.runner import DispatchRunResult
    appmod, _ = _client(tmp_path)

    def fake(settings, emit, **kw):
        from dispatch.runner import DispatchProgressEvent
        emit(DispatchProgressEvent("learn", "learning"))
        emit(DispatchProgressEvent("done", "done", "ok", {"stamp": "S1"}))
        return DispatchRunResult("S1", tmp_path, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake
    from fastapi.testclient import TestClient
    client = TestClient(app)
    r = client.post("/build", data={"history_days": "90"})
    assert r.status_code == 200
    assert "sse" in r.text.lower()
    assert "/build/job/" in r.text and "/stream" in r.text


def test_post_build_passes_skip_learn(tmp_path):
    from dispatch.runner import DispatchRunResult
    import time
    appmod, _ = _client(tmp_path)
    captured: dict = {}

    def fake(settings, emit, **kw):
        captured["skip_learn"] = settings.skip_learn
        captured["history_days"] = settings.history_days
        return DispatchRunResult("S", None, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake
    from fastapi.testclient import TestClient
    client = TestClient(app)

    def _wait(job_id):
        for _ in range(200):
            if app.state.manager.get(job_id).done:
                return
            time.sleep(0.01)
        raise AssertionError("job did not finish")

    jid = client.post("/build", data={"history_days": "45",
                                      "skip_learn": "true"}).headers["x-job-id"]
    _wait(jid)
    assert captured["skip_learn"] is True
    assert captured["history_days"] == 45

    captured.clear()
    jid = client.post("/build", data={"history_days": "90"}).headers["x-job-id"]
    _wait(jid)
    assert captured["skip_learn"] is False


def test_post_build_rejects_when_active(tmp_path):
    from dispatch.runner import DispatchRunResult
    import time
    appmod, _ = _client(tmp_path)

    def slow(settings, emit, **kw):
        time.sleep(0.3)
        return DispatchRunResult("S", tmp_path, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = slow
    from fastapi.testclient import TestClient
    client = TestClient(app)
    client.post("/build", data={"history_days": "90"})
    r2 = client.post("/build", data={"history_days": "90"})
    assert "in progress" in r2.text.lower()


def test_stream_emits_events_with_plan_link(tmp_path):
    from dispatch.runner import DispatchRunResult, DispatchProgressEvent
    appmod, _ = _client(tmp_path)

    def fake(settings, emit, **kw):
        emit(DispatchProgressEvent("learn", "learning"))
        emit(DispatchProgressEvent("done", "all done", "ok", {"stamp": "S1"}))
        return DispatchRunResult("S1", tmp_path, {"assignments": 0}, "empty")

    app = appmod.create_app(repo_root=tmp_path)
    app.state.manager._runner = fake
    from fastapi.testclient import TestClient
    client = TestClient(app)
    job_id = client.post("/build", data={"history_days": "90"}).headers["x-job-id"]
    with client.stream("GET", f"/build/job/{job_id}/stream") as s:
        body = "".join(chunk for chunk in s.iter_text())
    assert "learning" in body
    assert "event: done" in body
    assert "/plans/S1" in body
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_web_dispatch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'web_dispatch.app'`.

- [ ] **Step 3: Copy the static assets**

```bash
mkdir -p src/web_dispatch/static src/web_dispatch/templates
cp src/web/static/app.css src/web_dispatch/static/app.css
cp src/web/static/htmx.min.js src/web_dispatch/static/htmx.min.js
cp src/web/static/sse.js src/web_dispatch/static/sse.js
```

- [ ] **Step 4: Create `src/web_dispatch/jobs.py`**

Copied from `web/jobs.py`, retyped against the dispatch runner. `Job.stamp`
replaces `Job.run_id`.

```python
"""In-process, single-build job manager for the dispatch console.

One build at a time — the console serves a single dispatcher and a live CC
pull is heavy. A second start while a build is active is rejected so a
double-click can't fire two pulls. The build is blocking (sync httpx +
pandas), so it runs in a worker thread; progress events are buffered for the
SSE endpoint to drain.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from dispatch.runner import (
    DispatchProgressEvent,
    DispatchRunResult,
    DispatchRunSettings,
    run_dispatch_job,
)

Runner = Callable[
    [DispatchRunSettings, Callable[[DispatchProgressEvent], None]],
    DispatchRunResult,
]


@dataclass
class Job:
    job_id: str
    status: str = "running"          # running / success / empty / failed
    events: list = field(default_factory=list)
    result: DispatchRunResult | None = None
    error: str | None = None
    done: bool = False
    stamp: str | None = None         # the on-disk plan folder name, once known


class JobManager:
    class RunInProgressError(RuntimeError):
        """Raised when a build is already active."""

    def __init__(self, runner: Runner = run_dispatch_job):
        self._runner = runner
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None

    def start(self, settings: DispatchRunSettings) -> str:
        with self._lock:
            if self._active is not None:
                raise self.RunInProgressError("a dispatch build is already in progress")
            job_id = uuid.uuid4().hex[:12]
            self._jobs[job_id] = Job(job_id=job_id)
            self._active = job_id
        threading.Thread(
            target=self._run, args=(job_id, settings), daemon=True,
        ).start()
        return job_id

    def _run(self, job_id: str, settings: DispatchRunSettings) -> None:
        job = self._jobs[job_id]

        def progress(event: DispatchProgressEvent) -> None:
            job.events.append(event)

        try:
            result = self._runner(settings, progress)
            job.result = result
            job.status = result.status
            job.stamp = result.stamp
            job.error = result.error
        except Exception as exc:  # noqa: BLE001 — never crash the worker
            job.status = "failed"
            job.error = str(exc)
            job.events.append(
                DispatchProgressEvent("done", f"Build failed: {exc}", "error"))
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

- [ ] **Step 5: Create `src/web_dispatch/app.py` (index + build + stream only)**

```python
"""FastAPI app for the dispatch run console.

Server-rendered (Jinja2) + HTMX + SSE. One process, no build step.
``create_app(repo_root)`` is a factory so tests can point it at a tmp dir.
READ-ONLY against CartonCloud.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dispatch.runner import DispatchRunSettings
from . import plans as plans_mod
from .jobs import JobManager

_HERE = Path(__file__).resolve().parent


def create_app(repo_root: Path | None = None) -> FastAPI:
    repo_root = repo_root or _HERE.parent.parent
    dispatch_base = repo_root / "data" / "processed" / "dispatch"

    app = FastAPI(title="Go Cold Dispatch Run Console")
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    templates = Jinja2Templates(directory=str(_HERE / "templates"))
    manager = JobManager()
    app.state.repo_root = repo_root
    app.state.dispatch_base = dispatch_base
    app.state.manager = manager
    app.state.templates = templates

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {
            "plans": plans_mod.list_plans(dispatch_base),
        })

    @app.post("/build", response_class=HTMLResponse)
    def start_build(
        request: Request,
        history_days: int = Form(90),
        skip_learn: bool = Form(False),
    ):
        settings = DispatchRunSettings(
            repo_root=repo_root, history_days=history_days,
            skip_learn=skip_learn)
        try:
            job_id = manager.start(settings)
        except JobManager.RunInProgressError:
            return templates.TemplateResponse(request, "_run_busy.html", {})
        resp = templates.TemplateResponse(
            request, "_progress.html", {"job_id": job_id})
        resp.headers["x-job-id"] = job_id
        return resp

    @app.get("/build/job/{job_id}/stream")
    def stream(job_id: str):
        def gen():
            sent = 0
            while True:
                job = manager.get(job_id)
                while sent < len(job.events):
                    e = job.events[sent]; sent += 1
                    cls = {"ok": "ok", "error": "error",
                           "info": "run"}.get(e.level, "")
                    html = f'<div class="{cls}">{e.message}</div>'
                    if e.stage == "done":
                        stamp = e.data.get("stamp") if e.data else None
                        link = (f'<a href="/plans/{stamp}">View plan →</a>'
                                if stamp and job.status != "failed" else "")
                        yield (f"event: done\ndata: <div class='{cls}'>"
                               f"{e.message}</div> {link}\n\n")
                    else:
                        yield f"event: message\ndata: {html}\n\n"
                if job.done and sent >= len(job.events):
                    break
                time.sleep(0.1)
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


app = create_app()
```

- [ ] **Step 6: Create the templates**

Create `src/web_dispatch/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Go Cold · Dispatch Run Console</title>
  <link rel="stylesheet" href="/static/app.css">
  <script src="/static/htmx.min.js"></script>
  <script src="/static/sse.js"></script>
</head>
<body>
  <header class="bar">
    <span class="dot"></span>
    <strong>Go Cold</strong> · Dispatch Run Console
    <span class="bar-right">Forage · predictions only — not written to CartonCloud</span>
  </header>
  <main class="wrap">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

Create `src/web_dispatch/templates/index.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="grid">
  <section class="card">
    <h4>New dispatch build</h4>
    <form hx-post="/build" hx-target="#progress" hx-swap="innerHTML">
      <label>History window (days)
        <input class="in" name="history_days" type="number" value="90">
      </label>
      <label class="check">
        <input type="checkbox" name="skip_learn" value="true">
        Reuse cached history model
        <small>Skips the consignment pull and reuses the last learned model.
        Faster, but won't pick up runs added since the last build.</small>
      </label>
      <button class="btn" type="submit">⚡ Build predictions</button>
    </form>
  </section>
  <div>
    <section class="card mb">
      <h4>Live progress</h4>
      <div id="progress"><p class="muted">No build in progress.</p></div>
    </section>
    <section class="card">
      <h4>Recent builds</h4>
      <table class="tbl">
        <tr><th>Plan</th><th>Runs</th><th>Assigned</th><th>Review</th>
            <th>Carriers</th><th></th></tr>
        {% for p in plans %}
        <tr>
          <td>{{ p.generated_at }}</td>
          <td>{{ p.n_runs }}</td>
          <td>{{ p.n_assignments }}</td>
          <td>{% if p.n_review %}<span class="pill warn">{{ p.n_review }}</span>
              {% else %}0{% endif %}</td>
          <td>{{ p.n_carriers }}</td>
          <td><a href="/plans/{{ p.stamp }}">View →</a></td>
        </tr>
        {% else %}
        <tr><td colspan="6" class="muted">No builds yet.</td></tr>
        {% endfor %}
      </table>
    </section>
  </div>
</div>
{% endblock %}
```

Create `src/web_dispatch/templates/_progress.html`:

```html
<div hx-ext="sse" sse-connect="/build/job/{{ job_id }}/stream" sse-swap="message"
     hx-target="#log" hx-swap="beforeend">
  <div id="log" class="log"></div>
  <div sse-swap="done" hx-swap="beforeend" hx-target="#after"></div>
  <div id="after"></div>
</div>
```

Create `src/web_dispatch/templates/_run_busy.html`:

```html
<p class="pill warn">A dispatch build is already in progress.</p>
<p class="muted">Wait for it to finish before starting another.</p>
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_web_dispatch.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Commit**

```bash
git add src/web_dispatch/jobs.py src/web_dispatch/app.py src/web_dispatch/static src/web_dispatch/templates tests/test_web_dispatch.py
git commit -m "feat(web_dispatch): app skeleton — index, build trigger, SSE progress

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Plan detail, run detail, download

Add the three viewing routes + templates. Extends the existing
`tests/test_web_dispatch.py` (the `_make_plan` helper is already there).

**Files:**
- Modify: `src/web_dispatch/app.py` (add three routes before `return app`)
- Create: `src/web_dispatch/templates/plan_detail.html`
- Create: `src/web_dispatch/templates/run_detail.html`
- Modify: `tests/test_web_dispatch.py` (append tests)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_web_dispatch.py`:

```python
def test_plan_detail_shows_runs_and_review(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000")
    assert r.status_code == 200
    assert "West-Tue" in r.text          # predicted run
    assert "new_address" in r.text       # review flag
    assert "Geelong" in r.text           # review reason/zone


def test_plan_detail_missing_404(tmp_path):
    _, client = _client(tmp_path)
    r = client.get("/plans/nope")
    assert r.status_code == 404


def test_run_detail_lists_stops(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000/runs/West-Tue")
    assert r.status_code == 200
    assert "1 A St" in r.text
    assert "Scoresby" in r.text


def test_download_suggested_csv(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000/files/suggested_runs.csv")
    assert r.status_code == 200
    assert "West-Tue" in r.text


def test_download_traversal_404(tmp_path):
    _, client = _client(tmp_path)
    base = tmp_path / "data" / "processed" / "dispatch"
    _make_plan(base, "20260605_093000")
    r = client.get("/plans/20260605_093000/files/..%2f..%2fsecret")
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `.venv/bin/python -m pytest tests/test_web_dispatch.py -k "plan_detail or run_detail or download" -v`
Expected: FAIL (routes return 404 / not found — `/plans/...` not defined).

- [ ] **Step 3: Add the routes**

In `src/web_dispatch/app.py`, insert these three routes immediately before
`return app`:

```python
    @app.get("/plans/{stamp}", response_class=HTMLResponse)
    def plan_detail(request: Request, stamp: str):
        try:
            plan = plans_mod.get_plan(dispatch_base, stamp)
        except (FileNotFoundError, OSError):
            raise HTTPException(status_code=404, detail="plan not found")
        return templates.TemplateResponse(
            request, "plan_detail.html", {"plan": plan})

    @app.get("/plans/{stamp}/runs/{run}", response_class=HTMLResponse)
    def run_detail(request: Request, stamp: str, run: str):
        data = plans_mod.get_run(dispatch_base, stamp, run)
        return templates.TemplateResponse(
            request, "run_detail.html", {"run": data})

    @app.get("/plans/{stamp}/files/{name}")
    def download(stamp: str, name: str):
        try:
            path = plans_mod.file_path(dispatch_base, stamp, name)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(path, filename=name)
```

- [ ] **Step 4: Create `src/web_dispatch/templates/plan_detail.html`**

```html
{% extends "base.html" %}
{% block content %}
<div class="crumb"><a href="/">← Console</a> / Plan {{ plan.stamp }}</div>
<div class="cards">
  <div class="stat"><div class="n">{{ plan.runs|sum(attribute='n_stops') }}</div><div class="l">Assigned</div></div>
  <div class="stat"><div class="n">{{ plan.runs|length }}</div><div class="l">Runs</div></div>
  <div class="stat"><div class="n">{{ plan.review|length }}</div><div class="l">Review</div></div>
  <div class="stat"><div class="n">{{ plan.carriers|length }}</div><div class="l">Carriers</div></div>
</div>

<section class="card mb">
  <h4>Predicted runs</h4>
  <table class="tbl">
    <tr><th>Run</th><th>Stops</th><th>Avg confidence</th><th>Files</th></tr>
    {% for r in plan.runs %}
    <tr>
      <td><a href="/plans/{{ plan.stamp }}/runs/{{ r.run }}">{{ r.run }}</a></td>
      <td>{{ r.n_stops }}</td>
      <td>{{ '%.0f' % (r.avg_confidence * 100) }}%</td>
      <td><a href="/plans/{{ plan.stamp }}/files/run_{{ r.run }}.xlsx">manifest</a></td>
    </tr>
    {% else %}
    <tr><td colspan="4" class="muted">No own-fleet assignments.</td></tr>
    {% endfor %}
  </table>
</section>

{% if plan.review %}
<section class="card mb">
  <h4><span class="pill warn">{{ plan.review|length }} review</span> — needs dispatcher attention</h4>
  <table class="tbl">
    <tr><th>SO ref</th><th>Flag</th><th>Best guess</th><th>Reason</th>
        <th>Address</th><th>Alternatives</th></tr>
    {% for s in plan.review %}
    <tr>
      <td>{{ s.so_ref }}</td>
      <td><span class="pill warn">{{ s.flag }}</span></td>
      <td>{{ s.predicted_run or '—' }}</td>
      <td>{{ s.reason }}</td>
      <td>{{ s.full_address }}</td>
      <td>{{ s.alternatives }}</td>
    </tr>
    {% endfor %}
  </table>
</section>
{% endif %}

{% if plan.carriers %}
<section class="card mb">
  <h4>Carrier orders</h4>
  {% for name, rows in plan.carriers.items() %}
  <p><strong>{{ name }}</strong> — {{ rows|length }} orders
    · <a href="/plans/{{ plan.stamp }}/files/carriers_{{ name }}.csv">CSV</a></p>
  {% endfor %}
</section>
{% endif %}

<section class="card">
  <h4>Downloads</h4>
  <p>
    <a href="/plans/{{ plan.stamp }}/files/suggested_runs.csv">suggested_runs.csv</a> ·
    <a href="/plans/{{ plan.stamp }}/files/review.csv">review.csv</a> ·
    <a href="/plans/{{ plan.stamp }}/files/summary.md">summary.md</a>
  </p>
</section>
{% endblock %}
```

- [ ] **Step 5: Create `src/web_dispatch/templates/run_detail.html`**

```html
{% extends "base.html" %}
{% block content %}
<div class="crumb">
  <a href="/">← Console</a> /
  <a href="/plans/{{ run.stamp }}">Plan {{ run.stamp }}</a> /
  Run {{ run.run }}
</div>
<section class="card">
  <h4>{{ run.run }} — {{ run.stops|length }} stops (postcode order)</h4>
  <table class="tbl">
    <tr><th>SO ref</th><th>Address</th><th>Suburb</th><th>Postcode</th>
        <th>Confidence</th><th>Reason</th></tr>
    {% for s in run.stops %}
    <tr>
      <td>{{ s.so_ref }}</td>
      <td>{{ s.full_address }}</td>
      <td>{{ s.suburb }}</td>
      <td>{{ s.postcode }}</td>
      <td>{{ s.confidence }}</td>
      <td>{{ s.reason }}</td>
    </tr>
    {% else %}
    <tr><td colspan="6" class="muted">No stops on this run.</td></tr>
    {% endfor %}
  </table>
</section>
{% endblock %}
```

- [ ] **Step 6: Run the full console test file**

Run: `.venv/bin/python -m pytest tests/test_web_dispatch.py -v`
Expected: PASS (11 tests).

- [ ] **Step 7: Commit**

```bash
git add src/web_dispatch/app.py src/web_dispatch/templates/plan_detail.html src/web_dispatch/templates/run_detail.html tests/test_web_dispatch.py
git commit -m "feat(web_dispatch): plan detail, run detail, file download

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Launcher, deploy checklist, docs, full-suite verification

**Files:**
- Create: `scripts/serve_web_dispatch.py`
- Create: `docs/dispatch-dashboard-deploy.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Create the launcher**

Create `scripts/serve_web_dispatch.py`:

```python
#!/usr/bin/env python3
"""Launch the Go Cold dispatch run console.

    python scripts/serve_web_dispatch.py            # http://127.0.0.1:8078
    python scripts/serve_web_dispatch.py --host 0.0.0.0 --port 8090

Binds 127.0.0.1 by default (single-operator). Read-only against CC.
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
    p.add_argument("--port", type=int, default=8078)
    args = p.parse_args()
    uvicorn.run("web_dispatch.app:app", host=args.host, port=args.port,
                reload=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the launcher parses and the app imports**

Run: `.venv/bin/python -c "import ast; ast.parse(open('scripts/serve_web_dispatch.py').read()); print('ok')"`
Expected: `ok`.
Run: `PYTHONPATH=src .venv/bin/python -c "from web_dispatch.app import create_app; create_app(); print('app ok')"`
Expected: `app ok`.

- [ ] **Step 3: Create the deploy checklist**

Create `docs/dispatch-dashboard-deploy.md`:

```markdown
# Dispatch Run Console — Deploy (runs.rolodex-ai.com)

Mirrors the wave-pick console deploy (`picks.rolodex-ai.com`). The console
serves a single dispatcher, read-only against CartonCloud, on the laptop
(data + `.env` CC creds live here).

## Process
- App: `scripts/serve_web_dispatch.py` → uvicorn `web_dispatch.app:app` on
  `127.0.0.1:8078`.
- Published at **https://runs.rolodex-ai.com** via a named Cloudflare Tunnel
  `wms-runs`, gated by Cloudflare Access (same one-time-PIN email allowlist
  as picks).

## Tunnel (run these via `!` — they trip the exposure classifier)
```
cloudflared tunnel create wms-runs
# write ~/.cloudflared/wms-runs.yml:
#   tunnel: <wms-runs-id>
#   credentials-file: /home/pop_os/.cloudflared/<wms-runs-id>.json
#   ingress:
#     - hostname: runs.rolodex-ai.com
#       service: http://127.0.0.1:8078
#     - service: http_status:404
cloudflared tunnel route dns wms-runs runs.rolodex-ai.com
```
Add `runs.rolodex-ai.com` to the existing Cloudflare Access application (or
clone the picks policy) so the email allowlist is enforced at the edge.

## systemd --user services
Create `~/.config/systemd/user/wms-runs-app.service` (ExecStart =
`/home/pop_os/archive/rolodex/gocold-wms-flow/.venv/bin/python
scripts/serve_web_dispatch.py`, WorkingDirectory = repo root) and
`wms-runs-tunnel.service` (`After=wms-runs-app.service`, ExecStart =
`cloudflared tunnel run wms-runs`). Then:
```
systemctl --user daemon-reload
systemctl --user enable --now wms-runs-app wms-runs-tunnel
```
Linger is already enabled for `pop_os`. After a Python change:
`systemctl --user restart wms-runs-app` (templates/CSS need no restart).

## Verify
- `curl -sI http://127.0.0.1:8078/` → 200.
- Unauthenticated `https://runs.rolodex-ai.com` → 302 to Cloudflare Access.
```

- [ ] **Step 4: Update `CLAUDE.md`**

Under "Current capabilities", after the `src/dispatch/` bullet, add:

```
- `src/web_dispatch/`: dispatcher-facing run console (FastAPI + HTMX + SSE,
  the delivery-side twin of the wave-pick console). Triggers
  `build_dispatch` with live progress, browses predicted runs + the review
  queue, downloads per-run manifests. Launcher `scripts/serve_web_dispatch.py`
  (127.0.0.1:8078); published at runs.rolodex-ai.com via the `wms-runs`
  Cloudflare tunnel. Read-only against CC. The build core is
  `src/dispatch/runner.py`, shared with the CLI.
```

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all PASS — **115 tests** (99 after Task 1 + 5 plans + 11 console [6 from Task 3 + 5 from Task 4] = 115). Confirm the count is green; the hard requirement is **0 failures**.

- [ ] **Step 6: Commit**

```bash
git add scripts/serve_web_dispatch.py docs/dispatch-dashboard-deploy.md CLAUDE.md
git commit -m "feat(web_dispatch): launcher + deploy checklist + capability docs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done criteria

- `dispatch/runner.py` is the shared build core; `build_dispatch.py` is a thin
  CLI delegating to it; `--dry-run` writes nothing; full suite green.
- The console renders at `127.0.0.1:8078`: build form triggers a job with live
  SSE progress; recent builds list shows the review count prominently; plan
  detail shows predicted runs + the review queue; run detail lists stops in
  postcode order; downloads work and reject path traversal.
- No CC writes anywhere; `write_enabled` never set; the read-only banner is
  shown.
- Deploy checklist documents the `wms-runs` tunnel + systemd steps; the
  operator runs the exposure-classifier commands via `!`.
- Shadow-mode note still applies: validate predictions against the dispatcher's
  real choices before considering any write-back (a future action behind the
  `CartonCloudSink` seam).
```
