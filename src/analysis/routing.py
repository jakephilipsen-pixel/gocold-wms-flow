"""Order-level stream classification + wave release planning.

This module sits on top of velocity / full_pallet / dim_loader to answer:

    "For each open SO, which pick stream does it belong to, and when
     should we release it to the floor?"

Three streams, locked with operator (May 2026):

    1. STREAM 1 - pick-to-pallet, wrap, pallet label.
       Big orders. Picker builds a pallet directly. No bench involvement.

    2. STREAM 2 - wave pick, bench bypass.
       Smaller orders made entirely of direct-to-pallet SKUs (pickbench=N).
       Wave together, skip the bench, straight to dispatch staging.

    3. STREAM 3 - wave pick via bench.
       Smaller orders containing at least one repack SKU (pickbench=Y).
       Wave together, route through the bench for scan/repack, then staging.

Stream 1 triggers (whichever fires first):
  A. Computed pallet fraction >= threshold (cube method OR position method,
     whichever is greater - belt and braces).
  B. Consignee override rule (e.g. Coles/Woolies VIC/NSW chocolate always
     pallet; Adelaide >= 20 cartons triggers pallet).
  C. Any SO line already flagged by full_pallet_analysis as a full-pallet
     shipment (TC brand line at >= 90% of a pallet).

Streams 2 & 3 hold until 13:00 final cutoff unless accumulated carton total
crosses an early-release threshold (configurable).

Output is read-only - CSVs/xlsx/Parquet for human review. No writes to CC.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import time as dt_time
from pathlib import Path

import numpy as np
import pandas as pd

from .loaders import Snapshot
from .full_pallet import FullPalletAnalysis
from .dispatch_link import FLAGGED_DISPATCH

log = logging.getLogger(__name__)

# Standard AU pallet footprint (CHEP / Loscam) in mm.
# Used as the denominator in the cube-based pallet-fraction calculation.
# Height is the max stack height for tier 3 (Pallet height 3 = 1400mm cap per
# operator), giving us a "useable carton stack volume" reference.
PALLET_FOOTPRINT_L_MM = 1165
PALLET_FOOTPRINT_W_MM = 1165
PALLET_USABLE_HEIGHT_MM = 1400
PALLET_USABLE_CUBE_MM3 = (
    PALLET_FOOTPRINT_L_MM * PALLET_FOOTPRINT_W_MM * PALLET_USABLE_HEIGHT_MM
)

# Default Stream 1 trigger - 70% of a pallet equivalent. Tunable.
DEFAULT_PALLET_FRACTION_THRESHOLD = 0.70

# Default wave release rule - hold to 13:00 (Melbourne local time) and
# release earlier if accumulated cartons reaches threshold.
DEFAULT_WAVE_CUTOFF = dt_time(13, 0)
DEFAULT_EARLY_RELEASE_CARTONS = 30

# Stream identifiers - used in output and downstream tooling.
STREAM_PALLET = "1_pallet_pick"
STREAM_BYPASS = "2_wave_bypass"
STREAM_BENCH = "3_wave_bench"
STREAM_UNCLASSIFIED = "0_unclassified"  # missing dims; needs measurement


@dataclass
class OrderMetricsResult:
    """Per-order roll-up of cartons, cube, pallet-fraction, routing flags."""
    per_order: pd.DataFrame
    n_orders: int
    n_orders_with_dims: int
    n_orders_partial_dims: int
    pallet_fraction_method_summary: dict[str, int]


@dataclass
class StreamClassification:
    """Stream assignment with reason tracking."""
    per_order: pd.DataFrame  # per_order + stream + reason
    counts_by_stream: pd.Series
    rule_hit_counts: pd.Series  # which rule fired most often
    threshold_used: float


@dataclass
class ConsigneeProfile:
    """Annotation-ready per-consignee profile (the human-fillable template)."""
    profile: pd.DataFrame


@dataclass
class WavePlan:
    """Wave release schedule for streams 2 + 3."""
    per_wave: pd.DataFrame  # one row per (date, run_group, stream, wave_index)
    per_order_assignment: pd.DataFrame  # order_id -> wave_id mapping
    cutoff_used: dt_time
    early_release_cartons: int


# ---------- name normalisation ----------

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[.,/&'\"`]+")
# common multi-word DC keywords to keep grouping coherent
_DC_TOKENS = ("DC", "DISTRIBUTION", "DEPOT", "WAREHOUSE", "RDC")


def _normalise_consignee(name: object) -> str:
    """Loose normalisation for grouping consignees with minor variation.

    'Woolworths NSW DC' / 'WOOLWORTHS  N.S.W DC' / 'woolworths nsw dc'
    all collapse to 'WOOLWORTHS NSW DC'. Single source of truth so we don't
    have eight rows per real-world destination.
    """
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return ""
    s = str(name).strip().upper()
    if not s:
        return ""
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


# ---------- per-order metrics ----------

def compute_order_metrics(
    snap: Snapshot,
    dims: pd.DataFrame,
    full_pallet: FullPalletAnalysis | None = None,
) -> OrderMetricsResult:
    """Roll SO lines up to per-order metrics with cube + pallet-fraction.

    Output frame columns:
        so_id, so_ref, customer_id, customer_name,
        delivery_company, delivery_company_norm,
        delivery_state, delivery_postcode, delivery_suburb,
        ts_packed,
        line_count, sku_count, total_cartons,
        cartons_with_dims, cartons_missing_dims, dims_coverage,
        total_cube_mm3,
        pallet_fraction_cube,       # cube sum / pallet usable cube
        pallet_fraction_positions,  # sum(qty / cartons_per_pallet)
        pallet_fraction,            # max of the two (belt + braces)
        has_pickbench_sku,          # any SKU pickbench=True
        all_direct_skus,            # every SKU pickbench=False
        has_unknown_pickbench,      # any SKU with pickbench=None
        has_full_pallet_line,       # any line flagged by full_pallet
        full_pallet_line_count
    """
    if snap.so_lines.empty:
        log.warning("snapshot has no SO lines")
        return OrderMetricsResult(
            per_order=pd.DataFrame(),
            n_orders=0,
            n_orders_with_dims=0,
            n_orders_partial_dims=0,
            pallet_fraction_method_summary={},
        )

    so = snap.so_lines.copy()
    so["quantity"] = pd.to_numeric(so["quantity"], errors="coerce").fillna(0)

    # Join dims onto every SO line. We need cube + cartons_per_pallet +
    # pickbench. Use a left join so missing-dim SKUs still show up; we'll
    # track coverage explicitly below.
    dim_cols = [
        "product_code",
        "outer_cube_mm3",
        "cartons_per_pallet",
        "pickbench",
        "measurement_complete",
    ]
    dim_cols = [c for c in dim_cols if c in dims.columns]
    dims_subset = dims[dim_cols].drop_duplicates("product_code")
    so = so.merge(dims_subset, on="product_code", how="left")

    # Per-line cube contribution = qty * outer_cube_mm3
    so["line_cube_mm3"] = so["quantity"] * so["outer_cube_mm3"]
    # Per-line pallet-position contribution
    so["line_pallet_positions"] = np.where(
        so["cartons_per_pallet"].fillna(0) > 0,
        so["quantity"] / so["cartons_per_pallet"],
        np.nan,
    )

    # Flag rows with full dims (used for coverage stats).
    so["has_line_dims"] = so["measurement_complete"].fillna(False)

    # Tag full-pallet lines if we have that analysis.
    if full_pallet is not None and not full_pallet.flagged_so_lines.empty:
        fp_ids = set(
            zip(
                full_pallet.flagged_so_lines["so_id"],
                full_pallet.flagged_so_lines["product_code"],
            )
        )
        so["is_full_pallet_line"] = [
            (sid, pc) in fp_ids
            for sid, pc in zip(so["so_id"], so["product_code"])
        ]
    else:
        so["is_full_pallet_line"] = False

    # Group up to per-order
    # We pick delivery fields with `first` since they're SO-level not line-level.
    grouped = so.groupby("so_id", sort=False)

    per_order = grouped.agg(
        so_ref=("so_ref", "first"),
        customer_id=("customer_id", "first"),
        customer_name=("customer_name", "first"),
        delivery_company=("delivery_company", "first"),
        delivery_state=("delivery_state", "first"),
        delivery_postcode=("delivery_postcode", "first"),
        delivery_suburb=("delivery_suburb", "first"),
        ts_packed=("ts_packed", "first"),
        line_count=("product_code", "size"),
        sku_count=("product_code", "nunique"),
        total_cartons=("quantity", "sum"),
        total_cube_mm3=("line_cube_mm3", "sum"),
        sum_pallet_positions=("line_pallet_positions", "sum"),
        cartons_with_dims=(
            "has_line_dims",
            lambda s: int(
                (s.values * so.loc[s.index, "quantity"].values).sum()
            ),
        ),
        has_full_pallet_line=("is_full_pallet_line", "any"),
        full_pallet_line_count=("is_full_pallet_line", "sum"),
    ).reset_index()

    per_order["cartons_missing_dims"] = (
        per_order["total_cartons"] - per_order["cartons_with_dims"]
    )
    per_order["dims_coverage"] = np.where(
        per_order["total_cartons"] > 0,
        per_order["cartons_with_dims"] / per_order["total_cartons"],
        0.0,
    )

    # Two methods of pallet fraction
    per_order["pallet_fraction_cube"] = (
        per_order["total_cube_mm3"] / PALLET_USABLE_CUBE_MM3
    )
    per_order["pallet_fraction_positions"] = per_order["sum_pallet_positions"]
    # belt-and-braces: max of the two (treat NaN as 0 so we don't lose orders
    # purely because one method couldn't be computed)
    per_order["pallet_fraction"] = np.maximum(
        per_order["pallet_fraction_cube"].fillna(0),
        per_order["pallet_fraction_positions"].fillna(0),
    )

    # Pickbench rollups: any/all/unknown across the order's lines.
    pickbench_rollup = grouped["pickbench"].agg(
        has_pickbench_sku=lambda s: bool((s == True).any()),  # noqa: E712
        all_direct_skus=lambda s: bool(
            (s == False).all() and s.notna().all()  # noqa: E712
        ),
        has_unknown_pickbench=lambda s: bool(s.isna().any()),
    ).reset_index()
    per_order = per_order.merge(pickbench_rollup, on="so_id", how="left")

    # Normalised consignee for grouping
    per_order["delivery_company_norm"] = per_order["delivery_company"].map(
        _normalise_consignee
    )

    # Drop the intermediate sum_pallet_positions column (it's reflected in
    # pallet_fraction_positions)
    per_order = per_order.drop(columns=["sum_pallet_positions"])

    # Coverage stats
    n = len(per_order)
    full_cov = int((per_order["dims_coverage"] >= 0.999).sum())
    partial = int(
        ((per_order["dims_coverage"] > 0) & (per_order["dims_coverage"] < 0.999)).sum()
    )

    cube_only = int(
        (per_order["pallet_fraction_cube"] > per_order["pallet_fraction_positions"])
        .fillna(False).sum()
    )
    pos_only = int(
        (per_order["pallet_fraction_positions"] > per_order["pallet_fraction_cube"])
        .fillna(False).sum()
    )
    tied = n - cube_only - pos_only
    method_summary = {
        "cube_method_higher": cube_only,
        "position_method_higher": pos_only,
        "tied_or_missing": tied,
    }

    log.info(
        "rolled up %d orders: %d fully dim-covered, %d partial, %d no dims",
        n, full_cov, partial, n - full_cov - partial,
    )

    return OrderMetricsResult(
        per_order=per_order,
        n_orders=n,
        n_orders_with_dims=full_cov,
        n_orders_partial_dims=partial,
        pallet_fraction_method_summary=method_summary,
    )


# ---------- consignee rules ----------

_RULE_OVERRIDE_STREAM = "override_stream"
_RULE_MIN_CARTONS = "min_cartons_override"

# Columns we expect in the operator-annotated rules CSV. We accept either the
# raw display name or the normalised name; we re-normalise here so rule lookup
# always uses the canonical form.
_RULE_REQUIRED_COLS = {"delivery_company"}
_RULE_OPTIONAL_COLS = {
    "delivery_company_norm",
    _RULE_OVERRIDE_STREAM,
    _RULE_MIN_CARTONS,
    "notes",
}


def load_consignee_rules(path: Path | None) -> pd.DataFrame:
    """Load operator-annotated consignee rules CSV.

    Returns DataFrame keyed by normalised consignee name with columns:
        delivery_company_norm, override_stream, min_cartons_override, notes

    If path is None or doesn't exist, returns an empty frame so callers can
    just merge against it without special-casing.
    """
    if path is None or not Path(path).exists():
        log.info(
            "no consignee rules file (path=%s); using defaults only",
            path,
        )
        return pd.DataFrame(
            columns=[
                "delivery_company_norm",
                _RULE_OVERRIDE_STREAM,
                _RULE_MIN_CARTONS,
                "notes",
            ]
        )

    df = pd.read_csv(path)
    missing = _RULE_REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"consignee rules CSV missing required columns: {sorted(missing)}. "
            f"got: {list(df.columns)}"
        )

    df["delivery_company_norm"] = (
        df.get("delivery_company_norm")
        .fillna(df["delivery_company"].map(_normalise_consignee))
        if "delivery_company_norm" in df.columns
        else df["delivery_company"].map(_normalise_consignee)
    )

    # Validate override_stream values
    if _RULE_OVERRIDE_STREAM in df.columns:
        bad = (
            ~df[_RULE_OVERRIDE_STREAM].isna()
            & ~df[_RULE_OVERRIDE_STREAM].isin(
                [STREAM_PALLET, STREAM_BYPASS, STREAM_BENCH, ""]
            )
        )
        if bad.any():
            bad_vals = df.loc[bad, _RULE_OVERRIDE_STREAM].unique()
            raise ValueError(
                f"consignee rules has invalid override_stream values: "
                f"{list(bad_vals)}. Allowed: {STREAM_PALLET}, "
                f"{STREAM_BYPASS}, {STREAM_BENCH}, or blank."
            )
    else:
        df[_RULE_OVERRIDE_STREAM] = pd.NA

    if _RULE_MIN_CARTONS in df.columns:
        df[_RULE_MIN_CARTONS] = pd.to_numeric(
            df[_RULE_MIN_CARTONS], errors="coerce"
        )
    else:
        df[_RULE_MIN_CARTONS] = pd.NA

    if "notes" not in df.columns:
        df["notes"] = ""

    # If a consignee has multiple rows, the LAST one wins (give the operator
    # an obvious way to edit by appending), but warn so they know.
    dupes = df["delivery_company_norm"].duplicated(keep=False)
    if dupes.any():
        log.warning(
            "consignee rules has %d duplicate consignee entries; "
            "last-wins applied. Edit the CSV to dedupe.",
            int(dupes.sum()),
        )
    df = df.drop_duplicates("delivery_company_norm", keep="last")

    log.info(
        "loaded %d consignee rules (%d always-pallet, %d threshold-based)",
        len(df),
        int((df[_RULE_OVERRIDE_STREAM] == STREAM_PALLET).sum()),
        int(df[_RULE_MIN_CARTONS].notna().sum()),
    )
    return df[
        ["delivery_company_norm", _RULE_OVERRIDE_STREAM, _RULE_MIN_CARTONS, "notes"]
    ].reset_index(drop=True)


# ---------- stream classification ----------

def classify_streams(
    order_metrics: OrderMetricsResult,
    consignee_rules: pd.DataFrame,
    pallet_fraction_threshold: float = DEFAULT_PALLET_FRACTION_THRESHOLD,
) -> StreamClassification:
    """Apply stream rules in priority order.

    Rule priority (first match wins):
      R1. Consignee override_stream is set            -> use that
      R2. Consignee min_cartons override is set
          AND order.total_cartons >= min_cartons      -> STREAM_PALLET
      R2b. dispatch_flag in FLAGGED_DISPATCH (run
          untrustworthy / order absent from plan)     -> STREAM_PALLET
      R3. Order has a full_pallet_line flag           -> STREAM_PALLET
      R4. Order pallet_fraction >= threshold          -> STREAM_PALLET
      R5. Order has_unknown_pickbench (any SKU
          with no pickbench dim captured)             -> STREAM_UNCLASSIFIED
      R6. Order has_pickbench_sku                     -> STREAM_BENCH
      R7. Order all_direct_skus                       -> STREAM_BYPASS
      R8. Fallback (shouldn't happen)                 -> STREAM_UNCLASSIFIED
    """
    if order_metrics.per_order.empty:
        return StreamClassification(
            per_order=order_metrics.per_order.copy(),
            counts_by_stream=pd.Series(dtype=int),
            rule_hit_counts=pd.Series(dtype=int),
            threshold_used=pallet_fraction_threshold,
        )

    df = order_metrics.per_order.copy()

    # Merge consignee rules
    if not consignee_rules.empty:
        df = df.merge(
            consignee_rules,
            on="delivery_company_norm",
            how="left",
        )
    else:
        df[_RULE_OVERRIDE_STREAM] = pd.NA
        df[_RULE_MIN_CARTONS] = pd.NA

    streams: list[str] = []
    reasons: list[str] = []
    rules_fired: list[str] = []

    for row in df.itertuples(index=False):
        override = getattr(row, _RULE_OVERRIDE_STREAM, None)
        min_cartons = getattr(row, _RULE_MIN_CARTONS, None)

        # R1: explicit override
        if isinstance(override, str) and override.strip():
            streams.append(override.strip())
            reasons.append(f"consignee override -> {override.strip()}")
            rules_fired.append("R1_consignee_override")
            continue

        # R2: min_cartons threshold via consignee rule
        if (
            pd.notna(min_cartons)
            and min_cartons > 0
            and row.total_cartons >= min_cartons
        ):
            streams.append(STREAM_PALLET)
            reasons.append(
                f"consignee min_cartons {int(min_cartons)} hit "
                f"(order has {int(row.total_cartons)})"
            )
            rules_fired.append("R2_consignee_min_cartons")
            continue

        # R2b: dispatch flagged this order's run as untrustworthy (or it was
        # absent from the plan) -> build it to a pallet, don't risk the bench.
        dispatch_flag = getattr(row, "dispatch_flag", None)
        if isinstance(dispatch_flag, str) and dispatch_flag in FLAGGED_DISPATCH:
            streams.append(STREAM_PALLET)
            reasons.append(f"dispatch flag '{dispatch_flag}' -> pallet")
            rules_fired.append("R2b_dispatch_flagged")
            continue

        # R3: any line flagged as full pallet
        if bool(row.has_full_pallet_line):
            streams.append(STREAM_PALLET)
            reasons.append(
                f"order contains {int(row.full_pallet_line_count)} "
                f"full-pallet line(s)"
            )
            rules_fired.append("R3_full_pallet_line")
            continue

        # R4: computed pallet fraction over threshold
        if (
            pd.notna(row.pallet_fraction)
            and row.pallet_fraction >= pallet_fraction_threshold
        ):
            streams.append(STREAM_PALLET)
            reasons.append(
                f"pallet_fraction {row.pallet_fraction:.2f} >= "
                f"{pallet_fraction_threshold:.2f}"
            )
            rules_fired.append("R4_pallet_fraction")
            continue

        # R5: missing dim data - can't classify safely
        if bool(row.has_unknown_pickbench):
            streams.append(STREAM_UNCLASSIFIED)
            reasons.append("order has SKU(s) with no pickbench dim captured")
            rules_fired.append("R5_unknown_pickbench")
            continue

        # R6: bench-required
        if bool(row.has_pickbench_sku):
            streams.append(STREAM_BENCH)
            reasons.append("contains pickbench SKU -> wave via bench")
            rules_fired.append("R6_has_pickbench")
            continue

        # R7: pure direct-to-pallet wave
        if bool(row.all_direct_skus):
            streams.append(STREAM_BYPASS)
            reasons.append("all SKUs direct-to-pallet -> wave bypass")
            rules_fired.append("R7_all_direct")
            continue

        # R8: shouldn't happen given R5/R6/R7 partition
        streams.append(STREAM_UNCLASSIFIED)
        reasons.append("no rule matched")
        rules_fired.append("R8_no_match")

    df["stream"] = streams
    df["stream_reason"] = reasons
    df["rule_fired"] = rules_fired

    counts = df["stream"].value_counts()
    rule_counts = df["rule_fired"].value_counts()

    log.info(
        "stream classification: %s",
        ", ".join(f"{k}={v}" for k, v in counts.items()),
    )
    return StreamClassification(
        per_order=df,
        counts_by_stream=counts,
        rule_hit_counts=rule_counts,
        threshold_used=pallet_fraction_threshold,
    )


# ---------- consignee profile (annotation template) ----------

def build_consignee_profile(
    classification: StreamClassification,
) -> ConsigneeProfile:
    """Aggregate per-order data into a per-consignee annotation template.

    One row per delivery_company_norm with carton stats, pallet-fraction
    stats, current auto-classification mix, and blank columns the operator
    fills in to override the defaults.

    Output is xlsx-ready: includes the raw display name (most common form
    seen), normalised name (the join key), and blank override columns.
    """
    df = classification.per_order
    if df.empty:
        return ConsigneeProfile(profile=pd.DataFrame())

    def _mode(s: pd.Series) -> object:
        s = s.dropna()
        if s.empty:
            return ""
        try:
            return s.mode().iloc[0]
        except (IndexError, AttributeError):
            return s.iloc[0]

    grp = df.groupby("delivery_company_norm", dropna=False)

    profile = grp.agg(
        delivery_company=("delivery_company", _mode),
        state_main=("delivery_state", _mode),
        postcode_main=("delivery_postcode", _mode),
        suburb_main=("delivery_suburb", _mode),
        orders=("so_id", "nunique"),
        total_cartons=("total_cartons", "sum"),
        cartons_mean=("total_cartons", "mean"),
        cartons_median=("total_cartons", "median"),
        cartons_p90=("total_cartons", lambda s: float(np.percentile(s, 90))),
        cartons_max=("total_cartons", "max"),
        pallet_frac_mean=("pallet_fraction", "mean"),
        pallet_frac_median=("pallet_fraction", "median"),
        pallet_frac_p90=(
            "pallet_fraction", lambda s: float(np.percentile(s.fillna(0), 90))
        ),
        pct_orders_stream_1=(
            "stream",
            lambda s: 100.0 * (s == STREAM_PALLET).sum() / len(s),
        ),
        pct_orders_stream_2=(
            "stream",
            lambda s: 100.0 * (s == STREAM_BYPASS).sum() / len(s),
        ),
        pct_orders_stream_3=(
            "stream",
            lambda s: 100.0 * (s == STREAM_BENCH).sum() / len(s),
        ),
        pct_orders_unclassified=(
            "stream",
            lambda s: 100.0 * (s == STREAM_UNCLASSIFIED).sum() / len(s),
        ),
    ).reset_index()

    # round + clean for human reading
    for c in (
        "cartons_mean",
        "cartons_median",
        "cartons_p90",
        "cartons_max",
    ):
        profile[c] = profile[c].round(1)
    for c in (
        "pallet_frac_mean",
        "pallet_frac_median",
        "pallet_frac_p90",
    ):
        profile[c] = profile[c].round(3)
    for c in (
        "pct_orders_stream_1",
        "pct_orders_stream_2",
        "pct_orders_stream_3",
        "pct_orders_unclassified",
    ):
        profile[c] = profile[c].round(1)

    profile = profile.sort_values("orders", ascending=False).reset_index(drop=True)

    # blank columns for the operator to fill in
    profile[_RULE_OVERRIDE_STREAM] = ""
    profile[_RULE_MIN_CARTONS] = pd.NA
    profile["notes"] = ""

    # reorder columns for readability
    cols = [
        "delivery_company",
        "delivery_company_norm",
        "state_main",
        "postcode_main",
        "suburb_main",
        "orders",
        "total_cartons",
        "cartons_mean",
        "cartons_median",
        "cartons_p90",
        "cartons_max",
        "pallet_frac_mean",
        "pallet_frac_median",
        "pallet_frac_p90",
        "pct_orders_stream_1",
        "pct_orders_stream_2",
        "pct_orders_stream_3",
        "pct_orders_unclassified",
        _RULE_OVERRIDE_STREAM,
        _RULE_MIN_CARTONS,
        "notes",
    ]
    profile = profile[cols]

    log.info(
        "built consignee profile: %d distinct consignees",
        len(profile),
    )
    return ConsigneeProfile(profile=profile)


# ---------- wave planning ----------

def plan_waves(
    classification: StreamClassification,
    cutoff: dt_time = DEFAULT_WAVE_CUTOFF,
    early_release_cartons: int = DEFAULT_EARLY_RELEASE_CARTONS,
    run_group_col: str = "delivery_state",
) -> WavePlan:
    """Group wave-eligible orders (streams 2 + 3) into release waves.

    Grouping key: (received_date, run_group, stream). Within each group,
    orders accumulate FIFO by ts_packed; a wave releases when accumulated
    cartons crosses early_release_cartons. Any leftover orders at end of
    day form a final wave released at `cutoff`.

    run_group_col defaults to delivery_state - good enough proxy for delivery
    run until you upload an explicit run map. Easy to swap by passing a
    different column name.

    Stream 1 orders are excluded - they go to the floor immediately, no wave.
    """
    df = classification.per_order
    if df.empty:
        return WavePlan(
            per_wave=pd.DataFrame(),
            per_order_assignment=pd.DataFrame(),
            cutoff_used=cutoff,
            early_release_cartons=early_release_cartons,
        )

    wave_eligible = df[df["stream"].isin([STREAM_BYPASS, STREAM_BENCH])].copy()
    if wave_eligible.empty:
        log.info("no orders in wave-eligible streams (2/3)")
        return WavePlan(
            per_wave=pd.DataFrame(),
            per_order_assignment=pd.DataFrame(),
            cutoff_used=cutoff,
            early_release_cartons=early_release_cartons,
        )

    # received_date for grouping - we use ts_packed as proxy (the timestamp
    # we have). In reality you might want received_at or due_date here.
    ts = pd.to_datetime(
        wave_eligible["ts_packed"], errors="coerce", utc=True,
    )
    # localise to Melbourne time for cutoff comparison
    try:
        ts_local = ts.dt.tz_convert("Australia/Melbourne")
    except (TypeError, AttributeError):
        ts_local = ts
    wave_eligible["receive_date"] = ts_local.dt.date

    if run_group_col not in wave_eligible.columns:
        log.warning(
            "run_group_col %r not in per_order; falling back to delivery_state",
            run_group_col,
        )
        run_group_col = "delivery_state"

    wave_eligible = wave_eligible.sort_values(
        ["receive_date", run_group_col, "stream", "ts_packed"]
    ).reset_index(drop=True)

    waves_per_order_rows: list[dict] = []
    waves_summary_rows: list[dict] = []

    group_keys = ["receive_date", run_group_col, "stream"]
    for keys, group in wave_eligible.groupby(group_keys, sort=False, dropna=False):
        receive_date, run_group, stream = keys
        accumulated = 0.0
        wave_idx = 1
        wave_orders: list[dict] = []

        for row in group.itertuples(index=False):
            wave_orders.append({
                "so_id": row.so_id,
                "cartons": float(row.total_cartons),
                "ts_packed": row.ts_packed,
            })
            accumulated += float(row.total_cartons)

            if accumulated >= early_release_cartons:
                wave_id = _make_wave_id(receive_date, run_group, stream, wave_idx)
                _emit_wave(
                    wave_id, receive_date, run_group, stream, wave_idx,
                    wave_orders, "early_release",
                    waves_per_order_rows, waves_summary_rows,
                )
                wave_orders = []
                accumulated = 0.0
                wave_idx += 1

        # leftover orders -> cutoff release
        if wave_orders:
            wave_id = _make_wave_id(receive_date, run_group, stream, wave_idx)
            _emit_wave(
                wave_id, receive_date, run_group, stream, wave_idx,
                wave_orders, "cutoff_release",
                waves_per_order_rows, waves_summary_rows,
            )

    per_order_df = pd.DataFrame(waves_per_order_rows)
    per_wave_df = pd.DataFrame(waves_summary_rows)

    log.info(
        "planned %d waves across %d orders (cutoff=%s, early=%d cartons)",
        len(per_wave_df), len(per_order_df),
        cutoff.strftime("%H:%M"), early_release_cartons,
    )

    return WavePlan(
        per_wave=per_wave_df,
        per_order_assignment=per_order_df,
        cutoff_used=cutoff,
        early_release_cartons=early_release_cartons,
    )


def _make_wave_id(
    receive_date: object, run_group: object, stream: str, idx: int
) -> str:
    d = receive_date.isoformat() if hasattr(receive_date, "isoformat") else str(receive_date)
    rg = str(run_group) if run_group is not None and not (
        isinstance(run_group, float) and np.isnan(run_group)
    ) else "UNK"
    stream_short = stream.split("_", 1)[0]  # 2 or 3
    return f"{d}_{rg}_S{stream_short}_W{idx:02d}"


def _emit_wave(
    wave_id: str,
    receive_date,
    run_group,
    stream: str,
    wave_idx: int,
    wave_orders: list[dict],
    release_reason: str,
    per_order_rows: list[dict],
    summary_rows: list[dict],
) -> None:
    total_cartons = sum(o["cartons"] for o in wave_orders)
    for o in wave_orders:
        per_order_rows.append({
            "wave_id": wave_id,
            "so_id": o["so_id"],
            "cartons": o["cartons"],
            "ts_packed": o["ts_packed"],
            "stream": stream,
        })
    summary_rows.append({
        "wave_id": wave_id,
        "receive_date": receive_date,
        "run_group": run_group,
        "stream": stream,
        "wave_index": wave_idx,
        "release_reason": release_reason,
        "order_count": len(wave_orders),
        "total_cartons": total_cartons,
    })
