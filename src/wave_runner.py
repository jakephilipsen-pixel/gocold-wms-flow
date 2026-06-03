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
import sys
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
    classify_streams,
    compute_order_metrics,
    compute_velocity,
    generate_wave_pick_sheets,
    load_consignee_rules,
    load_dimensions,
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
from locations import load_cc_locations
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
    run_group_col: str = "delivery_state"
    soh_fallback: bool = False
    lines_per_hour: int = DEFAULT_LINES_PER_HOUR
    pallet_ratio: float = DEFAULT_FULL_PALLET_RATIO
    # Optional explicit paths; None = resolve from repo_root at run time.
    raw_dir: Path | None = None
    dims_path: Path | None = None
    locations_path: Path | None = None
    rules_path: Path | None = None
    assignments_path: Path | None = None
    logo_path: Path | None = None
    out_dir: Path | None = None


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
# Lazy loader for the SO line flattener that lives in scripts/extract.py.
# scripts/ is not a package so we load by file path and cache the result.
# ---------------------------------------------------------------------------

_flatten_cache: dict = {}


def _get_flatten_fn(repo_root: Path):
    """Lazily load _flatten_outbound_order_lines from scripts/extract.py."""
    if "fn" not in _flatten_cache:
        extract_path = repo_root / "scripts" / "extract.py"
        spec = importlib.util.spec_from_file_location("_extract_mod", extract_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _flatten_cache["fn"] = mod._flatten_outbound_order_lines
    return _flatten_cache["fn"]


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


def _latest_assignments(processed_dir: Path) -> Path | None:
    """Find the most recently written assignments.csv across assign_* dirs."""
    candidates = sorted(
        processed_dir.glob("assign_*/assignments.csv"),
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
        raise SystemExit(f"CC pull failed: {exc}") from exc

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
    args,
) -> None:
    """Top-level index.md summarising every wave in this run."""
    lines = [
        "# Wave Pick Run",
        f"_Generated: {datetime.now():%Y-%m-%d %H:%M}_",
        "",
        "## Settings",
        f"- Status filter: `{args.status}`",
        f"- Customer filter: `{args.customer_name or '(none)'}`",
        f"- pallet_fraction_threshold: {args.pallet_fraction_threshold:.2f}",
        f"- early_release_cartons: {args.early_release_cartons}",
        f"- run_group_col: `{args.run_group_col}`",
        f"- Pick rate assumption: {args.lines_per_hour} lines/hour",
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
            "These orders were dropped from waves because we couldn't "
            "resolve a pick location for one or more SKUs. Run "
            "`scripts/assign.py` once dims are captured, or add the SKU "
            "to CC stock-on-hand at the correct location.",
            "",
            "| Wave | SO ref | Reason | Missing SKUs |",
            "|---|---|---|---|",
        ])
        for r in skipped.itertuples(index=False):
            lines.append(
                f"| `{r.wave_id}` | {r.so_ref} | {r.reason} | "
                f"{r.missing_skus} |"
            )

    (out_dir / "index.md").write_text("\n".join(lines))
