"""Read wave run outputs from disk for the console viewer.

The run folder is the source of truth — manifest.json carries the
summary + per-wave stats, and per-wave CSVs carry the detail. No state
is held between requests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _waves_base(repo_root: Path) -> Path:
    return repo_root / "data" / "processed" / "waves"


def list_runs(base: Path) -> list[dict]:
    """Newest-first list of run summaries. ``base`` is the waves dir."""
    runs = []
    if not base.exists():
        return runs
    for run_dir in sorted(base.iterdir(), reverse=True):
        manifest = run_dir / "manifest.json"
        if not run_dir.is_dir() or not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        s = m.get("summary", {})
        runs.append({
            "run_id": run_dir.name,
            "generated_at": m.get("generated_at", ""),
            "n_waves": s.get("n_waves", 0),
            "n_orders": s.get("n_orders_total", 0),
            "n_skipped": s.get("n_orders_skipped", 0),
            "n_lines_unallocated": s.get("n_lines_unallocated", 0),
            "n_skus_unallocated": s.get("n_skus_unallocated", 0),
            "n_lines_carton_pick": s.get("n_lines_carton_pick", 0),
            "n_carton_picks_no_reserve": s.get("n_carton_picks_no_reserve", 0),
            "settings": m.get("settings", {}),
        })
    return runs


def get_run(base: Path, run_id: str) -> dict:
    """Full manifest for one run + parsed skipped_orders."""
    run_dir = base / run_id
    m = json.loads((run_dir / "manifest.json").read_text())
    skipped = []
    skipped_csv = run_dir / "skipped_orders.csv"
    if skipped_csv.exists():
        skipped = pd.read_csv(skipped_csv).fillna("").to_dict("records")
    m["run_id"] = run_id
    m["skipped"] = skipped
    return m


def get_wave(base: Path, run_id: str, wave_id: str) -> dict:
    """Pick lines + orders for one wave, read from its CSVs."""
    wave_dir = base / run_id / wave_id
    picks_csv = wave_dir / f"{wave_id}_picks.csv"
    orders_csv = wave_dir / f"{wave_id}_orders.csv"
    picks = (pd.read_csv(picks_csv).fillna("").to_dict("records")
             if picks_csv.exists() else [])
    orders = (pd.read_csv(orders_csv).fillna("").to_dict("records")
              if orders_csv.exists() else [])
    return {"run_id": run_id, "wave_id": wave_id,
            "pick_lines": picks, "orders": orders}


def file_path(base: Path, run_id: str, wave_id: str, name: str) -> Path:
    """Validated path to a downloadable wave file (guards traversal)."""
    wave_dir = (base / run_id / wave_id).resolve()
    target = (wave_dir / name).resolve()
    if not str(target).startswith(str(wave_dir) + "/"):
        raise ValueError("path traversal rejected")
    if not target.exists():
        raise FileNotFoundError(name)
    return target
