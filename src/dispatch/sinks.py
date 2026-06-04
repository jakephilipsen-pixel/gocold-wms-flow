"""Dispatch write seam.

FileSink is the v1 destination (writes the review files). CartonCloudSink
is built so a future write-back is one tested adapter — but it refuses to
act unless BOTH write_enabled AND dispatch_write_approved are set, neither
of which is true in v1. CartonCloud is read-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .output import write_dispatch_plan
from .predict import DispatchPlan


@dataclass(frozen=True)
class AssignResult:
    so_id: str
    ok: bool
    detail: str


class DispatchSink(Protocol):
    def apply(self, plan: DispatchPlan) -> list[AssignResult]:
        ...


class FileSink:
    """v1 sink: write the plan to operator-facing files."""

    def __init__(self, out_dir: Path):
        self.out_dir = Path(out_dir)

    def apply(self, plan: DispatchPlan) -> list[AssignResult]:
        write_dispatch_plan(plan, self.out_dir)
        return [AssignResult(a.so_id, True, f"written → {a.predicted_run}")
                for a in plan.assignments]


class CartonCloudSink:
    """Future write-back. Refuses to act in v1 (CC stays read-only)."""

    def __init__(self, *, write_enabled: bool = False,
                 dispatch_write_approved: bool = False):
        self.write_enabled = write_enabled
        self.dispatch_write_approved = dispatch_write_approved

    def apply(self, plan: DispatchPlan) -> list[AssignResult]:
        if not (self.write_enabled and self.dispatch_write_approved):
            raise PermissionError(
                "CC dispatch write-back not approved; CartonCloud is "
                "read-only. Both write_enabled and dispatch_write_approved "
                "must be set, and the SAP B1 boundary cleared, first.")
        raise NotImplementedError(  # pragma: no cover - not built in v1
            "CartonCloudSink write path is intentionally unbuilt in v1")
