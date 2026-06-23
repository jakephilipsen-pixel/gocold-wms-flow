# DIMS_UOM_STATE.md — which UoM carries Forage carton dims, and why

State of the dims→CartonCloud sync, by unit-of-measure. Source of truth for "where do dims go".

_Last updated: 23 Jun 2026 (M-DIMS-5d each-write: cm confirmed live, 132 written, name-poison guard added)._

## TL;DR

- **Each / Base UoM (`defaultUnitOfMeasure`) — THE dims pipeline.** Automated target, written in
  **cm**. Built: `dims_write.run_each_bulk` + `scripts/run_dims_each_bulk.py` (M-DIMS-5d).
  Live-gated (`CC_LIVE_PROMOTION`, default-closed), batch hard stop, fail-fast, `finalize_exit`.
  **cm CONFIRMED LIVE** (few-SKU test BB-2CH/CL/SS, eyeballed in CC: BB-2CL = 23×14×20.5 for a
  1.3 kg 6-pack, physically sensible). The full bulk then wrote **132 SKUs** before halting (see
  the name-poison finding) — those 132 are correct cm and live. Re-run is idempotent (the 132
  no-op).

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
