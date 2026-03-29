# synthetic-test-data
"""Tests for admin team management routes -- E-100-04.

Tests cover AC-17 sub-items (a)-(n):
(a) GET /admin/teams returns 200 for admin, 403 for non-admin, 302 for unauthenticated.
(b) Flat team list with program/division/membership/opponent_count columns.
(c) POST /admin/teams with valid URL redirects to /admin/teams/confirm.
(d) Phase 1: URL parsed to public_id; bridge called for gc_uuid discovery.
(e) Phase 1: 403 from bridge stored as NULL gc_uuid (gc_uuid_status=forbidden).
(f) POST /admin/teams with invalid URL shows error on teams page.
(g) POST /admin/teams with raw UUID input shows UUID-rejection error.
(h) GET /admin/teams/confirm shows team name, public_id, gc_uuid status badge.
(i) GET /admin/teams/confirm duplicate detection shows error.
(j) POST /admin/teams/confirm inserts team and redirects to /admin/teams with flash.
(k) POST /admin/teams/confirm duplicate shows error, no insert.
(l) POST /admin/teams/confirm TOCTOU guard: gc_uuid refreshed before insert.
(m) POST /admin/teams/confirm: gc_uuid=None when bridge 403 on re-verify.
(n) Classification inference: JV/varsity/freshman/reserve/legion/age-U patterns.
(o) Program pre-selection: longest substring match.
(p) GET /admin/teams/{id}/edit uses INTEGER id path parameter.
(q) POST /admin/teams/{id}/edit updates team with INTEGER id.
(r) POST /admin/teams/{id}/toggle-active uses INTEGER id.
AC-16: User-team assignment form uses INTEGER team ids.
AC-18: Flash messages, ?msg= and ?error= params rendered.

Run with:
    pytest tests/test_admin_teams.py -v
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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

_CSRF = "test-csrf-token"
from src.api.main import app  # noqa: E402
from src.gamechanger.team_resolver import GameChangerAPIError, TeamNotFoundError, TeamProfile  # noqa: E402

_SEED_SQL = """
    INSERT OR IGNORE INTO programs (program_id, name, program_type)
        VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs');

    INSERT OR IGNORE INTO teams (name, program_id, membership_type, classification)
        VALUES ('LSB Varsity 2026', 'lsb-hs', 'member', 'varsity');
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a seeded test database.

    Args:
        tmp_path: pytest tmp_path fixture directory.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_teams.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    """Insert a user row and return the id."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, '')", (email,)
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
    conn.execute("PRAGMA foreign_keys=ON;")
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


def _insert_team(
    db_path: Path,
    name: str,
    membership_type: str = "member",
    public_id: str | None = None,
    gc_uuid: str | None = None,
    classification: str | None = None,
    program_id: str | None = None,
) -> int:
    """Insert a team row and return the INTEGER id."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        """
        INSERT INTO teams (name, membership_type, public_id, gc_uuid, classification, program_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, membership_type, public_id, gc_uuid, classification, program_id),
    )
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


def _count_rows(db_path: Path, table: str, where_clause: str, params: tuple) -> int:
    """Return a row count from a table."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_clause}", params)
    count = cursor.fetchone()[0]
    conn.close()
    return count


def _make_profile(name: str = "Riverside Hawks") -> TeamProfile:
    """Build a minimal TeamProfile mock."""
    return TeamProfile(
        public_id="abc123",
        name=name,
        sport="baseball",
    )


def _admin_env(db_path: Path, admin_email: str) -> dict[str, str]:
    """Build env dict for admin session."""
    return {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": admin_email}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def team_db(tmp_path: Path) -> Path:
    """Full schema database with seed data."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-17a: Auth guards on /admin/teams
# ---------------------------------------------------------------------------


class TestTeamsListAuth:
    """GET /admin/teams auth guards (AC-17a)."""

    def test_admin_gets_200(self, team_db: Path) -> None:
        """Admin email gets 200 from GET /admin/teams."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 200

    def test_non_admin_gets_403(self, team_db: Path) -> None:
        """Non-admin email gets 403 from GET /admin/teams."""
        user_id = _insert_user(team_db, "coach@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(team_db), "ADMIN_EMAIL": "other@example.com"},
        ):
            with TestClient(app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 403

    def test_no_session_redirects_to_login(self, team_db: Path) -> None:
        """Unauthenticated GET /admin/teams redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(team_db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# AC-17b: Flat team list columns
# ---------------------------------------------------------------------------


class TestTeamsFlatList:
    """GET /admin/teams shows flat list with new columns (AC-17b)."""

    def test_flat_list_shows_team_name(self, team_db: Path) -> None:
        """Flat list includes seeded team name."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert "LSB Varsity 2026" in response.text

    def test_flat_list_shows_membership_badge(self, team_db: Path) -> None:
        """Flat list shows membership type (member/tracked) labels."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        # 'Member' badge appears for the seeded varsity team
        assert "Member" in response.text

    def test_flat_list_uses_integer_id_in_edit_link(self, team_db: Path) -> None:
        """Edit links use INTEGER id (not a text slug)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        # Edit link should be /admin/teams/1/edit (integer 1, not a text slug)
        assert "/admin/teams/1/edit" in response.text

    def test_opponent_count_links_to_filtered_opponents_page(self, team_db: Path) -> None:
        """Opponent count links to /admin/opponents?team_id=<integer_id> (AC-6)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        # Opponent count should be a link to /admin/opponents?team_id=1
        assert "/admin/opponents?team_id=1" in response.text

    def test_flash_msg_displayed(self, team_db: Path) -> None:
        """?msg= query param renders a flash message on teams page."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams?msg=Team+added")
        assert "Team added" in response.text

    def test_added_flash_shows_team_name_and_hint(self, team_db: Path) -> None:
        """AC-8: ?added=1&team_name= renders enhanced flash with team name and Sync button hint."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams?added=1&team_name=River+Hawks")
        assert "River Hawks" in response.text
        assert "Sync" in response.text
        assert "bg-green-100" in response.text

    def test_added_flash_no_duplicate_banner(self, team_db: Path) -> None:
        """AC-4: When ?added=1 is set, ?msg= is absent so only one banner renders."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams?added=1&team_name=River+Hawks")
        # Count occurrences of the green banner div opening tag
        assert response.text.count("bg-green-100") == 1

    def test_added_flash_team_name_is_autoescaped(self, team_db: Path) -> None:
        """AC-3/AC-4: XSS attempt in team_name is autoescaped, not rendered as HTML."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams?added=1&team_name=%3Cscript%3Ealert(1)%3C%2Fscript%3E")
        assert "<script>" not in response.text
        assert "&lt;script&gt;" in response.text

    def test_flash_error_displayed(self, team_db: Path) -> None:
        """?error= query param renders an error banner on teams page."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams?error=Something+went+wrong")
        assert "Something went wrong" in response.text


# ---------------------------------------------------------------------------
# AC-17c, d, e: Phase 1 POST /admin/teams
# ---------------------------------------------------------------------------


class TestPhase1AddTeam:
    """POST /admin/teams Phase 1 resolution (AC-17c, d, e)."""

    def test_valid_url_redirects_to_confirm(self, team_db: Path) -> None:
        """Phase 1 with valid URL redirects to /admin/teams/confirm."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        profile = _make_profile("Riverside Hawks")

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid", return_value="uuid-1234"
        ), patch(
            "src.api.routes.admin.resolve_team", return_value=profile
        ), patch(
            "src.api.routes.admin.parse_team_url"
        ) as mock_parse:
            mock_result = MagicMock()
            mock_result.is_uuid = False
            mock_result.value = "abc123"
            mock_parse.return_value = mock_result

            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "https://web.gc.com/teams/abc123/schedule", "csrf_token": _CSRF},
                    )

        assert response.status_code == 303
        assert "/admin/teams/confirm" in response.headers["location"]

    def test_bridge_forbidden_sets_gc_uuid_forbidden(self, team_db: Path) -> None:
        """Phase 1: 403 from bridge results in gc_uuid_status=forbidden in redirect."""
        from src.gamechanger.bridge import BridgeForbiddenError

        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        profile = _make_profile("Riverside Hawks")

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            side_effect=BridgeForbiddenError("forbidden"),
        ), patch(
            "src.api.routes.admin.resolve_team", return_value=profile
        ), patch(
            "src.api.routes.admin.parse_team_url"
        ) as mock_parse:
            mock_result = MagicMock()
            mock_result.is_uuid = False
            mock_result.value = "abc123"
            mock_parse.return_value = mock_result

            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123", "csrf_token": _CSRF},
                    )

        assert response.status_code == 303
        location = response.headers["location"]
        assert "gc_uuid_status=forbidden" in location
        assert "gc_uuid=" not in location

    def test_bridge_success_includes_gc_uuid_in_redirect(self, team_db: Path) -> None:
        """Phase 1: successful bridge call includes gc_uuid in redirect params."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        profile = _make_profile("Riverside Hawks")

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value="gc-uuid-9999",
        ), patch(
            "src.api.routes.admin.resolve_team", return_value=profile
        ), patch(
            "src.api.routes.admin.parse_team_url"
        ) as mock_parse:
            mock_result = MagicMock()
            mock_result.is_uuid = False
            mock_result.value = "abc123"
            mock_parse.return_value = mock_result

            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123", "csrf_token": _CSRF},
                    )

        location = response.headers["location"]
        assert "gc_uuid=gc-uuid-9999" in location
        assert "gc_uuid_status=found" in location

    def test_invalid_url_shows_error(self, team_db: Path) -> None:
        """Phase 1: URL parse failure shows error message on teams page."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.parse_team_url",
            side_effect=ValueError("Cannot parse URL"),
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "not-a-valid-url", "csrf_token": _CSRF},
                    )

        assert response.status_code == 200
        assert "Cannot parse URL" in response.text

    def test_uuid_input_rejected(self, team_db: Path) -> None:
        """Phase 1: raw UUID input is rejected with a specific error."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch("src.api.routes.admin.parse_team_url") as mock_parse:
            mock_result = MagicMock()
            mock_result.is_uuid = True
            mock_result.value = "some-uuid"
            mock_parse.return_value = mock_result

            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "550e8400-e29b-41d4-a716-446655440000", "csrf_token": _CSRF},
                    )

        assert response.status_code == 200
        assert "UUID" in response.text

    def test_team_not_found_shows_error(self, team_db: Path) -> None:
        """Phase 1: TeamNotFoundError shows error on teams page."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid", return_value="uuid-1"
        ), patch(
            "src.api.routes.admin.resolve_team",
            side_effect=TeamNotFoundError("abc123"),
        ), patch(
            "src.api.routes.admin.parse_team_url"
        ) as mock_parse:
            mock_result = MagicMock()
            mock_result.is_uuid = False
            mock_result.value = "abc123"
            mock_parse.return_value = mock_result

            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123", "csrf_token": _CSRF},
                    )

        assert response.status_code == 200
        assert "not found" in response.text.lower()

    def test_api_error_shows_error(self, team_db: Path) -> None:
        """Phase 1: GameChangerAPIError shows error on teams page."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid", return_value="uuid-1"
        ), patch(
            "src.api.routes.admin.resolve_team",
            side_effect=GameChangerAPIError("network error"),
        ), patch(
            "src.api.routes.admin.parse_team_url"
        ) as mock_parse:
            mock_result = MagicMock()
            mock_result.is_uuid = False
            mock_result.value = "abc123"
            mock_parse.return_value = mock_result

            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123", "csrf_token": _CSRF},
                    )

        assert response.status_code == 200
        assert "GameChanger" in response.text


# ---------------------------------------------------------------------------
# AC-17h, i: Phase 2 GET /admin/teams/confirm
# ---------------------------------------------------------------------------


class TestPhase2ConfirmForm:
    """GET /admin/teams/confirm displays resolved info (AC-17h, i)."""

    def test_confirm_page_shows_team_name(self, team_db: Path) -> None:
        """GET /admin/teams/confirm renders the team name from query params."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(
                    "/admin/teams/confirm",
                    params={
                        "public_id": "abc123",
                        "team_name": "Riverside Hawks",
                        "gc_uuid_status": "forbidden",
                    },
                )
        assert response.status_code == 200
        assert "Riverside Hawks" in response.text

    def test_confirm_page_shows_public_id(self, team_db: Path) -> None:
        """GET /admin/teams/confirm shows the public_id."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(
                    "/admin/teams/confirm",
                    params={
                        "public_id": "abc123",
                        "team_name": "Riverside Hawks",
                        "gc_uuid_status": "forbidden",
                    },
                )
        assert "abc123" in response.text

    def test_confirm_page_shows_gc_uuid_found_badge(self, team_db: Path) -> None:
        """Confirm page shows Discovered badge when gc_uuid is found."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(
                    "/admin/teams/confirm",
                    params={
                        "public_id": "abc123",
                        "team_name": "Riverside Hawks",
                        "gc_uuid": "some-uuid",
                        "gc_uuid_status": "found",
                    },
                )
        assert "Discovered" in response.text

    def test_confirm_page_shows_not_available_badge_on_forbidden(
        self, team_db: Path
    ) -> None:
        """Confirm page shows Not available badge when gc_uuid is forbidden."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(
                    "/admin/teams/confirm",
                    params={
                        "public_id": "abc123",
                        "team_name": "Riverside Hawks",
                        "gc_uuid_status": "forbidden",
                    },
                )
        assert "403" in response.text or "Not available" in response.text

    def test_confirm_page_member_radio_disabled_when_gc_uuid_forbidden(
        self, team_db: Path
    ) -> None:
        """Confirm page disables Member radio and shows warning when gc_uuid_status=forbidden."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(
                    "/admin/teams/confirm",
                    params={
                        "public_id": "abc123",
                        "team_name": "Riverside Hawks",
                        "gc_uuid_status": "forbidden",
                    },
                )
        assert response.status_code == 200
        # Member radio must carry the disabled attribute
        assert 'value="member"' in response.text
        assert "disabled" in response.text
        # Warning message must explain why
        assert "GameChanger UUID" in response.text

    def test_confirm_page_member_radio_enabled_when_gc_uuid_found(
        self, team_db: Path
    ) -> None:
        """Confirm page enables Member radio when gc_uuid_status=found."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value="some-uuid",
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                    response = client.get(
                        "/admin/teams/confirm",
                        params={
                            "public_id": "abc123",
                            "team_name": "Riverside Hawks",
                            "gc_uuid": "some-uuid",
                            "gc_uuid_status": "found",
                        },
                    )
        assert response.status_code == 200
        assert 'value="member"' in response.text
        # The warning about UUID being required must NOT appear when UUID is available
        assert "UUID not available" not in response.text

    def test_confirm_page_duplicate_shows_error(self, team_db: Path) -> None:
        """GET /admin/teams/confirm shows error when team is already in DB."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        # Insert team with public_id=abc123
        _insert_team(team_db, "Existing Team", public_id="abc123")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(
                    "/admin/teams/confirm",
                    params={
                        "public_id": "abc123",
                        "team_name": "Existing Team",
                        "gc_uuid_status": "forbidden",
                    },
                )
        assert "already in the system" in response.text

    def test_confirm_page_missing_public_id_redirects(self, team_db: Path) -> None:
        """GET /admin/teams/confirm without public_id redirects to /admin/teams."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.get("/admin/teams/confirm")
        assert response.status_code == 302
        assert "/admin/teams" in response.headers["location"]


# ---------------------------------------------------------------------------
# AC-17j, k, l, m: Phase 2 POST /admin/teams/confirm
# ---------------------------------------------------------------------------


class TestPhase2ConfirmSubmit:
    """POST /admin/teams/confirm creates the team (AC-17j, k, l, m)."""

    def test_confirm_submit_inserts_team(self, team_db: Path) -> None:
        """Successful POST /admin/teams/confirm inserts a new team row."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value="gc-uuid-fresh",
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "newteam1",
                            "team_name": "New Team",
                            "gc_uuid": "gc-uuid-fresh",
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )

        assert response.status_code == 303
        assert _count_rows(team_db, "teams", "public_id = ?", ("newteam1",)) == 1

    def test_confirm_submit_redirects_with_flash(self, team_db: Path) -> None:
        """POST /admin/teams/confirm on success redirects with ?added=1 flash (E-142-05)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value="gc-uuid-xyz",
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "flashteam",
                            "team_name": "Flash Team",
                            "gc_uuid": "gc-uuid-xyz",
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )

        assert "added=1" in response.headers["location"]
        assert "team_name=Flash+Team" in response.headers["location"]

    def test_confirm_submit_duplicate_shows_error(self, team_db: Path) -> None:
        """POST /admin/teams/confirm with duplicate public_id shows error, no insert."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        _insert_team(team_db, "Already Exists", public_id="dup123")

        from src.gamechanger.bridge import BridgeForbiddenError

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            side_effect=BridgeForbiddenError("403"),
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "dup123",
                            "team_name": "Already Exists",
                            "gc_uuid": "",
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )

        assert response.status_code == 200
        assert "already in the system" in response.text
        # Only 1 row (the existing one)
        assert _count_rows(team_db, "teams", "public_id = ?", ("dup123",)) == 1

    def test_confirm_submit_duplicate_gc_uuid_case_insensitive(self, team_db: Path) -> None:
        """POST /admin/teams/confirm rejects gc_uuid that differs only by case from existing."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        existing_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        # Store UUID in uppercase on an existing team.
        _insert_team(team_db, "Other Team", public_id="other-pub-id", gc_uuid=existing_uuid.upper())

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value=existing_uuid,  # lowercase from bridge
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "new-team-pub",
                            "team_name": "New Team",
                            "gc_uuid": existing_uuid,
                            "membership_type": "member",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )

        assert response.status_code == 200
        assert "already in the system" in response.text
        # New team must not have been inserted.
        assert _count_rows(team_db, "teams", "public_id = ?", ("new-team-pub",)) == 0

    def test_confirm_submit_toctou_refreshes_gc_uuid(self, team_db: Path) -> None:
        """POST: TOCTOU guard calls bridge again to refresh gc_uuid before insert."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value="fresh-uuid-999",
        ) as mock_bridge:
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "toctou1",
                            "team_name": "TOCTOU Team",
                            "gc_uuid": "stale-uuid",  # Phase 1 found a uuid -> triggers re-verify
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )
        # Bridge should be called once (TOCTOU re-verify)
        mock_bridge.assert_called_once()

        # The inserted gc_uuid should be the fresh one
        conn = sqlite3.connect(str(team_db))
        row = conn.execute(
            "SELECT gc_uuid FROM teams WHERE public_id = ?", ("toctou1",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "fresh-uuid-999"

    def test_confirm_submit_gc_uuid_null_on_403_during_reverify(
        self, team_db: Path
    ) -> None:
        """POST: gc_uuid stored as NULL when TOCTOU re-verify returns 403."""
        from src.gamechanger.bridge import BridgeForbiddenError

        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            side_effect=BridgeForbiddenError("now 403"),
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "stale1",
                            "team_name": "Stale UUID Team",
                            "gc_uuid": "old-uuid",  # was found in Phase 1
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )

        conn = sqlite3.connect(str(team_db))
        row = conn.execute(
            "SELECT gc_uuid FROM teams WHERE public_id = ?", ("stale1",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] is None  # stored as NULL

    def test_confirm_submit_stores_membership_type(self, team_db: Path) -> None:
        """POST /admin/teams/confirm stores the chosen membership_type."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        from src.gamechanger.bridge import BridgeForbiddenError

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            side_effect=BridgeForbiddenError("403"),
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "memberteam1",
                            "team_name": "Member Team",
                            "gc_uuid": "",
                            "membership_type": "member",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )

        conn = sqlite3.connect(str(team_db))
        row = conn.execute(
            "SELECT membership_type FROM teams WHERE public_id = ?", ("memberteam1",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "member"

    def test_confirm_submit_duplicate_detected_via_phase1_uuid_when_reverify_fails(
        self, team_db: Path
    ) -> None:
        """POST: duplicate detected via Phase 1 gc_uuid when TOCTOU reverify returns 403.

        Scenario:
        - A team row exists with gc_uuid='existing-uuid' but no public_id
          (as created by opponent_resolver).
        - The add-team confirm POST arrives with public_id='newpub' and
          gc_uuid='existing-uuid' (Phase 1 found it).
        - TOCTOU reverify fails (403), so gc_uuid_value becomes None.
        - The duplicate check must still catch the existing row via the Phase 1 UUID.
        """
        from src.gamechanger.bridge import BridgeForbiddenError

        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        # Team row with gc_uuid but no public_id (opponent_resolver pattern)
        _insert_team(team_db, "Existing Opponent", gc_uuid="existing-uuid", membership_type="tracked")

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            side_effect=BridgeForbiddenError("403"),
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "newpub",
                            "team_name": "Existing Opponent",
                            "gc_uuid": "existing-uuid",  # Phase 1 discovered this
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "csrf_token": _CSRF,
                        },
                    )

        assert response.status_code == 200
        assert "already in the system" in response.text
        # No new row should be inserted; only the original row exists
        assert _count_rows(team_db, "teams", "gc_uuid = ?", ("existing-uuid",)) == 1


# ---------------------------------------------------------------------------
# AC-17n: Classification inference
# ---------------------------------------------------------------------------


class TestClassificationInference:
    """_infer_classification correctly maps team name keywords (AC-17n)."""

    def _infer(self, name: str) -> str | None:
        from src.api.routes.admin import _infer_classification
        return _infer_classification(name)

    def test_jv_keyword(self) -> None:
        assert self._infer("LSB JV 2026") == "jv"

    def test_junior_varsity_keyword(self) -> None:
        assert self._infer("LSB Junior Varsity 2026") == "jv"

    def test_varsity_keyword(self) -> None:
        assert self._infer("LSB Varsity 2026") == "varsity"

    def test_freshman_keyword(self) -> None:
        assert self._infer("LSB Freshman 2026") == "freshman"

    def test_frosh_keyword(self) -> None:
        assert self._infer("LSB Frosh 2026") == "freshman"

    def test_reserve_keyword(self) -> None:
        assert self._infer("LSB Reserve Team") == "reserve"

    def test_legion_keyword(self) -> None:
        assert self._infer("Lincoln Legion Post 100") == "legion"

    def test_age_14u(self) -> None:
        assert self._infer("Riverside 14U Hawks") == "14U"

    def test_age_12u(self) -> None:
        assert self._infer("Metro 12U Elite") == "12U"

    def test_age_8u(self) -> None:
        assert self._infer("Smith 8U Stars") == "8U"

    def test_age_lowercase_u(self) -> None:
        assert self._infer("Metro 13u Prospects") == "13U"

    def test_jv_wins_over_varsity_in_junior_varsity(self) -> None:
        """'Junior Varsity' should return 'jv', not 'varsity'."""
        assert self._infer("Lincoln Junior Varsity") == "jv"

    def test_out_of_range_age_returns_none(self) -> None:
        """Age patterns outside 8U-14U return None."""
        assert self._infer("Metro 7U Stars") is None

    def test_no_keyword_returns_none(self) -> None:
        assert self._infer("Riverside Hawks Baseball") is None


# ---------------------------------------------------------------------------
# AC-17o: Program pre-selection
# ---------------------------------------------------------------------------


class TestProgramInference:
    """_infer_program_id finds the longest matching program name (AC-17o)."""

    def _infer(self, team_name: str, programs: list[dict]) -> str | None:
        from src.api.routes.admin import _infer_program_id
        return _infer_program_id(team_name, programs)

    def test_exact_substring_match(self) -> None:
        programs = [{"program_id": "lsb-hs", "name": "Lincoln Standing Bear HS"}]
        assert self._infer("Lincoln Standing Bear HS Varsity", programs) == "lsb-hs"

    def test_case_insensitive_match(self) -> None:
        programs = [{"program_id": "lsb-hs", "name": "Lincoln Standing Bear HS"}]
        assert self._infer("lincoln standing bear hs varsity", programs) == "lsb-hs"

    def test_no_match_returns_none(self) -> None:
        programs = [{"program_id": "lsb-hs", "name": "Lincoln Standing Bear HS"}]
        assert self._infer("Riverside Hawks", programs) is None

    def test_longest_match_wins(self) -> None:
        programs = [
            {"program_id": "lincoln", "name": "Lincoln"},
            {"program_id": "lsb-hs", "name": "Lincoln Standing Bear HS"},
        ]
        # Both match, but 'Lincoln Standing Bear HS' is longer
        result = self._infer("Lincoln Standing Bear HS Varsity 2026", programs)
        assert result == "lsb-hs"

    def test_empty_programs_returns_none(self) -> None:
        assert self._infer("Any Team Name", []) is None


# ---------------------------------------------------------------------------
# AC-17p: GET /admin/teams/{id}/edit uses INTEGER id
# ---------------------------------------------------------------------------


class TestEditTeamForm:
    """GET /admin/teams/{id}/edit uses INTEGER path param (AC-17p)."""

    def test_edit_form_loads_with_integer_id(self, team_db: Path) -> None:
        """GET /admin/teams/1/edit returns 200 for a valid INTEGER team id."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        # Get the id of the seeded team
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(f"/admin/teams/{team_id}/edit")
        assert response.status_code == 200
        assert "LSB Varsity 2026" in response.text

    def test_edit_form_shows_membership_type(self, team_db: Path) -> None:
        """Edit form shows the team's membership_type field."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(f"/admin/teams/{team_id}/edit")
        # Should have membership radio buttons
        assert "membership_type" in response.text

    def test_edit_form_404_for_missing_id(self, team_db: Path) -> None:
        """GET /admin/teams/9999/edit returns 404 for nonexistent team."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams/9999/edit")
        assert response.status_code == 404

    def test_edit_form_action_uses_integer_id(self, team_db: Path) -> None:
        """Edit form's action attribute uses the INTEGER team id."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(f"/admin/teams/{team_id}/edit")
        assert f"/admin/teams/{team_id}/edit" in response.text


# ---------------------------------------------------------------------------
# AC-17q: POST /admin/teams/{id}/edit updates team with INTEGER id
# ---------------------------------------------------------------------------


class TestUpdateTeam:
    """POST /admin/teams/{id}/edit (AC-17q, AC-17b, AC-17m)."""

    def test_update_team_changes_name(self, team_db: Path) -> None:
        """POST /admin/teams/{id}/edit updates team name."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/edit",
                    data={
                        "name": "LSB Varsity Updated",
                        "program_id": "",
                        "classification": "",
                        "membership_type": "member",
                        "csrf_token": _CSRF,
                    },
                )
        assert response.status_code == 303
        assert _count_rows(
            team_db, "teams", "name = ?", ("LSB Varsity Updated",)
        ) == 1

    def test_update_team_persists_program_id(self, team_db: Path) -> None:
        """POST /admin/teams/{id}/edit persists program_id (AC-17b)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        # Clear program_id first so we can verify the POST sets it
        conn.execute("UPDATE teams SET program_id = NULL WHERE id = ?", (team_id,))
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/edit",
                    data={
                        "name": "LSB Varsity 2026",
                        "program_id": "lsb-hs",
                        "classification": "",
                        "membership_type": "tracked",
                        "csrf_token": _CSRF,
                    },
                )
        assert response.status_code == 303
        assert _count_rows(
            team_db, "teams", "id = ? AND program_id = ?", (team_id, "lsb-hs")
        ) == 1

    def test_update_team_persists_classification(self, team_db: Path) -> None:
        """POST /admin/teams/{id}/edit persists classification (AC-17b)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/edit",
                    data={
                        "name": "LSB Varsity 2026",
                        "program_id": "",
                        "classification": "jv",
                        "membership_type": "tracked",
                        "csrf_token": _CSRF,
                    },
                )
        assert response.status_code == 303
        assert _count_rows(
            team_db, "teams", "id = ? AND classification = ?", (team_id, "jv")
        ) == 1

    def test_update_team_membership_type_change_tracked_to_member(
        self, team_db: Path
    ) -> None:
        """Membership type change from tracked to member is persisted (AC-17m)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        # Start as tracked
        conn.execute(
            "UPDATE teams SET membership_type = 'tracked' WHERE id = ?", (team_id,)
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/edit",
                    data={
                        "name": "LSB Varsity 2026",
                        "program_id": "",
                        "classification": "",
                        "membership_type": "member",
                        "csrf_token": _CSRF,
                    },
                )
        assert response.status_code == 303
        assert _count_rows(
            team_db, "teams", "id = ? AND membership_type = ?", (team_id, "member")
        ) == 1


# ---------------------------------------------------------------------------
# AC-17r: POST /admin/teams/{id}/toggle-active uses INTEGER id
# ---------------------------------------------------------------------------


class TestToggleTeamActive:
    """POST /admin/teams/{id}/toggle-active (AC-17r)."""

    def test_toggle_active_deactivates_team(self, team_db: Path) -> None:
        """Toggle on active team sets is_active=0."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(f"/admin/teams/{team_id}/toggle-active", data={"csrf_token": _CSRF})
        assert response.status_code == 303
        assert _count_rows(
            team_db, "teams", "id = ? AND is_active = 0", (team_id,)
        ) == 1

    def test_toggle_active_reactivates_team(self, team_db: Path) -> None:
        """Toggle on inactive team sets is_active=1."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        inactive_id = _insert_team(team_db, "Inactive Team")
        conn = sqlite3.connect(str(team_db))
        conn.execute("UPDATE teams SET is_active=0 WHERE id=?", (inactive_id,))
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(f"/admin/teams/{inactive_id}/toggle-active", data={"csrf_token": _CSRF})
        assert response.status_code == 303
        assert _count_rows(
            team_db, "teams", "id = ? AND is_active = 1", (inactive_id,)
        ) == 1


# ---------------------------------------------------------------------------
# AC-16: User-team assignment uses INTEGER team ids
# ---------------------------------------------------------------------------


class TestUserTeamAssignmentIntegerIds:
    """User-team assignment form uses INTEGER team ids (AC-16)."""

    def test_edit_user_form_shows_integer_team_id_in_checkbox(
        self, team_db: Path
    ) -> None:
        """GET /admin/users/{id}/edit shows checkboxes with INTEGER team ids."""
        admin_id = _insert_user(team_db, "admin@example.com")
        coach_id = _insert_user(team_db, "coach@example.com")
        token = _insert_session(team_db, admin_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get(f"/admin/users/{coach_id}/edit")
        # The checkbox value should be the integer id (e.g., "1"), not a text slug
        assert f'value="{team_id}"' in response.text


# ---------------------------------------------------------------------------
# E-142-01: user_team_access fan-out on member team create
# ---------------------------------------------------------------------------


class TestMemberTeamAccessFanOut:
    """Fan-out inserts user_team_access for all users when a member team is created (E-142-01)."""

    def _post_new_team(
        self,
        client,
        public_id: str,
        team_name: str,
        membership_type: str,
    ) -> None:
        client.post(
            "/admin/teams/confirm",
            data={
                "public_id": public_id,
                "team_name": team_name,
                "gc_uuid": "",
                "membership_type": membership_type,
                "program_id": "",
                "classification": "",
                "csrf_token": _CSRF,
            },
        )

    def test_member_team_create_inserts_access_for_all_users(self, team_db: Path) -> None:
        """Creating a member team inserts user_team_access rows for every existing user (AC-1)."""
        admin_id = _insert_user(team_db, "admin@example.com")
        coach_id = _insert_user(team_db, "coach@example.com")
        token = _insert_session(team_db, admin_id)

        from src.gamechanger.bridge import BridgeForbiddenError

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            side_effect=BridgeForbiddenError("403"),
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    self._post_new_team(client, "newmember1", "New Member Team", "member")

        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute(
            "SELECT id FROM teams WHERE public_id = ?", ("newmember1",)
        ).fetchone()[0]
        admin_access = conn.execute(
            "SELECT 1 FROM user_team_access WHERE user_id = ? AND team_id = ?",
            (admin_id, team_id),
        ).fetchone()
        coach_access = conn.execute(
            "SELECT 1 FROM user_team_access WHERE user_id = ? AND team_id = ?",
            (coach_id, team_id),
        ).fetchone()
        conn.close()

        assert admin_access is not None, "Admin user should have access to new member team"
        assert coach_access is not None, "Coach user should have access to new member team"

    def test_tracked_team_create_does_not_insert_access(self, team_db: Path) -> None:
        """Creating a tracked team does NOT insert user_team_access rows (AC-3)."""
        admin_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, admin_id)

        from src.gamechanger.bridge import BridgeForbiddenError

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            side_effect=BridgeForbiddenError("403"),
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    self._post_new_team(client, "trackedteam1", "Tracked Opponent", "tracked")

        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute(
            "SELECT id FROM teams WHERE public_id = ?", ("trackedteam1",)
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM user_team_access WHERE team_id = ?", (team_id,)
        ).fetchone()[0]
        conn.close()

        assert count == 0, "Tracked team must not generate user_team_access rows"

    def test_fan_out_is_idempotent(self, team_db: Path) -> None:
        """Duplicate fan-out INSERT for the same (user_id, team_id) is silently ignored (AC-4)."""
        from src.api.routes.admin import _insert_team_new

        # Insert a user and create one member team via the function under test.
        conn = sqlite3.connect(str(team_db))
        conn.execute("PRAGMA foreign_keys=ON;")
        cursor = conn.execute(
            "INSERT INTO users (email, hashed_password) VALUES (?, '')", ("user@example.com",)
        )
        user_id = cursor.lastrowid
        conn.commit()

        with patch.dict("os.environ", {"DATABASE_PATH": str(team_db)}):
            team_id = _insert_team_new("Idempotent Team", "idempotent1", None, "member", None, None)

        # Manually re-run the fan-out INSERT for the same (user_id, team_id).
        # This exercises INSERT OR IGNORE directly: the second attempt must not raise
        # and must leave exactly one row.
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, team_id),
        )
        conn.commit()

        count = conn.execute(
            "SELECT COUNT(*) FROM user_team_access WHERE user_id = ? AND team_id = ?",
            (user_id, team_id),
        ).fetchone()[0]
        conn.close()

        assert count == 1, "INSERT OR IGNORE must keep exactly one access row per user/team"


# ---------------------------------------------------------------------------
# E-143-03: POST /admin/teams/{id}/delete -- delete deactivated zero-data teams
# ---------------------------------------------------------------------------


def _set_team_inactive(db_path: Path, team_id: int) -> None:
    """Set a team's is_active flag to 0."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("UPDATE teams SET is_active = 0 WHERE id = ?", (team_id,))
    conn.commit()
    conn.close()


def _insert_spray_chart_for_team(db_path: Path, team_id: int) -> None:
    """Insert a spray_charts row referencing the given team_id."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO spray_charts (team_id, chart_type) VALUES (?, ?)",
        (team_id, "offensive"),
    )
    conn.commit()
    conn.close()


class TestDeleteTeam:
    """GET+POST /admin/teams/{id}/delete -- two-step confirm/execute flow (E-150-01)."""

    def test_delete_link_shown_for_active_team(self, team_db: Path) -> None:
        """Delete link appears for active teams (AC-8: no deactivation guard)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 200
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()
        # Delete link is always present regardless of active status
        assert f"/admin/teams/{team_id}/delete" in response.text

    def test_delete_link_shown_for_inactive_team(self, team_db: Path) -> None:
        """Delete link appears for inactive teams."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Inactive Opponent", membership_type="tracked")
        _set_team_inactive(team_db, team_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 200
        assert f"/admin/teams/{team_id}/delete" in response.text
        # No JS confirm() dialog -- the GET confirmation page replaces it
        assert "confirm(" not in response.text

    def test_delete_active_team_succeeds(self, team_db: Path) -> None:
        """POST delete proceeds for an active team (AC-8: is_active guard removed)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        conn = sqlite3.connect(str(team_db))
        team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 303
        assert "msg=" in response.headers["location"]
        # Team is deleted
        assert _count_rows(team_db, "teams", "id = ?", (team_id,)) == 0

    def test_delete_team_with_data_removes_row(self, team_db: Path) -> None:
        """POST delete removes a team that has associated data (AC-5: full cascade)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Data Team", membership_type="tracked")
        _insert_spray_chart_for_team(team_db, team_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 303
        assert "msg=" in response.headers["location"]
        assert _count_rows(team_db, "teams", "id = ?", (team_id,)) == 0

    def test_delete_zero_data_team_removes_row(self, team_db: Path) -> None:
        """Successful delete removes the teams row (AC-7: zero-data path still works)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Clean Opponent", membership_type="tracked")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 303
        assert _count_rows(team_db, "teams", "id = ?", (team_id,)) == 0

    def test_delete_success_redirects_with_success_flash(self, team_db: Path) -> None:
        """Successful delete redirects to /admin/teams with a success flash (AC-5)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Gone Team", membership_type="tracked")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 303
        location = response.headers["location"]
        assert location.startswith("/admin/teams")
        assert "msg=" in location
        assert "Gone+Team" in location or "Gone Team" in location.replace("+", " ")

    def test_delete_cleans_up_junction_rows(self, team_db: Path) -> None:
        """Successful delete removes junction/access rows before the teams row (AC-5)."""
        admin_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, admin_id)
        team_id = _insert_team(team_db, "Junction Team", membership_type="tracked")

        # Insert a distinct member team so our_team_id != opponent_team_id
        # (CHECK constraint on team_opponents requires they differ)
        conn = sqlite3.connect(str(team_db))
        conn.execute("PRAGMA foreign_keys=ON;")
        member_id = conn.execute(
            "INSERT INTO teams (name, membership_type) VALUES ('Member Team', 'member') RETURNING id"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (member_id, team_id),
        )
        # Seed a coaching_assignments row
        conn.execute(
            "INSERT INTO coaching_assignments (user_id, team_id) VALUES (?, ?)",
            (admin_id, team_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                client.post(f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF})

        assert _count_rows(team_db, "teams", "id = ?", (team_id,)) == 0
        assert (
            _count_rows(team_db, "team_opponents", "opponent_team_id = ?", (team_id,)) == 0
        )
        assert (
            _count_rows(team_db, "coaching_assignments", "team_id = ?", (team_id,)) == 0
        )

    def test_delete_requires_admin(self, team_db: Path) -> None:
        """Non-admin user gets 403 on POST /admin/teams/{id}/delete (AC-6)."""
        user_id = _insert_user(team_db, "coach@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Secret Team", membership_type="tracked")

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(team_db), "ADMIN_EMAIL": "other@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 403
        # Team must still exist
        assert _count_rows(team_db, "teams", "id = ?", (team_id,)) == 1


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-3, AC-4, AC-5, AC-6: POST /admin/teams/{id}/sync
# ---------------------------------------------------------------------------


def _insert_crawl_job(
    db_path: Path,
    team_id: int,
    sync_type: str = "member_crawl",
    status: str = "running",
    started_at: str = "2026-01-01T10:00:00.000Z",
) -> int:
    """Insert a crawl_jobs row and return its id."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO crawl_jobs (team_id, sync_type, status, started_at) VALUES (?, ?, ?, ?)",
        (team_id, sync_type, status, started_at),
    )
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return job_id


class TestSyncRoute:
    """POST /admin/teams/{id}/sync -- AC-1, AC-2, AC-3, AC-5, AC-6."""

    def test_sync_requires_admin(self, team_db: Path) -> None:
        """Non-admin user gets 403 on POST /admin/teams/{id}/sync (AC-6)."""
        user_id = _insert_user(team_db, "coach@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Hawks Varsity", membership_type="member", public_id="pub1")

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(team_db), "ADMIN_EMAIL": "other@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/sync", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 403

    def test_sync_inactive_team_redirects_with_error(self, team_db: Path) -> None:
        """Inactive teams are rejected with an error flash (AC-3)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Inactive Team", membership_type="member", public_id="pub2")
        _set_team_inactive(team_db, team_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/sync", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 303
        assert "error=" in response.headers["location"]
        assert "inactive" in response.headers["location"].lower()

    def test_sync_unresolved_tracked_redirects_with_error(self, team_db: Path) -> None:
        """Tracked teams with no public_id are rejected with an error flash (AC-3)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        # No public_id -- unresolved tracked team
        team_id = _insert_team(team_db, "Unknown Opponent", membership_type="tracked")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/sync", data={"csrf_token": _CSRF}
                )
        assert response.status_code == 303
        assert "error=" in response.headers["location"]

    def test_sync_active_member_enqueues_task_and_creates_job(self, team_db: Path) -> None:
        """Active member team: crawl_jobs row created with status='running' (AC-1)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "LSB JV", membership_type="member", public_id="pub3")

        with patch("src.api.routes.admin.trigger.run_member_sync") as mock_task, \
             patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/sync", data={"csrf_token": _CSRF}
                )

        assert response.status_code == 303
        assert "msg=" in response.headers["location"]
        assert "Sync+started" in response.headers["location"]

        # A crawl_jobs row should have been created.
        conn = sqlite3.connect(str(team_db))
        conn.execute("PRAGMA foreign_keys=ON;")
        row = conn.execute(
            "SELECT status, sync_type FROM crawl_jobs WHERE team_id = ?", (team_id,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "running"
        assert row[1] == "member_crawl"

        # Background task should have been enqueued with correct team_id.
        mock_task.assert_called_once()
        call_args = mock_task.call_args[0]
        assert call_args[0] == team_id  # team_id

    def test_sync_active_tracked_with_public_id_enqueues_scouting_task(
        self, team_db: Path
    ) -> None:
        """Active tracked team with public_id: scouting pipeline enqueued (AC-2)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(
            team_db, "Rival Hawks", membership_type="tracked", public_id="rival-pub-id"
        )

        with patch("src.api.routes.admin.trigger.run_scouting_sync") as mock_task, \
             patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/sync", data={"csrf_token": _CSRF}
                )

        assert response.status_code == 303
        assert "Sync+started" in response.headers["location"]

        conn = sqlite3.connect(str(team_db))
        conn.execute("PRAGMA foreign_keys=ON;")
        row = conn.execute(
            "SELECT status, sync_type FROM crawl_jobs WHERE team_id = ?", (team_id,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "running"
        assert row[1] == "scouting_crawl"

        mock_task.assert_called_once()
        call_args = mock_task.call_args[0]
        assert call_args[0] == team_id
        assert call_args[1] == "rival-pub-id"  # public_id

    def test_sync_running_job_guard_rejects_duplicate(self, team_db: Path) -> None:
        """Double-submit or direct POST is rejected when a job is already running (server-side guard)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Hawks Varsity", membership_type="member", public_id="pub-guard")
        _insert_crawl_job(team_db, team_id, sync_type="member_crawl", status="running")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                response = client.post(
                    f"/admin/teams/{team_id}/sync", data={"csrf_token": _CSRF}
                )

        assert response.status_code == 303
        location = response.headers["location"]
        assert "error=" in location
        assert "already+in+progress" in location or "already in progress" in location

        # No new crawl_jobs row created -- only the pre-existing one.
        conn = sqlite3.connect(str(team_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM crawl_jobs WHERE team_id = ?", (team_id,)
        ).fetchone()[0]
        conn.close()
        assert count == 1


class TestTeamsSyncDisplay:
    """Last Synced column and status indicators -- AC-4, AC-5."""

    def test_never_synced_shows_never(self, team_db: Path) -> None:
        """Team with no last_synced shows 'Never' in the Last Synced column (AC-4)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        # Seeded team has no last_synced

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert "Never" in response.text

    def test_completed_job_shows_green_badge(self, team_db: Path) -> None:
        """Completed crawl_job shows a green 'done' badge (AC-4)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        # Get the seeded team id.
        conn = sqlite3.connect(str(team_db))
        row = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()
        conn.close()
        team_id = row[0]

        _insert_crawl_job(team_db, team_id, status="completed")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert "bg-green-100" in response.text
        assert "done" in response.text

    def test_failed_job_shows_red_badge(self, team_db: Path) -> None:
        """Failed crawl_job shows a red 'failed' badge (AC-4)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        conn = sqlite3.connect(str(team_db))
        row = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()
        conn.close()
        team_id = row[0]

        _insert_crawl_job(team_db, team_id, status="failed")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert "bg-red-100" in response.text
        assert "failed" in response.text

    def test_running_job_shows_running_badge(self, team_db: Path) -> None:
        """Running crawl_job shows a yellow 'running' badge (AC-4 / AC-5)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        conn = sqlite3.connect(str(team_db))
        row = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()
        conn.close()
        team_id = row[0]

        _insert_crawl_job(team_db, team_id, status="running")

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert "bg-yellow-100" in response.text
        assert "running" in response.text

    def test_unresolved_tracked_shows_map_first_indicator(self, team_db: Path) -> None:
        """Active tracked team without public_id shows 'map first' indicator (AC-3)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        _insert_team(team_db, "Unknown Rival", membership_type="tracked")  # no public_id

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        assert "map first" in response.text.lower()

    def test_sync_button_absent_for_inactive_team(self, team_db: Path) -> None:
        """Inactive teams do not show a Sync button (AC-3)."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)
        team_id = _insert_team(team_db, "Old Team", membership_type="member", public_id="oldpub")
        _set_team_inactive(team_db, team_id)

        with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
            with TestClient(app, cookies={"session": token, "csrf_token": _CSRF}) as client:
                response = client.get("/admin/teams")
        # The /sync action URL for this specific team should not appear.
        assert f"/admin/teams/{team_id}/sync" not in response.text


# ---------------------------------------------------------------------------
# E-147-02: Admin add-team threads season_year through INSERT
# ---------------------------------------------------------------------------


class TestAddTeamSeasonYear:
    """E-147-02: season_year flows through Phase 1 redirect → confirm form → INSERT."""

    def test_confirm_submit_stores_season_year(self, team_db: Path) -> None:
        """POST /admin/teams/confirm with season_year populates teams.season_year."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value="gc-uuid-sy",
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "syteam1",
                            "team_name": "Season Year Team",
                            "gc_uuid": "gc-uuid-sy",
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "season_year": "2026",
                            "csrf_token": _CSRF,
                        },
                    )

        assert response.status_code == 303

        conn = sqlite3.connect(str(team_db))
        row = conn.execute(
            "SELECT season_year FROM teams WHERE public_id = ?", ("syteam1",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 2026

    def test_confirm_submit_season_year_empty_stores_null(self, team_db: Path) -> None:
        """POST /admin/teams/confirm with empty season_year stores NULL."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        with patch(
            "src.api.routes.admin.resolve_public_id_to_uuid",
            return_value="gc-uuid-synull",
        ):
            with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                ) as client:
                    response = client.post(
                        "/admin/teams/confirm",
                        data={
                            "public_id": "syteam2",
                            "team_name": "No Season Year Team",
                            "gc_uuid": "gc-uuid-synull",
                            "membership_type": "tracked",
                            "program_id": "",
                            "classification": "",
                            "season_year": "",
                            "csrf_token": _CSRF,
                        },
                    )

        assert response.status_code == 303

        conn = sqlite3.connect(str(team_db))
        row = conn.execute(
            "SELECT season_year FROM teams WHERE public_id = ?", ("syteam2",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] is None

    def test_phase1_includes_season_year_in_redirect(self, team_db: Path) -> None:
        """Phase 1 redirect includes season_year param when profile.year is set."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        profile = TeamProfile(
            public_id="syredirect1",
            name="Redirect Team",
            sport="baseball",
            year=2026,
        )
        with patch(
            "src.api.routes.admin._parse_url_to_public_id",
            return_value=("syredirect1", None),
        ):
            with patch(
                "src.api.routes.admin._call_bridge",
                return_value=(None, "forbidden"),
            ):
                with patch(
                    "src.api.routes.admin._fetch_public_profile",
                    return_value=profile,
                ):
                    with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                        with TestClient(
                            app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                        ) as client:
                            response = client.post(
                                "/admin/teams",
                                data={
                                    "url_input": "https://web.gc.com/teams/syredirect1",
                                    "csrf_token": _CSRF,
                                },
                            )

        assert response.status_code == 303
        assert "season_year=2026" in response.headers["location"]

    def test_phase1_omits_season_year_when_none(self, team_db: Path) -> None:
        """Phase 1 redirect omits season_year param when profile.year is None."""
        user_id = _insert_user(team_db, "admin@example.com")
        token = _insert_session(team_db, user_id)

        profile = TeamProfile(
            public_id="syredirect2",
            name="No Year Team",
            sport="baseball",
        )
        with patch(
            "src.api.routes.admin._parse_url_to_public_id",
            return_value=("syredirect2", None),
        ):
            with patch(
                "src.api.routes.admin._call_bridge",
                return_value=(None, "forbidden"),
            ):
                with patch(
                    "src.api.routes.admin._fetch_public_profile",
                    return_value=profile,
                ):
                    with patch.dict("os.environ", _admin_env(team_db, "admin@example.com")):
                        with TestClient(
                            app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
                        ) as client:
                            response = client.post(
                                "/admin/teams",
                                data={
                                    "url_input": "https://web.gc.com/teams/syredirect2",
                                    "csrf_token": _CSRF,
                                },
                            )

        assert response.status_code == 303
        assert "season_year" not in response.headers["location"]
