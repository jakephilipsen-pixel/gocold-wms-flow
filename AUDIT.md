# AUDIT — gocold-wms-flow

**Audited:** 2026-06-03 · **Git SHA:** `e95a6c5` · **Source of truth:** `CLAUDE.md`
**Scope note:** The first `/audit-project` sweep targeted `/home/pop_os/archive/gocold` — a **stale,
parallel legacy folder** (old barcode-assignment + pdf→CC email tooling). The operator redirected to
the **real project** here (`archive/rolodex/gocold-wms-flow`) via `dims.ods`. This report is scoped
to the real project; legacy findings are retained as the **L-appendix**.

---

## Verdict

The **wave pick generator is genuinely built, complete, and has produced real operator-ready output**,
and it correctly honours the project's hard non-negotiable: **CartonCloud is read-only**. The
historical "primary blocker" — *0/460 SKUs have carton dimensions* — is **effectively resolved**:
**~409 SKUs now have full outer dimensions captured locally** (L/W/H 100%, inner-pack-qty 99.5%,
weight 69%). The one genuine remaining build is **getting those dims into CartonCloud**, which the
`dim-capture-app` sub-project is meant to do — and that is only **~1/8 built** (scaffold only).

The single most important *risk* is not technical debt — it's that **the entire working wave
generator is uncommitted to git**. A reset would erase production-ready work.

---

## What actually works (verified)

| Capability | Verified how |
|---|---|
| **Wave pick generator** — `src/analysis/wave_picks.py`, `scripts/generate_waves.py`, `src/output/pdf_picksheet.py`, `csv_picksheet.py` | Read in full — no stubs/TODO/NotImplemented. Produced **4 real waves** on 2026-05-17 (`data/processed/waves/20260517_103152/`): 60 pick lines / 143 cartons / 6 orders / 0 skipped. Each wave = themed PDF + `*_picks.csv` (one row per SKU, qty summed across orders, sorted by aisle walk order) + paste-ready `*_orders.csv`. |
| **Read-only enforcement** (the non-negotiable) | `cc_client/client.py:139` gates every non-GET behind `write_enabled` (default `False`). Only POST path is `post_search` (read-via-POST). Zero `.put/.patch/.delete`. `generate_waves.py` never enables writes. SAP-B1 collision risk respected. |
| **Status filter** | `AWAITING_PICK_AND_PACK`, verified live 2026-05-17 (`wave_picks.py:48`, `queries.py:89`). Optional `--status` override. |
| **CC API client** | Real OAuth2, paginated POST-search, retry/backoff, customer-scoped to The Forage Company. |
| **Carton dims** | `data/dims/dims_2026-05-13.xlsx`: ~409/409 full L/W/H (jumped 27%→100% on 12 May). Loaded locally by `dim_loader.py` for slotting — **no CC write**. |

---

## Findings

### R1 — GAP (build): Dims→CartonCloud sync does not exist
~409 SKUs have dims **locally** but **0 in CartonCloud**. CC-native wave/cartonisation needs them in
CC. The path is `dim-capture-app` module **02 (cc-client, PATCH /products)** + **04 (dim-api/sync)** —
both `🔲 not started`; routes return `501` (`dim-capture-app/backend/src/routes/sync.ts:5`,
`dims.ts:5`). **This is the real path-to-production gap.** → build `dim-capture-app` 01→02→04.

### R2 — DRIFT: CLAUDE.md dims line is stale
`CLAUDE.md:76` still says *"0 / 460 SKUs have carton dimensions in CC — primary blocker"* (10 May).
Dims were captured 12 May. Update to: *"~409 SKUs have outer dims captured **locally** (L/W/H 100%,
inner-pack-qty 99.5%, weight 69%); **0 synced to CC** — sync awaits dim-capture-app 02+04."*

### R3 — DRIFT: dim-capture-app module-01 icon overstates reality
`dim-capture-app/MODULES.md` marks `01 backend-core` **🟨 in-progress**, but
`modules/backend-core/STATE.md` says *"Not started"* and the code is **scaffold-only** — every route
returns `501`, no Prisma migration, no `.env`, vitest present but no implementations. Reconcile the
icon (→ 🔲, or 🟨 with an honest "scaffold only" note).

### R4 — GATE: the working wave generator is uncommitted
Repo has **2 commits**; **27 untracked paths**. `wave_picks.py`, `generate_waves.py`, `src/output/`,
`src/locations/`, most of `src/analysis/`, and all of `data/` are untracked. **First action should be
to commit/checkpoint** before any further change risks losing it.

### R5 — GAP: no tests; the read-only guard is unguarded by regression
`tests/` is empty. The `write_enabled` gate and the wave-consolidation logic are validated only by
real-data runs. The read-only guard is the project's **non-negotiable** — it most deserves a test
(a "non-GET without write_enabled must raise" unit test + a wave-consolidation assertion).

### R6 — GAP: dim weight capture incomplete
Outer weight 281/409 (69%); inner-pack-qty 407/409 (99.5%, 2 blank); L/W/H 100%. Minor — finish
weight capture for weight-based cartonisation/dispatch logic.

---

## Gate readiness
- **gocold-wms-flow (wave pipeline):** scripts + notebooks repo, **no module registry at root** →
  `/compile-stress` and `/deploy-local` do not apply. Validation is real-data runs (which pass).
- **dim-capture-app:** framework-managed. `.deploy-state` `local_validated:false`, ~1/8 modules
  scaffolded → **`/deploy-local` not started / blocked.**

---

## Non-code decisions for Jake
1. Confirm `AWAITING_PICK_AND_PACK` is the **only** pick-eligible status (no draft/hold variants to include).
2. Are the legacy `archive/gocold` barcode sheets the ones **loaded into CC**? That decides whether
   the L1 duplicate-barcodes are a live mis-pick risk at the bench.
3. Is `dim-capture-app` still the intended dims→CC mechanism — or sync dims another way (a one-off
   scripted `PATCH` behind the `write_enabled` flag, with human approval)?

---

## Proposed queue (ordered)
1. **Commit the wave generator** (R4) — checkpoint working, uncommitted code first.
2. **Kill the drift** — update CLAUDE.md dims line (R2) + reconcile dim-capture-app icons (R3).
3. **Build dims→CC sync** — `dim-capture-app` 01→02→04 (R1).
4. **Add read-only-guard + wave-consolidation tests** (R5) — lock the non-negotiable.
5. **Finish weight capture** (R6); then optionally settle the legacy folder (L1–L3).

---

## Appendix — legacy `archive/gocold` (separate, lower priority)
An older, parallel effort: pdf→CC inbound API + sales email-CSV + a barcode (EAN13/outer) assignment
exercise. Flagged only if still in use:

- **L1 (data):** In `FINAL EACH BARCODE.ods`, **5 each-barcodes each map to 2 distinct SKUs**
  (`15060489730043/0203/0654/0739` = Dash single-can vs doublepack; `19358794000095` = Barbell
  sea-salt variants) + **34 blank** of 422 — *verified by direct ODS parse*. Real scan mis-pick risk
  **iff** these were loaded into CC's product master. **The wave generator picks by SKU/location, not
  barcode, so it is not blocked by this.**
- **L2 (hygiene):** plaintext Gmail app-password in `pdf_to_cartoncloud_sales/.env:5` — local/untracked
  (not published). Rotate + `.gitignore` if still used.
- **L3 (decision):** inbound-API path is real but **dormant** (no `.env`, stale PO since 14 Jan);
  sales email-CSV path is the one that actually ran (9 Mar). Pick a go-forward path if either is live.

---

*Read-only audit. Only `AUDIT.md` + `audit.json` were written. No code, data, git, or deploy state
changed; nothing marked done/✅.*
