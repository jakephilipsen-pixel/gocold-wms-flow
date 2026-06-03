"""Shared core for wave pick generation.

Both the CLI (``scripts/generate_waves.py``) and the web console
(``src/web/``) call ``run_wave_generation`` so the pipeline lives in one
place. The CLI passes a ``progress`` callback that prints; the web app
passes one that buffers events for SSE.

Read-only against CartonCloud — we generate paperwork, never push back.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from analysis import (
    DEFAULT_AWAITING_STATUS,
    DEFAULT_EARLY_RELEASE_CARTONS,
    DEFAULT_FULL_PALLET_RATIO,
    DEFAULT_LINES_PER_HOUR,
    DEFAULT_PALLET_FRACTION_THRESHOLD,
)


@dataclass
class WaveRunSettings:
    """Everything ``run_wave_generation`` needs for one run.

    ``repo_root`` anchors the default data/output paths. Explicit path
    fields override the defaults (used by the CLI's flags).
    """
    repo_root: Path
    status: str = DEFAULT_AWAITING_STATUS
    customer_name: str | None = None
    pallet_fraction_threshold: float = DEFAULT_PALLET_FRACTION_THRESHOLD
    early_release_cartons: int = DEFAULT_EARLY_RELEASE_CARTONS
    run_group_col: str = "delivery_state"
    soh_fallback: bool = False
    lines_per_hour: int = DEFAULT_LINES_PER_HOUR
    pallet_ratio: float = DEFAULT_FULL_PALLET_RATIO
    # Optional explicit paths; None = resolve from repo_root at run time.
    raw_dir: Path | None = None
    dims_path: Path | None = None
    locations_path: Path | None = None
    rules_path: Path | None = None
    assignments_path: Path | None = None
    logo_path: Path | None = None
    out_dir: Path | None = None


@dataclass
class ProgressEvent:
    """One streamed progress line."""
    stage: str          # machine-readable stage key (see run_wave_generation)
    message: str        # human-readable line
    level: str = "info"  # info / ok / error
    data: dict[str, object] = field(default_factory=dict)


@dataclass
class RunResult:
    """Outcome of a single ``run_wave_generation`` call."""
    run_id: str
    out_dir: Path
    summary: dict[str, object]
    status: str          # success / empty / failed
    error: str | None = None


ProgressCallback = Callable[[ProgressEvent], None]
