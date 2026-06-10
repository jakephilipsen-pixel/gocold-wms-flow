"""Shared core for wave pick generation.

Both the CLI (``scripts/generate_waves.py``) and the web console
(``src/web/``) call ``run_wave_generation`` so the pipeline lives in one
place. The CLI passes a ``progress`` callback that prints; the web app
passes one that buffers events for SSE.

Read-only against CartonCloud — we generate paperwork, never push back.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from analysis import (
    DEFAULT_AWAITING_STATUS,
    DEFAULT_EARLY_RELEASE_CARTONS,
    DEFAULT_FULL_PALLET_RATIO,
    DEFAULT_LINES_PER_HOUR,
    DEFAULT_PALLET_FRACTION_THRESHOLD,
    apply_tags,
    attach_dispatch_runs,
    classify_streams,
    compute_order_metrics,
    compute_velocity,
    find_latest_dispatch_plan,
    generate_wave_pick_sheets,
    load_consignee_rules,
    load_dimensions,
    load_dispatch_link,
    load_latest,
    run_full_pallet_analysis,
)
from analysis.loaders import Snapshot
from cc_client import (
    CartonCloudClient,
    CartonCloudError,
    get_sku_locations,
    search_outbound_orders,
)
from locations.grammar import parse_location_name
from output import generate_wave_pdf, write_wave_csvs

log = logging.getLogger("wave_runner")


@dataclass
class WaveRunSettings:
    """Everything ``run_wave_generation`` needs for one run.

    ``repo_root`` anchors the default data/output paths. Explicit path
    fields override the defaults (used by the CLI's flags).
    """
    repo_root: Path
    status: str = DEFAULT_AWAITING_STATUS
    customer_name: str | None = None
    pallet_fraction_threshold: float = DEFAULT_PALLET_FRACTION_THRESHOLD
    early_release_cartons: int = DEFAULT_EARLY_RELEASE_CARTONS
    run_group_col: str = "predicted_run"
    lines_per_hour: int = DEFAULT_LINES_PER_HOUR
    pallet_ratio: float = DEFAULT_FULL_PALLET_RATIO
    # Optional explicit paths; None = resolve from repo_root at run time.
    raw_dir: Path | None = None
    dims_path: Path | None = None
    rules_path: Path | None = None
    logo_path: Path | None = None
    out_dir: Path | None = None
    dispatch_plan_dir: Path | None = None
    include_pallet_sheets: bool = True


@dataclass
class ProgressEvent:
    """One streamed progress line."""
    stage: str          # machine-readable stage key (see run_wave_generation)
    message: str        # human-readable line
    level: str = "info"  # info / ok / error
    data: dict[str, object] = field(default_factory=dict)


@dataclass
class RunResult:
    """Outcome of a single ``run_wave_generation`` call."""
    run_id: str
    out_dir: Path
    summary: dict[str, object]
    status: str          # success / empty / failed
    error: str | None = None


ProgressCallback = Callable[[ProgressEvent], None]

# ---------------------------------------------------------------------------
# SOH → pick-face lookup helper
# ---------------------------------------------------------------------------

_SKU_LOC_COLS = ["product_code", "location", "aisle", "bay", "level", "sublevel"]

_SKU_CAND_COLS = [
    "product_code", "location", "aisle", "bay", "level", "sublevel",
    "role", "qty",
]


def build_sku_location_candidates(items: list[dict]) -> pd.DataFrame:
    """Every live SOH location per SKU, best-first within each SKU.

    Per-SKU ordering mirrors the old single-pick selection: pick faces
    before reserve, lowest grammar position, then walk order. ``role``
    is 'pick_face' or 'reserve' — grammar-unknown names collapse to
    'reserve' (if it isn't a known pick face, treat it as forklift
    territory). ``qty`` is the SOH stock figure for that (SKU, location)
    bucket in the customer's ordering UOM (eaches for Forage).
    """
    if not items:
        return pd.DataFrame(columns=_SKU_CAND_COLS)

    candidates: list[dict] = []
    for it in items:
        code = it.get("product_code")
        name = it.get("location_name")
        if not code or not name:
            continue
        info = parse_location_name(name)
        is_pick_face = info.role_by_grammar == "pick_face"
        candidates.append({
            "product_code": code,
            "location": name,
            "aisle": info.aisle,
            "bay": info.bay,
            "level": info.level,
            "sublevel": info.sublevel,
            "role": "pick_face" if is_pick_face else "reserve",
            "qty": pd.to_numeric(it.get("qty"), errors="coerce"),
            "_role_rank": 0 if is_pick_face else 1,
            "position": info.position,
        })

    if not candidates:
        return pd.DataFrame(columns=_SKU_CAND_COLS)

    df = pd.DataFrame(candidates)
    df = df.sort_values(
        ["product_code", "_role_rank", "position",
         "aisle", "bay", "level", "sublevel"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    return df[_SKU_CAND_COLS]


def build_sku_locations_from_soh(items: list[dict]) -> pd.DataFrame:
    """Collapse live SOH rows into one best location per SKU.

    Thin wrapper over ``build_sku_location_candidates`` kept for callers
    that only want the single-location view (selection rules documented
    there). Returns ``_SKU_LOC_COLS`` — one row per SKU.
    """
    cands = build_sku_location_candidates(items)
    if cands.empty:
        return pd.DataFrame(columns=_SKU_LOC_COLS)
    return (
        cands.drop_duplicates("product_code", keep="first")
        .reset_index(drop=True)[_SKU_LOC_COLS]
    )


# ---------------------------------------------------------------------------
# Lazy loader for the SO line flattener that lives in scripts/extract.py.
# scripts/ is not a package so we load by file path and cache the result.
# ---------------------------------------------------------------------------

_flatten_cache: dict = {}


def _get_flatten_fn(repo_root: Path):
    """Lazily load _flatten_outbound_order_lines from scripts/extract.py."""
    key = str(repo_root)
    if key not in _flatten_cache:
        extract_path = repo_root / "scripts" / "extract.py"
        spec = importlib.util.spec_from_file_location("_extract_mod", extract_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _flatten_cache[key] = mod._flatten_outbound_order_lines
    return _flatten_cache[key]


# ---------------------------------------------------------------------------
# Pipeline helpers (moved from scripts/generate_waves.py)
# ---------------------------------------------------------------------------


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _latest_file(dirpath: Path, pattern: str) -> Path | None:
    candidates = sorted(
        dirpath.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _pull_open_orders(
    client: CartonCloudClient,
    *,
    status: list[str],
    customer_name: str | None,
    out_path: Path,
    flatten_fn,
) -> pd.DataFrame:
    """Pull open SOs from CC and persist a per-line parquet for audit."""
    print(f"pulling SOs with status {status} from CC...")
    n_orders = 0
    rows: list[dict] = []
    try:
        for order in search_outbound_orders(
            client,
            status=status,
            customer_name=customer_name,
        ):
            n_orders += 1
            rows.extend(flatten_fn(order))
    except CartonCloudError as exc:
        raise CartonCloudError(f"CC pull failed: {exc}") from exc

    print(f"  + {n_orders} orders -> {len(rows)} line items")
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    print(f"  + audit parquet saved to {out_path}")
    return df


def _build_snapshot(
    live_so_lines: pd.DataFrame,
    raw_dir: Path,
) -> Snapshot:
    """Splice live SO lines into the latest extract for PO + products."""
    base = load_latest(raw_dir)
    # Replace the SO lines with the live pull; keep PO + products from disk.
    return Snapshot(
        so_lines=live_so_lines,
        po_lines=base.po_lines,
        products=base.products,
        so_path=Path("<live>"),
        po_path=base.po_path,
        products_path=base.products_path,
    )


def _build_index_md(
    out_dir: Path,
    sheets: list,
    skipped: pd.DataFrame,
    cfg: dict,
    skus_to_measure: list[str] | None = None,
) -> None:
    """Top-level index.md summarising every wave in this run."""
    lines = [
        "# Wave Pick Run",
        f"_Generated: {datetime.now():%Y-%m-%d %H:%M}_",
        "",
        "## Settings",
        f"- Status filter: `{cfg['status']}`",
        f"- Customer filter: `{cfg['customer_name'] or '(none)'}`",
        f"- pallet_fraction_threshold: {cfg['pallet_fraction_threshold']:.2f}",
        f"- early_release_cartons: {cfg['early_release_cartons']}",
        f"- run_group_col: `{cfg['run_group_col']}`",
        f"- Pick rate assumption: {cfg['lines_per_hour']} lines/hour",
        "",
        f"## {len(sheets)} wave(s) generated",
        "",
        "| Wave ID | Stream | Run group | Receive date | Orders | Pick lines | Cartons | Files |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for s in sheets:
        rd = s.receive_date.isoformat() if s.receive_date else "—"
        wave_dir = f"{s.wave_id}/"
        files = (
            f"[PDF]({wave_dir}{s.wave_id}_picksheet.pdf) · "
            f"[picks]({wave_dir}{s.wave_id}_picks.csv) · "
            f"[orders]({wave_dir}{s.wave_id}_orders.csv)"
        )
        lines.append(
            f"| `{s.wave_id}` | `{s.stream}` | {s.run_group} | {rd} | "
            f"{len(s.orders)} | {s.total_lines} | {s.total_cartons} | {files} |"
        )

    if not skipped.empty:
        lines.extend([
            "",
            f"## {len(skipped)} skipped order(s)",
            "",
            "These orders had no SO lines present in the extract and were "
            "therefore skipped entirely. SKUs without a live stock location "
            "are not skipped — they appear as `unallocated` pick lines on "
            "the sheet for the operator to manually locate.",
            "",
            "| Wave | SO ref | Reason | Missing SKUs |",
            "|---|---|---|---|",
        ])
        for r in skipped.itertuples(index=False):
            lines.append(
                f"| `{r.wave_id}` | {r.so_ref} | {r.reason} | "
                f"{r.missing_skus} |"
            )

    if skus_to_measure:
        lines.extend([
            "",
            f"## {len(skus_to_measure)} SKUs to measure",
            "",
            "These SKUs appear on today's orders but have no captured carton "
            "dims, so their orders could not be cube-classified and rode the "
            "pallet sheets. Capture dims to let them classify normally.",
            "",
            "| SKU |",
            "|---|",
            *[f"| `{sku}` |" for sku in skus_to_measure],
        ])

    (out_dir / "index.md").write_text("\n".join(lines))


def _settings_dict(settings, audit_path, resolved_plan_dir=None):
    """Flatten the settings used for a run into a JSON-serialisable dict.

    ``resolved_plan_dir`` is the dispatch plan actually consumed (which may have
    been auto-discovered when ``settings.dispatch_plan_dir`` was None); recording
    it keeps the audit trail honest about which run-prediction fed the wave.
    """
    plan_dir = resolved_plan_dir or settings.dispatch_plan_dir
    return {
        "status": settings.status,
        "customer_name": settings.customer_name,
        "pallet_fraction_threshold": settings.pallet_fraction_threshold,
        "early_release_cartons": settings.early_release_cartons,
        "run_group_col": settings.run_group_col,
        "dispatch_plan_dir": str(plan_dir) if plan_dir else None,
        "include_pallet_sheets": settings.include_pallet_sheets,
        "lines_per_hour": settings.lines_per_hour,
        "placement_source": "live_soh",
        "audit_parquet": str(audit_path),
    }


# ---------------------------------------------------------------------------
# The orchestration core. Both the CLI and the web console call this.
# ---------------------------------------------------------------------------


def run_wave_generation(
    settings: WaveRunSettings,
    progress: ProgressCallback,
) -> RunResult:
    """Run the full wave pick pipeline once. Read-only against CC."""
    repo_root = settings.repo_root
    raw_dir = settings.raw_dir or repo_root / "data" / "raw"
    out_base = settings.out_dir or repo_root / "data" / "processed" / "waves"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_base / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    def emit(stage, message, level="info", **data):
        progress(ProgressEvent(stage=stage, message=message, level=level, data=data))

    try:
        _load_dotenv(repo_root / ".env")
        flatten_fn = _get_flatten_fn(repo_root)
        statuses = [s.strip() for s in settings.status.split(",") if s.strip()]

        # 1. live SO pull
        emit("pull", f"pulling SOs with status {statuses} from CC…")
        client = CartonCloudClient.from_env()
        audit_path = raw_dir / f"so_lines_open_{stamp}.parquet"
        so_lines = _pull_open_orders(
            client, status=statuses, customer_name=settings.customer_name,
            out_path=audit_path, flatten_fn=flatten_fn,
        )
        if so_lines.empty:
            (out_dir / "index.md").write_text(
                f"# Wave Pick Run\n_{datetime.now():%Y-%m-%d %H:%M}_\n\n"
                f"No orders matched status `{settings.status}` "
                f"(customer={settings.customer_name!r}).\n"
            )
            summary = {"n_waves": 0, "n_orders_total": 0,
                       "n_orders_skipped": 0, "n_pick_lines_total": 0}
            (out_dir / "manifest.json").write_text(json.dumps(
                {"generated_at": datetime.now().isoformat(),
                 "settings": _settings_dict(settings, audit_path),
                 "summary": summary, "waves": []}, indent=2))
            emit("done", "No open orders to wave.", level="ok", **summary)
            return RunResult(stamp, out_dir, summary, "empty")
        emit("pull", f"pulled {so_lines['so_id'].nunique()} orders → "
                     f"{len(so_lines)} lines", level="ok")

        # 2. snapshot
        snap = _build_snapshot(so_lines, raw_dir)
        emit("snapshot", "snapshot built (live SO + latest PO/products)", level="ok")

        # 3. dims
        dim_path = settings.dims_path or _latest_file(
            repo_root / "data" / "dims", "dims_*.xlsx")
        if not dim_path or not dim_path.exists():
            raise FileNotFoundError("no dim file in data/dims/")
        dims = load_dimensions(dim_path)
        emit("dims", f"dims {int(dims['measurement_complete'].sum())}/"
                     f"{len(dims)} SKUs measured", level="ok")

        # 4. routing
        rules_path = settings.rules_path or _latest_file(
            repo_root / "data" / "routing", "consignee_rules*.csv")
        rules = load_consignee_rules(rules_path)
        raw_vel = compute_velocity(snap)
        apply_tags(raw_vel.sku_metrics, dims)
        full_pallet = run_full_pallet_analysis(
            snap, dims, raw_vel.sku_metrics, ratio=settings.pallet_ratio)
        metrics = compute_order_metrics(snap, dims, full_pallet)

        # 4b. link dispatch-predicted runs onto the per-order frame so we can
        # group by run and route flagged orders to the pallet stream.
        plan_dir = settings.dispatch_plan_dir or find_latest_dispatch_plan(
            repo_root)
        if plan_dir is not None and plan_dir.exists():
            link = load_dispatch_link(plan_dir)
            metrics.per_order = attach_dispatch_runs(metrics.per_order, link)
            emit("route", f"linked runs from dispatch plan {plan_dir.name} "
                          f"({len(link)} mapped orders)", level="ok")
        elif settings.run_group_col == "predicted_run":
            raise CartonCloudError(
                "no dispatch plan found (run build_dispatch first) — refusing "
                "to wave by predicted_run without run grouping")
        else:
            # delivery_state grouping without a plan: no flags available.
            metrics.per_order["dispatch_flag"] = "no_plan"

        emit("route", f"{metrics.n_orders:,} orders "
                      f"({metrics.n_orders_with_dims} full dim coverage)", level="ok")

        # 5. classify
        classification = classify_streams(
            metrics, rules,
            pallet_fraction_threshold=settings.pallet_fraction_threshold)
        emit("classify", "streams classified: " + ", ".join(
            f"{k}={int(v)}" for k, v in classification.counts_by_stream.items()),
            level="ok")

        # 6. live SKU -> location from stock-on-hand (mandatory, fresh).
        emit("locations", "pulling live stock-on-hand for SKU locations…")
        codes = sorted({c for c in so_lines["product_code"].dropna().unique()})
        soh_customer_id = (so_lines.iloc[0]["customer_id"]
                           if "customer_id" in so_lines.columns and len(so_lines)
                           else None)
        if not soh_customer_id:
            raise CartonCloudError(
                "cannot resolve customer_id for SOH pull — no live stock "
                "locations available; refusing to wave from stale data")
        items = get_sku_locations(
            client, customer_id=soh_customer_id, product_codes=codes)
        sku_locations = build_sku_locations_from_soh(items)
        if sku_locations.empty:
            raise CartonCloudError(
                "live SOH returned no SKU locations — refusing to generate a "
                "wave with nothing placed")
        emit("locations",
             f"live SOH resolved {len(sku_locations)} SKU locations "
             f"({len(items)} stock rows)", level="ok")

        # 7. wave generation
        emit("generate", "generating wave pick sheets…")
        result = generate_wave_pick_sheets(
            classification=classification, so_lines=snap.so_lines,
            sku_locations=sku_locations,
            run_group_col=settings.run_group_col,
            early_release_cartons=settings.early_release_cartons,
            include_immediate_streams=settings.include_pallet_sheets)
        emit("generate",
             f"{result.summary['n_waves']} waves, "
             f"{result.summary['n_orders_total']} orders, "
             f"{result.summary['n_lines_unallocated']} unallocated lines, "
             f"{result.summary['n_orders_skipped']} skipped", level="ok")

        # 8. write outputs
        logo_path = (settings.logo_path
                     if settings.logo_path and Path(settings.logo_path).exists()
                     else None)
        for sheet in result.sheets:
            wave_dir = out_dir / sheet.wave_id
            wave_dir.mkdir(parents=True, exist_ok=True)
            try:
                generate_wave_pdf(
                    sheet, wave_dir / f"{sheet.wave_id}_picksheet.pdf",
                    logo_path=logo_path, lines_per_hour=settings.lines_per_hour)
            except Exception as exc:  # noqa: BLE001
                emit("write", f"PDF failed for {sheet.wave_id}: "
                              f"{type(exc).__name__}: {exc}", level="info")
                continue
            write_wave_csvs(sheet, wave_dir)

        if not result.skipped_orders.empty:
            result.skipped_orders.to_csv(out_dir / "skipped_orders.csv", index=False)

        # 9. index + manifest
        measured = set(
            dims.loc[dims["measurement_complete"] == True, "product_code"]  # noqa: E712
            .astype(str)
        )
        order_skus = set(snap.so_lines["product_code"].dropna().astype(str))
        skus_to_measure = sorted(order_skus - measured)
        _build_index_md(out_dir, result.sheets, result.skipped_orders,
                        _settings_dict(settings, audit_path, plan_dir),
                        skus_to_measure=skus_to_measure)
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "settings": _settings_dict(settings, audit_path, plan_dir),
            "summary": result.summary,
            "waves": [
                {"wave_id": s.wave_id, "stream": s.stream,
                 "run_group": s.run_group,
                 "receive_date": s.receive_date.isoformat() if s.receive_date else None,
                 "total_cartons": s.total_cartons, "total_lines": s.total_lines,
                 "n_orders": len(s.orders),
                 "estimated_walk_m": s.estimated_walk_distance_m}
                for s in result.sheets],
            "skus_to_measure": skus_to_measure,
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        emit("done", f"Done — {result.summary['n_waves']} waves written.",
             level="ok", **result.summary)
        return RunResult(stamp, out_dir, result.summary, "success")

    except Exception as exc:  # noqa: BLE001
        log.exception("wave generation failed")
        emit("done", f"Run failed: {type(exc).__name__}: {exc}", level="error")
        return RunResult(stamp, out_dir, {}, "failed", error=str(exc))
