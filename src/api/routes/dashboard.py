"""Dashboard routes for the baseball-crawl FastAPI application.

Provides server-rendered HTML views using Jinja2 templates.  All database
calls are executed via ``run_in_threadpool`` to avoid blocking the async
event loop.

Routes:
    GET /dashboard            -- Team season batting stats, scoped to the authenticated
                                 user's permitted teams.
    GET /dashboard/pitching   -- Team season pitching stats.
    GET /dashboard/games      -- Game log with scores and W/L indicators.
    GET /dashboard/games/{game_id} -- Single game box score with batting and pitching lines.
    GET /dashboard/opponents      -- Opponent list with record and next/last game date.
    GET /dashboard/opponents/{opponent_team_id} -- Opponent scouting report.
    GET /dashboard/players/{player_id} -- Player career profile across seasons and teams.
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
from src.api.helpers import format_avg, format_date, format_season_display, ip_display

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
templates.env.filters["season_display"] = format_season_display


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

    # AC-2: respect team_id query param, validate against permitted list
    requested_team_id_raw = request.query_params.get("team_id")
    if requested_team_id_raw:
        try:
            requested_team_id: int = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if requested_team_id not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)
        active_team_id: int = requested_team_id
    else:
        active_team_id = permitted_teams[0]

    current_year = datetime.date.today().year
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id)
    if not requested_season_id:
        season_id = available_seasons[0]["season_id"] if available_seasons else f"{current_year}-spring-hs"
    else:
        season_id = requested_season_id
    if not available_seasons:
        available_seasons = [{"season_id": season_id}]

    # Fetch batting stats and team display names in parallel threadpool calls
    players, team_infos = await _fetch_dashboard_data(
        active_team_id, season_id, permitted_teams
    )

    # Sort params (AC-1)
    raw_sort = request.query_params.get("sort", "").strip().lower()
    raw_dir = request.query_params.get("dir", "").strip().lower()
    if raw_sort in _BATTING_SORT_KEYS:
        current_sort = raw_sort
    else:
        current_sort = "avg"
    if raw_dir in ("asc", "desc"):
        current_dir = raw_dir
    else:
        current_dir = _BATTING_DEFAULT_DIR.get(current_sort, "desc")

    if raw_sort in _BATTING_SORT_KEYS:
        players = _sort_batting(players, current_sort, current_dir)
    # When raw_sort is unrecognized, current_sort falls back to "avg" (shown as the active
    # column in the template), and the SQL-level AVG desc order is preserved -- no re-sort.

    team_name = next(
        (t["name"] for t in team_infos if t["id"] == active_team_id),
        str(active_team_id),
    )

    logger.debug(
        "Dashboard: team=%s season_id=%s players=%d sort=%s dir=%s",
        active_team_id, season_id, len(players), current_sort, current_dir,
    )

    return templates.TemplateResponse(
        request,
        "dashboard/team_stats.html",
        {
            "players": players,
            "team_name": team_name,
            "permitted_team_infos": team_infos,
            "active_team_id": active_team_id,
            "season_id": season_id,
            "available_seasons": available_seasons,
            "is_current_season": int(season_id[:4]) == current_year,
            "current_year": current_year,
            "user": user,
            "no_assignments": False,
            "current_sort": current_sort,
            "current_dir": current_dir,
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

    requested_team_id_raw = request.query_params.get("team_id")
    if requested_team_id_raw:
        try:
            requested_team_id_int: int = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if requested_team_id_int not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)
        active_team_id_p: int = requested_team_id_int
    else:
        active_team_id_p = permitted_teams[0]

    current_year = datetime.date.today().year
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id_p)
    if not requested_season_id:
        season_id = available_seasons[0]["season_id"] if available_seasons else f"{current_year}-spring-hs"
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
    raw_sort_p = request.query_params.get("sort", "").strip().lower()
    raw_dir_p = request.query_params.get("dir", "").strip().lower()
    if raw_sort_p in _PITCHING_SORT_KEYS:
        current_sort_p = raw_sort_p
    else:
        current_sort_p = "era"
    if raw_dir_p in ("asc", "desc"):
        current_dir_p = raw_dir_p
    else:
        current_dir_p = _PITCHING_DEFAULT_DIR.get(current_sort_p, "asc")

    if raw_sort_p in _PITCHING_SORT_KEYS:
        pitchers = _sort_pitching(pitchers, current_sort_p, current_dir_p)

    team_name = next(
        (t["name"] for t in team_infos if t["id"] == active_team_id_p),
        str(active_team_id_p),
    )

    logger.debug(
        "Pitching dashboard: team=%s season_id=%s pitchers=%d sort=%s dir=%s",
        active_team_id_p, season_id, len(pitchers), current_sort_p, current_dir_p,
    )

    return templates.TemplateResponse(
        request,
        "dashboard/team_pitching.html",
        {
            "pitchers": pitchers,
            "team_name": team_name,
            "permitted_team_infos": team_infos,
            "active_team_id": active_team_id_p,
            "season_id": season_id,
            "available_seasons": available_seasons,
            "is_current_season": int(season_id[:4]) == current_year,
            "current_year": current_year,
            "user": user,
            "no_assignments": False,
            "current_sort": current_sort_p,
            "current_dir": current_dir_p,
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

    requested_team_id_raw = request.query_params.get("team_id")
    if requested_team_id_raw:
        try:
            requested_team_id_g: int = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if requested_team_id_g not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)
        active_team_id_g: int = requested_team_id_g
    else:
        active_team_id_g = permitted_teams[0]

    current_year = datetime.date.today().year
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id_g)
    if not requested_season_id:
        season_id = available_seasons[0]["season_id"] if available_seasons else f"{current_year}-spring-hs"
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

    return templates.TemplateResponse(
        request,
        "dashboard/game_list.html",
        {
            "games": games_raw,
            "team_name": team_name,
            "permitted_team_infos": team_infos,
            "active_team_id": active_team_id_g,
            "season_id": season_id,
            "available_seasons": available_seasons,
            "is_current_season": int(season_id[:4]) == current_year,
            "current_year": current_year,
            "user": user,
            "no_assignments": False,
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


def _compute_opponent_pitching_rates(pitchers: list[dict]) -> list[dict]:
    """Compute ERA, K/9, and WHIP for each pitcher row in the scouting report.

    Mutates each row in place by adding ``era``, ``k9``, ``whip``, and
    ``avg_pitches`` string keys.  Division by zero (ip_outs == 0) yields ``"-"``.

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
        if ip_outs == 0:
            row["era"] = "-"
            row["k9"] = "-"
            row["whip"] = "-"
        else:
            row["era"] = f"{(er * 27) / ip_outs:.2f}"
            row["k9"] = f"{(so * 27) / ip_outs:.1f}"
            row["whip"] = f"{(bb + h) * 3 / ip_outs:.2f}"
        row["avg_pitches"] = str(pitches // games) if games > 0 else "-"
    return pitchers


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

    requested_team_id_raw = request.query_params.get("team_id")
    if requested_team_id_raw:
        try:
            requested_team_id_o: int = int(requested_team_id_raw)
        except (ValueError, TypeError):
            return HTMLResponse(content="Bad Request", status_code=400)
        if requested_team_id_o not in permitted_teams:
            return HTMLResponse(content="Forbidden", status_code=403)
        active_team_id_o: int = requested_team_id_o
    else:
        active_team_id_o = permitted_teams[0]

    current_year = datetime.date.today().year
    requested_season_id = request.query_params.get("season_id", "").strip()

    available_seasons = await run_in_threadpool(db.get_available_seasons, active_team_id_o)
    if not requested_season_id:
        season_id = available_seasons[0]["season_id"] if available_seasons else f"{current_year}-spring-hs"
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

    return templates.TemplateResponse(
        request,
        "dashboard/opponent_list.html",
        {
            "opponents": opponents,
            "team_name": team_name,
            "permitted_team_infos": team_infos,
            "active_team_id": active_team_id_o,
            "season_id": season_id,
            "available_seasons": available_seasons,
            "is_current_season": int(season_id[:4]) == current_year,
            "current_year": current_year,
            "user": user,
            "no_assignments": False,
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


@router.get("/dashboard/opponents/{opponent_team_id}", response_model=None)
async def opponent_detail(request: Request, opponent_team_id: int) -> Response:
    """Render the opponent scouting report page.

    Shows Key Players card, Last Meeting card, batting leaders, and pitching
    leaders for the opponent team.

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

    # AC-11: verify opponent appears in games for at least one permitted team
    authorized = await run_in_threadpool(
        _check_opponent_authorization, opponent_team_id, permitted_teams
    )
    if not authorized:
        return HTMLResponse(content="Forbidden", status_code=403)

    # Determine active team for Last Meeting query (AC-16)
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

    # Compute pitching rates before key player selection
    pitchers = _compute_opponent_pitching_rates(scouting_report.get("pitching", []))
    scouting_report["pitching"] = pitchers

    key_players = _pick_key_players(scouting_report.get("batting", []), pitchers)

    # Fetch last meeting
    last_meeting = None
    if active_team_id_od:
        last_meeting = await run_in_threadpool(
            db.get_last_meeting, active_team_id_od, opponent_team_id, season_id
        )

    logger.debug(
        "Opponent detail: opponent=%s season_id=%s", opponent_team_id, season_id
    )

    return templates.TemplateResponse(
        request,
        "dashboard/opponent_detail.html",
        {
            "scouting_report": scouting_report,
            "opponent_team_id": opponent_team_id,
            "key_players": key_players,
            "last_meeting": last_meeting,
            "active_team_id": active_team_id_od,
            "permitted_team_infos": team_infos,
            "season_id": season_id,
            "user": user,
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

    logger.debug("Game detail: game_id=%s active_team_id=%s", game_id, active_team_id_gd)

    return templates.TemplateResponse(
        request,
        "dashboard/game_detail.html",
        {
            "game": game,
            "teams": box_score["teams"],
            "active_team_id": active_team_id_gd,
            "season_id": season_id_gd,
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
        if ip_outs == 0:
            row["era"] = "-"
            row["k9"] = "-"
            row["whip"] = "-"
        else:
            row["era"] = f"{(er * 27) / ip_outs:.2f}"
            row["k9"] = f"{(so * 27) / ip_outs:.1f}"
            row["whip"] = f"{(bb + h) * 3 / ip_outs:.2f}"
    return pitching_seasons


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
            "user": user,
        },
    )
