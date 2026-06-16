# Wave Orchestration Service — Design

**Date:** 2026-06-16
**Status:** Approved for planning
**Component of:** the operational loop in `docs/ROADMAP.md` (§2, the
stateless-to-stateful decision)
**Branch context:** builds on `feature/carton-aware-pick-lines` (carton-aware
pick lines + `dispatch_link`)

---

## 1. Purpose

Turn the one-shot wave pick generator into a **continuous, run-aware, stateful
orchestrator** that watches live orders, parks next-day-delivery orders by
delivery run, accumulates them toward an efficient wave size, and surfaces
"ready" waves for a human to release — while feeding pallet requirements back to
the delivery run sorter.

This is the first build of the "stateful orchestration service" the roadmap
identifies as the single decision gating most remaining work. The proven one-shot
generator (`run_wave_generation()`) stays; this wraps it with persistent state and
a scheduler.

## 2. Scope

### In scope (v1)

- Continuous poll loop (every 10 min, 08:00–18:00 Mon–Fri) over live open orders.
- Persistent **holding store** keyed by delivery run.
- **Next-day-delivery filter** — only next-business-day orders are parked.
- Carton accumulation toward a target wave size, with a generation window.
- **Pallet peel** — orders filling their own pallet queue as single-order waves.
- **Human-gated wave release** — one click generates pick sheets for a run's
  orders via the existing generator.
- **Dispatch feedback arc** — pallet requirements written where the run sorter
  reads them.
- **Shadow observability** — a holding board + poll history so the logic can be
  validated against real order flow before it is trusted.
- **Manual override** — force-release, exclude, re-assign run, toggle pallet.

### Explicitly out of scope (later phases)

- **Any write back to CartonCloud.** v1 is strictly read-only against CC. A
  released wave produces *paperwork only*; a human keys the orders into CC by
  hand. Auto-push to CC is a deliberate later phase, enabled only after one to two
  weeks of shadow validation.
- **Vehicle allocation and vehicle-fit (cube) logic.** The feedback arc records
  pallet requirements; consuming them for truck allocation is future work (roadmap
  component A).
- **Same-day / urgent re-prioritisation** beyond flagging.

## 3. Safety model (non-negotiable)

Per `CLAUDE.md`: zero-tolerance for breakage, change-averse workforce, human
approval gates, "no agent loops on the pick bench — fixed event-driven pipelines
only".

- The loop is a **fixed event-driven pipeline**, not an agent loop.
- All internal steps (poll, park, accumulate, next-day filter, pallet feedback)
  run unattended because none of them touch the floor or CC.
- The **only** floor-facing action — releasing a wave (generating pick sheets) —
  is behind a **human click**.
- CC stays **read-only**. The orchestrator never mutates CC state in v1.
- Failures **fail loud and preserve state** (mirrors the stocktake F1 fix); they
  never silently drop parked orders.

## 4. Architecture (Approach A)

A stateful layer added to the **existing `src/web` picks console** (FastAPI +
HTMX + SSE) — one process, one SQLite file.

```
   CartonCloud (read-only) ──pull open orders──┐
                                               ▼
   APScheduler (every 10 min, 08:00-18:00 M-F)  poll loop
       │  attach run (dispatch_link) · carton split · next-day filter
       ▼
   SQLite holding store (parked_order / wave_queue / wave_order / poll_run)
       │  accumulate by run · pallet peel · window + release-short
       ▼
   wave_queue (status=ready)  ──shown in──▶  Picks console "Ready waves"
                                                   │ human clicks Release
                                                   ▼
                              run_wave_generation(order_ids=...)  (existing)
                                                   ▼
                              pick sheets (PDF/CSV)  ──human keys into CC

   each poll also writes ──▶  data/processed/dispatch_feedback/pallet_feedback.csv
                                                   ▲ read by build_dispatch (sorter)
```

Rationale: least new infrastructure, reuses what is already deployed on the NUC,
and the SQLite file is a single artefact that is trivial to back up. Approach B
(separate daemon + heavier DB) is the right evolution if volume grows; Approach C
(cron + JSON files) races the console once state spans polls and days.

## 5. State model (SQLite, WAL mode)

File: `data/orchestrator/holding.sqlite` (under `data/`, gitignored; included in
NUC backup).

### `parked_order`

One row per open SO currently held.

| Column | Notes |
|---|---|
| `order_id` | PK; CC outbound order id |
| `order_number` | human-facing |
| `customer` | customer name |
| `predicted_run` | from `dispatch_link` |
| `run_confidence` | float, from sorter |
| `run_flag` | `stable`/`mixed`/`new_address`/`stale`/`no_address`/`no_run` |
| `carton_count` | from carton-aware split |
| `is_pallet` | bool — peeled to its own pallet wave |
| `required_delivery_date` | from CC order |
| `business_day` | the generation day this order belongs to (date) |
| `status` | `parked` / `queued` / `released` / `rolled` / `gone` |
| `first_seen_ts`, `last_seen_ts` | UTC, tz-aware |
| `override` | nullable JSON — manual override applied (excluded, run re-assigned, pallet toggled) |

### `wave_queue`

One row per ready/released wave.

| Column | Notes |
|---|---|
| `wave_id` | PK |
| `run_name` | delivery run |
| `business_day` | date |
| `kind` | `combined` / `pallet` |
| `carton_count`, `order_count` | snapshot at creation |
| `status` | `ready` / `released` / `cancelled` |
| `short` | bool — released under target threshold |
| `created_ts`, `released_ts`, `released_by` | audit |
| `output_path` | where the generated sheets landed |

### `wave_order`

Link table: (`wave_id`, `order_id`).

### `poll_run`

Audit per poll cycle: `ts`, `orders_seen`, `added`, `updated`, `gone`,
`waves_created`, `error` (nullable). The shadow-mode evidence trail.

## 6. Poll loop

APScheduler job, fires every 10 min, **only 08:00–18:00 Mon–Fri** (AEST). Each
cycle, inside one service-layer transaction:

1. **Pull** open `AWAITING_PICK_AND_PACK` orders read-only from CC (reuse
   `wave_runner._pull_open_orders`). On failure: record `poll_run.error`, skip the
   cycle, keep all state, raise a console banner. No state mutation.
2. **Enrich** each order: attach predicted run (`dispatch_link`), compute
   `carton_count` (carton-aware split), read `required_delivery_date`.
3. **Next-day filter:** park only orders whose `required_delivery_date` is the
   **next business day**. Orders due later are left alone (not parked). Orders due
   **today or overdue** are flagged urgent in the console (surfaced, not silently
   parked).
4. **Idempotent upsert** keyed on `order_id`: insert new, update `last_seen_ts` +
   `carton_count` for existing. Orders previously parked but no longer in CC's open
   list → `status = gone` (picked or cancelled elsewhere).
5. **Pallet peel:** orders filling their own pallet → `is_pallet = true`. They do
   **not** count toward a run's combined-carton accumulation; each queues as its
   own `pallet` wave when detected within the generation window.
6. **Accumulate (only inside the 08:00–12:30 generation window):** per run, sum
   non-pallet, non-excluded parked cartons. When a run reaches `WAVE_TARGET_MIN`,
   create a `wave_queue` row (`status = ready`, `kind = combined`) and set its
   orders to `status = queued`. **Oversize runs:** if a single run's parked cartons
   exceed `WAVE_TARGET_MAX`, pack waves up to the max (closing whole orders — never
   split an order across waves) and leave the remainder parked to either fill the
   next wave or release short at 12:30.
7. **End-of-window release-short (first poll at/after 12:30):** the threshold is a
   *wait-until target, not a hard floor*. On the first poll at or after 12:30, every
   run still holding parked next-day orders releases as a `ready` wave **even if
   under `WAVE_TARGET_MIN`**, with `short = true`. Next-day orders must ship, so they
   cannot roll.
8. **Rollover:** orders that *arrive after the 12:30 cutoff* are parked with
   `business_day` = the next business day and wait for tomorrow's window.

### Business-day calendar

v1: weekends are non-business. Public-holiday handling is a documented follow-up
(a holiday list config), not v1.

## 7. Release gate (the one human action)

The picks console grows a **"Ready waves"** panel listing `wave_queue` rows in
`ready` status: run, carton count, order list, `kind` (combined vs single-pallet),
and a `short`/flagged badge.

- **Release** → orchestrator calls `run_wave_generation()` **scoped to that wave's
  `order_id`s** → sheets written to `data/processed/waves/<ts>/<wave_id>/` → row
  flips to `released`, `output_path` + `released_by` + `released_ts` recorded.
  Operator downloads the sheets and keys the orders into CC by hand.
- **Cancel** → row → `cancelled`, its orders → back to `parked`.

## 8. Dispatch feedback arc (wave → sorter)

The orchestrator owns `is_pallet` per order. Each poll it writes
`data/processed/dispatch_feedback/pallet_feedback.csv`:

```
order_id, order_number, address_key, predicted_run, must_pallet, updated_ts
```

The run sorter gets a small new reader (`src/dispatch/pallet_feedback.py`) that, if
the file exists and is fresh, joins it onto the sorter's per-order frame so
`review.csv` marks those orders as pallet. This is the hook the future vehicle-fit
logic will consume. File-based contract chosen because `build_dispatch` runs as a
separate script (not in the console process). Still read-only against CC.

## 9. Shadow observability

The surface for validating the logic over one to two weeks before trusting it:

- **Holding board** — per run: cartons accumulating toward threshold, order count,
  oldest-order age, projected release time/condition.
- **Poll-history strip** — recent `poll_run` rows (seen/added/gone/waves-created/
  errors).
- **Released-today log** — waves released, by whom, short or not, with sheet links.

## 10. Manual override

From the console, all logged into `parked_order.override` and `poll_run`:

- Force-release a run now (even short).
- Exclude an order from waving.
- Re-assign an order's predicted run.
- Toggle an order's pallet flag.

## 11. The one change to existing code

`run_wave_generation()` (in `src/wave_runner.py`) gains an optional **order-id
subset** (or accepts a pre-pulled order frame) so the orchestrator can generate a
single run's wave. **Backward compatible** — no subset means today's behaviour
(pull live and wave everything). Everything else is new code.

## 12. New modules

Under `src/web/orchestrator/`:

- `store.py` — SQLite schema, migrations, single service-layer API (all writes go
  through here so the scheduler and console actions never race).
- `scheduler.py` — APScheduler setup, the poll job, window/calendar logic.
- `holding.py` — domain logic: next-day classification, idempotent upsert,
  accumulation, pallet peel, release-short, rollover.
- `feedback.py` — writes `pallet_feedback.csv`.
- console routes + templates — Ready waves, Holding board, override actions
  (extend `src/web/app.py`, `runs.py`, `templates/`).

Plus `src/dispatch/pallet_feedback.py` (sorter-side reader).

## 13. Failure handling and concurrency

- CC pull failure → skip poll, preserve state, console banner. Never drops parked
  orders.
- Idempotent upsert prevents duplicates across polls.
- SQLite WAL; state survives restart. On startup the scheduler reconciles parked
  rows against live CC before resuming.
- All mutations route through `store.py`'s service layer; the scheduler is the only
  background writer, console actions are foreground writes through the same API —
  no two uncoordinated writers.

## 14. Configuration knobs

- `WAVE_TARGET_MIN` / `WAVE_TARGET_MAX` cartons (default 100 / 150).
- Poll interval (default 10 min) and poll window (default 08:00–18:00).
- Generation window end / release-short boundary (default 12:30).
- Pallet-fraction threshold (reuse existing generator setting).
- Business-day calendar (weekends; holiday list = follow-up).

## 15. Testing

- **Unit:** next-day classification; idempotent upsert; threshold crossing; pallet
  peel; 12:30 release-short; after-12:30 → next-business-day parking; gone-order
  detection; override application.
- **Integration:** a scripted sequence of **fake polls** (growing order sets across
  simulated time) asserting waves fire at the right thresholds and times, that
  12:30 releases short, that post-cutoff orders roll to the next business day, and
  that `pallet_feedback.csv` has the expected contents.
- Reuses existing `wave_runner` and `dispatch` tests; release path asserts
  `run_wave_generation()` is called with exactly the wave's order ids.

## 16. Deployment

- Extends the picks console already deployed on the NUC (Caddy front, LAN:
  `picks.gocold.local:8077`).
- systemd keeps the console+scheduler process alive.
- SQLite file at `data/orchestrator/holding.sqlite` — gitignored, added to the NUC
  backup routine.

## 17. Success criteria

1. Over a shadow week, the holding board accurately reflects live order flow
   (parked orders, accumulating cartons, runs) when eyeballed against CC.
2. Waves are created at the right run/threshold/time, and the 12:30 release-short
   behaviour matches reality (no next-day order left unwaved).
3. A human can release a ready wave in one click and get correct pick sheets for
   exactly that run's orders.
4. `pallet_feedback.csv` is produced each poll and the sorter's `review.csv`
   reflects pallet flags.
5. No CC writes occur. A CC pull failure never corrupts or drops holding state.

## 18. Open assumptions (validate during shadow week)

- Orders arriving after the 12:30 cutoff are genuinely fine to pick in the next
  day's window (i.e. next-day picking the day before dispatch is the norm).
- `required_delivery_date` is populated on CC open orders and reliable enough to
  drive the next-day filter. If sparse, fall back to "park all open orders" with a
  louder review flag.
- Address-key for the feedback file matches the key the sorter uses for history
  pairings.
