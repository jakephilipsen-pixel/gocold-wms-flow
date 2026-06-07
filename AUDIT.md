# AUDIT — gocold-wms-flow

**Audited:** 2026-06-07 · **Git SHA:** `94dd795` · **Branch:** `feature/wave-soh-source-of-truth`
**Source of truth:** `CLAUDE.md` (root) + `dim-capture-app/MODULES.md` (sub-project registry)
**Supersedes:** the 2026-06-03 audit (`e95a6c5`), whose blockers are now largely resolved — see "Resolved since last audit".

---

## Verdict

**The floor-facing tooling in this repo is genuinely built, committed, and green.** The wave-pick
generator + console and the dispatch run-prediction + console are real, stub-free, and covered by a
**fully passing 129-test suite**. CartonCloud stays read-only as the non-negotiable demands, and that
guard now has a regression test. Nothing in *this* repo is blocking shipment of the wave/dispatch
workflow.

**The one path that is built but NOT live is dims→CartonCloud sync**, which lives in the
`dim-capture-app/` sub-project. All 8 core modules there are built and passed compile-stress, but it
has **not passed `/deploy-local`** (`local_validated: false`) and carries **3 security-hardening
modules that gate the production candidate** — most importantly an **unauthenticated `POST /api/sync/cc`
that writes to the real CartonCloud**, which directly conflicts with the CLAUDE.md "human approval
gate" rule. That is the single most important thing standing between "built" and "in production".

---

## What actually works (verified)

| Capability | Verified how |
|---|---|
| **Full Python test suite** | `129 passed` via `.venv/bin/python -m pytest -q` (2026-06-07). |
| **Stub-free codebase** | Sweep for `not implemented`/`TODO`/`FIXME`/stub classes across `src/` + `scripts/` returns only **intentional guards**: `client.py:256` (forces `post_search`), `sinks.py:56` (v1 write-back deliberately refuses). No console/none/mock stubs in non-test code. |
| **Read-only enforcement (non-negotiable)** | `cc_client/client.py` gates non-GET behind `write_enabled` (default off); now locked by `tests/test_read_only_guard.py`. |
| **Wave pick generator — live SOH as source of truth** | `src/analysis/wave_picks.py`, `src/wave_runner.py`, `scripts/generate_waves.py`. Latest work (this branch) makes live SOH the **sole, mandatory** placement source per gen, with per-line UNALLOCATED handling instead of whole-order skips. Covered by `test_wave_runner`, `test_wave_consolidation`, `test_soh_sku_locations`. |
| **Pick sheets (PDF + CSV)** | `src/output/pdf_picksheet.py`, `csv_picksheet.py` — themed PDF, walk-ordered picks.csv with UNALLOCATED block. `test_pdf_picksheet`, `test_csv_picksheet`. |
| **Wave-pick console** | `src/web/` (FastAPI + HTMX + SSE). `test_web`, `test_jobs`. Deployed at picks.rolodex-ai.com via `wms-picks` tunnel. |
| **Dispatch v1 (predict-to-run, read-only)** | `src/dispatch/` — habitual address→run learning, prediction, carrier split, review files. 8 dispatch test files all green. |
| **Dispatch console** | `src/web_dispatch/` (FastAPI + HTMX + SSE). `test_web_dispatch`, `test_dispatch_plans`. Published at runs.rolodex-ai.com. |
| **CC API client** | OAuth2 client-credentials, paginated POST-search, retry/backoff, customer-scoped to The Forage Company; SOH report-run + `get_sku_locations` aggregation. |
| **Carton dims (local)** | `data/dims/dims_2026-05-13.xlsx`, 412 rows; loaded by `dim_loader.py`. |

---

## Resolved since the 2026-06-03 audit

- **R4 (uncommitted wave generator) — RESOLVED.** Repo went from 2 commits to **55**; wave generator,
  output, locations, analysis all tracked.
- **R5 (no tests) — RESOLVED.** `tests/` empty → **129 passing tests**, including the read-only guard
  and wave-consolidation regressions the prior audit asked for.
- **R2 (CLAUDE.md dims drift) — RESOLVED.** CLAUDE.md now correctly frames dims as "captured locally,
  0 synced to CC — a *sync* problem, not a *capture* problem".
- **R3 (dim-capture module-01 icon overstated) — RESOLVED.** `dim-capture-app/MODULES.md` now shows
  **all 8 core modules ✅** with current STATE.md + smoke-green evidence (2026-06-03/04).
- **R1 (dims→CC sync doesn't exist) — RESOLVED AT BUILD LEVEL.** Modules 02 (`cc-client` PATCH) and 04
  (`dim-api`/syncService) are built and tested; no longer 501 stubs. Now a *deploy/security* gap, not a
  *build* gap — see B1 below.

---

## Blockers to the stated goal (dims→CC path going live)

### B1 — BLOCKER: `dim-capture-app` sync writes to real CC unauthenticated
`dim-capture-app/MODULES.md` module **12 `cc-write-authz` (🔲🚧)**: `POST /api/sync/cc` (and
`/api/admin/seed`) are unauthenticated with no confirmation step; in prod `sync/cc` PATCHes the **real**
CartonCloud. Directly conflicts with CLAUDE.md §"never push to CC automatically … human approval gate".
Needs an auth-model **decision** (shared secret / nginx basic-auth / explicit confirm) written to
`DECISIONS.md` before build. **Gate: deploy-prod. This is the top blocker.**

### B2 — GATE: `dim-capture-app` has never passed `/deploy-local`
`dim-capture-app/.deploy-state` → `local_validated: false`, `validated_at: null`. Compile-stress ran
(2026-06-04, 1 Critical resolved) but the local deploy gate has not. `/deploy-prod` stays locked until
it does. **Gate: deploy-local.**

### B3 — GATE: three security-hardening modules gate the production candidate
`dim-capture-app` modules **09 `backend-error-hardening` 🔲🚧** (stack-trace/DSN leakage), **11
`deploy-hardening` 🔲🚧** (backend published to LAN bypassing single-origin proxy; missing security
headers), **12 `cc-write-authz` 🔲🚧** (B1). All marked 🚧 = "security must land before prod" per Jake's
sign-off. Modules 10 (`cc-resilience`) and 13 (`write-concurrency`) are recommended but not gating.
Each still needs `/add-module` to scaffold before `/build-module`.

---

## Gate readiness

- **gocold-wms-flow (this repo):** scripts + notebooks + FastAPI consoles, **no root MODULES.md** →
  the framework's `/compile-stress` and `/deploy-local` gates do not formally apply. Validation is
  **pytest (129 green) + real-data runs**, both passing. The consoles are already tunnel-deployed.
- **dim-capture-app:** `/compile-stress` **passed** (2026-06-04). `/deploy-local` **not run**
  (`local_validated:false`) → **`/deploy-prod` blocked**, and gated behind hardening modules 09/11/12.

---

## Non-code decisions for Jake

1. **CC-write auth model (B1):** how does `POST /api/sync/cc` get protected before it can touch the
   real CC? (shared secret / basic-auth / explicit human-confirm). Write to `dim-capture-app/DECISIONS.md`.
2. **Carton weight capture** is incomplete (~69% per CLAUDE.md). Per memory, the missing weights exist
   nowhere digital — they need **physical weighing**, not estimation. Decide if/when that happens; it's
   only needed for weight-based cartonisation/dispatch logic, not current picks.
3. **`gocold-stocktake` sibling project** (`CLAUDE_CODE_GOAL_stocktake.md`, 2026-06-03): a *separate,
   not-yet-started* app to recount the reshuffled warehouse so CC location data can be trusted. No code
   exists yet. It is the upstream unblock for the wave generator using CC-native locations. Decide
   priority vs. the dims→CC sync go-live.

---

## Drift

- No remaining CLAUDE.md drift in this repo (R2/R3 resolved). CLAUDE.md "Open work" section still frames
  dim-sync modules 02/04 as "not yet built" (line ~155) — **stale**: they are built and tested; the
  real remaining work is deploy-local + security hardening. Minor; update when convenient.

---

## Proposed queue (ordered)

1. **Decide the CC-write auth model** (B1 / decision 1) — unblocks everything downstream.
2. **Build dim-capture-app hardening 09 → 11 → 12** (B3) — the prod-gating security set.
3. **Run `/deploy-local` on dim-capture-app** (B2) — unlock `/deploy-prod`.
4. **Optionally** build 10 (`cc-resilience`) + 13 (`write-concurrency`) — recommended, not gating.
5. **Decide stocktake priority** (decision 3) — the other path to a trustworthy CC.

---

*Read-only audit. Only `AUDIT.md` + `audit.json` were written. No code, data, git, or deploy state
changed; nothing marked done/✅ on the basis of prose.*
