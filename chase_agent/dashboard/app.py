"""FastAPI dashboard app. Bound to localhost only."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from chase_agent import db
from chase_agent.dashboard.state import build_view

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _seed_demo_today() -> date:
    """Demo date pinned via DEMO_TODAY env var, else real today."""
    raw = os.environ.get("DEMO_TODAY")
    if raw:
        return date.fromisoformat(raw)
    return date.today()


def create_app() -> FastAPI:
    app = FastAPI(title="Chase Maximizer", docs_url=None, redoc_url=None)

    static_dir = BASE_DIR / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    db.init_db()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        view = build_view(today=_seed_demo_today())
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"view": view},
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
