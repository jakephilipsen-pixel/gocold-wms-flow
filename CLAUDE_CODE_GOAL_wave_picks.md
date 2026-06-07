# Goal: build a wave pick generator

You are working in `~/rolodex/gocold-wms-flow`. The routing module
(`src/analysis/routing.py` + `scripts/route.py`) classifies SOs into pick
streams. Your job: build a wave pick generator that pulls SOs in "awaiting
pick and pack" status from CartonCloud, runs them through routing, and
produces operator-ready wave pick sheets the warehouse team can use to
manually create waves in CC.

## Hard rules — do not violate

1. **CartonCloud is READ-ONLY.** `CartonCloudClient` defaults to
   `write_enabled=False`. Never change this. Never pass `write_enabled=True`.
   Never call any POST/PUT/PATCH/DELETE on CC (the existing `post_search`
   paths are reads-via-POST and are already whitelisted internally — leave
   them alone). The whole point of this tool is the OPERATOR creates the
   waves in CC manually using the sheets you generate. SAP B1 is plugged
   into CC and writes could collide — this is non-negotiable.
2. **All output goes to local files only** (PDF, CSV, XLSX under
   `data/processed/waves/<timestamp>/`). The tool prints/emails/displays
   what to do; it never mutates CC state.
3. **Do not commit secrets.** Reference env var names only.
4. **Match project conventions.** Read `src/analysis/routing.py`,
   `src/analysis/assignment.py`, `src/cc_client/queries.py`,
   `src/locations/cc_loader.py` before adding anything. Style:
   `from __future__ import annotations`, type hints, dataclass results,
   `compute_*` / `build_*` / `generate_*` naming, structured logging via
   `logging.getLogger(__name__)`, no print statements in library code
   (scripts may print). Australian English in comments. No emojis.
5. **No new dependencies beyond reportlab.** Add `reportlab>=4.0` to
   `requirements.txt` for PDF generation. Everything else: httpx, pandas,
   pyarrow, openpyxl already in.
6. **No stub/placeholder code.** Every function fully implemented.

## What "awaiting pick and pack" means in CC

This is a CC outbound-order status. You'll need to:
1. Confirm the exact status string by inspecting `src/cc_client/queries.py`
   `search_outbound_orders` and a recent extract's data. Look at the
   `status` field on outbound orders. The display label "Awaiting Pick &
   Pack" likely maps to a code like `AWAITING_PICK_AND_PACK` or similar —
   verify against real data before hardcoding.
2. Extend `search_outbound_orders` (or build a new helper alongside it)
   to filter by status. Keep the existing signature intact — add an
   optional `status` parameter. Match the existing condition-building
   pattern (look at how `customer_name` and date filters are constructed).
3. If the exact status code isn't obvious from data, ask the operator.
   Don't guess.

## Tasks — execute in order, report progress after each

### Task 1 — extend CC client to filter by status

1. Read `src/cc_client/queries.py` `search_outbound_orders`.
2. Inspect a recent extract (parquet in `data/raw/`) — what statuses appear
   on `so_lines`? What's the column name? (Probably `status` or
   `order_status`.)
3. If the status column isn't in the extract, check
   `scripts/extract_forage.py` and `scripts/extract.py` — the raw CC
   response may have the field but the extract is dropping it. If so,
   add the field to the extract.
4. Add a `status` parameter (optional, list of strings) to
   `search_outbound_orders`. Pattern: build a `TextComparisonCondition`
   per status with `EQUAL_TO`, wrap in an `OrCondition` if multiple,
   AND it with the existing date/customer filters.
5. Smoke-test: pull "awaiting pick and pack" SOs only, count them, log.

### Task 2 — build the wave generator module

Create `src/analysis/wave_picks.py` with:

```python
@dataclass
class WavePickSheet:
    wave_id: str            # e.g. "2026-05-17_VIC_S2_W01"
    stream: str             # 1_pallet_pick / 2_wave_bypass / 3_wave_bench
    run_group: str          # delivery_state for now (delivery_run later)
    receive_date: date
    orders: pd.DataFrame    # so_id, so_ref, customer, dest, cartons, lines
    pick_lines: pd.DataFrame  # one row per pick: location, product, qty, so_ref
    total_cartons: int
    total_lines: int
    estimated_walk_distance_m: float  # optional, if we have aisle geometry

@dataclass
class WaveGenerationResult:
    sheets: list[WavePickSheet]
    skipped_orders: pd.DataFrame  # SOs that couldn't be waved (no location, etc)
    summary: dict
```

Core function:

```python
def generate_wave_pick_sheets(
    classification: StreamClassification,    # from routing module
    locations: pd.DataFrame,                  # from load_cc_locations
    assignments: pd.DataFrame | None = None,  # from assign_skus_to_locations
    aisle_walk_order: list[str] | None = None,
    run_group_col: str = "delivery_state",
) -> WaveGenerationResult:
```

What it does:
1. Filter `classification.per_order` to streams 2 and 3 only. Stream 1
   is pick-to-pallet and gets a separate per-order pick sheet (handle
   that too if scope allows, but flag and ask before going beyond
   streams 2/3 if it adds significant scope).
2. Group by `(receive_date, run_group, stream)` — same grouping as
   `plan_waves` in the routing module. Reuse `plan_waves` directly to
   get the wave assignments; don't reimplement.
3. For each wave, build a pick line list: join the wave's SO lines back
   onto the location data. Each pick line = (location, product_code,
   product_name, qty_to_pick, contributing_so_refs).
4. **Consolidate same-SKU picks across orders within a wave.** A wave with
   three orders all needing SKU X gets ONE pick line for SKU X with the
   summed qty and a list of so_refs. This is the whole point of waving.
5. **Sort pick lines by aisle walk order.** Default walk order: alphabetical
   aisle code (AA, AB, AC, ...) then bay ascending. Use the `aisle`, `bay`,
   `level`, `sublevel` columns from `locations`. If `aisle_walk_order` is
   passed, use that ordering (override for non-alphabetic warehouses).
6. Compute total cartons + total lines per wave.

### Task 3 — pick location resolution

For each (so_id, product_code) pick line, we need the location.

Priority:
1. If `assignments` is provided (from `assign_skus_to_locations`), use the
   assigned pick face location. This is the cleanest answer.
2. If no assignment for that SKU, fall back to CC's current SKU →
   location mapping. Pull this fresh via a new helper in
   `src/cc_client/queries.py` — `get_sku_locations(client, product_codes)`
   — that queries CC's stock-on-hand or product-location endpoint.
3. If still no location, add the order to `skipped_orders` with reason
   "no location for SKU X". Don't crash, don't guess.

### Task 4 — PDF pick sheet generation

Create `src/output/pdf_picksheet.py` (new package `src/output/` if it
doesn't exist; add `src/output/__init__.py`). Use reportlab.

Apply the **Go Cold PDF theme** (this is locked in operator memory):
- Logo path: configurable via `--logo` arg, default
  `~/rolodex/gocold-wms-flow/assets/gocold_logo.png` (operator will place
  it). If missing, skip the logo gracefully but log a warning.
- Colours: `GC_GREEN=#00C452`, `GC_BLUE=#0096CC`, `GC_DARK=#003366`,
  `GC_MID=#0076A8`
- Cover layout: logo top → green|blue split bar → navy title block →
  blue subtitle strip → green doc ID strip → metadata table → bottom
  split bar.
- Headers: navy background + green underline.
- Tables: navy header row.

PDF layout per wave (one PDF per wave_id):

**Page 1 — Cover**
- Wave ID (large, in title block)
- Stream (1/2/3) + bench routing indicator
- Run group (state)
- Receive date
- Total cartons + total pick lines + total orders
- Estimated time to pick (assume 60 lines/hour as a rule of thumb)
- "Print this sheet, walk the warehouse, return to bench" note
  (only Stream 3 needs the bench reminder)

**Page 2+ — Pick lines table**
Columns: Walk #, Location, SKU code, SKU name, Qty (cartons),
Cartons remaining (running total), Contributing SOs, Pick confirmed (☐)
- Pre-numbered walk order down the left
- Big tick boxes
- Location code in monospace, bigger font
- Page footer with wave_id + page X of Y + generated timestamp

**Final page — Order summary**
Columns: SO ref, Customer, Destination (suburb, state), Cartons, Lines
Sorted by SO ref. This is what the operator pastes into CC.

```python
def generate_wave_pdf(sheet: WavePickSheet, out_path: Path,
                     logo_path: Path | None = None) -> None:
```

### Task 5 — CSV companion file

Create `src/output/csv_picksheet.py`. For each wave produce two CSVs:

1. `<wave_id>_picks.csv` — pick lines (location, sku, qty, so_refs)
2. `<wave_id>_orders.csv` — SO list (so_ref, customer, dest)

The orders CSV is what the operator pastes into CC's wave creation.

### Task 6 — orchestrator script

Create `scripts/generate_waves.py`. Pattern: mirror `scripts/route.py`.

Pipeline:
1. Pull SOs with status "awaiting pick and pack" from CC live (don't use
   stale parquet — these are open orders, recency matters).
2. Save the pulled SOs to `data/raw/so_lines_open_<timestamp>.parquet`
   so we have an audit trail.
3. Build a `Snapshot` from the live pull + existing PO/products parquets.
4. Run the routing pipeline (velocity → tags → full_pallet → order_metrics
   → classify_streams) reusing existing functions.
5. Load locations and assignments (latest from `data/locations/` and
   `data/processed/assign_*/assignments.csv`).
6. Call `generate_wave_pick_sheets`.
7. Write each wave to `data/processed/waves/<timestamp>/<wave_id>/` containing:
   - `<wave_id>_picksheet.pdf`
   - `<wave_id>_picks.csv`
   - `<wave_id>_orders.csv`
8. Write top-level `data/processed/waves/<timestamp>/index.md` listing
   all waves with quick stats and links.

CLI:
```bash
python3 scripts/generate_waves.py
# tune
python3 scripts/generate_waves.py --pallet-fraction-threshold 0.65 \
                                   --early-release-cartons 25 \
                                   --logo path/to/logo.png
```

### Task 7 — smoke test against real data

1. Run the full pipeline against current CC data.
2. Open one of the generated PDFs. Check:
   - Theme applied correctly
   - Pick lines in walk order (AA-01-01 before AB-05-02 etc)
   - SOs consolidated (one pick line per SKU per wave, not per order)
   - Cartons total matches sum of pick line cartons
   - SO summary page lists all SOs in the wave
3. Open one of the CSVs. Check:
   - Picks CSV: location + SKU + total qty + SO list per line
   - Orders CSV: just the SO refs, ready to paste
4. Report: how many waves generated, how many orders covered, how many
   skipped (and why).

## Reporting cadence

After each task, write a short status update to the chat:
- What you did
- Any deviations from the plan and why
- What you found (key numbers)
- Whether to proceed or wait for operator input

If you hit ambiguity, **stop and ask** rather than guessing. Specifically:
- If the "awaiting pick and pack" status code isn't obvious from data — ask.
- If pick locations are missing for >5% of SKUs — ask.
- If reportlab PDF generation throws on Go Cold theme rendering — show
  the error and ask.
- If a wave ends up >100 pick lines (too big to pick in one go) — flag it.

## Out of scope — do not do these

- Don't push anything to CartonCloud. The whole point of this is the
  operator creates the wave in CC manually using your output.
- Don't add new analyses beyond what's specified.
- Don't tune routing parameters — that was the previous goal's job.
- Don't touch SAP integration in any way.
- Don't add a Stream 1 (pick-to-pallet) workflow yet unless you've
  finished streams 2/3 and the operator confirms. Stream 1 needs different
  paperwork (pallet labels, wrap instructions) — separate scope.
- Don't push to git. Leave changes uncommitted for operator review.
