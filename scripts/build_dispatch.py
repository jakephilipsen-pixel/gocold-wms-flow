"""Build today's dispatch run predictions from CC consignment history.

READ-ONLY. learn → predict → write files. CartonCloud is never mutated.

    python3 scripts/build_dispatch.py                 # learn + predict
    python3 scripts/build_dispatch.py --skip-learn    # reuse cached model
    python3 scripts/build_dispatch.py --history-days 90
    python3 scripts/build_dispatch.py --dry-run       # summary only, no files
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cc_client import (  # noqa: E402
    CartonCloudClient,
    search_consignments,
    search_outbound_orders,
)
from dispatch.consignments import parse_consignment  # noqa: E402
from dispatch.history import (  # noqa: E402
    compute_run_history,
    load_model,
    save_model,
)
from dispatch.predict import DispatchPlan, predict_runs  # noqa: E402
from dispatch.sinks import FileSink  # noqa: E402
from dispatch.zones import load_zone_config  # noqa: E402

log = logging.getLogger("build_dispatch")

DEFAULT_STATUS = ["AWAITING_PICK_AND_PACK", "PACKED"]
_MODEL_DIR = ROOT / "data" / "dispatch"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    import os
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history-days", type=int, default=90)
    ap.add_argument("--skip-learn", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zones-config", type=Path,
                    default=ROOT / "config" / "dispatch_zones.toml")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    _load_dotenv(ROOT / ".env")
    client = CartonCloudClient.from_env()   # write_enabled=False
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = _MODEL_DIR / "run_history.parquet"

    plan = run_dispatch(client=client, zones_path=args.zones_config,
                        history_days=args.history_days,
                        model_path=model_path, skip_learn=args.skip_learn)

    print(f"assignments={len(plan.assignments)} "
          f"carriers={sum(len(v) for v in plan.carriers.values())} "
          f"review={len(plan.review)}")

    if args.dry_run:
        print("(dry run — no files written)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "processed" / "dispatch" / stamp
    FileSink(out_dir).apply(plan)
    print(f"wrote → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
