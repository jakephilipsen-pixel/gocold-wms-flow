#!/usr/bin/env python3
"""Weekday-peak wave watcher — fire the wave pipeline once volume is real.

Why this exists
---------------
``generate_waves.py`` only waves the SOs that are open *right now*, and it
groups them by the predicted delivery run from the latest dispatch plan. To
actually *see* multiple run groups you need genuine peak volume — on a quiet
morning (or a public holiday) there's one order and one run group.

This watcher polls the open-order count from a start time, and the moment
volume crosses a threshold (or a hard deadline passes), it builds a FRESH
dispatch plan and generates waves, then reports how many distinct run groups
landed across the waves. A fresh plan is mandatory: the plan predicts the
orders open *at build time*, so we build it at peak, not before.

House style: this is a fixed event-driven pipeline, not an agent loop. It
shells out to the already-validated ``build_dispatch.py`` and
``generate_waves.py`` entrypoints. Read-only against CartonCloud — it only
generates paperwork; no CC writes, ever.

Usage
-----
    # default: poll every 15 min, trigger at >=15 open orders,
    # hard deadline 11:30 today (local), report needs >=3 run groups
    python scripts/peak_wave_watch.py --deadline 2026-06-09T11:30:00+10:00

    # tune
    python scripts/peak_wave_watch.py \
        --order-threshold 20 --poll-secs 1200 \
        --deadline 2026-06-09T11:30:00+10:00 --min-runs 3
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import json
import datetime as dt
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (mirrors smoke_test.py) — no extra dep."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _log(msg: str) -> None:
    stamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{stamp}] {msg}", flush=True)


def _count_open_orders(status: str, customer_name: str | None) -> int:
    """Cheap poll: how many SOs sit in ``status`` right now. Read-only."""
    from cc_client import CartonCloudClient
    from cc_client.queries import search_outbound_orders

    client = CartonCloudClient.from_env()
    n = 0
    for _ in search_outbound_orders(
        client, status=[status], customer_name=customer_name, page_size=100
    ):
        n += 1
    return n


def _run(script: str, extra: list[str] | None = None) -> int:
    """Run a project script with the SAME interpreter; stream its output."""
    cmd = [sys.executable, "-u", str(REPO_ROOT / "scripts" / script), *(extra or [])]
    _log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def _latest_waves_dir() -> Path | None:
    base = REPO_ROOT / "data" / "processed" / "waves"
    if not base.exists():
        return None
    dirs = [d for d in base.iterdir() if d.is_dir() and (d / "manifest.json").exists()]
    return max(dirs, key=lambda d: d.name) if dirs else None


def _report(min_runs: int) -> dict:
    """Summarise the newest wave run: run-group count, streams, skipped."""
    wd = _latest_waves_dir()
    if wd is None:
        return {"ok": False, "error": "no waves dir produced"}
    m = json.loads((wd / "manifest.json").read_text())
    waves = m.get("waves", [])
    run_groups = sorted({str(w.get("run_group", "")) for w in waves if w.get("run_group")})
    per_stream: dict[str, int] = {}
    for w in waves:
        per_stream[w.get("stream", "?")] = per_stream.get(w.get("stream", "?"), 0) + 1
    summ = m.get("summary", {})
    return {
        "ok": True,
        "run_dir": str(wd),
        "run_id": wd.name,
        "n_waves": summ.get("n_waves", len(waves)),
        "n_orders": summ.get("n_orders_total"),
        "n_run_groups": len(run_groups),
        "run_groups": run_groups,
        "waves_per_stream": per_stream,
        "n_orders_skipped": summ.get("n_orders_skipped"),
        "n_lines_unallocated": summ.get("n_lines_unallocated"),
        "multiple_run_groups": len(run_groups) >= min_runs,
        "console_url": f"http://127.0.0.1:8077/runs/{wd.name}",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--status", default="AWAITING_PICK_AND_PACK")
    p.add_argument("--customer-name", default=None)
    p.add_argument("--order-threshold", type=int, default=15,
                   help="trigger once this many SOs are open (default 15)")
    p.add_argument("--poll-secs", type=int, default=900,
                   help="seconds between polls (default 900 = 15 min)")
    p.add_argument("--deadline", required=True,
                   help="ISO 8601 local time; trigger no later than this even "
                        "if volume stays low (e.g. 2026-06-09T11:30:00+10:00)")
    p.add_argument("--min-runs", type=int, default=3,
                   help="run groups needed to call the test PASS (default 3)")
    p.add_argument("--history-days", type=int, default=90,
                   help="passed through to build_dispatch (default 90)")
    args = p.parse_args()

    _load_dotenv(REPO_ROOT / ".env")
    missing = [v for v in ("CC_CLIENT_ID", "CC_CLIENT_SECRET", "CC_TENANT_ID")
               if not os.environ.get(v)]
    if missing:
        _log(f"FATAL missing env vars: {', '.join(missing)}")
        return 2

    try:
        deadline = dt.datetime.fromisoformat(args.deadline)
    except ValueError as e:
        _log(f"FATAL bad --deadline {args.deadline!r}: {e}")
        return 2
    if deadline.tzinfo is None:
        deadline = deadline.astimezone()

    _log(f"watcher up. status={args.status} threshold={args.order_threshold} "
         f"poll={args.poll_secs}s deadline={deadline.isoformat()} "
         f"min_runs={args.min_runs}")

    triggered = False
    while True:
        now = dt.datetime.now().astimezone()
        past_deadline = now >= deadline
        try:
            n = _count_open_orders(args.status, args.customer_name)
            _log(f"poll: {n} open order(s) in {args.status}")
        except Exception as e:  # noqa: BLE001 — keep watching through transient errors
            _log(f"poll error (will retry): {e!r}")
            n = -1

        if n >= args.order_threshold or past_deadline:
            reason = ("threshold" if n >= args.order_threshold
                      else "deadline (volume stayed low)")
            _log(f"TRIGGER ({reason}); n={n}")
            triggered = True
            break

        sleep_for = args.poll_secs
        if now + dt.timedelta(seconds=sleep_for) > deadline:
            sleep_for = max(30, int((deadline - now).total_seconds()))
        _log(f"below threshold; sleeping {sleep_for}s")
        time.sleep(sleep_for)

    if not triggered:
        return 1

    _log("building fresh dispatch plan (build_dispatch.py, ~10 min)…")
    rc = _run("build_dispatch.py", ["--history-days", str(args.history_days)])
    if rc != 0:
        _log(f"build_dispatch FAILED rc={rc}; aborting")
        return rc

    _log("generating waves (generate_waves.py)…")
    rc = _run("generate_waves.py",
              ["--customer-name", args.customer_name] if args.customer_name else None)
    if rc != 0:
        _log(f"generate_waves FAILED rc={rc}; aborting")
        return rc

    rep = _report(args.min_runs)
    _log("=== REPORT ===")
    print(json.dumps(rep, indent=2), flush=True)
    if rep.get("ok") and rep.get("multiple_run_groups"):
        _log(f"PASS: {rep['n_run_groups']} distinct run groups across "
             f"{rep['n_waves']} waves → {rep['console_url']}")
        return 0
    if rep.get("ok"):
        _log(f"DONE but only {rep['n_run_groups']} run group(s) "
             f"(< {args.min_runs}); volume may still have been thin → "
             f"{rep.get('console_url')}")
        return 0
    _log(f"FAILED to produce a report: {rep.get('error')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
