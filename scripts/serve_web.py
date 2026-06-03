#!/usr/bin/env python3
"""Launch the Go Cold wave pick console.

    python scripts/serve_web.py            # http://127.0.0.1:8000
    python scripts/serve_web.py --host 0.0.0.0 --port 8080

Binds 127.0.0.1 by default (single-operator NUC). Read-only against CC.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import uvicorn  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    uvicorn.run("web.app:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
