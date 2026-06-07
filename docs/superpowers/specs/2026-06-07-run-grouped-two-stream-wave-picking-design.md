# Run-grouped, two-stream wave picking — design

**Date:** 2026-06-07
**Status:** approved (brainstorm) — pending spec review
**Author:** Jake + Claude
**Supersedes/extends:** `2026-06-04-wave-pick-console-design.md`, `2026-06-05-wave-soh-source-of-truth-design.md`

## Problem

The wave-pick generator and the dispatch run-predictor are both built and green,
but they are **separate subsystems**. Waves group by `delivery_state`
(`wave_runner.py:64`); dispatch separately predicts which delivery run each open
order belongs to. The floor needs picking organised **by delivery run**, and it
needs the big orders that are built straight onto a pallet pulled out of the
carton pick bench. Today neither happens: the picker can't pick a run at a time,
and pallet-sized orders clog the bench.

Two operator problems to solve:

1. **Pick by run.** Each delivery run should produce its own pick paperwork so a
   picker works one run at a time and cartons land sorted for dispatch.
2. **Pull pallet picks off the bench.** Large orders (and orders whose run is
   uncertain) should route to a separate **pick-to-pallet** stream, not the
   carton bench.

## Goals (MVP — "operational ASAP")

The MVP is the **paperwork loop**: live data in, run-grouped two-stream
picksheets out, printed at the bench (Zebra ZT411). Everything else stays manual.

- Join dispatch run-prediction into wave generation (two-step, file-based).
- Group picking by predicted run.
- Within each run, split orders into **BENCH** (carton picks) and **PALLET**
  (pick-to-pallet) streams.
- Drive the pallet decision from **carton cube**, not carton count.
- Surface uncertain/unmeasured orders rather than silently mis-routing them.
- Read-only against CartonCloud throughout. No CC writes.

## Non-goals (explicitly out of the MVP cut)

- **Phase 2:** live scan-verify bench UI (scan SKU → confirm qty → tick line per
  run/stream). This is the eventual "routing through the pick bench" target.
- **Phase 3 (separate track):** dims→CartonCloud sync go-live — gated by the
  `dim-capture-app` security work (audit findings B1/B2/B3). Independent of this
  picking loop.
- Line-level stream splitting (one order spanning both streams). MVP routes a
  whole order to one stream; line-level is a Phase-2 refinement.
- A console "edit & approve runs" UI. In the MVP the routing *is* the gate
  (see §"Flagged orders").

## Flow

```
CartonCloud (read-only)
   │
   ├─ build_dispatch (existing) ──▶ plan/<stamp>/suggested_runs.csv
   │      per SO: so_ref, so_id, predicted_run, confidence, flag
   │      flag ∈ {stable, mixed, new_address, stale, no_address}
   │      (review.csv holds the flagged subset)
   │            │  dispatcher glances at the review queue in the runs console
   │            │  (human gate); uncertain orders are expected to fall to PALLET
   ▼            ▼
generate_waves  ◀── reads suggested_runs.csv + review.csv  +  live SOH  +  local dims
   │
   ├─ attach (predicted_run, flag) to each AWAITING_PICK_AND_PACK SO
   ├─ classify each order: BENCH or PALLET (see §Stream classification)
   ├─ for each RUN, for each STREAM present:
   │     emit run_<R>_<stream>_picksheet.pdf + run_<R>_<stream>_picks.csv
   │                                          + run_<R>_<stream>_orders.csv
   └─ index.md: runs × streams × {orders, pick lines, cartons}
                + UNALLOCATED (SOH-miss) section
                + cube_uncertain SKUs-to-measure list
   ▼
print at pick bench (Zebra ZT411)
```

## Stream classification (the core rule)

For each order, compute **estimated cube**:

```
order_cube_mm3 = Σ over lines ( line_qty × dims.outer_cube_mm3[sku] )
```

`outer_cube_mm3` is already produced per SKU by `dim_loader` (`dim_loader.py:212`),
so no new dimension work is required.

An order routes to the **PALLET** stream if **any** of:

1. **Cube trigger:** `order_cube_mm3 (from known-dim lines) ≥ PALLET_CUBE_THRESHOLD`.
2. **Flagged address:** the dispatch `flag` is in
   `{mixed, new_address, stale, no_address}`, or the SO is absent from the plan
   (`flag = no_run`).
3. **Cube uncertain:** order cube from known lines is below threshold **but** the
   order contains one or more lines whose SKU has no dims — we cannot rule out
   that it is large, so it routes to PALLET/review and its missing SKUs are
   listed for measurement.

Otherwise the order routes to **BENCH** (stable run, all lines measured, cube
below threshold).

Rationale: carton count is noisy (few clean 100-of-one-carton orders; real pallet
picks run ~60–90 mixed cartons), so cube is the honest signal. This realises the
`patterns.py:51` TODO ("replace with estimated cube > pallet") and lets us
**retire the brand-gated `detect_full_pallet_lines` heuristic** as the primary
trigger. Single-SKU full-pallet orders are high-cube (→ PALLET) and also
address-predictable (→ grouped onto their stable run by the dispatch learner), so
they need no special-case logic.

### Threshold calibration

`PALLET_CUBE_THRESHOLD` is a configurable cube in m³ (default surfaced as a
constant + `--pallet-cube` CLI flag / console field). Default is **calibrated
from history**, not guessed:

- A one-off calibration step computes the order-cube distribution over recent SOs
  (95k+ historical line-items × dims) and reports where the ~60–90-carton pallet
  picks fall.
- The default threshold is set at that knee. Operators can override per-run
  without a code change.

## Components

All new modules are small, single-purpose, and unit-tested in isolation.

| Component | Type | Responsibility |
|---|---|---|
| `run_link` | new | Load `suggested_runs.csv` (+ `review.csv`); return `so_id/so_ref → (predicted_run, flag, confidence)`. SO in the wave snapshot but missing from the plan → `flag=no_run`. Never drops an SO. |
| `stream_classifier` | new (absorbs cube logic) | Compute `order_cube_mm3` from dims; apply the §Stream classification rules; return per-order `stream ∈ {BENCH, PALLET}` + a reason (`cube`, `flagged:<flag>`, `cube_uncertain`, `no_run`). |
| `cube` helper | new (small) | `order_cube_mm3(order_lines, dims)` + missing-dim detection. Pure, trivially testable. |
| `wave_runner` | change | `run_group_col` → `predicted_run`; add `stream` as the secondary split key; thread `pallet_cube_threshold` and the plan path through `WaveRunSettings`. |
| calibration | new script/notebook | Order-cube distribution → recommended default threshold. Run once; documents the chosen default. |
| `src/web` console | minimal change | Run page surfaces the runs × streams breakdown and the cube_uncertain list. No scan-verify UI (Phase 2). |

The existing sheet generators (`generate_wave_pick_sheets`, `generate_wave_pdf`,
`write_wave_csvs`) are reused unchanged — only the grouping key and sheet labels
change. Live-SOH placement and per-line UNALLOCATED handling (recent work) carry
through per stream untouched.

## Flagged orders — how "review" is satisfied

The chosen wiring is two-step (build_dispatch → wave reads the plan). The human
gate is preserved **without** a new approval UI: orders the predictor is unsure
about (`mixed/new_address/stale/no_address`) and orders missing from the plan
(`no_run`) are auto-routed to the PALLET stream, where a human builds/sorts them
on a pallet rather than the system guessing them onto a confident-looking bench
sheet. The dispatcher can still correct a run in the existing runs console before
generating waves. This is the "flagged + full-pallet merge" the operator asked
for: PALLET = `cube ≥ threshold` ∪ `flagged-address` ∪ `cube_uncertain`.

## Outputs

```
data/processed/waves/<stamp>/
  index.md
  run_<R>_bench_picksheet.pdf   run_<R>_bench_picks.csv   run_<R>_bench_orders.csv
  run_<R>_pallet_picksheet.pdf  run_<R>_pallet_picks.csv  run_<R>_pallet_orders.csv
  ...
```

`index.md` lists every (run, stream) with order/pick-line/carton counts, the
UNALLOCATED (SOH-miss) section, and the `cube_uncertain` SKUs-to-measure list.

## Error handling (read-only)

- **No/stale dispatch plan:** fail clean with a clear message (consistent with the
  recent `CartonCloudError` clean-fail commit) rather than emitting run-less sheets.
- **SOH miss for a SKU:** existing per-line UNALLOCATED handling carries through,
  per stream.
- **SO missing from plan:** `flag=no_run` → PALLET, listed in the index.
- **Missing dims on a line:** contributes to `cube_uncertain`; SKU surfaced for
  measurement. Never silently treated as zero-cube on a bench sheet.
- No CC writes anywhere; `write_enabled` stays off; the read-only guard test stays
  green.

## Testing

Floor-facing logic is locked by tests:

- `cube`: order cube sums correctly; missing-dim lines flagged.
- `stream_classifier`: cube ≥ threshold → PALLET; flagged-address → PALLET;
  below-threshold + missing dims → PALLET (`cube_uncertain`); stable + measured +
  below threshold → BENCH; reason string correct for each.
- `run_link`: matched SO; SO missing from plan → `no_run`; flag/confidence
  passthrough.
- grouping reconciliation: Σ(lines across all run×stream sheets) == total input
  pick lines + UNALLOCATED; nothing dropped or double-counted.
- end-to-end on a fixture snapshot (SOs + dims + a fixture plan) → expected sheet
  set.
- read-only guard regression stays green.

## Assumptions & open questions

- **Run definitions.** We use dispatch-predicted run labels as-is for grouping.
  CLAUDE.md flags "how runs are currently defined / road clusters" as a separate
  conversation; the dispatcher-review step is where bad labels get corrected for
  MVP. Revisit run definition quality after first floor use.
- **Threshold value** is set by the calibration step against real history before
  go-live; the constant is a starting point, tuned on the floor via flag.
- **Order-level routing** (whole order to one stream) is the MVP simplification;
  line-level splitting is deferred to Phase 2.

## Phasing

1. **Phase 1 — ASAP go-live (this spec):** the paperwork loop above.
2. **Phase 2:** live scan-verify bench UI; optional line-level stream split.
3. **Phase 3 — separate track:** dims→CC sync go-live (dim-capture-app B1/B2/B3).
```
