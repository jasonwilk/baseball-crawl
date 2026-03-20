"""Admin CRUD routes for the baseball-crawl application.

Provides server-rendered HTML views for managing user accounts and team
assignments.  All routes require an active session matching ADMIN_EMAIL
(or any authenticated user when ADMIN_EMAIL is unset in dev mode).

Routes:
    GET  /admin/users                                    -- List all users
    POST /admin/users                                    -- Create new user
    GET  /admin/users/{user_id}/edit                     -- Edit user form
    POST /admin/users/{user_id}/edit                     -- Update user
    POST /admin/users/{user_id}/delete                   -- Delete user (cascade)
    GET  /admin/teams                                    -- Flat team list + add-team Phase 1 form
    POST /admin/teams                                    -- Phase 1: resolve URL, redirect to confirm
    GET  /admin/teams/confirm                            -- Phase 2: confirm page
    POST /admin/teams/confirm                            -- Phase 2: create team
    GET  /admin/teams/{team_id}/edit                     -- Edit team form (INTEGER team_id)
    POST /admin/teams/{team_id}/edit                     -- Update team metadata (INTEGER team_id)
    POST /admin/teams/{id}/toggle-active                 -- Toggle team is_active flag (INTEGER id)
    POST /admin/teams/{id}/discover-opponents            -- Discover opponent placeholders (INTEGER id)
    GET  /admin/opponents                                -- Opponent link states listing
    GET  /admin/opponents/{link_id}/connect              -- URL-paste form
    GET  /admin/opponents/{link_id}/connect/confirm      -- Confirmation page (fetches team info)
    POST /admin/opponents/{link_id}/connect              -- Save manual link
    POST /admin/opponents/{link_id}/disconnect           -- Remove manual link
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.api.db import (
    bulk_create_opponents,
    disconnect_opponent_link,
    get_connection,
    get_duplicate_opponent_name,
    get_opponent_link_by_id,
    get_opponent_link_count_for_team,
    get_opponent_link_counts,
    get_opponent_links,
    is_member_team_public_id,
    save_manual_opponent_link,
)
from src.gamechanger.bridge import (
    BridgeForbiddenError,
    resolve_public_id_to_uuid,
)
from src.gamechanger.exceptions import ConfigurationError, CredentialExpiredError
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

# Valid classification values (must match schema CHECK constraint)
_VALID_CLASSIFICATIONS = {
    "varsity", "jv", "freshman", "reserve",
    "8U", "9U", "10U", "11U", "12U", "13U", "14U",
    "legion",
}

# Valid membership_type values (must match schema CHECK constraint)
_VALID_MEMBERSHIP_TYPES = {"member", "tracked"}


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

    Admin access is controlled by the ``ADMIN_EMAIL`` environment variable.
    If ``ADMIN_EMAIL`` is set, only that email address is treated as admin.
    If ``ADMIN_EMAIL`` is unset (dev mode), all authenticated users are admin.

    Args:
        request: The incoming HTTP request.

    Returns:
        User dict on success, Response on access denial.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if admin_email and user.get("email") != admin_email:
        return _forbidden_response(request)
    return user


# ---------------------------------------------------------------------------
# User management DB helpers (synchronous -- called via run_in_threadpool)
# ---------------------------------------------------------------------------


def _get_all_users() -> list[dict[str, Any]]:
    """Fetch all users with their team assignments.

    Returns:
        List of user dicts with keys: id, email,
        teams (comma-separated team names).
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        users = [
            dict(row)
            for row in conn.execute(
                "SELECT id, email FROM users ORDER BY email"
            ).fetchall()
        ]
        for user in users:
            rows = conn.execute(
                """
                SELECT t.name
                FROM user_team_access uta
                JOIN teams t ON t.id = uta.team_id
                WHERE uta.user_id = ?
                ORDER BY t.name
                """,
                (user["id"],),
            ).fetchall()
            user["teams"] = ", ".join(row["name"] for row in rows)
    return users


def _get_available_teams() -> list[dict[str, Any]]:
    """Return member teams for user assignment checkboxes.

    Returns:
        List of dicts with keys: id (INTEGER), name.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id, name FROM teams WHERE membership_type = 'member' ORDER BY name"
            ).fetchall()
        ]


def _get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Fetch a single user row by id.

    Args:
        user_id: The user's primary key.

    Returns:
        User dict or None if not found.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def _get_user_team_ids(user_id: int) -> list[int]:
    """Return the list of INTEGER team ids assigned to a user.

    Args:
        user_id: The user's primary key.

    Returns:
        List of INTEGER team ids.
    """
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT team_id FROM user_team_access WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [row[0] for row in rows]


def _create_user(
    email: str,
    team_ids: list[int],
) -> str | None:
    """Insert a new user and their team assignments.

    Args:
        email: Normalized (lowercase) email address.
        team_ids: List of INTEGER team ids to assign.

    Returns:
        None on success, or an error message string on failure.
    """
    try:
        with closing(get_connection()) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (email) VALUES (?)",
                    (email,),
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
    team_ids: list[int],
) -> None:
    """Replace a user's team assignments with the provided list.

    Args:
        user_id: The user's primary key.
        team_ids: Complete list of INTEGER team ids (replaces existing).
    """
    with closing(get_connection()) as conn:
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

    Deletes rows from user_team_access, sessions, magic_link_tokens,
    passkey_credentials, and coaching_assignments before deleting the user row.

    Args:
        user_id: The user's primary key.
    """
    with closing(get_connection()) as conn:
        conn.execute("DELETE FROM user_team_access WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM magic_link_tokens WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM passkey_credentials WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM coaching_assignments WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Team management DB helpers (synchronous -- called via run_in_threadpool)
# ---------------------------------------------------------------------------


def _get_all_teams_flat() -> list[dict[str, Any]]:
    """Return all teams in a flat list with program name and opponent count.

    Returns:
        List of dicts with keys: id, name, program_id, membership_type,
        classification, is_active, public_id, gc_uuid, last_synced,
        program_name (nullable), opponent_count.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                t.id,
                t.name,
                t.program_id,
                t.membership_type,
                t.classification,
                t.is_active,
                t.public_id,
                t.gc_uuid,
                t.last_synced,
                p.name AS program_name,
                (
                    SELECT COUNT(*)
                    FROM opponent_links ol
                    WHERE ol.our_team_id = t.id
                      AND ol.is_hidden = 0
                ) AS opponent_count
            FROM teams t
            LEFT JOIN programs p ON t.program_id = p.program_id
            ORDER BY t.name
            """
        ).fetchall()
    return [dict(r) for r in rows]


def _get_programs() -> list[dict[str, Any]]:
    """Return all programs for dropdowns.

    Returns:
        List of dicts with keys: program_id, name.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT program_id, name FROM programs ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def _get_team_by_integer_id(team_id: int) -> dict[str, Any] | None:
    """Fetch a single team row by INTEGER id.

    Args:
        team_id: The team's INTEGER primary key.

    Returns:
        Team dict with all columns plus program_name, or None if not found.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT t.id, t.name, t.program_id, t.membership_type, t.classification,
                   t.is_active, t.public_id, t.gc_uuid, t.last_synced,
                   p.name AS program_name
            FROM teams t
            LEFT JOIN programs p ON t.program_id = p.program_id
            WHERE t.id = ?
            """,
            (team_id,),
        ).fetchone()
        return dict(row) if row else None


def _update_team_integer(
    team_id: int,
    name: str,
    program_id: str | None,
    classification: str | None,
    membership_type: str,
) -> None:
    """Update a team's name, program, classification, and membership_type.

    Args:
        team_id: The team's INTEGER primary key.
        name: New team name.
        program_id: Program slug or None.
        classification: Classification string or None.
        membership_type: 'member' or 'tracked'.
    """
    with closing(get_connection()) as conn:
        conn.execute(
            """
            UPDATE teams
            SET name = ?, program_id = ?, classification = ?, membership_type = ?
            WHERE id = ?
            """,
            (name, program_id, classification, membership_type, team_id),
        )
        conn.commit()


def _toggle_team_active_integer(team_id: int) -> int:
    """Toggle a team's is_active flag between 0 and 1.

    Args:
        team_id: The team's INTEGER primary key.

    Returns:
        The new is_active value after toggling (0 or 1).
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT is_active FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if row is None:
            return 0
        new_value = 0 if row["is_active"] else 1
        conn.execute(
            "UPDATE teams SET is_active = ? WHERE id = ?", (new_value, team_id)
        )
        conn.commit()
        return new_value


def _check_duplicate_new(
    public_id: str,
    gc_uuid: str | None,
    phase1_gc_uuid: str | None = None,
) -> bool:
    """Return True if public_id or gc_uuid already exists in the teams table.

    Args:
        public_id: The GC public_id slug to check.
        gc_uuid: The GC UUID to check (may be None if TOCTOU reverify failed).
        phase1_gc_uuid: The UUID discovered in Phase 1 before TOCTOU reverify.
            Checked as a fallback when gc_uuid is None -- covers the case where
            opponent_resolver previously created a row with the gc_uuid but no
            public_id, and reverify failed so gc_uuid is now None.

    Returns:
        True if a duplicate exists.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT 1 FROM teams WHERE public_id = ?", (public_id,)
        ).fetchone()
        if row:
            return True
        if gc_uuid:
            row = conn.execute(
                "SELECT 1 FROM teams WHERE gc_uuid = ?", (gc_uuid,)
            ).fetchone()
            if row:
                return True
        # When reverify failed (gc_uuid is None), still check the Phase 1 UUID.
        # This catches the case where a row exists with gc_uuid but no public_id
        # (e.g., created by opponent_resolver) -- public_id check above misses it.
        if phase1_gc_uuid and phase1_gc_uuid != gc_uuid:
            row = conn.execute(
                "SELECT 1 FROM teams WHERE gc_uuid = ?", (phase1_gc_uuid,)
            ).fetchone()
            if row:
                return True
    return False


def _insert_team_new(
    name: str,
    public_id: str,
    gc_uuid: str | None,
    membership_type: str,
    program_id: str | None,
    classification: str | None,
) -> int:
    """Insert a new team row with INTEGER PK auto-assigned.

    For member teams, also inserts ``user_team_access`` rows for every
    existing user so the new team is immediately visible in their session
    without requiring a logout/login.

    Args:
        name: Team display name.
        public_id: GC public_id slug.
        gc_uuid: GC UUID (None if bridge returned 403).
        membership_type: 'member' or 'tracked'.
        program_id: Program slug or None.
        classification: Classification string or None.

    Returns:
        The INTEGER primary key of the newly inserted team.
    """
    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO teams
                (name, public_id, gc_uuid, membership_type, program_id,
                 classification, source, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 'gamechanger', 1)
            """,
            (name, public_id, gc_uuid, membership_type, program_id, classification),
        )
        new_team_id = cursor.lastrowid
        if membership_type == "member":
            user_rows = conn.execute("SELECT id FROM users").fetchall()
            for (user_id,) in user_rows:
                conn.execute(
                    "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                    (user_id, new_team_id),
                )
        conn.commit()
    return new_team_id


# ---------------------------------------------------------------------------
# Inference helpers for the add-team confirm page
# ---------------------------------------------------------------------------


def _infer_classification(name: str) -> str | None:
    """Infer team classification from name keywords.

    Checks HS division keywords (varsity, jv, freshman, reserve, legion)
    and USSSA age patterns (8U-14U).

    Args:
        name: Team display name from GameChanger API.

    Returns:
        Classification string or None if no match.
    """
    name_lower = name.lower()
    if "junior varsity" in name_lower or " jv " in name_lower or name_lower.endswith(" jv"):
        return "jv"
    if "varsity" in name_lower:
        return "varsity"
    if "freshman" in name_lower or "frosh" in name_lower:
        return "freshman"
    if "reserve" in name_lower:
        return "reserve"
    if "legion" in name_lower:
        return "legion"
    # Age divisions: match patterns like "14U", "13u", "8U"
    m = re.search(r"\b(\d{1,2})[uU]\b", name)
    if m:
        ag = m.group(1) + "U"
        if ag in {"8U", "9U", "10U", "11U", "12U", "13U", "14U"}:
            return ag
    return None


def _infer_program_id(
    team_name: str, programs: list[dict[str, Any]]
) -> str | None:
    """Find best matching program by substring (longest match wins).

    Matches program name as case-insensitive substring of team name.
    If multiple programs match, the longest program name wins.

    Args:
        team_name: Team display name from GameChanger API.
        programs: List of program dicts with program_id and name keys.

    Returns:
        program_id string or None if no match.
    """
    best_match: str | None = None
    best_len = 0
    name_lower = team_name.lower()
    for prog in programs:
        prog_name_lower = prog["name"].lower()
        if prog_name_lower in name_lower and len(prog_name_lower) > best_len:
            best_match = prog["program_id"]
            best_len = len(prog_name_lower)
    return best_match


# ---------------------------------------------------------------------------
# User management routes
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
        _get_available_teams
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
            "is_admin_page": True,
        },
    )


@router.post("/users", response_model=None)
async def create_user(
    request: Request,
    email: str = Form(...),
    team_ids: list[str] = Form(default=[]),
) -> Response:
    """Create a new user with team assignments.

    Normalizes email to lowercase.  Redirects back to /admin/users with a
    flash message on success, or re-renders with an error on duplicate email.

    Args:
        request: The incoming HTTP request.
        email: User email address (required).
        team_ids: List of INTEGER team id values from checkboxes (as strings).

    Returns:
        Redirect on success, or HTMLResponse with error on failure.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    normalized_email = email.strip().lower()
    int_team_ids = [int(tid) for tid in team_ids if tid.strip().isdigit()]

    error = await run_in_threadpool(_create_user, normalized_email, int_team_ids)

    if error:
        users, teams = await run_in_threadpool(
            _get_all_users
        ), await run_in_threadpool(_get_available_teams)
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
                "is_admin_page": True,
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
    ), await run_in_threadpool(_get_available_teams)

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
            "is_admin_page": True,
        },
    )


@router.post("/users/{user_id}/edit", response_model=None)
async def update_user(
    request: Request,
    user_id: int,
    team_ids: list[str] = Form(default=[]),
) -> Response:
    """Update a user's team assignments.

    Args:
        request: The incoming HTTP request.
        user_id: The user's primary key from the URL path.
        team_ids: Complete list of INTEGER team id values (replaces existing).

    Returns:
        Redirect on success, or 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    user = await run_in_threadpool(_get_user_by_id, user_id)
    if not user:
        return HTMLResponse(content="User not found", status_code=404)

    int_team_ids = [int(tid) for tid in team_ids if tid.strip().isdigit()]
    await run_in_threadpool(_update_user, user_id, int_team_ids)

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

    if guard["id"] == user_id:
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
# Team management routes
# ---------------------------------------------------------------------------


async def _render_teams_error(
    request: Request,
    guard: dict[str, Any],
    error: str,
    form_url_input: str,
) -> Response:
    """Re-render the teams page with a Phase 1 form error.

    Args:
        request: The incoming HTTP request.
        guard: Admin user dict from _require_admin.
        error: Error message to display.
        form_url_input: The submitted URL/public_id value to repopulate.

    Returns:
        HTMLResponse with the teams page and error banner.
    """
    teams = await run_in_threadpool(_get_all_teams_flat)
    return templates.TemplateResponse(
        request,
        "admin/teams.html",
        {
            "teams": teams,
            "msg": "",
            "error": error,
            "admin_user": guard,
            "form_url_input": form_url_input,
            "is_admin_page": True,
        },
    )


@router.get("/teams", response_model=None)
async def list_teams(request: Request) -> Response:
    """Render the team management page.

    Requires admin session.  Shows all teams in a flat table with program,
    division, membership badge, and opponent count columns.  Includes a
    Phase 1 add-team form (URL input only).

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
    added = request.query_params.get("added", "")
    added_team_name = request.query_params.get("team_name", "")

    teams = await run_in_threadpool(_get_all_teams_flat)

    return templates.TemplateResponse(
        request,
        "admin/teams.html",
        {
            "teams": teams,
            "msg": msg,
            "error": error,
            "added": added,
            "added_team_name": added_team_name,
            "admin_user": guard,
            "is_admin_page": True,
        },
    )


async def _call_bridge(
    request: Request,
    guard: Any,
    public_id: str,
    url_stripped: str,
) -> tuple[str | None, str] | Response:
    """Call reverse bridge to discover gc_uuid.

    Args:
        request: The incoming HTTP request.
        guard: Admin user dict.
        public_id: GC public_id slug.
        url_stripped: Original input for error re-display.

    Returns:
        ``(gc_uuid, gc_uuid_status)`` tuple on success/403, or a Response on
        credential/API error.
    """
    try:
        gc_uuid = await run_in_threadpool(resolve_public_id_to_uuid, public_id)
        return gc_uuid, "found"
    except BridgeForbiddenError:
        return None, "forbidden"
    except (CredentialExpiredError, ConfigurationError) as exc:
        return await _render_teams_error(
            request, guard,
            f"GameChanger credentials error: {exc}. Run: bb creds check",
            url_stripped,
        )
    except GameChangerAPIError:
        return await _render_teams_error(
            request, guard,
            "Could not reach GameChanger API. Try again later.",
            url_stripped,
        )


async def _fetch_public_profile(
    request: Request,
    guard: Any,
    public_id: str,
    url_stripped: str,
) -> Any | Response:
    """Fetch the public team profile for a given public_id.

    Args:
        request: The incoming HTTP request.
        guard: Admin user dict.
        public_id: GC public_id slug.
        url_stripped: Original input for error re-display.

    Returns:
        ``TeamProfile`` on success, or a Response on not-found/API error.
    """
    try:
        return await run_in_threadpool(resolve_team, public_id)
    except TeamNotFoundError:
        return await _render_teams_error(
            request, guard,
            "Team not found on GameChanger. Check the URL and try again.",
            url_stripped,
        )
    except GameChangerAPIError:
        return await _render_teams_error(
            request, guard,
            "Could not reach GameChanger API. Try again later.",
            url_stripped,
        )


async def _parse_url_to_public_id(
    request: Request, guard: Any, url_stripped: str
) -> tuple[str, None] | tuple[None, Response]:
    """Parse a team URL/public_id input to a public_id slug.

    Args:
        request: The incoming HTTP request.
        guard: Admin user dict.
        url_stripped: Stripped URL/public_id input.

    Returns:
        ``(public_id, None)`` on success, or ``(None, error_response)`` if
        the input is invalid or is a raw UUID.
    """
    try:
        id_result = parse_team_url(url_stripped)
    except ValueError as exc:
        return None, await _render_teams_error(request, guard, str(exc), url_stripped)
    if id_result.is_uuid:
        return None, await _render_teams_error(
            request, guard,
            "Please provide a GameChanger URL or public_id slug, not a raw UUID.",
            url_stripped,
        )
    return id_result.value, None


@router.post("/teams", response_model=None)
async def add_team_phase1(
    request: Request,
    url_input: str = Form(...),
) -> Response:
    """Phase 1: resolve URL, discover gc_uuid, redirect to confirm.

    Returns:
        Redirect to /admin/teams/confirm on success, or teams page with
        error banner on failure.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    url_stripped = url_input.strip()
    public_id, err = await _parse_url_to_public_id(request, guard, url_stripped)
    if err is not None:
        return err

    bridge_result = await _call_bridge(request, guard, public_id, url_stripped)
    if isinstance(bridge_result, Response):
        return bridge_result
    gc_uuid, gc_uuid_status = bridge_result

    profile = await _fetch_public_profile(request, guard, public_id, url_stripped)
    if isinstance(profile, Response):
        return profile

    params: dict[str, str] = {
        "public_id": public_id,
        "team_name": profile.name,
        "gc_uuid_status": gc_uuid_status,
    }
    if gc_uuid:
        params["gc_uuid"] = gc_uuid
    return RedirectResponse(
        url=f"/admin/teams/confirm?{urlencode(params)}", status_code=303
    )


async def _render_confirm_team_page(
    request: Request,
    guard: Any,
    public_id: str,
    team_name: str,
    gc_uuid: str | None,
    gc_uuid_status: str,
    error: str,
    programs: list[dict[str, Any]],
    inferred_classification: str | None,
    inferred_program_id: str | None,
) -> Response:
    """Render the confirm-add-team page with the given context.

    Args:
        request: The incoming HTTP request.
        guard: Admin user dict.
        public_id: GC public_id slug.
        team_name: Resolved team display name.
        gc_uuid: GC UUID or None.
        gc_uuid_status: 'found' or 'forbidden'.
        error: Error message to display (empty string for none).
        programs: List of program dicts for the dropdown.
        inferred_classification: Pre-selected division or None.
        inferred_program_id: Pre-selected program slug or None.

    Returns:
        TemplateResponse for the confirm page.
    """
    return templates.TemplateResponse(
        request,
        "admin/confirm_team.html",
        {
            "public_id": public_id,
            "team_name": team_name,
            "gc_uuid": gc_uuid or "",
            "gc_uuid_status": gc_uuid_status,
            "programs": programs,
            "inferred_classification": inferred_classification,
            "inferred_program_id": inferred_program_id,
            "error": error,
            "admin_user": guard,
            "is_admin_page": True,
        },
    )


@router.get("/teams/confirm", response_model=None)
async def confirm_team_form(request: Request) -> Response:
    """Phase 2: Render the confirm-add-team page.

    Displays resolved team info, gc_uuid status (informational), membership
    radio (default: tracked), and pre-populated program and division dropdowns.
    Also performs duplicate detection and shows an error if the team already
    exists.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with confirm form, or redirect to /admin/teams if
        required query params are missing.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    public_id = request.query_params.get("public_id", "")
    if not public_id:
        return RedirectResponse(url="/admin/teams", status_code=302)

    team_name = request.query_params.get("team_name", "")
    gc_uuid = request.query_params.get("gc_uuid", "") or None
    gc_uuid_status = request.query_params.get("gc_uuid_status", "forbidden")
    error = request.query_params.get("error", "")

    programs = await run_in_threadpool(_get_programs)
    if not error and await run_in_threadpool(_check_duplicate_new, public_id, gc_uuid):
        error = "This team is already in the system."

    return await _render_confirm_team_page(
        request, guard, public_id, team_name, gc_uuid, gc_uuid_status,
        error, programs,
        _infer_classification(team_name),
        _infer_program_id(team_name, programs),
    )


async def _toctou_refresh_uuid(
    gc_uuid_value: str | None, public_id: str
) -> str | None:
    """Re-verify the reverse bridge to guard against stale Phase 1 query params.

    Called only when gc_uuid_value is non-None (bridge succeeded in Phase 1).
    On any error (403, credential, API), returns None so the team is stored
    without a gc_uuid.

    Args:
        gc_uuid_value: UUID discovered in Phase 1 (non-None).
        public_id: GC public_id slug to re-verify.

    Returns:
        Fresh UUID string on success, or None on any bridge failure.
    """
    try:
        return await run_in_threadpool(resolve_public_id_to_uuid, public_id)
    except (
        BridgeForbiddenError,
        CredentialExpiredError,
        ConfigurationError,
        GameChangerAPIError,
    ):
        return None


def _normalize_confirm_inputs(
    gc_uuid: str, program_id: str, classification: str
) -> tuple[str | None, str | None, str | None]:
    """Normalize and validate Phase 2 form inputs.

    Returns:
        ``(gc_uuid_value, program_id_value, classification_value)`` with empty
        strings converted to None and invalid classifications replaced with None.
    """
    gc_uuid_value = gc_uuid.strip() or None
    program_id_value = program_id.strip() or None
    classification_value = classification.strip() or None
    if classification_value not in _VALID_CLASSIFICATIONS:
        classification_value = None
    return gc_uuid_value, program_id_value, classification_value


@router.post("/teams/confirm", response_model=None)
async def confirm_team_submit(
    request: Request,
    public_id: str = Form(...),
    team_name: str = Form(...),
    gc_uuid: str = Form(default=""),
    membership_type: str = Form(default="tracked"),
    program_id: str = Form(default=""),
    classification: str = Form(default=""),
) -> Response:
    """Phase 2: TOCTOU guard, duplicate check, then insert team.

    Returns:
        Redirect to /admin/teams on success, or re-rendered confirm page
        with error on duplicate.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    gc_uuid_value, program_id_value, classification_value = _normalize_confirm_inputs(
        gc_uuid, program_id, classification
    )

    if membership_type not in _VALID_MEMBERSHIP_TYPES:
        return HTMLResponse(
            content=f"Invalid membership_type: {membership_type!r}. Must be 'member' or 'tracked'.",
            status_code=400,
        )

    # Preserve Phase 1 UUID before TOCTOU may clear it on 403.
    # Used as fallback in duplicate check when reverify fails.
    phase1_gc_uuid = gc_uuid_value

    if gc_uuid_value:
        gc_uuid_value = await _toctou_refresh_uuid(gc_uuid_value, public_id)

    if await run_in_threadpool(_check_duplicate_new, public_id, gc_uuid_value, phase1_gc_uuid):
        programs = await run_in_threadpool(_get_programs)
        return await _render_confirm_team_page(
            request, guard, public_id, team_name, gc_uuid_value,
            "found" if gc_uuid_value else "forbidden",
            "This team is already in the system.",
            programs,
            _infer_classification(team_name),
            _infer_program_id(team_name, programs),
        )

    try:
        await run_in_threadpool(
            _insert_team_new,
            team_name, public_id, gc_uuid_value, membership_type,
            program_id_value, classification_value,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(
            url=f"/admin/teams?error={quote_plus('Team already exists (concurrent insert).')}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/admin/teams?added=1&team_name={quote_plus(team_name)}",
        status_code=303,
    )


@router.get("/teams/{team_id}/edit", response_model=None)
async def edit_team_form(request: Request, team_id: int) -> Response:
    """Render the edit team form.

    Pre-fills Name, Division, Program, and membership type.  Shows read-only
    Public ID, gc_uuid status, and last_synced.

    Args:
        request: The incoming HTTP request.
        team_id: The team's INTEGER primary key from the URL path.

    Returns:
        HTMLResponse with the edit form, or a 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_integer_id, team_id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    opponent_link_count = await run_in_threadpool(get_opponent_link_count_for_team, team_id)
    programs = await run_in_threadpool(_get_programs)

    return templates.TemplateResponse(
        request,
        "admin/edit_team.html",
        {
            "edit_team": team,
            "programs": programs,
            "opponent_link_count": opponent_link_count,
            "admin_user": guard,
            "is_admin_page": True,
        },
    )


@router.post("/teams/{team_id}/edit", response_model=None)
async def update_team(
    request: Request,
    team_id: int,
    name: str = Form(...),
    program_id: str = Form(default=""),
    classification: str = Form(default=""),
    membership_type: str = Form(default="tracked"),
) -> Response:
    """Update a team's name, program, division, and membership type.

    Args:
        request: The incoming HTTP request.
        team_id: The team's INTEGER primary key from the URL path.
        name: New team name (required).
        program_id: Program slug (optional).
        classification: Classification string (optional).
        membership_type: 'member' or 'tracked'.

    Returns:
        Redirect on success, or 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_integer_id, team_id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    if membership_type not in _VALID_MEMBERSHIP_TYPES:
        return HTMLResponse(
            content=f"Invalid membership_type: {membership_type!r}. Must be 'member' or 'tracked'.",
            status_code=400,
        )

    classification_value = classification.strip() or None
    if classification_value not in _VALID_CLASSIFICATIONS:
        classification_value = None

    await run_in_threadpool(
        _update_team_integer,
        team_id,
        name.strip(),
        program_id.strip() or None,
        classification_value,
        membership_type,
    )

    return RedirectResponse(url="/admin/teams?msg=Team+updated", status_code=303)


@router.post("/teams/{id}/toggle-active", response_model=None)
async def toggle_team_active(request: Request, id: int) -> Response:
    """Toggle a team's is_active status between active and inactive.

    Args:
        request: The incoming HTTP request.
        id: The team's INTEGER primary key from the URL path.

    Returns:
        Redirect to /admin/teams with an appropriate flash message.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_integer_id, id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    new_active = await run_in_threadpool(_toggle_team_active_integer, id)
    verb = "activated" if new_active else "deactivated"

    return RedirectResponse(
        url=f"/admin/teams?msg=Team+{quote_plus(verb)}", status_code=303
    )


@router.post("/teams/{id}/discover-opponents", response_model=None)
async def discover_team_opponents(request: Request, id: int) -> Response:
    """Trigger opponent auto-discovery from a team's public game schedule.

    Fetches ``GET /public/teams/{public_id}/games``, extracts unique opponent
    names, and inserts placeholder team rows for any opponents not already in
    the database.  Requires the team to have a ``public_id``.

    Args:
        request: The incoming HTTP request.
        id: The team's INTEGER primary key from the URL path.

    Returns:
        Redirect to /admin/teams with a success or error flash message.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_integer_id, id)
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
        logger.warning("Opponent discovery failed for team %s: %s", id, exc)
        return RedirectResponse(
            url="/admin/teams?error="
            + quote_plus("Could not reach GameChanger API. Try again later."),
            status_code=303,
        )

    names = [opp.name for opp in discovered]
    count = await run_in_threadpool(bulk_create_opponents, names)

    team_name = team.get("name", str(id))
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
    only) and summary counts.  Supports ``?team_id=`` (INTEGER) for scoping to
    a single member team and ``?filter=`` for resolution state filtering.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with the opponent listing, or auth redirect/403.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team_id_filter_raw = request.query_params.get("team_id", "")
    state_filter = request.query_params.get("filter", "")
    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    team_id_filter_int: int | None = None
    if team_id_filter_raw:
        try:
            team_id_filter_int = int(team_id_filter_raw)
        except ValueError:
            team_id_filter_int = None

    links = await run_in_threadpool(
        get_opponent_links, team_id_filter_int, state_filter or None
    )
    counts = await run_in_threadpool(get_opponent_link_counts, team_id_filter_int)
    member_teams = await run_in_threadpool(_get_available_teams)

    return templates.TemplateResponse(
        request,
        "admin/opponents.html",
        {
            "links": links,
            "counts": counts,
            "member_teams": member_teams,
            "team_id_filter": team_id_filter_raw,
            "state_filter": state_filter,
            "msg": msg,
            "error": error,
            "admin_user": guard,
            "is_admin_page": True,
        },
    )


def _render_connect_error(
    request: Request, link: dict[str, Any], admin_user: Any, error: str
) -> Response:
    """Return the opponent_connect.html template in error mode."""
    return templates.TemplateResponse(
        request,
        "admin/opponent_connect.html",
        {"link": link, "mode": "error", "error": error, "admin_user": admin_user, "is_admin_page": True},
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
            "is_admin_page": True,
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


async def _parse_and_validate_opponent_url(
    request: Request,
    link: dict[str, Any],
    guard: Any,
    url_input: str,
) -> tuple[str, None] | tuple[None, Response]:
    """Parse and validate a URL input for opponent connect confirm.

    Parses the raw URL/public_id, rejects UUIDs, and rejects member-team
    public_ids.

    Args:
        request: The incoming HTTP request.
        link: The opponent link row dict.
        guard: Admin user dict.
        url_input: Raw URL/public_id string from query params.

    Returns:
        ``(public_id, None)`` on success, or ``(None, error_response)`` on
        parse/validation failure.
    """
    try:
        id_result = parse_team_url(url_input)
    except ValueError as exc:
        return None, _render_connect_error(request, link, guard, str(exc))
    if id_result.is_uuid:
        return None, _render_connect_error(
            request, link, guard,
            "Opponent teams require a GameChanger URL or public_id, not a UUID.",
        )
    public_id = id_result.value
    is_own_team = await run_in_threadpool(is_member_team_public_id, public_id)
    if is_own_team:
        return None, _render_connect_error(
            request, link, guard,
            "This URL belongs to a Lincoln program team. You cannot link an opponent to an owned team.",
        )
    return public_id, None


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

    already_resolved = _check_already_resolved(link)
    if already_resolved is not None:
        return already_resolved

    url_input = request.query_params.get("url", "").strip()
    public_id, err = await _parse_and_validate_opponent_url(
        request, link, guard, url_input
    )
    if err is not None:
        return err

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
            "is_admin_page": True,
        },
    )


def _build_connect_success_msg(opponent_name: str, duplicate_name: str | None) -> str:
    """Build the flash message for a successful manual link save."""
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
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    already_resolved = _check_already_resolved(link)
    if already_resolved is not None:
        return already_resolved

    is_own_team = await run_in_threadpool(is_member_team_public_id, public_id)
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
        url=f"/admin/opponents?team_id={our_team_id}&msg={msg}",
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
        url=f"/admin/opponents?team_id={our_team_id}&msg={msg}",
        status_code=303,
    )
