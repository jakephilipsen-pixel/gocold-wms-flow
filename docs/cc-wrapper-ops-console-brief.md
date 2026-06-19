# Go Cold WMS — CartonCloud Ops-Console Wrapper: Project Brief & Build Directive

**Audience:** Claude (claude.ai) picking up this project to extend it.
**Status of this doc:** self-contained. You do not need any prior context — everything you need to understand the project and the new direction is below.
**Date:** 19 June 2026.

---

## 0. What you are being asked to do (read this first)

We are changing direction — with the boss's sign-off — from a read-only analysis toolkit to a **unified daily-operations console that wraps CartonCloud (CC)**.

- **CartonCloud stays the single source of truth.** We do not build a parallel datastore that competes with CC. The wrapper reads live state from CC, presents it to floor staff in purpose-built screens, and **writes approved changes back into CC**.
- The wrapper is the **staff-facing layer** for the whole daily flow: receiving/putaway → stock → pick waves → dispatch runs. Today those live as separate read-only tools and two separate web consoles. The job is to unify them and add the write path.
- The key technical shift is **extending our CC API integration from read-only to read+write.** Good news: we have already done this once, safely, in a sub-project (`dim-capture-app/`). That is the reference pattern to copy — not reinvent.

**Concretely, when you take this on, you should:**
1. Read the current state below and confirm it against the actual files in the repo.
2. Propose a consolidated architecture for the unified ops console (CC-as-source-of-truth, read+write).
3. Produce/refresh the planning docs in the project folder (vision, module breakdown, write-enablement plan) so the existing framework (`/new-project` → `/build-module` → `/compile-stress` → `/deploy-local`) can build it module by module.
4. **Do not enable any write to CC outside an explicit, gated, human-approved path.** The safety model is non-negotiable and described in §7.

---

## 1. The business context

- **Operator:** Go Cold — a cold-chain 3PL in Scoresby, VIC.
- **WMS:** CartonCloud (cloud SaaS). This is the system of record the warehouse already runs on. We are not replacing it; we are wrapping it.
- **Primary customer:** The Forage Company. ~100–120 sale orders/day, ~15 lines/order, ~438–460 active SKUs. Smaller customers exist but are deprioritised — all tooling targets Forage.
- **Hardware on the floor:** ASUS NUC (16GB / 500GB NVMe, the host), Symbol/Zebra scanners, Live! Cam Sync 3, Zebra ZT411 (industrial pick-bench printer) and ZQ630 (mobile, putaway team).
- **The hard constraint — read this twice:** the workforce is **change-averse**, and there is **zero tolerance for breakage**. Anything that ships to the floor must work first time. The established way of working here is: **build behind the scenes → validate in shadow mode → roll out**. Write-back especially must be proven before it is trusted.

---

## 2. The vision: a CartonCloud ops-console wrapper

One web app, run on the NUC, served on the warehouse LAN, that becomes the daily driver for floor staff — with CartonCloud underneath as the source of truth.

```
                       ┌─────────────────────────────┐
                       │      CartonCloud (WMS)       │  ← single source of truth
                       │  orders · stock · products · │
                       │   locations · consignments   │
                       └───────────┬─────────────────┘
                          reads ▲  │  ▼ writes (gated, approved)
                                 │  │
                       ┌─────────┴──┴─────────────────┐
                       │   Ops-Console Wrapper (NUC)   │
                       │  FastAPI + HTMX + SSE         │
                       ├──────────────────────────────┤
                       │  Receiving / Putaway          │
                       │  Stock & Slotting             │
                       │  Pick Waves   (built today)   │
                       │  Dispatch Runs (built today)  │
                       └──────────────────────────────┘
                                 ▲
                         floor staff on LAN
                    (picks/runs/dims .gocold.local)
```

The wrapper unifies what are currently **two separate read-only consoles** (pick + dispatch) and the **dim-capture PWA**, and grows the surfaces that don't exist yet (receiving/putaway, live stock & slotting actions), all sharing one CC client and one safety model.

---

## 3. Where the project is today (honest current state)

The foundation is real and validated — this is **not** a greenfield build. Validated against live Forage data (10 May 2026): 95,212 SO line items / 90 days; 9,613 PO line items / 180 days; ~460 active products.

### 3.1 What's built and working (read-only against CC)

- **CC API client** (`src/cc_client/`): OAuth2 client-credentials auth, token refresh, retry/backoff, paginated POST-search helpers. Read endpoints for outbound orders, inbound orders, warehouse products, and stock-on-hand (SOH) report-runs.
- **Analysis engine** (`src/analysis/`, 21 modules, no stubs): per-SKU velocity & ABC, order-density patterns, co-occurrence zoning, slotting (bay/height from cube × velocity × replen), routing (habitual address→run learning), wave-pick generation off live SOH, carton splits, dim loading.
- **Wave-pick console** (`src/web/`, FastAPI + HTMX + SSE): triggers live wave generation, streams progress, produces Zebra-ready PDF + CSV pick sheets. Launcher `scripts/serve_web.py` (127.0.0.1:8000). Published on LAN as `picks.gocold.local`.
- **Dispatch run console** (`src/web_dispatch/`, FastAPI + HTMX + SSE): predicts today's open orders onto habitual delivery runs (confidence + reason), splits carriers, produces per-run manifests. Launcher `scripts/serve_web_dispatch.py` (127.0.0.1:8078). Published on LAN as `runs.gocold.local`.
- **Carton dims captured:** ~409–429 SKUs measured locally (L/W/H ~100%, inner-pack-qty ~99.5%, weight ~69%). ~128 carton weights are genuinely missing and need physical weighing — do not estimate them.
- **Tests:** ~39 pytest files, suite green at last audit (2026-06-07).

### 3.2 What writes to CC already (the reference pattern — important)

The main repo is **read-only by design**, but a sub-project has **already shipped a safe write path to CartonCloud**. Study it before building any new writes.

- **`dim-capture-app/`** — a separate full-stack app (React 19 PWA + Express/TypeScript + PostgreSQL), 14 modules, 13–14 built, tested and locally validated (2026-06-07). It lets the putaway team scan a carton barcode, enter dims, and **sync them into CartonCloud**.
  - **Module 02 `cc-client`** (`backend/src/services/ccClient.ts`): `patchProductDims()` does a real `PATCH /products/{id}` with `{length,width,height,weight}`. Token-bucket rate limiter (60/min, split buckets for sync vs seed), typed errors, 12s abort timeout.
  - **Module 04 `dim-api`** (`backend/src/services/syncService.ts`): `syncUnsyncedDims()` batches unsynced dims (10 at a time) and PATCHes each to CC via `POST /api/sync/cc`. Uses `pg_try_advisory_xact_lock` to serialise concurrent syncs → exactly-once PATCH.
  - **Module 12 `cc-write-authz`:** every CC-write route requires an `X-Sync-Key` header. Missing/wrong → 401; secret unset on the server → **503 fail-closed** (it refuses to run rather than write unguarded).
  - **Module 13 `write-concurrency`:** same-SKU captures serialise via `pg_advisory_xact_lock`.
  - **Deploy state:** locally validated; **production deploy to the NUC is pending manual sign-off** (needs `SYNC_SECRET`, CC creds, DNS). Served on LAN as `dims.gocold.local`.

**Takeaway:** the "0 of 460 dims in CC" blocker is no longer a capture problem and no longer an unsolved write problem — the safe write mechanism exists and is tested. The wrapper generalises this proven pattern (rate-limited client + gated, fail-closed, idempotent write service) to the rest of daily ops.

### 3.3 The explicit write gates already in code (do not bypass)

- `src/cc_client/client.py` (~line 139): any non-GET request **raises** unless `write_enabled=True` (default `False`; env override `CC_WRITE_ENABLED=true`). There are currently **no** POST/PUT/PATCH/DELETE helper methods in the Python client — reads only.
- `src/dispatch/sinks.py` (`CartonCloudSink`, ~lines 42–57): the dispatch write-back sink **refuses to act** — both `write_enabled` and `dispatch_write_approved` must be set and "the SAP B1 boundary cleared" first, and the body is `NotImplementedError`. Dispatch output goes to review files for human approval only.

These gates are features, not bugs. Keep them. New write paths follow the same fail-closed shape.

---

## 4. The daily-ops surfaces the wrapper needs

Map of each console surface, what exists today, and what write operation it implies. The reads are largely done; the work is the write path + the missing surfaces + unification.

| Surface | State today | CC reads (have) | CC writes to add (gated) |
|---|---|---|---|
| **Receiving / Putaway** | Not built as a surface; inbound-order reads exist | inbound orders, products, locations | confirm receipts, assign putaway locations |
| **Stock & Slotting** | Slotting analysis exists (CSV out, manual import) | SOH report-runs, products, locations | push slotting/location moves, replen triggers |
| **Pick Waves** | **Built** (read-only console, PDF/CSV out) | orders, SOH, products | mark waves/lines picked, write pick confirmations |
| **Dispatch Runs** | **Built** (read-only console, manifests out) | consignments, orders | assign orders→runs, set run/consignment status |
| **Dims (products)** | **Built & writing** in `dim-capture-app/` | products | `PATCH /products/{id}` dims ✅ already live |

The shared spine: one CC client (read+write, gated), one auth/sync-key model, one SSE progress pattern, one approval-gate convention. Every write surface should be shippable in **shadow mode first** (compute the change, show it, require approval) before it's allowed to actually call CC.

---

## 5. Stack & conventions

- **Python 3.11+**, pandas, pyarrow, httpx for the data/analysis core and the existing FastAPI + HTMX + SSE consoles.
- **dim-capture-app** is the exception: React 19 + Express/TS + PostgreSQL (it predates the consolidation and proves the write pattern).
- The wrapper should extend the **Python/FastAPI** consoles rather than fork a second stack, unless there's a strong reason — keep the floor on one app.
- Deployment target is the **NUC**, served on the **warehouse LAN** via Caddy (`*.gocold.local`). Cloudflare tunnels exist for remote access but LAN is the floor's path.
- House style: **Australian English** (no American "z"s). "Weapons-grade" code — complete, production-ready, no placeholders. Rolodex AI conventions: `.env` git-ignored, `requirements.txt`, README + CLAUDE.md at root, `src/` layout. **No agent loops on the pick bench — fixed, event-driven pipelines only.**

---

## 6. Critical CartonCloud API gotchas (carry these over — learned the hard way)

1. **Search endpoints are POST**, not GET (large condition-tree bodies). Treat them as reads in auth/permission logic.
2. **Two date-filter patterns:** POs use `arrivalDate` (ValueField + `YYYY-MM-DD`); SOs use `/timestamps/packed/time` (JsonField pointer + ISO 8601).
3. **CC's UI CSV export omits Qty** on sale orders — the API has it. That's why we extract via API, not CSV.
4. **Stock on Hand is async:** POST creates a report run; poll `GET /report-runs/{id}` until `status=SUCCESS` or `FAILED`.
5. **Rate limit ~30 req/min** on outbound-order create. Reads aren't capped as hard but be polite. (The dim-capture client already implements a 60/min token bucket — reuse that thinking.)
6. **API version:** `Accept-Version: 1` for almost everything; warehouse-products supports `Accept-Version: 8` for the latest schema.
7. **`/warehouse-locations/search` returns 404** (not 403) on this tenant — the path isn't on the public v1 API. This is **not** a missing scope. Location data comes from (a) CC's UI XLS export (`data/locations/`, via `src/locations/cc_loader.py`) and (b) the SOH report-run aggregated by `location`. So "no stock locations" in wave generation is a data-source issue, not a credential one — don't re-chase the scope theory.
8. **SOH `aggregateBy` accepts only a fixed set of dimensions** (422 otherwise): productStatus, productGroup, productType, unitOfMeasure, inboundOrder, batch, receivedWeek, sscc, sapLineNo, expiryDate, **location**. Use `location` (not `warehouseLocation`) and `productType` (not `product`). In the aggregated SOH item the SKU is at `details.product.references.code` and the location at `properties.location`.
9. **The OAuth2 client is NOT customer-scoped** — it sees the whole tenant (~3754 products). Always pass the Forage customer id to scope queries: `d4810e1e-91ab-43ed-b68e-b72bd858b122`. Tenant: `4906532d-94ad-444c-89cf-e394d7d73581`.

---

## 7. Safety rules — DO NOT VIOLATE

1. **No credentials in code or chat.** Always env vars via `.env` (git-ignored). The live CC creds (`CC_CLIENT_ID` / `CC_CLIENT_SECRET` / `CC_TENANT_ID`, OAuth2 client_credentials) live only in `./.env`.
2. **Read-first, write-never until explicitly enabled.** The `write_enabled` flag stays off by default. Do not flip it for any flow that hasn't been explicitly approved.
3. **Every write path is gated and fail-closed**, following the `dim-capture-app` model: required auth header (`X-Sync-Key`-style), 401 on bad/missing key, **503 if the secret is unset** (refuse rather than write unguarded), and idempotency/serialisation on concurrent writes.
4. **Shadow mode before live.** A write surface first computes and displays the proposed change for human approval; only after validation against reality is the actual CC call allowed.
5. **Never auto-push slotting/dispatch decisions to CC.** Output for human review, let a person approve, then write through the gated path. The SAP B1 boundary must be cleared before dispatch write-back.
6. **`--dry-run` first** for any extract/sync in an unfamiliar state — counts before file writes, diffs before CC writes.

---

## 8. Your task — what to put in the project folder

When you take this on, update the repo so the build can proceed under the existing framework:

1. **A vision/north-star doc** (e.g. `docs/OPS_CONSOLE_VISION.md`) capturing §2–§4 above as the agreed direction, with CC as source of truth and the unified-console scope.
2. **A write-enablement plan** that, per surface (receiving/putaway, stock/slotting, picks, dispatch), specifies: the CC reads in hand, the CC writes to add, the exact endpoint + version, the gate/approval model, and the shadow-mode → live rollout step.
3. **A module breakdown** (`MODULES.md`-style) that decomposes the wrapper into buildable modules in dependency order, sized so each is a single focused build — generalising the `dim-capture-app` module pattern. Start from the lowest-risk, highest-value write (dims sync is already done; next candidates are pick-confirmation and putaway-location writes in shadow mode).
4. **Refresh `CLAUDE.md`** at root to state the new direction (wrapper / read+write / CC source of truth) while preserving the API gotchas (§6) and safety rules (§7) verbatim.
5. **Do not write any code that calls CC with a mutating verb** until the gate, the auth header, the fail-closed behaviour, and the shadow-mode display are in place and tested — mirror `dim-capture-app` modules 02, 04, 12, 13.

Keep the floor on one app, keep CC the source of truth, keep every write behind a gate, and prove it in shadow mode before it touches a single live order. That's the whole game.
