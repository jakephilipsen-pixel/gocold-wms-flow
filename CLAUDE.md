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
   products supports `Accept-Version: 8` for the latest schema.
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
  Go Cold branded `capture_template.xlsx`). **The next blocker is dims→CC
  sync** — getting captured dims into CartonCloud. That work lives in the
  `dim-capture-app/` sub-project (modules 02 `cc-client` PATCH /products +
  04 `dim-api`/syncService — both not yet built).
- Now that dims exist locally, next build:
    - Slotting recommendations: which SKU at which bay height
      (1500/1100/750mm) given (cube × velocity × replen frequency)
    - Replen rule generator: set qty trigger vs max-fill trigger per SKU
    - True bench-bypass threshold based on pallet fit, not just qty
- Run sequencing needs a separate convo about how runs are currently
  defined and what road clusters make sense for these postcodes.

## House style notes

- Australian English (no z's where s's belong)
- "Weapons grade" code: complete, production-ready, no placeholders
- Follow Rolodex AI conventions: gitignore `.env`, requirements.txt for deps,
  README + CLAUDE.md at root, `src/` layout for importable code
- No agent loops on the pick bench — fixed event-driven pipelines only
