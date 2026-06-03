# gocold-wms-flow

Workflow tooling for Go Cold's CartonCloud WMS — slotting analysis,
extract pipelines, and (eventually) the pick bench service.

This repo currently contains the data-pipeline foundation: a CartonCloud
API client and an extract script that pulls Sale Orders, Purchase Orders,
and Warehouse Products into local Parquet for offline analysis.

## Project status

- [x] CartonCloud API client (read-only by default)
- [x] Smoke test for credential / tenant validation
- [x] Extract script: SOs / POs / Products → Parquet
- [x] Velocity / pattern / zoning / destination analysis
- [x] Carton-dim capture template (Go Cold themed)
- [ ] Slotting recommendations (blocked on dim capture)
- [ ] Replenishment rules generator (blocked on dim capture)
- [ ] Bench scan/pack service
- [ ] Run-sequencing dispatcher

## Setup

```bash
# 1. Install deps (use a venv if you like)
python -m pip install -r requirements.txt

# 2. Get CartonCloud API credentials
#    In CC: Admin → API Clients → Create new
#    Required roles: WMS Create Job, WMS Add/Edit Product

# 3. Configure your .env
cp .env.example .env
# edit .env with CC_CLIENT_ID, CC_CLIENT_SECRET, CC_TENANT_ID

# 4. Verify connection
python scripts/smoke_test.py
```

The smoke test confirms auth, tenant access, and basic read perms before
you do any real extracts. If anything's wrong it tells you what.

## Pulling data

```bash
# Daily pull for The Forage Company (preset wrapper)
python scripts/extract_forage.py

# Larger backfill on first run
python scripts/extract_forage.py --so-days 90 --po-days 180

# Or use the generic extract directly for ad-hoc work
python scripts/extract.py --customer-name "Other Customer" --so-days 7
python scripts/extract.py --so-days 7 --po-days 7 --dry-run
```

## Running the analysis

```bash
# Run analysis on the latest extract in data/raw/
python scripts/analyze.py

# Tweak zoning parameters
python scripts/analyze.py --top-skus 80 --lift 0.35 --zone-size 6
```

Output goes to `data/processed/<timestamp>/` with:
- `summary.md` — start here, human-readable interpretation
- `capture_template.xlsx` — Go Cold themed carton-dim entry sheet for the
  warehouse team, sorted by measurement priority
- `sku_metrics.csv` — per-SKU velocity / frequency / inbound metrics
- `zone_assignment.csv` + `zone_suggestions.md` — co-occurrence-based
  groupings for the top SKUs
- `destinations_*.csv` — geographic distribution for run sequencing
- `plots/` — pareto curve, ABC breakdown, order density, lift heatmap

Output lands in `data/raw/*.parquet` along with a `manifest_*.json`
documenting the extract window. These files are gitignored.

## Wave Pick Console (web UI)

A local web console wrapping `scripts/generate_waves.py`. Trigger a live
wave generation run, watch progress stream, and browse/download the
resulting waves.

```bash
python scripts/serve_web.py     # then open http://127.0.0.1:8000
```

Read-only against CartonCloud — it generates paperwork only. Settings
exposed: status, customer, pallet-fraction-threshold, early-release-cartons,
run-group. One run at a time. The CLI (`scripts/generate_waves.py`) still
works unchanged and shares the same pipeline core (`src/wave_runner.py`).

## Safety

- **Read-only by default.** The client refuses POST/PUT/PATCH/DELETE
  unless `CC_WRITE_ENABLED=true`. Search endpoints use POST but are
  treated as reads internally.
- **Credentials never logged.** `.env` is gitignored, secrets are loaded
  via env vars only.
- **No write operations have been built yet.** Adding any (e.g.
  pushing slotting rules into CC) will require explicit code paths and
  the write flag flipped on.

## Project layout

```
src/cc_client/
  client.py           # OAuth2, retries, pagination, request core
  queries.py          # High-level helpers per endpoint
scripts/
  smoke_test.py       # Run first to verify creds + access
  extract.py          # Generic SO/PO/Product → Parquet
  extract_forage.py   # Preset wrapper for The Forage Company
data/
  raw/                # Extract output (gitignored)
notebooks/            # Analysis notebooks
tests/                # Unit tests (TODO)
```

## CC API quirks worth knowing

- **Search endpoints are POST**, not GET — the search body can be huge so
  CC chose POST. Our client treats them as reads internally.
- **Date fields use two patterns**: `arrivalDate` is a ValueField with
  YYYY-MM-DD, but `/timestamps/packed/time` is a JsonField pointer with
  full ISO 8601 timestamps. Both are wrapped by `queries.py`.
- **Pagination** is via `?page=&size=` with `Total-Pages` in response
  headers. Client handles this.
- **Stock on Hand is async**: POST a report run, poll until SUCCESS.
  Allow ~10–30 seconds for typical runs.
- **Rate limit** of 30 req/min on outbound order create (not relevant
  for reads, but worth knowing if we ever push orders back).
- **API version 8** for warehouse products is the latest. We use v1
  for everything else.
