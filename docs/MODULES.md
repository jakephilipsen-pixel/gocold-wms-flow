# MODULES.md — ops-console wrapper write-enablement, buildable module breakdown

**Status:** planning doc. No code in this commit.
**Companion to:** `docs/GROUND_TRUTH.md`, `docs/WRITE_ENABLEMENT_PLAN.md`.
**Framework:** built under the existing lifecycle (`/new-project` →
`/build-module` → `/compile-stress` → `/deploy-local` → `/deploy-nuc`). One
focused build per module, dependency-ordered.
**Generalises:** dim-capture-app's module pattern (02 cc-client write, 04
dim-api, 12 cc-write-authz, 13 write-concurrency), now proven (134 tests pass,
2026-06-19).

Each module lists: what it is, what it depends on, its definition of done, and
whether it may issue a real CC write. **Modules W0–W5 contain NO mutating CC
verb** — they build the gates first. The first real PATCH is M-DIMS-3, and only
against the sandbox.

---

## Phase W — the shared write spine (no surface writes yet)

> Build order is strict. Nothing past W5 may call CC with a mutating verb until
> W1–W5 exist and pass with CC mocked.

### W0 — `write-config`
- **What:** config surface for write enablement: `CC_WRITE_ENABLED` (default
  false), `CC_WRITE_SECRET`, `CC_WRITE_CUSTOMER_ALLOWLIST` (default = sandbox id
  ONLY: `a8dab3f2-defa-433e-87a0-01dee48a2286`).
- **Depends on:** nothing.
- **Done when:** config loads from env, defaults are closed (write disabled,
  allow-list = sandbox only), live Forage id is **absent** by default. Test
  asserts defaults.
- **Writes CC:** no.

### W1 — `cc-mutate-core`
- **What:** the single guarded `_mutate()` method on `src/cc_client/client.py`.
  Double-gate (`write_enabled` AND per-call `approved`), 12s timeout → typed
  error. Does NOT use the `post_search`/report-run flip-in-finally trick.
- **Depends on:** W0.
- **Done when:** calling `_mutate` with gates closed raises; with gates open and
  a mock transport, issues the request once; timeout converts to typed error.
  All tested, **CC mocked**.
- **Writes CC:** no (mock transport in tests).

### W2 — `cc-write-authz`  *(analogue of dim-capture-app module 12)*
- **What:** write-auth secret check. Unset/empty secret → **refuse**
  (503-analogue). Wrong/missing approval token → refuse (401-analogue). Constant-
  time compare (`hmac.compare_digest`).
- **Depends on:** W0, W1.
- **Done when:** four tests pass mirroring dim-capture-app rigour — refuse on
  unset secret, refuse on empty secret, refuse on missing token, proceed on
  correct. **CC mocked.**
- **Writes CC:** no.

### W3 — `cc-write-customer-guard`  ✅ Done (`feature/write-spine-w3`, merged PR #10)  *(the §0 guard rail — most safety-critical)*
- **What:** before any mutate, resolve the target object's customer id and assert
  it ∈ allow-list. Not in list → refuse, log offending id.
- **Depends on:** W0, W1.
- **Done when:** test asserts a **live-Forage-id** target
  (`d4810e1e-...`) is **refused even with every other gate open**; sandbox id
  passes. **CC mocked.**
- **Writes CC:** no.

### W4 — `cc-write-idempotency`  ✅ Done (`feature/write-spine-w4`, merged PR #11)  *(analogue of dim-capture-app module 13)*
- **What:** per-object serialisation (in-process lock keyed by object id) +
  read-before-write diff (empty diff → no-op).
- **Depends on:** W1.
- **Done when:** concurrent mutates to the same id serialise; a mutate whose
  payload already matches current CC state no-ops. **CC mocked.**
- **Writes CC:** no.

### W5 — `cc-rate-limit`  ✅ Done (`feature/write-spine-w5`, PR #12)
- **What:** token-bucket limiter on the mutate path. Ceiling = lower of CC's
  ~30/min (outbound create) and 60/min (dim-capture-app bucket) per endpoint.
  Reject (don't queue) when spent.
- **Depends on:** W1.
- **Done when:** limiter rejects past ceiling; refills correctly; tested.
- **Writes CC:** no.

**Gate W→surface:** W0–W5 complete and green (CC mocked) before any surface
module. This is the `docs/WRITE_ENABLEMENT_PLAN.md` §5 checklist.

---

## Phase DIMS — first surface (pattern already proven)

### M-DIMS-1 — `dims-write-decision`  ✅ DONE (decision, 2026-06-20)
- **Decision: ROUTE B — port the dims write natively into the W0–W5 Python spine.**
  NOT integrate/call the dim-capture-app Node service.
- **Rationale:** one stack on the floor (brief §5), one gate model, one deployable —
  and the right shape for the marketable-WMS ambition (§6.3). dim-capture-app becomes
  a **reference to port from, not a service to call**; its 134 tests are the
  behavioural spec for the Python port.
- **Carry-over from the verified dim-capture-app code:** `PATCH /products/{id}`,
  `Accept-Version: 1`, units **mm** (L/W/H) and **kg** (weight), **no conversion**.
  Idempotency is **not** ported as advisory-lock code — it's provided by **W4**
  (in-process lock by product id + read-before-write diff), since the Python side
  has no Postgres.
- **Writes CC:** no.

### M-DIMS-2 — `dims-shadow`
- **What:** dims write surface in **shadow mode**. Reads CC product, computes
  dim diff, displays proposed PATCH, requires human approve. Mutate never fires.
- **Depends on:** M-DIMS-1, W-phase.
- **Done when:** shadow path shows correct diffs for sandbox SKUs; approve button
  wired but disabled from calling CC. **CC mocked.**
- **Writes CC:** no.

### M-DIMS-3 — `dims-sandbox-roundtrip`  *(FIRST REAL CC WRITE)*
- **What:** with allow-list = sandbox only, perform real `PATCH /products/{id}`
  against ONE **named, known-active** sandbox SKU (active-status verified by a read
  first — "allow-listed" ≠ "safe to target blind", see WRITE_ENABLEMENT_PLAN §2.3).
- **Agreed first-PATCH protocol (restore-after, original sourced from CC):**
  1. **GET** the SKU's original dims and store them.
  2. **PATCH** the new dims.
  3. **read-back verify** the new dims landed.
  4. **PATCH back** to the stored original dims.
  5. **read-back verify** the original dims are restored.
  Two round-trips; the original values come from CC itself (not assumed). Leaves the
  sandbox SKU exactly as found.
- **Depends on:** M-DIMS-2, all W-gates green.
- **Done when:** the 5-step protocol passes against one named sandbox SKU,
  idempotent re-run no-ops (W4), audit log records each PATCH. **This is the
  CC-round-trip proof the 134 mocked tests cannot give.** Jake reviews this module
  closely.
- **Writes CC:** YES — sandbox customer only.

### M-DIMS-4 — `dims-sandbox-soak`
- **What:** run dims sync across all 46 active sandbox SKUs in normal operation
  for the agreed soak period. (46 active = the `s`-prefixed Forage mirrors;
  the customer holds 1111 total incl. ~1065 inactive `ZZ*` SKUs — see
  WRITE_ENABLEMENT_PLAN §0.)
- **Depends on:** M-DIMS-3.
- **Done when:** soak passes — no double-applies, rate limits respected, errors
  handled against the real endpoint.
- **Writes CC:** YES — sandbox only.

### M-DIMS-5 — `dims-live-promotion`  *(separately approved, boss sign-off)*
- **What:** one reviewed commit adding live Forage id to the allow-list. Nothing
  else.
- **Depends on:** M-DIMS-4 + explicit boss approval.
- **Done when:** allow-list change committed + reviewed in isolation; first live
  dims write observed and confirmed.
- **Writes CC:** YES — live, after sign-off.

---

## Phase PICKS — second surface (highest daily value)

> Endpoint TBD — `M-PICKS-0` discovers it first.

- **M-PICKS-0 — `picks-write-endpoint-discovery`** — identify the exact CC
  endpoint/version to mark waves/lines picked. No code beyond a verified API
  call against sandbox. *Writes CC: read-only probe.*
- **M-PICKS-1 — `picks-shadow`** — pick-confirmation in shadow mode off the
  existing read-only wave console. *Writes CC: no.*
- **M-PICKS-2 — `picks-sandbox-roundtrip`** — one real pick confirmation against
  a sandbox order. *Writes CC: sandbox only.*
- **M-PICKS-3 — `picks-sandbox-soak`** — *Writes CC: sandbox only.*
- **M-PICKS-4 — `picks-live-promotion`** — *Writes CC: live, after sign-off.*

---

## Phase PUTAWAY — third surface (validate API capability first)

> ⚠ May be API-blocked: `/warehouse-locations/search` 404s on this tenant
> (GROUND_TRUTH / brief §6.7). Confirm a location-assignment WRITE path exists
> before committing.

- **M-PUT-0 — `putaway-write-capability-check`** — determine whether this
  tenant's API supports the needed receipt-confirm / location-assign writes at
  all. If blocked, this phase stops here and the surface stays manual.
  *Writes CC: read-only probe.*
- **M-PUT-1 — `putaway-shadow`** — *Writes CC: no.*
- **M-PUT-2 — `putaway-sandbox-roundtrip`** — *Writes CC: sandbox only.*
- **M-PUT-3 — `putaway-sandbox-soak`** — *Writes CC: sandbox only.*
- **M-PUT-4 — `putaway-live-promotion`** — *Writes CC: live, after sign-off.*

---

## Phase DISPATCH — last surface (gated behind SAP B1)

> Highest blast radius. `CartonCloudSink` already refuses + `NotImplementedError`.
> SAP B1 owns dispatch writes today; the SAP B1 boundary must be cleared with the
> boss before this phase starts.

- **M-DISP-0 — `dispatch-sapb1-boundary`** — resolve, with the boss, whether CC
  dispatch write-back is permitted given SAP B1 ownership. Decision module.
  *Writes CC: no.*
- **M-DISP-1 — `dispatch-shadow`** — replace the review-file output with an
  in-console shadow approve. Keep `dispatch_write_approved` gate. *Writes CC: no.*
- **M-DISP-2 — `dispatch-sandbox-roundtrip`** — *Writes CC: sandbox only.*
- **M-DISP-3 — `dispatch-sandbox-soak`** — *Writes CC: sandbox only.*
- **M-DISP-4 — `dispatch-live-promotion`** — *Writes CC: live, after SAP B1
  boundary cleared + sign-off.*

---

## Phase PRODUCT (optional, parallel) — multi-3PL quarantine

> Only if the marketable-WMS ambition is live (open decision §6.3). Cheap now,
> painful later.

- **M-PROD-1 — `tenant-config-seam`** — move hardcoded Forage id, tenant id,
  `.gocold.local`, allow-list, SAP B1 boundary behind a per-deployment config
  object. No behaviour change for Go Cold. *Writes CC: no.*
- **M-PROD-2 — `locations-source-abstraction`** — abstract the XLS-export +
  SOH-aggregation locations workaround (the 404 path) behind an interface so
  other tenants with a working locations API can swap it. *Writes CC: no.*

---

## Build-order summary (the critical path)

```
W0 → W1 → {W2, W3, W4, W5}        ← gates, no CC writes
        │
        └→ M-DIMS-1 → M-DIMS-2 → M-DIMS-3 ⚡ → M-DIMS-4 → M-DIMS-5 ⚡⚡
                                   (first sandbox      (live, boss
                                    PATCH)              sign-off)
        then PICKS → PUTAWAY → DISPATCH, each repeating the
        shadow → sandbox-roundtrip → soak → live-promotion gate.

⚡  = first real CC write (sandbox only)
⚡⚡ = first live CC write (separately approved)
```

---

## Footer
- Companion to GROUND_TRUTH.md @ `7f4be88`, WRITE_ENABLEMENT_PLAN.md (same commit).
- Sandbox: `a8dab3f2-defa-433e-87a0-01dee48a2286` (same tenant as live Forage).
- No code, no flag, no mutating verb in this commit.
- Date: 2026-06-20. Author: claude.ai, from verified repo + sandbox facts.
