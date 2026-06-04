"""Build today's dispatch run predictions from CC consignment history.

READ-ONLY. learn → predict → write files. CartonCloud is never mutated.
Delegates to dispatch.runner.run_dispatch_job (shared with the web console).

    python3 scripts/build_dispatch.py                 # learn + predict + write
    python3 scripts/build_dispatch.py --skip-learn    # reuse cached model
    python3 scripts/build_dispatch.py --history-days 90
    python3 scripts/build_dispatch.py --dry-run       # summary only, no files
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dispatch.runner import (  # noqa: E402
    DispatchRunSettings,
    run_dispatch_job,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history-days", type=int, default=90)
    ap.add_argument("--skip-learn", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zones-config", type=Path, default=None)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    settings = DispatchRunSettings(
        repo_root=ROOT, history_days=args.history_days,
        skip_learn=args.skip_learn, zones_path=args.zones_config)

    def emit(e) -> None:
        print(f"[{e.level}] {e.message}")

    result = run_dispatch_job(settings, emit, write=not args.dry_run)
    print(f"status={result.status} assignments={result.counts['assignments']} "
          f"carriers={result.counts['carriers']} review={result.counts['review']}")
    if args.dry_run:
        print("(dry run — no files written)")
    elif result.out_dir is not None:
        print(f"wrote → {result.out_dir}")
    return 0 if result.status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
