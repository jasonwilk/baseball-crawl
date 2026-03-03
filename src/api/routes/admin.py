"""Admin CRUD routes for the baseball-crawl application.

Provides server-rendered HTML views for managing user accounts and team
assignments.  All routes require an active session with ``is_admin=1``.

Routes:
    GET  /admin/users                    -- List all users
    POST /admin/users                    -- Create new user
    GET  /admin/users/{user_id}/edit     -- Edit user form
    POST /admin/users/{user_id}/edit     -- Update user
    POST /admin/users/{user_id}/delete   -- Delete user (cascade)
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

from src.api.db import get_connection

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
