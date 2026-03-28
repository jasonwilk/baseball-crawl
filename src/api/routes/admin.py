"""Admin CRUD routes for the baseball-crawl application.

Provides server-rendered HTML views for managing user accounts and team
assignments.  All routes require admin access, granted via ADMIN_EMAIL env
var (bootstrap/fallback) OR ``users.role = 'admin'`` in the database.

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
    GET  /admin/teams/merge                              -- Team merge preview page
    POST /admin/teams/merge                              -- Execute team merge
    GET  /admin/teams/{team_id}/edit                     -- Edit team form (INTEGER team_id)
    POST /admin/teams/{team_id}/edit                     -- Update team metadata (INTEGER team_id)
    POST /admin/teams/{id}/toggle-active                 -- Toggle team is_active flag (INTEGER id)
    GET  /admin/teams/{id}/delete                        -- Delete confirmation page (INTEGER id)
    POST /admin/teams/{id}/delete                        -- Cascade delete team and all related data (INTEGER id)
    POST /admin/teams/{id}/sync                          -- Enqueue per-team crawl as BackgroundTask (INTEGER id)
    GET  /admin/programs                                 -- List all programs + add form
    POST /admin/programs                                 -- Create a new program
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

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.api.db import (
    disconnect_opponent_link,
    finalize_opponent_resolution,
    get_connection,
    get_duplicate_opponent_name,
    get_opponent_link_by_id,
    get_opponent_link_count_for_team,
    get_opponent_link_counts,
    get_opponent_links,
    get_unresolved_opponent_count,
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
    resolve_team,
)
from src.db.merge import (
    MergeBlockedError,
    MergePreview,
    find_duplicate_teams,
    merge_teams as _merge_teams_core,
    preview_merge,
)
from src.gamechanger.url_parser import parse_team_url
from src.pipeline import trigger

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals["get_unresolved_opponent_count"] = get_unresolved_opponent_count

router = APIRouter(prefix="/admin")

# Valid classification values (must match schema CHECK constraint)
_VALID_CLASSIFICATIONS = {
    "varsity", "jv", "freshman", "reserve",
    "8U", "9U", "10U", "11U", "12U", "13U", "14U",
    "legion",
}

# Valid membership_type values (must match schema CHECK constraint)
_VALID_MEMBERSHIP_TYPES = {"member", "tracked"}

# Valid role values (application-layer validation; SQLite cannot add CHECK via ALTER)
_VALID_ROLES = {"admin", "user"}

# Lowercase UUID format: 8-4-4-4-12 hex groups
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


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

    Admin access is granted if EITHER:
    - The user's email matches the ``ADMIN_EMAIL`` env var (bootstrap/fallback), OR
    - The user has ``role = 'admin'`` in the database.

    If ``ADMIN_EMAIL`` is unset AND the user does not have ``role = 'admin'``,
    access is denied (403).

    Args:
        request: The incoming HTTP request.

    Returns:
        User dict on success, Response on access denial.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    # Bootstrap/fallback: ADMIN_EMAIL env var grants admin access.
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if admin_email and user.get("email") == admin_email:
        return user

    # Primary path: database role check.
    user_role = await run_in_threadpool(_get_user_role_by_id, user["id"])
    if user_role == "admin":
        return user

    return _forbidden_response(request)


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
                "SELECT id, email, role FROM users ORDER BY email"
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
            "SELECT id, email, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def _get_user_role_by_id(user_id: int) -> str:
    """Fetch the role value for a user by id.

    Args:
        user_id: The user's primary key.

    Returns:
        Role string ('admin' or 'user'); defaults to 'user' if not found.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else "user"


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
    role: str = "user",
) -> str | None:
    """Insert a new user and their team assignments.

    Args:
        email: Normalized (lowercase) email address.
        team_ids: List of INTEGER team ids to assign.
        role: User role ('admin' or 'user').

    Returns:
        None on success, or an error message string on failure.
    """
    try:
        with closing(get_connection()) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (email, role) VALUES (?, ?)",
                    (email, role),
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
    role: str = "user",
) -> None:
    """Replace a user's team assignments and update their role.

    Args:
        user_id: The user's primary key.
        team_ids: Complete list of INTEGER team ids (replaces existing).
        role: User role ('admin' or 'user').
    """
    with closing(get_connection()) as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
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
    """Return all teams in a flat list with program name, opponent count, and latest crawl job.

    Returns:
        List of dicts with keys: id, name, program_id, membership_type,
        classification, is_active, public_id, gc_uuid, last_synced,
        program_name (nullable), opponent_count, latest_job_status (nullable),
        latest_job_started_at (nullable).
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
                ) AS opponent_count,
                cj.status AS latest_job_status,
                cj.started_at AS latest_job_started_at
            FROM teams t
            LEFT JOIN programs p ON t.program_id = p.program_id
            LEFT JOIN crawl_jobs cj ON cj.id = (
                SELECT id FROM crawl_jobs
                WHERE team_id = t.id
                ORDER BY started_at DESC
                LIMIT 1
            )
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


def _get_duplicate_groups() -> list[list[Any]]:
    """Return groups of duplicate tracked teams for the banner.

    Returns:
        List of duplicate groups from find_duplicate_teams(). Each group is a
        list of DuplicateTeam dataclass instances.
    """
    with closing(get_connection()) as conn:
        return find_duplicate_teams(conn)


def _get_teams_for_merge(team_ids: list[int]) -> list[dict[str, Any]]:
    """Fetch team details needed for the merge preview page.

    Args:
        team_ids: List of INTEGER team primary keys.

    Returns:
        List of dicts with keys: id, name, gc_uuid, public_id, membership_type,
        season_year, last_synced, game_count, has_stats, opponent_of (list of
        dicts with member team name/id/classification/season_year).
    """
    if not team_ids:
        return []
    placeholders = ",".join("?" * len(team_ids))
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT
                t.id,
                t.name,
                t.gc_uuid,
                t.public_id,
                t.membership_type,
                t.season_year,
                t.last_synced,
                (
                    SELECT COUNT(*) FROM games g
                    WHERE g.home_team_id = t.id OR g.away_team_id = t.id
                ) AS game_count,
                CASE WHEN (
                    EXISTS (SELECT 1 FROM player_season_batting  WHERE team_id = t.id)
                    OR EXISTS (SELECT 1 FROM player_season_pitching WHERE team_id = t.id)
                    OR EXISTS (SELECT 1 FROM scouting_runs        WHERE team_id = t.id)
                ) THEN 1 ELSE 0 END AS has_stats
            FROM teams t
            WHERE t.id IN ({placeholders})
            """,  # noqa: S608
            tuple(team_ids),
        ).fetchall()

        # Which member teams list each merge candidate as an opponent?
        opponent_of_rows = conn.execute(
            f"""
            SELECT
                tpo.opponent_team_id,
                mt.id              AS member_id,
                mt.name            AS member_name,
                mt.season_year     AS member_season_year,
                mt.classification  AS member_classification
            FROM team_opponents tpo
            JOIN teams mt ON mt.id = tpo.our_team_id
            WHERE tpo.opponent_team_id IN ({placeholders})
            ORDER BY mt.name
            """,  # noqa: S608
            tuple(team_ids),
        ).fetchall()

        opponent_of_map: dict[int, list[dict[str, Any]]] = {}
        for row in opponent_of_rows:
            opp_id = row["opponent_team_id"]
            opponent_of_map.setdefault(opp_id, []).append({
                "id": row["member_id"],
                "name": row["member_name"],
                "season_year": row["member_season_year"],
                "classification": row["member_classification"],
            })

    result = [dict(r) for r in rows]
    for team in result:
        team["opponent_of"] = opponent_of_map.get(team["id"], [])
    return result


def _run_preview_merge(canonical_id: int, duplicate_id: int) -> MergePreview:
    """Call preview_merge() with a fresh DB connection.

    Args:
        canonical_id: The team id to keep.
        duplicate_id: The team id to delete.

    Returns:
        MergePreview dataclass instance.
    """
    with closing(get_connection()) as conn:
        return preview_merge(canonical_id, duplicate_id, conn)


def _run_merge_teams(canonical_id: int, duplicate_id: int) -> None:
    """Call merge_teams() with a fresh DB connection.

    Args:
        canonical_id: The team id to keep.
        duplicate_id: The team id to delete.

    Raises:
        MergeBlockedError: If the merge is not allowed.
        sqlite3.Error: On database failure.
    """
    with closing(get_connection()) as conn:
        _merge_teams_core(canonical_id, duplicate_id, conn)


def _get_all_programs() -> list[dict[str, Any]]:
    """Return all programs with team count and metadata for the programs list page.

    Returns:
        List of dicts with keys: program_id, name, program_type, org_name,
        team_count, created_at.
    """
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                p.program_id,
                p.name,
                p.program_type,
                p.org_name,
                p.created_at,
                (SELECT COUNT(*) FROM teams t WHERE t.program_id = p.program_id) AS team_count
            FROM programs p
            ORDER BY p.name
            """
        ).fetchall()
    return [dict(r) for r in rows]


def _create_program(
    program_id: str,
    name: str,
    program_type: str,
    org_name: str | None,
) -> str | None:
    """Insert a new program row.

    Args:
        program_id: Operator-chosen slug (TEXT PK).
        name: Display name.
        program_type: One of 'hs', 'usssa', 'legion'.
        org_name: Optional organization name.

    Returns:
        None on success, or an error message string on failure.
    """
    try:
        with closing(get_connection()) as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO programs (program_id, name, program_type, org_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    (program_id, name, program_type, org_name or None),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return f"A program with ID '{program_id}' already exists"
    except sqlite3.Error:
        logger.exception("Failed to create program %s", program_id)
        return "Database error while creating program"
    return None


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
    gc_uuid: str | None,
) -> None:
    """Update a team's name, program, classification, membership_type, and gc_uuid.

    Args:
        team_id: The team's INTEGER primary key.
        name: New team name.
        program_id: Program slug or None.
        classification: Classification string or None.
        membership_type: 'member' or 'tracked'.
        gc_uuid: GameChanger UUID string or None (stores NULL).

    Raises:
        sqlite3.IntegrityError: If gc_uuid conflicts with an existing team's UUID.
    """
    with closing(get_connection()) as conn:
        conn.execute(
            """
            UPDATE teams
            SET name = ?, program_id = ?, classification = ?, membership_type = ?,
                gc_uuid = ?
            WHERE id = ?
            """,
            (name, program_id, classification, membership_type, gc_uuid, team_id),
        )
        conn.commit()


def _check_gc_uuid_duplicate_ci(gc_uuid_lower: str, exclude_team_id: int) -> bool:
    """Return True if any other team already has this UUID (case-insensitive).

    The unique index idx_teams_gc_uuid is case-sensitive.  This pre-save check
    catches legacy uppercase UUIDs that the index would miss.

    Args:
        gc_uuid_lower: Lowercased UUID to check.
        exclude_team_id: The team being edited -- excluded from the check.

    Returns:
        True if a duplicate exists on a different team, False otherwise.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT id FROM teams WHERE LOWER(gc_uuid) = ? AND id != ?",
            (gc_uuid_lower, exclude_team_id),
        ).fetchone()
        return row is not None


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


def _get_delete_confirmation_data(team_id: int) -> dict[str, Any]:
    """Gather row counts and relationship data for the delete confirmation page.

    Queries row counts for all tables in the 4-phase cascade deletion order
    (TN-1), shared-opponent linkages (TN-2), and orphaned-opponent detection.
    The spray_charts count uses the combined condition (game_id IN subquery
    OR team_id = T) to match what the cascade actually deletes.

    Args:
        team_id: The team's INTEGER primary key.

    Returns:
        Dict with per-table row counts, total_count, affected_opponent_teams
        (count of distinct opponent teams whose per-game stats are affected),
        shared_member_teams (list of member team names that reference this
        team as an opponent -- non-empty only for tracked teams), and
        orphaned_opponents (list of tracked opponent names that would be
        linked from no member team after deletion -- non-empty only for
        member teams).
    """
    _game_ids = "SELECT game_id FROM games WHERE home_team_id = ? OR away_team_id = ?"

    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row

        pgb_count: int = conn.execute(
            f"SELECT COUNT(*) FROM player_game_batting WHERE game_id IN ({_game_ids})",
            (team_id, team_id),
        ).fetchone()[0]

        pgp_count: int = conn.execute(
            f"SELECT COUNT(*) FROM player_game_pitching WHERE game_id IN ({_game_ids})",
            (team_id, team_id),
        ).fetchone()[0]

        games_count: int = conn.execute(
            "SELECT COUNT(*) FROM games WHERE home_team_id = ? OR away_team_id = ?",
            (team_id, team_id),
        ).fetchone()[0]

        affected_opponent_teams: int = conn.execute(
            """
            SELECT COUNT(DISTINCT CASE
                WHEN home_team_id = ? THEN away_team_id
                ELSE home_team_id
            END)
            FROM games
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND home_team_id != away_team_id
            """,
            (team_id, team_id, team_id),
        ).fetchone()[0]

        psb_count: int = conn.execute(
            "SELECT COUNT(*) FROM player_season_batting WHERE team_id = ?",
            (team_id,),
        ).fetchone()[0]

        psp_count: int = conn.execute(
            "SELECT COUNT(*) FROM player_season_pitching WHERE team_id = ?",
            (team_id,),
        ).fetchone()[0]

        # Combined condition: game-linked rows (Phase 1) + direct team_id rows (Phase 3)
        sc_count: int = conn.execute(
            f"SELECT COUNT(*) FROM spray_charts WHERE game_id IN ({_game_ids}) OR team_id = ?",
            (team_id, team_id, team_id),
        ).fetchone()[0]

        tr_count: int = conn.execute(
            "SELECT COUNT(*) FROM team_rosters WHERE team_id = ?",
            (team_id,),
        ).fetchone()[0]

        sr_count: int = conn.execute(
            "SELECT COUNT(*) FROM scouting_runs WHERE team_id = ?",
            (team_id,),
        ).fetchone()[0]

        cj_count: int = conn.execute(
            "SELECT COUNT(*) FROM crawl_jobs WHERE team_id = ?",
            (team_id,),
        ).fetchone()[0]

        uta_count: int = conn.execute(
            "SELECT COUNT(*) FROM user_team_access WHERE team_id = ?",
            (team_id,),
        ).fetchone()[0]

        ca_count: int = conn.execute(
            "SELECT COUNT(*) FROM coaching_assignments WHERE team_id = ?",
            (team_id,),
        ).fetchone()[0]

        to_count: int = conn.execute(
            "SELECT COUNT(*) FROM team_opponents WHERE our_team_id = ? OR opponent_team_id = ?",
            (team_id, team_id),
        ).fetchone()[0]

        ol_count: int = conn.execute(
            "SELECT COUNT(*) FROM opponent_links WHERE our_team_id = ? OR resolved_team_id = ?",
            (team_id, team_id),
        ).fetchone()[0]

        team_row = conn.execute(
            "SELECT membership_type FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        membership_type = team_row["membership_type"] if team_row else None

        shared_member_teams: list[str] = []
        if membership_type == "tracked":
            shared_rows = conn.execute(
                """
                SELECT DISTINCT t.name
                FROM team_opponents link
                JOIN teams t ON t.id = link.our_team_id
                WHERE link.opponent_team_id = ?
                UNION
                SELECT DISTINCT t.name
                FROM opponent_links ol
                JOIN teams t ON t.id = ol.our_team_id
                WHERE ol.resolved_team_id = ?
                """,
                (team_id, team_id),
            ).fetchall()
            shared_member_teams = [row[0] for row in shared_rows]

        orphaned_opponents: list[str] = []
        if membership_type == "member":
            orphaned_rows = conn.execute(
                """
                SELECT t.name
                FROM team_opponents link
                JOIN teams t ON t.id = link.opponent_team_id
                WHERE link.our_team_id = ?
                  AND (
                    SELECT COUNT(*) FROM team_opponents other
                    WHERE other.opponent_team_id = link.opponent_team_id
                      AND other.our_team_id != ?
                  ) = 0
                """,
                (team_id, team_id),
            ).fetchall()
            orphaned_opponents = [row[0] for row in orphaned_rows]

    total_count = (
        pgb_count + pgp_count + games_count + psb_count + psp_count
        + sc_count + tr_count + sr_count + cj_count + uta_count + ca_count
        + to_count + ol_count
    )

    return {
        "games": games_count,
        "player_game_batting": pgb_count,
        "player_game_pitching": pgp_count,
        "player_season_batting": psb_count,
        "player_season_pitching": psp_count,
        "spray_charts": sc_count,
        "team_rosters": tr_count,
        "scouting_runs": sr_count,
        "crawl_jobs": cj_count,
        "user_team_access": uta_count,
        "coaching_assignments": ca_count,
        "team_opponents": to_count,
        "opponent_links": ol_count,
        "total_count": total_count,
        "affected_opponent_teams": affected_opponent_teams,
        "shared_member_teams": shared_member_teams,
        "orphaned_opponents": orphaned_opponents,
    }


def _delete_team_cascade(team_id: int) -> None:
    """Delete a team and all related data rows in a single transaction.

    Implements the 4-phase cascade deletion order from TN-1:
      Phase 1 -- game-child rows (player_game_batting, player_game_pitching,
                 spray_charts linked via game_id)
      Phase 2 -- games (home_team_id=T OR away_team_id=T)
      Phase 3 -- direct team_id FK rows (player_season_batting,
                 player_season_pitching, spray_charts with game_id NULL,
                 team_rosters, scouting_runs, crawl_jobs, user_team_access,
                 coaching_assignments, team_opponents, opponent_links)
      Phase 4 -- teams row

    Args:
        team_id: The team's INTEGER primary key.
    """
    _game_ids = "SELECT game_id FROM games WHERE home_team_id = ? OR away_team_id = ?"

    with closing(get_connection()) as conn:
        # Phase 1 -- game-child rows
        conn.execute(
            f"DELETE FROM player_game_batting WHERE game_id IN ({_game_ids})",
            (team_id, team_id),
        )
        conn.execute(
            f"DELETE FROM player_game_pitching WHERE game_id IN ({_game_ids})",
            (team_id, team_id),
        )
        conn.execute(
            f"DELETE FROM spray_charts WHERE game_id IN ({_game_ids})",
            (team_id, team_id),
        )

        # Phase 2 -- games
        conn.execute(
            "DELETE FROM games WHERE home_team_id = ? OR away_team_id = ?",
            (team_id, team_id),
        )

        # Phase 3 -- direct team_id FKs
        conn.execute("DELETE FROM player_season_batting WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM player_season_pitching WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM spray_charts WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM team_rosters WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM scouting_runs WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM crawl_jobs WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM user_team_access WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM coaching_assignments WHERE team_id = ?", (team_id,))
        conn.execute(
            "DELETE FROM team_opponents WHERE our_team_id = ? OR opponent_team_id = ?",
            (team_id, team_id),
        )
        conn.execute(
            "DELETE FROM opponent_links WHERE our_team_id = ? OR resolved_team_id = ?",
            (team_id, team_id),
        )

        # Phase 4 -- team row
        conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        conn.commit()


def _create_crawl_job(team_id: int, sync_type: str) -> int:
    """Insert a new crawl_jobs row with status='running' and return its id.

    Args:
        team_id: The team's INTEGER primary key.
        sync_type: Either 'member_crawl' or 'scouting_crawl'.

    Returns:
        The INTEGER primary key of the newly inserted crawl_jobs row.
    """
    with closing(get_connection()) as conn:
        cursor = conn.execute(
            "INSERT INTO crawl_jobs (team_id, sync_type, status) VALUES (?, ?, 'running')",
            (team_id, sync_type),
        )
        conn.commit()
        return cursor.lastrowid


def _has_running_job(team_id: int) -> bool:
    """Return True if a crawl_jobs row with status='running' exists for team_id.

    Args:
        team_id: The team's INTEGER primary key.

    Returns:
        True if an in-progress job exists, False otherwise.
    """
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT 1 FROM crawl_jobs WHERE team_id = ? AND status = 'running' LIMIT 1",
            (team_id,),
        ).fetchone()
    return row is not None


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
                "SELECT 1 FROM teams WHERE LOWER(gc_uuid) = LOWER(?)", (gc_uuid,)
            ).fetchone()
            if row:
                return True
        # When reverify failed (gc_uuid is None), still check the Phase 1 UUID.
        # This catches the case where a row exists with gc_uuid but no public_id
        # (e.g., created by opponent_resolver) -- public_id check above misses it.
        if phase1_gc_uuid and phase1_gc_uuid != gc_uuid:
            row = conn.execute(
                "SELECT 1 FROM teams WHERE LOWER(gc_uuid) = LOWER(?)", (phase1_gc_uuid,)
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
    season_year: int | None = None,
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
        season_year: Season year from GC profile or None.

    Returns:
        The INTEGER primary key of the newly inserted team.
    """
    # season_year column added in migration 004.  Safe because the Dockerfile
    # CMD runs apply_migrations.py before uvicorn starts (no route handler can
    # execute before all migrations have been applied).
    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO teams
                (name, public_id, gc_uuid, membership_type, program_id,
                 classification, season_year, source, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'gamechanger', 1)
            """,
            (name, public_id, gc_uuid, membership_type, program_id,
             classification, season_year),
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
    role: str = Form(default="user"),
) -> Response:
    """Create a new user with team assignments.

    Normalizes email to lowercase.  Redirects back to /admin/users with a
    flash message on success, or re-renders with an error on duplicate email
    or invalid role.

    Args:
        request: The incoming HTTP request.
        email: User email address (required).
        team_ids: List of INTEGER team id values from checkboxes (as strings).
        role: User role ('admin' or 'user', default: 'user').

    Returns:
        Redirect on success, or HTMLResponse with error on failure.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    normalized_email = email.strip().lower()
    int_team_ids = [int(tid) for tid in team_ids if tid.strip().isdigit()]

    if role not in _VALID_ROLES:
        error_msg: str | None = "Invalid role; must be 'admin' or 'user'"
        role = "user"
    else:
        error_msg = await run_in_threadpool(_create_user, normalized_email, int_team_ids, role)

    if error_msg:
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
                "error": error_msg,
                "admin_user": guard,
                "form_email": normalized_email,
                "form_role": role,
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
            "error": "",
            "admin_user": guard,
            "is_admin_page": True,
        },
    )


@router.post("/users/{user_id}/edit", response_model=None)
async def update_user(
    request: Request,
    user_id: int,
    team_ids: list[str] = Form(default=[]),
    role: str = Form(default="user"),
) -> Response:
    """Update a user's team assignments and role.

    Self-demotion guard: an admin cannot set their own role to 'user'.

    Args:
        request: The incoming HTTP request.
        user_id: The user's primary key from the URL path.
        team_ids: Complete list of INTEGER team id values (replaces existing).
        role: User role ('admin' or 'user').

    Returns:
        Redirect on success, or 404/auth response.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    user = await run_in_threadpool(_get_user_by_id, user_id)
    if not user:
        return HTMLResponse(content="User not found", status_code=404)

    if role not in _VALID_ROLES:
        assigned_team_ids = await run_in_threadpool(_get_user_team_ids, user_id)
        teams = await run_in_threadpool(_get_available_teams)
        return templates.TemplateResponse(
            request,
            "admin/edit_user.html",
            {
                "edit_user": user,
                "teams": teams,
                "assigned_team_ids": assigned_team_ids,
                "error": "Invalid role; must be 'admin' or 'user'.",
                "admin_user": guard,
                "is_admin_page": True,
            },
            status_code=200,
        )

    # Self-demotion guard: prevent an admin from removing their own admin role.
    if guard["id"] == user_id and role != "admin":
        assigned_team_ids = await run_in_threadpool(_get_user_team_ids, user_id)
        teams = await run_in_threadpool(_get_available_teams)
        return templates.TemplateResponse(
            request,
            "admin/edit_user.html",
            {
                "edit_user": user,
                "teams": teams,
                "assigned_team_ids": assigned_team_ids,
                "error": "You cannot demote your own admin role.",
                "admin_user": guard,
                "is_admin_page": True,
            },
            status_code=200,
        )

    int_team_ids = [int(tid) for tid in team_ids if tid.strip().isdigit()]
    await run_in_threadpool(_update_user, user_id, int_team_ids, role)

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
    merged_canonical_id_raw = request.query_params.get("merged_canonical_id", "")
    merged_canonical_id: int | None = None
    try:
        if merged_canonical_id_raw:
            merged_canonical_id = int(merged_canonical_id_raw)
    except ValueError:
        pass

    teams = await run_in_threadpool(_get_all_teams_flat)
    duplicate_groups = await run_in_threadpool(_get_duplicate_groups)

    return templates.TemplateResponse(
        request,
        "admin/teams.html",
        {
            "teams": teams,
            "duplicate_groups": duplicate_groups,
            "msg": msg,
            "error": error,
            "added": added,
            "added_team_name": added_team_name,
            "merged_canonical_id": merged_canonical_id,
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
    if profile.year is not None:
        params["season_year"] = str(profile.year)
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
    season_year: int | None = None,
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
        season_year: Season year from GC profile or None.

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
            "season_year": season_year,
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
    season_year_raw = request.query_params.get("season_year", "")
    try:
        season_year = int(season_year_raw) if season_year_raw.strip() else None
    except ValueError:
        season_year = None

    programs = await run_in_threadpool(_get_programs)
    if not error and await run_in_threadpool(_check_duplicate_new, public_id, gc_uuid):
        error = "This team is already in the system."

    return await _render_confirm_team_page(
        request, guard, public_id, team_name, gc_uuid, gc_uuid_status,
        error, programs,
        _infer_classification(team_name),
        _infer_program_id(team_name, programs),
        season_year=season_year,
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
    season_year: str = Form(default=""),
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
    try:
        season_year_value = int(season_year) if season_year.strip() else None
    except ValueError:
        season_year_value = None

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
            season_year=season_year_value,
        )

    try:
        await run_in_threadpool(
            _insert_team_new,
            team_name, public_id, gc_uuid_value, membership_type,
            program_id_value, classification_value, season_year_value,
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


# ---------------------------------------------------------------------------
# Team merge routes
# ---------------------------------------------------------------------------


def _parse_team_ids(raw: str) -> list[int] | None:
    """Parse a comma-separated string of integer team IDs.

    Args:
        raw: Comma-separated string, e.g. "1,2,3".

    Returns:
        List of ints, or None if parsing fails or list has fewer than 2 items.
    """
    try:
        ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        return None
    return ids if len(ids) >= 2 else None


@router.get("/teams/merge", response_model=None)
async def merge_teams_page(request: Request) -> Response:
    """Render the team merge preview page.

    Accepts ``team_ids`` (comma-separated) and optionally ``canonical_id``
    (and ``duplicate_id`` for groups of 3+) as query parameters.

    On initial load (no canonical_id): renders team comparison with radio
    buttons to select the canonical team.  On reload with canonical_id:
    renders the full directional preview from preview_merge().

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with the merge preview, or redirect on invalid params.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team_ids_raw = request.query_params.get("team_ids", "")
    canonical_id_raw = request.query_params.get("canonical_id", "")
    duplicate_id_raw = request.query_params.get("duplicate_id", "")
    error = request.query_params.get("error", "")

    team_ids = _parse_team_ids(team_ids_raw)
    if team_ids is None:
        return RedirectResponse(
            url="/admin/teams?error=" + quote_plus("Merge requires at least 2 valid team IDs."),
            status_code=302,
        )

    team_rows = await run_in_threadpool(_get_teams_for_merge, team_ids)
    found_ids = {t["id"] for t in team_rows}
    if len(found_ids) < 2 or any(tid not in found_ids for tid in team_ids):
        return RedirectResponse(
            url="/admin/teams?error=" + quote_plus("One or more teams not found."),
            status_code=302,
        )

    # Order team_rows to match the team_ids order
    id_to_team = {t["id"]: t for t in team_rows}
    teams = [id_to_team[tid] for tid in team_ids if tid in id_to_team]

    # Parse canonical_id and duplicate_id from query params
    canonical_id: int | None = None
    duplicate_id: int | None = None
    try:
        if canonical_id_raw:
            canonical_id = int(canonical_id_raw)
            if canonical_id not in found_ids:
                canonical_id = None
    except ValueError:
        canonical_id = None

    try:
        if duplicate_id_raw:
            duplicate_id = int(duplicate_id_raw)
            if duplicate_id not in found_ids:
                duplicate_id = None
    except ValueError:
        duplicate_id = None

    # For 2-team case, derive duplicate automatically
    if canonical_id and len(team_ids) == 2:
        duplicate_id = next((tid for tid in team_ids if tid != canonical_id), None)

    # Run directional preview when both IDs are known
    merge_preview: MergePreview | None = None
    if canonical_id and duplicate_id and canonical_id != duplicate_id:
        merge_preview = await run_in_threadpool(_run_preview_merge, canonical_id, duplicate_id)

    # Build the team_ids query string for form actions
    team_ids_str = ",".join(str(tid) for tid in team_ids)

    return templates.TemplateResponse(
        request,
        "admin/merge_teams.html",
        {
            "teams": teams,
            "team_ids_str": team_ids_str,
            "canonical_id": canonical_id,
            "duplicate_id": duplicate_id,
            "merge_preview": merge_preview,
            "is_pairwise": len(team_ids) == 2,
            "error": error,
            "admin_user": guard,
            "is_admin_page": True,
        },
    )


@router.post("/teams/merge", response_model=None)
async def execute_merge(
    request: Request,
    canonical_id: int = Form(...),
    duplicate_id: int = Form(...),
    team_ids_str: str = Form(...),
    csrf_token: str = Form(...),  # noqa: ARG001 -- validated by middleware
) -> Response:
    """Execute a team merge and redirect.

    Calls merge_teams() with the provided canonical and duplicate IDs.  On
    success redirects to /admin/teams with a confirmation message and a
    Sync Now button.  On MergeBlockedError redirects back to the merge page.

    Args:
        request: The incoming HTTP request.
        canonical_id: The team id to keep (from form).
        duplicate_id: The team id to delete (from form).
        team_ids_str: Comma-separated team IDs for the Resolve link back (from form).
        csrf_token: CSRF token validated by the session middleware.

    Returns:
        Redirect to /admin/teams on success, or back to merge page on failure.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    # Fetch team names for the success/error messages
    team_rows = await run_in_threadpool(_get_teams_for_merge, [canonical_id, duplicate_id])
    id_to_team = {t["id"]: t for t in team_rows}
    canonical_team = id_to_team.get(canonical_id)
    duplicate_team = id_to_team.get(duplicate_id)

    if not canonical_team or not duplicate_team:
        return RedirectResponse(
            url="/admin/teams?error=" + quote_plus("One or both teams not found."),
            status_code=303,
        )

    canonical_name = canonical_team["name"]
    duplicate_name = duplicate_team["name"]

    try:
        await run_in_threadpool(_run_merge_teams, canonical_id, duplicate_id)
    except MergeBlockedError as exc:
        merge_url = (
            f"/admin/teams/merge?team_ids={quote_plus(team_ids_str)}"
            f"&canonical_id={canonical_id}&duplicate_id={duplicate_id}"
            f"&error={quote_plus(str(exc))}"
        )
        return RedirectResponse(url=merge_url, status_code=303)
    except Exception:
        logger.exception(
            "Unexpected error during merge: canonical=%d duplicate=%d",
            canonical_id,
            duplicate_id,
        )
        merge_url = (
            f"/admin/teams/merge?team_ids={quote_plus(team_ids_str)}"
            f"&canonical_id={canonical_id}&duplicate_id={duplicate_id}"
            f"&error={quote_plus('Database error during merge. No changes were made.')}"
        )
        return RedirectResponse(url=merge_url, status_code=303)

    msg = f"Merged {duplicate_name} into {canonical_name}. Stats will update on next sync."
    return RedirectResponse(
        url=f"/admin/teams?msg={quote_plus(msg)}&merged_canonical_id={canonical_id}",
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
            "error": "",
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
    gc_uuid: str = Form(default=""),
) -> Response:
    """Update a team's name, program, division, membership type, and gc_uuid.

    UUID validation is conditional (TN-1): if the submitted gc_uuid (after
    trimming) exactly matches the current DB value, validation is skipped and
    the value is preserved as-is.  New or changed non-empty values are
    lowercased and must match the standard UUID format.  Empty input stores
    NULL.  Duplicate UUID raises IntegrityError which is caught and returned
    as a form re-render with an error banner.

    Args:
        request: The incoming HTTP request.
        team_id: The team's INTEGER primary key from the URL path.
        name: New team name (required).
        program_id: Program slug (optional).
        classification: Classification string (optional).
        membership_type: 'member' or 'tracked'.
        gc_uuid: GameChanger UUID string (optional; empty → NULL).

    Returns:
        Redirect on success, re-rendered form on validation/uniqueness error,
        or 404/auth response.
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

    # Normalize and conditionally validate gc_uuid (TN-1, TN-3).
    gc_uuid_str = gc_uuid.strip()
    current_gc_uuid = team["gc_uuid"]
    error = ""
    gc_uuid_value: str | None
    gc_uuid_changed = False  # True when gc_uuid_value is a newly computed lowercase value

    if not gc_uuid_str:
        # Empty → NULL (TN-3)
        gc_uuid_value = None
    elif gc_uuid_str == current_gc_uuid:
        # Unchanged (exact match against raw DB value) → preserve as-is, skip validation
        gc_uuid_value = current_gc_uuid
    else:
        # New or changed value → lowercase, then validate format
        gc_uuid_lower = gc_uuid_str.lower()
        if not _UUID_RE.match(gc_uuid_lower):
            error = "Invalid UUID format"
            gc_uuid_value = None  # unused on error path
        else:
            gc_uuid_value = gc_uuid_lower
            gc_uuid_changed = True

    async def _rerender(err: str) -> Response:
        edit_team_ctx = {
            **team,
            "name": name.strip(),
            "program_id": program_id.strip() or None,
            "classification": classification_value,
            "membership_type": membership_type,
            "gc_uuid": gc_uuid.strip() or None,
        }
        programs_list = await run_in_threadpool(_get_programs)
        opp_count = await run_in_threadpool(get_opponent_link_count_for_team, team_id)
        return templates.TemplateResponse(
            request,
            "admin/edit_team.html",
            {
                "edit_team": edit_team_ctx,
                "programs": programs_list,
                "opponent_link_count": opp_count,
                "error": err,
                "admin_user": guard,
                "is_admin_page": True,
            },
        )

    if error:
        return await _rerender(error)

    # Pre-save case-insensitive duplicate check.  The unique index is
    # case-sensitive so it misses existing uppercase UUIDs.  This catches them.
    if gc_uuid_changed and await run_in_threadpool(
        _check_gc_uuid_duplicate_ci, gc_uuid_value, team_id
    ):
        return await _rerender("This UUID is already assigned to another team")

    try:
        await run_in_threadpool(
            _update_team_integer,
            team_id,
            name.strip(),
            program_id.strip() or None,
            classification_value,
            membership_type,
            gc_uuid_value,
        )
    except sqlite3.IntegrityError as exc:
        # Only treat as duplicate-UUID error when the constraint involves gc_uuid.
        # Other IntegrityError causes (e.g. FK violations) are re-raised.
        if "gc_uuid" in str(exc).lower():
            return await _rerender("This UUID is already assigned to another team")
        raise

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


@router.get("/teams/{id}/delete", response_model=None)
async def confirm_delete_team(request: Request, id: int) -> Response:
    """Render the cascade-delete confirmation page for a team.

    Displays the team's name, membership type, active status, per-table row
    counts, total row count, affected-game/opponent summary, shared-opponent
    warnings (for tracked teams), and orphaned-opponent notices (for member
    teams).

    Args:
        request: The incoming HTTP request.
        id: The team's INTEGER primary key from the URL path.

    Returns:
        TemplateResponse with confirmation page, or 403/404.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_integer_id, id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    counts = await run_in_threadpool(_get_delete_confirmation_data, id)

    return templates.TemplateResponse(
        request,
        "admin/confirm_delete.html",
        {"team": team, "counts": counts},
    )


@router.post("/teams/{id}/delete", response_model=None)
async def delete_team(request: Request, id: int) -> Response:
    """Permanently delete a team and all related data rows in a single transaction.

    Performs the full 4-phase cascade deletion (TN-1). The is_active guard
    is removed -- any team can be deleted regardless of active status. The
    GET confirmation page provides the safety mechanism.

    Args:
        request: The incoming HTTP request.
        id: The team's INTEGER primary key from the URL path.

    Returns:
        Redirect to /admin/teams with success flash message.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_integer_id, id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    team_name = team["name"]
    await run_in_threadpool(_delete_team_cascade, id)

    return RedirectResponse(
        url=f"/admin/teams?msg={quote_plus(f'Team \"{team_name}\" deleted.')}",
        status_code=303,
    )


@router.post("/teams/{id}/sync", response_model=None)
async def sync_team(
    request: Request, id: int, background_tasks: BackgroundTasks
) -> Response:
    """Enqueue a per-team data sync as a FastAPI BackgroundTask.

    Creates a ``crawl_jobs`` row with ``status='running'`` and enqueues the
    appropriate pipeline:
    - Member teams: ``trigger.run_member_sync`` (crawl.run + load.run).
    - Tracked teams: ``trigger.run_scouting_sync`` (ScoutingCrawler + ScoutingLoader).

    Eligibility (enforced server-side):
    - Active member teams are always eligible.
    - Active tracked teams are eligible only when ``public_id IS NOT NULL``.
    - Inactive teams and unresolved tracked teams (``public_id IS NULL``) are rejected.

    Args:
        request: The incoming HTTP request.
        id: The team's INTEGER primary key from the URL path.
        background_tasks: FastAPI BackgroundTasks injected by the framework.

    Returns:
        Redirect to /admin/teams with a flash message on success or error.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    team = await run_in_threadpool(_get_team_by_integer_id, id)
    if not team:
        return HTMLResponse(content="Team not found", status_code=404)

    # Eligibility check (AC-3 server-side enforcement).
    if not team["is_active"]:
        return RedirectResponse(
            url="/admin/teams?error=" + quote_plus("Cannot sync an inactive team."),
            status_code=303,
        )

    if team["membership_type"] == "tracked" and not team.get("public_id"):
        return RedirectResponse(
            url="/admin/teams?error="
            + quote_plus("Cannot sync unresolved team. Map a public ID first."),
            status_code=303,
        )

    # Running-job guard: reject duplicate submits / direct POSTs.
    if await run_in_threadpool(_has_running_job, id):
        team_name = team["name"]
        return RedirectResponse(
            url="/admin/teams?error="
            + quote_plus(f"Sync already in progress for {team_name}."),
            status_code=303,
        )

    sync_type = (
        "member_crawl" if team["membership_type"] == "member" else "scouting_crawl"
    )
    crawl_job_id = await run_in_threadpool(_create_crawl_job, id, sync_type)

    if team["membership_type"] == "member":
        background_tasks.add_task(
            trigger.run_member_sync, id, team["name"], crawl_job_id
        )
    else:
        background_tasks.add_task(
            trigger.run_scouting_sync, id, team["public_id"], crawl_job_id
        )

    team_name = team["name"]
    return RedirectResponse(
        url=f"/admin/teams?msg={quote_plus(f'Sync started for {team_name}.')}",
        status_code=303,
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


@router.get("/opponents/{link_id}/connect", response_model=None)
async def connect_opponent_form(request: Request, link_id: int) -> Response:
    """Redirect to the unified resolve page.

    The old connect URL-paste form is now integrated into the resolve page.
    This redirect preserves backward compatibility for bookmarks.
    """
    return RedirectResponse(
        url=f"/admin/opponents/{link_id}/resolve",
        status_code=303,
    )


@router.get("/opponents/{link_id}/connect/confirm", response_model=None)
async def connect_opponent_confirm(request: Request, link_id: int) -> Response:
    """Redirect to the unified resolve page with parsed URL.

    Preserves backward compatibility for bookmarked connect/confirm URLs.
    Parses the ``url`` query param and redirects to the resolve confirm mode.
    Retains the already-resolved guard for links that have already been connected.
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
    if url_input:
        try:
            id_result = parse_team_url(url_input)
        except ValueError:
            pass
        else:
            if not id_result.is_uuid:
                return RedirectResponse(
                    url=f"/admin/opponents/{link_id}/resolve?confirm={quote_plus(id_result.value)}",
                    status_code=303,
                )
    # Fallback: redirect to the unified resolve page
    return RedirectResponse(
        url=f"/admin/opponents/{link_id}/resolve",
        status_code=303,
    )


def _build_connect_success_msg(
    opponent_name: str,
    duplicate_name: str | None,
    *,
    scouting_triggered: bool = False,
) -> str:
    """Build the flash message for a successful manual link save."""
    scout_suffix = " Stats syncing in the background." if scouting_triggered else ""
    if duplicate_name:
        return quote_plus(
            f"Linked {opponent_name} -- note: this URL is already used by {duplicate_name}.{scout_suffix}"
        )
    return quote_plus(f"Linked {opponent_name} successfully.{scout_suffix}")


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
    background_tasks: BackgroundTasks,
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
    save_result = await run_in_threadpool(
        save_manual_opponent_link,
        link_id,
        public_id,
        our_team_id,
        link["opponent_name"],
    )

    # Auto-scout: enqueue scouting sync if the resolved team has a public_id.
    resolved_team_id = save_result.get("resolved_team_id")
    effective_public_id = save_result.get("effective_public_id")
    scouting_triggered = False
    if resolved_team_id and effective_public_id:
        crawl_job_id = await run_in_threadpool(
            _create_crawl_job, resolved_team_id, "scouting_crawl"
        )
        background_tasks.add_task(
            trigger.run_scouting_sync,
            resolved_team_id,
            effective_public_id,
            crawl_job_id,
        )
        scouting_triggered = True
    elif resolved_team_id:
        logger.warning(
            "Connected opponent '%s' (team_id=%d) has no public_id — "
            "skipping auto-scout",
            link["opponent_name"],
            resolved_team_id,
        )

    msg = _build_connect_success_msg(
        link["opponent_name"], duplicate_name, scouting_triggered=scouting_triggered,
    )
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


# ---------------------------------------------------------------------------
# Opponent resolve / skip / unhide routes (E-167-04)
# ---------------------------------------------------------------------------

_SEARCH_CONTENT_TYPE = "application/vnd.gc.com.post_search+json; version=0.0.0"


def _gc_search_teams(name: str) -> list[dict[str, Any]]:
    """Search GC teams via POST /search. Returns normalized flat dicts."""
    from src.gamechanger.client import GameChangerClient

    client = GameChangerClient()
    result = client.post_json(
        "/search",
        body={"name": name},
        params={"start_at_page": 0, "search_source": "search"},
        content_type=_SEARCH_CONTENT_TYPE,
    )
    hits = result.get("hits", []) if isinstance(result, dict) else []
    normalized: list[dict[str, Any]] = []
    for hit in hits:
        r = hit.get("result", {})
        location = r.get("location") or {}
        season = r.get("season") or {}
        normalized.append({
            "name": r.get("name"),
            "gc_uuid": r.get("id"),
            "public_id": r.get("public_id"),
            "city": location.get("city"),
            "state": location.get("state"),
            "season_year": season.get("year"),
            "season_name": season.get("name"),
            "sport": r.get("sport"),
            "num_players": r.get("number_of_players"),
            "staff": r.get("staff", []),
        })
    return normalized


@router.get("/opponents/{link_id}/resolve", response_model=None)
async def resolve_opponent_page(request: Request, link_id: int) -> Response:
    """Render the search-powered suggestion page or confirm page for opponent resolution."""
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    confirm_id = request.query_params.get("confirm", "").strip()
    gc_uuid = request.query_params.get("gc_uuid", "").strip()

    if confirm_id:
        # Confirm page: fetch team detail and check for duplicates
        try:
            profile = await run_in_threadpool(resolve_team, confirm_id)
        except (TeamNotFoundError, GameChangerAPIError) as exc:
            return templates.TemplateResponse(
                request,
                "admin/opponent_resolve.html",
                {
                    "link": link, "mode": "confirm_error",
                    "error": f"Could not fetch team: {exc}",
                    "admin_user": guard, "is_admin_page": True,
                },
            )
        public_id = profile.public_id
        duplicate_team = None
        if public_id:
            with closing(get_connection()) as conn:
                dup_row = conn.execute(
                    "SELECT id, name FROM teams WHERE public_id = ?", (public_id,)
                ).fetchone()
                if dup_row:
                    duplicate_team = {"id": dup_row[0], "name": dup_row[1]}
        return templates.TemplateResponse(
            request,
            "admin/opponent_resolve.html",
            {
                "link": link, "mode": "confirm",
                "profile": profile, "confirm_id": confirm_id,
                "gc_uuid": gc_uuid,
                "duplicate_team": duplicate_team,
                "admin_user": guard, "is_admin_page": True,
            },
        )

    # URL-paste mode: parse URL and redirect to confirm
    url_input = request.query_params.get("url", "").strip()
    if url_input:
        try:
            id_result = parse_team_url(url_input)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/opponent_resolve.html",
                {
                    "link": link, "mode": "confirm_error",
                    "error": str(exc),
                    "admin_user": guard, "is_admin_page": True,
                },
            )
        if id_result.is_uuid:
            return templates.TemplateResponse(
                request,
                "admin/opponent_resolve.html",
                {
                    "link": link, "mode": "confirm_error",
                    "error": "Opponent teams require a GameChanger URL or public_id, not a UUID.",
                    "admin_user": guard, "is_admin_page": True,
                },
            )
        parsed_public_id = id_result.value
        # Guard: reject member-team slugs
        if await run_in_threadpool(is_member_team_public_id, parsed_public_id):
            return templates.TemplateResponse(
                request,
                "admin/opponent_resolve.html",
                {
                    "link": link, "mode": "confirm_error",
                    "error": "This URL belongs to a Lincoln program team. You cannot link an opponent to an owned team.",
                    "admin_user": guard, "is_admin_page": True,
                },
            )
        return RedirectResponse(
            url=f"/admin/opponents/{link_id}/resolve?confirm={quote_plus(parsed_public_id)}",
            status_code=303,
        )

    # Search mode
    q = request.query_params.get("q", "").strip() or link["opponent_name"]

    results: list[dict[str, Any]] = []
    search_error: str | None = None
    try:
        results = await run_in_threadpool(_gc_search_teams, q)
    except Exception as exc:
        search_error = str(exc)
        logger.warning("GC search failed for link %d: %s", link_id, exc)

    return templates.TemplateResponse(
        request,
        "admin/opponent_resolve.html",
        {
            "link": link, "mode": "search",
            "results": results, "search_error": search_error,
            "q": q,
            "admin_user": guard, "is_admin_page": True,
        },
    )


@router.post("/opponents/{link_id}/resolve", response_model=None)
async def resolve_opponent_confirm(
    request: Request,
    link_id: int,
    background_tasks: BackgroundTasks,
    confirm_id: str = Form(...),
    gc_uuid: str = Form(""),
) -> Response:
    """Confirm opponent resolution from a GC search result."""
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    # Guard: reject member-team slugs
    if await run_in_threadpool(is_member_team_public_id, confirm_id):
        msg = quote_plus("Cannot link an opponent to a Lincoln program team.")
        return RedirectResponse(
            url=f"/admin/opponents/{link_id}/resolve?error={msg}",
            status_code=303,
        )

    from src.db.teams import ensure_team_row

    # confirm_id is a public_id slug; gc_uuid is the progenitor_team_id UUID.
    # resolve_team() fetches the public profile to get name/year.
    profile = None
    try:
        profile = await run_in_threadpool(resolve_team, confirm_id)
    except (TeamNotFoundError, GameChangerAPIError):
        logger.warning(
            "resolve_team(%r) failed during confirm POST", confirm_id,
        )

    if profile is not None:
        team_name = profile.name
        input_public_id = profile.public_id or confirm_id
        season_year = profile.year
    else:
        team_name = link["opponent_name"]
        input_public_id = confirm_id
        season_year = None

    with closing(get_connection()) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        team_id = ensure_team_row(
            conn,
            gc_uuid=gc_uuid or None,
            public_id=input_public_id,
            name=team_name,
            season_year=season_year,
            source="admin_resolve",
        )
        # Read back the team's actual public_id (ensure_team_row may have
        # skipped the public_id backfill due to a collision).
        actual_pub = conn.execute(
            "SELECT public_id FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        effective_public_id = actual_pub[0] if actual_pub else None
        conn.execute(
            """
            UPDATE opponent_links
            SET resolved_team_id = ?, public_id = ?,
                resolution_method = 'search', resolved_at = datetime('now')
            WHERE id = ?
            """,
            (team_id, effective_public_id, link_id),
        )
        # Write-through: propagate resolution to team_opponents, activate team,
        # and reassign FK references from any old stub.
        wt_result = finalize_opponent_resolution(
            conn,
            our_team_id=link["our_team_id"],
            resolved_team_id=team_id,
            opponent_name=link["opponent_name"],
        )
        conn.commit()

    # Auto-scout: enqueue scouting sync if the resolved team has a public_id.
    resolved_public_id = wt_result["public_id"]
    if resolved_public_id:
        crawl_job_id = await run_in_threadpool(
            _create_crawl_job, team_id, "scouting_crawl"
        )
        background_tasks.add_task(
            trigger.run_scouting_sync, team_id, resolved_public_id, crawl_job_id
        )
        msg = quote_plus(
            f"Resolved {link['opponent_name']} via search. Stats syncing in the background."
        )
    else:
        logger.warning(
            "Resolved opponent '%s' (team_id=%d) has no public_id — "
            "skipping auto-scout",
            link["opponent_name"],
            team_id,
        )
        msg = quote_plus(f"Resolved {link['opponent_name']} via search.")

    return RedirectResponse(
        url=f"/admin/opponents?filter=unresolved&msg={msg}",
        status_code=303,
    )


@router.post("/opponents/{link_id}/skip", response_model=None)
async def skip_opponent(request: Request, link_id: int) -> Response:
    """Mark an opponent as 'no match' by setting is_hidden = 1."""
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE opponent_links SET is_hidden = 1 WHERE id = ?", (link_id,)
        )
        conn.commit()

    msg = quote_plus(f"Skipped {link['opponent_name']} (hidden).")
    return RedirectResponse(
        url=f"/admin/opponents?filter=unresolved&msg={msg}",
        status_code=303,
    )


@router.post("/opponents/{link_id}/unhide", response_model=None)
async def unhide_opponent(request: Request, link_id: int) -> Response:
    """Restore a hidden opponent by setting is_hidden = 0."""
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    link = await run_in_threadpool(get_opponent_link_by_id, link_id)
    if not link:
        return HTMLResponse(content="Opponent link not found", status_code=404)

    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE opponent_links SET is_hidden = 0 WHERE id = ?", (link_id,)
        )
        conn.commit()

    msg = quote_plus(f"Unhid {link['opponent_name']}.")
    return RedirectResponse(
        url=f"/admin/opponents?filter=hidden&msg={msg}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Program management routes
# ---------------------------------------------------------------------------

_VALID_PROGRAM_TYPES = {"hs", "usssa", "legion"}


@router.get("/programs", response_model=None)
async def list_programs(request: Request) -> Response:
    """Render the program management page.

    Requires admin session.  Lists all programs and provides an Add Program form.

    Args:
        request: The incoming HTTP request.

    Returns:
        HTMLResponse with the program list, or an auth redirect/403.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    programs = await run_in_threadpool(_get_all_programs)

    return templates.TemplateResponse(
        request,
        "admin/programs.html",
        {
            "programs": programs,
            "msg": msg,
            "error": error,
            "admin_user": guard,
            "is_admin_page": True,
        },
    )


@router.post("/programs", response_model=None)
async def create_program(
    request: Request,
    program_id: str = Form(...),
    name: str = Form(...),
    program_type: str = Form(...),
    org_name: str = Form(default=""),
) -> Response:
    """Create a new program.

    Validates program_type, then inserts the program row.  Redirects back to
    /admin/programs with a success flash, or re-renders with an error on
    duplicate program_id or invalid input.

    Args:
        request: The incoming HTTP request.
        program_id: Operator-chosen slug (TEXT PK).
        name: Display name.
        program_type: One of 'hs', 'usssa', 'legion'.
        org_name: Optional organization name.

    Returns:
        Redirect on success, or HTMLResponse with error on failure.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    cleaned_id = program_id.strip()
    cleaned_name = name.strip()
    cleaned_type = program_type.strip().lower()
    cleaned_org = org_name.strip() or None

    if cleaned_type not in _VALID_PROGRAM_TYPES:
        programs = await run_in_threadpool(_get_all_programs)
        return templates.TemplateResponse(
            request,
            "admin/programs.html",
            {
                "programs": programs,
                "msg": "",
                "error": "Invalid program type. Must be hs, usssa, or legion.",
                "admin_user": guard,
                "is_admin_page": True,
                "form_program_id": cleaned_id,
                "form_name": cleaned_name,
                "form_program_type": cleaned_type,
                "form_org_name": org_name.strip(),
            },
        )

    error = await run_in_threadpool(
        _create_program, cleaned_id, cleaned_name, cleaned_type, cleaned_org
    )

    if error:
        programs = await run_in_threadpool(_get_all_programs)
        return templates.TemplateResponse(
            request,
            "admin/programs.html",
            {
                "programs": programs,
                "msg": "",
                "error": error,
                "admin_user": guard,
                "is_admin_page": True,
                "form_program_id": cleaned_id,
                "form_name": cleaned_name,
                "form_program_type": cleaned_type,
                "form_org_name": org_name.strip(),
            },
        )

    success_msg = quote_plus(f"Program '{cleaned_name}' created successfully.")
    return RedirectResponse(
        url=f"/admin/programs?msg={success_msg}", status_code=303
    )


# ---------------------------------------------------------------------------
# Reports management
# ---------------------------------------------------------------------------


def _get_all_reports() -> list[dict[str, Any]]:
    """Return all reports sorted by generated_at descending."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base_url = os.environ.get("APP_URL", "http://localhost:8001").rstrip("/")
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, slug, title, status, generated_at, expires_at, "
            "report_path, error_message FROM reports ORDER BY generated_at DESC"
        ).fetchall()
    result = []
    for row in rows:
        r = dict(row)
        r["url"] = f"{base_url}/reports/{r['slug']}"
        r["is_expired"] = r["expires_at"] < now
        result.append(r)
    return result


def _delete_report(report_id: int) -> None:
    """Delete a report row and its HTML file from disk."""
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT report_path FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if row and row["report_path"]:
            file_path = Path(__file__).resolve().parents[3] / "data" / row["report_path"]
            if file_path.is_file():
                file_path.unlink()
                logger.info("Deleted report file: %s", file_path)
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()


@router.get("/reports", response_model=None)
async def list_reports(request: Request) -> Response:
    """Render the admin reports management page.

    Shows a URL input form for generating new reports and a table of all
    existing reports with status badges, links, and delete actions.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    msg = request.query_params.get("msg", "")
    error = request.query_params.get("error", "")

    reports = await run_in_threadpool(_get_all_reports)
    has_generating = any(r["status"] == "generating" for r in reports)

    return templates.TemplateResponse(
        request,
        "admin/reports.html",
        {
            "reports": reports,
            "msg": msg,
            "error": error,
            "has_generating": has_generating,
        },
    )


@router.post("/reports/generate", response_model=None)
async def generate_report_admin(
    request: Request,
    background_tasks: BackgroundTasks,
    gc_url: str = Form(...),
) -> Response:
    """Start report generation as a background task.

    Validates the URL, then enqueues ``generate_report()`` via FastAPI
    BackgroundTasks. Redirects to the reports list with a flash message.
    """
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    gc_url = gc_url.strip()
    if not gc_url:
        return RedirectResponse(
            url="/admin/reports?error=" + quote_plus("Please enter a GameChanger URL."),
            status_code=303,
        )

    # Validate the URL
    try:
        parsed = parse_team_url(gc_url)
    except ValueError as exc:
        return RedirectResponse(
            url="/admin/reports?error=" + quote_plus(f"Invalid URL: {exc}"),
            status_code=303,
        )

    if parsed.is_uuid:
        return RedirectResponse(
            url="/admin/reports?error=" + quote_plus(
                "UUID-based URLs are not supported. Use a public team URL."
            ),
            status_code=303,
        )

    from src.reports.generator import generate_report
    background_tasks.add_task(generate_report, gc_url)

    msg = f"Report generation started for {gc_url}. This may take a few minutes."
    return RedirectResponse(
        url=f"/admin/reports?msg={quote_plus(msg)}", status_code=303
    )


@router.post("/reports/{report_id}/delete", response_model=None)
async def delete_report(request: Request, report_id: int) -> Response:
    """Delete a report (DB row + file on disk)."""
    guard = await _require_admin(request)
    if isinstance(guard, Response):
        return guard

    await run_in_threadpool(_delete_report, report_id)
    return RedirectResponse(
        url="/admin/reports?msg=" + quote_plus("Report deleted."),
        status_code=303,
    )
