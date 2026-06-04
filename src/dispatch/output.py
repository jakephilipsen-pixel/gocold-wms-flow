"""Write a DispatchPlan to operator-facing files."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from .predict import DispatchPlan, RunAssignment

log = logging.getLogger(__name__)

_ASSIGN_COLS = ["so_ref", "so_id", "predicted_run", "confidence", "flag",
                "reason", "alternatives", "full_address", "street", "suburb",
                "state", "postcode"]


def _rows(items: list[RunAssignment]) -> list[dict]:
    out = []
    for a in items:
        out.append({
            "so_ref": a.so_ref, "so_id": a.so_id,
            "predicted_run": a.predicted_run,
            "confidence": round(a.confidence, 3), "flag": a.flag,
            "reason": a.reason, "alternatives": ", ".join(a.alternatives),
            "full_address": a.address.get("full_address", ""),
            "street": a.address.get("street", ""),
            "suburb": a.address.get("suburb", ""),
            "state": a.address.get("state", ""),
            "postcode": a.address.get("postcode", ""),
        })
    return out


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "unnamed"


def write_dispatch_plan(plan: DispatchPlan, out_dir: Path) -> None:
    """Write suggested_runs.csv, per-run xlsx, carrier CSVs, review.csv, summary."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    assign_df = pd.DataFrame(_rows(plan.assignments), columns=_ASSIGN_COLS)
    assign_df.to_csv(out_dir / "suggested_runs.csv", index=False)

    review_df = pd.DataFrame(_rows(plan.review), columns=_ASSIGN_COLS)
    review_df.to_csv(out_dir / "review.csv", index=False)

    for carrier, items in plan.carriers.items():
        pd.DataFrame(_rows(items), columns=_ASSIGN_COLS).to_csv(
            out_dir / f"carriers_{_safe(carrier)}.csv", index=False)

    # One manifest per predicted run (own-fleet assignments only).
    if not assign_df.empty:
        for run, g in assign_df.groupby("predicted_run", sort=True):
            g.sort_values("postcode").to_excel(
                out_dir / f"run_{_safe(str(run))}.xlsx",
                index=False, sheet_name="run")

    n_runs = assign_df["predicted_run"].nunique() if not assign_df.empty else 0
    n_carrier = sum(len(v) for v in plan.carriers.values())
    summary = [
        "# Dispatch run prediction summary", "",
        f"- Own-fleet assignments: {len(plan.assignments)} across {n_runs} runs",
        f"- Carrier orders: {n_carrier} across {len(plan.carriers)} carriers",
        f"- **Review queue: {len(plan.review)}**"
        + ("  ← needs dispatcher attention" if plan.review else ""),
        "",
    ]
    if not assign_df.empty:
        summary.append("## Assignments per run")
        for run, g in assign_df.groupby("predicted_run", sort=True):
            summary.append(f"- {run}: {len(g)} stops")
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n")
    log.info("wrote dispatch outputs to %s", out_dir)
