"""Dashboard routes for the baseball-crawl FastAPI application.

Provides server-rendered HTML views using Jinja2 templates.  All database
calls are executed via ``run_in_threadpool`` to avoid blocking the async
event loop.

Routes:
    GET /dashboard   -- Team season batting stats, scoped to the authenticated
                        user's permitted teams.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.api import db

logger = logging.getLogger(__name__)

# Resolve templates directory relative to this file's location so the module
# works regardless of the working directory the server is started from.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


@router.get("/dashboard", response_model=None)
async def team_stats(request: Request) -> Response:
    """Render the team batting stats dashboard page.

    Fetches season batting stats for the authenticated user's permitted team
    from the database and renders them as an HTML table using the Jinja2
    template ``dashboard/team_stats.html``.

    The active team is determined by:
    1. The ``team_id`` query parameter, if provided and permitted.
    2. The first entry in ``request.state.permitted_teams`` otherwise.

    Returns a 403 if the requested team_id is not in the user's permitted list.
    Returns a "no assignments" page if the user has no permitted teams.

    Args:
        request: The incoming HTTP request (required by Jinja2Templates).

    Returns:
        HTMLResponse containing the rendered team stats page, or a 403.
    """
    permitted_teams: list[str] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    # AC-7: no permitted teams
    if not permitted_teams:
        return templates.TemplateResponse(
            request,
            "dashboard/team_stats.html",
            {
                "players": [],
                "team_name": "",
                "permitted_team_infos": [],
                "active_team_id": None,
                "user": user,
                "no_assignments": True,
            },
        )

    # AC-2: respect team_id query param, validate against permitted list
    requested_team_id = request.query_params.get("team_id")
    if requested_team_id:
        if requested_team_id not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)
        active_team_id = requested_team_id
    else:
        active_team_id = permitted_teams[0]

    # AC-6: season defaults to current year
    season = str(datetime.date.today().year)

    # Fetch batting stats and team display names in parallel threadpool calls
    players, team_infos = await _fetch_dashboard_data(
        active_team_id, season, permitted_teams
    )

    team_name = next(
        (t["name"] for t in team_infos if t["team_id"] == active_team_id),
        active_team_id,
    )

    logger.debug(
        "Dashboard: team=%s season=%s players=%d", active_team_id, season, len(players)
    )

    return templates.TemplateResponse(
        request,
        "dashboard/team_stats.html",
        {
            "players": players,
            "team_name": team_name,
            "permitted_team_infos": team_infos,
            "active_team_id": active_team_id,
            "user": user,
            "no_assignments": False,
        },
    )


async def _fetch_dashboard_data(
    active_team_id: str,
    season: str,
    permitted_teams: list[str],
) -> tuple[list, list]:
    """Fetch batting stats and team display names concurrently.

    Args:
        active_team_id: The team_id whose stats to fetch.
        season: The season year string.
        permitted_teams: All team_ids the user can access (for selector).

    Returns:
        Tuple of (players list, team_infos list).
    """
    players = await run_in_threadpool(db.get_team_batting_stats, active_team_id, season)
    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)
    return players, team_infos
