"""Shared pytest setup for gocold-wms-flow.

Mirrors the scripts/ convention: put ``src/`` on ``sys.path`` so tests can
``from cc_client.client import ...`` / ``from analysis.wave_picks import ...``
without installing the package.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
