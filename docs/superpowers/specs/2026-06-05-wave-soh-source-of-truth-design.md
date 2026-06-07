# Wave gen: live SOH as the source of truth

**Date:** 2026-06-05
**Status:** Approved — ready for implementation plan
**Area:** `src/wave_runner.py`, `src/analysis/wave_picks.py`, `src/output/pdf_picksheet.py`,
`src/web/app.py`, `src/web/jobs.py`, tests

## Problem

Wave pick generation currently resolves each SKU's pick location from a **stale
`data/processed/assignments*.csv`** (step 7 in `run_wave_generation`), with a
location-master spreadsheet (`data/locations/*.xlsx`, step 6) and live
stock-on-hand only as an **off-by-default fallback** (`soh_fallback=False`, step 8)
that ranks *below* the stale CSV.

A stale spreadsheet cannot be the source of truth for where stock physically is —
it drifts the moment putaway or replen moves a pallet. Sending a picker to a bay
that a day-old CSV claims holds a SKU is exactly the floor breakage the project
forbids.

## Goal

Every wave gen resolves SKU→location from a **fresh CartonCloud stock-on-hand pull**.
No spreadsheet or CSV is ever a placement source. SKUs that live SOH cannot place
still ride the wave, flagged `unallocated` for a human to locate.

## Decisions (operator-confirmed)

1. **No stale fallback, ever.** A SKU with no live SOH location is **not** dropped
   and **not** read from the old CSV/xlsx — its line goes on the wave flagged
   `unallocated`.
2. **Always pull fresh.** Every gen blocks on a live SOH report-run (POST + poll
   to SUCCESS). No caching window.
3. **Walk-order from SOH names.** Drop the location-master xlsx; infer the route by
   parsing SOH location names through the existing `locations/grammar.py`.
4. **Hard-fail on total SOH failure.** If the SOH pull errors or times out, the run
   aborts with a clear error. An all-`unallocated` wave is not a wave; better to
   stop than send pickers out blind.
5. **Pick-face selection for multi-location SKUs.** A SKU with stock in several bays
   resolves to its pick-face (grammar `role_by_grammar == "pick_face"`, lowest
   `position`; tiebreak by walk order). One location per SKU enters the lookup.

## Background facts (verified in code, 2026-06-05)

- `get_sku_locations` (`src/cc_client/queries.py`) already does the SOH report-run
  aggregated by `location` + `productType` + `unitOfMeasure`, filters client-side
  by product code, and returns
  `{product_code, location_name, location_id, qty, uom}` rows — one per
  (product, location, uom) bucket. It polls until SUCCESS (`max_wait=300s`).
- `grammar.parse_location_name` / `grammar.classify_locations` turn a location
  name (`XX-YY-ZZ` or `XX-YY-ZZ-WW`) into
  `aisle, bay, level, sublevel, position, role_by_grammar, bay_height_mm`. This is
  the walk-order structure — no xlsx required.
- The `locations` DataFrame param of `generate_wave_pick_sheets` is **vestigial**:
  documented but never read in the function body. Walk-order is built from the
  `aisle/bay/level/sublevel` columns carried on each lookup row, sorted by
  `_walk_sort_key`.
- Whole-order skip-on-missing-location lives at
  `wave_picks.py:386–423`: any unlocatable SKU sends the entire order to
  `skipped_orders`.

## Design

### 1. `wave_runner.py` — data sourcing

Replace steps 6–8 of `run_wave_generation`:

- **Remove** the location-xlsx load (step 6) and the assignments-CSV load (step 7)
  as placement sources. Delete `locations_path` and `assignments_path` from the
  resolution flow. (Keep reading `data/dims/` and `data/routing/` unchanged.)
- **SOH pull becomes mandatory and primary, every gen:**
  - Resolve `customer_id` from the SO lines as today.
  - Call `get_sku_locations(client, customer_id=…, product_codes=<order SKUs>)`.
  - On **any** failure (`CartonCloudError`, timeout, empty result): **raise** and
    abort the run with a clear, emitted error — do not silently continue.
- **Enrich** each SOH row by parsing `location_name` through
  `grammar.parse_location_name`, attaching `aisle, bay, level, sublevel, position,
  role_by_grammar`.
- **Collapse to one location per SKU** with the pick-face rule:
  - Among a SKU's SOH rows, prefer `role_by_grammar == "pick_face"`.
  - Within pick faces, lowest `position` wins (1 before 2).
  - Tiebreak by walk order (`aisle, bay, level, sublevel`).
  - If a SKU has only reserve locations (no pick face), take the best reserve by
    walk order (still a real, live location — not unallocated).
  - Build the `sku_locations` DataFrame:
    `product_code, location, aisle, bay, level, sublevel`.
- **Remove the `soh_fallback` field** from `WaveRunSettings` and stop threading it
  through `_settings_dict`.
- Emit a progress event around the pull (`"pulling live stock…"` → count of
  (SKU, location) rows resolved) so the console shows the wait.

### 2. `wave_picks.py` — generation

- `generate_wave_pick_sheets`: drop the `locations` and `assignments` params;
  rename `sku_locations_fallback` → `sku_locations` as the sole placement source.
  Update `_build_sku_location_lookup` to take just the one frame (or inline it).
- **Replace the whole-order skip** (`386–423`): when a line's SKU is absent from
  the lookup, **still append the line** with
  `location="UNALLOCATED"`, `aisle/bay/level/sublevel = NA`, `unallocated=True`.
  The order is **not** sent to `skipped_orders`.
- `skipped_orders` is now reserved for genuinely empty orders ("no SO lines in
  extract") only.
- **Walk-sort:** `_walk_sort_key` pushes `UNALLOCATED` rows to the **end** of the
  route (after all real bays), so the picker walks a clean route and the
  unallocated lines are grouped at the foot.
- **Consolidation:** unallocated lines group together (by `product_code`) with no
  walk position; they still carry qty and contributing so_refs.
- **Summary** gains `n_lines_unallocated` and `n_skus_unallocated`; keep
  `n_orders_skipped` for the empty-order case.
- Add an `unallocated` boolean column to the consolidated pick frame so the PDF and
  CSV can flag it.

### 3. `pdf_picksheet.py`

- Render unallocated picks in a clearly separated, highlighted block at the foot of
  the sheet — heading e.g. **"⚠ UNALLOCATED — no live stock location, locate
  manually"** — listing SKU, name, qty, contributing orders. They must not blend
  into the numbered walk route.

### 4. Console (`web/app.py`, `web/jobs.py`)

- Remove the `soh_fallback` form field and its plumbing into `WaveRunSettings`
  (SOH is always on now).
- Surface the unallocated count in the run summary / progress so the supervisor
  sees it before printing.

## Data flow (after)

```
open SOs ──► snapshot ──► dims ──► routing ──► classify
                                                   │
                                                   ▼
                              live SOH report-run (get_sku_locations)   ◄── mandatory, fresh, every gen
                                                   │
                              parse names via grammar → aisle/bay/level
                                                   │
                              one pick-face location per SKU
                                                   ▼
                              generate_wave_pick_sheets(sku_locations)
                                   │                         │
                          located lines               unallocated lines
                          (walk-ordered)              (flagged, end of sheet)
                                   └─────────► PDF + CSV per wave
```

## Error handling

- **SOH pull fails / times out / returns nothing:** abort the whole run, emit a
  clear error, write no wave outputs. (Decision 4.)
- **A SKU has no SOH row:** that line is `unallocated`, order still waves.
  (Decision 1.)
- **A location name doesn't parse the grammar** (`valid=False`): treat as a real
  location with no walk structure — it sorts to the end among parsed bays but is
  NOT `unallocated` (stock genuinely lives there; the picker can read the label).
  Log it so malformed names surface.

## Testing

- `test_wave_consolidation.py` / `test_wave_runner.py`:
  - SOH map is the sole placement source; assignments/xlsx no longer consulted.
  - A SKU absent from SOH keeps its order on the wave and produces an
    `unallocated` line (order NOT in `skipped_orders`).
  - Walk-order is inferred correctly from SOH location names (grammar parse).
  - Multi-location SKU resolves to the pick face, not reserve.
  - Total SOH failure raises / aborts the run (no partial output).
  - `n_lines_unallocated` / `n_skus_unallocated` reported in summary.
- Reuse the live-shape fixture behind `test_sku_locations` for the SOH row shape.

## Out of scope

- Writing anything back to CC (client stays read-only).
- SOH caching / TTL (explicitly rejected — always fresh).
- Re-introducing any spreadsheet as a placement source.
- Fixing the upstream numeric-SKU SOH gap itself — this design makes that gap
  *visible* (as `unallocated`) rather than silently dropping orders; the root-cause
  follow-up is tracked separately.

## Floor-safety notes

- Every gen now blocks on a SOH report-run (seconds to ~minutes). The console must
  show the wait so the supervisor doesn't think it hung.
- The known numeric-SKU SOH gap now manifests as visible `unallocated` lines a
  human resolves at the bench — the safe resolution to that open follow-up, not a
  regression.
- Shadow-validate against a real morning's open orders before this replaces the
  current path on the floor: confirm the unallocated set is small and matches
  reality, and that walk-order from SOH names matches the current xlsx-derived
  route.
