"""FastAPI app for the dispatch run console.

Server-rendered (Jinja2) + HTMX + SSE. One process, no build step.
``create_app(repo_root)`` is a factory so tests can point it at a tmp dir.
READ-ONLY against CartonCloud.
"""
from __future__ import annotations

import time
from html import escape
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dispatch.runner import DispatchRunSettings
from . import plans as plans_mod
from .jobs import JobManager

_HERE = Path(__file__).resolve().parent


def create_app(repo_root: Path | None = None) -> FastAPI:
    repo_root = repo_root or _HERE.parent.parent
    dispatch_base = repo_root / "data" / "processed" / "dispatch"

    app = FastAPI(title="Go Cold Dispatch Run Console")
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    templates = Jinja2Templates(directory=str(_HERE / "templates"))
    manager = JobManager()
    app.state.repo_root = repo_root
    app.state.dispatch_base = dispatch_base
    app.state.manager = manager
    app.state.templates = templates

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {
            "plans": plans_mod.list_plans(dispatch_base),
        })

    @app.post("/build", response_class=HTMLResponse)
    def start_build(
        request: Request,
        history_days: int = Form(90),
        skip_learn: bool = Form(False),
    ):
        settings = DispatchRunSettings(
            repo_root=repo_root, history_days=history_days,
            skip_learn=skip_learn)
        try:
            job_id = manager.start(settings)
        except JobManager.RunInProgressError:
            return templates.TemplateResponse(request, "_run_busy.html", {})
        resp = templates.TemplateResponse(
            request, "_progress.html", {"job_id": job_id})
        resp.headers["x-job-id"] = job_id
        return resp

    @app.get("/build/job/{job_id}/stream")
    def stream(job_id: str):
        def gen():
            sent = 0
            while True:
                job = manager.get(job_id)
                while sent < len(job.events):
                    e = job.events[sent]; sent += 1
                    cls = {"ok": "ok", "error": "error",
                           "info": "run"}.get(e.level, "")
                    msg = escape(e.message)
                    html = f'<div class="{cls}">{msg}</div>'
                    if e.stage == "done":
                        stamp = e.data.get("stamp") if e.data else None
                        link = (f'<a href="/plans/{stamp}">View plan →</a>'
                                if stamp and job.status != "failed" else "")
                        yield (f"event: done\ndata: <div class='{cls}'>"
                               f"{msg}</div> {link}\n\n")
                    else:
                        yield f"event: message\ndata: {html}\n\n"
                if job.done and sent >= len(job.events):
                    break
                time.sleep(0.1)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/plans/{stamp}", response_class=HTMLResponse)
    def plan_detail(request: Request, stamp: str):
        try:
            plan = plans_mod.get_plan(dispatch_base, stamp)
        except (FileNotFoundError, OSError):
            raise HTTPException(status_code=404, detail="plan not found")
        return templates.TemplateResponse(
            request, "plan_detail.html", {"plan": plan})

    @app.get("/plans/{stamp}/runs/{run}", response_class=HTMLResponse)
    def run_detail(request: Request, stamp: str, run: str):
        if not (dispatch_base / stamp / "suggested_runs.csv").exists():
            raise HTTPException(status_code=404, detail="plan not found")
        data = plans_mod.get_run(dispatch_base, stamp, run)
        return templates.TemplateResponse(
            request, "run_detail.html", {"run": data})

    @app.get("/plans/{stamp}/files/{name}")
    def download(stamp: str, name: str):
        try:
            path = plans_mod.file_path(dispatch_base, stamp, name)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(path, filename=name)

    return app


app = create_app()
