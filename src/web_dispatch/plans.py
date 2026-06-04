"""Read dispatch plan outputs from disk for the console viewer.

A plan is one ``data/processed/dispatch/<stamp>/`` directory written by
dispatch.output.write_dispatch_plan. No state is held between requests — the
directory is the source of truth.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

_SUGGESTED = "suggested_runs.csv"
_REVIEW = "review.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a plan CSV as strings (keeps postcode/so_id intact). Empty on miss."""
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def _stamp_to_iso(stamp: str) -> str:
    try:
        return datetime.strptime(stamp, "%Y%m%d_%H%M%S").isoformat(
            sep=" ", timespec="minutes")
    except ValueError:
        return stamp


def _n_runs(df: pd.DataFrame) -> int:
    if df.empty or "predicted_run" not in df.columns:
        return 0
    return int(df["predicted_run"].replace("", pd.NA).dropna().nunique())


def list_plans(base: Path) -> list[dict]:
    """Newest-first list of plan summaries. ``base`` is the dispatch dir."""
    plans: list[dict] = []
    if not base.exists():
        return plans
    for d in sorted(base.iterdir(), reverse=True):
        if not d.is_dir() or not (d / _SUGGESTED).exists():
            continue
        suggested = _read_csv(d / _SUGGESTED)
        review = _read_csv(d / _REVIEW)
        n_carriers = sum(len(_read_csv(c))
                         for c in d.glob("carriers_*.csv"))
        plans.append({
            "stamp": d.name,
            "generated_at": _stamp_to_iso(d.name),
            "n_assignments": int(len(suggested)),
            "n_runs": _n_runs(suggested),
            "n_review": int(len(review)),
            "n_carriers": int(n_carriers),
        })
    return plans


def get_plan(base: Path, stamp: str) -> dict:
    """Parsed plan: runs (grouped), review rows, carriers, files, summary."""
    d = base / stamp
    if not d.is_dir() or not (d / _SUGGESTED).exists():
        raise FileNotFoundError(stamp)

    suggested = _read_csv(d / _SUGGESTED)
    runs: list[dict] = []
    if not suggested.empty and "predicted_run" in suggested.columns:
        conf = pd.to_numeric(suggested["confidence"], errors="coerce")
        suggested = suggested.assign(_conf=conf)
        for run, g in suggested.groupby("predicted_run", sort=True):
            runs.append({
                "run": run,
                "n_stops": int(len(g)),
                "avg_confidence": round(float(g["_conf"].mean()), 3),
            })

    review = _read_csv(d / _REVIEW).to_dict("records")

    carriers: dict[str, list[dict]] = {}
    for c in sorted(d.glob("carriers_*.csv")):
        name = c.stem[len("carriers_"):]
        carriers[name] = _read_csv(c).to_dict("records")

    summary_md = ""
    summary_path = d / "summary.md"
    if summary_path.exists():
        summary_md = summary_path.read_text()

    files = sorted(p.name for p in d.iterdir() if p.is_file())

    return {"stamp": stamp, "runs": runs, "review": review,
            "carriers": carriers, "files": files, "summary_md": summary_md}


def get_run(base: Path, stamp: str, run: str) -> dict:
    """Stops for one predicted run, sorted by postcode."""
    d = base / stamp
    suggested = _read_csv(d / _SUGGESTED)
    stops: list[dict] = []
    if not suggested.empty and "predicted_run" in suggested.columns:
        sel = suggested[suggested["predicted_run"] == run]
        sel = sel.sort_values("postcode")
        stops = sel.to_dict("records")
    return {"stamp": stamp, "run": run, "stops": stops}


def file_path(base: Path, stamp: str, name: str) -> Path:
    """Validated path to a downloadable plan file (guards traversal)."""
    plan_dir = (base / stamp).resolve()
    target = (plan_dir / name).resolve()
    if not str(target).startswith(str(plan_dir) + "/"):
        raise ValueError("path traversal rejected")
    if not target.exists():
        raise FileNotFoundError(name)
    return target
