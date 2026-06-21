# GROUND_TRUTH.md — canonical build-state record

**Rule for all three parties (Jake, Claude Code, claude.ai):** the repo is the
source of truth, this file is the index. Nobody narrates build state from
memory. **If it's not in a commit, it doesn't exist.** Every claim below was
verified by inspecting the tree at the HEAD recorded in the footer — not from
the brief, not from memory.

Verification method: `git ls-files`, `git log`, `grep` over `src/`, and a full
`pytest` run. Commands and outputs are reproducible from the working tree.

---

## 1. Surface build state

Surfaces of the intended ops-console wrapper. "Read paths" = code in this repo
that reads the relevant data from CC. "Write paths" = code in this repo that
issues a mutating call to CC.

| Surface | State | Read paths | Write paths | Test status | Last-verified |
|---|---|---|---|---|---|
| **Receiving / Putaway** | **planned** | y — `src/cc_client/queries.py` `search_inbound_orders` reads inbound orders | **n** — no surface, no write | no surface-specific tests | 9c53a99 |
| **Stock / Slotting** | **partial** | y — SOH report-run `get_sku_locations` (`queries.py`), slotting analysis (`src/analysis/slotting.py`, `zoning.py`), locations via XLS loader (`src/locations/cc_loader.py`) | **n** — analysis only; output is CSV for manual import to CC | pass — `test_soh_sku_locations` (7), `test_soh_location_candidates` (8), `test_sku_locations` (3) | 9c53a99 |
| **Pick waves** | **built (read-only)** | y — live wave generation off SOH (`src/wave_runner.py`, `src/analysis/wave_picks.py`), web console `src/web/` | **n** — output is PDF/CSV pick sheets only (`src/output/`) | pass — `test_wave_runner` (13), `test_wave_consolidation` (7), `test_carton_split` (13), `test_carton_pick_locations` (11), `test_web` (22), `test_csv_picksheet` (5), `test_pdf_picksheet` (4) | 9c53a99 |
| **Dispatch** | **built (read-only, predict-to-run)** | y — consignment-history learning + prediction (`src/dispatch/`), web console `src/web_dispatch/` | **n / unbuilt** — `CartonCloudSink` exists but refuses + `NotImplementedError` (see §2.4) | pass — `test_dispatch_*` (9 files, ~34 tests), `test_web_dispatch` (12), `test_build_dispatch` (1) | 9c53a99 |
| **Dims** | **built (CC write in-repo; live-proven single + sandbox soak)** | y — warehouse-products read (dims under v8); worklist/reconciliation tooling (`src/analysis/dims_worklist*.py`, `dims_measuring_sheet.py`, `dim_loader.py`) | **y, IN THIS REPO** — `src/dims_write/` issues a real `PATCH /warehouse-products/{id}` through the W0–W5 gate chain + human hard stop (§2.5). **M-DIMS-3** landed the first live write (21 Jun 2026, sandbox `sHL-BWC`); **M-DIMS-4** (`bulk.py`) then soaked the WHOLE active sandbox set — **43 written + read-back verified, 1 no-op, 2 skipped = all 46** (21 Jun 2026) — reusing the same path in a paced, fail-fast loop. **M-DIMS-5a** added the `CC_LIVE_PROMOTION` live-promotion gate (no live runner/write yet; flag disarmed). Sandbox-only; live Forage not yet written | pass — `test_dims_shadow_approve` (15), `test_dims_sandbox_roundtrip` (26), `test_dims_bulk` (7), `test_dims_worklist` (10), `test_dims_worklist_xlsx` (5), `test_dims_measuring_sheet` (4); 5a gate in `test_write_config` (41) + `test_write_customer_guard` (15); **`test_dim_loader` still has 1 FAILING test** (see §4) | 4f7fab4 |

**Aggregate test status on `master` @ `4f7fab4` (M-DIMS-3 + M-DIMS-4 + the #20 resolver
fix + M-DIMS-5a live gate all merged): 356 passed, 1 failed** (full suite, local data present).
The one failure is `test_dim_loader.py::test_june_ods_template_loads`, a fixture/data
mismatch (`cartons-per-pallet` column absent from a capture template), **not** a
write-safety regression.

**Test baseline is branch- and environment-dependent — record the true green to keep
regressions detectable:**
- **`master` progression, full local data, same known `test_dim_loader` failure:**
  193 passed (pre-M-DIMS-3) → 325 (PR #17, M-DIMS-3 v8 write) → 332 (PR #18, M-DIMS-4) →
  **356 passed at `4f7fab4`** (PR #20 resolver +2, PR #21 M-DIMS-5a live gate +22).
- **`test_wave_runner.py` is data-dependent:** several of its tests need the local
  `data/` parquet fixtures (gitignored: `data/raw/` etc.). They **pass with the real
  data present** and **error on a data-less checkout** — an environment artifact, NOT
  a code regression. A "true green" run therefore requires the data files in place;
  a fresh clone will show those as errors until the data is provided.
- So a real regression = the known-failure count rises **above** the one documented
  `test_dim_loader` case, or a non-data test newly fails. Don't read data-less
  `test_wave_runner` errors as breakage.

---

## 2. Write-safety: every place that can issue a non-GET to CartonCloud

Exhaustive `grep` of `src/` for `PATCH`/`PUT`/`DELETE`/`POST` and every site
that touches `write_enabled`. As of M-DIMS-3 there is now exactly **one** real
business-data write — the dims `PATCH` (§2.5), issued through the dedicated,
double-gated `client._mutate` entry point (`src/cc_client/client.py:226`:
requires `write_enabled` **and** a per-call `approved` token, fires once, no
retry). Everything else is unchanged: the default non-GET gate (2.1), two `POST`
sites that are reads/triggers (2.2 search, 2.3 SOH report-run), and the
refused/unbuilt dispatch sink (2.4).

### 2.1 The default gate — `src/cc_client/client.py:148` ✅ closed-by-default
```python
if method.upper() not in {"GET"} and not self.write_enabled:
    raise CartonCloudError("write operations disabled (method=...) ...")
```
Any non-GET raises unless `write_enabled` is True. Default `write_enabled=False`
(constructor); env override `CC_WRITE_ENABLED=true`. **State: ACTIVE, default-closed.**

### 2.2 `post_search()` — `src/cc_client/client.py:352` ⚠ opens gate, but read-only
Sets `self.write_enabled = True` (line ~352) to issue paginated `POST /.../search`,
then **restores it in a `finally`**. CC's search endpoints are POST
despite being reads (large query bodies). **State: semantically a read; gate is
temporarily opened and reliably restored; only ever POSTs to search paths.** No
business object is created or mutated.

### 2.3 SOH report-run — `src/cc_client/queries.py:~236` ⚠ a benign POST trigger
Sets `client.write_enabled = True`, does `POST /report-runs` (creates a
report-run resource on CC), then **restores in a `finally`**. It is a **report
trigger** — no order/product/stock/consignment **business** data is mutated (the
one business-data mutation is the dims `PATCH`, §2.5, which goes through `_mutate`,
not this path). **State: gated open→restored; benign report creation only.**

### 2.4 `CartonCloudSink.apply()` — `src/dispatch/sinks.py:42` ✅ refuses, unbuilt
```python
if not (self.write_enabled and self.dispatch_write_approved):
    raise PermissionError("CC dispatch write-back not approved ...")
raise NotImplementedError(...)  # pragma: no cover - not built in v1
```
Double-gated (`write_enabled` **and** `dispatch_write_approved`) **and** the body
is unimplemented. **State: cannot write; refuses even if both flags were set.**

### 2.5 Dims write — the one real business-data PATCH (M-DIMS-3) ✅ gated, sandbox-only, live-proven
The dims write surface (`src/dims_write/`) is the first and only path that mutates a
business object on CC. It composes the full **W0–W5 gate chain** (rate-limit → read →
customer-guard → authz → idempotent-mutate; `approve.py:approve_dims_write`) behind a
**human hard stop**, then fires through the §2-intro `_mutate`:
```python
# src/dims_write/roundtrip.py:80 — live_mutate_fn (the injected do_mutate)
resp = client._mutate("PATCH", path, approved=True, json=ops, headers=headers)
# path/ops/headers from build_dims_patch() (src/dims_write/approve.py)
```
- **Wire shape (validated live):** `PATCH /warehouse-products/{id}`, JSON-Patch `add`
  ops on `/unitOfMeasures/{uom}/{dim}`, `Accept-Version: 8`,
  `Content-Type: application/json-patch+json`. (A `/products/{id}` path 404s — that's
  *transport products*; `op:replace` 422s on an unset dim; a v1 PATCH 200s but silently
  drops L/W/H. See CLAUDE.md gotcha #6.)
- **Gate state — what stops a live-Forage write (M-DIMS-5a):** `write_enabled` defaults
  `False` (`client.py:76`); the `WriteConfig` allow-list defaults to the **sandbox
  singleton** (`write_config.py` `_default_allowlist = {SANDBOX_CUSTOMER_ID}` = `a8dab3f2-…`);
  the **live Forage id (`d4810e1e-…`) is writable ONLY when `CC_LIVE_PROMOTION=true` is
  armed** (`WriteConfig.live_promotion`, default `False`). `is_customer_allowed` gates the
  live id *solely* on that flag — never on allow-list membership, so it can't be smuggled
  in via `CC_WRITE_CUSTOMER_ALLOWLIST`. The run-gate `assert_write_target_allowed`
  (`roundtrip.py`, renamed from `assert_sandbox_only` at M-DIMS-5a) still requires the base
  allow-list to be *exactly* the sandbox singleton (you cannot promote by editing it) and
  logs a loud `LIVE PROMOTION ARMED` WARNING when the flag is on. The customer-guard (W3,
  `verify_customer_allowed`) re-checks the read-back target's customer id on every write —
  flag-aware. A human types `go` at the hard stop; the write is read back and verified.
  **As of HEAD the flag is DISARMED** (no live write has occurred or is possible).
- **Exercised live (sandbox only):** M-DIMS-3 landed one SKU (`sHL-BWC`,
  `255×230×150 / 2.2 kg`, read-back verified under v8, 21 Jun 2026); **M-DIMS-4**
  (`src/dims_write/bulk.py` `run_sandbox_bulk`) then looped this SAME path —
  `write_and_verify` → `_mutate` per SKU, ONE batch hard stop, fail-fast, paced through W5 —
  over the whole active sandbox set: **43 written + read-back verified, 1 no-op, 2 skipped =
  all 46** (21 Jun 2026). It adds NO new write site or wire shape. **M-DIMS-5a** added the
  live-promotion gate (the `CC_LIVE_PROMOTION` flag above) but **no live runner and no live
  write** — the flag is disarmed, and a live-Forage write remains impossible until it is
  deliberately armed (a separate, boss-approved step; the live runner is M-DIMS-5b, not yet built).

### 2.6 Lock test
`tests/test_read_only_guard.py` (22 tests, passing) asserts the gate behaviour;
`test_dims_shadow_approve.py` (15) + `test_dims_sandbox_roundtrip.py` (21) assert the
dims-write chain, the sandbox-only refusal, and that shadow never calls `_mutate`;
`test_dims_bulk.py` (7) asserts the M-DIMS-4 batch hard stop, fail-fast, the idempotent
re-run (zero PATCHes), the paced limiter (not bypassed), and the sandbox-only refusal;
`test_write_config.py` + `test_write_customer_guard.py` assert the M-DIMS-5a live gate —
the live id writable IFF `CC_LIVE_PROMOTION` armed, the anti-bypass (allow-list membership
never grants it), and the per-write W3 re-check.

**Summary:** the Python repo has exactly **one** business-data write path — the dims `PATCH`
to a warehouse-product UoM (§2.5); M-DIMS-4 loops it and M-DIMS-5a adds the live gate, but
neither adds a new write site. It has run live against the **sandbox** customer only — one
SKU (M-DIMS-3) then the full active set (M-DIMS-4, 43 written) — each through the full gate
chain + human hard stop, read-back verified. It is **default-closed**: `write_enabled` off,
base allow-list sandbox-only, and `CC_LIVE_PROMOTION` **disarmed** — so the live Forage id
is unwritable until that flag is deliberately armed. Other non-GET traffic is search reads
(2.2) and SOH report-run creation (2.3). Dispatch write-back (2.4)
is refused and unbuilt.

---

## 3. The `dim-capture-app` answer (does it exist? where?)

**It exists, and it is real code — but it is NOT part of this repo.**

- It is a **separate GitHub repository**, embedded in the gocold-wms-flow working
  tree on Jake's machine as an **untracked directory with its own nested `.git`**.
  It is **not a submodule** (no `.gitmodules`) and appears in **zero commits** of
  gocold-wms-flow on any branch. **Cloning gocold-wms-flow gets none of it.**
- Its own repo identity:
  - **Clone URL:** `https://github.com/jakephilipsen-pixel/dim-capture-app.git`
  - **Branch:** `main`  · **HEAD:** `8e3b065` · **28 commits**
  - **Latest commit:** `8e3b065 chore(deploy): local-deploy gate re-passed — Jake sign-off 2026-06-08 (SHA a9d2136, incl. module 14)`
- Key files (verified present in the local checkout):
  - `backend/src/services/ccClient.ts` (469 lines) — `patchProductDims()` does the real `PATCH /products/{id}` with `{length,width,height,weight}`
  - `backend/src/services/syncService.ts` (158 lines) — `syncUnsyncedDims()` batches unsynced dims and calls `patchProductDims`
  - `backend/src/middleware/requireSyncKey.ts` — `X-Sync-Key` authz
  - ~200 `*.test.ts` files present; `node_modules` + lockfile installed
- **Built/tested?** Per the **dim-capture-app repo's own committed history**, it
  was built and its local-deploy gate re-passed with Jake's sign-off (commit
  `8e3b065`, 2026-06-08). That is a claim made *inside that repo*, verifiable by
  cloning it and running its suite — **not** verifiable from gocold-wms-flow.
- **Caveats / do-not-over-trust:** verification here is from this machine's
  checkout, which has one uncommitted change (`backend/.dockerignore`). Before any
  dims write touches the floor, the authoritative step is: clone the repo, run its
  tests, and confirm the gate behaviour independently. "Planned but proven in its
  own repo, not yet integrated here" is the accurate description — not "part of
  this project and done."

**Integration decision (M-DIMS-1, Route B) — supersedes the above as the write
mechanism:** rather than wire this separate repo into the ops console, the dims→CC
write was **ported natively into the Python W0–W5 spine** (`src/cc_client/write_*`,
`src/dims_write/`). That in-repo path is now the **live write mechanism** (§2.5) and is
what landed M-DIMS-3. `dim-capture-app` is therefore **reference-only** going forward —
and notably its `patchProductDims` targets the **legacy** `app.cartoncloud.com.au/api/v1`
`/products/{id}` endpoint (Bearer key, not-live), a *different* API from the live OAuth2
`/warehouse-products` path we actually ship. Do not treat `dim-capture-app` as the write
path; the authoritative dims write now lives and is tested **in this repo**.

---

## 4. Claims in the brief NOT backed by code in this repo

`docs/cc-wrapper-ops-console-brief.md` §3.2 describes `dim-capture-app` as though
it is a deliverable of this project. Correcting the record:

1. **"dim-capture-app is part of this project."** Not in this tree. It is a
   separate repo (§3). gocold-wms-flow contains **no** TypeScript, **no**
   `PATCH /products`, **no** `syncService`. Confirmed by `grep`.
2. **"The dims→CC write path exists."** **Now true IN THIS repo** as of M-DIMS-3
   (`src/dims_write/`, §2.5) — superseding the earlier state where it lived only in
   `dim-capture-app`. The in-repo path landed a real sandbox write on 21 Jun 2026. The
   brief's direction was right; it is now realised here, gated and sandbox-only, not just
   in the separate repo.
3. **"X-Sync-Key authz, advisory-lock idempotency, locally validated 2026-06-07."**
   These are properties of the `dim-capture-app` repo, not this one. The date is
   also approximate — that repo's own latest gate sign-off is **2026-06-08**
   (commit `8e3b065`, SHA `a9d2136`).
4. **Why this drift happened:** the embedded nested-`.git` directory makes
   `dim-capture-app` *look* present in the working tree while being invisible to
   anyone who clones gocold-wms-flow. Reading the brief without inspecting `git
   ls-files` produces exactly this three-way mismatch.

Nothing else in the brief asserts code-state that contradicts the tree. The brief
remains accurate as a **forward plan** (the wrapper direction, the pattern to
copy); it is only the "already built, here" framing of `dim-capture-app` that
this record corrects.

---

## 5. Sandbox customer — scoped-read verification (2026-06-20)

The write-enablement plan defaults all writes to a single sandbox customer. That
id was checked against CartonCloud with a **read-only** scoped query
(`POST /warehouse-products/search`, `write_enabled=False` throughout — no mutate).

| Fact | Result |
|---|---|
| Customer id | `a8dab3f2-defa-433e-87a0-01dee48a2286` |
| Resolves to | **`SANDBOX TEST - FORAGE`** |
| Tenant | `4906532d-94ad-444c-89cf-e394d7d73581` (same tenant as live Forage) |
| Product count | **46 active** (1111 total; ~1065 inactive/archived `ZZ*` legacy test SKUs) |
| Active code shape | `s`-prefixed (`sRK-`, `sGP-`, `sHL-`, `sRD-`, `sTC-`…) |
| Live contrast | `d4810e1e-…` → "The Forage Company", codes `FP-*`/`HI-*` — the customer-id filter genuinely discriminates |

**Status: WRITE-PROVEN AT SCALE (M-DIMS-3 then M-DIMS-4, 21 Jun 2026).** M-DIMS-3 landed one
real `PATCH` (`sHL-BWC`, read-back verified under v8, §2.5); M-DIMS-4 then soaked the whole
active set — **43 written + verified, 1 no-op, 2 skipped = all 46** — through the same gated,
paced, fail-fast loop. The sandbox id is confirmed **end-to-end at batch scale** (read *and*
gated writes), not config-only. The allow-list still admits this customer's products and
refuses all others.

Caveat carried into the spine: the customer-id allow-list (WRITE_ENABLEMENT_PLAN
§2.3) admits **all 1111** products under this customer, not just the 46 active —
the active-status / `s`-prefix selection is operational, layered on top of the
customer-id safety boundary, not the boundary itself.

---

## Footer

- **Branch:** refreshed on `docs/ground-truth-5a-gate` (docs-only, base `master`). The
  M-DIMS-3 (#17), M-DIMS-4 (#18), the #20 resolver fix, and the **M-DIMS-5a live gate (#21)**
  are **all merged to `master`** — `assert_write_target_allowed` and `WriteConfig.live_promotion`
  (default `False`) are present at `4f7fab4` — so this record is true at `master` itself.
  Other spine/worklist code remains on its own feature branches per earlier footers.
- **Re-verified at `4f7fab4`** on `master` (`grep` over `src/` + full `pytest`), 2026-06-22:
  the **§1 Dims row** (incl. M-DIMS-4 soak + M-DIMS-5a gate), the **§1 aggregate test count**,
  all of **§2** (write-safety — still exactly one write path; M-DIMS-4/5a reuse it, 5a adds the
  promotion gate), and **§5**. §3–§4 carried forward. The other four §1 surface rows
  (Receiving, Stock, Pick waves, Dispatch) are **unchanged from `9c53a99` and were NOT re-run
  this pass** — their `Last-verified` column still reads `9c53a99`.
- **Full suite at this HEAD:** **356 passed, 1 failed** — the one failure is the known
  `test_dim_loader::test_june_ods_template_loads` data-fixture mismatch (local `data/`
  present); not a write-safety regression.
- **Live-promotion flag (`CC_LIVE_PROMOTION`) state at this HEAD: DISARMED.** No live runner
  exists (M-DIMS-5b not built); no live-Forage write has occurred or is possible.
- **dim-capture-app repo HEAD (external):** `8e3b065` on `main` @ `github.com/jakephilipsen-pixel/dim-capture-app`
- **Date:** 2026-06-22
- **Verified by:** Claude Code, from the working tree (git + grep + full pytest run)
