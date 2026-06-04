"""Dispatch run build core — learn → predict → write, with progress events.

READ-ONLY against CartonCloud. Shared by the CLI (scripts/build_dispatch.py)
and the web console (src/web_dispatch). Mirrors wave_runner: a settings
dataclass in, progress events + a result out. ``run_dispatch`` is the pure
learn-or-load-then-predict step; ``run_dispatch_job`` adds env loading, the
file write, progress reporting, and a structured result.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from cc_client import (
    CartonCloudClient,
    search_consignments,
    search_outbound_orders,
)

from .consignments import parse_consignment
from .history import compute_run_history, load_model, save_model
from .predict import DispatchPlan, predict_runs
from .sinks import FileSink
from .zones import load_zone_config

log = logging.getLogger(__name__)

DEFAULT_STATUS = ["AWAITING_PICK_AND_PACK", "PACKED"]


@dataclass
class DispatchRunSettings:
    """Everything ``run_dispatch_job`` needs for one build.

    ``repo_root`` anchors output (``data/processed/dispatch/<stamp>/``) and the
    model cache. ``zones_path`` / ``model_path`` override the repo-relative
    defaults (tests point ``zones_path`` at the real config while writing
    output to a tmp dir).
    """
    repo_root: Path
    history_days: int = 90
    skip_learn: bool = False
    zones_path: Path | None = None
    model_path: Path | None = None

    def resolved_zones_path(self) -> Path:
        return self.zones_path or self.repo_root / "config" / "dispatch_zones.toml"

    def resolved_model_path(self) -> Path:
        return (self.model_path
                or self.repo_root / "data" / "dispatch" / "run_history.parquet")


@dataclass
class DispatchProgressEvent:
    """One streamed progress line."""
    stage: str            # learn | predict | write | done
    message: str
    level: str = "info"   # info | ok | error
    data: dict = field(default_factory=dict)


@dataclass
class DispatchRunResult:
    """Outcome of a single ``run_dispatch_job`` call."""
    stamp: str
    out_dir: Path | None
    counts: dict          # assignments / carriers / review / runs
    status: str           # success | empty | failed
    error: str | None = None


ProgressCallback = Callable[[DispatchProgressEvent], None]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _open_order_stops(client) -> list[dict]:
    """Pull open orders and reduce to {so_id, so_ref, address}."""
    stops = []
    for o in search_outbound_orders(client, status=DEFAULT_STATUS):
        addr = ((o.get("details") or {}).get("deliver") or {}).get("address")
        stops.append({"so_id": o.get("id"),
                      "so_ref": (o.get("references") or {}).get("customer"),
                      "address": addr})
    return stops


def run_dispatch(*, client, zones_path: Path, history_days: int,
                 as_of: date | None = None, model_path: Path | None = None,
                 skip_learn: bool = False) -> DispatchPlan:
    """Learn (or load) the model, pull open orders, predict. Returns the plan."""
    as_of = as_of or date.today()
    if skip_learn and model_path and model_path.exists():
        model = load_model(model_path)
        log.info("loaded cached model from %s", model_path)
    else:
        cutoff = (as_of - timedelta(days=history_days)).isoformat()
        records = [parse_consignment(c)
                   for c in search_consignments(client, run_sheet_date_from=cutoff)]
        model = compute_run_history(records, as_of=as_of,
                                    window_days=history_days)
        if model_path:
            save_model(model, model_path)
            log.info("cached model → %s", model_path)

    zones = load_zone_config(zones_path)
    stops = _open_order_stops(client)
    return predict_runs(stops, model, zones, as_of=as_of)


def run_dispatch_job(
    settings: DispatchRunSettings,
    emit: ProgressCallback,
    *,
    write: bool = True,
    as_of: date | None = None,
) -> DispatchRunResult:
    """Full build: learn → predict → (optionally) write. READ-ONLY against CC.

    Emits coarse progress events and returns a structured result. ``write=False``
    is the CLI --dry-run path (no files). On error, emits an error ``done``
    event and returns ``status="failed"`` rather than raising, so a web worker
    can record it cleanly.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    counts = {"assignments": 0, "carriers": 0, "review": 0, "runs": 0}
    try:
        _load_dotenv(settings.repo_root / ".env")
        emit(DispatchProgressEvent(
            "learn",
            f"Building predictions from {settings.history_days}d of "
            f"consignment history…"))
        client = CartonCloudClient.from_env()       # write_enabled=False
        plan = run_dispatch(
            client=client,
            zones_path=settings.resolved_zones_path(),
            history_days=settings.history_days,
            model_path=settings.resolved_model_path(),
            skip_learn=settings.skip_learn,
            as_of=as_of)

        counts = {
            "assignments": len(plan.assignments),
            "carriers": sum(len(v) for v in plan.carriers.values()),
            "review": len(plan.review),
            "runs": len({a.predicted_run for a in plan.assignments}),
        }
        emit(DispatchProgressEvent(
            "predict",
            f"Predicted {counts['assignments']} stable across "
            f"{counts['runs']} runs · {counts['review']} review · "
            f"{counts['carriers']} carrier", "ok", counts))

        out_dir: Path | None = None
        if write:
            out_dir = (settings.repo_root / "data" / "processed" / "dispatch"
                       / stamp)
            FileSink(out_dir).apply(plan)
            emit(DispatchProgressEvent(
                "write", f"Wrote plan {stamp}", "ok", {"stamp": stamp}))

        status = ("success"
                  if any(counts[k] for k in ("assignments", "review", "carriers"))
                  else "empty")
        emit(DispatchProgressEvent(
            "done",
            f"Done — {counts['assignments']} assigned, "
            f"{counts['review']} to review", "ok", {"stamp": stamp}))
        return DispatchRunResult(stamp, out_dir, counts, status)
    except Exception as exc:  # noqa: BLE001 — report, don't crash the worker
        log.exception("dispatch build failed")
        emit(DispatchProgressEvent("done", f"Build failed: {exc}", "error"))
        return DispatchRunResult(stamp, None, counts, "failed", str(exc))
