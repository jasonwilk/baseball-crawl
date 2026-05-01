"""Dashboard routes for the baseball-crawl FastAPI application.

Provides server-rendered HTML views using Jinja2 templates.  All database
calls are executed via ``run_in_threadpool`` to avoid blocking the async
event loop.

Routes:
    GET /dashboard            -- Season schedule (upcoming + completed games).
    GET /dashboard/batting    -- Team season batting stats, scoped to the authenticated
                                 user's permitted teams.
    GET /dashboard/pitching   -- Team season pitching stats.
    GET /dashboard/games      -- Game log with scores and W/L indicators.
    GET /dashboard/games/{game_id} -- Single game box score with batting and pitching lines.
    GET /dashboard/opponents      -- Opponent list with record and next/last game date.
    GET /dashboard/opponents/{opponent_team_id} -- Opponent scouting report.
    GET /dashboard/players/{player_id} -- Player career profile across seasons and teams.
    GET /dashboard/charts/spray/player/{player_id}.png -- Per-player offensive spray chart PNG.
    GET /dashboard/charts/spray/team/{team_id}.png     -- Team aggregate offensive spray chart PNG.
"""

from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.api import db
from src.api.helpers import format_avg, format_date, ip_display
from src.charts.spray import render_spray_chart

logger = logging.getLogger(__name__)

# Resolve templates directory relative to this file's location so the module
# works regardless of the working directory the server is started from.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()

# Register Jinja2 filters for all dashboard templates.
templates.env.filters["ip_display"] = ip_display
templates.env.filters["format_avg"] = format_avg
templates.env.filters["format_date"] = format_date


def _relative_date(date_str: str | None) -> str:
    """Format an ISO date string as relative days (e.g., '5d ago', 'Today')."""
    if not date_str:
        return "—"
    try:
        d = datetime.date.fromisoformat(date_str)
        days = (datetime.date.today() - d).days
        if days == 0:
            return "Today"
        if days == 1:
            return "1d ago"
        return f"{days}d ago"
    except (ValueError, TypeError):
        return date_str


templates.env.filters["relative_date"] = _relative_date


_BATTING_SORT_KEYS: set[str] = {
    "name", "avg", "obp", "gp", "bb", "so", "slg", "h", "ab", "2b", "3b", "hr", "sb", "rbi",
}
_BATTING_DEFAULT_DIR: dict[str, str] = {
    "name": "asc", "so": "asc",
    "avg": "desc", "obp": "desc", "slg": "desc", "h": "desc", "ab": "desc",
    "2b": "desc", "3b": "desc", "hr": "desc", "rbi": "desc", "sb": "desc",
    "bb": "desc", "gp": "desc",
}

_PITCHING_SORT_KEYS: set[str] = {
    "name", "era", "k9", "bb9", "whip", "gp", "ip", "h", "er", "bb", "so", "hr",
}
_PITCHING_DEFAULT_DIR: dict[str, str] = {
    "name": "asc", "era": "asc", "bb9": "asc", "whip": "asc",
    "er": "asc", "bb": "asc", "h": "asc", "hr": "asc",
    "k9": "desc", "so": "desc", "ip": "desc", "gp": "desc",
}

# Opponent scouting report column subsets (per TN-3) -- no bb9/hr on opponent pitching.
_OPP_BAT_KEYS: set[str] = {"name", "avg", "obp", "gp", "ab", "bb", "so", "slg", "h", "hr", "sb", "rbi"}
_OPP_PIT_KEYS: set[str] = {"name", "era", "k9", "whip", "gp", "ip", "h", "er", "bb", "so"}


def _resolve_year_and_team(
    team_year_map: dict[int, int],
    permitted_teams: list[int],
    team_id_param: int | None,
    year_param: int | None,
    *,
    current_year: int | None = None,
) -> tuple[int, int]:
    """Resolve (active_team_id, active_year) per TN-2 parameter resolution order.

    Args:
        team_year_map: Mapping of team_id → year from ``db.get_team_year_map``.
        permitted_teams: Ordered list of all permitted team ids.
        team_id_param:  Parsed team_id query param (already validated), or None.
        year_param:     Parsed year query param, or None.
        current_year:   The "current" year to use for defaults.  When *None*,
            falls back to ``max(team_year_map.values())`` (consistent with
            route handlers) or ``datetime.date.today().year`` if the map is
            empty.

    Returns:
        Tuple of (active_team_id, active_year).
    """
    if current_year is None:
        current_year = max(team_year_map.values()) if team_year_map else datetime.date.today().year
    available_years = sorted(set(team_year_map.values()), reverse=True)

    # Path 2: team_id present → team wins; derive year from map
    if team_id_param is not None and team_id_param in permitted_teams:
        return team_id_param, team_year_map.get(team_id_param, current_year)

    # Path 3: explicit year param with matching teams
    if year_param is not None:
        teams_for_year = [t for t in permitted_teams if team_year_map.get(t) == year_param]
        if teams_for_year:
            return teams_for_year[0], year_param
        # Path 5: fall through — explicit year has no matching teams

    # Path 4: default to current calendar year
    teams_for_current = [t for t in permitted_teams if team_year_map.get(t) == current_year]
    if teams_for_current:
        return teams_for_current[0], current_year

    # Fallback: most recent year with any data
    if available_years:
        fallback_year = available_years[0]
        teams_for_fallback = [t for t in permitted_teams if team_year_map.get(t) == fallback_year]
        if teams_for_fallback:
            return teams_for_fallback[0], fallback_year

    # No teams have data at all
    return permitted_teams[0], current_year


def _pick_season_for_year(
    available_seasons: list[dict[str, str]],
    active_year: int,
    fallback_year: int,
) -> str:
    """Choose the best season_id matching *active_year*.

    Season IDs follow the ``YYYY-type[-class]`` convention (e.g.
    ``2025-spring-hs``).  The function returns the first season whose
    leading four digits match *active_year*.  If none match, it falls
    back to ``available_seasons[0]`` (most-recent) or synthesises a
    placeholder using *fallback_year*.
    """
    year_prefix = str(active_year)
    for s in available_seasons:
        if s["season_id"].startswith(year_prefix):
            return s["season_id"]
    # No season matches the active year — fall back to newest available
    if available_seasons:
        return available_seasons[0]["season_id"]
    return f"{fallback_year}-spring-hs"


def _parse_sort_params(
    request: Request,
    sort_param: str,
    dir_param: str,
    valid_keys: set[str],
    default_sort: str,
    default_dirs: dict[str, str],
) -> tuple[str, str, bool]:
    """Parse and validate sort query parameters.

    Returns (sort_key, direction, is_explicit) where is_explicit is True when
    the caller provided a recognized sort key (meaning the data needs re-sorting).
    """
    raw_sort = request.query_params.get(sort_param, "").strip().lower()
    raw_dir = request.query_params.get(dir_param, "").strip().lower()
    if raw_sort in valid_keys:
        sort_key = raw_sort
        direction = raw_dir if raw_dir in ("asc", "desc") else default_dirs.get(sort_key, "desc")
        return sort_key, direction, True
    return default_sort, default_dirs.get(default_sort, "desc"), False


def _sort_batting(players: list[dict], sort_key: str, direction: str) -> list[dict]:
    """Sort batting rows by the given key, zero-denominator rows always last.

    Args:
        players:   List of player dicts from ``db.get_team_batting_stats``.
        sort_key:  Column key from ``_BATTING_SORT_KEYS``.
        direction: ``"asc"`` or ``"desc"``.

    Returns:
        Sorted list (new list, original untouched).
    """
    reverse = direction == "desc"

    # Name sort: split zero-AB rows to bottom, sort the rest alphabetically.
    if sort_key == "name":
        has_ab = [r for r in players if (r.get("ab") or 0) > 0]
        zero_ab = [r for r in players if (r.get("ab") or 0) == 0]
        has_ab_sorted = sorted(has_ab, key=lambda r: r.get("name") or "", reverse=reverse)
        zero_ab_sorted = sorted(zero_ab, key=lambda r: r.get("name") or "")
        return has_ab_sorted + zero_ab_sorted

    def _key(row: dict) -> tuple:
        ab = row.get("ab") or 0
        ip_zero = ab == 0  # sentinel for zero-denominator

        if sort_key == "avg":
            val = (row.get("h") or 0) / ab if ab else 0.0
        elif sort_key == "obp":
            h = row.get("h") or 0
            bb = row.get("bb") or 0
            hbp = row.get("hbp") or 0
            shf = row.get("shf") or 0
            denom = ab + bb + hbp + shf
            val = (h + bb + hbp) / denom if denom else 0.0
        elif sort_key == "slg":
            h = row.get("h") or 0
            doubles = row.get("doubles") or 0
            triples = row.get("triples") or 0
            hr = row.get("hr") or 0
            val = (h + doubles + 2 * triples + 3 * hr) / ab if ab else 0.0
        elif sort_key == "gp":
            val = float(row.get("games") or 0)
        elif sort_key == "h":
            val = float(row.get("h") or 0)
        elif sort_key == "ab":
            val = float(row.get("ab") or 0)
        elif sort_key == "2b":
            val = float(row.get("doubles") or 0)
        elif sort_key == "3b":
            val = float(row.get("triples") or 0)
        elif sort_key == "hr":
            val = float(row.get("hr") or 0)
        elif sort_key == "rbi":
            val = float(row.get("rbi") or 0)
        elif sort_key == "bb":
            val = float(row.get("bb") or 0)
        elif sort_key == "so":
            val = float(row.get("so") or 0)
        elif sort_key == "sb":
            val = float(row.get("sb") or 0)
        else:
            val = 0.0
        # Zero-denominator rows always sort last; within those, stable by name
        return (1 if ip_zero else 0, -val if reverse else val)

    return sorted(players, key=_key)


def _sort_pitching(pitchers: list[dict], sort_key: str, direction: str) -> list[dict]:
    """Sort pitching rows by the given key, zero ip_outs rows always last.

    Args:
        pitchers:  List of pitcher dicts (after ``_compute_pitching_rates``).
        sort_key:  Column key from ``_PITCHING_SORT_KEYS``.
        direction: ``"asc"`` or ``"desc"``.

    Returns:
        Sorted list (new list, original untouched).
    """
    reverse = direction == "desc"

    # Name sort: split zero-ip_outs rows to bottom, sort the rest alphabetically.
    if sort_key == "name":
        has_ip = [r for r in pitchers if (r.get("ip_outs") or 0) > 0]
        zero_ip = [r for r in pitchers if (r.get("ip_outs") or 0) == 0]
        has_ip_sorted = sorted(has_ip, key=lambda r: r.get("name") or "", reverse=reverse)
        zero_ip_sorted = sorted(zero_ip, key=lambda r: r.get("name") or "")
        return has_ip_sorted + zero_ip_sorted

    def _key(row: dict) -> tuple:
        ip_outs = row.get("ip_outs") or 0
        zero_ip = ip_outs == 0

        if sort_key == "era":
            val = (row.get("er") or 0) * 27 / ip_outs if ip_outs else float("inf")
        elif sort_key == "k9":
            val = (row.get("so") or 0) * 27 / ip_outs if ip_outs else 0.0
        elif sort_key == "bb9":
            val = (row.get("bb") or 0) * 27 / ip_outs if ip_outs else float("inf")
        elif sort_key == "whip":
            val = ((row.get("bb") or 0) + (row.get("h") or 0)) * 3 / ip_outs if ip_outs else float("inf")
        elif sort_key == "gp":
            val = float(row.get("games") or 0)
        elif sort_key == "ip":
            val = float(ip_outs)
        elif sort_key == "h":
            val = float(row.get("h") or 0)
        elif sort_key == "er":
            val = float(row.get("er") or 0)
        elif sort_key == "bb":
            val = float(row.get("bb") or 0)
        elif sort_key == "so":
            val = float(row.get("so") or 0)
        elif sort_key == "hr":
            val = float(row.get("hr") or 0)
        else:
            val = 0.0
        return (1 if zero_ip else 0, -val if reverse else val)

    return sorted(pitchers, key=_key)


@router.get("/dashboard", response_model=None)
async def schedule(request: Request) -> Response:
    """Render the schedule landing page for the active team.

    Shows upcoming games (status='scheduled') as cards sorted by date ascending
    and completed games as a compact table sorted by date descending.  The nearest
    upcoming game receives visual emphasis (NEXT badge).  Each game row links to
    the opponent scouting page; completed game scores link to the box score.

    The active team is determined by:
    1. The ``team_id`` query parameter, if provided and permitted.
    2. The first entry in ``request.state.permitted_teams`` otherwise.

    Returns a 403 if the requested team_id is not in the user's permitted list.
    Returns a "no assignments" page if the user has no permitted teams.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse containing the rendered schedule page, or a 403.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    if not permitted_teams:
        return templates.TemplateResponse(
            request,
            "dashboard/schedule.html",
            {
                "upcoming_games": [],
                "completed_games": [],
                "next_game_id": None,
                "team_name": "",
                "permitted_team_infos": [],
                "active_team_id": None,
                "user": user,
                "is_admin": False,
                "no_assignments": True,
                "is_dev_mode": bool(os.environ.get("DEV_USER_EMAIL")),
            },
        )

    # Parse team_id param and validate
    requested_team_id_raw = request.query_params.get("team_id")
    team_id_param_s: int | None = None
    if requested_team_id_raw:
        try:
            team_id_param_s = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if team_id_param_s not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)

    # Parse year param
    year_raw_s = request.query_params.get("year")
    year_param_s: int | None = None
    if year_raw_s:
        try:
            year_param_s = int(year_raw_s)
        except (ValueError, TypeError):
            year_param_s = None

    # Build team→year map and resolve active team + year
    team_year_map_s = await run_in_threadpool(db.get_team_year_map, permitted_teams)
    current_year = max(team_year_map_s.values()) if team_year_map_s else datetime.date.today().year
    active_team_id_s, active_year_s = _resolve_year_and_team(
        team_year_map_s, permitted_teams, team_id_param_s, year_param_s,
        current_year=current_year,
    )
    available_years_s: list[int] = sorted(set(team_year_map_s.values()), reverse=True)
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id_s)
    if not requested_season_id or year_param_s is not None:
        season_id = _pick_season_for_year(available_seasons, active_year_s, current_year)
    else:
        season_id = requested_season_id
    if not available_seasons:
        available_seasons = [{"season_id": season_id}]

    games_raw, team_infos = await _fetch_schedule_data(active_team_id_s, season_id, permitted_teams)

    # Split into upcoming (scheduled) and completed, in correct display order
    today = datetime.date.today()
    upcoming: list[dict] = [g for g in games_raw if g.get("status") == "scheduled"]
    completed: list[dict] = list(reversed([g for g in games_raw if g.get("status") == "completed"]))

    # Identify the nearest upcoming game
    next_game_id: str | None = None
    for g in upcoming:
        date_str = g.get("game_date", "")
        if date_str:
            try:
                game_date = datetime.date.fromisoformat(date_str[:10])
                if game_date >= today:
                    next_game_id = g["game_id"]
                    break
            except ValueError:
                pass

    # Add days_until to each upcoming game
    for g in upcoming:
        date_str = g.get("game_date", "")
        if date_str:
            try:
                game_date = datetime.date.fromisoformat(date_str[:10])
                g["days_until"] = (game_date - today).days
            except ValueError:
                g["days_until"] = None
        else:
            g["days_until"] = None

    # Add W/L indicator to completed games
    for g in completed:
        g["wl"] = _compute_wl(g, active_team_id_s)

    team_name = next(
        (t["name"] for t in team_infos if t["id"] == active_team_id_s),
        str(active_team_id_s),
    )

    logger.debug(
        "Schedule: team=%s season_id=%s upcoming=%d completed=%d",
        active_team_id_s, season_id, len(upcoming), len(completed),
    )

    teams_with_stat_data_s = await run_in_threadpool(db.get_teams_with_stat_data, permitted_teams)
    year_team_infos_s = [t for t in team_infos if team_year_map_s.get(t["id"]) == active_year_s]
    if not year_team_infos_s:
        year_team_infos_s = team_infos
    for t in year_team_infos_s:
        t["has_stat_data"] = t["id"] in teams_with_stat_data_s

    # Admin detection for conditional "Link" CTA on unscouted schedule cards.
    is_admin_s = await run_in_threadpool(_is_admin_user, user)

    return templates.TemplateResponse(
        request,
        "dashboard/schedule.html",
        {
            "upcoming_games": upcoming,
            "completed_games": completed,
            "next_game_id": next_game_id,
            "team_name": team_name,
            "permitted_team_infos": year_team_infos_s,
            "active_team_id": active_team_id_s,
            "active_year": active_year_s,
            "available_years": available_years_s,
            "current_year": current_year,
            "season_id": season_id,
            "user": user,
            "is_admin": is_admin_s,
            "no_assignments": False,
        },
    )


async def _fetch_schedule_data(
    active_team_id: int,
    season_id: str,
    permitted_teams: list[int],
) -> tuple[list, list]:
    """Fetch schedule games and team display names concurrently.

    Args:
        active_team_id: The team_id whose schedule to fetch.
        season_id: The season slug.
        permitted_teams: All team_ids the user can access.

    Returns:
        Tuple of (games list, team_infos list).
    """
    games = await run_in_threadpool(db.get_schedule_games, active_team_id, season_id)
    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)
    return games, team_infos


@router.get("/dashboard/batting", response_model=None)
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
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
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
                "is_dev_mode": bool(os.environ.get("DEV_USER_EMAIL")),
            },
        )

    # Parse team_id param and validate
    requested_team_id_raw = request.query_params.get("team_id")
    team_id_param: int | None = None
    if requested_team_id_raw:
        try:
            team_id_param = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if team_id_param not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)

    # Parse year param
    year_raw = request.query_params.get("year")
    year_param: int | None = None
    if year_raw:
        try:
            year_param = int(year_raw)
        except (ValueError, TypeError):
            year_param = None

    # Build team→year map and resolve active team + year (AC-1, AC-2, AC-3)
    team_year_map = await run_in_threadpool(db.get_team_year_map, permitted_teams)
    current_year = max(team_year_map.values()) if team_year_map else datetime.date.today().year
    active_team_id, active_year = _resolve_year_and_team(
        team_year_map, permitted_teams, team_id_param, year_param,
        current_year=current_year,
    )
    available_years: list[int] = sorted(set(team_year_map.values()), reverse=True)
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id)
    # year takes precedence over season_id param (AC-8)
    if not requested_season_id or year_param is not None:
        season_id = _pick_season_for_year(available_seasons, active_year, current_year)
    else:
        season_id = requested_season_id
    if not available_seasons:
        available_seasons = [{"season_id": season_id}]

    # Fetch batting stats and team display names in parallel threadpool calls
    players, team_infos = await _fetch_dashboard_data(
        active_team_id, season_id, permitted_teams
    )

    # Sort params (AC-1)
    current_sort, current_dir, needs_sort = _parse_sort_params(
        request, "sort", "dir", _BATTING_SORT_KEYS, "avg", _BATTING_DEFAULT_DIR,
    )
    if needs_sort:
        players = _sort_batting(players, current_sort, current_dir)

    team_name = next(
        (t["name"] for t in team_infos if t["id"] == active_team_id),
        str(active_team_id),
    )

    logger.debug(
        "Dashboard: team=%s season_id=%s players=%d sort=%s dir=%s",
        active_team_id, season_id, len(players), current_sort, current_dir,
    )

    # Determine which teams have real stat data (E-142-03 empty state)
    teams_with_stat_data = await run_in_threadpool(db.get_teams_with_stat_data, permitted_teams)

    # Filter team pills to only teams with data in the active year (Finding 1)
    year_team_infos = [t for t in team_infos if team_year_map.get(t["id"]) == active_year]
    if not year_team_infos:
        year_team_infos = team_infos
    for t in year_team_infos:
        t["has_stat_data"] = t["id"] in teams_with_stat_data

    return templates.TemplateResponse(
        request,
        "dashboard/team_stats.html",
        {
            "players": players,
            "team_name": team_name,
            "permitted_team_infos": year_team_infos,
            "active_team_id": active_team_id,
            "active_year": active_year,
            "available_years": available_years,
            "current_year": current_year,
            "season_id": season_id,
            "user": user,
            "no_assignments": False,
            "current_sort": current_sort,
            "current_dir": current_dir,
            "active_team_has_stat_data": active_team_id in teams_with_stat_data,
        },
    )


async def _fetch_dashboard_data(
    active_team_id: int,
    season_id: str,
    permitted_teams: list[int],
) -> tuple[list, list]:
    """Fetch batting stats and team display names concurrently.

    Args:
        active_team_id: The team_id whose stats to fetch.
        season_id: The season slug (e.g. ``"2026-spring-hs"``).
        permitted_teams: All team_ids the user can access (for selector).

    Returns:
        Tuple of (players list, team_infos list).
    """
    players = await run_in_threadpool(db.get_team_batting_stats, active_team_id, season_id)
    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)
    return players, team_infos


def _compute_pitching_rates(pitchers: list[dict]) -> list[dict]:
    """Compute ERA, K/9, BB/9, and WHIP for each pitcher row.

    Mutates each row in place by adding ``era``, ``k9``, ``bb9``, and
    ``whip`` string keys.  Division by zero (ip_outs == 0) yields ``"-"``.

    Args:
        pitchers: List of pitcher dicts from ``db.get_team_pitching_stats``.

    Returns:
        The same list with computed rate fields added to each dict.
    """
    for row in pitchers:
        ip_outs = row.get("ip_outs") or 0
        er = row.get("er") or 0
        so = row.get("so") or 0
        bb = row.get("bb") or 0
        h = row.get("h") or 0
        pitches = row.get("pitches") or 0
        total_strikes = row.get("total_strikes") or 0
        if ip_outs == 0:
            row["era"] = "-"
            row["k9"] = "-"
            row["bb9"] = "-"
            row["whip"] = "-"
        else:
            row["era"] = f"{(er * 27) / ip_outs:.2f}"
            row["k9"] = f"{(so * 27) / ip_outs:.1f}"
            row["bb9"] = f"{(bb * 27) / ip_outs:.1f}"
            row["whip"] = f"{(bb + h) * 3 / ip_outs:.2f}"
        row["strike_pct"] = f"{(total_strikes / pitches) * 100:.1f}%" if pitches > 0 else "-"
    return pitchers


@router.get("/dashboard/pitching", response_model=None)
async def team_pitching(request: Request) -> Response:
    """Render the team pitching stats dashboard page.

    Fetches season pitching stats for the authenticated user's permitted team
    and renders them as an HTML table using the Jinja2 template
    ``dashboard/team_pitching.html``.  Computed rate stats (ERA, K/9, BB/9,
    WHIP) are calculated in Python before template rendering.

    The active team is determined by:
    1. The ``team_id`` query parameter, if provided and permitted.
    2. The first entry in ``request.state.permitted_teams`` otherwise.

    Returns a 403 if the requested team_id is not in the user's permitted list.
    Returns a "no assignments" page if the user has no permitted teams.

    Args:
        request: The incoming HTTP request (required by Jinja2Templates).

    Returns:
        HTMLResponse containing the rendered pitching stats page, or a 403.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    if not permitted_teams:
        return templates.TemplateResponse(
            request,
            "dashboard/team_pitching.html",
            {
                "pitchers": [],
                "team_name": "",
                "permitted_team_infos": [],
                "active_team_id": None,
                "user": user,
                "no_assignments": True,
            },
        )

    # Parse team_id param and validate
    requested_team_id_raw = request.query_params.get("team_id")
    team_id_param_p: int | None = None
    if requested_team_id_raw:
        try:
            team_id_param_p = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if team_id_param_p not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)

    # Parse year param
    year_raw_p = request.query_params.get("year")
    year_param_p: int | None = None
    if year_raw_p:
        try:
            year_param_p = int(year_raw_p)
        except (ValueError, TypeError):
            year_param_p = None

    # Build team→year map and resolve active team + year
    team_year_map_p = await run_in_threadpool(db.get_team_year_map, permitted_teams)
    current_year = max(team_year_map_p.values()) if team_year_map_p else datetime.date.today().year
    active_team_id_p, active_year_p = _resolve_year_and_team(
        team_year_map_p, permitted_teams, team_id_param_p, year_param_p,
        current_year=current_year,
    )
    available_years_p: list[int] = sorted(set(team_year_map_p.values()), reverse=True)
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id_p)
    if not requested_season_id or year_param_p is not None:
        season_id = _pick_season_for_year(available_seasons, active_year_p, current_year)
    else:
        season_id = requested_season_id
    if not available_seasons:
        available_seasons = [{"season_id": season_id}]

    pitchers_raw = await run_in_threadpool(
        db.get_team_pitching_stats, active_team_id_p, season_id
    )
    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)

    pitchers = _compute_pitching_rates(pitchers_raw)

    # Sort params (AC-2)
    current_sort_p, current_dir_p, needs_sort_p = _parse_sort_params(
        request, "sort", "dir", _PITCHING_SORT_KEYS, "era", _PITCHING_DEFAULT_DIR,
    )
    if needs_sort_p:
        pitchers = _sort_pitching(pitchers, current_sort_p, current_dir_p)

    team_name = next(
        (t["name"] for t in team_infos if t["id"] == active_team_id_p),
        str(active_team_id_p),
    )

    logger.debug(
        "Pitching dashboard: team=%s season_id=%s pitchers=%d sort=%s dir=%s",
        active_team_id_p, season_id, len(pitchers), current_sort_p, current_dir_p,
    )

    # Determine which teams have real stat data (E-142-03 empty state)
    teams_with_stat_data_p = await run_in_threadpool(db.get_teams_with_stat_data, permitted_teams)

    # Filter team pills to only teams with data in the active year (Finding 1)
    year_team_infos_p = [t for t in team_infos if team_year_map_p.get(t["id"]) == active_year_p]
    if not year_team_infos_p:
        year_team_infos_p = team_infos
    for t in year_team_infos_p:
        t["has_stat_data"] = t["id"] in teams_with_stat_data_p

    return templates.TemplateResponse(
        request,
        "dashboard/team_pitching.html",
        {
            "pitchers": pitchers,
            "team_name": team_name,
            "permitted_team_infos": year_team_infos_p,
            "active_team_id": active_team_id_p,
            "active_year": active_year_p,
            "available_years": available_years_p,
            "current_year": current_year,
            "season_id": season_id,
            "user": user,
            "no_assignments": False,
            "current_sort": current_sort_p,
            "current_dir": current_dir_p,
            "active_team_has_stat_data": active_team_id_p in teams_with_stat_data_p,
        },
    )


def _compute_wl(game: dict, team_id: int) -> str:
    """Compute W/L indicator from a game dict for the given team_id.

    Returns ``"W"``, ``"L"``, ``"T"`` for tied games, or ``"-"`` if scores are null.

    Args:
        game:    A game dict from ``db.get_team_games``.
        team_id: The team whose perspective determines W/L.

    Returns:
        ``"W"``, ``"L"``, ``"T"``, or ``"-"``.
    """
    home_score = game.get("home_score")
    away_score = game.get("away_score")
    if home_score is None or away_score is None:
        return "-"
    if home_score == away_score:
        return "T"
    is_home = game.get("is_home")
    if is_home:
        return "W" if home_score > away_score else "L"
    return "W" if away_score > home_score else "L"


@router.get("/dashboard/games", response_model=None)
async def game_list(request: Request) -> Response:
    """Render the game log page for the active team.

    Shows a list of games with date, opponent, score, W/L, and home/away
    indicator.  Games are sorted by date descending (most recent first).

    The active team is determined by:
    1. The ``team_id`` query parameter, if provided and permitted.
    2. The first entry in ``request.state.permitted_teams`` otherwise.

    Returns a 403 if the requested team_id is not in the user's permitted list.
    Returns a "no assignments" page if the user has no permitted teams.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse containing the rendered game list page, or a 403.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    if not permitted_teams:
        return templates.TemplateResponse(
            request,
            "dashboard/game_list.html",
            {
                "games": [],
                "team_name": "",
                "permitted_team_infos": [],
                "active_team_id": None,
                "user": user,
                "no_assignments": True,
            },
        )

    # Parse team_id param and validate
    requested_team_id_raw = request.query_params.get("team_id")
    team_id_param_g: int | None = None
    if requested_team_id_raw:
        try:
            team_id_param_g = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if team_id_param_g not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)

    # Parse year param
    year_raw_g = request.query_params.get("year")
    year_param_g: int | None = None
    if year_raw_g:
        try:
            year_param_g = int(year_raw_g)
        except (ValueError, TypeError):
            year_param_g = None

    # Build team→year map and resolve active team + year
    team_year_map_g = await run_in_threadpool(db.get_team_year_map, permitted_teams)
    current_year = max(team_year_map_g.values()) if team_year_map_g else datetime.date.today().year
    active_team_id_g, active_year_g = _resolve_year_and_team(
        team_year_map_g, permitted_teams, team_id_param_g, year_param_g,
        current_year=current_year,
    )
    available_years_g: list[int] = sorted(set(team_year_map_g.values()), reverse=True)
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id_g)
    if not requested_season_id or year_param_g is not None:
        season_id = _pick_season_for_year(available_seasons, active_year_g, current_year)
    else:
        season_id = requested_season_id
    if not available_seasons:
        available_seasons = [{"season_id": season_id}]

    games_raw, team_infos = await _fetch_game_list_data(active_team_id_g, season_id, permitted_teams)

    # Annotate each game with W/L indicator and formatted score
    for game in games_raw:
        game["wl"] = _compute_wl(game, active_team_id_g)

    team_name = next(
        (t["name"] for t in team_infos if t["id"] == active_team_id_g),
        str(active_team_id_g),
    )

    logger.debug(
        "Game list: team=%s season_id=%s games=%d", active_team_id_g, season_id, len(games_raw)
    )

    # Determine which teams have real stat data (E-142-03 empty state)
    teams_with_stat_data_g = await run_in_threadpool(db.get_teams_with_stat_data, permitted_teams)

    # Filter team pills to only teams with data in the active year (Finding 1)
    year_team_infos_g = [t for t in team_infos if team_year_map_g.get(t["id"]) == active_year_g]
    if not year_team_infos_g:
        year_team_infos_g = team_infos
    for t in year_team_infos_g:
        t["has_stat_data"] = t["id"] in teams_with_stat_data_g

    return templates.TemplateResponse(
        request,
        "dashboard/game_list.html",
        {
            "games": games_raw,
            "team_name": team_name,
            "permitted_team_infos": year_team_infos_g,
            "active_team_id": active_team_id_g,
            "active_year": active_year_g,
            "available_years": available_years_g,
            "current_year": current_year,
            "season_id": season_id,
            "user": user,
            "no_assignments": False,
            "active_team_has_stat_data": active_team_id_g in teams_with_stat_data_g,
        },
    )


async def _fetch_game_list_data(
    active_team_id: int,
    season_id: str,
    permitted_teams: list[int],
) -> tuple[list, list]:
    """Fetch game list and team display names concurrently.

    Args:
        active_team_id: The team_id whose games to fetch.
        season_id: The season slug.
        permitted_teams: All team_ids the user can access.

    Returns:
        Tuple of (games list, team_infos list).
    """
    games = await run_in_threadpool(db.get_team_games, active_team_id, season_id)
    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)
    return games, team_infos


def _format_coverage_text(latest_game_date: str, game_count: int) -> str:
    """Format game coverage data as 'Through [date] ([N] games)'.

    Args:
        latest_game_date: Date string in ``YYYY-MM-DD`` format.
        game_count:       Number of completed games.

    Returns:
        Formatted coverage string, e.g. ``"Through Mar 25 (5 games)"``.
    """
    try:
        dt = datetime.datetime.strptime(latest_game_date, "%Y-%m-%d")
        # Abbreviated month + day without leading zero (e.g., "Mar 25").
        formatted_date = f"{dt.strftime('%b')} {dt.day}"
    except (ValueError, TypeError):
        formatted_date = latest_game_date
    game_word = "game" if game_count == 1 else "games"
    return f"Through {formatted_date} ({game_count} {game_word})"


def _compute_opponent_pitching_rates(pitchers: list[dict]) -> list[dict]:
    """Compute ERA, K/9, BB/9, WHIP, K/BB, and usage stats for each pitcher.

    Mutates each row in place by adding ``era``, ``k9``, ``bb9``, ``whip``,
    ``k_bb_ratio``, ``avg_pitches``, and ``strike_pct`` string keys.
    Division by zero (ip_outs == 0) yields ``"-"``.

    Args:
        pitchers: List of pitcher dicts from ``db.get_opponent_scouting_report``.

    Returns:
        The same list with computed rate fields added to each dict.
    """
    for row in pitchers:
        ip_outs = row.get("ip_outs") or 0
        er = row.get("er") or 0
        so = row.get("so") or 0
        bb = row.get("bb") or 0
        h = row.get("h") or 0
        games = row.get("games") or 0
        pitches = row.get("pitches") or 0
        total_strikes = row.get("total_strikes") or 0
        if ip_outs == 0:
            row["era"] = "-"
            row["k9"] = "-"
            row["bb9"] = "-"
            row["whip"] = "-"
        else:
            row["era"] = f"{(er * 27) / ip_outs:.2f}"
            row["k9"] = f"{(so * 27) / ip_outs:.1f}"
            row["bb9"] = f"{(bb * 27) / ip_outs:.1f}"
            row["whip"] = f"{(bb + h) * 3 / ip_outs:.2f}"
        row["k_bb_ratio"] = f"{so / bb:.1f}" if bb > 0 else "--"
        row["avg_pitches"] = str(pitches // games) if games > 0 else "-"
        row["strike_pct"] = f"{(total_strikes / pitches) * 100:.1f}%" if pitches > 0 else "-"
    return pitchers


def _get_top_pitchers(pitchers: list[dict], n: int = 3) -> list[dict]:
    """Return the top N pitchers sorted by innings pitched descending.

    Args:
        pitchers: List of pitcher dicts (with ``ip_outs`` already populated
                  and rate fields computed by ``_compute_opponent_pitching_rates``).
        n:        Maximum number of pitchers to return.

    Returns:
        List of up to *n* pitcher dicts, highest ip_outs first.
    """
    return sorted(
        (p for p in pitchers if (p.get("ip_outs") or 0) > 0),
        key=lambda p: p.get("ip_outs") or 0,
        reverse=True,
    )[:n]


def _enrich_pitchers_with_workload(
    pitchers: list[dict],
    workload: dict[str, dict],
    *,
    use_formatted_date: bool = False,
) -> None:
    """Merge workload data into pitcher dicts in place.

    Adds ``rest_display``, ``p7d_display``, and ``workload_subline`` keys to
    each pitcher dict for template rendering.

    Args:
        pitchers: List of pitcher dicts (mutated in place).
        workload: Dict from ``db.get_pitching_workload()`` keyed by player_id.
        use_formatted_date: When True, ``rest_display`` uses ``"Mar 28"``
            format (print view).  When False, uses ``"3d"`` / ``"Today"``
            format (dashboard).
    """
    for pitcher in pitchers:
        pid = pitcher.get("player_id")
        w = workload.get(pid) if pid else None
        if w is None:
            pitcher["rest_display"] = "\u2014"
            pitcher["p7d_display"] = "\u2014"
            pitcher["workload_subline"] = "No recent outings"
            continue

        # Rest / Last display
        days_ago = w["last_outing_days_ago"]
        last_date = w["last_outing_date"]
        if days_ago is None:
            pitcher["rest_display"] = "\u2014"
        elif use_formatted_date and last_date:
            pitcher["rest_display"] = _format_short_date(last_date)
        elif days_ago == 0:
            pitcher["rest_display"] = "Today"
        else:
            pitcher["rest_display"] = f"{days_ago}d"

        # P(7d) display -- branch on appearances_7d first (see E-210 TN)
        appearances = w["appearances_7d"]
        pitches_7d = w["pitches_7d"]
        if appearances is None:
            pitcher["p7d_display"] = "\u2014"
        elif pitches_7d is None:
            pitcher["p7d_display"] = f"?p ({appearances}g)"
        else:
            pitcher["p7d_display"] = f"{pitches_7d}p ({appearances}g)"

        # Workload sub-line for "Their Pitchers" card
        if days_ago is None:
            pitcher["workload_subline"] = "No recent outings"
        else:
            rest_part = "Today" if days_ago == 0 else f"{days_ago}d ago"
            pitcher["workload_subline"] = f"Last: {rest_part} \u00b7 {pitcher['p7d_display']}"


def _format_short_date(iso_date: str) -> str:
    """Format an ISO date as ``'Mar 28'`` for print views.

    Args:
        iso_date: Date string in ``YYYY-MM-DD`` format.

    Returns:
        Formatted date string like ``"Mar 28"``.
    """
    try:
        dt = datetime.datetime.strptime(iso_date, "%Y-%m-%d")
        return f"{dt.strftime('%b')} {dt.day}"
    except (ValueError, TypeError):
        return iso_date


def _compute_team_batting(batting: list[dict]) -> dict:
    """Compute team-level aggregate batting tendencies from player season rows.

    Aggregates OBP, K%, BB%, and SLG across all batters.  Returns a dict
    of formatted string values plus a ``has_data`` flag.

    Args:
        batting: List of batter dicts from ``db.get_opponent_scouting_report``
                 (must include ``tb`` field added in this story).

    Returns:
        Dict with keys: ``obp``, ``k_pct``, ``bb_pct``, ``slg``, ``has_data``.
        Rate values are formatted strings (e.g., ``".345"``, ``"18.2%"``).
        ``has_data`` is ``True`` when the denominators are non-zero.
    """
    total_h = sum(p.get("h") or 0 for p in batting)
    total_bb = sum(p.get("bb") or 0 for p in batting)
    total_hbp = sum(p.get("hbp") or 0 for p in batting)
    total_shf = sum(p.get("shf") or 0 for p in batting)
    total_so = sum(p.get("so") or 0 for p in batting)
    total_ab = sum(p.get("ab") or 0 for p in batting)
    total_tb = sum(p.get("tb") or 0 for p in batting)

    pa_denom = total_ab + total_bb + total_hbp + total_shf
    has_data = pa_denom > 0

    if not has_data:
        return {"obp": "-", "k_pct": "-", "bb_pct": "-", "slg": "-", "has_data": False}

    obp_num = total_h + total_bb + total_hbp
    obp_val = obp_num / pa_denom
    k_pct_val = total_so / pa_denom * 100
    bb_pct_val = total_bb / pa_denom * 100
    slg_val = total_tb / total_ab if total_ab > 0 else 0.0

    obp_str = f"{obp_val:.3f}".lstrip("0") if obp_val < 1 else f"{obp_val:.3f}"
    slg_str = f"{slg_val:.3f}".lstrip("0") if slg_val < 1 else f"{slg_val:.3f}"

    return {
        "obp": obp_str or ".000",
        "k_pct": f"{k_pct_val:.1f}%",
        "bb_pct": f"{bb_pct_val:.1f}%",
        "slg": slg_str or ".000",
        "has_data": True,
    }


def _is_admin_user(user: dict) -> bool:
    """Return True if *user* has admin access (ADMIN_EMAIL match or DB role).

    Mirrors the logic in ``admin.py::_require_admin`` without raising
    HTTP exceptions -- used for soft admin checks in dashboard routes.

    Args:
        user: The user dict from ``request.state.user``.

    Returns:
        True if the user has admin access, False otherwise.
    """
    import sqlite3 as _sqlite3
    from contextlib import closing as _closing

    if not user:
        return False
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if admin_email and user.get("email") == admin_email:
        return True
    user_id = user.get("id")
    if not user_id:
        return False
    try:
        with _closing(db.get_connection()) as conn:
            row = conn.execute(
                "SELECT role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return row is not None and row[0] == "admin"
    except _sqlite3.Error:
        logger.exception("Failed to check admin role for user %s", user_id)
        return False


def _pick_key_players(
    batting: list[dict],
    pitching: list[dict],
) -> dict:
    """Select the best hitter (min 5 AB) and best pitcher (min 9 ip_outs).

    Args:
        batting:  List of batting dicts from scouting report (pre-sorted by AVG).
        pitching: List of pitching dicts from scouting report (pre-sorted by ERA,
                  with era/k9/avg_pitches fields already computed).

    Returns:
        Dict with keys:
            - ``best_hitter``: dict with name, avg (str), games -- or None
            - ``best_pitcher``: dict with name, era, k9, avg_pitches, games -- or None
    """
    best_hitter = None
    for p in batting:
        if (p.get("ab") or 0) >= 5:
            ab = p["ab"]
            h = p.get("h") or 0
            avg = f"{h / ab:.3f}".lstrip("0") or ".000"
            best_hitter = {
                "name": p["name"],
                "avg": avg,
                "games": p.get("games") or 0,
            }
            break

    best_pitcher = None
    for p in pitching:
        if (p.get("ip_outs") or 0) >= 9:
            best_pitcher = {
                "name": p["name"],
                "era": p.get("era") or "-",
                "k9": p.get("k9") or "-",
                "avg_pitches": p.get("avg_pitches") or "-",
                "games": p.get("games") or 0,
            }
            break

    return {"best_hitter": best_hitter, "best_pitcher": best_pitcher}


@router.get("/dashboard/opponents", response_model=None)
async def opponent_list(request: Request) -> Response:
    """Render the opponent list page for the active team.

    Shows all opponents the team has faced or is scheduled to face this season,
    with game count, W-L record, and next or most-recent game date.

    The active team is determined by:
    1. The ``team_id`` query parameter, if provided and permitted.
    2. The first entry in ``request.state.permitted_teams`` otherwise.

    Returns 403 if the requested team_id is not permitted.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse containing the rendered opponent list page, or a 403.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    if not permitted_teams:
        return templates.TemplateResponse(
            request,
            "dashboard/opponent_list.html",
            {
                "opponents": [],
                "team_name": "",
                "permitted_team_infos": [],
                "active_team_id": None,
                "user": user,
                "no_assignments": True,
            },
        )

    # Parse team_id param and validate
    requested_team_id_raw = request.query_params.get("team_id")
    team_id_param_o: int | None = None
    if requested_team_id_raw:
        try:
            team_id_param_o = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if team_id_param_o not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)

    # Parse year param
    year_raw_o = request.query_params.get("year")
    year_param_o: int | None = None
    if year_raw_o:
        try:
            year_param_o = int(year_raw_o)
        except (ValueError, TypeError):
            year_param_o = None

    # Build team→year map and resolve active team + year
    team_year_map_o = await run_in_threadpool(db.get_team_year_map, permitted_teams)
    current_year = max(team_year_map_o.values()) if team_year_map_o else datetime.date.today().year
    active_team_id_o, active_year_o = _resolve_year_and_team(
        team_year_map_o, permitted_teams, team_id_param_o, year_param_o,
        current_year=current_year,
    )
    available_years_o: list[int] = sorted(set(team_year_map_o.values()), reverse=True)
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id_o)
    if not requested_season_id or year_param_o is not None:
        season_id = _pick_season_for_year(available_seasons, active_year_o, current_year)
    else:
        season_id = requested_season_id
    if not available_seasons:
        available_seasons = [{"season_id": season_id}]

    opponents, team_infos = await _fetch_opponent_list_data(active_team_id_o, season_id, permitted_teams)

    team_name = next(
        (t["name"] for t in team_infos if t["id"] == active_team_id_o),
        str(active_team_id_o),
    )

    logger.debug(
        "Opponent list: team=%s season_id=%s opponents=%d",
        active_team_id_o,
        season_id,
        len(opponents),
    )

    # Determine which teams have real stat data (E-142-03 empty state)
    teams_with_stat_data_o = await run_in_threadpool(db.get_teams_with_stat_data, permitted_teams)

    # Filter team pills to only teams with data in the active year (Finding 1)
    year_team_infos_o = [t for t in team_infos if team_year_map_o.get(t["id"]) == active_year_o]
    if not year_team_infos_o:
        year_team_infos_o = team_infos
    for t in year_team_infos_o:
        t["has_stat_data"] = t["id"] in teams_with_stat_data_o

    return templates.TemplateResponse(
        request,
        "dashboard/opponent_list.html",
        {
            "opponents": opponents,
            "team_name": team_name,
            "permitted_team_infos": year_team_infos_o,
            "active_team_id": active_team_id_o,
            "active_year": active_year_o,
            "available_years": available_years_o,
            "current_year": current_year,
            "season_id": season_id,
            "user": user,
            "no_assignments": False,
            "active_team_has_stat_data": active_team_id_o in teams_with_stat_data_o,
        },
    )


async def _fetch_opponent_list_data(
    active_team_id: int,
    season_id: str,
    permitted_teams: list[int],
) -> tuple[list, list]:
    """Fetch opponent list and team display names concurrently.

    Args:
        active_team_id: The team_id whose opponents to fetch.
        season_id: The season slug.
        permitted_teams: All team_ids the user can access.

    Returns:
        Tuple of (opponents list, team_infos list).
    """
    opponents = await run_in_threadpool(db.get_team_opponents, active_team_id, season_id)
    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)
    return opponents, team_infos


# ---------------------------------------------------------------------------
# Heat-map helpers for opponent detail (E-189-04)
# ---------------------------------------------------------------------------

_BATTING_HEAT_TIERS = [(9, 4), (7, 3), (5, 2), (3, 1)]   # 0-2 qualified = max 0
_PITCHING_HEAT_TIERS = [(6, 4), (4, 3), (3, 2), (2, 1)]   # 0-1 qualified = max 0
_HEAT_THRESHOLDS = [(0.70, 4), (0.40, 3), (0.20, 2), (0.0, 1)]
_MIN_PA_BATTING = 5
_MIN_OUTS_PITCHING = 18  # 6 IP


def _max_heat_for_depth(
    qualified_count: int,
    tiers: list[tuple[int, int]],
) -> int:
    """Return the maximum heat level for a given number of qualified players."""
    for min_count, max_level in tiers:
        if qualified_count >= min_count:
            return max_level
    return 0


def _percentile_rank(value: float, values: list[float]) -> float:
    """Compute percentile rank of value within values. Returns 0-1."""
    if not values:
        return 0.0
    count_le = sum(1 for v in values if v <= value)
    return count_le / len(values)


def _percentile_to_level(pct: float) -> int:
    """Map a percentile (0-1) to a heat level (1-4)."""
    for threshold, level in _HEAT_THRESHOLDS:
        if pct >= threshold:
            return level
    return 1


def _compute_batting_heat(batting: list[dict]) -> None:
    """Compute PA and heat levels for each batter. Mutates rows in place.

    Adds ``_pa`` (int) and ``_heat`` (dict with avg/obp/slg keys, values 0-4)
    to each player dict.
    """
    for p in batting:
        pa = (p.get("ab") or 0) + (p.get("bb") or 0) + (p.get("hbp") or 0) + (p.get("shf") or 0)
        p["_pa"] = pa

    qualified = [p for p in batting if p["_pa"] >= _MIN_PA_BATTING]
    cap = _max_heat_for_depth(len(qualified), _BATTING_HEAT_TIERS)

    if cap == 0 or not qualified:
        for p in batting:
            p["_heat"] = {"avg": 0, "obp": 0, "slg": 0}
        return

    # Compute raw rate values for qualified players.
    for p in qualified:
        pa = p["_pa"]
        ab = p.get("ab") or 0
        p["_avg_raw"] = (p.get("h") or 0) / ab if ab else 0.0
        p["_obp_raw"] = ((p.get("h") or 0) + (p.get("bb") or 0) + (p.get("hbp") or 0)) / pa if pa else 0.0
        tb = (p.get("h") or 0) + (p.get("doubles") or 0) + 2 * (p.get("triples") or 0) + 3 * (p.get("hr") or 0)
        p["_slg_raw"] = tb / ab if ab else 0.0

    avg_vals = [p["_avg_raw"] for p in qualified]
    obp_vals = [p["_obp_raw"] for p in qualified]
    slg_vals = [p["_slg_raw"] for p in qualified]

    for p in qualified:
        p["_heat"] = {
            "avg": min(_percentile_to_level(_percentile_rank(p["_avg_raw"], avg_vals)), cap),
            "obp": min(_percentile_to_level(_percentile_rank(p["_obp_raw"], obp_vals)), cap),
            "slg": min(_percentile_to_level(_percentile_rank(p["_slg_raw"], slg_vals)), cap),
        }
        # Clean up temp keys.
        p.pop("_avg_raw", None)
        p.pop("_obp_raw", None)
        p.pop("_slg_raw", None)

    # Unqualified players get zero heat.
    for p in batting:
        if "_heat" not in p:
            p["_heat"] = {"avg": 0, "obp": 0, "slg": 0}


def _compute_pitching_heat(pitching: list[dict]) -> None:
    """Compute heat levels for each pitcher. Mutates rows in place.

    Adds ``_heat`` (dict with era/k9/whip keys, values 0-4) to each pitcher dict.
    """
    qualified = [p for p in pitching if (p.get("ip_outs") or 0) >= _MIN_OUTS_PITCHING]
    cap = _max_heat_for_depth(len(qualified), _PITCHING_HEAT_TIERS)

    if cap == 0 or not qualified:
        for p in pitching:
            p["_heat"] = {"era": 0, "k9": 0, "whip": 0}
        return

    for p in qualified:
        outs = p.get("ip_outs") or 0
        ip = outs / 3.0
        p["_era_raw"] = ((p.get("er") or 0) * 9.0 / ip) if ip else 99.0
        p["_k9_raw"] = ((p.get("so") or 0) * 9.0 / ip) if ip else 0.0
        p["_whip_raw"] = (((p.get("bb") or 0) + (p.get("h") or 0)) / ip) if ip else 99.0

    # ERA and WHIP are inverted (lower is better).
    neg_era_vals = [-p["_era_raw"] for p in qualified]
    k9_vals = [p["_k9_raw"] for p in qualified]
    neg_whip_vals = [-p["_whip_raw"] for p in qualified]

    for p in qualified:
        p["_heat"] = {
            "era": min(_percentile_to_level(_percentile_rank(-p["_era_raw"], neg_era_vals)), cap),
            "k9": min(_percentile_to_level(_percentile_rank(p["_k9_raw"], k9_vals)), cap),
            "whip": min(_percentile_to_level(_percentile_rank(-p["_whip_raw"], neg_whip_vals)), cap),
        }
        p.pop("_era_raw", None)
        p.pop("_k9_raw", None)
        p.pop("_whip_raw", None)

    for p in pitching:
        if "_heat" not in p:
            p["_heat"] = {"era": 0, "k9": 0, "whip": 0}


@router.get("/dashboard/opponents/{opponent_team_id}", response_model=None)
async def opponent_detail(request: Request, opponent_team_id: int) -> Response:
    """Render the opponent scouting report page.

    Shows pitching card, team batting summary, last meeting, and full stat
    tables for the opponent team.  Handles three states: full stats, linked
    but unscouted, and unlinked.

    Authorization: the opponent must appear in games for at least one of the
    user's permitted teams.  Returns 403 otherwise.

    Args:
        request:          The incoming HTTP request.
        opponent_team_id: The opponent's team_id from the URL path.

    Returns:
        HTMLResponse containing the rendered scouting report page, or a 403.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    # Verify opponent appears in games for at least one permitted team.
    authorized = await run_in_threadpool(
        _check_opponent_authorization, opponent_team_id, permitted_teams
    )
    if not authorized:
        return HTMLResponse(content="Forbidden", status_code=403)

    # Determine active team for Last Meeting and opponent_links scope.
    requested_team_id_raw = request.query_params.get("team_id")
    if requested_team_id_raw:
        try:
            requested_team_id_od: int | None = int(requested_team_id_raw)
        except (ValueError, TypeError):
            requested_team_id_od = None
        if requested_team_id_od is not None and requested_team_id_od in permitted_teams:
            active_team_id_od: int | None = requested_team_id_od
        else:
            active_team_id_od = permitted_teams[0] if permitted_teams else None
    else:
        active_team_id_od = permitted_teams[0] if permitted_teams else None

    current_year = datetime.date.today().year
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons_opp = await run_in_threadpool(db.get_available_seasons, opponent_team_id)
    if not requested_season_id:
        season_id = (
            available_seasons_opp[0]["season_id"]
            if available_seasons_opp
            else f"{current_year}-spring-hs"
        )
    else:
        season_id = requested_season_id

    scouting_report, team_infos = await _fetch_opponent_detail_data(
        opponent_team_id, season_id, permitted_teams
    )

    if not scouting_report:
        return HTMLResponse(content="Internal error fetching scouting report", status_code=500)

    # Determine empty state (unlinked / linked_unscouted / full_stats).
    scouting_status = await run_in_threadpool(
        db.get_opponent_scouting_status,
        opponent_team_id,
        active_team_id_od,
        season_id,
    )
    empty_state: str = scouting_status["status"]
    link_id: int | None = scouting_status["link_id"]

    # Admin detection for conditional shortcut link.
    is_admin = await run_in_threadpool(_is_admin_user, user)
    if link_id is not None:
        admin_link_url = f"/admin/opponents/{link_id}/connect"
    else:
        admin_link_url = "/admin/opponents"

    # Compute pitching rates.
    pitchers = _compute_opponent_pitching_rates(scouting_report.get("pitching", []))

    # Enrich pitchers with workload data BEFORE _get_top_pitchers so cards
    # also carry workload sub-lines.
    workload = await run_in_threadpool(
        db.get_pitching_workload,
        opponent_team_id,
        season_id,
        datetime.date.today().isoformat(),
    )
    _enrich_pitchers_with_workload(pitchers, workload)
    scouting_report["pitching"] = pitchers

    # Top 3 pitchers for the pitching card (by innings pitched).
    top_pitchers = _get_top_pitchers(pitchers)

    # Team batting summary card.
    team_batting = _compute_team_batting(scouting_report.get("batting", []))

    # Game count from the season record.
    record = scouting_report.get("record")
    game_count = (record["wins"] + record["losses"]) if record else 0

    # Opponent batting sort params -- subset per TN-3, see _OPP_BAT_KEYS
    bat_sort, bat_dir, bat_needs_sort = _parse_sort_params(
        request, "bat_sort", "bat_dir", _OPP_BAT_KEYS, "avg", _BATTING_DEFAULT_DIR,
    )
    if bat_needs_sort:
        scouting_report["batting"] = _sort_batting(scouting_report.get("batting", []), bat_sort, bat_dir)

    # Opponent pitching sort params -- subset per TN-3, see _OPP_PIT_KEYS
    pit_sort, pit_dir, pit_needs_sort = _parse_sort_params(
        request, "pit_sort", "pit_dir", _OPP_PIT_KEYS, "era", _PITCHING_DEFAULT_DIR,
    )
    if pit_needs_sort:
        scouting_report["pitching"] = _sort_pitching(scouting_report.get("pitching", []), pit_sort, pit_dir)

    # Compute heat-map levels (E-189-04).
    _compute_batting_heat(scouting_report.get("batting", []))
    _compute_pitching_heat(scouting_report.get("pitching", []))

    # Predicted starter (Tier 1 only -- no LLM on dashboard).
    starter_prediction = None
    from src.reports.starter_prediction import is_predicted_starter_enabled
    if is_predicted_starter_enabled():
        try:
            pitching_history_rows = await run_in_threadpool(
                db.get_pitching_history, opponent_team_id, season_id,
            )
            if pitching_history_rows:
                from src.reports.starter_prediction import (
                    compute_starter_prediction,
                    detect_league_level,
                )

                league_info = await run_in_threadpool(
                    db.get_team_league_info, opponent_team_id,
                )
                league = detect_league_level(
                    program_type=league_info.get("program_type"),
                    classification=league_info.get("classification"),
                    team_name=league_info.get("team_name"),
                )

                pitcher_profiles = db.build_pitcher_profiles(pitching_history_rows)
                starter_prediction = compute_starter_prediction(
                    pitcher_profiles, pitching_history_rows,
                    reference_date=datetime.date.today(),
                    workload=workload,
                    league=league,
                )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Predicted starter failed for opponent %d; continuing without.",
                opponent_team_id,
                exc_info=True,
            )

    # Fetch last meeting.
    last_meeting = None
    if active_team_id_od:
        last_meeting = await run_in_threadpool(
            db.get_last_meeting, active_team_id_od, opponent_team_id, season_id
        )

    year_od_raw = request.query_params.get("year")
    year_od: int | None = None
    if year_od_raw:
        try:
            year_od = int(year_od_raw)
        except (ValueError, TypeError):
            year_od = None

    # Spray chart context: team aggregate count + per-player counts.
    team_spray_bip_count: int = await run_in_threadpool(
        db.get_team_spray_bip_count, opponent_team_id, season_id
    )
    batting_player_ids = [p["player_id"] for p in scouting_report.get("batting", [])]
    player_spray_bip_counts: dict[str, int] = await run_in_threadpool(
        db.get_player_spray_bip_counts, batting_player_ids, season_id
    )

    # Classify team-level spray events for zone/contact stats below team chart.
    team_spray_events_od, _ = await run_in_threadpool(
        db.get_team_spray_events, opponent_team_id, season_id
    )
    from src.charts.spray import classify_field_zone, contact_type_label

    team_spray_zones: dict[str, int] = {"left": 0, "center": 0, "right": 0}
    team_spray_contacts: dict[str, int] = {"gb": 0, "ld": 0, "fb": 0, "pu": 0, "bu": 0}
    for ev in team_spray_events_od:
        x = ev.get("x")
        y = ev.get("y")
        if x is not None and y is not None:
            zone = classify_field_zone(x, y)
            team_spray_zones[zone] += 1
        ct = contact_type_label(ev.get("play_type"))
        if ct:
            team_spray_contacts[ct] += 1

    # Game coverage indicator (E-181-02): "Through [date] ([N] games)".
    game_coverage = await run_in_threadpool(db.get_game_coverage, opponent_team_id)
    coverage_text: str | None = None
    if game_coverage:
        coverage_text = _format_coverage_text(
            game_coverage["latest_game_date"], game_coverage["game_count"]
        )

    logger.debug(
        "Opponent detail: opponent=%s season_id=%s empty_state=%s bat_sort=%s pit_sort=%s",
        opponent_team_id, season_id, empty_state, bat_sort, pit_sort,
    )

    return templates.TemplateResponse(
        request,
        "dashboard/opponent_detail.html",
        {
            "scouting_report": scouting_report,
            "opponent_team_id": opponent_team_id,
            "last_meeting": last_meeting,
            "active_team_id": active_team_id_od,
            "permitted_team_infos": team_infos,
            "season_id": season_id,
            "year": year_od,
            "active_year": year_od,
            "user": user,
            "bat_sort": bat_sort,
            "bat_dir": bat_dir,
            "pit_sort": pit_sort,
            "pit_dir": pit_dir,
            "empty_state": empty_state,
            "is_admin": is_admin,
            "admin_link_url": admin_link_url,
            "top_pitchers": top_pitchers,
            "team_batting": team_batting,
            "game_count": game_count,
            "team_spray_bip_count": team_spray_bip_count,
            "player_spray_bip_counts": player_spray_bip_counts,
            "team_spray_zones": team_spray_zones,
            "team_spray_contacts": team_spray_contacts,
            "coverage_text": coverage_text,
            "starter_prediction": starter_prediction,
        },
    )


@router.get("/dashboard/opponents/{opponent_team_id}/print", response_model=None)
async def opponent_print(request: Request, opponent_team_id: int) -> Response:
    """Render the print-optimized opponent scouting report.

    Shows a self-contained print layout: report header, context bar, full
    pitching table (page 1), full batting table with spray chart placeholders
    (page 2+).  Uses inline CSS only — does not extend base.html.

    Authorization: same as ``opponent_detail`` — opponent must appear in games
    for at least one permitted team.  Returns 403 otherwise.

    Args:
        request:          The incoming HTTP request.
        opponent_team_id: The opponent's team_id from the URL path.

    Returns:
        HTMLResponse containing the rendered print scouting report, or a 403.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])

    authorized = await run_in_threadpool(
        _check_opponent_authorization, opponent_team_id, permitted_teams
    )
    if not authorized:
        return HTMLResponse(content="Forbidden", status_code=403)

    # Determine active team for Last Meeting and scouting-status scope.
    requested_team_id_raw = request.query_params.get("team_id")
    if requested_team_id_raw:
        try:
            requested_team_id_pr: int | None = int(requested_team_id_raw)
        except (ValueError, TypeError):
            requested_team_id_pr = None
        if requested_team_id_pr is not None and requested_team_id_pr in permitted_teams:
            active_team_id_pr: int | None = requested_team_id_pr
        else:
            active_team_id_pr = permitted_teams[0] if permitted_teams else None
    else:
        active_team_id_pr = permitted_teams[0] if permitted_teams else None

    current_year = datetime.date.today().year
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons_pr = await run_in_threadpool(db.get_available_seasons, opponent_team_id)
    if not requested_season_id:
        season_id = (
            available_seasons_pr[0]["season_id"]
            if available_seasons_pr
            else f"{current_year}-spring-hs"
        )
    else:
        season_id = requested_season_id

    scouting_report, _team_infos = await _fetch_opponent_detail_data(
        opponent_team_id, season_id, permitted_teams
    )

    if not scouting_report:
        return HTMLResponse(content="Internal error fetching scouting report", status_code=500)

    # Determine empty state (unlinked / linked_unscouted / full_stats).
    scouting_status = await run_in_threadpool(
        db.get_opponent_scouting_status,
        opponent_team_id,
        active_team_id_pr,
        season_id,
    )
    empty_state: str = scouting_status["status"]

    # Compute pitching rates and enrich with workload data.
    pitchers = _compute_opponent_pitching_rates(scouting_report.get("pitching", []))
    workload_pr = await run_in_threadpool(
        db.get_pitching_workload,
        opponent_team_id,
        season_id,
        datetime.date.today().isoformat(),
    )
    _enrich_pitchers_with_workload(pitchers, workload_pr, use_formatted_date=True)
    scouting_report["pitching"] = _sort_pitching(pitchers, "era", "asc")
    scouting_report["batting"] = _sort_batting(scouting_report.get("batting", []), "avg", "desc")

    # Predicted starter (Tier 1 only -- no LLM on dashboard).
    starter_prediction_pr = None
    from src.reports.starter_prediction import is_predicted_starter_enabled
    if is_predicted_starter_enabled():
        try:
            pitching_history_pr = await run_in_threadpool(
                db.get_pitching_history, opponent_team_id, season_id,
            )
            if pitching_history_pr:
                from src.reports.starter_prediction import (
                    compute_starter_prediction,
                    detect_league_level,
                )

                league_info_pr = await run_in_threadpool(
                    db.get_team_league_info, opponent_team_id,
                )
                league_pr = detect_league_level(
                    program_type=league_info_pr.get("program_type"),
                    classification=league_info_pr.get("classification"),
                    team_name=league_info_pr.get("team_name"),
                )

                pitcher_profiles_pr = db.build_pitcher_profiles(pitching_history_pr)
                starter_prediction_pr = compute_starter_prediction(
                    pitcher_profiles_pr, pitching_history_pr,
                    reference_date=datetime.date.today(),
                    workload=workload_pr,
                    league=league_pr,
                )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Predicted starter failed for opponent %d (print); continuing without.",
                opponent_team_id,
                exc_info=True,
            )

    # Team batting summary for context bar.
    team_batting = _compute_team_batting(scouting_report.get("batting", []))

    # Compute PA for badges (E-189-04). Heat computed but only PA/IP used in print.
    _compute_batting_heat(scouting_report.get("batting", []))

    # Fetch last meeting.
    last_meeting = None
    if active_team_id_pr:
        last_meeting = await run_in_threadpool(
            db.get_last_meeting, active_team_id_pr, opponent_team_id, season_id
        )

    # Optional year param — round-trip context only, not used in data-fetching.
    year_pr_raw = request.query_params.get("year")
    year_pr: int | None = None
    if year_pr_raw:
        try:
            year_pr = int(year_pr_raw)
        except (ValueError, TypeError):
            year_pr = None

    today = datetime.date.today()
    print_date = f"{today.strftime('%B')} {today.day}, {today.year}"

    # Per-player spray events for the Batter Tendencies grid.  Pass the
    # opponent team id as the explicit perspective so a batter who also
    # appeared on another team in the same season does not contribute
    # cross-team events (Codex Phase 4b MUST FIX 1).
    batting_list_pr = scouting_report.get("batting", [])
    batting_player_ids_pr = [p["player_id"] for p in batting_list_pr]

    def _fetch_player_spray_events_pr() -> dict[str, list[dict]]:
        return db.get_players_spray_events_batch(
            batting_player_ids_pr,
            season_id,
            perspective_team_id=opponent_team_id,
        )

    player_spray_events_pr: dict[str, list[dict]] = await run_in_threadpool(
        _fetch_player_spray_events_pr
    )

    # Build per-player BIP counts (backward compat) and enriched spray stats.
    player_spray_bip_counts_pr: dict[str, int] = {
        pid: len(evts) for pid, evts in player_spray_events_pr.items()
    }

    # Build enriched stats dict for all batters.
    from src.charts.spray import classify_field_zone, contact_type_label, format_baseball_stat

    tendency_stats_pr: dict[str, dict] = {}
    for player in batting_list_pr:
        pid = player["player_id"]
        h = player.get("h") or 0
        ab = player.get("ab") or 0
        bb = player.get("bb") or 0
        hbp = player.get("hbp") or 0
        shf = player.get("shf") or 0
        doubles = player.get("doubles") or 0
        triples = player.get("triples") or 0
        hr = player.get("hr") or 0
        pa = player.get("_pa", 0)

        # OBP/SLG recomputed from raw fields per TN-3
        obp_denom = ab + bb + hbp + shf
        avg = format_baseball_stat(h, ab)
        obp = format_baseball_stat(h + bb + hbp, obp_denom)
        slg = format_baseball_stat(h + doubles + 2 * triples + 3 * hr, ab)

        events = player_spray_events_pr.get(pid, [])
        zones: dict[str, int] = {"left": 0, "center": 0, "right": 0}
        contacts: dict[str, int] = {"gb": 0, "ld": 0, "fb": 0, "pu": 0, "bu": 0}
        for ev in events:
            x = ev.get("x")
            y = ev.get("y")
            if x is not None and y is not None:
                zone = classify_field_zone(x, y)
                zones[zone] += 1
            ct = contact_type_label(ev.get("play_type"))
            if ct:
                contacts[ct] += 1

        tendency_stats_pr[pid] = {
            "avg": avg,
            "obp": obp,
            "slg": slg,
            "pa": pa,
            "bip_count": len(events),
            "jersey_number": player.get("jersey_number"),
            "zones": zones,
            "contacts": contacts,
        }

    # Game coverage indicator (E-181-02): "Through [date] ([N] games)".
    game_coverage_pr = await run_in_threadpool(db.get_game_coverage, opponent_team_id)
    coverage_text_pr: str | None = None
    if game_coverage_pr:
        coverage_text_pr = _format_coverage_text(
            game_coverage_pr["latest_game_date"], game_coverage_pr["game_count"]
        )

    logger.debug(
        "Opponent print: opponent=%s season_id=%s empty_state=%s",
        opponent_team_id,
        season_id,
        empty_state,
    )

    return templates.TemplateResponse(
        request,
        "dashboard/opponent_print.html",
        {
            "scouting_report": scouting_report,
            "opponent_team_id": opponent_team_id,
            "last_meeting": last_meeting,
            "active_team_id": active_team_id_pr,
            "season_id": season_id,
            "year": year_pr,
            "team_batting": team_batting,
            "empty_state": empty_state,
            "print_date": print_date,
            "player_spray_bip_counts": player_spray_bip_counts_pr,
            "tendency_stats": tendency_stats_pr,
            "coverage_text": coverage_text_pr,
            "starter_prediction": starter_prediction_pr,
        },
    )


def _check_opponent_authorization(
    opponent_team_id: int,
    permitted_teams: list[int],
) -> bool:
    """Return True if the opponent appears in games for at least one permitted team.

    Args:
        opponent_team_id: The opponent's team_id.
        permitted_teams:  The user's permitted team_ids.

    Returns:
        True if authorized, False otherwise.
    """
    import sqlite3 as _sqlite3
    from contextlib import closing as _closing

    if not permitted_teams:
        return False
    placeholders = ",".join("?" for _ in permitted_teams)
    query = f"""
        SELECT 1 FROM games
        WHERE (home_team_id = ? OR away_team_id = ?)
          AND (home_team_id IN ({placeholders}) OR away_team_id IN ({placeholders}))
        LIMIT 1
    """
    params = [opponent_team_id, opponent_team_id] + permitted_teams + permitted_teams
    try:
        with _closing(db.get_connection()) as conn:
            row = conn.execute(query, params).fetchone()
        return row is not None
    except _sqlite3.Error:
        logger.exception("Failed to check opponent authorization")
        return False


async def _fetch_opponent_detail_data(
    opponent_team_id: int,
    season_id: str,
    permitted_teams: list[int],
) -> tuple[dict, list]:
    """Fetch scouting report and team display names.

    Args:
        opponent_team_id: The opponent's team_id.
        season_id: The season slug.
        permitted_teams: All team_ids the user can access.

    Returns:
        Tuple of (scouting_report dict, team_infos list).
    """
    report = await run_in_threadpool(db.get_opponent_scouting_report, opponent_team_id, season_id)
    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)
    return report, team_infos


@router.get("/dashboard/games/{game_id}", response_model=None)
async def game_detail(request: Request, game_id: str) -> Response:
    """Render the game detail box score page.

    Shows batting and pitching lines for both teams in a collapsible
    ``<details>/<summary>`` layout.  The user's active team section is open
    by default; the opponent section is collapsed.

    Authorization: the game must involve at least one of the user's permitted
    teams.  Returns 403 otherwise.

    Args:
        request: The incoming HTTP request.
        game_id: The game identifier from the URL path.

    Returns:
        HTMLResponse containing the rendered box score page, or a 403/404.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    box_score = await run_in_threadpool(db.get_game_box_score, game_id)

    if not box_score:
        return HTMLResponse(content="Game not found", status_code=404)

    game = box_score["game"]
    team_ids_in_game: set[int] = {game["home_team_id"], game["away_team_id"]}

    # AC-11: verify game involves at least one permitted team
    if not team_ids_in_game.intersection(permitted_teams):
        return HTMLResponse(content="Forbidden", status_code=403)

    # Determine active_team_id for the details open attribute
    requested_team_id_raw = request.query_params.get("team_id")
    if requested_team_id_raw:
        try:
            requested_team_id_gd: int | None = int(requested_team_id_raw)
        except (ValueError, TypeError):
            requested_team_id_gd = None
        if requested_team_id_gd is not None and requested_team_id_gd in permitted_teams:
            active_team_id_gd: int | None = requested_team_id_gd
        else:
            active_team_id_gd = next(
                (t for t in permitted_teams if t in team_ids_in_game),
                permitted_teams[0] if permitted_teams else None,
            )
    else:
        # Use first permitted team that appears in this game; fall back to first permitted
        active_team_id_gd = next(
            (t for t in permitted_teams if t in team_ids_in_game),
            permitted_teams[0] if permitted_teams else None,
        )

    team_infos = await run_in_threadpool(db.get_teams_by_ids, list(permitted_teams))
    season_id_gd = request.query_params.get("season_id", "").strip()

    # AC-7: pass year through for back-links
    year_gd_raw = request.query_params.get("year")
    year_gd: int | None = None
    if year_gd_raw:
        try:
            year_gd = int(year_gd_raw)
        except (ValueError, TypeError):
            year_gd = None

    # Compute strike_pct for each team's pitching lines
    teams = box_score["teams"]
    for team in teams:
        _compute_game_pitching_rates(team.get("pitching_lines", []))

    logger.debug("Game detail: game_id=%s active_team_id=%s", game_id, active_team_id_gd)

    return templates.TemplateResponse(
        request,
        "dashboard/game_detail.html",
        {
            "game": game,
            "teams": teams,
            "active_team_id": active_team_id_gd,
            "season_id": season_id_gd,
            "year": year_gd,
            "active_year": year_gd,
            "permitted_team_infos": team_infos,
            "user": user,
        },
    )


def _compute_player_pitching_rates(pitching_seasons: list[dict]) -> list[dict]:
    """Compute ERA, K/9, and WHIP for each pitching season row.

    Mutates each row in place.  Division by zero (ip_outs == 0) yields ``"-"``.

    Args:
        pitching_seasons: List of pitching season dicts from ``db.get_player_profile``.

    Returns:
        The same list with ``era``, ``k9``, and ``whip`` fields added to each dict.
    """
    for row in pitching_seasons:
        ip_outs = row.get("ip_outs") or 0
        er = row.get("er") or 0
        so = row.get("so") or 0
        bb = row.get("bb") or 0
        h = row.get("h") or 0
        pitches = row.get("pitches") or 0
        total_strikes = row.get("total_strikes") or 0
        if ip_outs == 0:
            row["era"] = "-"
            row["k9"] = "-"
            row["whip"] = "-"
        else:
            row["era"] = f"{(er * 27) / ip_outs:.2f}"
            row["k9"] = f"{(so * 27) / ip_outs:.1f}"
            row["whip"] = f"{(bb + h) * 3 / ip_outs:.2f}"
        row["strike_pct"] = f"{(total_strikes / pitches) * 100:.1f}%" if pitches > 0 else "-"
    return pitching_seasons


def _compute_game_pitching_rates(pitchers: list[dict]) -> list[dict]:
    """Compute strike_pct for each pitcher row in a game box score.

    Mutates each row in place by adding a ``strike_pct`` string key.
    When ``pitches`` is 0 or NULL, yields ``"-"``.

    Args:
        pitchers: List of pitcher dicts from ``db.get_game_box_score``.

    Returns:
        The same list with ``strike_pct`` field added to each dict.
    """
    for row in pitchers:
        pitches = row.get("pitches") or 0
        total_strikes = row.get("total_strikes") or 0
        row["strike_pct"] = f"{(total_strikes / pitches) * 100:.1f}%" if pitches > 0 else "-"
    return pitchers


def _check_player_authorization(
    player_id: str,
    permitted_teams: list[int],
) -> bool:
    """Return True if the player has a team_rosters entry on any permitted team.

    Args:
        player_id:       The player's UUID.
        permitted_teams: The user's permitted team_ids.

    Returns:
        True if authorized, False otherwise.
    """
    import sqlite3 as _sqlite3
    from contextlib import closing as _closing

    if not permitted_teams:
        return False
    placeholders = ",".join("?" for _ in permitted_teams)
    query = f"""
        SELECT 1 FROM team_rosters
        WHERE player_id = ?
          AND team_id IN ({placeholders})
        LIMIT 1
    """
    params = [player_id] + permitted_teams
    try:
        with _closing(db.get_connection()) as conn:
            row = conn.execute(query, params).fetchone()
        return row is not None
    except _sqlite3.Error:
        logger.exception("Failed to check player authorization")
        return False


@router.get("/dashboard/players/{player_id}", response_model=None)
async def player_profile(request: Request, player_id: str) -> Response:
    """Render the player career profile page.

    Shows current season summary, batting by season, pitching by season,
    and recent games for the given player.

    Authorization: the player must appear on at least one of the user's
    permitted teams (current or historical ``team_rosters`` entry).
    Returns 403 otherwise.  Returns 404 if the player_id does not exist.

    Args:
        request:   The incoming HTTP request.
        player_id: The player's UUID from the URL path.

    Returns:
        HTMLResponse containing the rendered player profile page, or a 403/404.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    user: dict = getattr(request.state, "user", {})

    profile = await run_in_threadpool(db.get_player_profile, player_id)

    if not profile:
        return HTMLResponse(content="Player not found", status_code=404)

    # AC-10: verify player has roster entry on at least one permitted team
    authorized = await run_in_threadpool(
        _check_player_authorization, player_id, permitted_teams
    )
    if not authorized:
        return HTMLResponse(content="Forbidden", status_code=403)

    team_infos = await run_in_threadpool(db.get_teams_by_ids, permitted_teams)

    pitching_seasons = _compute_player_pitching_rates(profile.get("pitching_seasons", []))

    # Current season summary: most recent season_id's batting/pitching rows
    current_batting: dict | None = None
    current_pitching: dict | None = None

    batting_seasons = profile.get("batting_seasons", [])
    if batting_seasons:
        current_batting = batting_seasons[0]  # already sorted by season_id DESC

    if pitching_seasons:
        current_pitching = pitching_seasons[0]  # already sorted by season_id DESC

    # Backlink should go to a permitted team, not an opponent team from scouting
    permitted_set = set(permitted_teams)
    backlink_team_id: int | None = next(
        (s["team_id"] for s in batting_seasons if s["team_id"] in permitted_set),
        next(
            (s["team_id"] for s in pitching_seasons if s["team_id"] in permitted_set),
            permitted_teams[0] if permitted_teams else None,
        ),
    )

    # AC-7: pass year through for back-links
    year_pp_raw = request.query_params.get("year")
    year_pp: int | None = None
    if year_pp_raw:
        try:
            year_pp = int(year_pp_raw)
        except (ValueError, TypeError):
            year_pp = None

    # Resolve spray chart season: use the most recent batting season when available,
    # otherwise fall back to the most recent season with spray data.
    spray_season_id: str | None = (
        current_batting["season_id"] if current_batting is not None else None
    )
    if spray_season_id is None and pitching_seasons:
        spray_season_id = pitching_seasons[0]["season_id"]

    if spray_season_id is not None:
        spray_events_pp, _ = await run_in_threadpool(
            db.get_player_spray_events, player_id, spray_season_id
        )
        spray_bip_count: int = len(spray_events_pp)
    else:
        spray_events_pp = []
        spray_bip_count = 0

    # Classify spray events into zones and contact types.
    from src.charts.spray import classify_field_zone, contact_type_label

    spray_zones: dict[str, int] = {"left": 0, "center": 0, "right": 0}
    spray_contacts: dict[str, int] = {"gb": 0, "ld": 0, "fb": 0, "pu": 0, "bu": 0}
    for ev in spray_events_pp:
        x = ev.get("x")
        y = ev.get("y")
        if x is not None and y is not None:
            zone = classify_field_zone(x, y)
            spray_zones[zone] += 1
        ct = contact_type_label(ev.get("play_type"))
        if ct:
            spray_contacts[ct] += 1

    logger.debug("Player profile: player_id=%s", player_id)

    return templates.TemplateResponse(
        request,
        "dashboard/player_profile.html",
        {
            "player": profile["player"],
            "batting_seasons": batting_seasons,
            "pitching_seasons": pitching_seasons,
            "recent_games": profile.get("recent_games", []),
            "current_batting": current_batting,
            "current_pitching": current_pitching,
            "permitted_team_infos": team_infos,
            "backlink_team_id": backlink_team_id,
            "year": year_pp,
            "active_year": year_pp,
            "user": user,
            "spray_bip_count": spray_bip_count,
            "spray_season_id": spray_season_id,
            "spray_zones": spray_zones,
            "spray_contacts": spray_contacts,
        },
    )


@router.get("/dashboard/charts/spray/player/{player_id}.png", response_model=None)
async def player_spray_chart_image(
    request: Request,
    player_id: str,
    season_id: str | None = None,
) -> Response:
    """Render an offensive spray chart PNG for a single player.

    Returns the rendered PNG image when the player has ≥1 offensive BIP event
    for the requested season.  Returns 204 No Content when no events exist.

    When ``season_id`` is omitted, uses the most recent season with spray data
    for this player.

    Authorization: requires an authenticated session (``permitted_teams`` must
    be non-empty) but deliberately skips the per-player ``permitted_teams``
    check.  Reason: opponent players cannot pass ``permitted_teams`` but their
    spray data is legitimately viewable (spray chart auth exception, per
    CLAUDE.md Architecture section).

    Args:
        request:   The incoming HTTP request.
        player_id: The player's UUID from the URL path.
        season_id: Optional season slug query parameter.

    Returns:
        200 ``image/png`` response with rendered PNG bytes, or 204 No Content.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    if not permitted_teams:
        return HTMLResponse(content="Forbidden", status_code=403)

    events, _title = await run_in_threadpool(db.get_player_spray_events, player_id, season_id)

    if not events:
        return Response(status_code=204)

    png_bytes: bytes = await run_in_threadpool(render_spray_chart, events, None)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/dashboard/charts/spray/team/{team_id}.png", response_model=None)
async def team_spray_chart_image(
    request: Request,
    team_id: int,
    season_id: str | None = None,
) -> Response:
    """Render an offensive spray chart PNG aggregating all players on a team.

    Returns the rendered PNG image when the team has ≥1 offensive BIP event
    for the requested season.  Returns 204 No Content when no events exist.

    When ``season_id`` is omitted, uses the most recent season with spray data
    for this team.

    Authorization: requires an authenticated session (``permitted_teams`` must
    be non-empty) but deliberately skips the per-team ``permitted_teams``
    check.  Reason: opponent teams cannot pass ``permitted_teams`` but their
    spray data is legitimately viewable (spray chart auth exception, per
    CLAUDE.md Architecture section).

    Args:
        request:   The incoming HTTP request.
        team_id:   The INTEGER team id from the URL path.
        season_id: Optional season slug query parameter.

    Returns:
        200 ``image/png`` response with rendered PNG bytes, or 204 No Content.
    """
    permitted_teams: list[int] = getattr(request.state, "permitted_teams", [])
    if not permitted_teams:
        return HTMLResponse(content="Forbidden", status_code=403)

    events, title = await run_in_threadpool(db.get_team_spray_events, team_id, season_id)

    if not events:
        return Response(status_code=204)

    png_bytes: bytes = await run_in_threadpool(render_spray_chart, events, title)
    return Response(content=png_bytes, media_type="image/png")
