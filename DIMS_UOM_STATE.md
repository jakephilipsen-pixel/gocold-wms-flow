# DIMS_UOM_STATE.md — which UoM carries Forage carton dims, and why

State of the dims→CartonCloud sync, by unit-of-measure. Source of truth for "where do dims go".

_Last updated: 25 Jun 2026 (engine now writes metres ÷1000 + capture-sheet pre-flight — see banner;
24 Jun was the units correction)._

## ⚠⚠ UNITS CORRECTION — CC stores METRES, not centimetres (Jake, 24 Jun 2026)

The earlier "cm confirmed live" was **wrong**. CC's UoM `length`/`width`/`height` are **metres**.
Conversion at the write boundary must be **mm→m (÷1000)**, NOT mm→cm (÷10). A 300 mm carton edge
is `0.3`, not `30`.

**Corroboration:** (1) Jake confirmed metres against CC, 24 Jun. (2) The "cm confirmed" eyeball
read the numbers `23×14×20.5` as cm — but in a metres field those are 23 m × 14 m × 20.5 m
(absurd). (3) The census below already found 11 SKUs stored as `0.21`-style values and mislabeled
them "wrong (metres)"; under the metres truth **those 11 were the only correct entries**, and the
cm engine would have inflated them 100×.

**Impact:**
- ✅ The Python engine (`dims_write.captured_cc_dims_table`, now `mm_to_m`, `MM_PER_METRE=1000`)
  **writes metres (÷1000)** as of 25 Jun 2026 — branch `fix/dims-metres-and-preflight` (TDD,
  CC-mocked, NOT run live). It replaced the wrong `mm_to_cm` / `MM_PER_CM=10` (÷10).
- ⚠ The dims **already written live are still the wrong magnitude** in CC's metres field, and are
  **NOT separately corrected**: the **132 SKUs from 5d went in as cm (~100× too big)**; the sandbox
  `sHL-BWC` and the 4 EA 5b writes went in as mm (~1000× too big). The next deliberately-armed
  metres bulk run's idempotent W4 diff overwrites them (a stored `23` ≠ the new `0.023` → diff
  non-empty → PATCH corrects; an already-correct metres value no-ops). A known, recorded state —
  Jake owns that gated re-run.
- The **app** (`dim-capture-app`) write boundary was corrected to mm→m (÷1000) on 24 Jun 2026 —
  `backend/src/services/ccClient.ts`.

_Everything below this banner that says "cm" predates the correction — read it as "metres" for the
target unit; the wrong-unit analysis in the tracking table is now inverted (see notes there)._

## TL;DR

- **Each / Base UoM (`defaultUnitOfMeasure`) — THE dims pipeline.** Automated target, written in
  **metres** (÷1000, engine fixed 25 Jun 2026). Built: `dims_write.run_each_bulk` +
  `scripts/run_dims_each_bulk.py` (M-DIMS-5d). Live-gated (`CC_LIVE_PROMOTION`, default-closed),
  batch hard stop, fail-fast, `finalize_exit`. ⚠ The earlier live bulk wrote **132 SKUs in cm**
  (the old ÷10 bug) before halting on the name-poison finding — those 132 are the WRONG magnitude
  in CC's metres field and get corrected by the next metres re-run (idempotent diff: `23 ≠ 0.023`
  → PATCH; already-metres SKUs no-op).

## ⚠ The name-poison finding (M-DIMS-5d live bulk, 23 Jun 2026)

The bulk fail-fast halted on **HL-6VA** with a 422 on `/unitOfMeasures/CT/name` — **even though
the write targeted EA, not CT.** Conclusion: **CartonCloud validates the ENTIRE product UoM set on
any UoM dims PATCH.** So a UoM with an invalid name (the carton `CT`, 2 chars) poisons a dims write
to *every* UoM on that product, **including the each**. The each-probe missed this — it checked
each names were valid but not that a sibling CT name would block the each write.

**Guard added (`block_on_poisoning_uom`, on by default in `run_each_bulk`):** before writing a
SKU's each, `find_poisoning_uoms` inspects the whole UoM set; if ANY UoM name fails CC's 3–64 rule
the SKU is **skipped** — `"skipped — has a UoM with an invalid name (poisons whole-product save):
{codes}"` — not attempted, so the run completes the clean cohort instead of fail-fasting.
**General, name-length based (not CT-hardcoded)** — robust to any short/long-named UoM; and a CT
UoM with a *valid* name would NOT be skipped, so fixing names auto-unblocks. Fail-fast stays for
genuine unexpected write failures.

**Cohort math (full disarmed preview, 23 Jun, with the guard):** 180 writable · 135 already-correct
(incl. the 132) · **5 name-poisoned & skipped** (FB-PSM, HL-6HH, HL-6SC, HL-6VA, TSP-OYS) · 135 no
captured dims. So in the *current* sheet only **5** SKUs are blocked from getting each dims by the
CT-name problem — not ~88: the other CT-bearing SKUs had their carton dims deleted, so they have no
each dims to write anyway. The run now completes; those 5 attach once their CT name is fixed in CC.

**Open question for Jake (not Code):** is the 2-char CT name fixable on live master (CC UI bulk
edit / CC support / a different API)? If 5 (or more, as new dims are captured) SKUs can never get
dims because of an unfixable name, that's a rulebook gap worth one more push before accepting.
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

CC's UoM `length`/`width`/`height` are **metres** (corrected 24 Jun 2026 — see top banner);
weight is **kg**. The capture template is in **mm**, so the write boundary converts
**mm→m (÷1000)**. ✅ `dims_write.captured_cc_dims_table` (via `mm_to_m`, `MM_PER_METRE=1000`) now
does this (fixed 25 Jun 2026); the app's `ccClient.ts` already converted mm→m. (See CLAUDE.md
gotcha #6.) Pre-flight an edited capture sheet read-only with `scripts/validate_capture_sheet.py`
(no CC — confirms it parses + is uniformly mm) before any bulk consumes it.

## Tracking — the 15 live SKUs that already carry each (Base UoM) dims (read-only census, 23 Jun 2026)

Recorded so the each-write's effect on them is explicit, not silent. ⚠ **This table's wrong-unit
analysis is INVERTED by the metres correction** (see top banner): the target value is metres, so
the 11 "metres" SKUs were actually CORRECT and the 4 "mm" rows plus any cm value are the wrong ones.

| Regime (under the corrected metres truth) | Count | SKUs | Example |
|---|---|---|---|
| **mm (1000× too big)** — the M-DIMS-5b EA writes | 4 | BB-2CH, BE-1CH, BF-GRC, BI-BOM | BB-2CH stored `230`, should be `0.23` m |
| **metres — ALREADY CORRECT** (prior CC-UI entry; cm engine wrongly flagged these) | 11 | BI-CEH, BI-CHO, BI-CMI, BI-COI, BI-CPE, BI-CSU, BI-HON, BI-PES, BI-SRI, BI-SUG, BI-VSU | BI-CEH `0.21` m ≈ 205 mm ✓ (a few have stray values to check by hand) |

The correct desired value for, e.g., BB-2CH (205 mm captured) is `0.205` m. Once the engine is
fixed to ÷1000 and re-armed, the each-write will set every SKU to its captured **metres** value;
the 11 already-metres SKUs will largely no-op. Census artifact: `data/dims/each_uom_census.csv`.

## Engine (shared by 5c-CT, 5d-each, sandbox soak)

`dims_write.bulk._run_bulk` — 5a gate → ONE batch hard stop → paced fail-fast →
`write_and_verify` (PATCH `/warehouse-products/{id}` UoM dims, Accept-Version 8, JSON-Patch
`op:add`) → UoM-specific read-back → W4 idempotency. The ONLY thing the each-write changes vs the
CT write is the UoM resolver: `resolve_default_uom` (the each) instead of `resolve_ct_uom`.

## Deferred

- GUI — deferred; prove the pipeline (this) first.
- The CT UoM names — Jake fixes by hand in the CC UI if/when CT dims are ever wanted.
