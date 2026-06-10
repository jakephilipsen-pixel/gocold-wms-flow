# Carton-Aware Pick Lines — Design

**Date:** 2026-06-11
**Status:** Approved (Jake, 11 Jun 2026)
**Scope:** Wave pick generation (`src/analysis/wave_picks.py` + new `src/analysis/carton_split.py`)

## Problem

Forage orders everything in eaches in CartonCloud — all 93,480 SO lines in the
90-day extract are `EA / Each`. For 73 of 409 SKUs the "each" is a retail unit
inside a carton (`inner_pack_qty` of 2–12, mostly 4 and 6). When an order asks
for, say, 24 EA of a 6-per-carton SKU, the picker correctly grabs 4 cartons off
the storage (reserve) pallet — but the picksheet pointed them at the pick face,
so the system's picture of where stock came from is wrong, and the printed
quantity (24) doesn't match what was physically handled (4 cartons).

Two defects in the current pipeline cause this:

1. **Quantities are consolidated blind to UOM.** `wave_picks.py`
   (`qty_cartons=("quantity", "sum")`) treats every SO-line quantity as
   cartons. For the 334 SKUs where each *is* the carton this is accidentally
   correct; for combo SKUs it is wrong whenever the quantity spans full
   cartons.
2. **Location selection always prefers the pick face.** The per-SKU lookup
   sorts pick-face role first and collapses to a single location, so a
   full-carton pick is never routed to the reserve pallet that the picker
   actually uses.

## Sizing (90 days of real Forage data, snapshot 2026-05-13)

- 73/409 SKUs are each/ctn combos; they carry 21.2% of all order lines.
- Only **814 lines (~9/day)** have an EA qty ≥ 1 full carton, spread across
  **322 orders (~4/day, 5.3% of orders)**.
- 82.6% of convertible lines are exact carton multiples; 142 lines have
  leftover eaches.
- Most flagged orders need 1–2 reserve cartons; a small tail runs 15+.
- Highest-frequency SKUs: TSP-SAR (4/ctn), FD-BAR (6/ctn), TSP-TUN, TSP-MAC,
  TSP-1SA.

## Decision

**Option B — convert lines in place.** No order-level separation: these
orders are predominantly large and already land in the pallet/bypass streams,
so fixing the lines fixes the problem wherever the order routes. (Order-level
stream separation — Option A — and a standalone shadow report — Option C —
were considered and declined 11 Jun 2026.)

## Design

### 1. Line splitting — new module `src/analysis/carton_split.py`

Runs after orders are pulled and dims joined, before location resolution and
consolidation. For each SO line:

- If the SKU's `inner_pack_qty > 1` **and** `quantity >= inner_pack_qty *
  min_full_cartons`:
  - Emit a **carton line**: `quantity // inner_pack_qty` cartons,
    `pick_uom = "CTN"`, carrying the original each-qty for display.
  - If `quantity % inner_pack_qty > 0`, emit a **remainder line** with the
    leftover eaches, `pick_uom = "EA"`.
- Otherwise the line passes through untouched with `pick_uom = "EA"`.

Pass-through cases (behaviour identical to today): SKUs with
`inner_pack_qty` of 1 or missing from dims, combo lines under the threshold.
`min_full_cartons` defaults to 1 and is exposed as a parameter.

### 2. Location routing — per-line role selection in `wave_picks.py`

`build_sku_location_lookup` changes from "one location per SKU, pick-face
first" to retaining **all** live SOH locations per SKU, each tagged with its
role (pick face vs reserve) by joining the CC locations export
(`src/locations/cc_loader.py`: `is_pick_face` from `efficiency >= 21`, plus
grammar `role_by_grammar`). Selection then happens per pick line:

- **CTN lines** → best *reserve* location holding stock: largest qty first,
  walk-order grammar as tiebreak. If the SKU's only stock is at the pick
  face, fall back to the pick face and flag the line `reserve_unavailable`
  (visible, not silent).
- **EA lines** → existing pick-face-first behaviour, unchanged.

Locations present in SOH but absent from the CC export resolve role via
`role_by_grammar`; if still unknown, treat as reserve.

### 3. Picksheet output

- Carton lines print as `4 CTN (24 EA)` at the reserve location.
- Consolidation groups by **(SKU, pick_uom)** so carton picks and each picks
  of the same SKU never merge into one row. CTN and EA components of the same
  original line may land at different locations — that is the point.
- Walk-order sorting unchanged; reserve locations sort by the same grammar.
- Wave summary gains `n_lines_carton_pick` and `n_carton_picks_no_reserve`;
  the picks console (`src/web/`) surfaces both alongside the existing
  unallocated counts.
- `min_full_cartons` is exposed on the picks console run form like
  `pallet_fraction_threshold`.

### 4. Edge handling

| Case | Behaviour |
|---|---|
| No SOH anywhere for SKU | `UNALLOCATED`, end of walk — unchanged from today |
| Reserve qty < required cartons | Route to the largest reserve anyway, print shortfall flag. No splitting across multiple reserves (~9 lines/day doesn't justify it) |
| Stock only at pick face | CTN line routed to pick face, flagged `reserve_unavailable` |
| `inner_pack_qty` missing/1 | Pass through, today's behaviour |
| Remainder eaches | Separate EA line at pick face |

### 5. Testing & validation

- **Unit tests, splitter:** exact multiple (24 EA @ 6 → 4 CTN), remainder
  (27 EA @ 6 → 4 CTN + 3 EA), under threshold (5 EA @ 6 → pass-through),
  ipq = 1, SKU missing from dims, `min_full_cartons = 2`.
- **Unit tests, location chooser:** reserve available, multiple reserves
  (qty then walk-order), pick-face-only fallback + flag, no stock, role
  unknown → reserve.
- **Regression diff:** regenerate a recent wave with the feature enabled and
  confirm all non-combo lines are identical to the current output; review
  converted lines against TSP-SAR / FD-BAR floor reality before relying on
  the sheets.

## Out of scope / future

- **CC write-back for stock allocation.** This design fixes what the
  picksheet tells the picker; CartonCloud still decrements stock wherever the
  pick is confirmed in CC. Pushing the chosen location/UOM back into CC so
  allocation matches reality is a later phase, gated behind the existing
  read-only boundary and explicit approval (per CLAUDE.md safety rules).
- Order-level stream separation for carton-heavy orders (Option A) — revisit
  if the in-place conversion proves insufficient on the floor.
- Wave-generation stalling on missing/empty SOH locations — parked
  separately; it is a data-source issue, not part of this feature.
