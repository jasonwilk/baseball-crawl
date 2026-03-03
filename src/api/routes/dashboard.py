"""Dashboard routes for the baseball-crawl FastAPI application.

Provides server-rendered HTML views using Jinja2 templates.  All database
calls are executed via ``run_in_threadpool`` to avoid blocking the async
event loop.

Routes:
    GET /dashboard   -- Team season batting stats (LSB Varsity 2026)
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from src.api import db

logger = logging.getLogger(__name__)

# Resolve templates directory relative to this file's location so the module
# works regardless of the working directory the server is started from.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def team_stats(request: Request) -> HTMLResponse:
    """Render the team batting stats dashboard page.

    Fetches season batting stats for the LSB Varsity 2026 team from the
    database and renders them as an HTML table using the Jinja2 template
    ``dashboard/team_stats.html``.

    Args:
        request: The incoming HTTP request (required by Jinja2Templates).

    Returns:
        HTMLResponse containing the rendered team stats page.
    """
    players = await run_in_threadpool(
        db.get_team_batting_stats, "lsb-varsity-2026", "2026"
    )
    logger.debug("Dashboard: fetched %d player rows", len(players))
    return templates.TemplateResponse(
        request,
        "dashboard/team_stats.html",
        {
            "players": players,
            "team_name": "Lincoln HS Varsity",
        },
    )
