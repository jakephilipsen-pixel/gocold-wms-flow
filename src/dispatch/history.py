"""Recency-weighted address→run history model."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunCandidate:
    run: str
    score: float          # recency-weighted sum of consignments
    n: int                # raw consignment count for this (address, run)
    last_seen: date | None


@dataclass(frozen=True)
class RunHistoryModel:
    by_address: dict[str, list[RunCandidate]]   # sorted best-first
    window_days: int
    half_life_days: int
    generated_at: datetime


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def compute_run_history(
    records: list[dict[str, Any]],
    *,
    as_of: date | None = None,
    window_days: int = 90,
    half_life_days: int = 30,
) -> RunHistoryModel:
    """Aggregate consignment records into per-address run candidates.

    Each record needs ``address_key``, ``run`` and ``run_date`` (ISO str).
    Weight per consignment = 0.5 ** (age_days / half_life_days), so recent
    runs dominate. Records with no key or no run are skipped.
    """
    as_of = as_of or date.today()
    # (address_key, run) -> {"score", "n", "last_seen"}
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in records:
        key = rec.get("address_key") or ""
        run = rec.get("run") or ""
        if not key or not run:
            continue
        d = _parse_date(rec.get("run_date")) or as_of
        age = max((as_of - d).days, 0)
        weight = 0.5 ** (age / half_life_days)
        slot = acc.setdefault((key, run), {"score": 0.0, "n": 0, "last_seen": d})
        slot["score"] += weight
        slot["n"] += 1
        if slot["last_seen"] is None or d > slot["last_seen"]:
            slot["last_seen"] = d

    by_address: dict[str, list[RunCandidate]] = {}
    for (key, run), v in acc.items():
        by_address.setdefault(key, []).append(
            RunCandidate(run=run, score=v["score"], n=v["n"],
                         last_seen=v["last_seen"])
        )
    for key in by_address:
        by_address[key].sort(key=lambda c: c.score, reverse=True)

    log.info("history model: %d addresses, %d (address,run) pairs",
             len(by_address), len(acc))
    return RunHistoryModel(
        by_address=by_address, window_days=window_days,
        half_life_days=half_life_days,
        generated_at=datetime.now(),
    )


def save_model(model: RunHistoryModel, path: Path) -> None:
    """Persist the model to parquet (one row per address/run candidate)."""
    rows = [
        {"address_key": key, "run": c.run, "score": c.score, "n": c.n,
         "last_seen": c.last_seen.isoformat() if c.last_seen else None}
        for key, cands in model.by_address.items() for c in cands
    ]
    df = pd.DataFrame(rows, columns=["address_key", "run", "score", "n",
                                     "last_seen"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_model(path: Path) -> RunHistoryModel:
    """Rebuild a model from a parquet written by save_model."""
    df = pd.read_parquet(path)
    by_address: dict[str, list[RunCandidate]] = {}
    for row in df.itertuples(index=False):
        by_address.setdefault(row.address_key, []).append(
            RunCandidate(run=row.run, score=float(row.score), n=int(row.n),
                         last_seen=_parse_date(row.last_seen))
        )
    for key in by_address:
        by_address[key].sort(key=lambda c: c.score, reverse=True)
    return RunHistoryModel(by_address=by_address, window_days=0,
                           half_life_days=0, generated_at=datetime.now())
