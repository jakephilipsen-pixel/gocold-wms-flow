"""FastAPI app for the wave pick console.

Server-rendered (Jinja2) + HTMX + SSE. One process, no build step.
``create_app(repo_root)`` is a factory so tests can point it at a tmp dir.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wave_runner import WaveRunSettings, _load_dotenv
from . import runs as runs_mod
from .jobs import JobManager

_HERE = Path(__file__).resolve().parent


def create_app(repo_root: Path | None = None) -> FastAPI:
    repo_root = repo_root or _HERE.parent.parent
    waves_base = repo_root / "data" / "processed" / "waves"
    _load_dotenv(repo_root / ".env")

    app = FastAPI(title="Go Cold Wave Pick Console")
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    templates = Jinja2Templates(directory=str(_HERE / "templates"))
    manager = JobManager()
    app.state.repo_root = repo_root
    app.state.waves_base = waves_base
    app.state.manager = manager
    app.state.templates = templates

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {
            "runs": runs_mod.list_runs(waves_base),
        })

    @app.post("/runs", response_class=HTMLResponse)
    def start_run(
        request: Request,
        status: str = Form("AWAITING_PICK_AND_PACK"),
        customer_name: str = Form(""),
        pallet_fraction_threshold: float = Form(0.70),
        early_release_cartons: int = Form(30),
        run_group_col: str = Form("delivery_state"),
        soh_fallback: bool = Form(False),
    ):
        settings = WaveRunSettings(
            repo_root=repo_root, status=status,
            customer_name=customer_name or None,
            pallet_fraction_threshold=pallet_fraction_threshold,
            early_release_cartons=early_release_cartons,
            run_group_col=run_group_col,
            soh_fallback=soh_fallback)
        try:
            job_id = manager.start(settings)
        except JobManager.RunInProgressError:
            return templates.TemplateResponse(request, "_run_busy.html", {})
        resp = templates.TemplateResponse(
            request, "_progress.html", {"job_id": job_id})
        resp.headers["x-job-id"] = job_id
        return resp

    @app.get("/runs/job/{job_id}/stream")
    def stream(job_id: str):
        def gen():
            sent = 0
            while True:
                job = manager.get(job_id)
                while sent < len(job.events):
                    e = job.events[sent]; sent += 1
                    cls = {"ok": "ok", "error": "error", "info": "run"}.get(e.level, "")
                    html = f'<div class="{cls}">{e.message}</div>'
                    if e.stage == "done":
                        link = (f'<a href="/runs/{job.run_id}">View run →</a>'
                                if job.run_id and job.status != "failed" else "")
                        yield (f"event: done\ndata: <div class='{cls}'>"
                               f"{e.message}</div> {link}\n\n")
                    else:
                        yield f"event: message\ndata: {html}\n\n"
                if job.done and sent >= len(job.events):
                    break
                time.sleep(0.1)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(request: Request, run_id: str):
        try:
            run = runs_mod.get_run(waves_base, run_id)
        except (FileNotFoundError, OSError):
            raise HTTPException(status_code=404, detail="run not found")
        return templates.TemplateResponse(
            request, "run_detail.html", {"run": run})

    @app.get("/runs/{run_id}/waves/{wave_id}", response_class=HTMLResponse)
    def wave_detail(request: Request, run_id: str, wave_id: str):
        wave = runs_mod.get_wave(waves_base, run_id, wave_id)
        return templates.TemplateResponse(
            request, "wave_detail.html", {"wave": wave})

    @app.get("/runs/{run_id}/files/{wave_id}/{name}")
    def download(run_id: str, wave_id: str, name: str):
        try:
            path = runs_mod.file_path(waves_base, run_id, wave_id, name)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(path, filename=name)

    return app


app = create_app()
