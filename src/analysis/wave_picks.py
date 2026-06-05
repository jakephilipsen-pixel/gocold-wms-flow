"""Build operator-ready wave pick sheets from routed open orders.

Sits on top of routing (``StreamClassification`` + ``plan_waves``) and
the locations/assignments modules to produce one ``WavePickSheet`` per
wave_id. Each sheet contains:

  * the orders in the wave (so the operator can paste their refs into
    CartonCloud's wave-creation UI)
  * consolidated pick lines (one row per unique SKU per wave, with the
    total carton qty summed across orders and the contributing so_refs
    listed) sorted by warehouse walk order
  * pre-numbered Walk # column so the picker just walks down the page

Read-only. We never push anything back to CC; the operator manually
creates the wave in CC using the order list we generate.

Location resolution for each (so_id, product_code):
    There is one source: ``sku_locations`` — a live SKU → location map
    derived from the CartonCloud stock-on-hand report (one pick-face
    location per SKU). A line whose SKU is absent from ``sku_locations``
    still rides the wave, flagged ``unallocated`` (location shown as
    ``UNALLOCATED``), and is sorted to the end of the walk for manual
    locating by the operator. Only genuinely empty orders (no SO lines
    present in the extract) are skipped to ``skipped_orders``.

Streams 2 + 3 only. Stream 1 (pick-to-pallet) needs different paperwork
(pallet labels, wrap instructions) and is out of scope.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from .routing import (
    STREAM_BENCH,
    STREAM_BYPASS,
    StreamClassification,
    plan_waves,
)

log = logging.getLogger(__name__)


# Default CC outbound-order status code for orders ready to be waved.
# Confirmed live against the API on 2026-05-17.
DEFAULT_AWAITING_STATUS = "AWAITING_PICK_AND_PACK"

# Rule of thumb for time-to-pick — used on the cover page to give the
# operator an expected duration. Tune once we have actual cycle data.
DEFAULT_LINES_PER_HOUR = 60


@dataclass
class WavePickSheet:
    """One wave_id worth of operator-facing data."""
    wave_id: str
    stream: str  # 1_pallet_pick / 2_wave_bypass / 3_wave_bench
    run_group: str  # delivery_state (or delivery_run when wired up)
    receive_date: date | None
    orders: pd.DataFrame
    pick_lines: pd.DataFrame
    total_cartons: int
    total_lines: int
    estimated_walk_distance_m: float


@dataclass
class WaveGenerationResult:
    """Output of ``generate_wave_pick_sheets``."""
    sheets: list[WavePickSheet] = field(default_factory=list)
    skipped_orders: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: dict = field(default_factory=dict)


# ---------- internal helpers ----------

def _empty_pick_lines() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "walk_index",
        "location",
        "aisle",
        "bay",
        "level",
        "sublevel",
        "product_code",
        "product_name",
        "qty_cartons",
        "cartons_running_total",
        "contributing_so_refs",
        "unallocated",
    ])


def _empty_orders() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "so_id",
        "so_ref",
        "customer_name",
        "delivery_company",
        "delivery_suburb",
        "delivery_state",
        "delivery_postcode",
        "cartons",
        "lines",
    ])


def _build_sku_location_lookup(
    sku_locations: pd.DataFrame | None,
) -> pd.DataFrame:
    """Normalise the live SKU -> location frame to the columns the
    generator needs: product_code, location, aisle, bay, level, sublevel."""
    cols = ["product_code", "location", "aisle", "bay", "level", "sublevel"]
    if sku_locations is None or sku_locations.empty:
        return pd.DataFrame(columns=cols)
    s = sku_locations.copy()
    if "assigned_location" in s.columns and "location" not in s.columns:
        s = s.rename(columns={"assigned_location": "location"})
    if "location" not in s.columns:
        raise ValueError("sku_locations must include a 'location' column")
    for c in ("aisle", "bay", "level", "sublevel"):
        if c not in s.columns:
            s[c] = pd.NA
    return s.drop_duplicates("product_code", keep="first").reset_index(
        drop=True)[cols]


def _walk_sort_key(
    df: pd.DataFrame, aisle_walk_order: list[str] | None
) -> pd.DataFrame:
    """Return df with a deterministic walk-order ranking applied.

    Default order: alphabetical aisle, then bay asc, then level asc, then
    sublevel asc. If ``aisle_walk_order`` is provided, that list dictates
    aisle ordering (and unlisted aisles sort to the end alphabetically).
    """
    df = df.copy()

    if "unallocated" in df.columns:
        df["_unalloc_rank"] = df["unallocated"].fillna(False).astype(int)
    else:
        df["_unalloc_rank"] = 0

    if aisle_walk_order:
        # Anchor known aisles to explicit indices; unknown ones land after.
        rank = {code: i for i, code in enumerate(aisle_walk_order)}
        df["_aisle_rank"] = df["aisle"].map(
            lambda a: rank.get(a, len(rank) + 1)
        )
        # Keep a tiebreaker so unknown aisles still sort alphabetically.
        df["_aisle_tie"] = df["aisle"].fillna("").astype(str)
    else:
        df["_aisle_rank"] = 0
        df["_aisle_tie"] = df["aisle"].fillna("").astype(str)

    for col in ("bay", "level", "sublevel"):
        if col not in df.columns:
            df[col] = pd.NA

    df["_bay_num"] = pd.to_numeric(df["bay"], errors="coerce").fillna(9999)
    df["_level_num"] = pd.to_numeric(df["level"], errors="coerce").fillna(9999)
    df["_sublevel_num"] = pd.to_numeric(
        df["sublevel"], errors="coerce"
    ).fillna(9999)

    df = df.sort_values(
        ["_unalloc_rank", "_aisle_rank", "_aisle_tie",
         "_bay_num", "_level_num", "_sublevel_num"],
        kind="mergesort",
    ).reset_index(drop=True)
    return df.drop(columns=[
        "_unalloc_rank", "_aisle_rank", "_aisle_tie",
        "_bay_num", "_level_num", "_sublevel_num"
    ])


def _estimate_walk_distance(pick_lines: pd.DataFrame) -> float:
    """Rough walk-distance estimate in metres.

    Treats each unique (aisle, bay) hop as 1.4 m of travel plus a 6 m
    aisle-change cost. Good enough to give the operator a ballpark on
    the cover page. Returns 0.0 if we don't have aisle data.
    """
    if pick_lines.empty:
        return 0.0
    if pick_lines["aisle"].isna().all():
        return 0.0
    travel = 0.0
    last_aisle: object = None
    last_bay: object = None
    for row in pick_lines.itertuples(index=False):
        if last_aisle is None:
            travel += 5.0  # entry walk to first pick
        elif row.aisle != last_aisle:
            travel += 6.0  # aisle change
        else:
            try:
                travel += 1.4 * abs(int(row.bay) - int(last_bay))
            except (TypeError, ValueError):
                travel += 1.4
        last_aisle, last_bay = row.aisle, row.bay
    return round(travel, 1)


# ---------- public entry point ----------

def generate_wave_pick_sheets(
    classification: StreamClassification,
    so_lines: pd.DataFrame,
    sku_locations: pd.DataFrame | None = None,
    aisle_walk_order: list[str] | None = None,
    run_group_col: str = "delivery_state",
    early_release_cartons: int | None = None,
) -> WaveGenerationResult:
    """Build wave pick sheets from a stream classification.

    Pipeline:
      1. Reuse ``plan_waves`` to group streams 2/3 orders into waves.
      2. For each wave, pull the order detail (so_lines for those so_ids).
      3. Resolve a location for each (so_id, product_code) via
         ``sku_locations`` (the sole live SOH-derived source).
      4. Lines whose SKU has no live location ride the wave flagged
         ``unallocated`` (sorted last); only genuinely empty orders are
         skipped.
      5. Consolidate same-SKU picks across orders within the wave (one
         row per unique location/SKU with summed qty and a list of
         contributing so_refs).
      6. Sort by walk order (unallocated lines last) and pre-number the
         picks.

    Parameters
    ----------
    classification :
        Output of ``classify_streams`` — needed for per-order metadata.
    so_lines :
        Raw SO lines (typically ``Snapshot.so_lines``). Provides the
        per-line SKU/qty detail that the order-level frame doesn't have.
    sku_locations :
        Live SKU -> location frame derived from the SOH report (the sole
        location source). Must include ``product_code`` and ``location``
        columns. Optional split-location columns ``aisle``, ``bay``,
        ``level``, ``sublevel`` are used for walk-order sorting when
        present. SKUs absent from this frame ride the wave flagged
        ``unallocated``.
    aisle_walk_order :
        Optional explicit aisle order. Default = alphabetical.
    run_group_col :
        Column from per-order data used to group waves by delivery run.
    early_release_cartons :
        Override for ``plan_waves.early_release_cartons``. ``None`` keeps
        the routing-module default.
    """
    result = WaveGenerationResult()

    if classification.per_order.empty:
        log.warning("classification has no orders; nothing to wave")
        result.summary = {
            "n_waves": 0,
            "n_orders_total": 0,
            "n_orders_skipped": 0,
            "n_pick_lines_total": 0,
            "n_lines_unallocated": 0,
            "n_skus_unallocated": 0,
        }
        return result

    if so_lines is None or so_lines.empty:
        log.warning("no so_lines provided; nothing to wave")
        result.summary = {
            "n_waves": 0,
            "n_orders_total": 0,
            "n_orders_skipped": 0,
            "n_pick_lines_total": 0,
            "n_lines_unallocated": 0,
            "n_skus_unallocated": 0,
        }
        return result

    # Reuse the routing module's wave planner.
    plan_kwargs: dict = {"run_group_col": run_group_col}
    if early_release_cartons is not None:
        plan_kwargs["early_release_cartons"] = early_release_cartons
    wave_plan = plan_waves(classification, **plan_kwargs)

    if wave_plan.per_wave.empty:
        log.info("plan_waves produced no waves (no stream 2/3 orders)")
        result.summary = {
            "n_waves": 0,
            "n_orders_total": 0,
            "n_orders_skipped": 0,
            "n_pick_lines_total": 0,
            "n_lines_unallocated": 0,
            "n_skus_unallocated": 0,
        }
        return result

    # Build the SKU -> location lookup once (live SOH only).
    sku_lookup = _build_sku_location_lookup(sku_locations)
    sku_lookup_idx = (
        sku_lookup.set_index("product_code") if not sku_lookup.empty else None
    )
    if sku_lookup.empty:
        log.warning(
            "no live SKU locations provided; every line will be unallocated"
        )

    # Per-order assignments: wave_id -> [so_id, ...]
    wave_orders = wave_plan.per_order_assignment.groupby("wave_id")["so_id"].apply(
        list
    ).to_dict()

    # Per-order frame (for orders DataFrame on each sheet).
    per_order = classification.per_order.set_index("so_id")

    # Index SO lines by so_id for fast lookup.
    so_lines = so_lines.copy()
    so_lines["quantity"] = pd.to_numeric(
        so_lines["quantity"], errors="coerce"
    ).fillna(0)
    so_lines_by_so = {
        sid: g for sid, g in so_lines.groupby("so_id", sort=False)
    }

    skipped_rows: list[dict] = []
    sheets: list[WavePickSheet] = []
    total_pick_lines = 0
    n_orders_total = 0
    n_orders_skipped = 0

    # Iterate waves in stable order.
    for wave_row in wave_plan.per_wave.itertuples(index=False):
        wave_id = wave_row.wave_id
        stream = wave_row.stream
        run_group = str(wave_row.run_group) if wave_row.run_group is not None else ""
        receive_date = wave_row.receive_date

        so_ids = wave_orders.get(wave_id, [])
        if not so_ids:
            continue

        # Walk every order's lines; either route to the consolidated pick
        # frame or drop the whole order into ``skipped_orders``.
        order_picks: list[dict] = []
        orders_in_wave: list[dict] = []
        for sid in so_ids:
            n_orders_total += 1
            lines = so_lines_by_so.get(sid)
            if lines is None or lines.empty:
                skipped_rows.append({
                    "wave_id": wave_id,
                    "so_id": sid,
                    "so_ref": per_order.loc[sid, "so_ref"]
                    if sid in per_order.index else "",
                    "reason": "no SO lines in extract",
                    "missing_skus": "",
                })
                n_orders_skipped += 1
                continue

            order_rows: list[dict] = []
            for line in lines.itertuples(index=False):
                code = getattr(line, "product_code", None)
                qty = float(getattr(line, "quantity", 0) or 0)
                if not code or qty <= 0:
                    continue
                loc_row = None
                if sku_lookup_idx is not None and code in sku_lookup_idx.index:
                    loc_row = sku_lookup_idx.loc[code]
                if loc_row is None:
                    # No live location — line still rides the wave, flagged.
                    order_rows.append({
                        "so_id": sid,
                        "product_code": code,
                        "product_name": getattr(line, "product_name", ""),
                        "quantity": qty,
                        "location": "UNALLOCATED",
                        "aisle": pd.NA, "bay": pd.NA,
                        "level": pd.NA, "sublevel": pd.NA,
                        "unallocated": True,
                    })
                    continue
                order_rows.append({
                    "so_id": sid,
                    "product_code": code,
                    "product_name": getattr(line, "product_name", ""),
                    "quantity": qty,
                    "location": loc_row.get("location"),
                    "aisle": loc_row.get("aisle"),
                    "bay": loc_row.get("bay"),
                    "level": loc_row.get("level"),
                    "sublevel": loc_row.get("sublevel"),
                    "unallocated": False,
                })

            order_picks.extend(order_rows)

            if sid in per_order.index:
                meta = per_order.loc[sid]
                orders_in_wave.append({
                    "so_id": sid,
                    "so_ref": meta.get("so_ref", ""),
                    "customer_name": meta.get("customer_name", ""),
                    "delivery_company": meta.get("delivery_company", ""),
                    "delivery_suburb": meta.get("delivery_suburb", ""),
                    "delivery_state": meta.get("delivery_state", ""),
                    "delivery_postcode": meta.get("delivery_postcode", ""),
                    "cartons": int(round(float(meta.get("total_cartons", 0) or 0))),
                    "lines": int(meta.get("line_count", 0) or 0),
                })

        if not order_picks:
            log.info(
                "wave %s: all orders skipped (no pick lines built)", wave_id
            )
            continue

        picks_df = pd.DataFrame(order_picks)
        # so_ref per so_id for the contributing list.
        so_ref_map = (
            per_order["so_ref"]
            if "so_ref" in per_order.columns
            else pd.Series(dtype=str)
        )
        picks_df["so_ref"] = picks_df["so_id"].map(so_ref_map).fillna("")

        # Consolidate: one row per (location, product_code) with summed qty
        # and the list of contributing so_refs.
        consolidated = picks_df.groupby(
            ["location", "product_code"], dropna=False, sort=False
        ).agg(
            product_name=("product_name", "first"),
            aisle=("aisle", "first"),
            bay=("bay", "first"),
            level=("level", "first"),
            sublevel=("sublevel", "first"),
            qty_cartons=("quantity", "sum"),
            contributing_so_refs=("so_ref", lambda s: ", ".join(
                sorted({x for x in s if x})
            )),
            unallocated=("unallocated", "first"),
        ).reset_index()

        consolidated = _walk_sort_key(consolidated, aisle_walk_order)
        consolidated.insert(0, "walk_index", range(1, len(consolidated) + 1))
        consolidated["cartons_running_total"] = (
            consolidated["qty_cartons"].cumsum().astype(int)
        )
        consolidated["qty_cartons"] = consolidated["qty_cartons"].astype(int)

        ordered_cols = [
            "walk_index",
            "location",
            "aisle",
            "bay",
            "level",
            "sublevel",
            "product_code",
            "product_name",
            "qty_cartons",
            "cartons_running_total",
            "contributing_so_refs",
            "unallocated",
        ]
        consolidated = consolidated[ordered_cols]

        orders_df = pd.DataFrame(orders_in_wave) if orders_in_wave else _empty_orders()
        if not orders_df.empty:
            orders_df = orders_df.sort_values("so_ref").reset_index(drop=True)

        total_cartons = int(consolidated["qty_cartons"].sum())
        total_lines = len(consolidated)
        walk_distance = _estimate_walk_distance(consolidated)

        sheets.append(WavePickSheet(
            wave_id=wave_id,
            stream=stream,
            run_group=run_group,
            receive_date=receive_date,
            orders=orders_df,
            pick_lines=consolidated,
            total_cartons=total_cartons,
            total_lines=total_lines,
            estimated_walk_distance_m=walk_distance,
        ))
        total_pick_lines += total_lines

    n_lines_unallocated = sum(
        int(s.pick_lines["unallocated"].fillna(False).sum())
        for s in sheets if "unallocated" in s.pick_lines.columns
    )
    n_skus_unallocated = len({
        code
        for s in sheets if "unallocated" in s.pick_lines.columns
        for code in s.pick_lines.loc[
            s.pick_lines["unallocated"].fillna(False), "product_code"]
    })

    skipped_df = (
        pd.DataFrame(skipped_rows)
        if skipped_rows
        else pd.DataFrame(columns=[
            "wave_id", "so_id", "so_ref", "reason", "missing_skus",
        ])
    )

    result.sheets = sheets
    result.skipped_orders = skipped_df
    result.summary = {
        "n_waves": len(sheets),
        "n_orders_total": n_orders_total,
        "n_orders_skipped": n_orders_skipped,
        "n_pick_lines_total": total_pick_lines,
        "streams": sorted({s.stream for s in sheets}),
        "n_lines_unallocated": n_lines_unallocated,
        "n_skus_unallocated": n_skus_unallocated,
    }

    log.info(
        "generated %d waves over %d orders (%d skipped, %d total pick lines)",
        len(sheets), n_orders_total, n_orders_skipped, total_pick_lines,
    )
    return result


def estimated_time_to_pick_minutes(
    n_lines: int, lines_per_hour: int = DEFAULT_LINES_PER_HOUR
) -> int:
    """Rule-of-thumb minutes to pick a wave of ``n_lines`` lines."""
    if lines_per_hour <= 0:
        return 0
    return int(round(60.0 * n_lines / lines_per_hour))
