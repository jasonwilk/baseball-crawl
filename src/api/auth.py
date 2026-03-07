"""Session middleware and auth helpers for the baseball-crawl application.

Provides:
- ``SessionMiddleware``: Starlette BaseHTTPMiddleware that validates session
  cookies on every protected request, attaches ``request.state.user`` and
  ``request.state.permitted_teams``, and redirects unauthenticated requests to
  the login page.
- ``create_session``: Creates a new session row in the DB and returns the raw
  session token to set as a cookie.
- ``hash_token``: SHA-256 hex digest helper.

Dev bypass:
    When ``DEV_USER_EMAIL`` is set, the middleware auto-creates a session for
    that email on every request, creating the user in the DB if needed.

Excluded paths (no session check):
    /  /auth/*  /health  /static/*
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sqlite3
from contextlib import closing
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.api.db import get_connection

logger = logging.getLogger(__name__)

_SESSION_COOKIE_NAME = "session"
_SESSION_TTL_DAYS = 7
_SESSION_MAX_AGE = 604800  # 7 days in seconds

# Paths excluded from session validation
_EXCLUDED_PREFIXES = ("/auth/", "/health", "/static/")
# Exact paths excluded from session validation (matched before prefix check)
_EXCLUDED_EXACT = ("/",)


def hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of the given token string.

    Args:
        raw_token: Raw token string to hash.

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _is_excluded_path(path: str) -> bool:
    """Return True if path is excluded from session checks.

    Args:
        path: URL path to test.

    Returns:
        True when path matches an excluded exact path or starts with an excluded prefix.
    """
    if path in _EXCLUDED_EXACT:
        return True
    # Normalise to ensure /auth (without trailing slash) is also excluded.
    normalized = path if path.endswith("/") else path + "/"
    return any(
        path.startswith(prefix) or normalized.startswith(prefix)
        for prefix in _EXCLUDED_PREFIXES
    )


def create_session(user_id: int) -> str:
    """Create a new session in the database and return the raw session token.

    Generates a ``secrets.token_hex(32)`` raw token, stores its SHA-256 hash
    in the ``sessions`` table with a 7-day expiry.

    Args:
        user_id: The authenticated user's database ID.

    Returns:
        Raw 64-character hex session token to be set as a cookie.

    Raises:
        sqlite3.Error: If the database write fails.
    """
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_token_hash, user_id, expires_at)
            VALUES (?, ?, datetime('now', '+7 days'))
            """,
            (token_hash, user_id),
        )
        conn.commit()
    return raw_token


def _get_user_by_email(conn: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    """Fetch user row by email; returns None if not found."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT user_id, email, display_name, is_admin FROM users WHERE email = ?",
        (email,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _create_dev_user(conn: sqlite3.Connection, email: str) -> dict[str, Any]:
    """Insert a dev admin user and return the new row dict."""
    cursor = conn.execute(
        "INSERT INTO users (email, display_name, is_admin) VALUES (?, ?, 1)",
        (email, "Dev Admin"),
    )
    conn.commit()
    user_id = cursor.lastrowid
    return {
        "user_id": user_id,
        "email": email,
        "display_name": "Dev Admin",
        "is_admin": 1,
    }


def _get_permitted_teams(conn: sqlite3.Connection, user: dict[str, Any]) -> list[str]:
    """Return the list of permitted team_ids for the user.

    Admins receive all is_owned=1 team_ids.  Non-admins receive only their
    explicitly granted team_ids from user_team_access.

    Args:
        conn: Open SQLite connection.
        user: User dict with at least ``user_id`` and ``is_admin``.

    Returns:
        List of team_id strings.
    """
    if user.get("is_admin"):
        cursor = conn.execute(
            "SELECT team_id FROM teams WHERE is_owned = 1"
        )
    else:
        cursor = conn.execute(
            "SELECT team_id FROM user_team_access WHERE user_id = ?",
            (user["user_id"],),
        )
    return [row[0] for row in cursor.fetchall()]


def _resolve_session_from_cookie(
    cookie_value: str,
) -> dict[str, Any] | None:
    """Look up a session by raw cookie token.

    Hashes the token, checks ``sessions`` for a non-expired row, then fetches
    the user and their permitted teams.

    Args:
        cookie_value: Raw session token from the cookie.

    Returns:
        Dict with keys ``user`` and ``permitted_teams`` if valid; None otherwise.
    """
    token_hash = hash_token(cookie_value)
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT s.user_id
                FROM sessions s
                WHERE s.session_token_hash = ?
                  AND s.expires_at > datetime('now')
                """,
                (token_hash,),
            )
            session_row = cursor.fetchone()
            if not session_row:
                return None

            user_id = session_row["user_id"]
            cursor = conn.execute(
                "SELECT user_id, email, display_name, is_admin FROM users WHERE user_id = ?",
                (user_id,),
            )
            user_row = cursor.fetchone()
            if not user_row:
                return None

            user = dict(user_row)
            permitted_teams = _get_permitted_teams(conn, user)
            return {"user": user, "permitted_teams": permitted_teams}
    except sqlite3.OperationalError:
        # Re-raise OperationalError (e.g., "no such table") so the
        # middleware's dispatch() can handle graceful degradation.
        raise
    except sqlite3.Error:
        logger.exception("DB error resolving session")
        return None


def _handle_dev_bypass(email: str) -> dict[str, Any] | None:
    """Auto-create or fetch user for dev bypass.

    Args:
        email: The DEV_USER_EMAIL value.

    Returns:
        Dict with ``user`` and ``permitted_teams``; None on DB error.
    """
    try:
        with closing(get_connection()) as conn:
            user = _get_user_by_email(conn, email)
            if not user:
                user = _create_dev_user(conn, email)
            permitted_teams = _get_permitted_teams(conn, user)
            return {"user": user, "permitted_teams": permitted_teams}
    except sqlite3.OperationalError:
        # Let OperationalError propagate so dispatch() can handle schema errors
        # (e.g., "no such table") with a 503 response.
        raise
    except sqlite3.Error:
        logger.exception("DB error in dev bypass for %s", email)
        return None


class SessionMiddleware(BaseHTTPMiddleware):
    """Validate session cookies on protected routes.

    On each request:
    1. If the path is excluded (/auth/*, /health, /static/*), pass through.
    2. If DEV_USER_EMAIL is set, handle dev bypass (auto-create session state).
    3. Otherwise, read the ``session`` cookie, validate it, and attach
       ``request.state.user`` and ``request.state.permitted_teams``.
    4. If validation fails, redirect to /auth/login.

    Handles missing ``users`` table gracefully (logs warning, allows through).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        dev_email = os.environ.get("DEV_USER_EMAIL", "")
        if dev_email:
            app_env = os.environ.get("APP_ENV", "")
            if app_env.lower() == "production":
                raise RuntimeError(
                    "DEV_USER_EMAIL must not be set in production (APP_ENV=production). "
                    "Remove DEV_USER_EMAIL from the environment before starting the app."
                )
            logger.info("[DEV] Auth bypass active for: %s", dev_email)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process the request through session middleware.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response from downstream handlers, or a redirect to /auth/login.
        """
        path = request.url.path

        if _is_excluded_path(path):
            return await call_next(request)

        dev_email = os.environ.get("DEV_USER_EMAIL", "")
        if dev_email:
            try:
                state = _handle_dev_bypass(dev_email)
                if state:
                    request.state.user = state["user"]
                    request.state.permitted_teams = state["permitted_teams"]
                    return await call_next(request)
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower():
                    logger.warning(
                        "Auth table missing (migration not applied?); "
                        "returning 503: %s",
                        path,
                    )
                    from starlette.responses import PlainTextResponse
                    return PlainTextResponse(
                        "Service temporarily unavailable", status_code=503
                    )
                raise

        cookie_value = request.cookies.get(_SESSION_COOKIE_NAME, "")
        if not cookie_value:
            # Fail closed: check auth tables exist before redirecting to login.
            # If tables are missing, return 503 so the error is visible rather
            # than silently sending an unauthenticated user to the login page
            # against a broken schema.
            try:
                with closing(get_connection()) as conn:
                    conn.execute("SELECT 1 FROM sessions LIMIT 1")
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower():
                    logger.warning(
                        "Auth table missing (migration not applied?); "
                        "returning 503: %s",
                        path,
                    )
                    from starlette.responses import PlainTextResponse
                    return PlainTextResponse(
                        "Service temporarily unavailable", status_code=503
                    )
                raise
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/auth/login", status_code=302)

        try:
            state = _resolve_session_from_cookie(cookie_value)
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                logger.warning(
                    "Auth table missing (migration not applied?); "
                    "returning 503: %s",
                    path,
                )
                from starlette.responses import PlainTextResponse
                return PlainTextResponse(
                    "Service temporarily unavailable", status_code=503
                )
            raise

        if not state:
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/auth/login", status_code=302)

        request.state.user = state["user"]
        request.state.permitted_teams = state["permitted_teams"]
        return await call_next(request)
