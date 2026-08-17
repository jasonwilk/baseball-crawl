"""Admin routes for the surviving baseball-crawl surfaces.

Provides server-rendered HTML views for the two admin surfaces that survive the
E-239 quarantine-then-removal pass:

- **Reports management** (the live product surface): list, generate, and delete
  standalone scouting reports.
- **User management** (auth / E-023 infrastructure): create, edit, and delete
  user accounts and their team assignments.

All routes require admin access, granted via the ``ADMIN_EMAIL`` env var
(bootstrap/fallback) OR ``users.role = 'admin'`` in the database.  This module
imports the canonical ``user_is_admin`` predicate from ``src.api.auth`` so
exactly one copy of the admin check exists.

This module was extracted out of the former ``src/api/routes/admin.py`` precisely
to sever its coupling chains onto the E-239 deletion set (E-239-01); the dead
team-management, opponent-resolution, and program-admin routes did NOT carry
over.  Every module in that deletion set has since been removed outright (E-239,
E-246, E-256), so those chains can no longer be re-formed by accident.

Routes:
    GET  /admin/users                 -- List all users
    POST /admin/users                 -- Create new user
    GET  /admin/users/{user_id}/edit  -- Edit user form
    POST /admin/users/{user_id}/edit  -- Update user
    POST /admin/users/{user_id}/delete-- Delete user (cascade)
    GET  /admin/reports               -- List all reports + generate form
    POST /admin/reports/generate      -- Start report generation (background)
    POST /admin/reports/{id}/delete   -- Delete a report (row + file)
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.api.auth import user_is_admin
from src.api.db import get_connection, list_reports_with_runs
from src.api.helpers import get_app_url
from src.gamechanger.url_parser import parse_team_url
from src.reports.lifecycle import reap_stale_generating_reports
from src.util.timezone import utcnow_iso

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/admin")

# Valid role values (application-layer validation; SQLite cannot add CHECK via ALTER)
_VALID_ROLES = {"admin", "user"}

# Admission cap for POST /admin/reports/generate.
#
# WARRANT. A generation submitted here runs as a plain sync `generate_report`
# handed to Starlette's BackgroundTask, which sends it to `run_in_threadpool` ->
# `anyio.to_thread.run_sync` with no limiter, i.e. the DEFAULT anyio limiter --
# 40 tokens in this container. So every submission got its own thread and the
# only ceiling in the system was 40. A measured 2026-08-10 operator run put 14
# simultaneous generations against the one SQLite file, exhausting the 30s
# busy_timeout and producing 243 `database is locked` tracebacks. This is the
# admission check that run had none of; `busy_timeout` is deliberately untouched,
# because waiting longer only moves the cliff.
#
# ⚠ LOAD-BEARING PREMISE: this is an IN-PROCESS cap, so it is a real cap only
# while the app is deployed as exactly ONE process serving HTTP -- one container,
# one uvicorn worker, not replicated. The half of that premise living in tracked
# files is pinned by
# tests/test_admin_reports.py::TestTheCheckedInTopology. Two halves CANNOT be
# tested and are enforced only by the deployment invariant in
# `docs/admin/operations.md`: runtime replication of the container, and a
# `WEB_CONCURRENCY` entry in the untracked env file, which uvicorn reads directly
# to set its worker count. Either multiplies this cap and nothing warns you.
#
# ⚠ THIS CONSTANT ALONE DOES NOT MAKE THE PAGE SAFE, and reading it that way is
# how the 2026-08-16 incident happened. `bb report generate` /
# `bb report morning-run` write the same WAL file in ANOTHER PROCESS, which no
# in-process counter can see. That door is guarded separately, by
# `_a_generation_is_in_flight` below -- and because that gate cannot tell a CLI
# run from this page's own generation, the page is effectively ONE-AT-A-TIME and
# this constant only binds inside the window before a `generating` row exists.
# The CLI itself remains uncapped BY DESIGN (operator ruling); the admin door
# DEFERS to it rather than capping it.
MAX_CONCURRENT_ADMIN_GENERATIONS = 2

# BoundedSemaphore, not Semaphore, deliberately: a double-release bug raises
# ValueError loudly instead of silently inflating the cap.
_generation_slots = threading.BoundedSemaphore(MAX_CONCURRENT_ADMIN_GENERATIONS)


def _a_generation_is_in_flight() -> bool:
    """True when ANY report generation is running, from any process.

    The cross-path gate (operator ruling 2026-08-16). The semaphore above is an
    IN-PROCESS bound and structurally cannot see `bb report generate` or
    `bb report morning-run`, which write this same SQLite file. On 2026-08-16 an
    admin click raced the serial CLI restore run: it hard-deleted stat rows on
    games the CLI was actively writing, forced the CLI to skip orphan
    reclamation, and produced a report served as `ready` carrying 155
    uncorrected reconciliation discrepancies. Per-path caps do not compose.

    Reap-then-count, in that ORDER, reusing the canonical reaper rather than
    growing a second copy of it (`.claude/rules/canonical-seams.md`; the same
    sequence `reclaim_orphan_reference_data` already uses).

    The order is load-bearing, but NOT for the reason an earlier version of this
    comment gave (it claimed reaping first avoids wedging the page "for the full
    STALE_GENERATING_SECONDS = 3600", which is wrong in both directions and is
    corrected here). The reaper only selects rows ALREADY older than that
    threshold, so reaping first does not shorten the hour for anybody: a
    generation younger than the threshold blocks this page under either order,
    and that is correct -- it is probably alive. What the order actually buys is
    that once a crashed row IS past the threshold, this call clears it and
    admits the submission in the SAME request. Counting first would report the
    stale row as live and refuse, clearing it only for some LATER submission --
    or never, if a future edit turns the count into an early return.

    ⚠ The reaper UPDATEs rows, unlinks orphan HTML, and COMMITS unconditionally
    even when it reaps nothing -- so this is NOT a passive read on a serving
    route. It is why this chunk owes a `/security-review`.

    ⚠ We pass our OWN connection rather than None. `_conn_scope(None)` resolves
    `lifecycle.get_connection`, which test fixtures do not patch -- passing None
    would point this gate at the real data/app.db. The injected-connection seam
    exists precisely so the caller's sandbox travels with the connection.

    ⚠ There is NO source column on `reports`, so this cannot distinguish a CLI
    run from this page's own in-flight generation. By operator ruling the admin
    page is therefore ONE-AT-A-TIME; the semaphore still covers the window
    between the click and the `generating` row being written, which this gate is
    blind to.
    """
    try:
        with closing(get_connection()) as conn:
            result = reap_stale_generating_reports(conn)
            if result.errors:
                # Gated on `errors` ALONE, which since 2026-08-17 means exactly
                # "the ROW could not be cleared" -- a row still 'generating',
                # which the count two lines below WILL see and refuse on. That
                # is a real wedge, and the operator otherwise sees only the
                # generic banner with no way to learn the reap failed.
                #
                # A failed orphan-HTML unlink is deliberately NOT here: after
                # the 2026-08-16 reorder those rows are already 'failed', so
                # this count no longer sees them and they refuse nothing.
                # `ReaperResult.files_failed` carries them instead, and the
                # reaper logs each one at WARNING. Before the counters were
                # split, every stray file produced this ERROR and told the
                # operator the page was wedged when it was not.
                logger.error(
                    "Stale-'generating' reaper could not clear %d row(s) while "
                    "gating the admin generate route; each will keep refusing "
                    "submissions from this page until it is resolved.",
                    result.errors,
                )
            return bool(
                conn.execute(
                    "SELECT COUNT(*) FROM reports WHERE status = 'generating'"
                ).fetchone()[0]
            )
    except Exception:
        # FAIL CLOSED. The reaper's SELECT and its final commit sit OUTSIDE its
        # per-row error isolation, so `database is locked` propagates out of here
        # -- and that is precisely the contention this gate exists to handle (a
        # CLI generation holding the same WAL file). Letting it escape would
        # return a 500 instead of the designed 303 flash. Refusing on an
        # unreadable signal is the house rule: a missing safety signal defaults
        # to REFUSE, never to proceed (`.claude/rules/python-style.md`).
        logger.exception(
            "Could not determine whether a generation is in flight; refusing the "
            "submission rather than racing an unknown writer."
        )
        return True


def _generate_report_releasing_slot(gc_url: str) -> None:
    """Run a generation and hand its slot back, however it ends.

    The import stays INSIDE the function, as it was at the original call site.
    That is load-bearing for the existing tests, which patch
    ``src.reports.generator.generate_report`` and assert on the call -- only a
    call-time import resolves through the patch.

    ⚠ The import is INSIDE the ``try``, not above it. The slot is acquired in the
    route BEFORE this task runs, so an exception raised by the import itself
    (``ImportError`` from a circular-import regression, a missing transitive
    dependency) would otherwise skip the ``finally`` and leak the slot
    PERMANENTLY -- two such failures wedge the generate page until the process
    restarts. Pinned by
    ``TestAdminGenerate_WhenTheGenerationImportFails::test_the_slot_is_still_returned``.
    """
    try:
        from src.reports.generator import generate_report

        generate_report(gc_url)
    finally:
        _generation_slots.release()


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
    access is denied (403).  The admin check delegates to the canonical
    predicate in ``auth.py`` so exactly one copy of this security check exists.

    Args:
        request: The incoming HTTP request.

    Returns:
        User dict on success, Response on access denial.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    if await run_in_threadpool(user_is_admin, user):
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
# Reports management
# ---------------------------------------------------------------------------


def _get_all_reports() -> list[dict[str, Any]]:
    """Return all reports (joined to their run record) sorted by generated_at desc.

    Uses the shared ``list_reports_with_runs`` join (src/api/db.py) so this admin
    surface and the CLI ``list_reports()`` read the same 1:1 LEFT JOIN
    (E-235-06 / TN-6). Each dict gains the per-stage ``report_generation_runs``
    columns and the operator-only trust flag (``identity_match_method``);
    ``error_message`` was already selected here.
    Run columns are NULL for legacy reports with no run row (LEFT join).
    """
    now = utcnow_iso()
    base_url = get_app_url()
    with closing(get_connection()) as conn:
        result = list_reports_with_runs(conn)
    for r in result:
        r["url"] = f"{base_url}/reports/{r['slug']}"
        r["is_expired"] = r["expires_at"] < now
        # E-236-07 AC-3 / TN-3: derived operator-"degraded" flag, computed at
        # READ time (no schema column). True when the run finished
        # (overall_status == 'completed') yet some stage degraded to 'partial'
        # or 'failed' -- the run "succeeded" overall but a stage is not clean,
        # so the operator should drill in. OPERATOR-ONLY (coach C3): this flag
        # never reaches the coach footer.
        r["operator_degraded"] = (
            r.get("overall_status") == "completed"
            and any(
                r.get(col) in ("partial", "failed")
                for col in (
                    "crawl_status", "load_status", "gc_uuid_status",
                    "spray_status", "plays_status", "reconciliation_status",
                    "enrichment_status",
                )
            )
        )
    return result


def _delete_report(report_id: int) -> None:
    """Delete a report row, its HTML file, and cascade-delete team data if safe.

    Reads ``team_id`` from the report row before deletion (the FK is lost
    after the row is removed).  After removing the report row and file,
    checks guard conditions and cascade-deletes the team and all dependent
    data when the team is not independently tracked.
    """
    # E-256-04 / TN-13: the deletion cascade lives in the client-free lifecycle
    # module, so this path no longer pulls httpx/jinja2 in transitively through
    # the generation stack just to delete a team.
    from src.reports.lifecycle import (
        cascade_delete_team,
        is_team_eligible_for_cleanup,
        reclaim_orphan_reference_data,
    )

    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT report_path, team_id FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if not row:
            return

        report_path = row["report_path"]
        team_id = row["team_id"]

        # Delete the HTML file from disk
        if report_path:
            file_path = Path(__file__).resolve().parents[3] / "data" / report_path
            if file_path.is_file():
                file_path.unlink()
                logger.info("Deleted report file: %s", file_path)

        # Check guard conditions BEFORE deleting the report row
        # (the multi-report guard needs the row to still exist, but we
        # exclude this report_id from the count)
        eligible = is_team_eligible_for_cleanup(conn, team_id, report_id)

        # Delete the report row. report_generation_runs FK-references reports(id)
        # with ON DELETE CASCADE (migration 002), so this DELETE also removes the
        # report's run record -- satisfying the cleanup-detection mirror invariant
        # (E-235-05 / TN-5). The cascade fires because get_connection() sets
        # PRAGMA foreign_keys=ON (src/api/db.py:55) on THIS connection (conn1),
        # the one that deletes the reports row. No explicit
        # `DELETE FROM report_generation_runs` is needed; were the pragma ever
        # off here, the cascade (and every other FK on this path) would silently
        # not fire -- the AC-1 test asserts the run row is gone after this call.
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()

    # Cascade-delete team data if eligible
    if eligible:
        try:
            with closing(get_connection()) as conn:
                cascade_delete_team(conn, team_id)
            logger.info(
                "Cascade-deleted team_id=%d after report %d removal.",
                team_id, report_id,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Cascade-delete failed for team_id=%d after report %d removal.",
                team_id, report_id,
                exc_info=True,
            )

    # E-273-02 / TN-4: terminal ownership-invariant self-heal. Runs
    # UNCONDITIONALLY (regardless of `eligible`) on a FRESH connection after
    # conn1 (report row) and the optional conn2 (cascade). A DIFFERENT report's
    # deletion may have freed teams even when THIS report's own team is not
    # eligible -- opponent stubs are never in any single cascade's scope (RC#2),
    # so a per-report `eligible` gate would leave them orphaned forever. The pass
    # owns its reap-then-gate concurrency guard + single BEGIN IMMEDIATE
    # transaction (E-273-01), so a live generation's data is never deleted (it
    # defers). Best-effort: a sweep failure must not fail the report deletion.
    try:
        with closing(get_connection()) as conn:
            reclaim_orphan_reference_data(conn)
    except Exception:  # noqa: BLE001 -- reclamation is best-effort housekeeping
        logger.warning(
            "Orphan reclamation failed after report %d deletion; continuing",
            report_id,
            exc_info=True,
        )


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

    # Cross-path gate, BEFORE the semaphore acquire. Ordering is deliberate: a
    # refusal here cannot leak a slot because no slot is held yet. (Acquiring
    # first and releasing on refusal is also correct but relies on a release a
    # reviewer must verify; this removes the failure mode instead of guarding
    # it.) Pinned by
    # TestAdminGenerate_WhenAGenerationIsInFlightAnywhere::test_no_slot_is_consumed.
    if await run_in_threadpool(_a_generation_is_in_flight):
        return RedirectResponse(
            url="/admin/reports?error=" + quote_plus(
                "A report generation is already in progress -- it may have been "
                "started from the command line. Wait for it to finish, then try again."
            ),
            status_code=303,
        )

    # Admission check, LAST -- after _require_admin and after all three URL
    # validations. ⚠ This ordering is the whole correctness of the cap. Acquiring
    # any earlier means every rejected empty/invalid/UUID URL returns without
    # releasing and permanently burns a slot, so two bad pastes would wedge the
    # page. Pinned by
    # TestAdminGenerate_WhenTheUrlIsInvalid::test_no_slot_is_consumed.
    #
    # Reject, not queue: a queued job the operator was told "started" that
    # actually sits idle is a worse lie than an immediate refusal, and queuing
    # would pin an anyio thread for the duration.
    if not _generation_slots.acquire(blocking=False):
        return RedirectResponse(
            url="/admin/reports?error=" + quote_plus(
                f"{MAX_CONCURRENT_ADMIN_GENERATIONS} report generations are already "
                "running. Wait for one to finish, then try again."
            ),
            status_code=303,
        )

    background_tasks.add_task(_generate_report_releasing_slot, gc_url)

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
