# Run-grouped, stream-split wave picking — design

**Date:** 2026-06-07
**Status:** approved (brainstorm) — revised after code reconnaissance
**Author:** Jake + Claude
**Supersedes/extends:** `2026-06-04-wave-pick-console-design.md`, `2026-06-05-wave-soh-source-of-truth-design.md`

> **Revision note (2026-06-07):** the first draft proposed a 2-stream (bench/pallet)
> model and a new cube classifier. Reading `src/analysis/routing.py` showed both
> already exist: a **3-stream model** (`1_pallet_pick` / `2_wave_bypass` /
> `3_wave_bench`, plus `0_unclassified`) locked with the operator in May 2026, and
> **cube-based pallet classification** (`compute_order_metrics.pallet_fraction_cube`
> + `classify_streams` rule R4). This spec is revised to build *on* that, not
> replace it. Decisions: keep the 3 streams; cube-uncertain (`0_unclassified`)
> rides the pallet sheets plus a measure-list.

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

The MVP is the **paperwork loop**: live data in, run-grouped stream-split
picksheets out, printed at the bench (Zebra ZT411). Everything else stays manual.

- Join dispatch run-prediction into wave generation (two-step, file-based).
- **Group picking by predicted run** (swap `run_group_col` from `delivery_state`
  to `predicted_run` — the hook `plan_waves` already documents).
- Keep the existing **3-stream** split (`1_pallet_pick` / `2_wave_bypass` /
  `3_wave_bench`) within each run.
- **Route dispatch-flagged orders to the pallet stream** (new rule).
- **Produce pallet-stream paperwork** — today the sheet generator handles streams
  2 + 3 only; stream 1 (and `0_unclassified`) produce no sheets. This is the main
  build.
- Keep the **cube-based** pallet trigger that already exists; **calibrate** its
  threshold from history rather than guessing.
- `0_unclassified` (missing-dim / cube-uncertain) orders ride the pallet sheets
  and have their unmeasured SKUs surfaced in a measure-list.
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
   ├─ attach (predicted_run, dispatch_flag) to each AWAITING_PICK_AND_PACK order
   ├─ classify each order into a stream (routing.classify_streams + new R2b):
   │     1_pallet_pick  (cube≥thr | full-pallet line | dispatch-flagged | consignee rule)
   │     2_wave_bypass  (small, all direct-to-pallet SKUs)
   │     3_wave_bench   (small, has a repack/pickbench SKU)
   │     0_unclassified (missing dims → rides pallet sheets)
   ├─ group by predicted_run (run_group_col="predicted_run"); within each run,
   │     streams 2/3 wave with cutoff/early-release; streams 1/0 = one immediate
   │     sheet per (run, stream)
   ├─ emit per wave_id: <wave_id>_picksheet.pdf + _picks.csv + _orders.csv
   └─ index.md: runs × streams × {orders, pick lines, cartons}
                + UNALLOCATED (SOH-miss) section
                + SKUs-to-measure list (cube-uncertain)
   ▼
print at pick bench (Zebra ZT411)
```

## Stream classification (what exists, what changes)

Cube is **already computed** per order. `compute_order_metrics` (routing.py:137)
joins `dims.outer_cube_mm3` (produced by `dim_loader.py:212`) onto every SO line,
sums to `total_cube_mm3`, and derives `pallet_fraction_cube = total_cube_mm3 /
PALLET_USABLE_CUBE_MM3` (pallet ref 1165×1165×1400mm). `pallet_fraction` is the
max of the cube and position methods (belt-and-braces). `classify_streams`
(routing.py:426) already applies, first-match-wins:

```
R1 consignee override_stream set         -> that stream
R2 consignee min_cartons hit             -> 1_pallet_pick
R3 order has a full_pallet_line          -> 1_pallet_pick
R4 pallet_fraction >= threshold          -> 1_pallet_pick   (the cube trigger)
R5 has_unknown_pickbench (missing dims)  -> 0_unclassified
R6 has_pickbench_sku                     -> 3_wave_bench
R7 all_direct_skus                       -> 2_wave_bypass
R8 fallback                              -> 0_unclassified
```

So "use carton dims/cube for the pallet decision" is **R4, already built**. Carton
count is noisy (few clean 100-of-one-carton orders; real pallet picks run ~60–90
mixed cartons), so the cube fraction is the honest signal — this is exactly what
R4 does.

**The one new rule.** Insert a dispatch-flag rule so low-confidence orders build to
a pallet rather than landing on a confident-looking bench sheet:

```
R2b dispatch_flag in {mixed,new_address,stale,no_address,no_run} -> 1_pallet_pick
```

Placed after R2 and before R3 (a distrusted run beats the cube/bench decision).
`dispatch_flag` arrives as a column on `per_order` via the dispatch join (below);
`classify_streams` reads it with `getattr(row, "dispatch_flag", None)` so callers
that don't supply it are unaffected.

**Cube-uncertain.** `0_unclassified` (R5, missing dims) is the spec's
cube-uncertain bucket. Per the approved decision it **rides the pallet sheets**
(handled by a human on a pallet) and its unmeasured SKUs are listed in the index
measure-list. No separate stream needed.

### Threshold calibration

The cube threshold is the existing `pallet_fraction_threshold`
(`DEFAULT_PALLET_FRACTION_THRESHOLD = 0.70`, i.e. 70% of a pallet by cube),
already wired through `WaveRunSettings`, the `--pallet-fraction-threshold` CLI flag,
and the console form. We **calibrate** it, not add a new knob:

- A one-off script computes the `pallet_fraction_cube` distribution over a recent
  snapshot and reports percentiles + where the ~60–90-carton pallet picks fall.
- The recommended default is set at that knee; operators override per-run via the
  existing flag/form. No code change to retune.

## Components

| Component | Type | Responsibility |
|---|---|---|
| `dispatch_link` (`src/analysis/dispatch_link.py`) | **new, small** | Find the latest `data/processed/dispatch/<stamp>/`; load `suggested_runs.csv` + `review.csv`; return `so_id → (predicted_run, dispatch_flag, confidence)`. Plus `attach_dispatch_runs(per_order, link)` → adds `predicted_run` + `dispatch_flag` columns; SO missing from the plan → `predicted_run="no_run"`, `dispatch_flag="no_run"`. Never drops an order. |
| `classify_streams` (routing.py) | **change** | Add rule R2b (dispatch-flag → `1_pallet_pick`). |
| `plan_waves` (routing.py) | **change** | New `include_immediate_streams: bool=False`. When true, also emit one wave per `(receive_date, run_group, stream)` for `1_pallet_pick` and `0_unclassified` with no accumulation (`release_reason="immediate"`), so the existing sheet machinery produces pallet/unclassified sheets. Streams 2/3 keep their cutoff/early-release behaviour. |
| `generate_wave_pick_sheets` (wave_picks.py) | **change** | Pass `include_immediate_streams` through to `plan_waves`. Everything downstream (location resolution, consolidation, walk-sort, `WavePickSheet`) already handles any stream label. |
| `wave_runner` | **change** | After `compute_order_metrics`, call `attach_dispatch_runs`; default `run_group_col="predicted_run"`; thread `dispatch_plan_dir` + `include_pallet_sheets=True` through `WaveRunSettings`; clean-fail (`CartonCloudError`-style) if no dispatch plan is found. |
| `_build_index_md` (wave_runner) | **change** | Add a runs × streams roll-up and a "SKUs to measure" list (SO-line SKUs with `measurement_complete=False`). |
| calibration script (`scripts/calibrate_pallet_cube.py`) | **new** | Cube-fraction distribution → recommended threshold. Run once. |
| CLI / console | **tiny** | CLI already has `--run-group-col` + `--pallet-fraction-threshold`; add `--dispatch-plan`. Console: default `run_group_col` form value → `predicted_run`. |

The existing sheet generators (`generate_wave_pdf`, `write_wave_csvs`) and the
live-SOH placement + per-line UNALLOCATED handling are reused **unchanged** — only
the grouping key, the new rule, and the immediate-stream waves are added.

## Flagged orders — how "review" is satisfied

The chosen wiring is two-step (build_dispatch → wave reads the plan). The human
gate is preserved **without** a new approval UI: orders the predictor is unsure
about (`mixed/new_address/stale/no_address`) and orders missing from the plan
(`no_run`) are auto-routed (rule R2b) to `1_pallet_pick`, where a human builds/sorts
them on a pallet rather than the system guessing them onto a confident-looking
bench sheet. The dispatcher can still correct a run in the existing runs console
before generating waves. This realises the "flagged + full-pallet merge": the
pallet stream now collects `cube ≥ threshold` (R4) ∪ full-pallet line (R3) ∪
dispatch-flagged (R2b) ∪ consignee rule (R1/R2), and `0_unclassified` rides the
same sheets.

## Outputs

Each wave (including the new immediate pallet/unclassified waves) gets its own
directory named by the existing `_make_wave_id`
(`{receive_date}_{run_group}_S{stream_short}_W{idx}`):

```
data/processed/waves/<stamp>/
  index.md
  2026-06-07_RUN-3_S1_W01/  <wave_id>_picksheet.pdf  _picks.csv  _orders.csv   # pallet, run 3
  2026-06-07_RUN-3_S3_W01/  ...                                                # bench, run 3
  2026-06-07_RUN-5_S2_W01/  ...                                                # bypass, run 5
  ...
```

`index.md` lists every wave (run, stream, counts), the UNALLOCATED (SOH-miss)
section, and the SKUs-to-measure list (cube-uncertain).

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

Floor-facing logic is locked by tests (extending the existing `tests/`):

- `dispatch_link`: latest-plan discovery; `suggested_runs.csv` + `review.csv`
  merge; `attach_dispatch_runs` adds `predicted_run`/`dispatch_flag`; SO missing
  from plan → `no_run`; never drops an order.
- `classify_streams` R2b: each flagged value → `1_pallet_pick`; non-flagged
  unaffected; absent `dispatch_flag` column is harmless (existing tests stay green).
- `plan_waves` immediate streams: `include_immediate_streams=True` emits one wave
  per (run, stream) for `1_pallet_pick` and `0_unclassified`, no accumulation;
  streams 2/3 unchanged when false.
- grouping reconciliation: Σ(lines across all wave sheets) == total input pick
  lines + UNALLOCATED; nothing dropped or double-counted.
- `wave_runner` end-to-end on a fixture (SOs + dims + a fixture dispatch plan) →
  expected per-(run,stream) sheet set; clean-fail when no plan present.
- the existing read-only guard + full suite stay green.

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
