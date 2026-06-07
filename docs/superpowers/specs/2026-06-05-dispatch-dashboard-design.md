# Dispatch Dashboard (runs.rolodex-ai.com) — Design Spec

**Date:** 2026-06-05
**Status:** Approved (brainstorming)
**Feature spec:** builds on `docs/superpowers/specs/2026-06-05-dispatch-run-prediction-design.md`

## Goal

A dispatcher-facing web console at **runs.rolodex-ai.com** for the dispatch
run-prediction pipeline (`src/dispatch/` + `scripts/build_dispatch.py`). The
dispatcher can: trigger a build with live progress, browse the predicted
delivery runs and the review queue, and download per-run manifests. It is the
delivery-side twin of the existing wave-pick console at picks.rolodex-ai.com.

**Read-only against CartonCloud.** `write_enabled` is never set anywhere in
this app. A future "push to CC" action slots in behind the existing
`CartonCloudSink` seam once that path is approved and tested — the layout
leaves room for it, but it is **not built in this version**.

## Vocabulary

The picks console already uses `/runs` to mean *wave* runs. To avoid the
collision (and because this is a separate app), this console uses:

- **plan** — one `build_dispatch` output: a timestamped directory under
  `data/processed/dispatch/<stamp>/` (one `DispatchPlan` materialised to disk).
- **run** — one predicted delivery run *within* a plan (a `predicted_run`
  value, e.g. "West-Tue").

## Non-goals (YAGNI — deliberately excluded)

- No override capture, no run locking, no "mark dispatched" workflow.
- No `--dry-run` in the UI (it writes a stamped dir every build).
- No CartonCloud writes of any kind.
- No auth in the app — Cloudflare Access gates the tunnel edge, same as picks.
- No multi-operator concurrency — single in-flight build, like picks.

## Architecture

A new self-contained FastAPI app `src/web_dispatch/`, mirroring the proven
`src/web/` picks console: server-rendered Jinja2 + HTMX + SSE, one process,
no build step. It reads `data/processed/dispatch/<stamp>/` and triggers builds
via a shared run core. Approach A from brainstorming (separate app + tunnel):
zero changes to the live picks app; the small `base.html` + CSS + JS are copied
for a consistent look.

```
                 build_dispatch.py CLI ─┐
                                        ├─→ dispatch/runner.run_dispatch_job(settings, emit)
   web_dispatch (POST /build) ──Job───┘         │  (read-only CC pull → predict → FileSink)
                                                 ▼
                              data/processed/dispatch/<stamp>/
                                 suggested_runs.csv, review.csv,
                                 carriers_*.csv, run_*.xlsx, summary.md
                                                 │
   web_dispatch (GET /plans/...) ──plans.py──────┘  (disk reader, no held state)
```

## Components

Each is small, single-purpose, independently testable.

### 1. `src/dispatch/runner.py` (new — the build core)

Extracts the orchestration glue currently inside `scripts/build_dispatch.py`
`main()` into a reusable, progress-emitting core. Both the CLI and the web app
call it. Mirrors the `generate_waves → wave_runner` precedent (commit e6b6fa1).

```python
@dataclass
class DispatchRunSettings:
    repo_root: Path
    history_days: int = 90
    skip_learn: bool = False

@dataclass
class DispatchProgressEvent:        # shape mirrors wave_runner.ProgressEvent
    stage: str                      # machine key: learn|predict|write|done
    message: str
    level: str = "info"             # info | ok | error
    data: dict[str, object] = field(default_factory=dict)

@dataclass
class DispatchRunResult:
    stamp: str                      # the on-disk plan folder name
    out_dir: Path
    counts: dict[str, int]          # assignments / carriers / review / runs
    status: str                     # success | empty | failed
    error: str | None = None

ProgressCallback = Callable[[DispatchProgressEvent], None]

def run_dispatch_job(
    settings: DispatchRunSettings,
    emit: ProgressCallback,
) -> DispatchRunResult: ...
```

Behaviour: load `.env`, build `CartonCloudClient.from_env()` (write disabled),
call the existing `dispatch.predict.predict_runs` flow via `run_dispatch(...)`,
write with `FileSink(out_dir)` to `data/processed/dispatch/<stamp>/`
(stamp = `datetime.now().strftime("%Y%m%d_%H%M%S")`), emit coarse events along
the way (learning from history → records pulled → open orders pulled →
predicted N stable / M review / K carriers → wrote → stamp), return the result.
`status="empty"` when there are zero open orders to predict; `"failed"` on a
caught exception (the event with `level="error"` is emitted, exception
re-raised for the JobManager to record — matching the picks contract).

**`scripts/build_dispatch.py`** is refactored so `main()` delegates to
`run_dispatch_job` with a stdout-printing `emit`. The existing
`run_dispatch()` function and the integration test (`tests/test_build_dispatch.py`)
are preserved unchanged — `run_dispatch_job` calls `run_dispatch` internally.

### 2. `src/web_dispatch/jobs.py` (copied from `web/jobs.py`)

`JobManager` — single in-flight job, worker thread, buffered events. Identical
structure to the picks `JobManager`, retyped against `DispatchRunSettings` /
`DispatchRunResult` / `run_dispatch_job`. `RunInProgressError` rejects a second
concurrent build (double-click guard). `Job` carries
`status / events / result / error / done / stamp`.

### 3. `src/web_dispatch/plans.py` (disk reader — pure functions, no held state)

```python
def list_plans(base: Path) -> list[dict]:
    # newest-first; one card per <stamp> dir. Reads summary.md + the CSVs
    # to derive: stamp, generated_at (from dir mtime or summary), n_runs,
    # n_assignments, n_review, n_carriers.

def get_plan(base: Path, stamp: str) -> dict:
    # summary_md (raw text), runs: [{run, n_stops, avg_confidence}],
    # review: [rows from review.csv], carriers: {name: [rows]},
    # files: [downloadable names present in the dir].

def get_run(base: Path, stamp: str, run: str) -> dict:
    # stops for one predicted run: rows of suggested_runs.csv filtered to
    # predicted_run == run, sorted by postcode.

def file_path(base: Path, stamp: str, name: str) -> Path:
    # resolved path with traversal guard (str(target).startswith(dir + "/")),
    # FileNotFoundError if absent — same guard as web/runs.py.
```

`base` is `repo_root / "data" / "processed" / "dispatch"`. CSVs read with
`pandas` and `.fillna("").to_dict("records")` (matching `web/runs.py`).

### 4. `src/web_dispatch/app.py` (`create_app(repo_root)` factory + routes)

Mirrors `web/app.py`: mounts `/static`, Jinja2 templates, stores
`repo_root / dispatch_base / manager / templates` on `app.state`. Module-level
`app = create_app()` for uvicorn.

### 5. `static/` + `templates/`

Copied from picks for a consistent look: `app.css`, `htmx.min.js`, `sse.js`,
`base.html`. New page templates: `index.html`, `_progress.html`,
`_run_busy.html`, `plan_detail.html`, `run_detail.html`. Title: "Go Cold
Dispatch Run Console". A persistent banner notes *"Predictions only — not
written to CartonCloud."*

## Routes

| Method & path | Purpose |
| --- | --- |
| `GET /` | Build form (history-days=90, skip-learn checkbox) + newest-first plan list. **Review-queue count shown prominently** per plan. |
| `POST /build` | Start a build job. Returns `_progress.html` partial + `x-job-id` header. `_run_busy.html` if a build is already active. |
| `GET /build/job/{job_id}/stream` | SSE stream of progress events; on `done`, a "View plan →" link to `/plans/{stamp}` (only when status != failed). |
| `GET /plans/{stamp}` | Plan detail: summary, predicted runs (stops + avg confidence), **review queue table** (so_ref, flag, reason, zone, best-guess run, alternatives), carriers, download links. 404 if stamp missing. |
| `GET /plans/{stamp}/runs/{run}` | One delivery run's stops, postcode-sorted. |
| `GET /plans/{stamp}/files/{name}` | Download a file (CSV / xlsx / summary.md) via `FileResponse`; 404 on traversal or missing. |

The SSE and busy-guard mechanics are lifted verbatim from the picks
`/runs/job/{id}/stream` + `_run_busy.html` flow.

## Data flow

1. Dispatcher clicks **Build** → `POST /build` → `JobManager.start(settings)`
   spawns a worker thread running `run_dispatch_job`.
2. The worker emits `DispatchProgressEvent`s, buffered on the `Job`.
3. The browser's `sse.js` drains `GET /build/job/{id}/stream`; on `done` it
   swaps in the "View plan →" link.
4. `GET /plans/{stamp}` reads the freshly-written dir via `plans.py` and renders
   runs + the review queue. No state persists between requests — the stamped
   dir is the source of truth.

## Error handling

- Build failure: worker catches, sets `Job.status="failed"`, appends an
  `error`-level done event; the stream surfaces it; no plan link shown.
- Missing/unparseable plan dir: `get_plan` raises, route returns 404.
- Download traversal/missing: `file_path` raises, route returns 404.
- Empty open-order set: `status="empty"`, plan still written (all rows in
  review or none), UI shows a clear "no open orders" note.
- Worker never crashes the process (broad except in `JobManager._run`, same as
  picks).

## Deploy (mirrors the picks pattern — see `[[wave-console-tunnel-deploy]]`)

- `scripts/serve_web_dispatch.py` launcher (copy of `serve_web.py`), binds
  `127.0.0.1:8078` by default, read-only.
- New named Cloudflare Tunnel `wms-runs` → `runs.rolodex-ai.com` →
  `http://127.0.0.1:8078`, gated by Cloudflare Access (same email allowlist).
  Config: `~/.cloudflared/wms-runs.yml`.
- systemd `--user` services: `wms-runs-app.service` (uvicorn on :8078) and
  `wms-runs-tunnel.service` (cloudflared, `After=app`). Unit files under
  `~/.config/systemd/user/`. Linger already enabled for `pop_os`.
- **Operational steps the user runs via `!`** (tunnel create, DNS route,
  systemd enable): the build delivers the app, launcher, tests, and a
  `docs/` deploy checklist; it does not create the tunnel or touch DNS
  (the exposure classifier — same constraint as the picks deploy).

## Testing

Mirror `tests/test_web.py` with FastAPI `TestClient` over `create_app(tmp_path)`
seeded with fixture dispatch dirs:

- `test_web_dispatch.py`: index lists plans; plan detail renders runs + review
  table; run detail renders postcode-sorted stops; download returns a file and
  rejects traversal; `POST /build` starts a job (runner stubbed via the
  `JobManager(runner=...)` injection seam — **no live CC**); busy guard returns
  `_run_busy` on a second concurrent start.
- `test_dispatch_plans.py`: `plans.py` parsing of `suggested_runs.csv` /
  `review.csv` / `summary.md` into the documented dict shapes; `file_path`
  traversal guard.
- `test_dispatch_runner.py`: `run_dispatch_job` emits the expected stages and
  writes a stamped dir, with `search_consignments` / `search_outbound_orders`
  monkeypatched (same technique as `tests/test_build_dispatch.py`); `status`
  is `"empty"` when no open orders, `"success"` otherwise.

All tests offline. Run with `.venv/bin/python -m pytest` (stale-shebang venv).

## File structure

| File | Responsibility |
| --- | --- |
| `src/dispatch/runner.py` (create) | `DispatchRunSettings`, `DispatchProgressEvent`, `DispatchRunResult`, `run_dispatch_job` |
| `scripts/build_dispatch.py` (modify) | `main()` delegates to `run_dispatch_job`; `run_dispatch()` unchanged |
| `src/web_dispatch/__init__.py` (create) | package marker |
| `src/web_dispatch/app.py` (create) | `create_app` factory + routes |
| `src/web_dispatch/jobs.py` (create) | `JobManager` (copied/retyped from `web/jobs.py`) |
| `src/web_dispatch/plans.py` (create) | disk reader: `list_plans`, `get_plan`, `get_run`, `file_path` |
| `src/web_dispatch/static/{app.css,htmx.min.js,sse.js}` (copy) | assets from picks |
| `src/web_dispatch/templates/{base,index,_progress,_run_busy,plan_detail,run_detail}.html` (create/copy) | views |
| `scripts/serve_web_dispatch.py` (create) | uvicorn launcher on :8078 |
| `tests/test_web_dispatch.py` (create) | route/integration tests |
| `tests/test_dispatch_plans.py` (create) | disk-reader tests |
| `tests/test_dispatch_runner.py` (create) | runner tests |
| `docs/` deploy checklist (create) | tunnel + systemd steps for the operator |

## Future (explicitly out of scope now)

- **CC write-back**: a "Push run to CC" action behind `CartonCloudSink`, enabled
  only when both `write_enabled` and `dispatch_write_approved` are set and the
  SAP B1 boundary is cleared. The plan layout reserves a spot; nothing is wired.
- Override capture for shadow-mode (predicted vs actual) could be layered on
  later; for now the dispatcher reconciles manually against the review queue.
- A future shared web-scaffolding library if a third console appears (would
  retire the copied `jobs.py` / `base.html` duplication).
