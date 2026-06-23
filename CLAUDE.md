# CLAUDE.md — gocold-wms-flow

## What this is

Workflow tooling for Go Cold's CartonCloud WMS. Started as the data-pipeline
foundation: pull SOs / POs / Products from CC API into local Parquet for
slotting analysis. Will grow into the pick bench service, replenishment
rule generator, and dispatch run sequencer.

## Project context

- **Operator:** Go Cold (cold chain 3PL, Scoresby VIC).
- **Primary customer:** The Forage Company. ~100–120 sale orders/day,
  ~15 lines per order, 438 active SKUs. A handful of smaller customers
  exist but are deprioritised; all analysis and tooling targets Forage.
- **Hardware:** ASUS NUC (16GB DDR4, 500GB NVMe) + Symbol scanner +
  Live! Cam Sync 3 + Zebra ZT411 (industrial pick bench printer) and
  ZQ630 (mobile, putaway team).
- **Constraint:** zero-tolerance for breakage. Workforce is change-averse;
  whatever ships to the floor must work first time. Build behind the
  scenes, validate in shadow mode, then roll out.

## Architecture

**Read-first, write-never (until explicitly enabled).**

```
CartonCloud API ──[OAuth2]──> CartonCloudClient (read-only by default)
                                    │
                                    ▼
                              extract.py
                                    │
                                    ▼
                             data/raw/*.parquet
                                    │
                                    ▼
                          notebooks/ (slotting analysis)
                                    │
                                    ▼
                       slotting recommendations (CSV)
                                    │
                                    ▼
                          (manual import to CC)  ← human approval gate
```

The human approval gate is deliberate. We don't automate writes back to CC
until the slotting logic has been validated against reality for a quarter.

## Stack

- **Python 3.11+**, pandas, pyarrow, httpx
- No web framework yet (pure scripts + notebooks)
- Will add FastAPI later for the bench service
- PostgreSQL + Docker Compose later for daily sync (currently file-based)

## Current capabilities

- `src/cc_client/`: OAuth2 client, paginated search, retry/backoff,
  type-safe query helpers for outbound orders, inbound orders, warehouse
  products, and stock-on-hand reports.
- `src/analysis/`: velocity (per-SKU metrics, ABC), patterns (order
  density, bench bypass threshold), zoning (co-occurrence + greedy
  clustering on top-N SKUs), destinations (postcode/state breakdowns).
- `scripts/smoke_test.py`: verifies auth + tenant access + minimal read.
  Always run this before anything else.
- `scripts/extract.py` / `scripts/extract_forage.py`: pulls SO/PO/Product
  to Parquet with date windows.
- `scripts/analyze.py`: orchestrates analysis, writes CSVs, plots, the
  Go Cold themed `capture_template.xlsx`, and a readable `summary.md`.
- `src/dispatch/`: read-only delivery-run prediction — learns habitual
  address→run pairings from CC consignment history, predicts today's open
  orders onto runs (confidence + reason), splits carriers, writes review
  files. Orchestrator: `scripts/build_dispatch.py`. CC stays read-only;
  `CartonCloudSink` write-back is built but refuses to act (v1).
- `src/web_dispatch/`: dispatcher-facing run console (FastAPI + HTMX + SSE,
  the delivery-side twin of the wave-pick console). Triggers
  `build_dispatch` with live progress, browses predicted runs + the review
  queue, downloads per-run manifests. Launcher `scripts/serve_web_dispatch.py`
  (127.0.0.1:8078); published at runs.rolodex-ai.com via the `wms-runs`
  Cloudflare tunnel. Read-only against CC. The build core is
  `src/dispatch/runner.py`, shared with the CLI.

## Validated against real data (10 May 2026)

- 95,212 SO line items / 90 days
- 9,613 PO line items / 180 days
- 460 active products
- **Carton dims (updated 12 May 2026): ~409 SKUs captured LOCALLY**
  (`data/dims/`, L/W/H 100%, inner-pack-qty 99.5%, weight ~69%) — but
  **0 synced to CartonCloud.** Local dims drive slotting/wave analysis
  today; CC-native wave + cartonisation need them IN CC. The original
  "0/460 in CC" blocker is now a *sync* problem, not a *capture* problem.
- Customer-scoped API client sees only "The Forage Company" (UUID
  `d4810e1e-91ab-43ed-b68e-b72bd858b122`)
- Tenant: `4906532d-94ad-444c-89cf-e394d7d73581` (GoCold Warehouse Management)

## Critical CC API gotchas (learned the hard way)

1. **Search endpoints are POST**, not GET. Bodies can be large condition
   trees. Treat as reads in our auth/permission logic.
2. **Two date-filter patterns**:
   - `arrivalDate` (POs) uses ValueField + `YYYY-MM-DD`
   - `/timestamps/packed/time` (SOs) uses JsonField pointer + ISO 8601
3. **CSV exports from CC's UI omit Qty** on sale orders — the API has it.
   This is why we built the API extract instead of using CSV exports.
4. **Stock on Hand is async.** POST creates a report run, poll GET
   /report-runs/{id} until status=SUCCESS or FAILED.
5. **Rate limit** of 30 req/min on outbound order create. Reads aren't
   capped that hard but be polite.
6. **API version**: `Accept-Version: 1` for almost everything; warehouse
   products supports `Accept-Version: 8` for the latest schema. **Carton dims
   (L/W/H) on the UoM exist ONLY under v8** — a v1 PATCH returns 200 but
   SILENTLY DROPS length/width/height (only `weight`, a v1 field, persists),
   and v1/v8 even return different UoM objects (different ids). The validated
   dims-write recipe (M-DIMS-3, landed live 21 Jun 2026): **PATCH
   `/warehouse-products/{id}`** (NOT `/products/{id}` — that path is *transport
   products* / carton classes and 404s "Invalid product id"), JSON-Patch
   **`op:"add"`** (NOT `replace` — `replace` 422s "Path not exists" on an unset
   dim) on `/unitOfMeasures/{uom}/{dim}`, headers `Accept-Version: 8` +
   `Content-Type: application/json-patch+json`; read back under v8 to verify.
7. **`/warehouse-locations/search` returns 404** (not 403) on this tenant —
   the path is not exposed on the public v1 API. This is NOT a missing read
   scope. Location data therefore comes from (a) CC's UI XLS export
   (`data/locations/`, loaded by `src/locations/cc_loader.py`) and (b) the
   SOH report-run aggregated by `location` (`get_sku_locations`).
   So a "no stock locations" symptom in wave generation is a data/source
   issue, not a credential-scope one — don't re-chase the scope theory.
8. **SOH `aggregateBy` only accepts a fixed set of dimensions** (422 on
   anything else): productStatus, productGroup, productType, unitOfMeasure,
   inboundOrder, batch, receivedWeek, sscc, sapLineNo, expiryDate,
   **location**. Use `location` (NOT `warehouseLocation`) and `productType`
   (NOT `product`). In the aggregated SOH item, the SKU is under
   `details.product.references.code` and the location under
   `properties.location` — see `get_sku_locations` and `test_sku_locations`.

## Credentials & scopes

- **Only `./.env` holds live CC creds** (`CC_CLIENT_ID` / `CC_CLIENT_SECRET`
  / `CC_TENANT_ID`), OAuth2 client_credentials. The `dim-capture-app/*`
  envs are a different, not-yet-live auth model (Bearer `CC_API_KEY`) and
  currently hold placeholders only.
- **Granted scopes in use (all reads):** orders + SOH/inventory via the
  *WMS Create Job* role (`/outbound-orders`, `/inbound-orders`,
  `/report-runs`); carton dims via *WMS Add/Edit Product*
  (`/warehouse-products`). CC's `/uaa/userinfo` does not enumerate
  authorities — verify scope functionally (search + a SOH report-run).
- **Rotation:** done via "reset secret" on the existing client (same
  client ID, new secret — old secret dies server-side immediately, so any
  other host holding it, e.g. the NUC, breaks until updated). Last rotated
  5 Jun 2026, verified read-green (auth/orders/products/SOH).

## Safety rules — DO NOT VIOLATE

1. **No credentials in code or chat.** Always env vars via `.env`.
2. **Read-only client.** The `write_enabled` flag is off by default.
   Don't enable it for any flow that hasn't been explicitly approved.
3. **Never push slotting rules to CC automatically.** Output as CSV, let
   a human review and import via CC's UI.
4. **Test with `--dry-run` first** when running extracts in unfamiliar
   states. Counts before file writes.

## Open work / where we left off

- API client + extract + analysis all working end-to-end against real
  Forage data (validated 10 May 2026).
- **Carton dim capture is DONE** (~409 SKUs, captured 12 May 2026 via the
  Go Cold branded `capture_template.xlsx`). **dims→CC sync: FIRST REAL WRITE
  LANDED** (M-DIMS-3, 21 Jun 2026). One sandbox SKU (`sHL-BWC`) got full
  L/W/H + weight written to CC and read-back verified, via `src/dims_write/`
  (the W0–W5 gate chain → human hard stop → PATCH warehouse-products UoM under
  v8 → read-back). **UNITS CORRECTION (23 Jun 2026): CC's UoM L/W/H are
  CENTIMETRES, not mm** (Jake, confirmed against the CC UI — supersedes the
  earlier "mm" read-back). The capture template is in mm, so the dims-write
  scripts now convert mm→cm (÷10) at the write boundary via
  `dims_write.captured_cc_dims_table` (weight stays kg). ⚠ Dims already written
  live before this fix (`sHL-BWC` sandbox + the 4 EA Forage SKUs from M-DIMS-5b)
  are 10× too large and need correcting in a separate, deliberately-armed run.
  The earlier
  `dim-capture-app/` legacy-API approach (Bearer key, `/products` PATCH on
  `app.cartoncloud.com.au/api/v1`) is **superseded** — the live OAuth2 API
  writes dims natively (see gotcha #6 for the recipe). Remaining before the
  live Forage rollout: build the all-~409-SKU loop (rate-limited) and
  deliberately flip the `assert_sandbox_only` allow-list from sandbox→Forage
  (it refuses to write to Forage until that approved change is made).
  Run previews with `scripts/run_dims_shadow_validate.py` (no write); the
  human-gated write is `scripts/run_dims_sandbox_roundtrip.py`.
- **M-DIMS-5c (CT carton-UoM write) is DROPPED from automated scope — CC-side
  name trap, not a code bug.** The armed 5c run fail-fast halted on AE-BLA with
  a 422 `{"field":"/unitOfMeasures/CT/name","message":"Must be between 3 and 64
  characters."}`. A read-only census (`scripts/probe_ct_uom_names.py` →
  `dims_write.ct_probe`, 23 Jun 2026) found **all 81 live CT UoMs are named
  `"CT"` (2 chars), 0 valid** — adding a dim under `/unitOfMeasures/CT/` makes CC
  validate the whole UoM object and its name is below the 3-char floor. Fixing CT
  names is a **manual CC-UI job Jake will do by hand**, so the automated target
  moves to the **Each / Base UoM** (every SKU has one). Before building that
  each-write, probe the Base UoM the same way, read-only:
  `scripts/probe_each_uom_names.py` → `dims_write.each_probe` buckets each SKU
  each-writable / each-blocked (same name trap) / no-each. Shared name-validation
  lives in `dims_write.uom_name` (CC's 3–64 char rule). Probe verdict: Base UoM
  cohort is CLEAN (455/455 valid), so the each-write is unblocked.
- **M-DIMS-5d (Each/Base UoM dims write) BUILT, CC-mocked, NOT run live.**
  `dims_write.run_each_bulk` + `scripts/run_dims_each_bulk.py` — the same proven
  engine as 5c with `resolve_default_uom` (the each) swapped in for the CT
  resolver; dims written in cm via `captured_cc_dims_table`. Live-gated
  (`CC_LIVE_PROMOTION`, default-closed), ONE batch hard stop, fail-fast,
  `finalize_exit` still-armed safeguard. `--only CODES` restricts the run for
  Jake's first deliberate few-SKU cm test (eyeball in CC, confirm cm) before the
  bulk. **cm CONFIRMED LIVE; the bulk wrote 132 SKUs then hit the name-poison
  finding** (below). CT carton UoM is CLOSED (out of automated scope).
  - **Name-poison guard (`block_on_poisoning_uom`, default-on in `run_each_bulk`).**
    The live bulk fail-fast halted on HL-6VA with a 422 on `/unitOfMeasures/CT/name`
    *while writing EA* — CC validates the WHOLE product UoM set on any dims PATCH, so
    a sibling UoM with an invalid name (the 2-char `CT`) poisons the each write too.
    Guard: `find_poisoning_uoms` skips any SKU with a UoM whose name fails CC's 3–64
    rule (general, name-length based — not CT-hardcoded; a valid CT name wouldn't
    block, so fixing names auto-unblocks). Cohort now: 180 writable / 5 name-poisoned
    & skipped (FB-PSM, HL-6HH, HL-6SC, HL-6VA, TSP-OYS) / rest no-op or no-dims. See
    `DIMS_UOM_STATE.md`. NEXT: Jake reviews PR #27, then re-runs (132 no-op).
    Open Q for Jake: is the 2-char CT name fixable on live master?
- Now that dims exist locally, next build:
    - Slotting recommendations: which SKU at which bay height
      (1500/1100/750mm) given (cube × velocity × replen frequency)
    - Replen rule generator: set qty trigger vs max-fill trigger per SKU
    - True bench-bypass threshold based on pallet fit, not just qty
- Dispatch v1 (predict-to-run) built; v2 = stop sequencing; write-back
  pending SAP B1 boundary.
- Run sequencing needs a separate convo about how runs are currently
  defined and what road clusters make sense for these postcodes.

## House style notes

- Australian English (no z's where s's belong)
- "Weapons grade" code: complete, production-ready, no placeholders
- Follow Rolodex AI conventions: gitignore `.env`, requirements.txt for deps,
  README + CLAUDE.md at root, `src/` layout for importable code
- No agent loops on the pick bench — fixed event-driven pipelines only
