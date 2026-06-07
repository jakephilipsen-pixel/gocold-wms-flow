#!/usr/bin/env python3
"""Launch the Go Cold wave pick console.

    python scripts/serve_web.py            # http://127.0.0.1:8000
    python scripts/serve_web.py --host 0.0.0.0 --port 8080
    python scripts/serve_web.py --reload   # auto-restart on src/ changes

Binds 127.0.0.1 by default (single-operator NUC). Read-only against CC.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import uvicorn  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument(
        "--reload",
        action="store_true",
        help="Auto-restart on code edits. Watches src/ ONLY — never data/ — "
        "so wave-run output writes can't trigger a restart mid-pick.",
    )
    args = p.parse_args()
    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(SRC_DIR)] if args.reload else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
