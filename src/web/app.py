"""FastAPI app for the wave pick console.

Server-rendered (Jinja2) + HTMX + SSE. One process, no build step.
``create_app(repo_root)`` is a factory so tests can point it at a tmp dir.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wave_runner import _load_dotenv
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

    return app


app = create_app()
