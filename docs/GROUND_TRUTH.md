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
| **Dims** | **partial (reconciliation built; CC write lives in a SEPARATE repo)** | y — warehouse-products read; worklist/reconciliation tooling (`src/analysis/dims_worklist*.py`, `dims_measuring_sheet.py`, `dim_loader.py`) | **n IN THIS REPO.** The dims→CC write (`PATCH /products`) exists ONLY in the separate `dim-capture-app` repo (§3) | mostly pass — `test_dims_worklist` (10), `test_dims_worklist_xlsx` (5), `test_dims_measuring_sheet` (4); **`test_dim_loader` has 1 FAILING test** (see §4) | 9c53a99 |

**Aggregate test status at HEAD: 212 passed, 1 failed** (full suite, no network).
The one failure is in the Dims surface — `test_dim_loader.py::test_june_ods_template_loads`, a fixture/data mismatch (`cartons-per-pallet` column absent from a capture template), **not** a write-safety regression.

---

## 2. Write-safety: every place that can issue a non-GET to CartonCloud

Exhaustive `grep` of `src/` for `PATCH`/`PUT`/`DELETE`/`POST` and every site
that touches `write_enabled`. There are **no** `PATCH`/`PUT`/`DELETE` calls
anywhere in `src/`. There are exactly **two** `POST` sites and **two** gates.

### 2.1 The default gate — `src/cc_client/client.py:139` ✅ closed-by-default
```python
if method.upper() not in {"GET"} and not self.write_enabled:
    raise CartonCloudError("write operations disabled (method=...) ...")
```
Any non-GET raises unless `write_enabled` is True. Default `write_enabled=False`
(constructor); env override `CC_WRITE_ENABLED=true`. **State: ACTIVE, default-closed.**

### 2.2 `post_search()` — `src/cc_client/client.py:258` ⚠ opens gate, but read-only
Sets `self.write_enabled = True` (line ~275) to issue paginated `POST /.../search`,
then **restores it in a `finally`** (line ~308). CC's search endpoints are POST
despite being reads (large query bodies). **State: semantically a read; gate is
temporarily opened and reliably restored; only ever POSTs to search paths.** No
business object is created or mutated.

### 2.3 SOH report-run — `src/cc_client/queries.py:~233` ⚠ the one real POST
Sets `client.write_enabled = True`, does `POST /report-runs` (creates a
report-run resource on CC), then **restores in a `finally`**. This is the single
place in the Python codebase that actually creates a server-side object. It is a
**report trigger** — no order/product/stock/consignment business data is
mutated. **State: gated open→restored; benign report creation only.**

### 2.4 `CartonCloudSink.apply()` — `src/dispatch/sinks.py:42` ✅ refuses, unbuilt
```python
if not (self.write_enabled and self.dispatch_write_approved):
    raise PermissionError("CC dispatch write-back not approved ...")
raise NotImplementedError(...)  # pragma: no cover - not built in v1
```
Double-gated (`write_enabled` **and** `dispatch_write_approved`) **and** the body
is unimplemented. **State: cannot write; refuses even if both flags were set.**

### 2.5 Lock test
`tests/test_read_only_guard.py` (22 tests, passing) asserts the gate behaviour.

**Summary:** the Python repo issues no business-data writes to CC. The only
non-GET traffic is search reads (2.2) and SOH report-run creation (2.3). Dispatch
write-back (2.4) is refused and unbuilt.

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

---

## 4. Claims in the brief NOT backed by code in this repo

`docs/cc-wrapper-ops-console-brief.md` §3.2 describes `dim-capture-app` as though
it is a deliverable of this project. Correcting the record:

1. **"dim-capture-app is part of this project."** Not in this tree. It is a
   separate repo (§3). gocold-wms-flow contains **no** TypeScript, **no**
   `PATCH /products`, **no** `syncService`. Confirmed by `grep`.
2. **"The dims→CC write path exists."** True only in the separate repo. In
   gocold-wms-flow the dims surface is read + worklist/reconciliation only; there
   is no code here that writes dims to CC.
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

**Status: config-verified, NOT write-proven.** The read confirms the id resolves
as claimed; it does **not** prove the write path. The CC round-trip proof lands at
**M-DIMS-3** (one real `PATCH` against one sandbox SKU, read back). Treat the id as
verified-for-config only until then.

Caveat carried into the spine: the customer-id allow-list (WRITE_ENABLEMENT_PLAN
§2.3) admits **all 1111** products under this customer, not just the 46 active —
the active-status / `s`-prefix selection is operational, layered on top of the
customer-id safety boundary, not the boundary itself.

---

## Footer

- **Branch:** `master` (canonical docs; cherry-picked from `feature/dims-cc-sync`).
  Spine code on `feature/write-spine-w0`. dims-worklist code remains on
  `feature/dims-cc-sync` pending its own review.
- **§1–§4 verified at:** `9c53a994aa0828ccae05525b48ece77f180c3837` (tree state on
  `feature/dims-cc-sync`); §5 added 2026-06-20.
- **dim-capture-app repo HEAD (external):** `8e3b065` on `main` @ `github.com/jakephilipsen-pixel/dim-capture-app`
- **Date:** 2026-06-20
- **Verified by:** Claude Code, from the working tree (git + grep + full pytest run + read-only scoped CC query)
