# Wave Pick Console — Design

_Spec date: 2026-06-04_

## Purpose

A local web console for the wave pick generator. Today, generating waves means
running `scripts/generate_waves.py` from a terminal: it pulls live open sale
orders from CartonCloud, routes them into streams, and writes per-wave PDF pick
sheets + CSVs + a `manifest.json`/`index.md` into
`data/processed/waves/<timestamp>/`. The console wraps that pipeline so a Go Cold
operator can:

1. Configure a run (status, customer, routing knobs) and click **Generate**.
2. Watch the pipeline progress live as it runs.
3. Browse the resulting waves, drill into a wave's pick lines, and download the
   PDF/CSV paperwork — without touching the terminal.

This is the first piece of the "bench service" CLAUDE.md anticipates.

## Scope

**In scope**
- Real live generation triggered from the UI (hits CC, writes the audit
  parquet + run outputs). Read-only against CC — it generates paperwork only.
- Exposed settings: `status`, `customer_name`, `pallet_fraction_threshold`,
  `early_release_cartons`, `run_group_col`.
- Live progress streaming while a run executes.
- Browsing past runs, run detail, wave detail, and file downloads (reading from
  disk — `manifest.json` + per-wave CSVs).

**Out of scope (defaults, not exposed)**
- `--soh-fallback` stays OFF (slow; off by default in the CLI too).
- `--logo`, `--lines-per-hour`, custom paths — keep CLI defaults.
- No pick-bench tick-off / floor display (that is a later, separate build).
- No writes back to CC. No `write_enabled`. No database.

## Constraints (from CLAUDE.md)

- **Read-only against CC.** Generation creates paperwork; nothing is pushed back.
- **Zero-tolerance for breakage.** No Node/SPA build toolchain — server-rendered
  HTML + HTMX + SSE, one `pip install`, one process.
- Credentials via `.env` only (loaded at startup, same as the CLI).
- Australian English in copy. Production-ready, no placeholders.
- Fixed event-driven pipeline — no agent loops.

## Architecture

```
Browser (HTMX + SSE)
      │ HTTP
      ▼
FastAPI app  (src/web/app.py)
  GET  /                      console: settings form + run history
  POST /runs                  start a job → HTMX-swaps in the live progress panel
  GET  /runs/{id}/stream      SSE: structured progress events
  GET  /runs/{id}             run detail: summary, waves table, skipped orders
  GET  /runs/{id}/waves/{w}   wave detail: pick lines in walk order, orders
  GET  /runs/{id}/files/{w}/{name}   download PDF / picks.csv / orders.csv
      │
      ▼
JobManager (src/web/jobs.py)   in-process, ONE run at a time
      │ runs in a worker thread (pipeline is blocking httpx/pandas)
      ▼
run_wave_generation(settings, progress_cb)   ← NEW src/wave_runner.py
      │ writes (unchanged file outputs)
      ▼
data/processed/waves/<timestamp>/  (manifest.json, index.md, per-wave dirs)
```

### Components

**`src/wave_runner.py` (new) — the shared pipeline core.**
The single most important change: lift the body of
`scripts/generate_waves.py:main()` into a reusable function so the CLI and the
web app run the *same* code.

- `WaveRunSettings` dataclass — `status: str`, `customer_name: str | None`,
  `pallet_fraction_threshold: float`, `early_release_cartons: int`,
  `run_group_col: str`, `soh_fallback: bool = False`, `lines_per_hour: int`,
  plus resolved paths (raw dir, dims, locations, assignments, rules, logo, out).
  Defaults pulled from the existing `analysis` constants
  (`DEFAULT_AWAITING_STATUS`, `DEFAULT_PALLET_FRACTION_THRESHOLD`,
  `DEFAULT_EARLY_RELEASE_CARTONS`, `DEFAULT_LINES_PER_HOUR`).
- `ProgressEvent` dataclass — `stage: str` (machine key, e.g. `"pull"`,
  `"classify"`, `"write"`), `message: str` (human line), `level: str`
  (`"info"`/`"ok"`/`"error"`), optional `data: dict` (e.g. counts).
- `RunResult` dataclass — `run_id: str` (the timestamp dir name), `out_dir: Path`,
  `summary: dict` (the existing `result.summary`), `status: str`
  (`"success"`/`"empty"`/`"failed"`), optional `error: str`.
- `run_wave_generation(settings: WaveRunSettings, progress: Callable[[ProgressEvent], None]) -> RunResult`
  — runs the existing 11 steps (live SO pull → snapshot → dims → routing →
  classify → locations → assignments → wave generation → write outputs →
  skipped report → index/manifest), calling `progress(...)` at each boundary.
  Raises are caught at the JobManager layer; the function itself may raise
  `CartonCloudError`/`SystemExit`-equivalents which become a `failed` RunResult.
  The "no open orders" path returns a `RunResult(status="empty")` with the
  empty run dir still written (matching current behaviour).

**`scripts/generate_waves.py` (refactor) — thin CLI wrapper.**
`main()` keeps its argparse surface, builds a `WaveRunSettings` from the parsed
args, and calls `run_wave_generation` with a `progress` callback that `print()`s
each event. **Observable CLI behaviour is unchanged** — same flags, same stdout
shape, same file outputs. This is the regression boundary we protect with tests.

**`src/web/jobs.py` — JobManager.**
- Holds at most one active run. `start(settings) -> run_id` rejects with a
  "run already in progress" error if one is active (single operator; prevents a
  double-click launching two live CC pulls).
- Runs `run_wave_generation` in a worker thread (the pipeline is blocking:
  sync httpx + pandas). The `progress` callback is thread-safe and appends each
  `ProgressEvent` to the active job's event buffer.
- Exposes the active job's events for the SSE endpoint to drain, plus terminal
  state (running / success / empty / failed + error message).
- A run that raises is captured as a `failed` job with the exception message;
  the worker thread never crashes the server.

**`src/web/runs.py` — disk reader (viewing).**
Pure functions over `data/processed/waves/`:
- `list_runs()` → newest-first list of `{run_id, generated_at, n_waves,
  n_orders, n_skipped, settings}` read from each `manifest.json`.
- `get_run(run_id)` → full manifest + skipped-orders (from
  `skipped_orders.csv` if present).
- `get_wave(run_id, wave_id)` → orders + pick lines read from the per-wave
  `*_orders.csv` / `*_picks.csv`.
- `file_path(run_id, wave_id, name)` → validated path for downloads (guards
  against path traversal; only serves files under the run dir).

**`src/web/app.py` — FastAPI app + routes.**
Jinja2 templates, static files, the six routes above. Loads `.env` at startup
(reusing the CLI's dotenv loader). Binds `127.0.0.1` by default.

**Templates (`src/web/templates/`)** — `base.html` (header, palette, HTMX +
vendored assets), `index.html` (settings form + progress panel target + run
history), `run_detail.html`, `wave_detail.html`, and partials
(`_progress.html`, `_run_row.html`).

**Static (`src/web/static/`)** — `app.css` (the palette below), vendored
`htmx.min.js` (no CDN), and a tiny `sse.js` only if HTMX's SSE extension isn't
vendored. No build step.

**`scripts/serve_web.py`** — launches uvicorn against `src.web.app:app`.

### Data flow — a run

1. Operator submits the settings form → `POST /runs` (HTMX).
2. App builds `WaveRunSettings`, calls `JobManager.start()`. If a run is active,
   returns a partial showing "a run is already in progress". Otherwise returns
   the progress panel partial, which opens an SSE connection to
   `/runs/{id}/stream`.
3. Worker thread runs `run_wave_generation`; each `ProgressEvent` is buffered.
4. `/runs/{id}/stream` emits buffered events as SSE (`event: progress`) and a
   final `event: done` carrying the terminal status + a link to `/runs/{id}`.
5. On `done`, the panel swaps in a "View run →" link. Viewing reads from disk.

### Data flow — viewing

Run detail and wave detail read entirely from the run folder on disk
(`manifest.json`, `skipped_orders.csv`, per-wave `*_picks.csv` / `*_orders.csv`).
No state is held between requests; the disk is the source of truth.

## UI

Three server-rendered screens (validated as mockups during brainstorming):

1. **Console (`/`)** — left: settings form (status, customer, pallet-fraction-
   threshold, early-release-cartons, run-group select); right: live progress log
   (per-stage ✓/▸/· ticks via SSE) and a "Recent runs" table linking to detail.
2. **Run detail (`/runs/{id}`)** — summary stat cards (waves / orders / pick
   lines / skipped), a waves table (stream pill, run group, orders, lines,
   cartons, est. walk, PDF/picks/orders links), and a skipped-orders panel when
   non-empty.
3. **Wave detail (`/runs/{id}/waves/{w}`)** — download buttons + consolidated
   pick lines in walk order (walk #, location, SKU, product, qty, running total,
   contributing SOs).

**Palette** — blue header (`#1a7fd4`) with a yellow status dot (`#ffd23f`),
bright green primary action (`#22b573`), yellow accents on the in-progress
line and bypass pills, green for ✓-success in the log. Stream pills: bench =
blue, bypass = yellow. Final visual polish via the `frontend-design` skill at
build time.

## Error handling

- **Run already active** → `POST /runs` returns a non-destructive partial; no
  second job starts.
- **Pipeline failure** (CC auth, missing dims xlsx, missing locations xlsx, CC
  pull error) → caught in the worker; job marked `failed`; SSE emits an `error`
  event with the message; the panel shows the error; the run does not appear as
  a successful entry. Missing required data files (dims/locations) fail fast with
  a clear message **before** the CC pull, mirroring the CLI's current checks.
- **No open orders** → `empty` run; UI shows "No orders matched status …"
  (the empty run dir is still written, as today).
- **Downloads** → path-validated; a request for a file outside the run dir or a
  non-existent file returns 404.
- **Malformed/partial run folder** when listing/viewing → skipped or shown with
  a clear "incomplete run" note rather than 500-ing the page.

## Testing

- **`tests/test_wave_runner.py`** — `run_wave_generation` against a fake CC
  client (monkeypatch `search_outbound_orders`) + fixture dims/locations/
  assignments. Assert: emits ordered progress events, writes the expected run
  folder + `manifest.json`, returns `success`; the no-orders path returns
  `empty`; a CC error yields `failed` without raising out of the manager.
- **CLI regression** — invoking `scripts/generate_waves.py` (via the refactored
  path, fake CC client) still produces the same file outputs and a 0 exit code.
- **`tests/test_jobs.py`** — JobManager single-run guard (second `start` while
  active is rejected), progress buffering order, terminal state transitions,
  failure capture.
- **`tests/test_web.py`** — FastAPI `TestClient`: `GET /` renders the form;
  `POST /runs` (mocked pipeline) starts a job and returns the progress partial;
  `/runs/{id}/stream` yields progress then done; run detail + wave detail render
  from a fixture run folder; downloads return the right bytes; path traversal and
  missing files 404.

## File layout

```
src/wave_runner.py            # NEW — shared pipeline core (settings + progress)
src/web/
  __init__.py
  app.py                      # FastAPI app + routes
  jobs.py                     # JobManager, ProgressEvent buffering
  runs.py                     # disk readers for run/wave/file
  templates/                  # base, index, run_detail, wave_detail, partials
  static/                     # app.css, htmx.min.js (vendored)
scripts/serve_web.py          # uvicorn launcher
scripts/generate_waves.py     # REFACTORED to call wave_runner (CLI unchanged)
tests/test_wave_runner.py
tests/test_jobs.py
tests/test_web.py
```

**New deps** (append to `requirements.txt`): `fastapi`, `uvicorn[standard]`,
`jinja2`, `python-multipart`. HTMX is vendored into `static/` — no CDN, no Node.

## Open questions / future

- Network binding: `127.0.0.1` for now. If the console must be reached from
  another machine on the bench LAN, switch to `0.0.0.0` behind the NUC firewall
  (later, explicit decision).
- Pick-bench tick-off / floor display is a deliberate later build.
- Live `--soh-fallback` toggle could be exposed once its latency is acceptable.
