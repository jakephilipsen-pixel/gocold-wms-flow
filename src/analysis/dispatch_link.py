"""Bridge dispatch run-prediction into the wave pipeline.

The dispatch builder (scripts/build_dispatch.py / src/dispatch) writes a plan
per run to ``data/processed/dispatch/<stamp>/`` with:

  * ``suggested_runs.csv`` - own-fleet assignments
    (columns: so_ref, so_id, predicted_run, confidence, flag)
  * ``review.csv`` - low-confidence orders needing dispatcher attention
    (same columns; flag in {mixed, new_address, stale, no_address})

We load both, key by ``so_id``, and attach ``predicted_run`` + ``dispatch_flag``
onto the per-order frame so wave generation can group by run and route flagged
orders to the pallet stream. Read-only: we only read CSVs the dispatch step
already wrote; we never touch CartonCloud.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Dispatch flags meaning "don't trust the run - build it to a pallet".
# ``no_run`` is our own sentinel for orders absent from the dispatch plan.
FLAGGED_DISPATCH = frozenset(
    {"mixed", "new_address", "stale", "no_address", "no_run"}
)

_LINK_COLS = ["so_id", "predicted_run", "dispatch_flag", "confidence"]


def find_latest_dispatch_plan(repo_root: Path) -> Path | None:
    """Return the most recent ``data/processed/dispatch/<stamp>/`` dir.

    Only considers dirs that actually contain a ``suggested_runs.csv`` (a
    half-written plan dir is ignored). Returns ``None`` when there is none.
    """
    base = Path(repo_root) / "data" / "processed" / "dispatch"
    if not base.exists():
        return None
    candidates = sorted(
        (d for d in base.iterdir()
         if d.is_dir() and (d / "suggested_runs.csv").exists()),
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def load_dispatch_link(plan_dir: Path) -> pd.DataFrame:
    """Load ``suggested_runs.csv`` + ``review.csv`` into one so_id->run frame.

    Returns columns: ``so_id, predicted_run, dispatch_flag, confidence``.
    Suggested (own-fleet) rows take precedence over review rows if an id
    appears in both. Returns an empty frame (correct columns) if neither file
    exists or both are empty.
    """
    plan_dir = Path(plan_dir)
    frames: list[pd.DataFrame] = []
    for name in ("suggested_runs.csv", "review.csv"):
        path = plan_dir / name
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if df.empty:
            continue
        df = df.rename(columns={"flag": "dispatch_flag"})
        for col in _LINK_COLS:
            if col not in df.columns:
                df[col] = pd.NA
        df = df.dropna(subset=["so_id"])
        if df.empty:
            continue
        df["so_id"] = df["so_id"].astype(str)
        frames.append(df[_LINK_COLS])
    if not frames:
        log.warning("no dispatch data found in %s", plan_dir)
        return pd.DataFrame(columns=_LINK_COLS)
    link = pd.concat(frames, ignore_index=True)
    link = link.drop_duplicates("so_id", keep="first").reset_index(drop=True)
    log.info("loaded %d mapped orders from dispatch plan %s", len(link), plan_dir.name)
    return link


def attach_dispatch_runs(
    per_order: pd.DataFrame, link: pd.DataFrame
) -> pd.DataFrame:
    """Add ``predicted_run`` + ``dispatch_flag`` columns to a per-order frame.

    Orders absent from the dispatch plan (or when the link is empty) get
    ``predicted_run="no_run"`` and ``dispatch_flag="no_run"`` so they group
    under a ``no_run`` bucket and route to the pallet stream — never dropped.
    """
    out = per_order.copy()
    out = out.drop(columns=["predicted_run", "dispatch_flag"], errors="ignore")
    out["so_id"] = out["so_id"].astype(str)
    if link is None or link.empty:
        out["predicted_run"] = "no_run"
        out["dispatch_flag"] = "no_run"
        return out
    out = out.merge(link, on="so_id", how="left")
    out["predicted_run"] = out["predicted_run"].fillna("no_run")
    out["dispatch_flag"] = out["dispatch_flag"].fillna("no_run")
    return out
