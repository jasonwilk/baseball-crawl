# synthetic-test-data
"""Tests for admin routes (src/api/routes/admin.py) -- E-023-05 AC-12.

Tests cover:
- Admin routes require active session with is_admin=1 (AC-12a)
- Non-admin authenticated users get 403 (AC-12b)
- Unauthenticated requests redirect to /auth/login (AC-12c)
- User CRUD operations (create, read, update, delete) (AC-12d)
- Duplicate email rejection (AC-12e)
- Self-delete prevention (AC-12f)
- Cascade delete removes auth artifacts (AC-12g)

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

from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Schema SQL (base + auth tables)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    INSERT OR IGNORE INTO _migrations (filename) VALUES ('001_initial_schema.sql');

    CREATE TABLE IF NOT EXISTS players (
        player_id  TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name  TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS teams (
        team_id    TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        level      TEXT,
        is_owned   INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS team_rosters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id       TEXT NOT NULL,
        player_id     TEXT NOT NULL,
        season        TEXT NOT NULL,
        jersey_number TEXT,
        position      TEXT,
        UNIQUE(team_id, player_id, season)
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id      TEXT PRIMARY KEY,
        season       TEXT NOT NULL,
        game_date    TEXT NOT NULL,
        home_team_id TEXT NOT NULL,
        away_team_id TEXT NOT NULL,
        home_score   INTEGER,
        away_score   INTEGER,
        status       TEXT NOT NULL DEFAULT 'completed'
    );

    CREATE TABLE IF NOT EXISTS player_game_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_game_pitching (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ip_outs   INTEGER,
        h         INTEGER,
        er        INTEGER,
        bb        INTEGER,
        so        INTEGER,
        hr        INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_batting (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        season    TEXT NOT NULL,
        games     INTEGER,
        ab        INTEGER,
        h         INTEGER,
        doubles   INTEGER,
        triples   INTEGER,
        hr        INTEGER,
        rbi       INTEGER,
        bb        INTEGER,
        so        INTEGER,
        sb        INTEGER,
        home_ab   INTEGER,
        home_h    INTEGER,
        away_ab   INTEGER,
        away_h    INTEGER,
        vs_lhp_ab INTEGER,
        vs_lhp_h  INTEGER,
        vs_rhp_ab INTEGER,
        vs_rhp_h  INTEGER,
        UNIQUE(player_id, team_id, season)
    );

    -- Auth tables (003_auth.sql)
    CREATE TABLE IF NOT EXISTS users (
        user_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        email        TEXT    NOT NULL UNIQUE,
        display_name TEXT    NOT NULL,
        is_admin     INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_team_access (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL REFERENCES users(user_id),
        team_id  TEXT    NOT NULL REFERENCES teams(team_id),
        UNIQUE(user_id, team_id)
    );

    CREATE TABLE IF NOT EXISTS magic_link_tokens (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT    NOT NULL UNIQUE,
        user_id    INTEGER NOT NULL REFERENCES users(user_id),
        expires_at TEXT    NOT NULL,
        used_at    TEXT,
        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS passkey_credentials (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER NOT NULL REFERENCES users(user_id),
        credential_id BLOB    NOT NULL UNIQUE,
        public_key    BLOB    NOT NULL,
        sign_count    INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        session_token_hash  TEXT    NOT NULL UNIQUE,
        user_id             INTEGER NOT NULL REFERENCES users(user_id),
        expires_at          TEXT    NOT NULL,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
    );
"""

_SEED_SQL = """
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned) VALUES
        ('lsb-varsity-2026', 'LSB Varsity 2026', 'varsity', 1),
        ('lsb-jv-2026', 'LSB JV 2026', 'jv', 1);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed database with team rows.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_admin.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str, is_admin: int = 0) -> int:
    """Insert a user row and return the user_id.

    Args:
        db_path: Path to the database file.
        email: Email address for the user.
        is_admin: 1 for admin, 0 for non-admin.

    Returns:
        The new user_id.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email, display_name, is_admin) VALUES (?, ?, ?)",
        (email, "Test User", is_admin),
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
        INSERT INTO sessions (session_token_hash, user_id, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
        """,
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_db(tmp_path: Path) -> Path:
    """Full schema database with owned teams."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-12a: Admin routes require is_admin=1
# ---------------------------------------------------------------------------


class TestAdminAuthRequired:
    """Admin routes require an active session with is_admin=1 (AC-12a)."""

    def test_admin_session_can_access_users_page(self, admin_db: Path) -> None:
        """Admin with valid session gets 200 from GET /admin/users."""
        admin_id = _insert_user(admin_db, "admin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/admin/users")
        assert response.status_code == 200

    def test_admin_page_contains_user_table(self, admin_db: Path) -> None:
        """Admin page HTML includes a users table header."""
        admin_id = _insert_user(admin_db, "tableadmin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/admin/users")
        assert "Manage Users" in response.text


# ---------------------------------------------------------------------------
# AC-12b: Non-admin gets 403 HTML page (not JSON)
# ---------------------------------------------------------------------------


class TestNonAdminForbidden:
    """Authenticated non-admin users receive a 403 HTML page (AC-12b)."""

    def test_non_admin_gets_403(self, admin_db: Path) -> None:
        """Non-admin session results in 403 status code."""
        user_id = _insert_user(admin_db, "coach@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                response = client.get("/admin/users")
        assert response.status_code == 403

    def test_non_admin_gets_html_not_json(self, admin_db: Path) -> None:
        """Non-admin 403 response is HTML, not a JSON error body."""
        user_id = _insert_user(admin_db, "htmlcheck@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/admin/users")
        assert "text/html" in response.headers.get("content-type", "")
        assert "permission" in response.text.lower()

    def test_non_admin_forbidden_page_has_dashboard_link(self, admin_db: Path) -> None:
        """Forbidden page includes a link back to the dashboard."""
        user_id = _insert_user(admin_db, "dashlink@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/admin/users")
        assert "/dashboard" in response.text


# ---------------------------------------------------------------------------
# AC-12c: Unauthenticated requests redirect to /auth/login
# ---------------------------------------------------------------------------


class TestUnauthenticatedRedirect:
    """Unauthenticated requests to /admin/* redirect to /auth/login (AC-12c)."""

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
            with TestClient(app, follow_redirects=False) as client:
                response = client.post(
                    "/admin/users",
                    data={"email": "x@x.com", "display_name": "X"},
                )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# AC-12d: CRUD operations
# ---------------------------------------------------------------------------


class TestUserCRUD:
    """User CRUD operations work correctly (AC-12d)."""

    def test_list_users_returns_existing_user(self, admin_db: Path) -> None:
        """GET /admin/users lists an existing user by name."""
        admin_id = _insert_user(admin_db, "listadmin@example.com", is_admin=1)
        _insert_user(admin_db, "coach@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/admin/users")
        assert "coach@example.com" in response.text

    def test_create_user_inserts_db_row(self, admin_db: Path) -> None:
        """POST /admin/users creates a user row in the database."""
        admin_id = _insert_user(admin_db, "createadmin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                response = client.post(
                    "/admin/users",
                    data={
                        "email": "newcoach@example.com",
                        "display_name": "New Coach",
                    },
                )
        assert response.status_code == 303
        assert _count_rows(admin_db, "users", "email = ?", ("newcoach@example.com",)) == 1

    def test_create_user_with_team_assignment(self, admin_db: Path) -> None:
        """POST /admin/users with team_ids creates user_team_access rows."""
        admin_id = _insert_user(admin_db, "teamadmin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                client.post(
                    "/admin/users",
                    data={
                        "email": "withteam@example.com",
                        "display_name": "With Team",
                        "team_ids": "lsb-varsity-2026",
                    },
                )

        conn = sqlite3.connect(str(admin_db))
        cursor = conn.execute(
            """
            SELECT uta.team_id FROM user_team_access uta
            JOIN users u ON u.user_id = uta.user_id
            WHERE u.email = ?
            """,
            ("withteam@example.com",),
        )
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "lsb-varsity-2026"

    def test_create_user_success_redirects_with_flash(self, admin_db: Path) -> None:
        """POST /admin/users on success redirects with ?msg= flash message."""
        admin_id = _insert_user(admin_db, "flashadmin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                response = client.post(
                    "/admin/users",
                    data={"email": "flash@example.com", "display_name": "Flash"},
                )
        assert response.status_code == 303
        assert "msg=" in response.headers["location"]

    def test_edit_user_form_shows_current_values(self, admin_db: Path) -> None:
        """GET /admin/users/{id}/edit renders current user details."""
        admin_id = _insert_user(admin_db, "editadmin@example.com", is_admin=1)
        coach_id = _insert_user(admin_db, "editcoach@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get(f"/admin/users/{coach_id}/edit")
        assert response.status_code == 200
        assert "editcoach@example.com" in response.text

    def test_update_user_changes_display_name(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/edit updates the user's display name."""
        admin_id = _insert_user(admin_db, "updadmin@example.com", is_admin=1)
        coach_id = _insert_user(admin_db, "updcoach@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                response = client.post(
                    f"/admin/users/{coach_id}/edit",
                    data={"display_name": "Updated Coach Name"},
                )
        assert response.status_code == 303

        conn = sqlite3.connect(str(admin_db))
        cursor = conn.execute(
            "SELECT display_name FROM users WHERE user_id = ?", (coach_id,)
        )
        name = cursor.fetchone()[0]
        conn.close()
        assert name == "Updated Coach Name"

    def test_update_user_success_redirects_with_flash(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/edit redirects with ?msg= flash message."""
        admin_id = _insert_user(admin_db, "updflash@example.com", is_admin=1)
        coach_id = _insert_user(admin_db, "updflashcoach@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                response = client.post(
                    f"/admin/users/{coach_id}/edit",
                    data={"display_name": "Name"},
                )
        assert response.status_code == 303
        assert "msg=" in response.headers["location"]

    def test_delete_user_removes_row(self, admin_db: Path) -> None:
        """POST /admin/users/{id}/delete removes the user row."""
        admin_id = _insert_user(admin_db, "deladmin@example.com", is_admin=1)
        coach_id = _insert_user(admin_db, "delcoach@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                response = client.post(f"/admin/users/{coach_id}/delete")
        assert response.status_code == 303
        assert _count_rows(admin_db, "users", "user_id = ?", (coach_id,)) == 0


# ---------------------------------------------------------------------------
# AC-12e: Duplicate email rejection
# ---------------------------------------------------------------------------


class TestDuplicateEmail:
    """Duplicate email shows error message and does not create a duplicate (AC-12e)."""

    def test_duplicate_email_returns_error_message(self, admin_db: Path) -> None:
        """POST /admin/users with duplicate email shows error message."""
        admin_id = _insert_user(admin_db, "dupadmin@example.com", is_admin=1)
        _insert_user(admin_db, "existing@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.post(
                    "/admin/users",
                    data={
                        "email": "existing@example.com",
                        "display_name": "Duplicate",
                    },
                )
        assert response.status_code == 200
        assert "already exists" in response.text.lower()

    def test_duplicate_email_does_not_create_second_row(self, admin_db: Path) -> None:
        """POST /admin/users with duplicate email does not insert a second user row."""
        admin_id = _insert_user(admin_db, "dup2admin@example.com", is_admin=1)
        _insert_user(admin_db, "dup2@example.com", is_admin=0)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                client.post(
                    "/admin/users",
                    data={"email": "dup2@example.com", "display_name": "Dup"},
                )
        assert _count_rows(admin_db, "users", "email = ?", ("dup2@example.com",)) == 1

    def test_email_normalized_to_lowercase(self, admin_db: Path) -> None:
        """POST /admin/users normalizes email to lowercase before storage."""
        admin_id = _insert_user(admin_db, "normadmin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                client.post(
                    "/admin/users",
                    data={
                        "email": "Coach@Example.COM",
                        "display_name": "Mixed Case",
                    },
                )
        assert (
            _count_rows(admin_db, "users", "email = ?", ("coach@example.com",)) == 1
        )
        assert (
            _count_rows(admin_db, "users", "email = ?", ("Coach@Example.COM",)) == 0
        )


# ---------------------------------------------------------------------------
# AC-12f: Self-delete prevention
# ---------------------------------------------------------------------------


class TestSelfDeletePrevention:
    """Admins cannot delete their own account (AC-12f)."""

    def test_self_delete_is_rejected(self, admin_db: Path) -> None:
        """POST /admin/users/{own_id}/delete returns redirect with error."""
        admin_id = _insert_user(admin_db, "selfadmin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                response = client.post(f"/admin/users/{admin_id}/delete")
        assert response.status_code == 303
        assert "error=" in response.headers["location"]

    def test_self_delete_does_not_remove_row(self, admin_db: Path) -> None:
        """POST /admin/users/{own_id}/delete leaves the admin row intact."""
        admin_id = _insert_user(admin_db, "selfkeep@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                client.post(f"/admin/users/{admin_id}/delete")
        assert _count_rows(admin_db, "users", "user_id = ?", (admin_id,)) == 1


# ---------------------------------------------------------------------------
# AC-12g: Cascade delete removes auth artifacts
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """Deleting a user removes all their auth artifacts (AC-12g)."""

    def _seed_full_user(self, db_path: Path, email: str) -> int:
        """Insert a user with sessions, magic_link_tokens, and passkey_credentials.

        Args:
            db_path: Path to the database.
            email: Email for the new user.

        Returns:
            The new user_id.
        """
        conn = sqlite3.connect(str(db_path))

        cursor = conn.execute(
            "INSERT INTO users (email, display_name, is_admin) VALUES (?, ?, 0)",
            (email, "Full User"),
        )
        user_id = cursor.lastrowid

        # Sessions
        for _ in range(2):
            raw_token = secrets.token_hex(32)
            conn.execute(
                """
                INSERT INTO sessions (session_token_hash, user_id, expires_at)
                VALUES (?, ?, datetime('now', '+7 days'))
                """,
                (hash_token(raw_token), user_id),
            )

        # Magic link token
        import secrets as _secrets
        raw_magic = _secrets.token_urlsafe(32)
        conn.execute(
            """
            INSERT INTO magic_link_tokens (token_hash, user_id, expires_at)
            VALUES (?, ?, datetime('now', '+15 minutes'))
            """,
            (hash_token(raw_magic), user_id),
        )

        # Passkey credential (dummy blob data)
        conn.execute(
            """
            INSERT INTO passkey_credentials (user_id, credential_id, public_key)
            VALUES (?, ?, ?)
            """,
            (user_id, b"dummy-cred-id", b"dummy-public-key"),
        )

        # Team assignment
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, "lsb-varsity-2026"),
        )

        conn.commit()
        conn.close()
        return user_id

    def test_cascade_delete_removes_sessions(self, admin_db: Path) -> None:
        """Deleting a user removes their session rows."""
        admin_id = _insert_user(admin_db, "cascadeadmin@example.com", is_admin=1)
        coach_id = self._seed_full_user(admin_db, "cascadecoach@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                client.post(f"/admin/users/{coach_id}/delete")

        assert _count_rows(admin_db, "sessions", "user_id = ?", (coach_id,)) == 0

    def test_cascade_delete_removes_magic_link_tokens(self, admin_db: Path) -> None:
        """Deleting a user removes their magic_link_token rows."""
        admin_id = _insert_user(admin_db, "cascadeadmin2@example.com", is_admin=1)
        coach_id = self._seed_full_user(admin_db, "cascadecoach2@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                client.post(f"/admin/users/{coach_id}/delete")

        assert (
            _count_rows(admin_db, "magic_link_tokens", "user_id = ?", (coach_id,)) == 0
        )

    def test_cascade_delete_removes_passkey_credentials(self, admin_db: Path) -> None:
        """Deleting a user removes their passkey_credentials rows."""
        admin_id = _insert_user(admin_db, "cascadeadmin3@example.com", is_admin=1)
        coach_id = self._seed_full_user(admin_db, "cascadecoach3@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                client.post(f"/admin/users/{coach_id}/delete")

        assert (
            _count_rows(admin_db, "passkey_credentials", "user_id = ?", (coach_id,))
            == 0
        )

    def test_cascade_delete_removes_team_access(self, admin_db: Path) -> None:
        """Deleting a user removes their user_team_access rows."""
        admin_id = _insert_user(admin_db, "cascadeadmin4@example.com", is_admin=1)
        coach_id = self._seed_full_user(admin_db, "cascadecoach4@example.com")
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": raw_token}
            ) as client:
                client.post(f"/admin/users/{coach_id}/delete")

        assert (
            _count_rows(admin_db, "user_team_access", "user_id = ?", (coach_id,)) == 0
        )


# ---------------------------------------------------------------------------
# AC-10: Admin link on dashboard visible to admins only
# ---------------------------------------------------------------------------


class TestAdminLinkOnDashboard:
    """Admin link in dashboard header visible only to is_admin=1 users (AC-10)."""

    def test_admin_link_visible_for_admin_user(self, admin_db: Path) -> None:
        """Dashboard header shows Admin link for is_admin=1 users."""
        admin_id = _insert_user(admin_db, "linkadmin@example.com", is_admin=1)
        raw_token = _insert_session(admin_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/dashboard")
        assert response.status_code == 200
        assert "/admin/users" in response.text

    def test_admin_link_hidden_for_non_admin(self, admin_db: Path) -> None:
        """Dashboard header does not show Admin link for non-admin users."""
        # Need to grant team access so they can see the dashboard
        coach_id = _insert_user(admin_db, "nolink@example.com", is_admin=0)
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (coach_id, "lsb-varsity-2026"),
        )
        conn.commit()
        conn.close()
        raw_token = _insert_session(admin_db, coach_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": raw_token}) as client:
                response = client.get("/dashboard")
        assert response.status_code == 200
        assert "/admin/users" not in response.text
