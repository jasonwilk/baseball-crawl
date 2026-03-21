# synthetic-test-data
"""Tests for admin routes (src/api/routes/admin.py) -- E-100-04.

Tests cover:
- Admin routes require session matching ADMIN_EMAIL (or any session in dev mode)
- Non-admin authenticated users get 403 (ADMIN_EMAIL set to different email)
- Unauthenticated requests redirect to /auth/login
- User CRUD operations (create, read, update, delete)
- Duplicate email rejection
- Self-delete prevention
- Cascade delete removes auth artifacts

Uses an in-process seeded SQLite database via tmp_path; no Docker or network.

Run with:
    pytest tests/test_admin.py -v
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

_CSRF = "test-csrf-token"

_SEED_SQL = """
    INSERT OR IGNORE INTO programs (program_id, name, program_type)
        VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs');

    INSERT OR IGNORE INTO teams (name, program_id, membership_type, classification)
        VALUES ('LSB Varsity 2026', 'lsb-hs', 'member', 'varsity'),
               ('LSB JV 2026', 'lsb-hs', 'member', 'jv');
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed database with seed rows.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_admin.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    """Insert a user row and return the id.

    Args:
        db_path: Path to the database file.
        email: Email address for the user.

    Returns:
        The new integer user id.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, '')",
        (email,),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def _insert_session(db_path: Path, user_id: int) -> str:
    """Insert a valid session and return the raw token.

    Args:
        db_path: Path to the database file.
        user_id: User to associate the session with.

    Returns:
        Raw session token (64 hex chars).
    """
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
        """,
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _get_team_id(db_path: Path, name: str) -> int:
    """Return the INTEGER id of a team by name.

    Args:
        db_path: Path to the database file.
        name: Team name to look up.

    Returns:
        Integer team id.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT id FROM teams WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return row[0]


def _count_rows(db_path: Path, table: str, where_clause: str, params: tuple) -> int:
    """Return a row count from a table.

    Args:
        db_path: Path to the database file.
        table: Table name.
        where_clause: SQL WHERE clause (without the WHERE keyword).
        params: Parameters to bind.

    Returns:
        Integer row count.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {where_clause}", params
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def _set_user_role(db_path: Path, user_id: int, role: str) -> None:
    """Update a user's role column.

    Args:
        db_path: Path to the database file.
        user_id: User primary key.
        role: Role value to set ('admin' or 'user').
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()


def _get_user_role(db_path: Path, user_id: int) -> str:
    """Fetch a user's role from the database.

    Args:
        db_path: Path to the database file.
        user_id: User primary key.

    Returns:
        Role string ('admin' or 'user').
    """
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row else "user"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_db(tmp_path: Path) -> Path:
    """Full schema database with seeded teams."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# Admin auth: ADMIN_EMAIL controls access
# ---------------------------------------------------------------------------


class TestAdminAuthRequired:
    """Admin routes require a session matching ADMIN_EMAIL (or any session if unset)."""

    def test_admin_email_match_can_access_users_page(self, admin_db: Path) -> None:
        """Session email matching ADMIN_EMAIL gets 200 from GET /admin/users."""
        user_id = _insert_user(admin_db, "admin@example.com")
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert response.status_code == 200

    def test_db_role_admin_can_access_users_page(self, admin_db: Path) -> None:
        """When ADMIN_EMAIL is unset, a user with role='admin' in DB gets 200."""
        import os
        user_id = _insert_user(admin_db, "dbroleadmin@example.com")
        _set_user_role(admin_db, user_id, "admin")
        raw_token = _insert_session(admin_db, user_id)

        old = os.environ.pop("ADMIN_EMAIL", None)
        try:
            with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}, clear=False):
                with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                    response = client.get("/admin/users")
            assert response.status_code == 200
        finally:
            if old is not None:
                os.environ["ADMIN_EMAIL"] = old

    def test_no_admin_email_and_no_db_role_gets_403(self, admin_db: Path) -> None:
        """When ADMIN_EMAIL is unset and user role is 'user', access is denied (403)."""
        import os
        user_id = _insert_user(admin_db, "norole@example.com")
        raw_token = _insert_session(admin_db, user_id)

        old = os.environ.pop("ADMIN_EMAIL", None)
        try:
            with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}, clear=False):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
                ) as client:
                    response = client.get("/admin/users")
            assert response.status_code == 403
        finally:
            if old is not None:
                os.environ["ADMIN_EMAIL"] = old

    def test_admin_page_contains_user_table(self, admin_db: Path) -> None:
        """Admin page HTML includes a users table header."""
        user_id = _insert_user(admin_db, "tableadmin@example.com")
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "tableadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert "Manage Users" in response.text


# ---------------------------------------------------------------------------
# Non-admin gets 403
# ---------------------------------------------------------------------------


class TestNonAdminForbidden:
    """Authenticated users get 403 when ADMIN_EMAIL is set to a different email."""

    def test_non_admin_gets_403(self, admin_db: Path) -> None:
        """ADMIN_EMAIL set to different email results in 403 status code."""
        user_id = _insert_user(admin_db, "coach@example.com")
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "other-admin@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get("/admin/users")
        assert response.status_code == 403

    def test_non_admin_gets_html_not_json(self, admin_db: Path) -> None:
        """Non-admin 403 response is HTML, not a JSON error body."""
        user_id = _insert_user(admin_db, "htmlcheck@example.com")
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "other@example.com",
            },
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert "text/html" in response.headers.get("content-type", "")
        assert "permission" in response.text.lower()

    def test_non_admin_forbidden_page_has_dashboard_link(self, admin_db: Path) -> None:
        """Forbidden page includes a link back to the dashboard."""
        user_id = _insert_user(admin_db, "dashlink@example.com")
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "other@example.com",
            },
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert "/dashboard" in response.text


# ---------------------------------------------------------------------------
# Unauthenticated requests redirect to /auth/login
# ---------------------------------------------------------------------------


class TestUnauthenticatedRedirect:
    """Unauthenticated requests to /admin/* redirect to /auth/login."""

    def test_no_session_redirects_to_login(self, admin_db: Path) -> None:
        """GET /admin/users without session cookie -> redirect to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/admin/users")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_post_no_session_redirects_to_login(self, admin_db: Path) -> None:
        """POST /admin/users without session cookie -> redirect to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    "/admin/users",
                    data={"email": "x@x.com", "csrf_token": _CSRF},
                )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# User CRUD operations
# ---------------------------------------------------------------------------


class TestUserCRUD:
    """User CRUD operations work correctly with the new schema."""

    def test_list_users_returns_existing_user(self, admin_db: Path) -> None:
        """GET /admin/users lists an existing user by email."""
        admin_id = _insert_user(admin_db, "listadmin@example.com")
        _insert_user(admin_db, "coach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "listadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert "coach@example.com" in response.text

    def test_create_user_inserts_db_row(self, admin_db: Path) -> None:
        """POST /admin/users creates a user row in the database."""
        admin_id = _insert_user(admin_db, "createadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "createadmin@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    "/admin/users",
                    data={"email": "newcoach@example.com", "csrf_token": _CSRF},
                )
        assert response.status_code == 303
        assert _count_rows(admin_db, "users", "email = ?", ("newcoach@example.com",)) == 1

    def test_create_user_with_team_assignment(self, admin_db: Path) -> None:
        """POST /admin/users with team_ids (INTEGER) creates user_team_access rows."""
        admin_id = _insert_user(admin_db, "teamadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)
        team_id = _get_team_id(admin_db, "LSB Varsity 2026")

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "teamadmin@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(
                    "/admin/users",
                    data={"email": "withteam@example.com", "team_ids": str(team_id), "csrf_token": _CSRF},
                )

        conn = sqlite3.connect(str(admin_db))
        cursor = conn.execute(
            """
            SELECT uta.team_id FROM user_team_access uta
            JOIN users u ON u.id = uta.user_id
            WHERE u.email = ?
            """,
            ("withteam@example.com",),
        )
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == team_id

    def test_create_user_success_redirects_with_flash(self, admin_db: Path) -> None:
        """POST /admin/users on success redirects with ?msg= flash message."""
        admin_id = _insert_user(admin_db, "flashadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "flashadmin@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    "/admin/users",
                    data={"email": "flash@example.com", "csrf_token": _CSRF},
                )
        assert response.status_code == 303
        assert "msg=" in response.headers["location"]

    def test_edit_user_form_shows_email(self, admin_db: Path) -> None:
        """GET /admin/users/{id}/edit renders the user's email."""
        admin_id = _insert_user(admin_db, "editadmin@example.com")
        coach_id = _insert_user(admin_db, "editcoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "editadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get(f"/admin/users/{coach_id}/edit")
        assert response.status_code == 200
        assert "editcoach@example.com" in response.text

    def test_update_user_team_assignment(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/edit updates the user's team assignments."""
        admin_id = _insert_user(admin_db, "updadmin@example.com")
        coach_id = _insert_user(admin_db, "updcoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)
        team_id = _get_team_id(admin_db, "LSB Varsity 2026")

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "updadmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/users/{coach_id}/edit",
                    data={"team_ids": str(team_id), "csrf_token": _CSRF},
                )
        assert response.status_code == 303
        assert _count_rows(
            admin_db, "user_team_access", "user_id = ? AND team_id = ?",
            (coach_id, team_id)
        ) == 1

    def test_update_user_success_redirects_with_flash(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/edit redirects with ?msg= flash message."""
        admin_id = _insert_user(admin_db, "updflash@example.com")
        coach_id = _insert_user(admin_db, "updflashcoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "updflash@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/users/{coach_id}/edit",
                    data={"csrf_token": _CSRF},
                )
        assert response.status_code == 303
        assert "msg=" in response.headers["location"]

    def test_delete_user_removes_row(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/delete removes the user row."""
        admin_id = _insert_user(admin_db, "deladmin@example.com")
        coach_id = _insert_user(admin_db, "delcoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "deladmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(f"/admin/users/{coach_id}/delete", data={"csrf_token": _CSRF})
        assert response.status_code == 303
        assert _count_rows(admin_db, "users", "id = ?", (coach_id,)) == 0


# ---------------------------------------------------------------------------
# Duplicate email rejection
# ---------------------------------------------------------------------------


class TestDuplicateEmail:
    """Duplicate email shows error message and does not create a duplicate."""

    def test_duplicate_email_returns_error_message(self, admin_db: Path) -> None:
        """POST /admin/users with duplicate email shows error message."""
        admin_id = _insert_user(admin_db, "dupadmin@example.com")
        _insert_user(admin_db, "existing@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "dupadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.post(
                    "/admin/users",
                    data={"email": "existing@example.com", "csrf_token": _CSRF},
                )
        assert response.status_code == 200
        assert "already exists" in response.text.lower()

    def test_duplicate_email_does_not_create_second_row(self, admin_db: Path) -> None:
        """POST /admin/users with duplicate email does not insert a second user row."""
        admin_id = _insert_user(admin_db, "dup2admin@example.com")
        _insert_user(admin_db, "dup2@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "dup2admin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                client.post(
                    "/admin/users",
                    data={"email": "dup2@example.com", "csrf_token": _CSRF},
                )
        assert _count_rows(admin_db, "users", "email = ?", ("dup2@example.com",)) == 1

    def test_email_normalized_to_lowercase(self, admin_db: Path) -> None:
        """POST /admin/users normalizes email to lowercase before storage."""
        admin_id = _insert_user(admin_db, "normadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "normadmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(
                    "/admin/users",
                    data={"email": "Coach@Example.COM", "csrf_token": _CSRF},
                )
        assert (
            _count_rows(admin_db, "users", "email = ?", ("coach@example.com",)) == 1
        )
        assert (
            _count_rows(admin_db, "users", "email = ?", ("Coach@Example.COM",)) == 0
        )


# ---------------------------------------------------------------------------
# Self-delete prevention
# ---------------------------------------------------------------------------


class TestSelfDeletePrevention:
    """Admins cannot delete their own account."""

    def test_self_delete_is_rejected(self, admin_db: Path) -> None:
        """POST /admin/users/{own_id}/delete returns redirect with error."""
        admin_id = _insert_user(admin_db, "selfadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "selfadmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(f"/admin/users/{admin_id}/delete", data={"csrf_token": _CSRF})
        assert response.status_code == 303
        assert "error=" in response.headers["location"]

    def test_self_delete_does_not_remove_row(self, admin_db: Path) -> None:
        """POST /admin/users/{own_id}/delete leaves the admin row intact."""
        admin_id = _insert_user(admin_db, "selfkeep@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "selfkeep@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(f"/admin/users/{admin_id}/delete", data={"csrf_token": _CSRF})
        assert _count_rows(admin_db, "users", "id = ?", (admin_id,)) == 1


# ---------------------------------------------------------------------------
# Cascade delete removes auth artifacts
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """Deleting a user removes all their auth artifacts."""

    def _seed_full_user(self, db_path: Path, email: str) -> int:
        """Insert a user with sessions and tokens.

        Args:
            db_path: Path to the database.
            email: Email for the new user.

        Returns:
            The new user id.
        """
        conn = sqlite3.connect(str(db_path))

        cursor = conn.execute(
            "INSERT INTO users (email, hashed_password) VALUES (?, '')",
            (email,),
        )
        user_id = cursor.lastrowid

        # Sessions
        for _ in range(2):
            raw_token = secrets.token_hex(32)
            conn.execute(
                """
                INSERT INTO sessions (session_id, user_id, expires_at)
                VALUES (?, ?, datetime('now', '+7 days'))
                """,
                (hash_token(raw_token), user_id),
            )

        # Magic link token
        raw_magic = secrets.token_urlsafe(32)
        conn.execute(
            """
            INSERT INTO magic_link_tokens (token, user_id, expires_at)
            VALUES (?, ?, datetime('now', '+15 minutes'))
            """,
            (raw_magic, user_id),
        )

        # Passkey credential
        conn.execute(
            """
            INSERT INTO passkey_credentials (credential_id, user_id, public_key)
            VALUES (?, ?, ?)
            """,
            (secrets.token_hex(16), user_id, "fake-public-key"),
        )

        conn.commit()
        conn.close()
        return user_id

    def test_delete_user_removes_sessions(self, admin_db: Path) -> None:
        """Deleting a user removes their sessions from the database."""
        admin_id = _insert_user(admin_db, "cascadeadmin@example.com")
        full_user_id = self._seed_full_user(admin_db, "fulluser@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        assert _count_rows(admin_db, "sessions", "user_id = ?", (full_user_id,)) == 2

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "cascadeadmin@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(f"/admin/users/{full_user_id}/delete", data={"csrf_token": _CSRF})

        assert _count_rows(admin_db, "sessions", "user_id = ?", (full_user_id,)) == 0

    def test_delete_user_removes_magic_link_tokens(self, admin_db: Path) -> None:
        """Deleting a user removes their magic link tokens."""
        admin_id = _insert_user(admin_db, "cascadeadmin2@example.com")
        full_user_id = self._seed_full_user(admin_db, "fulluser2@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        assert (
            _count_rows(
                admin_db, "magic_link_tokens", "user_id = ?", (full_user_id,)
            )
            == 1
        )

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "cascadeadmin2@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(f"/admin/users/{full_user_id}/delete", data={"csrf_token": _CSRF})

        assert (
            _count_rows(
                admin_db, "magic_link_tokens", "user_id = ?", (full_user_id,)
            )
            == 0
        )

    def test_delete_user_removes_passkey_credentials(self, admin_db: Path) -> None:
        """Deleting a user removes their passkey credentials."""
        admin_id = _insert_user(admin_db, "cascadeadmin3@example.com")
        full_user_id = self._seed_full_user(admin_db, "fulluser3@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        assert (
            _count_rows(
                admin_db, "passkey_credentials", "user_id = ?", (full_user_id,)
            )
            == 1
        )

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "cascadeadmin3@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(f"/admin/users/{full_user_id}/delete", data={"csrf_token": _CSRF})

        assert (
            _count_rows(
                admin_db, "passkey_credentials", "user_id = ?", (full_user_id,)
            )
            == 0
        )

    def test_delete_user_removes_coaching_assignments(self, admin_db: Path) -> None:
        """Deleting a user with coaching assignments raises no IntegrityError."""
        admin_id = _insert_user(admin_db, "cascadeadmin4@example.com")
        user_id = _insert_user(admin_db, "coachuser@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        # Insert a coaching assignment for the user being deleted.
        conn = sqlite3.connect(str(admin_db))
        team_id = _get_team_id(admin_db, "LSB Varsity 2026")
        conn.execute(
            "INSERT INTO coaching_assignments (user_id, team_id, role) VALUES (?, ?, 'assistant')",
            (user_id, team_id),
        )
        conn.commit()
        conn.close()

        assert _count_rows(admin_db, "coaching_assignments", "user_id = ?", (user_id,)) == 1

        with patch.dict(
            "os.environ",
            {
                "DATABASE_PATH": str(admin_db),
                "ADMIN_EMAIL": "cascadeadmin4@example.com",
            },
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(f"/admin/users/{user_id}/delete", data={"csrf_token": _CSRF})

        # No IntegrityError -- deletion succeeded and redirected.
        assert response.status_code == 303
        assert _count_rows(admin_db, "coaching_assignments", "user_id = ?", (user_id,)) == 0


# ---------------------------------------------------------------------------
# Role enforcement -- AC-1, AC-2, AC-3, AC-4, AC-5, AC-6
# ---------------------------------------------------------------------------


class TestRoleEnforcement:
    """Role field in user forms, display, and self-demotion guard."""

    def test_users_list_shows_role_column(self, admin_db: Path) -> None:
        """GET /admin/users includes a Role column header."""
        admin_id = _insert_user(admin_db, "rolelistadmin@example.com")
        _set_user_role(admin_db, admin_id, "admin")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "rolelistadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert response.status_code == 200
        assert "Role" in response.text

    def test_users_list_shows_admin_badge(self, admin_db: Path) -> None:
        """GET /admin/users shows 'Admin' badge for an admin-role user."""
        admin_id = _insert_user(admin_db, "badgeadmin@example.com")
        _set_user_role(admin_db, admin_id, "admin")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "badgeadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert "Admin" in response.text

    def test_add_user_form_includes_role_field(self, admin_db: Path) -> None:
        """GET /admin/users renders a role radio input in the Add User form."""
        admin_id = _insert_user(admin_db, "roleformadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "roleformadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/users")
        assert 'name="role"' in response.text

    def test_create_user_stores_role_admin(self, admin_db: Path) -> None:
        """POST /admin/users with role=admin creates a user with admin role in DB."""
        admin_id = _insert_user(admin_db, "rolecreatadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "rolecreatadmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(
                    "/admin/users",
                    data={"email": "newadmin@example.com", "role": "admin", "csrf_token": _CSRF},
                )

        conn = sqlite3.connect(str(admin_db))
        row = conn.execute("SELECT role FROM users WHERE email = ?", ("newadmin@example.com",)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "admin"

    def test_create_user_defaults_to_user_role(self, admin_db: Path) -> None:
        """POST /admin/users without role field creates a user with 'user' role."""
        admin_id = _insert_user(admin_db, "roledefaultadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "roledefaultadmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                client.post(
                    "/admin/users",
                    data={"email": "defaultrole@example.com", "csrf_token": _CSRF},
                )

        conn = sqlite3.connect(str(admin_db))
        row = conn.execute("SELECT role FROM users WHERE email = ?", ("defaultrole@example.com",)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "user"

    def test_create_user_invalid_role_shows_error(self, admin_db: Path) -> None:
        """POST /admin/users with invalid role value returns error."""
        admin_id = _insert_user(admin_db, "invalidroleadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "invalidroleadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.post(
                    "/admin/users",
                    data={"email": "badrole@example.com", "role": "superuser", "csrf_token": _CSRF},
                )
        assert response.status_code == 200
        assert "invalid role" in response.text.lower()

    def test_edit_user_form_includes_role_field(self, admin_db: Path) -> None:
        """GET /admin/users/{id}/edit renders a role radio input."""
        admin_id = _insert_user(admin_db, "editroleadmin@example.com")
        coach_id = _insert_user(admin_db, "editrolecoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "editroleadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get(f"/admin/users/{coach_id}/edit")
        assert response.status_code == 200
        assert 'name="role"' in response.text

    def test_update_user_role_changes_in_db(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/edit with role=admin updates role in DB."""
        admin_id = _insert_user(admin_db, "updateroleadmin@example.com")
        coach_id = _insert_user(admin_db, "updaterolecoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        assert _get_user_role(admin_db, coach_id) == "user"

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "updateroleadmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/users/{coach_id}/edit",
                    data={"role": "admin", "csrf_token": _CSRF},
                )
        assert response.status_code == 303
        assert _get_user_role(admin_db, coach_id) == "admin"

    def test_update_user_invalid_role_shows_error(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/edit with invalid role returns error and does not update DB."""
        admin_id = _insert_user(admin_db, "editinvalidroleadmin@example.com")
        coach_id = _insert_user(admin_db, "editinvalidrolecoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "editinvalidroleadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.post(
                    f"/admin/users/{coach_id}/edit",
                    data={"role": "superuser", "csrf_token": _CSRF},
                )
        assert response.status_code == 200
        assert "invalid role" in response.text.lower()
        assert _get_user_role(admin_db, coach_id) == "user"

    def test_self_demotion_is_rejected(self, admin_db: Path) -> None:
        """POST /admin/users/{own_id}/edit with role=user returns error for self-demotion."""
        admin_id = _insert_user(admin_db, "selfdemoteadmin@example.com")
        _set_user_role(admin_db, admin_id, "admin")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "selfdemoteadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.post(
                    f"/admin/users/{admin_id}/edit",
                    data={"role": "user", "csrf_token": _CSRF},
                )
        assert response.status_code == 200
        assert "demot" in response.text.lower()

    def test_self_demotion_does_not_change_role(self, admin_db: Path) -> None:
        """POST /admin/users/{own_id}/edit with role=user leaves admin role intact."""
        admin_id = _insert_user(admin_db, "selfkeeprolead@example.com")
        _set_user_role(admin_db, admin_id, "admin")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "selfkeeprolead@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                client.post(
                    f"/admin/users/{admin_id}/edit",
                    data={"role": "user", "csrf_token": _CSRF},
                )
        assert _get_user_role(admin_db, admin_id) == "admin"


# ---------------------------------------------------------------------------
# AC-3/AC-4: membership_type validation and already-resolved link guard
# ---------------------------------------------------------------------------


def _insert_opponent_link(
    db_path: Path,
    our_team_id: int,
    opponent_name: str,
    public_id: str | None = None,
) -> int:
    """Insert an opponent_links row and return its id."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id)"
        " VALUES (?, ?, ?, ?)",
        (our_team_id, f"root-{opponent_name}", opponent_name, public_id),
    )
    conn.commit()
    link_id = cursor.lastrowid
    conn.close()
    return link_id


class TestMembershipTypeValidation:
    """Invalid membership_type values are rejected with 400."""

    def test_confirm_team_submit_rejects_invalid_membership_type(
        self, admin_db: Path
    ) -> None:
        """POST /admin/teams/confirm with an invalid membership_type returns 400."""
        admin_id = _insert_user(admin_db, "mtadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "mtadmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    "/admin/teams/confirm",
                    data={
                        "public_id": "some-team-slug",
                        "team_name": "Some Team",
                        "membership_type": "superadmin",
                        "csrf_token": _CSRF,
                    },
                )
        assert response.status_code == 400


class TestConfirmTeamInsertIntegrityError:
    """Concurrent insert raising IntegrityError returns a redirect, not a 500."""

    def test_confirm_team_submit_integrity_error_returns_redirect(
        self, admin_db: Path
    ) -> None:
        """POST /admin/teams/confirm redirects with error when _insert_team_new raises IntegrityError."""
        admin_id = _insert_user(admin_db, "ierr@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "ierr@example.com"},
        ):
            with patch(
                "src.api.routes.admin._insert_team_new",
                side_effect=sqlite3.IntegrityError("UNIQUE constraint failed: teams.public_id"),
            ):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "some-team-slug",
                            "team_name": "Some Team",
                            "membership_type": "tracked",
                            "csrf_token": _CSRF,
                        },
                    )
        assert response.status_code != 500
        assert response.status_code == 303


class TestAlreadyResolvedLinkGuard:
    """GET connect/confirm returns 400 when the link already has a public_id."""

    def test_connect_opponent_confirm_get_returns_400_for_resolved_link(
        self, admin_db: Path
    ) -> None:
        """GET /admin/opponents/{link_id}/connect/confirm returns 400 when already resolved."""
        admin_id = _insert_user(admin_db, "rladmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        our_team_id = _get_team_id(admin_db, "LSB Varsity 2026")
        link_id = _insert_opponent_link(
            admin_db, our_team_id, "Resolved Opponent", public_id="already-linked-slug"
        )

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "rladmin@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get(
                    f"/admin/opponents/{link_id}/connect/confirm"
                )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# AC-1: opponent_count excludes hidden links
# ---------------------------------------------------------------------------


class TestOpponentCountExcludesHidden:
    """Team list opponent_count only counts non-hidden opponent_links rows."""

    def test_opponent_count_excludes_hidden_links(self, admin_db: Path) -> None:
        """_get_all_teams_flat returns opponent_count that excludes hidden rows."""
        from src.api.routes.admin import _get_all_teams_flat

        our_team_id = _get_team_id(admin_db, "LSB Varsity 2026")

        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, is_hidden)"
            " VALUES (?, 'root-visible', 'Visible Opponent', 0)",
            (our_team_id,),
        )
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, is_hidden)"
            " VALUES (?, 'root-hidden', 'Hidden Opponent', 1)",
            (our_team_id,),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            teams = _get_all_teams_flat()

        varsity = next(t for t in teams if t["name"] == "LSB Varsity 2026")
        assert varsity["opponent_count"] == 1


# ---------------------------------------------------------------------------
# XSS escaping regression: query parameters are HTML-escaped in responses
# ---------------------------------------------------------------------------


class TestXSSEscaping:
    """User-controlled query parameters are HTML-escaped in admin templates."""

    def test_msg_param_is_escaped_in_team_list(self, admin_db: Path) -> None:
        """GET /admin/teams?msg=<script>alert(1)</script> escapes the payload."""
        admin_id = _insert_user(admin_db, "xssadmin@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        payload = "<script>alert(1)</script>"

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(admin_db), "ADMIN_EMAIL": "xssadmin@example.com"},
        ):
            with TestClient(app, cookies={"session": raw_token, "csrf_token": _CSRF}) as client:
                response = client.get(f"/admin/teams?msg={payload}")

        assert response.status_code == 200
        assert payload not in response.text
        assert "&lt;script&gt;" in response.text
