# Dims → CC UoM state — which dims live on which unit-of-measure

**Purpose.** Record, as a written known-fact, the three groups of active live Forage SKUs by
unit-of-measure shape and the dims-write status of each — so the deliberately-PARTIAL state
after M-DIMS-5c (carton dims on the CT UoM, but each-level dims still empty) reads as a known
fact, not as "dims done".

**Date:** 2026-06-22 · **Milestone:** M-DIMS-5c (CT carton-dims bulk; CC-mocked, not yet run live).

## Why UoM targeting matters

Captured dims are **carton/outer** dims (measured at outer-carton level: mm L/W/H, kg weight).
A CartonCloud warehouse-product carries dims **per unit-of-measure**, not once. The M-DIMS-5b
proving run found that a blind "write the captured dims to the *default* UoM" mis-dimensions the
**each** on every SKU that has a separate carton UoM (the `AE-2CB` finding: it has a `CT` UoM, so
its each is not its carton). So dims must target the **right UoM**: carton dims → the carton
(`CT`) UoM; each-level dims → the each (default/`EA`) UoM.

## The three groups (active live Forage SKUs)

| Group | Count* | UoM shape | Where its dims belong | Status |
|-------|-------:|-----------|-----------------------|--------|
| **EA-only** | ~367 | default `EA`, no carton UoM | each dims → the default (`EA`) UoM | **each path** (the M-DIMS-3/4 default-UoM write mechanism) — **not** 5c's job |
| **CT-carton** | 81 | `EA` + a `CT` carton UoM | carton dims → the `CT` UoM; each dims → the `EA` UoM | **carton via M-DIMS-5c** (CT UoM). **Each-level (Base UoM) dims still EMPTY — pending 5d** (each capture via the app) |
| **CTN/PLT no-EA** | 7 | `CTN`/`PLT`, **no** each | genuinely different shape | **DEFERRED, undecided.** NOT handled by 5c, NOT to be assumed into 5d |

\* Counts are the M-DIMS-5b-derived expectation (~88 SKUs carry a carton UoM ≈ 81 `CT` + 7
`CTN`/`PLT`). The **authoritative** count is produced at runtime by 5c: the resolver runs over
every active live product, and the SKUs it places onto a `CT` UoM ARE the CT cohort — shown in
full at the batch hard stop before any write.

## What M-DIMS-5c does (and deliberately does NOT do)

- **Does:** writes the captured **carton** dims to the **`CT`** UoM for the **CT-carton** group,
  resolving each SKU's `CT` UoM id from its actual UoM list at runtime
  (`resolve_ct_uom`, `src/dims_write/bulk.py`). The read-back verifies the dims landed on the
  **`CT`** UoM specifically (not merely that some dim changed). Reuses the proven M-DIMS-4 bulk
  loop unchanged (5a gate → one batch hard stop → paced fail-fast → `write_and_verify` →
  UoM-specific read-back → W4 idempotency); only the customer (live) and the UoM resolver (CT)
  differ. Requires `CC_LIVE_PROMOTION` armed.
- **Does NOT:** write the **each** (`EA` / Base UoM) dims for the CT-carton group — those stay
  **EMPTY** until **5d** (each capture via the app). It is **CT-only**: a SKU with no `CT` UoM is
  skipped **"no CT UoM"** with **no fall-through** to the each (the `AE-2CB` mistake) and **no
  guessing** at `CTN` — so the **CTN/PLT no-EA** group falls out here cleanly and is **deferred**,
  not silently rolled into 5d.

## Bottom line

After a full 5c run: carton (`CT`) dims are written for the CT cohort; **each-level dims for
those 81 SKUs remain empty (pending 5d)**, the ~367 EA-only SKUs are the each path's job, and the
7 `CTN`/`PLT` no-EA SKUs are **deferred and undecided**. Dims are **not** "done".
