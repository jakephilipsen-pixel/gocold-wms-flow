"""In-process, single-build job manager for the dispatch console.

One build at a time — the console serves a single dispatcher and a live CC
pull is heavy. A second start while a build is active is rejected so a
double-click can't fire two pulls. The build is blocking (sync httpx +
pandas), so it runs in a worker thread; progress events are buffered for the
SSE endpoint to drain.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from dispatch.runner import (
    DispatchProgressEvent,
    DispatchRunResult,
    DispatchRunSettings,
    run_dispatch_job,
)

Runner = Callable[
    [DispatchRunSettings, Callable[[DispatchProgressEvent], None]],
    DispatchRunResult,
]


@dataclass
class Job:
    job_id: str
    status: str = "running"          # running / success / empty / failed
    events: list = field(default_factory=list)
    result: DispatchRunResult | None = None
    error: str | None = None
    done: bool = False
    stamp: str | None = None         # the on-disk plan folder name, once known


class JobManager:
    class RunInProgressError(RuntimeError):
        """Raised when a build is already active."""

    def __init__(self, runner: Runner = run_dispatch_job):
        self._runner = runner
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None

    def start(self, settings: DispatchRunSettings) -> str:
        with self._lock:
            if self._active is not None:
                raise self.RunInProgressError("a dispatch build is already in progress")
            job_id = uuid.uuid4().hex[:12]
            self._jobs[job_id] = Job(job_id=job_id)
            self._active = job_id
        threading.Thread(
            target=self._run, args=(job_id, settings), daemon=True,
        ).start()
        return job_id

    def _run(self, job_id: str, settings: DispatchRunSettings) -> None:
        job = self._jobs[job_id]

        def progress(event: DispatchProgressEvent) -> None:
            job.events.append(event)

        try:
            result = self._runner(settings, progress)
            job.result = result
            job.status = result.status
            job.stamp = result.stamp
            job.error = result.error
        except Exception as exc:  # noqa: BLE001 — never crash the worker
            job.status = "failed"
            job.error = str(exc)
            job.events.append(
                DispatchProgressEvent("done", f"Build failed: {exc}", "error"))
        finally:
            job.done = True
            with self._lock:
                self._active = None

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    @property
    def active(self) -> bool:
        return self._active is not None
