# DIMS_UOM_STATE.md — which UoM carries Forage carton dims, and why

State of the dims→CartonCloud sync, by unit-of-measure. Source of truth for "where do dims go".

_Last updated: 23 Jun 2026 (M-DIMS-5d each-write built, not yet run live)._

## TL;DR

- **Each / Base UoM (`defaultUnitOfMeasure`) — THE dims pipeline.** Automated target. Every live
  Forage SKU has one; all 455 names are valid, so the each accepts dims. Written in **cm**.
  Built: `dims_write.run_each_bulk` + `scripts/run_dims_each_bulk.py` (M-DIMS-5d). Live-gated
  (`CC_LIVE_PROMOTION`, default-closed), batch hard stop, fail-fast, `finalize_exit` safeguard.
  **Not yet run live** — first run is Jake's deliberate few-SKU cm test (`--only …`), eyeballed
  in CC, before any bulk.
- **CT carton UoM — CLOSED, not written.** Will NOT be written by automation. Two reasons:
  1. **CC name-validation.** Writing any dim sub-field forces CC to validate the whole CT UoM
     object; every live CT UoM is named `"CT"` (2 chars), below CC's 3–64 char rule → 422 on
     `/unitOfMeasures/CT/name`. (Probe: all 81 live CT UoMs are 2-char shells, 0 valid —
     `scripts/probe_ct_uom_names.py`.)
  2. **No-edit-on-master policy.** Fixing CT names is a manual CC-UI operation; we do not edit
     live-master UoM names from automation. So the 5c CT-write path
     (`dims_write.run_ct_bulk` / `scripts/run_dims_ct_bulk.py`) stays in the tree but is **out of
     automated scope** — superseded by the each-write.

## Units

CC's UoM `length`/`width`/`height` are **centimetres**; weight is **kg**. The capture template is
in **mm**, converted mm→cm (÷10) at the write boundary by `dims_write.captured_cc_dims_table`.
(See CLAUDE.md gotcha #6.)

## Tracking — the 15 live SKUs that already carry each (Base UoM) dims (read-only census, 23 Jun 2026)

Recorded so the each-write's effect on them is explicit, not silent. **All 15 are in the captured
dims table, so the each-write's idempotent diff CORRECTS each of them in place** to the captured
cm value — no special-casing. Their current stored values are in the WRONG unit (two regimes):

| Regime | Count | SKUs | Example (stored → captured cm) |
|---|---|---|---|
| **mm (10× too big)** — the M-DIMS-5b EA writes | 4 | BB-2CH, BE-1CH, BF-GRC, BI-BOM | BB-2CH `230` → `23.0` |
| **metres (~100× too small, some garbage)** — prior CC-UI/other entry | 11 | BI-CEH, BI-CHO, BI-CMI, BI-COI, BI-CPE, BI-CSU, BI-HON, BI-PES, BI-SRI, BI-SUG, BI-VSU | BI-CEH `0.21` → `20.5` (and stray values like BI-COI W=`0.8`) |

When the each-write runs: each of these 15 PATCHes from its wrong-unit value to the captured cm
value (diff is non-empty), so the bulk run cleans them up for free. SKUs whose each already matches
the captured cm value will no-op. Census artifact: `data/dims/each_uom_census.csv`.

## Engine (shared by 5c-CT, 5d-each, sandbox soak)

`dims_write.bulk._run_bulk` — 5a gate → ONE batch hard stop → paced fail-fast →
`write_and_verify` (PATCH `/warehouse-products/{id}` UoM dims, Accept-Version 8, JSON-Patch
`op:add`) → UoM-specific read-back → W4 idempotency. The ONLY thing the each-write changes vs the
CT write is the UoM resolver: `resolve_default_uom` (the each) instead of `resolve_ct_uom`.

## Deferred

- GUI — deferred; prove the pipeline (this) first.
- The CT UoM names — Jake fixes by hand in the CC UI if/when CT dims are ever wanted.
