# Go Cold WMS — Roadmap

**Reconciled:** 2026-06-16 · **Branch at reconciliation:** `feature/carton-aware-pick-lines`

This is the accurate, code-grounded successor to the original "gocold
brainstorming" scratchpad. It is structured around the **operational loop** the
tooling is meant to form — not a fixed list of scripts. The three workflows from
the original doc are real and live here as *components of that loop*, alongside a
data substrate they all depend on and an open horizon of candidate workflows.

Times change; this is deliberately not a three-horse race. The Horizon section is
an open list and is expected to grow.

---

## 1. The shape of the system

The goal is a closed operational loop, not a set of disconnected scripts:

```
              ┌──────────────────────────────────────────────┐
              │                CartonCloud (read-only)         │
              └───────────────┬────────────────────────────────┘
                              │ open orders, history, SOH
                              ▼
                  ┌───────────────────────┐
                  │  A. Delivery Run Sorter│  intake + sequencing
                  │  (predict order → run) │
                  └───────────┬───────────┘
                              │ run allocation
                              ▼
                  ┌───────────────────────┐   pallet-must-go-alone
                  │  B. Wave Pick Generator│◀──────────┐ feedback
                  │  (release work to floor)│           │ (NOT yet wired)
                  └───────────┬───────────┘            │
                              │ pick sheets             │
                              ▼                         │
                  ┌───────────────────────┐             │
                  │  Pick / pack on floor  │─────────────┘
                  └───────────┬───────────┘
                              │ packed orders
                              ▼
                  ┌───────────────────────┐
                  │  Dispatch / vehicle    │  load → truck (NOT yet built)
                  │  allocation            │
                  └───────────────────────┘

   Underneath all of it — the DATA SUBSTRATE the loop runs on:
   · trustworthy SKU → location (unblocked by C. Stocktake)
   · carton dims for every SKU (captured locally, not yet in CC)
```

Today the code is a **one-directional, stateless pipeline**: CC → predict → wave →
paperwork. The loop's two missing arcs — continuous wave release with memory, and
the pallet-feedback / vehicle arc back from the floor — are the heart of the work
ahead.

---

## 2. The architectural decision that gates most of this

> **Stateless scripts → a stateful orchestration service.**

The original doc's wave behaviour (poll every 10 min, *park* next-day orders in a
*holding area* by run, *accumulate* to 100–150 cartons, roll leftovers to the next
day) and the run-sorter's *feedback loop* both reduce to the same missing capability:
**persistent state + a scheduler**. Each `run_wave_generation()` call today is
stateless — it pulls fresh, waves fresh, forgets everything. There is no holding
area because there is nowhere to hold.

So the foundational decision is: introduce a small **stateful service** (the
existing FastAPI consoles + a lightweight datastore / persistent queue) that the
proven one-shot generators plug into. The generators stay; orchestration wraps them.

**Until this exists, components B and C's loop behaviours stay manual.** Almost
every "Absent" below traces back to this one decision. It should be designed once,
deliberately, before being half-built three times.

---

## 3. Components of the loop (status reconciled against code)

Status key: ✅ built · ⚠️ partial · ❌ absent.

### A. Delivery Run Sorter — *intake + sequencing* (`src/dispatch/`)

Predict-to-run v1 is genuinely built and validated against real 90-day data.

| Capability | Status | Evidence / note |
|---|---|---|
| Sort open orders by delivery run | ✅ | `runner.py`, `predict.py`, `output.py` → `suggested_runs.csv` |
| Learn runs from ~90d consignment history | ✅ | `history.py` recency-weighted (30d half-life) |
| Predict with confidence + flag + reason | ✅ | `RunAssignment` in `predict.py`; `review.csv` |
| Exclude orders **not** next-day delivery | ❌ | sorts all open orders; `delivery_required_date` stored but unused |
| Feedback **from** wave gen (must-pallet) | ⚠️ | dispatch→wave wired (`dispatch_link.py`); wave→dispatch return path absent |
| Allocate run/load to a **vehicle** | ❌ | no vehicle model anywhere |
| Vehicle **fit** (carton dims vs load dims) | ❌ | 409 SKU dims exist; no cube/packing calc, no vehicle master |

**Gap to close:** next-day filter (small), then the vehicle layer (master data +
volumetric fit — large, and the doc's real ambition for this component).

### B. Wave Pick Generator — *work release* (`scripts/generate_waves.py`, `src/wave_runner.py`)

The **one-shot generator is solid**: live `AWAITING_PICK_AND_PACK` pull → routing /
stream classification → carton-split (this branch) → accumulate by run+stream →
PDF/CSV pick sheets → manual-trigger web console with SSE progress. It already links
*to* dispatch (groups by `predicted_run`).

What the doc wants beyond that is the **continuous orchestration layer** (see §2):

| Capability | Status | Note |
|---|---|---|
| Pull live open SOs from CC | ✅ | `wave_runner.py:_pull_open_orders` |
| Group/release by predicted run (from sorter) | ✅ | `dispatch_link.py` |
| Poll every 10 min, 8am–6pm | ⚠️ | `peak_wave_watch.py` is a manual-trigger watcher, not a continuous auto-loop |
| Address → next run + next-business-day check | ❌ | run comes from the dispatch plan; no next-bday logic here |
| Persistent **holding area**, park by run, accumulate across polls | ❌ | every run is stateless |
| Wait for 100–150 cartons before waving | ⚠️ | threshold exists but defaults to 30, not persistent |
| Peel pallet-sized orders to a "pallet orders" tab, re-measure remaining | ⚠️ | carton-split is per-order; pallet stream separated, but no peel-and-re-measure loop |
| 8:00–12:30 window + after-12:30 → next-day rollover | ⚠️ | cutoff is 13:00; no rollover queue |
| Manual per-order override | ❌ | none |

**Gap to close:** the stateful scheduler/holding service of §2 (large), then the
window + rollover + override knobs on top of it (small–medium each).

### C. Stocktake & Reconciliation — *data-trust substrate* (`gocold-stocktake/`)

A separate, well-built repo (FastAPI + React + Postgres + Caddy, 90 passing tests).
It exists to make CC's per-location stock trustworthy again after the warehouse
reshuffle — which is what unblocks B's location-candidate step.

> **Update vs the 12 Jun audit:** the F1 blocker (CC SOH read failing silently to an
> empty snapshot → "add everything" CSV) is **CLOSED**. The read now fails loud:
> 503 at aisle selection, blocked `open_bin`, and refused variance build on a
> degraded snapshot (`routers/aisles.py:22`, `services/sessions.py:92,199`).

| Doc feature | Status | Note |
|---|---|---|
| Aisle select → scan slot | ✅ | `NewSessionPage`, `CountSessionPage` |
| 4-digit PIN login | ✅ | keypad + hashed PIN |
| Laptop-only admin (names/PINs), mobile-blocked | ✅ | `routers/admin.py`, supervisor-gated |
| Laptop variance list after a count | ✅ | `ReviewSessionPage` |
| Show expected SKU **batch + expiry** | ⚠️ | qty + UOM only; design spec exists (2026-06-14), gated on a CC field probe not yet run |
| 4 per-slot options | ⚠️ | 3 of 4 built (confirm / cancel / change-qty); **option 4 — change SKU via search+dropdown, enter batch/expiry/qty — absent** |
| Upload customer SOH + **3-way compare** (physical / CC / customer) | ❌ | export is adjustment-columns only; no SOH import, no 3-column spreadsheet |

**Gap to close:** batch+expiry capture (large, design already drafted), SKU search +
batch/expiry entry at the shelf (medium), customer-SOH upload + 3-way export (large —
this is the comparison artefact the doc is really after).

---

## 4. Data substrate (what the whole loop runs on)

Two shared dependencies sit under every component. They are not workflows; they are
the ground the workflows stand on.

- **Carton dims** — ~409 SKUs captured locally (`data/dims/`, L/W/H ~100%), but
  **0 synced to CartonCloud**. Local dims drive slotting and wave analysis today;
  CC-native wave + cartonisation, and any vehicle-fit maths (A), need them *in CC*.
  This is the existing **dims→CC sync** blocker — work lives in `dim-capture-app/`.
  *Still the most leveraged unblock in the project.*
- **Trustworthy SKU → location** — what component C exists to restore. With F1 now
  closed, the path to a trusted snapshot is open; it needs a real stocktake run and
  the 3-way compare to confirm CC against physical + customer SOH.

---

## 5. Horizon — candidate workflows (open list, grows over time)

Not commitments and not exhaustive — a place to capture directions as they surface.
Each becomes its own spec → plan → build when picked up.

- **Putaway workflow driven by recent SKU locations** — guide the putaway team
  (ZQ630 mobile) to slot incoming stock near where that SKU has recently lived /
  picks fastest, instead of nearest-empty. Feeds and is fed by the location-trust
  substrate (§4) and slotting logic.
- **Pick-by-vision / AI glasses** — hands-free picking for cold-store gloves:
  heads-up display of the next pick, slot, qty; scan/confirm by voice or gesture.
  Sits downstream of B (consumes the same wave/pick data, different presentation
  layer). Hardware + ergonomics validation is the real gate, not the software.
- **KPI / metrics dashboard** — throughput, pick rate, wave cycle time, variance
  trends, dispatch prediction accuracy, dims-coverage. A read-only lens over the
  data the loop already produces; cheap to start, compounds in value as the loop
  fills in.
- **Slotting recommendations** — SKU → bay height (1500/1100/750mm) from
  cube × velocity × replen frequency (already flagged in CLAUDE.md open work).
- **Replenishment rule generator** — set-qty vs max-fill trigger per SKU.
- **(your next idea here)** — keep adding. The architecture in §2 is meant to make
  new floor workflows cheap to bolt on, not a rebuild each time.

---

## 6. Suggested sequence (dependency-ordered — reasoning, not a commitment)

Ordered by what unblocks what, not by appeal:

1. **dims→CC sync** (substrate) — unblocks CC-native cartonisation and is a
   prerequisite for any honest vehicle-fit maths. Highest leverage.
2. **Stocktake: 3-way compare + a real run** (C) — turns the now-fail-loud app into
   a trusted location source for B. The comparison artefact is the missing piece.
3. **The stateful orchestration service** (§2) — the one decision that unblocks B's
   holding area / polling / rollover *and* A's feedback loop. Design once.
4. **Wave orchestration on top of the service** (B) — window, accumulation, rollover,
   per-order override.
5. **Next-day filter + wave→sorter pallet feedback** (A↔B) — closes the loop's
   return arc.
6. **Vehicle allocation + fit** (A) — the largest piece; needs §1 (dims in CC) and a
   vehicle master. The doc's end-state for dispatch.
7. **Horizon workflows** (§5) — picked up as priorities and hardware allow.

---

*Maintenance: when a component's status changes, update its table here and in the
`~/Documents/gocold brainstorming` working copy. Per-feature designs live in
`docs/superpowers/specs/`.*
