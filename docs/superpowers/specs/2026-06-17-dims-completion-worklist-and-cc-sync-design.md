# Dims completion worklist + CartonCloud dim sync — design

**Date:** 2026-06-17 · **Branch at design:** `master`
**Status:** approved (brainstorm), pending spec review → implementation plan

## Problem

~412 carton dims were captured locally in `data/dims/dims_2026-05-13.xlsx`
(Outer L/W/H ~100%, Outer Weight ~69%, Inner-Pack-Qty) but **0 are in
CartonCloud**. Getting them into CC is the roadmap's highest-leverage unblock
(CC-native cartonisation + any future vehicle-fit maths). This is a *sync*
problem, not a capture problem — for the carton level.

### The inner-pack-qty classification (decisive)

The sheet's **Inner Pack Qty** column is the inners-per-outer conversion, and
it splits the SKUs into two physically different kinds:

- **Inner-Pack-Qty = 1 → the SKU *is* an inner/each.** There is no separate
  outer carton; the dims captured for it are already **each-level** dims.
  These need no each-level measurement — they are complete.
- **Inner-Pack-Qty > 1 → a genuine multi-pack carton.** The captured dims are
  the **outer carton**; the each-level L/W/H were never captured.

Measured against `dims_2026-05-13.xlsx` (2026-06-17): **334 of 409** rows are
1:1 inners (complete), **73** are multi-pack cartons (each-level missing), and
**2** have no inner-pack-qty (unclassifiable → flagged). So the physical
each-level measurement task is **~73 SKUs, not ~412.**

### Remaining gaps

1. **Each-level L/W/H** are missing **only for the 73 multi-pack SKUs**.
   They cannot be honestly derived from carton dims — the packing arrangement
   inside a carton is unrecorded, so splitting carton L/W/H into per-each
   L/W/H would be fabricated. (Each *weight* divides cleanly and is derivable;
   linear dims do not.)
2. **~31% of carton/each weights are missing** and exist nowhere but a
   physical scale — they must not be estimated (the R6 discipline).

**Decision:** export a gap worklist (each-level fill needed only for the 73
multi-pack SKUs + 2 unknowns), Jake fills the missing dims physically, then a
single complete sync writes per-UoM dims to CC. Nothing is written to CC until
the dataset is complete.

## Credentials & API reality (verified 2026-06-17)

- The working creds are the **parent `./.env` OAuth2 client**
  (`CC_CLIENT_ID`/`CC_CLIENT_SECRET`/`CC_TENANT_ID`), carrying the
  *WMS Add/Edit Product* role. Smoke test passes.
- The `dim-capture-app/` Bearer creds remain placeholders and target a
  **different** API (`PATCH /products/{id}`, root-level dims). That app is
  **not** the path for this migration — wrong API, no live creds.
- The OAuth2 client talks to `/warehouse-products`, where **dims live per
  unit-of-measure**. A product has `id` (PATCH target), `references.code`
  (match key), and a `unitOfMeasures` map keyed by UoM code (e.g. `PLT`
  baseQty 576, `CT` baseQty 12, `EA` baseQty 1 with `weight`/`volume`/
  `barcode`). Confirmed by a read probe against the real Forage product
  `AE-BLA`.
- This is the **real "The Forage Company"** (`d4810e1e-91ab-43ed-b68e-
  b72bd858b122`) — **production data**, not sandbox. Writes carry production
  risk; gates below are non-negotiable.
- The `/warehouse-products` **write contract has never been exercised**. The
  exact update verb (PATCH vs PUT), per-UoM dims field names, and required
  `Accept-Version` are unconfirmed and discovered via a read probe + the
  1-SKU canary before any fan-out write.

## Scope

**This session (Part 1):** build the gap-worklist export only.
**Deferred (Part 2):** the complete sync, specced here, built after Jake
returns the filled worklist.

---

## Part 1 — gap-worklist export (build now)

### Component

`scripts/build_dims_worklist.py` — orchestrator. Reads CC's live active
Forage products (read-only) ⨝ existing captured dims from
`dims_2026-05-13.xlsx` → writes `data/dims/dims_worklist_<date>.xlsx`.

Supporting unit (new, reusable by Part 2):
`src/dims/capture_sheet.py` — pure parser of the existing capture xlsx into
clean `CapturedDim` records (code, L/W/H mm, weight kg, inner_pack_qty). No
I/O beyond reading the given path. The May sheet has banner/instruction rows
above the real header (real columns begin at row index 2: Priority, Product
Code, Product Name, Units/day, ABC, Outer L/W/H (mm), Outer Weight (kg),
Inner Pack Qty, …) — the parser locates the header row rather than assuming
a fixed offset.

### Source of truth

CC's **live active Forage product list** drives the row set — authoritative,
carries real UoM codes + `baseQty` for validation, and catches SKUs added
since May. Existing captured dims are joined in to pre-fill, so only genuine
gaps are blank.

### Output: one row per CC active SKU

| Group | Columns | Source |
|---|---|---|
| Identity | Product Code, Product Name | CC `references.code`, `name` |
| Kind | `kind` = `inner` (ipq=1) / `carton` (ipq>1) / `unknown` (ipq blank) | computed |
| CC structure | Carton UoM code, Carton baseQty, EA UoM code | CC `unitOfMeasures` |
| Captured (pre-filled) | Inner-Pack-Qty, Outer L (mm), Outer W (mm), Outer H (mm), Outer Weight (kg) | existing xlsx; **blank + highlighted where missing** |
| Each (conditional) | Each L (mm), Each W (mm), Each H (mm) | see below |
| Flags | `baseqty_ne_innerpack`, `no_carton_uom`, `weight_pending`, `ipq_unknown` | computed |

- **Each columns are conditional on `kind`:**
  - `inner` (ipq=1): the captured Outer L/W/H **are** the each dims — these
    rows are complete; each columns are **not** presented for fill (shown as
    "= captured" / left out). No measurement needed.
  - `carton` (ipq>1): each L/W/H are **blank + highlighted — Jake fills**.
  - `unknown` (ipq blank): flagged `ipq_unknown`; Jake resolves the
    conversion before the row can be classified.
- **Carton UoM identification:** the UoM whose `baseQty` equals the row's
  Inner-Pack-Qty. For an `inner` row that is the `baseQty == 1` UoM (the each
  itself). If none matches (or several do), set `no_carton_uom` and leave the
  carton-UoM columns blank — never force a guess.
- **Highlighting:** cells that need filling (missing weights; each L/W/H for
  `carton` rows only) are visually highlighted so the fill task is obvious.
- **Each weight** is derived at sync time (`captured weight ÷ inner-pack-qty`;
  for inners ipq=1 so it equals the captured weight), so it is **not** a fill
  column.
- **Format:** clean xlsx with highlighted gap cells (not the branded
  capture template) — faster to fill, easier to diff on return.

### Testing (this session)

- `capture_sheet.py`: fixture xlsx — header-row detection, unit
  normalisation, missing-weight rows, malformed rows skipped.
- `build_dims_worklist.py`: mock CC product set + fixture xlsx — correct
  join; `kind` classification (inner / carton / unknown) by inner-pack-qty;
  each-fill columns blank only for `carton` rows; blanks where data missing;
  flags fire on baseQty≠inner-pack, no-carton-UoM, and ipq-unknown. **No live
  CC calls in the test suite.**

---

## Part 2 — complete sync (specced now, built after the sheet returns)

### Components

- `src/cc_client/` extension:
  - `get_warehouse_product(code)` — read one product by code (verify step).
  - `patch_product_dims(product_id, uom_dims)` — the write, gated by
    `write_enabled`. Builds the per-UoM update body; maps 404/422/rate-limit
    to typed errors.
- `scripts/sync_dims_to_cc.py` — orchestrator: ingest filled worklist →
  match → build per-UoM payloads → run mode → verify → report.

### Data flow

```
filled worklist xlsx ──> [CompletedDim]            ─┐
                                                    ├ match code → references.code
CC /warehouse-products (read) ──> product(id,UoMs) ─┘
                                   │
   kind == inner (ipq=1):
       EA UoM (baseQty == 1)              ← captured L/W/H + captured weight
   kind == carton (ipq>1):
       carton UoM (baseQty == ipq)        ← captured L/W/H + captured weight
       EA UoM (baseQty == 1)              ← filled each L/W/H + derived weight
                                   │
          dry-run → print intended PATCH, write nothing
          canary  → PATCH one SKU, re-read, assert dims landed
          full    → PATCH all matched, re-read-verify each, report
```

### What gets written (and what doesn't)

- **Inner SKUs (ipq=1):** captured L/W/H + weight → the EA UoM (the each).
  No separate carton UoM is written.
- **Carton SKUs (ipq>1):**
  - **Carton UoM** (baseQty == ipq): captured outer L/W/H + weight.
  - **EA UoM** (baseQty == 1): filled each L/W/H + derived each weight
    (`carton_weight / inner_pack_qty`, only where carton weight present).
- **Missing carton weight** (if any remain): L/W/H written, weight left
  untouched, row reported as `weight_pending`. Never estimated.
- **Idempotency:** PATCH is idempotent; re-runs safe. Products already
  carrying identical dims are skipped as "already current".
- **Untouched:** PLT UoM, EA volume, any field not in scope, every other
  product attribute.
- **Unmatched worklist rows:** skipped and reported, never force-created.

### Safety gate (run modes)

`--mode`, default `dry-run`:

- `dry-run` (default): `write_enabled=False`. Prints per-SKU intended PATCH
  + summary (matched / unmatched / weight-pending / uom-mismatch). Writes
  nothing.
- `--mode canary`: writes exactly one SKU (default first cleanly-matched
  row, overridable), re-reads, asserts dims returned, stops. Requires
  `CC_WRITE_ENABLED=true` **and** explicit
  `--i-understand-this-writes-to-production`.
- `--mode full`: write+verify loop over all matched rows. Same two guards.
  Rate-polite (client already backs off).

Reads use the existing temporary-write-enable pattern (search/report POSTs);
the genuine PATCH is the only thing behind the production guards. Every run
writes a timestamped report to `data/processed/dim_sync_<date>.{csv,md}`.

### Write-contract probe (first implementation step of Part 2)

Before any real write: a documented read+probe spike — read one product,
confirm UoM-dims field names and the update verb/body/`Accept-Version` from
CC's behaviour. The canary then proves it end-to-end on one SKU. If the
contract can't be confirmed safely, stop at dry-run and report — do not guess
on a production write.

### Testing (Part 2)

- `patch_product_dims`: refuses when `write_enabled=False`; correct
  URL/body/version; typed errors on 404/422/rate-limit (mocked transport).
- `sync_dims_to_cc.py`: match/skip/uom-mismatch/weight-pending logic + the
  dry-run differ, against a mock CC. No live calls in the suite.

---

## Out of scope

- Wiring the `dim-capture-app/` (different API, no creds).
- Each-level *volume* (overstated by carton void) and PLT dims.
- Any automated/unattended write — every real PATCH is human-gated.
- Re-capturing carton dims already held locally.

## Open items (resolved during Part 2 probe, not blockers now)

- Exact per-UoM dims field names in `/warehouse-products`.
- PATCH vs PUT for the update.
- Required `Accept-Version` (CLAUDE.md notes warehouse products supports `8`).
