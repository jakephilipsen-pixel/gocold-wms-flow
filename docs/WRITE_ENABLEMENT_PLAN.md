# WRITE_ENABLEMENT_PLAN.md — extending gocold-wms-flow from read-only to gated read+write

**Status:** planning doc. No code in this commit. Nothing here flips a write flag
or adds a mutating CC verb.
**Companion to:** `docs/GROUND_TRUTH.md` (build state) and
`docs/cc-wrapper-ops-console-brief.md` (direction). Where the brief and ground
truth disagree, **ground truth wins**.
**Reference pattern:** the `dim-capture-app` repo
(`github.com/jakephilipsen-pixel/dim-capture-app`, `main` @ `8e3b065`), whose
backend suite was independently re-run on 2026-06-19 — **134 tests pass** — and
whose gate logic (503 fail-closed, 401, advisory-lock idempotency) is verified.
**Caveat carried forward:** every dim-capture-app test mocks CartonCloud. The
gate is CC-mocked-proven, **not** CC-round-trip-proven. This plan's entire
purpose is to add the missing round-trip proof safely.

---

## 0. The one fact that shapes every decision below

**The sandbox is in the same CC tenant as live Forage.**

- Sandbox customer: `SANDBOX TEST - FORAGE` →
  `a8dab3f2-defa-433e-87a0-01dee48a2286` (**46 active** products, Forage
  codes/descriptions with an `s` prefix). Confirmed by a scoped CC read on
  2026-06-20: the customer holds 1111 products total, but only 46 are active —
  those 46 are the `s`-prefixed Forage mirrors; the other ~1065 are
  inactive/archived `ZZ*` legacy test SKUs. Note the customer-id allow-list
  (§2.3) admits *all* products under this customer, not just the 46 active — the
  active-status / `s`-prefix filter is an operational selector layered on top of
  the customer-id safety boundary.
- Live customer: `The Forage Company` → `d4810e1e-91ab-43ed-b68e-b72bd858b122`.
- Tenant (both): `4906532d-94ad-444c-89cf-e394d7d73581`.

Because both customers live in **one tenant**, the same OAuth2 client that can
PATCH a sandbox product can physically reach a live Forage product. **There is
no tenant boundary protecting live data.** The only thing standing between a test
write and a real Forage product is customer-id scoping *in our code*.

The `s`-prefix on SKU codes is a **human tell, not a guard rail.** The guard rail
is a hard, positive allow-list assertion on customer id (§2.3). Treat any write
path that can resolve a target product without checking its customer id against
an explicit allow-list as **unsafe and unshippable.**

---

## 1. Principles (inherited, non-negotiable)

These come from the brief §7 and the verified code; restating so the plan can be
read standalone.

1. **CC is the single source of truth.** No parallel datastore. Reads are live;
   writes go back into CC through the gated path.
2. **Default-closed.** `client.py:139` raises on any non-GET unless
   `write_enabled=True`. Default stays `False`. No flow flips it except an
   explicit, gated, approved write.
3. **Fail-closed on missing config.** Mirror dim-capture-app: if the write-auth
   secret is unset, **refuse (503-equivalent)** rather than write unguarded.
4. **Idempotent / serialised writes.** Concurrent writes to the same object must
   not double-apply. dim-capture-app uses Postgres advisory locks; the Python
   side has no Postgres, so §3 specifies the equivalent.
5. **Shadow mode before live.** Every write surface first *computes and displays*
   the proposed change for human approval. Only after a human approves does the
   actual CC call fire.
6. **Customer-id allow-list.** Every mutating call asserts the target object
   belongs to an allow-listed customer id. In all non-production config the
   allow-list contains **only the sandbox id**. Live Forage is added to the
   allow-list only by an explicit, separately-approved config change.

---

## 2. The shared write spine (build this once, before any surface)

Today the Python client is read-only by design and has **no** POST/PUT/PATCH/
DELETE helpers (verified — GROUND_TRUTH §2). Adding writes means adding a small,
heavily-gated spine that every surface reuses. This generalises dim-capture-app
modules 02 (`cc-client` write), 12 (`cc-write-authz`), 13 (`write-concurrency`).

### 2.1 A guarded mutate method on the Python client

Add a single private `_mutate()` entry point to `src/cc_client/client.py` — the
*only* place in the Python codebase allowed to issue a non-GET business write. It
must:

- Refuse unless `write_enabled` **and** a per-call `approved=True` token are both
  set (double-gate, mirroring `CartonCloudSink`'s `write_enabled and
  dispatch_write_approved`).
- Require a write-auth secret to be present in env; **if unset, raise (refuse) —
  never write unguarded.** This is the Python analogue of dim-capture-app's 503.
- Carry the rate-limit discipline dim-capture-app proved: ≤60 req/min, reject
  (don't queue) when the budget is spent. CC's documented ceiling on
  outbound-order create is ~30/min (brief §6.5) — use the **lower** of the two
  per endpoint.
- Apply a 12s abort timeout (dim-capture-app `CC_DEFAULT_TIMEOUT_MS`), convert
  timeouts to a typed error, never let a raw timeout escape.
- **NOT** reuse the `post_search`/`report-run` trick of flipping
  `write_enabled=True` inside a `finally`. Those are reads; a business write must
  be gated explicitly, not by transiently toggling the global flag.

### 2.2 The write-auth gate (Python analogue of `requireSyncKey`)

A required secret (`CC_WRITE_SECRET` or equivalent), checked before any mutate:

- secret unset/empty on the server → **refuse** (the 503 analogue);
- caller does not present the matching approval token → refuse (the 401
  analogue);
- correct → proceed.

Use a constant-time comparison (dim-capture-app uses `crypto.timingSafeEqual`;
Python equivalent is `hmac.compare_digest`).

### 2.3 The customer-id allow-list guard (the §0 guard rail)

Before issuing any mutate against a product/order/consignment, resolve the target
object's customer id and assert it is in `CC_WRITE_CUSTOMER_ALLOWLIST`. Default
allow-list = **`{a8dab3f2-... sandbox}` only.** A target whose customer id is not
in the list → refuse, loudly, with the offending id logged. Live Forage
(`d4810e1e-...`) is **absent** from the default allow-list and is added only by
an explicit, separately-approved config change at go-live.

This is the single most safety-critical check in the whole write path. It must
have its own unit test that asserts a live-Forage-id target is refused even when
every other gate is open.

**"Allow-listed" is not "safe to target blind."** The guard gates by *customer id*,
not by active-status. An allow-listed customer exposes its **entire** product set:
the sandbox customer holds **1111** products (only 46 active, `s`-prefixed — the rest
~1065 inactive/archived `ZZ*` legacy SKUs, see GROUND_TRUTH §5). The allow-list lets
a write reach **any** of those 1111, not just the 46 active. So M-DIMS-3 must target a
**deliberately chosen, known-active** sandbox SKU (verified active by a read first) —
never an arbitrary product just because its customer cleared the guard.

### 2.4 Idempotency / serialisation (Python analogue of advisory locks)

The Python side has no Postgres, so dim-capture-app's `pg_advisory_xact_lock`
doesn't transfer directly. Per surface, pick the lightest sufficient mechanism:

- For single-process FastAPI consoles: an in-process `asyncio.Lock`/`threading.Lock`
  keyed by object id, plus an idempotency check (don't re-PATCH a value that
  already matches CC's current state — read-before-write).
- Read-before-write doubles as a correctness check: fetch the object, compute the
  diff, and if the diff is empty, no-op. This is also what makes shadow mode
  honest (§4).

---

## 3. Per-surface write enablement

Ordered lowest-risk / highest-confidence first. Each surface ships **shadow-mode
first**, then a **single sandbox round-trip**, then (separately approved)
**sandbox→live promotion**. No surface skips a step.

Reads are largely already in hand (GROUND_TRUTH §1); the work is the write.

### 3.1 Dims (`PATCH /products/{id}`) — FIRST, because the pattern is proven

| | |
|---|---|
| CC reads in hand | warehouse-products read (GROUND_TRUTH Dims row) |
| CC write to add | `PATCH /products/{id}` with `{length,width,height,weight}` |
| Endpoint + version | `PATCH /products/{id}`, `Accept-Version: 1`; units **mm** for L/W/H, **kg** for weight (verbatim, no conversion — dim-capture-app convention) |
| Gate / approval | full spine (§2): double-gate + write-secret + allow-list + idempotency |
| Reference | dim-capture-app `ccClient.patchProductDims()` (line 421) — copy its shape |

**Why first:** the write mechanism already exists and is 134-test-proven *in its
own repo*. The remaining gap is exactly the round-trip this plan adds. Two viable
routes:

- **(a) Integrate dim-capture-app** as the dims write service (it already does
  this end-to-end, including the X-Sync-Key gate). gocold-wms-flow calls it; it
  owns the PATCH. Lowest new-code risk; introduces a second stack on the floor
  (brief §5 prefers one app — weigh this).
- **(b) Port `patchProductDims` into the Python spine** (§2). One stack, but
  re-implements proven code — must re-earn the 134 tests' worth of confidence.

**Decision deferred to Jake** (recorded as open in §6). Either way, the first
live action is one sandbox PATCH (§4).

### 3.2 Pick-confirmation (mark waves/lines picked) — SECOND, highest daily value

| | |
|---|---|
| State today | Pick-wave console **built, read-only** (PDF/CSV out) — GROUND_TRUTH |
| CC reads in hand | orders, SOH, products |
| CC write to add | mark wave/line picked, write pick confirmations |
| Endpoint + version | **TBD — confirm the exact CC endpoint before building.** Not yet identified in repo. Treat endpoint discovery as the first task of this surface. |
| Gate / approval | full spine; shadow mode shows the confirmation set for human approve |
| Risk note | mutates order/fulfilment state — higher blast radius than dims. Sandbox round-trip mandatory before any live order. |

### 3.3 Putaway-location writes (confirm receipts, assign locations) — THIRD

| | |
|---|---|
| State today | **planned** — no surface yet; inbound-order reads exist |
| CC reads in hand | inbound orders, products; locations via XLS loader |
| CC write to add | confirm receipts, assign putaway locations |
| Endpoint + version | **TBD.** Note GROUND_TRUTH / brief §6.7: `/warehouse-locations/search` **404s on this tenant** — location data comes from CC's XLS export + SOH aggregation, not a live locations API. Confirm whether a *write* path for location assignment even exists on this tenant's API before committing to this surface. |
| Gate / approval | full spine; shadow mode |
| Risk note | the 404 means this surface may be **blocked by the API itself**, not just unbuilt. Validate API capability first. |

### 3.4 Dispatch (assign orders→runs, set status) — LAST, gated behind SAP B1

| | |
|---|---|
| State today | console **built, read-only**; `CartonCloudSink` refuses + `NotImplementedError` |
| CC reads in hand | consignments, orders |
| CC write to add | assign orders→runs, set run/consignment status |
| Endpoint + version | **TBD** |
| Gate / approval | full spine **plus** the existing `dispatch_write_approved` flag **plus** the SAP B1 boundary must be cleared first (brief §7.5) |
| Risk note | highest blast radius; SAP B1 owns dispatch writes today. Do not enable until the SAP B1 boundary question is resolved with the boss. |

---

## 4. Shadow mode → sandbox → live: the rollout gate (every surface)

The brief says "shadow mode before live." Here is the concrete definition of done
that turns that from a slogan into a checklist. **No surface is "trusted" until
all four pass, in order.**

1. **Shadow (no CC write).** Surface computes the proposed change, reads current
   CC state, shows the diff, requires a human to approve. The mutate method is
   never called. Unit-tested with CC mocked (the dim-capture-app model).
2. **Sandbox round-trip (one real CC write).** With the allow-list containing
   **only** the sandbox id, perform ONE real mutate against ONE sandbox SKU
   (e.g. an `s`-prefixed product). Read it back. Confirm the value landed and
   matches. This is the CC-round-trip proof the 134 mocked tests can't give.
3. **Sandbox soak.** Run the surface against the 46 active sandbox SKUs in normal
   operation for an agreed period. Confirm idempotency (re-running doesn't
   double-apply), rate-limit behaviour, error handling against a real endpoint.
4. **Live promotion (separately approved).** Only after 1–3, and only by an
   explicit config change that adds the live Forage id to the allow-list, signed
   off by the boss. The change to the allow-list is its own commit, its own
   review, its own approval. Never bundled with feature work.

**The allow-list is the live/sandbox switch.** Promotion to live == one reviewed
line adding `d4810e1e-...`. Demotion == removing it. This makes "are we pointed
at live?" a single greppable, auditable fact.

---

## 5. What must be true before ANY mutate verb is written (pre-code gate)

Mirror dim-capture-app modules 02/04/12/13. Do not write a single mutating CC
call until all of these exist and are tested **with CC mocked**:

- [ ] `_mutate()` exists, double-gated, default-closed (§2.1).
- [ ] Write-auth secret check, fail-closed when unset (§2.2), with a test
      asserting the refuse-on-unset path (dim-capture-app asserts 503 four ways —
      match that rigour).
- [ ] Customer-id allow-list guard (§2.3), with a test asserting a live-Forage-id
      target is **refused** even with all other gates open.
- [ ] Idempotency / serialisation + read-before-write diff (§2.4).
- [ ] Rate limiter (≤ lower of 30/min CC ceiling and 60/min bucket), reject not
      queue.
- [ ] 12s timeout → typed error, no raw timeout escapes.
- [ ] Shadow-mode display path for the target surface.

Only then is the sandbox round-trip (§4 step 2) permitted.

---

## 6. Open decisions (recorded, not yet made)

1. **Dims write: integrate dim-capture-app (route a) or port into Python (route
   b)?** §3.1. Trade-off: proven-code-reuse + second stack vs one-stack +
   re-implementation. Jake to decide.
2. **Build order after dims:** brief offers pick-confirmation (value) vs putaway
   (low risk) first. Putaway may be API-blocked (§3.3 404). Provisional order
   here is dims → picks → putaway → dispatch; confirm.
3. **Product ambition / Go Cold quarantine.** If this becomes a marketable
   multi-3PL WMS wrapper, the hardcoded Forage id, `.gocold.local`, SAP B1
   boundary, and XLS-locations workaround must move behind a tenant/config
   boundary. Decide now whether to build the config seam from the start (cheap
   now, painful later) or ship Go Cold-shaped and refactor.
4. **Pick / putaway / dispatch write endpoints are all TBD** — none identified in
   the current tree. Endpoint discovery is the first task of each surface.

---

## Footer

- Companion to GROUND_TRUTH.md @ `7f4be88` on `feature/dims-cc-sync`.
- dim-capture-app reference: `main` @ `8e3b065`, suite re-run 2026-06-19 → 134
  pass, CC mocked throughout.
- Sandbox customer: `a8dab3f2-defa-433e-87a0-01dee48a2286` (same tenant as live).
- No code, no flag, no mutating verb in this commit.
- Date: 2026-06-20. Author: claude.ai, from verified repo + sandbox facts.
