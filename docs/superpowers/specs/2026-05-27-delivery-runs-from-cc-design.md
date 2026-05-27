# Delivery runs from CartonCloud — design

**Date:** 2026-05-27
**Status:** Approved (brainstorm)
**Project:** gocold-wms-flow
**Owner:** Jake Philipsen

## Problem

Go Cold's dispatch team needs to build delivery runs each day from open
CartonCloud sale orders. Today's extract pulls SO/PO data into Parquet
but discards most of the delivery address payload — only suburb, state,
postcode, and company name survive. There's no driver-ready output that
groups stops into runnable buckets.

This design adds:

1. Full delivery-address capture in the existing extract.
2. A zone-based grouping module that buckets stops into named runs.
3. Driver-ready XLSX output (one file per run) plus a master CSV for
   external routing tools.

CartonCloud stays read-only end to end.

## Non-goals

- No writes to CartonCloud. `write_enabled=False` everywhere.
- No actual route optimisation (sequencing inside a run is left blank
  for the dispatcher or an external tool like OptimoRoute/Onfleet).
- No truck-capacity assignment. Runs are grouped by zone × required
  date only; cartage decisions stay manual.
- No new persistent state. File outputs only, no DB.
- No new dependencies — uses what's already in `requirements.txt`
  (httpx, pandas, pyarrow, matplotlib, openpyxl).

## Architecture

```
CC API (read-only)
   │
   ▼
search_outbound_orders(status=["AWAITING_PICK_AND_PACK","PACKED"])
   │
   ▼
extract.py  ── flattens FULL deliver.address payload now ──┐
   │                                                       │
   ▼                                                       │
data/raw/so_lines_open_<ts>.parquet                        │
   │                                                       │
   ▼                                                       │
src/analysis/delivery_runs.py  (NEW)                       │
   ├── load addresses, dedupe to one row per SO            │
   ├── assign zone via config/delivery_zones.yaml          │
   ├── group SOs → run buckets (zone × required_date)      │
   └── return DeliveryRunPlan dataclass                    │
   │                                                       │
   ▼                                                       │
scripts/build_runs.py (NEW)  ── orchestrator               │
   │
   ▼
data/processed/runs/<ts>/
   ├── runs_master.csv         (every stop, all zones)
   ├── runs_<zone>_<date>.xlsx (one file per run)
   ├── summary.md              (counts, zone mix, flags)
   └── unzoned.csv             (postcodes not in config)
```

The new module fits the existing pattern: `compute_*` / dataclass
result / `from __future__ import annotations` / typed / structured
logging / no prints in library code.

## Components

### 1. Extended address capture in `scripts/extract.py`

The current `_flatten_outbound_order_lines` picks four fields from
`details.deliver.address`. Replace that with a fuller capture:

| Output column | CC source path | Status |
| --- | --- | --- |
| `delivery_company` | `details.deliver.address.companyName` | existing |
| `delivery_contact` | `details.deliver.address.contactName` ↦ fallback `details.deliver.contact` | new |
| `delivery_phone` | `details.deliver.address.phone` ↦ fallback `details.deliver.phone` | new |
| `delivery_email` | `details.deliver.address.email` | new |
| `delivery_street1` | `details.deliver.address.line1` | new |
| `delivery_street2` | `details.deliver.address.line2` | new |
| `delivery_suburb` | `details.deliver.address.suburb` | existing |
| `delivery_state` | `details.deliver.address.state.code` (str or dict) | existing |
| `delivery_postcode` | `details.deliver.address.postcode` | existing |
| `delivery_country` | `details.deliver.address.country.code` | new |
| `delivery_instructions` | `details.deliver.instructions` ↦ fallback `details.notes` | new |
| `delivery_required_date` | `details.deliver.requiredDate` | existing |
| `delivery_time_window` | `details.deliver.timeWindow` (best-effort, string) | new |

CC field names are inferred from the existing code and standard CC
schema. Before committing the flatten changes:

1. Extend `scripts/smoke_test.py` (or add a small `scripts/probe_so.py`)
   to dump one full SO JSON to `data/probes/so_<id>.json` so the actual
   shape is verified.
2. If any inferred path is wrong, update the table above and the
   flatten code together.

Behaviour on missing values: `None` (pandas → empty cell). Driver-ready
output will flag SOs with a missing street as red.

### 2. Status filter on outbound search

`src/cc_client/queries.py::search_outbound_orders` already accepts a
`status` list. Add a thin convenience wrapper or just pass the explicit
list from the new orchestrator:

```python
status=["AWAITING_PICK_AND_PACK", "PACKED"]
```

This is "everything in-flight that hasn't left the building." The
existing `so_lines_open_*.parquet` naming convention confirms this
shape is already in use.

### 3. Zone config (`config/delivery_zones.yaml`)

Operator-editable YAML; first match wins. Postcode strings (exact) or
ranges (`"3000-3207"`) supported.

```yaml
zones:
  - name: "Metro Melbourne"
    state: VIC
    postcodes: ["3000-3207"]
  - name: "Geelong"
    state: VIC
    postcodes: ["3211-3242"]
  - name: "Regional VIC"
    state: VIC
    postcodes: ["3210", "3243-3999"]
  - name: "Interstate NSW"
    state: NSW
  - name: "Interstate QLD"
    state: QLD
  - name: "Interstate SA"
    state: SA
  - name: "Interstate TAS"
    state: TAS
  - name: "Interstate WA"
    state: WA
  - name: "Interstate ACT"
    state: ACT
  - name: "Interstate NT"
    state: NT
fallback: "Unzoned"
```

Matching rules:

- If `postcodes` present, the SO's postcode must match one entry
  (exact or within range) AND the SO's state must match if `state`
  is set on the zone.
- If `postcodes` absent, the SO's state matching `state` is sufficient.
- First match wins (order in YAML matters).
- No match → assigned to `fallback` zone name and also written to
  `unzoned.csv` for operator review.

### 4. `src/analysis/delivery_runs.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

@dataclass(frozen=True)
class ZoneRule:
    name: str
    state: str | None
    postcode_ranges: list[tuple[int, int]]   # inclusive, may be (n, n)

@dataclass(frozen=True)
class ZoneConfig:
    zones: list[ZoneRule]
    fallback: str

@dataclass(frozen=True)
class DeliveryRun:
    zone: str
    required_date: date | None
    stops: pd.DataFrame      # one row per SO
    total_stops: int
    total_cartons_est: float

@dataclass(frozen=True)
class DeliveryRunPlan:
    runs: list[DeliveryRun]
    master: pd.DataFrame     # all stops flattened
    unzoned: pd.DataFrame
    missing_address: pd.DataFrame

def load_zone_config(path: Path) -> ZoneConfig: ...
def compute_delivery_runs(
    snap_open: pd.DataFrame,        # so_lines_open_*.parquet
    routing_streams: pd.DataFrame,  # from routing.py
    zones: ZoneConfig,
) -> DeliveryRunPlan: ...
def write_run_plan(
    plan: DeliveryRunPlan, out_dir: Path,
) -> None: ...
```

Library code: no prints, structured logging via
`logging.getLogger(__name__)`, type hints everywhere, Australian
English in comments/strings.

`compute_delivery_runs` deduplicates `snap_open` (one row per SO, not
per line), joins routing-stream classification by SO id, assigns
zones, then groups by `(zone, required_date)` to produce runs.

Carton estimate per SO: reuse the cartons-per-line logic from
`routing.py` / `wave_picks.py`. If no dim data, leave blank — flagged
in summary.

### 5. `scripts/build_runs.py`

```bash
python3 scripts/build_runs.py                       # all open SOs
python3 scripts/build_runs.py --required-date 2026-05-28
python3 scripts/build_runs.py --zones-config config/delivery_zones.yaml
python3 scripts/build_runs.py --dry-run             # extract only, no XLSX
python3 scripts/build_runs.py --skip-extract        # use latest snapshot
```

Default behaviour:

1. Run an `extract.py` open-orders pull (unless `--skip-extract`).
2. Load the latest `so_lines_open_*.parquet` and `routing_streams.csv`
   (if absent, run routing first or warn).
3. Load `config/delivery_zones.yaml` (default path).
4. Compute the plan.
5. Write outputs to `data/processed/runs/<ts>/`.

### 6. Output structure

`data/processed/runs/<YYYYMMDD_HHMMSS>/`:

- `runs_master.csv` — every stop, flat. Columns:
  `zone, run_id, sequence (blank), so_ref, so_id, customer_name,
  delivery_company, delivery_contact, delivery_phone, delivery_email,
  delivery_street1, delivery_street2, delivery_suburb, delivery_state,
  delivery_postcode, delivery_country, delivery_instructions,
  delivery_required_date, delivery_time_window, stream, cartons_est,
  pallet_fraction, urgent, address_complete (bool)`.
- `runs_<zone>_<YYYY-MM-DD>.xlsx` — one workbook per run; one sheet
  named `run`:
  - **Header block (rows 1–6):** zone, required_date, total stops,
    total cartons (est), total SOs, generated_at.
  - **Stops table (row 8+):** as above but human-friendly column
    headers; sorted by postcode then suburb; urgent rows
    highlighted; rows with `address_complete=False` highlighted red.
- `summary.md` — readable rundown:
  - Total open SOs, by stream mix.
  - Stops per zone, with required-date spread.
  - Unzoned count (red flag if > 0).
  - Missing-address count (red flag — driver can't deliver without
    a street).
- `unzoned.csv` — SOs that didn't match any zone rule. Same columns
  as `runs_master.csv`.

### 7. Safety / hard rules (carried forward)

From `CLAUDE_CODE_GOAL_routing.md`:

- `CartonCloudClient.from_env()` only. Never pass `write_enabled=True`.
- All output goes to local files under `data/processed/runs/` or
  `data/probes/`. Never mutate CC state.
- No secrets in code or docs — reference env var names only.
- Match existing conventions: dataclass results, `compute_*` naming,
  `from __future__ import annotations`, type hints, structured logging,
  no prints in library code (scripts may print), Australian English in
  comments and strings ("colour", "centre", "behaviour"), no emojis.
- No new dependencies.
- No stub/placeholder code.

## Testing

- Unit test `load_zone_config` against a fixture YAML (range parsing,
  exact-postcode matching, fallback behaviour).
- Unit test `compute_delivery_runs` against a synthetic
  `snap_open` DataFrame covering: Metro VIC, Geelong, Regional VIC,
  Interstate NSW, an unzoned postcode, an SO with missing street,
  multiple SOs to the same consignee on the same required_date.
- Integration test that `scripts/build_runs.py --dry-run` against the
  latest open-orders snapshot produces a non-empty
  `DeliveryRunPlan` with expected zone names.
- Probe verification: dump one live SO JSON and confirm every address
  path in the table above resolves correctly. If any path is wrong,
  patch the flatten code AND the table.

## Open questions

1. Does CC actually populate `address.line1` / `address.line2` for
   Forage SOs today, or do those addresses sit in a different field
   (e.g. free-text `details.notes`)? Resolved by the probe step
   before committing the flatten changes.
2. Are time windows surfaced at all in CC for Forage, or always blank?
   If always blank, drop `delivery_time_window` from the schema.
3. Should `address_complete=False` SOs be excluded from runs or
   surfaced with a red flag? Current design: surface with red flag so
   the dispatcher can ring the consignee.

## Rollout

This is shadow-mode work — the dispatcher keeps doing whatever they
do today. Once outputs look right against a real day of orders, the
operator decides when to hand it to the floor.
