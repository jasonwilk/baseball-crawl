# synthetic-test-data
"""Tests for the admin programs routes (E-143-01).

Tests cover:
- GET /admin/programs lists programs with all required columns
- GET /admin/programs shows Programs tab in sub-nav
- POST /admin/programs creates a new program and redirects with success flash
- POST /admin/programs duplicate program_id returns validation error (not 500)
- POST /admin/programs invalid program_type returns validation error
- Newly created program appears in team-add confirm page program dropdown
- Newly created program appears in team edit page program dropdown

Uses an in-process SQLite database via tmp_path; no Docker or network.

Run with:
    pytest tests/test_admin_programs.py -v
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
    INSERT OR IGNORE INTO programs (program_id, name, program_type, org_name)
        VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs', 'Lincoln Standing Bear High School'),
               ('lsb-legion', 'Lincoln Legion', 'legion', NULL);

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
    db_path = tmp_path / "test_programs.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    """Insert a user row and return the id."""
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
    """Insert a valid session and return the raw token."""
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


def _count_programs(db_path: Path) -> int:
    """Return total row count in programs table."""
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0]
    conn.close()
    return count


def _get_program(db_path: Path, program_id: str) -> dict | None:
    """Return a program row dict or None."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM programs WHERE program_id = ?", (program_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _insert_team_for_edit(db_path: Path) -> int:
    """Insert a standalone team (no program) and return INTEGER id."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        """
        INSERT INTO teams (name, membership_type, classification, public_id)
        VALUES ('Test Team', 'member', 'varsity', 'test-public-id')
        """
    )
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def programs_db(tmp_path: Path) -> Path:
    """Full schema database with seeded programs and teams."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# GET /admin/programs
# ---------------------------------------------------------------------------


class TestListPrograms:
    """GET /admin/programs renders the program list."""

    def test_list_programs_returns_200(self, programs_db: Path) -> None:
        """Admin session gets 200 from GET /admin/programs."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get("/admin/programs")

        assert response.status_code == 200

    def test_list_programs_shows_program_ids(self, programs_db: Path) -> None:
        """Programs page lists seeded program IDs."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get("/admin/programs")

        assert "lsb-hs" in response.text
        assert "lsb-legion" in response.text

    def test_list_programs_shows_program_type(self, programs_db: Path) -> None:
        """Programs page shows program types (hs, legion)."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get("/admin/programs")

        assert "hs" in response.text
        assert "legion" in response.text

    def test_list_programs_shows_programs_tab_active(self, programs_db: Path) -> None:
        """Programs page has Programs tab as active (bold) in the sub-nav."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get("/admin/programs")

        # Active tab: font-bold underline text-blue-900
        assert 'href="/admin/programs"' in response.text
        assert "font-bold underline text-blue-900" in response.text

    def test_list_programs_nav_includes_all_tabs(self, programs_db: Path) -> None:
        """Programs page sub-nav has Users, Teams, Programs, and Opponents links."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get("/admin/programs")

        assert 'href="/admin/users"' in response.text
        assert 'href="/admin/teams"' in response.text
        assert 'href="/admin/programs"' in response.text
        assert 'href="/admin/opponents"' in response.text

    def test_list_programs_requires_admin(self, programs_db: Path) -> None:
        """Unauthenticated request to /admin/programs redirects to login."""
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/admin/programs")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# Sub-nav Programs tab on existing admin pages
# ---------------------------------------------------------------------------


class TestSubNavProgramsTab:
    """Existing admin pages contain the Programs tab in their sub-nav."""

    def _get_page(self, db_path: Path, path: str) -> str:
        """Helper: make authenticated GET and return response text."""
        email = f"navtest{path.replace('/', '_')}@example.com"
        user_id = _insert_user(db_path, email)
        raw_token = _insert_session(db_path, user_id)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get(path)
        return response.text

    def test_teams_page_has_programs_tab(self, programs_db: Path) -> None:
        """Teams admin page includes Programs tab in sub-nav."""
        html = self._get_page(programs_db, "/admin/teams")
        assert 'href="/admin/programs"' in html

    def test_users_page_has_programs_tab(self, programs_db: Path) -> None:
        """Users admin page includes Programs tab in sub-nav."""
        html = self._get_page(programs_db, "/admin/users")
        assert 'href="/admin/programs"' in html

    def test_opponents_page_has_programs_tab(self, programs_db: Path) -> None:
        """Opponents admin page includes Programs tab in sub-nav."""
        html = self._get_page(programs_db, "/admin/opponents")
        assert 'href="/admin/programs"' in html

    def test_edit_user_page_has_programs_tab(self, programs_db: Path) -> None:
        """Edit user page includes Programs tab in sub-nav."""
        # Insert a user to edit
        email = "navtest_edit_user@example.com"
        user_id = _insert_user(programs_db, email)
        raw_token = _insert_session(programs_db, user_id)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": email},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get(f"/admin/users/{user_id}/edit")
        assert 'href="/admin/programs"' in response.text

    def test_edit_team_page_has_programs_tab(self, programs_db: Path) -> None:
        """Edit team page includes Programs tab in sub-nav."""
        team_id = _insert_team_for_edit(programs_db)
        email = "navtest_edit_team@example.com"
        user_id = _insert_user(programs_db, email)
        raw_token = _insert_session(programs_db, user_id)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": email},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get(f"/admin/teams/{team_id}/edit")
        assert 'href="/admin/programs"' in response.text

    def test_confirm_team_page_has_programs_tab(self, programs_db: Path) -> None:
        """Confirm-add-team page includes Programs tab in sub-nav."""
        email = "navtest_confirm@example.com"
        user_id = _insert_user(programs_db, email)
        raw_token = _insert_session(programs_db, user_id)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": email},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get(
                    "/admin/teams/confirm",
                    params={"public_id": "some-public-id", "team_name": "Test Team"},
                )
        assert response.status_code == 200
        assert 'href="/admin/programs"' in response.text

    def test_opponent_connect_page_has_programs_tab(self, programs_db: Path) -> None:
        """Opponent connect page includes Programs tab in sub-nav."""
        # Insert a member team and an opponent_link row so the route returns 200
        email = "navtest_connect@example.com"
        user_id = _insert_user(programs_db, email)
        raw_token = _insert_session(programs_db, user_id)
        conn = sqlite3.connect(str(programs_db))
        conn.row_factory = sqlite3.Row
        our_team_id = conn.execute(
            "SELECT id FROM teams WHERE membership_type='member' LIMIT 1"
        ).fetchone()["id"]
        cursor = conn.execute(
            """
            INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name)
            VALUES (?, 'root-uuid-nav-test', 'Nav Test Opponent')
            """,
            (our_team_id,),
        )
        link_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": email},
        ):
            with TestClient(
                app, cookies={"session": raw_token, "csrf_token": _CSRF}
            ) as client:
                response = client.get(f"/admin/opponents/{link_id}/connect")
        assert response.status_code == 200
        assert 'href="/admin/programs"' in response.text


# ---------------------------------------------------------------------------
# POST /admin/programs
# ---------------------------------------------------------------------------


class TestCreateProgram:
    """POST /admin/programs creates programs and handles errors."""

    def test_create_program_redirects_on_success(self, programs_db: Path) -> None:
        """Valid submission redirects to /admin/programs with 303."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.post(
                    "/admin/programs",
                    data={
                        "program_id": "new-prog",
                        "name": "New Program",
                        "program_type": "usssa",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )

        assert response.status_code == 303
        assert "/admin/programs" in response.headers["location"]

    def test_create_program_inserts_row(self, programs_db: Path) -> None:
        """Valid submission inserts a row in the programs table."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        before = _count_programs(programs_db)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                client.post(
                    "/admin/programs",
                    data={
                        "program_id": "new-prog",
                        "name": "New Program",
                        "program_type": "usssa",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )

        after = _count_programs(programs_db)
        assert after == before + 1

        row = _get_program(programs_db, "new-prog")
        assert row is not None
        assert row["name"] == "New Program"
        assert row["program_type"] == "usssa"

    def test_create_program_with_org_name(self, programs_db: Path) -> None:
        """org_name is saved when provided."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                client.post(
                    "/admin/programs",
                    data={
                        "program_id": "org-prog",
                        "name": "Org Program",
                        "program_type": "hs",
                        "org_name": "My School District",
                        "csrf_token": _CSRF,
                    },
                )

        row = _get_program(programs_db, "org-prog")
        assert row is not None
        assert row["org_name"] == "My School District"

    def test_success_flash_in_redirect_url(self, programs_db: Path) -> None:
        """Redirect URL contains a success message fragment."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.post(
                    "/admin/programs",
                    data={
                        "program_id": "flash-prog",
                        "name": "Flash Program",
                        "program_type": "legion",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )

        assert "msg=" in response.headers["location"]

    def test_duplicate_program_id_returns_error(self, programs_db: Path) -> None:
        """Duplicate program_id returns 200 with error message (not 500)."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.post(
                    "/admin/programs",
                    data={
                        "program_id": "lsb-hs",  # already exists
                        "name": "Duplicate HS",
                        "program_type": "hs",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )

        assert response.status_code == 200
        assert "already exists" in response.text.lower()

    def test_duplicate_program_id_does_not_insert(self, programs_db: Path) -> None:
        """Duplicate program_id submission does not insert a new row."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        before = _count_programs(programs_db)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                client.post(
                    "/admin/programs",
                    data={
                        "program_id": "lsb-hs",  # already exists
                        "name": "Duplicate HS",
                        "program_type": "hs",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )

        after = _count_programs(programs_db)
        assert after == before

    def test_invalid_program_type_returns_error(self, programs_db: Path) -> None:
        """Invalid program_type returns 200 with error message."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                response = client.post(
                    "/admin/programs",
                    data={
                        "program_id": "bad-type",
                        "name": "Bad Type Program",
                        "program_type": "college",  # not valid
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )

        assert response.status_code == 200
        assert "Invalid program type" in response.text

    def test_invalid_type_does_not_insert(self, programs_db: Path) -> None:
        """Invalid program_type does not insert a new row."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        before = _count_programs(programs_db)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                client.post(
                    "/admin/programs",
                    data={
                        "program_id": "bad-type",
                        "name": "Bad Type Program",
                        "program_type": "college",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )

        after = _count_programs(programs_db)
        assert after == before


# ---------------------------------------------------------------------------
# AC-5: New programs appear in team dropdowns immediately
# ---------------------------------------------------------------------------


class TestNewProgramsInDropdowns:
    """Newly created programs appear in the program dropdown on team pages."""

    def test_new_program_in_confirm_page_dropdown(self, programs_db: Path) -> None:
        """After creating a program, it appears in the confirm_team page dropdown."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                # Create a new program (follow redirect manually so client state persists)
                post_resp = client.post(
                    "/admin/programs",
                    data={
                        "program_id": "new-usssa",
                        "name": "USSSA Tournament",
                        "program_type": "usssa",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )
                assert post_resp.status_code == 303

                # Access the confirm page directly -- requires non-empty public_id
                response = client.get(
                    "/admin/teams/confirm",
                    params={"public_id": "some-public-id", "team_name": "Test"},
                )

        # Confirm we got the confirm page (not a redirect to another page)
        assert response.status_code == 200
        assert "Confirm Add Team" in response.text
        assert "USSSA Tournament" in response.text or "new-usssa" in response.text

    def test_new_program_in_edit_team_dropdown(self, programs_db: Path) -> None:
        """After creating a program, it appears in the edit team page dropdown."""
        user_id = _insert_user(programs_db, "admin@example.com")
        raw_token = _insert_session(programs_db, user_id)
        team_id = _insert_team_for_edit(programs_db)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(programs_db), "ADMIN_EMAIL": "admin@example.com"},
        ):
            with TestClient(
                app,
                follow_redirects=True,
                cookies={"session": raw_token, "csrf_token": _CSRF},
            ) as client:
                # Create a new program
                client.post(
                    "/admin/programs",
                    data={
                        "program_id": "new-usssa-edit",
                        "name": "USSSA Edit Test",
                        "program_type": "usssa",
                        "org_name": "",
                        "csrf_token": _CSRF,
                    },
                )
                # Access the edit team page
                response = client.get(f"/admin/teams/{team_id}/edit")

        assert "USSSA Edit Test" in response.text or "new-usssa-edit" in response.text
