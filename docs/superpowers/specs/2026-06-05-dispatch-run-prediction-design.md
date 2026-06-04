# Dispatch run prediction (v1) — design

**Date:** 2026-06-05
**Status:** Approved (brainstorm)
**Project:** gocold-wms-flow
**Owner:** Jake Philipsen

## Problem

Every morning a dispatcher hand-assigns Go Cold's open CartonCloud sale
orders to delivery runs (CC run sheets / delivery runs). The work is
highly repetitive — most delivery addresses go on the same run day after
day — but it is rebuilt from scratch each day, and a slice of orders is
handed to third-party carriers who route themselves.

v1 learns the habitual address→run pairings from CC consignment history
and produces a **review-and-apply suggestion** for today's open orders:
the run each order most likely belongs on, with a confidence score and a
plain-English reason. Carrier-bound orders are split off into per-carrier
manifests. The dispatcher reviews and applies the assignments in CC.

CartonCloud stays read-only end to end. A write-adapter seam is built so a
vetted write-back can be switched on later, but it is never wired in v1.

## Decisions (from brainstorm, 2026-06-05)

- **Scope on the floor-layer roadmap:** dispatch / run sequencing, built
  first (pick bench, replen, putaway come later).
- **v1 job:** predict-to-run only. Stop sequencing (drive order within a
  run) is explicitly v2.
- **Write boundary:** build read-only now, architect a clean write seam for
  later. Writing run assignments back to CC contradicts the standing rule
  ("CC strictly read-only; SAP B1 owns all writes") and must not happen
  until that boundary is cleared and accuracy is proven in shadow mode.
- **Prediction engine:** deterministic recency-weighted frequency model.
  **No LLM in the pipeline** — the task has an exact, auditable answer, and
  CLAUDE.md mandates fixed event-driven pipelines on the floor (no agent
  loops). An optional, offline, human-gated LLM advisory on the *review
  bucket only* may be revisited in v2+; it is out of scope here.
- **Zone fallback config:** stdlib TOML (`tomllib`), not YAML — no PyYAML in
  `requirements.txt`, so TOML keeps the zero-new-dependency rule.

## Non-goals (v1)

- No stop sequencing, no route optimisation, no truck-capacity assignment.
- No writes to CartonCloud. `write_enabled=False` everywhere; the
  `CartonCloudSink` adapter is a stub that refuses to write.
- No LLM / agent loop in the daily pipeline.
- No new runtime dependencies. No database — local files plus a cached
  model parquet.
- No new persistent service. Batch script, like the existing extracts.

## Architecture

```
CC API (read-only)
  ├─ search_consignments()  ── last 30–90d, runSheetDate filter ──┐ LEARN
  └─ search_outbound_orders(status=open)  ── today ──────────────┐│ PREDICT
                                                                 ││
  src/dispatch/                                                  ▼▼
   ├─ addresses.py    normalise_address / address_key   (lifted from script)
   ├─ consignments.py extract_run_info, parse consignment → record
   ├─ history.py      compute_run_history(consignments) → RunHistoryModel
   │                    per address_key: {run: recency-weighted score,
   │                    last_seen, n}; cached → data/dispatch/run_history_<ts>.parquet
   ├─ zones.py        load_zone_config (TOML) + assign_zone   (unknown-addr fallback)
   ├─ predict.py      predict_runs(open_orders, model, zones, carrier_rule)
   │                    → DispatchPlan(assignments, carriers, review)
   ├─ sinks.py        DispatchSink port → FileSink (now) | CartonCloudSink (stub)
   └─ output.py       run manifests (xlsx) + CSVs + summary.md
        │
  scripts/build_dispatch.py   (orchestrator: learn → predict → write via sink)
        ▼
  data/processed/dispatch/<YYYYMMDD_HHMMSS>/
```

The new modules follow the existing pattern: `compute_*` functions,
frozen dataclass results, `from __future__ import annotations`, full type
hints, structured logging via `logging.getLogger(__name__)`, no prints in
library code, Australian English, no emojis.

## Components

### 1. `search_consignments()` in `src/cc_client/queries.py`

The read path the learning engine needs. `scripts/extract_address_runs.py`
and `scripts/_patch_client_search_consignments.py` both reference
`client.search_consignments(...)`, but it is **not on the client today** —
the patch was never applied, so the script would crash. Add it properly:

- POST `/consignments/search`, paginated via the existing `post_search`
  plumbing (search endpoints are POST but are reads — same treatment as
  outbound/inbound/products/locations).
- Export from `cc_client/__init__.py`.
- **Verify the consignment scope live** with a read probe before any build
  (it was never exercised in the 2026-06-05 credential-rotation audit;
  could 403/404). If the scope is missing, that is a credential-side
  blocker surfaced before implementation, not a code bug.

### 2. Shared address/run library (`addresses.py`, `consignments.py`)

Lift `normalise_address` / `address_key` and `extract_run_info` out of
`scripts/extract_address_runs.py` into `src/dispatch/` so the script and
the predictor share one implementation instead of duplicating it. Fix the
script's non-standard `from src.cc_client.client import ...` to the
project-standard `from cc_client import ...`, and re-point the script to
the lifted library. The known CC shapes (verified by the existing script):

- Delivery address: `details.deliver.address` with `lines` (list or str),
  `suburb`/`city`, `state` (`{code,name}` or str), `postcode`.
- Run info: `details.runsheet.{name,date}` and `details.deliveryRun.{name}`.

`address_key` = lower-cased, whitespace-collapsed join of street, suburb,
state, postcode — the dedup key the model is built and queried on.

### 3. `history.py` — the learning model

`compute_run_history(consignments) -> RunHistoryModel`. For each
`address_key`, build a map `delivery_run -> score`, where `score` is a
**recency-weighted count**: each historical consignment to that address
contributes a weight that decays with age (recent runs count more than old
ones), so a recently changed run wins over stale habit. Also record
`last_seen` (max date) and `n` (total consignments) per address.

Cache the computed model to `data/dispatch/run_history_<ts>.parquet` so the
daily predict step does not re-pull and re-aggregate history every run; the
orchestrator can `--skip-learn` to reuse the latest cached model.

```python
@dataclass(frozen=True)
class RunCandidate:
    run: str
    score: float          # recency-weighted
    n: int                # raw consignment count for this (address, run)
    last_seen: date | None

@dataclass(frozen=True)
class RunHistoryModel:
    by_address: dict[str, list[RunCandidate]]   # sorted, best first
    window_days: int
    generated_at: datetime
```

### 4. `predict.py` — the daily assignment

`predict_runs(open_orders, model, zones, carrier_rule) -> DispatchPlan`.
For each open order:

1. Normalise its delivery address → `address_key`.
2. If carrier-bound (see §5), route to the carrier bucket; skip run
   prediction.
3. Else look up `address_key` in the model:
   - **predicted_run** = highest-scoring `RunCandidate`.
   - **confidence** = `predicted.score / sum(all candidate scores)` for
     that address (its share of the address's weighted history).
   - **flag**:
     - `stable` — share ≥ 0.8 and n ≥ 3.
     - `mixed` — multiple runs with no clear winner; list alternatives.
     - `new_address` — `address_key` absent from the model → zone fallback
       (§6) + review.
     - `stale` — `last_seen` older than a separate `stale_days` threshold
       (default 30d; distinct from the learning `window_days`, default 90d).
   - **reason** — plain English, e.g. "8/10 recent consignments to this
     address went on West-Tue; last 2026-06-03." Non-negotiable: the floor
     must see *why* before it trusts the suggestion.

```python
@dataclass(frozen=True)
class RunAssignment:
    so_id: str
    so_ref: str
    predicted_run: str | None
    confidence: float          # 0.0–1.0
    flag: str                  # stable | mixed | new_address | stale | no_address
    reason: str
    alternatives: list[str]    # other runs seen for this address
    address: dict              # normalised address fields for the manifest

@dataclass(frozen=True)
class DispatchPlan:
    assignments: list[RunAssignment]   # own-fleet, predicted
    carriers: dict[str, list[RunAssignment]]  # carrier name → orders
    review: list[RunAssignment]        # new/stale/mixed/no-address
```

### 5. Carrier split

Third-party-carrier orders are pulled out before run prediction and grouped
per carrier. The exact CC signal — a freight/carrier field on the
consignment/order vs a recognisable run-name pattern — is **unconfirmed**,
so carrier detection is a small configurable `carrier_rule` (a field-value
match and/or name pattern), and confirming the real field is an explicit
probe step (§9). Until confirmed, the rule defaults to empty (everything
treated as own-fleet) so nothing is silently mis-routed.

### 6. `zones.py` — unknown-address fallback

`load_zone_config(path) -> ZoneConfig` reading a TOML file
(`config/dispatch_zones.toml`); `assign_zone(address, zones) -> str` by
postcode (exact or range) then state, first match wins, else a `fallback`
zone name. Used only for `new_address` orders so even a never-seen address
lands in a sensible bucket for the dispatcher rather than nowhere.

### 7. `sinks.py` — the write seam

```python
class DispatchSink(Protocol):
    def assign(self, assignment: RunAssignment) -> AssignResult: ...

class FileSink:   # v1 — writes suggestion rows to the output dir
    ...

class CartonCloudSink:   # built, never wired in v1
    def assign(self, assignment):
        if not (self.write_enabled and self.dispatch_write_approved):
            raise PermissionError(
                "CC dispatch write-back not approved; CC is read-only")
        ...  # future: PATCH/POST the run assignment, post-SAP-boundary
```

Both flags must be true for `CartonCloudSink` to act, and neither is set in
v1. This isolates the future write behind one tested adapter so enabling it
is a switch, not a refactor.

### 8. `scripts/build_dispatch.py` — orchestrator

```bash
python3 scripts/build_dispatch.py                      # learn + predict, all open SOs
python3 scripts/build_dispatch.py --skip-learn         # reuse latest cached model
python3 scripts/build_dispatch.py --history-days 90    # learning window
python3 scripts/build_dispatch.py --required-date 2026-06-06
python3 scripts/build_dispatch.py --dry-run            # predict, print summary, no files
```

Flow: (1) unless `--skip-learn`, pull consignment history and compute +
cache the model; (2) pull today's open orders; (3) load zones; (4)
`predict_runs`; (5) write via `FileSink`. Prints progress (scripts may
print); library stays silent.

### 9. Output (`data/processed/dispatch/<YYYYMMDD_HHMMSS>/`)

- `suggested_runs.csv` — own-fleet orders: `so_ref, so_id, predicted_run,
  confidence, flag, reason, alternatives, delivery_company, street, suburb,
  state, postcode, required_date`.
- `run_<name>.xlsx` — one manifest per predicted run; header block (run,
  date, stop count, generated_at) + stops sorted by postcode then suburb;
  low-confidence / new / stale rows highlighted.
- `carriers_<carrier>.csv` — per-carrier handoff lists.
- `review.csv` — new / stale / mixed / no-address orders for the dispatcher
  to decide, with the reason and any alternatives.
- `summary.md` — totals, confidence distribution, counts per run, carrier
  split, review/unmatched flags (red if review or no-address > 0).

## Error handling

- Consignment scope 403/404 → caught at the live probe; build halts with a
  clear scope message (never a silent empty model).
- Open order with no delivery address → `review` bucket, flag `no_address`.
- `address_key` absent from model → `new_address` → zone fallback + review;
  never silently dropped.
- CC pull failure → existing client retry/backoff; orchestrator aborts
  cleanly. Nothing to roll back — there are no writes.
- Stale model → predict logs a warning if the cached model's
  `generated_at` is older than N days; `--skip-learn` surfaces the age.

## Safety (carried forward from CLAUDE.md)

- `CartonCloudClient.from_env()` only; `write_enabled` never True in v1.
- All output to local files under `data/processed/dispatch/` and
  `data/dispatch/`. Never mutate CC state.
- No secrets in code or docs — env var names only.
- Conventions: frozen-dataclass results, `compute_*` naming,
  `from __future__ import annotations`, type hints, structured logging, no
  prints in library code, Australian English, no emojis, no new deps, no
  stub/placeholder logic (the `CartonCloudSink` refusal is real behaviour,
  not a placeholder).

## Testing

- **Unit (offline, fake transport / fixtures):**
  - `normalise_address` / `address_key` (list vs str lines, dict vs str
    state, whitespace/case).
  - `extract_run_info` against real consignment shapes.
  - `compute_run_history` recency weighting: recent run outranks older,
    `last_seen`/`n` correct.
  - `predict_runs` flags: stable, mixed, new_address, stale, no_address;
    confidence share maths; alternatives populated.
  - `carrier_rule` split routes carrier orders out of own-fleet.
  - `load_zone_config` TOML parse, range + exact match, fallback.
  - `FileSink` output shape; **`CartonCloudSink` refuses to write** in v1
    (regression guard, like `test_read_only_guard`).
- **Integration:** `build_dispatch.py --dry-run` over consignment +
  open-order fixtures yields a non-empty `DispatchPlan` with expected runs,
  carrier, and review buckets.
- **Live read probe:** read-only check that `search_consignments` returns
  data and run/address fields resolve (mirrors the rotation verify harness).

## Open questions (resolved by a probe before building)

1. Does the **consignment search scope** work for our client? (untested in
   the rotation audit.)
2. What is the real **carrier vs own-fleet signal** on a consignment/order
   (freight/carrier field vs run-name pattern)?
3. Are `details.runsheet` / `details.deliveryRun` populated on *open*
   orders, or only after dispatch? If post-dispatch only, prediction stays
   purely history-based (acceptable) — but confirm so the open-order pull
   isn't expected to carry run info it doesn't have.

## Rollout

Pure shadow mode. The dispatcher keeps working exactly as today. For a
couple of weeks we diff our predicted runs against what they actually chose,
measure accuracy per flag, and tune the recency weighting. Only once the
predictions are trusted do we consider the web console surface (roadmap
option B) and, separately and later, the write-back (behind the cleared
SAP B1 boundary).
