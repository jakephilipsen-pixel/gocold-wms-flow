"""In-process, single-run job manager for wave generation.

One run at a time — the console serves a single operator, and a live CC
pull is heavy. A second start while a run is active is rejected so a
double-click can't fire two pulls. The pipeline is blocking (sync httpx +
pandas), so it runs in a worker thread; progress events are buffered for
the SSE endpoint to drain.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from wave_runner import (
    ProgressEvent,
    RunResult,
    WaveRunSettings,
    run_wave_generation,
)

Runner = Callable[[WaveRunSettings, Callable[[ProgressEvent], None]], RunResult]


@dataclass
class Job:
    job_id: str
    status: str = "running"          # running / success / empty / failed
    events: list = field(default_factory=list)
    result: RunResult | None = None
    error: str | None = None
    done: bool = False
    run_id: str | None = None        # the on-disk run folder name, once known


class JobManager:
    class RunInProgressError(RuntimeError):
        """Raised when a run is already active."""

    def __init__(self, runner: Runner = run_wave_generation):
        self._runner = runner
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active: str | None = None

    def start(self, settings: WaveRunSettings) -> str:
        with self._lock:
            if self._active is not None:
                raise self.RunInProgressError("a wave run is already in progress")
            job_id = uuid.uuid4().hex[:12]
            self._jobs[job_id] = Job(job_id=job_id)
            self._active = job_id
        threading.Thread(
            target=self._run, args=(job_id, settings), daemon=True,
        ).start()
        return job_id

    def _run(self, job_id: str, settings: WaveRunSettings) -> None:
        job = self._jobs[job_id]

        def progress(event: ProgressEvent) -> None:
            job.events.append(event)

        try:
            result = self._runner(settings, progress)
            job.result = result
            job.status = result.status
            job.run_id = result.run_id
            job.error = result.error
        except Exception as exc:  # noqa: BLE001 — never crash the worker
            job.status = "failed"
            job.error = str(exc)
            job.events.append(
                ProgressEvent("done", f"Run failed: {exc}", "error"))
        finally:
            job.done = True
            with self._lock:
                self._active = None

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    @property
    def active(self) -> bool:
        return self._active is not None
