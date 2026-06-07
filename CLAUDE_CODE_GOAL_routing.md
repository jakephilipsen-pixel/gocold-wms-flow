# Goal: validate, tune, and harden the order routing module

You are working in `~/rolodex/gocold-wms-flow`. A new module
`src/analysis/routing.py` and orchestrator `scripts/route.py` have just been
added (see `INSTALL.md` for the drop-in). They classify SOs into three pick
streams and plan wave releases. Your job is to validate them against real CC
data, tune the parameters, and harden anything that breaks.

## Hard rules — do not violate

1. **CartonCloud is READ-ONLY.** `CartonCloudClient` defaults to
   `write_enabled=False`. Never change this. Never pass `write_enabled=True`.
   Never call any POST/PUT/PATCH/DELETE on CC (the `post_search` paths are
   reads-via-POST and are already whitelisted internally — leave them alone).
   If you find yourself wanting to write to CC, stop and ask the operator.
2. **All output goes to local files only** (CSV/XLSX/parquet/MD under
   `data/processed/` or `data/routing/`). Never mutate CC state.
3. **Do not commit secrets.** The `.env` file holds live CC creds. If you need
   to reference env vars in code, reference the names only.
4. **Match the project's existing conventions.** Read
   `src/analysis/full_pallet.py`, `assignment.py`, `loaders.py` before adding
   anything new. Style: dataclass results, `compute_*` / `run_*_analysis`
   naming, `from __future__ import annotations`, type hints everywhere,
   structured logging via `logging.getLogger(__name__)`, no print statements
   in library code (scripts may print). Australian English in comments and
   strings ("colour", "centre", "behaviour"). No emojis.
5. **No new dependencies.** Stick to what's in `requirements.txt`: httpx,
   pandas, pyarrow, matplotlib, openpyxl.
6. **No stub/placeholder code.** Every function fully implemented or not added
   at all.

## Context — what you already have

- `src/cc_client/client.py` — auth + retry + paginated POST search. Use
  `CartonCloudClient.from_env()`.
- `src/cc_client/queries.py` — `search_outbound_orders`, `search_inbound_orders`,
  `search_warehouse_products`, `search_warehouse_locations`, `get_stock_on_hand`.
- `scripts/extract_forage.py` — refreshes parquet snapshots in `data/raw/`
  for Forage tenant. Forage customer UUID: `d4810e1e-...` (see `.env`).
- `src/analysis/loaders.py` — `load_latest(raw_dir)` returns a `Snapshot`.
- `src/analysis/dim_loader.py` — loads the dim capture template.
  409/409 Forage SKUs measured as of the last upload.
- `src/analysis/full_pallet.py` — flags TC chocolate full-pallet SO lines.
- `src/analysis/routing.py` — the new module. Three streams:
  - `1_pallet_pick` (Stream 1, pick-to-pallet + wrap + label)
  - `2_wave_bypass` (Stream 2, wave pick, no bench)
  - `3_wave_bench` (Stream 3, wave pick via bench)
  - `0_unclassified` (missing pickbench dim)
- `scripts/route.py` — the orchestrator.

## Tasks — execute in order, report progress after each

### Task 1 — verify the pipeline runs against real data

1. Refresh the CC extract if it's older than 24h:
   `python3 scripts/extract_forage.py` (this reads, doesn't write to CC).
2. Confirm the latest dim file is in `data/dims/` and contains the 409
   measured SKUs. If not, ask the operator.
3. Run `python3 scripts/route.py` with defaults.
4. Open the produced `summary.md`. Read it.
5. Report:
   - Total orders classified.
   - Stream mix (counts and percentages for streams 0/1/2/3).
   - Which rule fired most often.
   - Dim coverage (orders fully dim-covered vs partial).
6. **Stop and check for red flags** — if any of these are true, halt and
   report before continuing:
   - More than 5% of orders land in `0_unclassified` (likely missing dim
     data for SKUs that ARE in the dim file — investigate the join).
   - Stream 1 captures less than 5% or more than 60% of orders (likely
     bad threshold).
   - Any rule path fires 0 times (likely dead code or bad data shape).

### Task 2 — tune the pallet-fraction threshold

The default `pallet_fraction_threshold` is 0.70 (set in `routing.py` as
`DEFAULT_PALLET_FRACTION_THRESHOLD`). It's a guess.

1. Re-run `route.py` four times: `--pallet-fraction-threshold 0.50`, `0.60`,
   `0.70`, `0.80`. Capture stream mix for each.
2. Read the `pallet_fraction` distribution from one of the
   `order_streams.csv` outputs. Find natural break points (look for
   bi-modality, plateaus). Tools: pandas describe + percentile plot via
   matplotlib (save chart under `data/processed/route_tuning/`).
3. Recommend a final threshold value with a one-paragraph justification
   based on the observed distribution.
4. Do NOT change `DEFAULT_PALLET_FRACTION_THRESHOLD` in code yet — just
   recommend. The operator decides whether to bake it in.

### Task 3 — build the top-20 consignee shortlist for annotation

1. From the most recent `consignee_profile.xlsx`, identify the top 20
   consignees by order count.
2. For each, surface:
   - state, postcode, suburb (display name)
   - orders count
   - median cartons / P90 cartons / max cartons
   - median pallet_fraction / P90
   - current auto-stream mix (% S1 / S2 / S3 / unclassified)
3. Suggest a recommended rule for each based on the shape:
   - If P90 cartons is big AND pallet_frac P90 is near 1 → suggest
     `override_stream = 1_pallet_pick`.
   - If they're a multi-mode shipper (some big, some small) AND there's a
     visible knee in cartons-per-order → suggest
     `min_cartons_override = <knee value>`.
   - Otherwise → leave blank, recommend "no rule needed (auto-classify
     handles it fine)".
4. Output as `data/processed/route_tuning/top20_consignee_recommendations.md`.

### Task 4 — sanity check the pallet-fraction belt-and-braces method

The cube method and position method should usually agree closely. Big
disagreements signal bad dim data.

1. Compute, for each order:
   `divergence = abs(pallet_fraction_cube - pallet_fraction_positions)`
2. Find orders where divergence > 0.30.
3. For each such order, identify which SKU(s) contribute most to the gap
   (typically: a SKU where cube ÷ pallet position math doesn't agree with
   its cartons-per-pallet value — usually means the dim or the
   cartons-per-pallet figure is wrong).
4. Output `data/processed/route_tuning/dim_divergence_review.csv` listing
   the suspect SKUs. Include `product_code`, `product_name`,
   `outer_l/w/h_mm`, `outer_cube_mm3`, `cartons_per_pallet`, the implied
   cube-per-pallet from cartons_per_pallet × outer_cube_mm3, and the
   divergence percentage vs the standard pallet usable cube.

### Task 5 — verify wave plan plausibility

1. Look at the `wave_schedule.csv` from the last run.
2. Check:
   - Are wave totals (cartons) sensible (not all 8-carton waves, not all
     200-carton mega-waves)?
   - Is the cutoff-release rate too high? (>40% of waves being `cutoff_release`
     means the early-release threshold is too high — operator has to wait
     until 13:00 for too much work).
   - Are any single waves over 80 cartons? (Probably too big to pick in
     one go — early-release should be tighter.)
3. Recommend an `--early-release-cartons` value with one-paragraph
   justification.

### Task 6 — write a short tuning report

Write `data/processed/route_tuning/REPORT.md` containing:
- Summary of findings from tasks 1–5.
- Recommended `pallet_fraction_threshold` and `early_release_cartons`
  values.
- Top 20 consignee rule recommendations (link to the file).
- List of SKUs with suspect dim data (link to the divergence CSV).
- Any bugs found in `routing.py` or `route.py` and what was patched.
- Any rule paths that fired 0 times and whether that's expected.

## Reporting cadence

After each task, write a short status update to the chat:
- What you did
- Any deviations from the plan and why
- What you found (key numbers)
- Whether to proceed to the next task or wait for operator input

If you hit ambiguity, **stop and ask** rather than guessing. Specifically:
- If a CC extract refresh fails — ask.
- If real-data results contradict the synthetic-test results (e.g. a rule
  that worked in synthetic test now fires 0 times) — ask.
- If proposed parameter changes look like they'd dramatically reshape
  the stream mix (>30% shift) — ask before recommending.

## Out of scope — do not do these

- Don't refactor existing modules unless you find a bug.
- Don't add new analyses beyond what's specified.
- Don't tune `DEFAULT_FULL_PALLET_RATIO` (0.90) — that's owned by
  `full_pallet.py` and out of scope here.
- Don't touch `assignment.py` — slotting is paused pending operator
  decisions about the recently-reshuffled warehouse layout.
- Don't push to git. Leave anything you change uncommitted so the
  operator can review.
