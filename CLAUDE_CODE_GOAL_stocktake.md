# Goal: build a cycle count stocktake web app + CC reconciliation tool

You are building a new product inside Jake's Rolodex AI ecosystem. This is
NOT inside `gocold-wms-flow` — it's a fresh project. Create it at
`~/rolodex/gocold-stocktake/`.

## Why this exists

Go Cold's warehouse was recently reshuffled. CartonCloud's per-location
stock data is stale in spots, so we can't trust "SKU X is at AA-05-01"
until a physical recount catches CC up to reality. This app drives that
recount: warehouse staff scan-count an aisle at a time, the app compares
to CC, and produces a CSV the operator uploads to CC to adjust stock.

Once CC is trusted again, the wave generator (in `gocold-wms-flow`) can
use CC's live SKU → location data to route picks. So this project
unblocks that one.

## Hard rules — do not violate

1. **CartonCloud is READ-ONLY.** Reuse `CartonCloudClient` from
   `~/rolodex/gocold-wms-flow/src/cc_client/` (vendor a copy into this
   project; do NOT modify it; `write_enabled=False` stays locked). The
   adjustment workflow is: app generates a CSV → operator manually uploads
   to CC. The app NEVER writes to CC.
2. **SAP B1 is plugged into CC.** Writes from us could collide with
   SAP-driven changes. This is why everything goes via operator-reviewed
   CSV upload.
3. **No new dependencies beyond what's strictly needed.** Stick to
   FastAPI, SQLAlchemy/Prisma (Jake prefers Prisma for app projects but <!-- gitleaks:allow -->
   Python projects typically use SQLAlchemy — check existing Rolodex AI
   Python apps for convention; if unclear, use SQLAlchemy 2.0 to keep
   surface small), Pydantic, httpx, pandas. React 18+/TypeScript +
   Tailwind + shadcn/ui on the frontend. PostgreSQL via Docker.
4. **Match Rolodex AI conventions.** Look at `~/rolodex/gocold-wms-flow/`
   and any other Rolodex project on disk for stack patterns. Production-
   complete code only — no stubs/placeholders. Australian English in UI
   strings and comments. No emojis. Pino-style structured logging.
5. **Three-segment app pattern Jake uses everywhere:** Docker Compose +
   Caddy reverse proxy + Cloudflare DDNS for external access (but this
   tool is LAN-internal). Self-hosted on the NUC at Go Cold.

## Stack constraints (Jake's defaults)

- Backend: FastAPI + SQLAlchemy 2.0 async + Alembic migrations + Pydantic v2
- Frontend: React 18 + TypeScript + Vite + Tailwind + shadcn/ui
- DB: PostgreSQL 16 (Docker)
- Reverse proxy: Caddy
- Deploy: Docker Compose, lives on the NUC at Go Cold
- Ports: don't collide with existing NUC services. Use 3008 for API,
  5178 for frontend dev, 5441 for PostgreSQL (audit existing
  compose files on the NUC if reachable; otherwise these are sensible).
- Target hardware in the field: Zebra TC series Android devices running
  Chrome. The page must work on a 4-6 inch screen with chunky tap
  targets and hardware-scanner input (scanner emits keyboard events).

## Scope — features

### Auth
PIN-per-counter pattern.
- `Counter` table: id, name, pin_hash (bcrypt), active, created_at.
- Login: enter 4-digit PIN. Session via HTTP-only cookie, 12-hour expiry.
- One supervisor PIN with admin scope (manage counters, see all sessions).
- Every count event tagged with `counter_id` so we know who counted what.
- Audit trail is non-negotiable for a stocktake.

### Cycle count workflow

1. **Start session.** Counter logs in with PIN, picks an aisle from a
   dropdown of CC aisles (we pull these from CC at session start). They
   can also tag the session with a sub-zone if needed.
2. **Bin loop.** App shows: "Scan location barcode". Hardware scanner
   feeds the bin code. App displays:
   - Bin code (large, monospace)
   - What CC currently says is in this bin (SKU + qty per SKU)
   - "Scan SKU" prompt + qty input
3. **SKU scan.** Counter scans product barcode. Two cases:
   - **Expected SKU**: app auto-fills the SKU row, counter just types qty.
   - **Unexpected SKU** (CC says it's elsewhere or nowhere): app shows
     "NOT EXPECTED HERE — counted anyway?" with a confirm step.
4. **Empty bin button.** Big red "EMPTY" button confirms bin has nothing.
5. **Complete bin.** Press "Done with this bin" to move on. Bin marked
   counted in session.
6. **Resume support.** Counter can pause and resume; partial sessions
   persist.
7. **Submit aisle.** When all bins in aisle done, counter hits submit.
   Session goes to `pending_review` state.

### Live picks during count (the no-lock decision)

Picks continue during a count session. To handle this:
- When the session is submitted, server re-pulls CC stock for the
  affected bins.
- Compare scanned counts to CC at submit time (not at session start).
- If a bin's CC count CHANGED during the session (a pick happened),
  flag the bin as `volatile` in the variance report so the supervisor
  knows the variance might be due to a legitimate intervening pick.
- Store both: CC count at session start AND CC count at session submit.
  Variance = scanned - cc_at_submit. Note the delta for transparency.

### Variance report

After session submit, app shows a per-bin variance table:
- Bin | SKU | CC qty (at submit) | Counted | Variance | Volatile? | Notes
- Color-code: green = match, yellow = small variance (±5 units),
  red = big variance.
- Supervisor can mark variances as "accept count" or "recount required".

### CC adjustment CSV export

Once variances are reviewed and accepted, export a CSV in the format CC's
stock adjustment import expects. Format (verify by checking CC docs or
existing CC export, then hardcode):

```
location_name,product_code,adjustment_qty,reason,notes
AA-05-01,RK-COKE-12,+8,Cycle count adjustment,Counter: Jake / Session 17
AA-05-02,PC-LRG,-3,Cycle count adjustment,Counter: Jake / Session 17
```

`adjustment_qty` is the delta (scanned - cc_current), not the new total.
The operator uploads this manually in CC. App writes a confirmation note
saying "CSV exported - upload to CC Admin > Stock Adjustments".

### Reporting

- **Sessions list:** all sessions with date, counter, aisle, status,
  variance summary.
- **Aisle heatmap:** show which aisles have been counted in the last 30
  days. Red = >30 days since count or never counted.
- **Counter performance:** counts per session, bins per hour, variance
  rate per counter (NOT for performance reviews — for spotting training
  needs).
- **Top variance SKUs:** SKUs with biggest cumulative variance across
  sessions. These need investigation.

## Tasks — execute in order, report progress after each

### Task 1 — project scaffold

1. Create `~/rolodex/gocold-stocktake/` with structure:

   ```
   gocold-stocktake/
   ├── api/                 # FastAPI backend
   │   ├── app/
   │   │   ├── __init__.py
   │   │   ├── main.py
   │   │   ├── config.py
   │   │   ├── db.py
   │   │   ├── auth.py
   │   │   ├── models/
   │   │   ├── routers/
   │   │   ├── services/
   │   │   └── cc_client/       # vendored from gocold-wms-flow
   │   ├── alembic/
   │   ├── tests/
   │   ├── requirements.txt
   │   └── Dockerfile
   ├── web/                 # React/Vite frontend
   │   ├── src/
   │   ├── public/
   │   ├── package.json
   │   ├── tsconfig.json
   │   ├── vite.config.ts
   │   ├── tailwind.config.ts
   │   └── Dockerfile
   ├── caddy/
   │   └── Caddyfile
   ├── docker-compose.yml
   ├── .env.example
   ├── .gitignore
   ├── README.md
   └── CLAUDE.md
   ```

2. Vendor `CartonCloudClient` + queries into `api/app/cc_client/` by
   COPYING (not symlinking) from `~/rolodex/gocold-wms-flow/src/cc_client/`.
   Add a note in `cc_client/__init__.py`: "vendored from gocold-wms-flow,
   keep in sync".
3. Write `CLAUDE.md` capturing the read-only rule, port allocations,
   stack choices, and link to this goal file.
4. Smoke: `docker compose up` brings up Postgres, API, Caddy. Frontend
   dev runs separately via Vite for now.

### Task 2 — data model + migrations

Schema:

```
Counter(id, name, pin_hash, is_supervisor, active, created_at)
CountSession(id, counter_id, aisle, status[in_progress|pending_review|
              completed|cancelled], started_at, submitted_at, notes)
BinCount(id, session_id, location_code, cc_qty_at_start,
          cc_qty_at_submit, marked_empty, scanned_at_start,
          scanned_at_complete, volatile)
SkuCount(id, bin_count_id, product_code, scanned_qty, was_expected,
          notes, scanned_at)
VarianceReview(id, session_id, location_code, product_code,
                cc_qty, counted_qty, variance, decision[accept|recount|
                pending], decided_by_counter_id, decided_at)
AdjustmentExport(id, session_id, csv_path, exported_at, exported_by,
                  uploaded_to_cc_at)
```

Add Alembic migration. Seed two counters in dev (supervisor + worker)
with known PINs from env vars.

### Task 3 — CC integration layer

`api/app/services/cc_stock.py`:
- `list_aisles()` — from CC location data, returns distinct aisle codes.
- `get_bin_stock(location_code)` — current SKU + qty per bin via
  stock-on-hand report aggregated by location + product.
- `get_expected_skus_for_bin(location_code)` — for the "what should be
  here" UI. Cache aggressively (5 min TTL) so we don't hammer CC.
- All functions wrap existing `get_stock_on_hand` / `search_warehouse_
  locations`. ZERO writes to CC.

Stock-on-hand is async at CC's end (report run). Schedule a session-
start prefetch: when a counter picks an aisle, kick off an async fetch
of all bins in that aisle, cache locally, return as the counter walks.

### Task 4 — backend routers

- `POST /auth/login` — PIN, returns session cookie.
- `POST /auth/logout`.
- `GET /aisles` — available aisles to count.
- `POST /sessions` — start session (counter_id from cookie, aisle in
  body). Triggers async stock prefetch.
- `GET /sessions/{id}` — current state + remaining bins.
- `GET /sessions/{id}/bins/{location_code}` — what CC says is here.
- `POST /sessions/{id}/bins/{location_code}/skus` — record a SKU scan
  with qty.
- `POST /sessions/{id}/bins/{location_code}/empty` — mark bin empty.
- `POST /sessions/{id}/bins/{location_code}/complete` — finalise bin.
- `POST /sessions/{id}/submit` — submit aisle for review. Re-fetches
  CC stock at submit time for variance calc.
- `GET /sessions/{id}/variances` — variance report rows.
- `POST /sessions/{id}/variances/{variance_id}/decide` — accept/recount.
- `POST /sessions/{id}/export-adjustment-csv` — write CSV, return
  download URL.
- `GET /reports/aisle-heatmap` — last counted dates per aisle.
- `GET /reports/counter-stats` — per-counter session/variance stats.
- `GET /reports/top-variance-skus` — biggest cumulative variances.

Pydantic models for everything. OpenAPI auto-generated. Background tasks
for stock prefetch via FastAPI BackgroundTasks (don't reach for Celery
yet — overkill).

### Task 5 — frontend

Pages:
- `/login` — PIN entry. 4 big digit buttons + clear/enter.
- `/sessions/new` — pick aisle dropdown, "Start counting".
- `/sessions/{id}/count` — the main work screen.
  - Big bin code at top
  - "Expected" SKU list with checkboxes
  - "Scan SKU" input (hardware scanner emits keyboard events; just an
    `<input autoFocus>` with debounce so consecutive scans don't bleed)
  - Qty pad (big +1/+5/+10/clear buttons + numeric input)
  - Big red "EMPTY BIN" button
  - "Done with bin" button
- `/sessions/{id}/review` — variance table for supervisor.
- `/admin/counters` — manage counters (supervisor only).
- `/reports` — heatmap + counter stats + top variances.

UX rules:
- Tap targets ≥44px (Apple HIG) but go bigger here — these are gloved
  warehouse hands. Aim for 60px buttons.
- High-contrast colours, large fonts. Test on a real Zebra TC if possible.
- One-handed operation: critical actions on the right side of the
  screen.
- Loud feedback: green flash on successful scan, red on error,
  vibrate (`navigator.vibrate(200)`).
- Offline-resilient: if API call fails, queue the action in
  localStorage and retry. Show "OFFLINE — count saved locally" banner.

### Task 6 — Docker Compose

- `db`: postgres:16 on 5441
- `api`: FastAPI on 3008
- `caddy`: 8090 (LAN only; no Cloudflare tunnel for this)
- `web`: built statically and served by Caddy
- `stocktake.local.gocold` resolvable via NUC's local DNS or hosts file

Caddyfile reverse-proxies API to /api/* and serves static frontend
for everything else.

### Task 7 — smoke test plan

Before declaring done:
1. Start the stack with `docker compose up`.
2. Seed two counters via env. Log in as both.
3. Pick a real aisle, walk through 3 bins, scan, submit.
4. Verify variance report shows correct deltas.
5. Export CSV, open it, confirm format matches CC's adjustment import
   format.
6. Take a screenshot of the count screen on a phone-sized viewport
   (Chrome dev tools, 360x640).
7. Write findings into `data/processed/stocktake/smoke_<date>.md`.

## Reporting cadence

After each task, write a short status update:
- What you did
- Any deviations and why
- What you found (key numbers, issues)
- Whether to proceed or wait for operator input

If you hit ambiguity, **stop and ask**:
- If CC's stock adjustment CSV format is unknown — ask before guessing.
- If the existing CC client wraps don't support per-location stock
  filtering well — ask before extending.
- If port collisions on the NUC are unclear — ask, don't pick randomly.
- If Zebra TC scanner input mode (keyboard wedge vs intent) isn't
  configurable from your side — ask for a sample scan to confirm.

## Out of scope — do not do these

- Don't write to CC. Ever. The CSV upload is manual, by the operator.
- Don't add features beyond cycle count + variance report + CSV export.
  No full WMS, no putaway workflow, no transfer orders.
- Don't add native mobile apps. Web only on the Zebra browser.
- Don't add a "merge multiple counters" multi-user-per-bin flow yet —
  one counter per session is enough. Race conditions if two people
  count the same bin can wait.
- Don't add Stream 1 (pick-to-pallet) integration with this app. It's
  a stocktake tool, not a pick tool.
- Don't push to git. Leave changes uncommitted for operator review.
- Don't deploy to production until smoke tests pass and Jake confirms.
