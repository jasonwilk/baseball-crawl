"""Admin CRUD routes for the baseball-crawl application.

Provides server-rendered HTML views for managing user accounts and team
assignments.  All routes require an active session with ``is_admin=1``.

Routes:
    GET  /admin/users                                    -- List all users
    POST /admin/users                                    -- Create new user
    GET  /admin/users/{user_id}/edit                     -- Edit user form
    POST /admin/users/{user_id}/edit                     -- Update user
    POST /admin/users/{user_id}/delete                   -- Delete user (cascade)
    GET  /admin/teams                                    -- List all teams with add-team form
    POST /admin/teams                                    -- Add team via GameChanger URL or public_id
    GET  /admin/teams/{team_id}/edit                     -- Edit team form
    POST /admin/teams/{team_id}/edit                     -- Update team metadata
    POST /admin/teams/{team_id}/toggle-active            -- Toggle team is_active flag
    GET  /admin/opponents                                -- Opponent link states listing
    GET  /admin/opponents/{id}/connect                   -- URL-paste form
    GET  /admin/opponents/{id}/connect/confirm           -- Confirmation page (fetches team info)
    POST /admin/opponents/{id}/connect                   -- Save manual link
    POST /admin/opponents/{id}/disconnect                -- Remove manual link
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.api.db import (
    bulk_create_opponents,
    count_all_opponent_links,
    disconnect_opponent_link,
    get_connection,
    get_duplicate_opponent_name,
    get_opponent_link_by_id,
    get_opponent_link_count_for_team,
    get_opponent_link_counts,
    get_opponent_links,
    is_owned_team_public_id,
    save_manual_opponent_link,
)
from src.gamechanger.team_resolver import (
    GameChangerAPIError,
    TeamNotFoundError,
    discover_opponents,
    resolve_team,
)
from src.gamechanger.url_parser import parse_team_url

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/admin")


# ---------------------------------------------------------------------------
# Admin guard dependency
# ---------------------------------------------------------------------------


def _forbidden_response(request: Request) -> Response:
    """Render the 403 forbidden HTML page.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with status 403.
    """
    return templates.TemplateResponse(
        request,
        "errors/forbidden.html",
        {},
        status_code=403,
    )


async def _require_admin(request: Request) -> dict[str, Any] | Response:
    """Check that the request has an admin session.

    Reads ``request.state.user`` set by the session middleware.  Returns the
    user dict for admins, a redirect for unauthenticated requests, or a 403
    page for non-admin authenticated users.

    Args:
        request: The incoming HTTP request.

    Returns:
        User dict on success, Response on access denial.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    if not user.get("is_admin"):
        return _forbidden_response(request)
    return user


# ---------------------------------------------------------------------------
# DB helpers (synchronous -- called via run_in_threadpool)
# ---------------------------------------------------------------------------


def _get_all_users() -> list[dict[str, Any]]:
    """Fetch all users with their team assignments.

    Returns:
        List of user dicts with keys: user_id, email, display_name, is_admin,
        teams (comma-separated team names).
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        users = [
            dict(row)
            for row in conn.execute(
                "SELECT user_id, email, display_name, is_admin FROM users ORDER BY display_name"
            ).fetchall()
        ]
        for user in users:
            rows = conn.execute(
                """
                SELECT t.name
                FROM user_team_access uta
                JOIN teams t ON t.team_id = uta.team_id
                WHERE uta.user_id = ?
                ORDER BY t.name
                """,
                (user["user_id"],),
            ).fetchall()
            user["teams"] = ", ".join(row["name"] for row in rows)
    return users


def _get_owned_teams() -> list[dict[str, Any]]:
    """Return all is_owned=1 teams for the checkbox list.

    Returns:
        List of dicts with keys: team_id, name.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in conn.execute(
                "SELECT team_id, name FROM teams WHERE is_owned = 1 ORDER BY name"
            ).fetchall()
        ]


def _get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Fetch a single user row by user_id.

    Args:
        user_id: The user's primary key.

    Returns:
        User dict or None if not found.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT user_id, email, display_name, is_admin FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def _get_user_team_ids(user_id: int) -> list[str]:
    """Return the list of team_ids assigned to a user.

    Args:
        user_id: The user's primary key.

    Returns:
        List of team_id strings.
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT team_id FROM user_team_access WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [row[0] for row in rows]


def _create_user(
    email: str,
    display_name: str,
    is_admin: int,
    team_ids: list[str],
) -> str | None:
    """Insert a new user and their team assignments.

    Args:
        email: Normalized (lowercase) email address.
        display_name: Display name.
        is_admin: 1 for admin, 0 otherwise.
        team_ids: List of team_id strings to assign.

    Returns:
        None on success, or an error message string on failure.
    """
    try:
        with closing(get_connection()) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (email, display_name, is_admin) VALUES (?, ?, ?)",
                    (email, display_name, is_admin),
                )
                new_user_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                return "A user with this email already exists"

            for team_id in team_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                    (new_user_id, team_id),
                )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to create user %s", email)
        return "Database error while creating user"
    return None


def _update_user(
    user_id: int,
    display_name: str,
    is_admin: int,
    team_ids: list[str],
) -> None:
    """Update a user's name, admin status, and team assignments.

    Replaces all existing team assignments with the provided list.

    Args:
        user_id: The user's primary key.
        display_name: New display name.
        is_admin: 1 for admin, 0 otherwise.
        team_ids: Complete list of team_id strings (replaces existing).
    """
    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE users SET display_name = ?, is_admin = ? WHERE user_id = ?",
            (display_name, is_admin, user_id),
        )
        conn.execute(
            "DELETE FROM user_team_access WHERE user_id = ?", (user_id,)
        )
        for team_id in team_ids:
            conn.execute(
                "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                (user_id, team_id),
            )
        conn.commit()


def _delete_user(user_id: int) -> None:
    """Cascade-delete a user and all their auth artifacts.

    Deletes rows from user_team_access, sessions, magic_link_tokens, and
    passkey_credentials before deleting the user row.

    Args:
        user_id: The user's primary key.
    """
    with closing(get_connection()) as conn:
        conn.execute("DELETE FROM user_team_access WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM magic_link_tokens WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM passkey_credentials WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/users", response_model=None)
async def list_users(request: Request) -> Response:
    """Render the user management page.

    Requires admin session.  Lists all users with their team assignments and
    provides an Add User form.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with the user list, or an auth redirect/403.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    users, teams = await run_in_threadpool(_get_all_users), await run_in_threadpool(
        _get_owned_teams
    )

    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "users": users,
            "teams": teams,
            "msg": msg,
            "error": error,
            "admin_user": guard,
        },
    )


@router.post("/users", response_model=None)
async def create_user(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    is_admin: str = Form(default=""),
    team_ids: list[str] = Form(default=[]),
) -> Response:
    """Create a new user with team assignments.

    Normalizes email to lowercase.  Redirects back to /admin/users with a
    flash message on success, or re-renders with an error on duplicate email.

    Args:
        request: The incoming HTTP request.
        email: User email address (required).
        display_name: Display name (required).
        is_admin: Checkbox value ("on" when checked, empty otherwise).
        team_ids: List of selected team_id values from checkboxes.

    Returns:
        Redirect on success, or HTMLResponse with error on failure.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    normalized_email = email.strip().lower()
    is_admin_int = 1 if is_admin else 0

    error = await run_in_threadpool(
        _create_user, normalized_email, display_name.strip(), is_admin_int, team_ids
    )

    if error:
        users, teams = await run_in_threadpool(
            _get_all_users
        ), await run_in_threadpool(_get_owned_teams)
        return templates.TemplateResponse(
            request,
            "admin/users.html",
            {
                "users": users,
                "teams": teams,
                "msg": "",
                "error": error,
                "admin_user": guard,
                "form_email": normalized_email,
                "form_display_name": display_name.strip(),
            },
        )

    return RedirectResponse(
        url="/admin/users?msg=User+added+successfully", status_code=303
    )


@router.get("/users/{user_id}/edit", response_model=None)
async def edit_user_form(request: Request, user_id: int) -> Response:
    """Render the edit user form.

    Args:
        request: The incoming HTTP request.
        user_id: The user's primary key from the URL path.

    Returns:
        HTMLResponse with the edit form, or a 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    user, teams = await run_in_threadpool(
        _get_user_by_id, user_id
    ), await run_in_threadpool(_get_owned_teams)

    if not user:
        return HTMLResponse(content="User not found", status_code=404)

    assigned_team_ids = await run_in_threadpool(_get_user_team_ids, user_id)

    return templates.TemplateResponse(
        request,
        "admin/edit_user.html",
        {
            "edit_user": user,
            "teams": teams,
            "assigned_team_ids": assigned_team_ids,
            "admin_user": guard,
        },
    )


@router.post("/users/{user_id}/edit", response_model=None)
async def update_user(
    request: Request,
    user_id: int,
    display_name: str = Form(...),
    is_admin: str = Form(default=""),
    team_ids: list[str] = Form(default=[]),
) -> Response:
    """Update a user's display name, admin status, and team assignments.

    Args:
        request: The incoming HTTP request.
        user_id: The user's primary key from the URL path.
        display_name: Updated display name.
        is_admin: Checkbox value ("on" when checked, empty otherwise).
        team_ids: Complete list of selected team_id values.

    Returns:
        Redirect on success, or 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    user = await run_in_threadpool(_get_user_by_id, user_id)
    if not user:
        return HTMLResponse(content="User not found", status_code=404)

    is_admin_int = 1 if is_admin else 0
    await run_in_threadpool(
        _update_user, user_id, display_name.strip(), is_admin_int, team_ids
    )

    return RedirectResponse(
        url="/admin/users?msg=User+updated+successfully", status_code=303
    )


@router.post("/users/{user_id}/delete", response_model=None)
async def delete_user(request: Request, user_id: int) -> Response:
    """Delete a user and all their auth artifacts (cascade).

    Admins cannot delete themselves (self-delete prevention).

    Args:
        request: The incoming HTTP request.
        user_id: The user's primary key from the URL path.

    Returns:
        Redirect on success, or auth/error response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    if guard["user_id"] == user_id:
        return RedirectResponse(
            url="/admin/users?error=You+cannot+delete+your+own+account",
            status_code=303,
        )

    user = await run_in_threadpool(_get_user_by_id, user_id)
    if not user:
        return HTMLResponse(content="User not found", status_code=404)

    await run_in_threadpool(_delete_user, user_id)

    return RedirectResponse(
        url="/admin/users?msg=User+deleted+successfully", status_code=303
    )


# ---------------------------------------------------------------------------
# Team management DB helpers (synchronous -- called via run_in_threadpool)
# ---------------------------------------------------------------------------


def _get_all_teams_split() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return teams split into owned (Lincoln) and opponent lists.

    Returns:
        Tuple of (owned_teams, opponent_teams), each a list of dicts with keys:
        team_id, name, level, is_active, public_id, last_synced.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        owned_rows = conn.execute(
            "SELECT team_id, name, level, is_owned, is_active, public_id, last_synced "
            "FROM teams WHERE is_owned = 1 ORDER BY name"
        ).fetchall()
        opponent_rows = conn.execute(
            "SELECT team_id, name, level, is_owned, is_active, public_id, last_synced "
            "FROM teams WHERE is_owned = 0 ORDER BY name"
        ).fetchall()
    return [dict(r) for r in owned_rows], [dict(r) for r in opponent_rows]


def _find_discovered_placeholder(name: str) -> dict[str, Any] | None:
    """Look up an existing team row that is a discovered placeholder matching the given name.

    A placeholder is a row where ``source='discovered'`` and ``public_id IS NULL``.
    Matching is case-insensitive on the ``name`` column.

    Args:
        name: Team name to match (case-insensitive).

    Returns:
        Team dict (team_id, name, ...) if a placeholder exists, else None.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT team_id, name, source FROM teams "
            "WHERE LOWER(name) = LOWER(?) AND source = 'discovered' AND public_id IS NULL",
            (name,),
        ).fetchone()
    return dict(row) if row else None


def _team_id_exists(team_id: str) -> bool:
    """Check whether a team with the given team_id already exists.

    Args:
        team_id: The team_id to look up.

    Returns:
        True if a row exists, False otherwise.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT 1 FROM teams WHERE team_id = ?", (team_id,)
        ).fetchone()
    return row is not None


def _team_is_discovered_placeholder(team_id: str) -> bool:
    """Return True if the team with team_id is a discovered placeholder (not yet a real add).

    A placeholder has ``source='discovered'`` and ``public_id IS NULL``.

    Args:
        team_id: The team_id to check.

    Returns:
        True if the team is a discovered placeholder, False otherwise.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT 1 FROM teams WHERE team_id = ? AND source = 'discovered' AND public_id IS NULL",
            (team_id,),
        ).fetchone()
    return row is not None


def _upgrade_placeholder_team(
    old_team_id: str,
    new_team_id: str,
    name: str,
    public_id: str,
    level: str | None,
    is_owned: int,
) -> None:
    """Upgrade a discovered placeholder team row with resolved data.

    Updates team_id, public_id, name, level, is_owned, source, is_active on the
    matching placeholder row.

    Args:
        old_team_id: The existing placeholder's team_id to update.
        new_team_id: The resolved public_id (used as the new team_id).
        name: Team name from the API.
        public_id: The GameChanger public_id slug.
        level: Level string or None.
        is_owned: 1 for owned, 0 for tracked.
    """
    with closing(get_connection()) as conn:
        conn.execute(
            """
            UPDATE teams
            SET team_id   = ?,
                name      = ?,
                public_id = ?,
                level     = ?,
                is_owned  = ?,
                source    = 'gamechanger',
                is_active = 1
            WHERE team_id = ?
            """,
            (new_team_id, name, public_id, level or None, is_owned, old_team_id),
        )
        conn.commit()


def _insert_team(
    team_id: str,
    name: str,
    public_id: str,
    level: str | None,
    is_owned: int,
) -> None:
    """Insert a new team row.

    Args:
        team_id: Primary key (equals public_id for URL-added teams).
        name: Team name from the API.
        public_id: The GameChanger public_id slug.
        level: Level string or None.
        is_owned: 1 for owned, 0 for tracked.
    """
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO teams (team_id, name, public_id, level, is_owned, source, is_active)
            VALUES (?, ?, ?, ?, ?, 'gamechanger', 1)
            """,
            (team_id, name, public_id, level or None, is_owned),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Team management routes
# ---------------------------------------------------------------------------


@router.get("/teams", response_model=None)
async def list_teams(request: Request) -> Response:
    """Render the team management page.

    Requires admin session.  Shows Lincoln-owned teams and tracked opponents
    in separate tables, plus an Add Team form.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with team list and form, or auth redirect/403.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    owned_teams, opponent_teams = await run_in_threadpool(_get_all_teams_split)
    total_opponent_links = await run_in_threadpool(count_all_opponent_links)

    return templates.TemplateResponse(
        request,
        "admin/teams.html",
        {
            "owned_teams": owned_teams,
            "opponent_teams": opponent_teams,
            "total_opponent_links": total_opponent_links,
            "msg": msg,
            "error": error,
            "admin_user": guard,
        },
    )


@router.post("/teams", response_model=None)
async def add_team(
    request: Request,
    url_input: str = Form(...),
    level: str = Form(default=""),
    team_type: str = Form(default="tracked"),
) -> Response:
    """Add a team by GameChanger URL or public_id.

    Parses the URL input, resolves the team profile from the public API, and
    either upgrades an existing discovered placeholder or inserts a new row.

    Args:
        request: The incoming HTTP request.
        url_input: GameChanger URL or bare public_id.
        level: Optional level value (freshman/jv/varsity/reserve/legion/other).
        team_type: "owned" for Lincoln teams, "tracked" for opponents.

    Returns:
        Redirect on success, or HTMLResponse with error on failure.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    is_owned = 1 if team_type == "owned" else 0
    level_value = level.strip() or None

    # --- Parse URL ---
    try:
        public_id = parse_team_url(url_input.strip())
    except ValueError as exc:
        return await _render_teams_error(request, guard, str(exc), url_input, level_value, team_type)

    # --- Check for exact team_id duplicate that is NOT a discovered placeholder ---
    already_exists = await run_in_threadpool(_team_id_exists, public_id)
    if already_exists:
        is_placeholder = await run_in_threadpool(_team_is_discovered_placeholder, public_id)
        if not is_placeholder:
            return await _render_teams_error(
                request, guard,
                "This team is already in the system.",
                url_input, level_value, team_type,
            )

    # --- Resolve team via public API ---
    try:
        profile = await run_in_threadpool(resolve_team, public_id)
    except TeamNotFoundError:
        return await _render_teams_error(
            request, guard,
            "Team not found on GameChanger. Check the URL and try again.",
            url_input, level_value, team_type,
        )
    except GameChangerAPIError:
        return await _render_teams_error(
            request, guard,
            "Could not reach GameChanger API. Try again later.",
            url_input, level_value, team_type,
        )

    # --- Upgrade placeholder or insert new row ---
    placeholder = await run_in_threadpool(_find_discovered_placeholder, profile.name)
    if placeholder:
        await run_in_threadpool(
            _upgrade_placeholder_team,
            placeholder["team_id"],
            public_id,
            profile.name,
            public_id,
            level_value,
            is_owned,
        )
    else:
        await run_in_threadpool(
            _insert_team,
            public_id,
            profile.name,
            public_id,
            level_value,
            is_owned,
        )

    # Build success message with location if available
    location_parts = [p for p in (profile.city, profile.state) if p]
    if location_parts:
        location_str = ", ".join(location_parts)
        msg = f"Team added: {profile.name} ({location_str})"
    else:
        msg = f"Team added: {profile.name}"

    from urllib.parse import quote_plus
    return RedirectResponse(
        url=f"/admin/teams?msg={quote_plus(msg)}", status_code=303
    )


def _get_team_by_id(team_id: str) -> dict[str, Any] | None:
    """Fetch a single team row by team_id.

    Args:
        team_id: The team's primary key.

    Returns:
        Team dict with all columns, or None if not found.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT team_id, name, level, is_owned, is_active, public_id, last_synced "
            "FROM teams WHERE team_id = ?",
            (team_id,),
        ).fetchone()
        return dict(row) if row else None


def _update_team(team_id: str, name: str, level: str | None, is_owned: int) -> None:
    """Update a team's name, level, and is_owned flag.

    Args:
        team_id: The team's primary key.
        name: New team name.
        level: Level string or None.
        is_owned: 1 for owned (Lincoln), 0 for tracked opponent.
    """
    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE teams SET name = ?, level = ?, is_owned = ? WHERE team_id = ?",
            (name, level or None, is_owned, team_id),
        )
        conn.commit()


def _toggle_team_active(team_id: str) -> int:
    """Toggle a team's is_active flag between 0 and 1.

    Args:
        team_id: The team's primary key.

    Returns:
        The new is_active value after toggling (0 or 1).
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT is_active FROM teams WHERE team_id = ?", (team_id,)
        ).fetchone()
        if row is None:
            return 0
        new_value = 0 if row["is_active"] else 1
        conn.execute(
            "UPDATE teams SET is_active = ? WHERE team_id = ?", (new_value, team_id)
        )
        conn.commit()
        return new_value


async def _render_teams_error(
    request: Request,
    guard: dict[str, Any],
    error: str,
    form_url_input: str,
    form_level: str | None,
    form_team_type: str,
) -> Response:
    """Re-render the teams page with an error message.

    Args:
        request: The incoming HTTP request.
        guard: Admin user dict from _require_admin.
        error: Error message to display.
        form_url_input: The submitted URL/public_id value to repopulate.
        form_level: The submitted level value to repopulate.
        form_team_type: The submitted team_type value to repopulate.

    Returns:
        HTMLResponse with the teams page and error banner.
    """
    owned_teams, opponent_teams = await run_in_threadpool(_get_all_teams_split)
    total_opponent_links = await run_in_threadpool(count_all_opponent_links)
    return templates.TemplateResponse(
        request,
        "admin/teams.html",
        {
            "owned_teams": owned_teams,
            "opponent_teams": opponent_teams,
            "total_opponent_links": total_opponent_links,
            "msg": "",
            "error": error,
            "admin_user": guard,
            "form_url_input": form_url_input,
            "form_level": form_level or "",
            "form_team_type": form_team_type,
        },
    )


@router.get("/teams/{team_id}/edit", response_model=None)
async def edit_team_form(request: Request, team_id: str) -> Response:
    """Render the edit team form.

    Pre-fills Name, Level, Type, and shows read-only Public ID, status, and
    last_synced.

    Args:
        request: The incoming HTTP request.
        team_id: The team's primary key from the URL path.

    Returns:
        HTMLResponse with the edit form, or a 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_id, team_id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    opponent_link_count = await run_in_threadpool(
        get_opponent_link_count_for_team, team_id
    )

    return templates.TemplateResponse(
        request,
        "admin/edit_team.html",
        {
            "edit_team": team,
            "opponent_link_count": opponent_link_count,
            "admin_user": guard,
        },
    )


@router.post("/teams/{team_id}/edit", response_model=None)
async def update_team(
    request: Request,
    team_id: str,
    name: str = Form(...),
    level: str = Form(default=""),
    team_type: str = Form(default="tracked"),
) -> Response:
    """Update a team's name, level, and is_owned flag.

    Args:
        request: The incoming HTTP request.
        team_id: The team's primary key from the URL path.
        name: New team name (required).
        level: Level value (optional).
        team_type: "owned" for Lincoln teams, "tracked" for opponents.

    Returns:
        Redirect on success, or 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_id, team_id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    is_owned = 1 if team_type == "owned" else 0
    level_value = level.strip() or None
    await run_in_threadpool(_update_team, team_id, name.strip(), level_value, is_owned)

    return RedirectResponse(url="/admin/teams?msg=Team+updated", status_code=303)


@router.post("/teams/{team_id}/toggle-active", response_model=None)
async def toggle_team_active(request: Request, team_id: str) -> Response:
    """Toggle a team's is_active status between active and inactive.

    Args:
        request: The incoming HTTP request.
        team_id: The team's primary key from the URL path.

    Returns:
        Redirect to /admin/teams with an appropriate flash message.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_id, team_id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    new_active = await run_in_threadpool(_toggle_team_active, team_id)
    verb = "activated" if new_active else "deactivated"

    from urllib.parse import quote_plus
    return RedirectResponse(
        url=f"/admin/teams?msg=Team+{quote_plus(verb)}", status_code=303
    )


@router.post("/teams/{team_id}/discover-opponents", response_model=None)
async def discover_team_opponents(request: Request, team_id: str) -> Response:
    """Trigger opponent auto-discovery from a team's public game schedule.

    Fetches ``GET /public/teams/{public_id}/games``, extracts unique opponent
    names, and inserts placeholder team rows for any opponents not already in
    the database.  Requires the team to have a ``public_id``.

    Args:
        request: The incoming HTTP request.
        team_id: The team's primary key from the URL path.

    Returns:
        Redirect to /admin/teams with a success or error flash message.
    """
    from urllib.parse import quote_plus

    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_id, team_id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    public_id = team.get("public_id")
    if not public_id:
        return RedirectResponse(
            url="/admin/teams?error="
            + quote_plus("Cannot discover opponents: team has no public ID."),
            status_code=303,
        )

    try:
        discovered = await run_in_threadpool(discover_opponents, public_id)
    except GameChangerAPIError as exc:
        logger.warning("Opponent discovery failed for team %s: %s", team_id, exc)
        return RedirectResponse(
            url="/admin/teams?error="
            + quote_plus("Could not reach GameChanger API. Try again later."),
            status_code=303,
        )

    names = [opp.name for opp in discovered]
    count = await run_in_threadpool(bulk_create_opponents, names)

    team_name = team.get("name", team_id)
    msg = f"Discovered {count} new opponent{'s' if count != 1 else ''} for {team_name}"
    return RedirectResponse(
        url=f"/admin/teams?msg={quote_plus(msg)}", status_code=303
    )


# ---------------------------------------------------------------------------
# Opponent link management routes
# ---------------------------------------------------------------------------


@router.get("/opponents", response_model=None)
async def list_opponents(request: Request) -> Response:
    """Render the opponent link management page.

    Lists opponent_links rows with filter pills (All / Full stats / Scoresheet
    only) and summary counts.  Supports ``?team_id=`` for scoping to a single
    owned team and ``?filter=`` for resolution state filtering.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with the opponent listing, or auth redirect/403.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team_id_filter = request.query_params.get("team_id", "")
    state_filter = request.query_params.get("filter", "")
    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    links = await run_in_threadpool(
        get_opponent_links, team_id_filter or None, state_filter or None
    )
    counts = await run_in_threadpool(get_opponent_link_counts, team_id_filter or None)
    owned_teams = await run_in_threadpool(_get_owned_teams)

    return templates.TemplateResponse(
        request,
        "admin/opponents.html",
        {
            "links": links,
            "counts": counts,
            "owned_teams": owned_teams,
            "team_id_filter": team_id_filter,
            "state_filter": state_filter,
            "msg": msg,
            "error": error,
            "admin_user": guard,
        },
    )


def _render_connect_error(
    request: Request, link: dict[str, Any], admin_user: Any, error: str
) -> Response:
    """Return the opponent_connect.html template in error mode."""
    return templates.TemplateResponse(
        request,
        "admin/opponent_connect.html",
        {"link": link, "mode": "error", "error": error, "admin_user": admin_user},
    )


@router.get("/opponents/{link_id}/connect", response_model=None)
async def connect_opponent_form(request: Request, link_id: int) -> Response:
    """Render the URL-paste form for manually linking an unlinked opponent.

    Args:
        request: The incoming HTTP request.
        link_id: The opponent_links primary key from the URL path.

    Returns:
        HTMLResponse with the connect form, or 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    return templates.TemplateResponse(
        request,
        "admin/opponent_connect.html",
        {
            "link": link,
            "mode": "form",
            "admin_user": guard,
        },
    )


async def _fetch_team_profile(
    request: Request, link: dict[str, Any], guard: Any, public_id: str
) -> tuple[Any | None, Response | None]:
    """Fetch team profile via public API; return (profile, None) or (None, error_response)."""
    try:
        profile = await run_in_threadpool(resolve_team, public_id)
        return profile, None
    except TeamNotFoundError:
        return None, _render_connect_error(
            request, link, guard,
            "Team not found on GameChanger. Check the URL and try again.",
        )
    except GameChangerAPIError:
        return None, _render_connect_error(
            request, link, guard,
            "Could not reach GameChanger API. Try again later.",
        )


async def _get_duplicate_name_for_link(
    link: dict, public_id: str, link_id: int
) -> str | None:
    """Look up any existing opponent link that already uses the given public_id.

    Args:
        link: The opponent link row dict (must contain ``our_team_id``).
        public_id: The GameChanger public_id slug to check for duplicates.
        link_id: The current link's primary key, excluded from the duplicate search.

    Returns:
        The name of the duplicate opponent if one exists, otherwise None.
    """
    our_team_id = link["our_team_id"]
    return await run_in_threadpool(
        get_duplicate_opponent_name, public_id, our_team_id, link_id
    )


@router.get("/opponents/{link_id}/connect/confirm", response_model=None)
async def connect_opponent_confirm(request: Request, link_id: int) -> Response:
    """Render the confirmation page for a manual opponent link.

    Args:
        request: The incoming HTTP request.
        link_id: The opponent_links primary key from the URL path.

    Returns:
        HTMLResponse with team profile confirmation or error, or 404/auth.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    url_input = request.query_params.get("url", "").strip()
    try:
        public_id = parse_team_url(url_input)
    except ValueError as exc:
        return _render_connect_error(request, link, guard, str(exc))

    is_own_team = await run_in_threadpool(is_owned_team_public_id, public_id)
    if is_own_team:
        return _render_connect_error(
            request, link, guard,
            "This URL belongs to a Lincoln program team. You cannot link an opponent to an owned team.",
        )

    duplicate_name = await _get_duplicate_name_for_link(link, public_id, link_id)
    profile, err = await _fetch_team_profile(request, link, guard, public_id)
    if err is not None:
        return err

    return templates.TemplateResponse(
        request,
        "admin/opponent_connect.html",
        {
            "link": link,
            "mode": "confirm",
            "profile": profile,
            "public_id": public_id,
            "duplicate_name": duplicate_name,
            "admin_user": guard,
        },
    )


def _build_connect_success_msg(opponent_name: str, duplicate_name: str | None) -> str:
    """Build the flash message for a successful manual link save."""
    from urllib.parse import quote_plus

    if duplicate_name:
        return quote_plus(
            f"Linked {opponent_name} -- note: this URL is already used by {duplicate_name}."
        )
    return quote_plus(f"Linked {opponent_name} successfully.")


def _check_already_resolved(link: dict) -> HTMLResponse | None:
    """Return a 400 response if the link already has a public_id, else None."""
    if link.get("public_id") is not None:
        return HTMLResponse(
            content=(
                "This opponent is already resolved and cannot be manually linked. "
                "Disconnect the existing link first."
            ),
            status_code=400,
        )
    return None


@router.post("/opponents/{link_id}/connect", response_model=None)
async def connect_opponent(
    request: Request,
    link_id: int,
    public_id: str = Form(...),
) -> Response:
    """Save a manual opponent link.

    Args:
        request: The incoming HTTP request.
        link_id: The opponent_links primary key from the URL path.
        public_id: The GameChanger public_id slug from the hidden form field.

    Returns:
        Redirect to /admin/opponents?team_id=... on success, or error response.
    """
    from urllib.parse import quote_plus

    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    already_resolved = _check_already_resolved(link)
    if already_resolved is not None:
        return already_resolved

    is_own_team = await run_in_threadpool(is_owned_team_public_id, public_id)
    if is_own_team:
        return HTMLResponse(
            content="Cannot link an opponent to a Lincoln program team.",
            status_code=400,
        )

    our_team_id = link["our_team_id"]
    duplicate_name = await run_in_threadpool(
        get_duplicate_opponent_name, public_id, our_team_id, link_id
    )
    await run_in_threadpool(save_manual_opponent_link, link_id, public_id)
    msg = _build_connect_success_msg(link["opponent_name"], duplicate_name)
    return RedirectResponse(
        url=f"/admin/opponents?team_id={quote_plus(our_team_id)}&msg={msg}",
        status_code=303,
    )


@router.post("/opponents/{link_id}/disconnect", response_model=None)
async def disconnect_opponent(request: Request, link_id: int) -> Response:
    """Remove a manual opponent link.

    Only disconnects links where ``resolution_method='manual'``.  Returns 400
    for auto-resolved links (which would be re-created by the resolver).

    Args:
        request: The incoming HTTP request.
        link_id: The opponent_links primary key from the URL path.

    Returns:
        Redirect to /admin/opponents on success, or 400/404/auth response.
    """
    from urllib.parse import quote_plus

    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    if link.get("resolution_method") != "manual":
        return HTMLResponse(
            content="Cannot disconnect an auto-resolved link. Only manual links can be disconnected.",
            status_code=400,
        )

    success = await run_in_threadpool(disconnect_opponent_link, link_id)
    if not success:
        return HTMLResponse(content="Failed to disconnect opponent link.", status_code=500)

    our_team_id = link["our_team_id"]
    msg = quote_plus(f"Disconnected {link['opponent_name']}.")
    return RedirectResponse(
        url=f"/admin/opponents?team_id={quote_plus(our_team_id)}&msg={msg}",
        status_code=303,
    )
