# synthetic-test-data
"""Tests for admin team management routes (E-042-03).

Tests cover:
- GET /admin/teams returns 200 for admin, 403 for non-admin, 302 for unauthenticated.
- Team list renders both owned and opponent sections.
- POST /admin/teams with valid URL creates team and redirects.
- POST /admin/teams with invalid URL shows parsing error.
- POST /admin/teams with TeamNotFoundError shows not-found error.
- POST /admin/teams with GameChangerAPIError shows API-unreachable error.
- POST /admin/teams with duplicate non-placeholder team shows already-exists error.
- POST /admin/teams with URL matching an existing discovered placeholder upgrades it.
- Flash messages appear for ?msg= and ?error= params.
- resolve_team is mocked -- no real HTTP calls.

Run with:
    pytest tests/test_admin_teams.py -v
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
from src.gamechanger.team_resolver import (  # noqa: E402
    DiscoveredOpponent,
    GameChangerAPIError,
    TeamNotFoundError,
    TeamProfile,
)

# ---------------------------------------------------------------------------
# Schema SQL (minimal -- includes public_id column from migration 005)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS players (
        player_id  TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name  TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS seasons (
        season_id   TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        season_type TEXT NOT NULL,
        year        INTEGER NOT NULL,
        start_date  TEXT,
        end_date    TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS teams (
        team_id    TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        level      TEXT,
        is_owned   INTEGER NOT NULL DEFAULT 0,
        source     TEXT NOT NULL DEFAULT 'gamechanger',
        is_active  INTEGER NOT NULL DEFAULT 1,
        last_synced TEXT,
        public_id  TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_public_id
        ON teams(public_id) WHERE public_id IS NOT NULL;

    CREATE TABLE IF NOT EXISTS team_rosters (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id       TEXT NOT NULL,
        player_id     TEXT NOT NULL,
        season_id     TEXT NOT NULL,
        jersey_number TEXT,
        position      TEXT,
        UNIQUE(team_id, player_id, season_id)
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id      TEXT PRIMARY KEY,
        season_id    TEXT NOT NULL,
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
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id   TEXT NOT NULL,
        team_id     TEXT NOT NULL,
        season_id   TEXT NOT NULL,
        games       INTEGER,
        ab          INTEGER,
        h           INTEGER,
        doubles     INTEGER,
        triples     INTEGER,
        hr          INTEGER,
        rbi         INTEGER,
        bb          INTEGER,
        so          INTEGER,
        sb          INTEGER,
        UNIQUE(player_id, team_id, season_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_pitching (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id   TEXT NOT NULL,
        team_id     TEXT NOT NULL,
        season_id   TEXT NOT NULL,
        games       INTEGER,
        ip_outs     INTEGER,
        h           INTEGER,
        er          INTEGER,
        bb          INTEGER,
        so          INTEGER,
        hr          INTEGER,
        UNIQUE(player_id, team_id, season_id)
    );

    -- Auth tables
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

    CREATE TABLE IF NOT EXISTS coaching_assignments (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(user_id),
        team_id    TEXT    NOT NULL REFERENCES teams(team_id),
        season_id  TEXT    NOT NULL REFERENCES seasons(season_id),
        role       TEXT    NOT NULL DEFAULT 'assistant',
        created_at TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(user_id, team_id, season_id)
    );

    CREATE TABLE IF NOT EXISTS opponent_links (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        our_team_id         TEXT    NOT NULL REFERENCES teams(team_id),
        root_team_id        TEXT    NOT NULL,
        opponent_name       TEXT    NOT NULL,
        resolved_team_id    TEXT    REFERENCES teams(team_id),
        public_id           TEXT,
        resolution_method   TEXT CHECK (resolution_method IN ('auto', 'manual') OR resolution_method IS NULL),
        resolved_at         TEXT,
        is_hidden           INTEGER NOT NULL DEFAULT 0,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(our_team_id, root_team_id)
    );
"""

_SEED_SQL = """
    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned, source, is_active)
    VALUES
        ('lsb-varsity-2026', 'LSB Varsity 2026', 'varsity', 1, 'gamechanger', 1),
        ('lsb-jv-2026', 'LSB JV 2026', 'jv', 1, 'gamechanger', 1);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed database.

    Args:
        tmp_path: pytest tmp_path fixture.

    Returns:
        Path to the database file.
    """
    db_path = tmp_path / "test_admin_teams.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str, is_admin: int = 0) -> int:
    """Insert a user and return user_id.

    Args:
        db_path: Path to the database.
        email: Email address.
        is_admin: 1 for admin, 0 otherwise.

    Returns:
        New user_id.
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
    """Insert a valid (non-expired) session and return the raw token.

    Args:
        db_path: Path to the database.
        user_id: User to associate the session with.

    Returns:
        Raw session token (64 hex chars).
    """
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO sessions (session_token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, "2099-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()
    return raw_token


def _get_team(db_path: Path, team_id: str) -> dict | None:
    """Fetch a team row by team_id.

    Args:
        db_path: Path to the database.
        team_id: The team_id to look up.

    Returns:
        Dict or None.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def admin_db(tmp_path: Path) -> Path:
    """Database with schema and seed data.

    Args:
        tmp_path: pytest tmp_path fixture.

    Returns:
        Path to the database file.
    """
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------


class TestTeamListAuthGuard:
    """GET /admin/teams access control."""

    def test_admin_gets_200(self, admin_db: Path) -> None:
        """Admin with valid session sees 200."""
        user_id = _insert_user(admin_db, "admin@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 200

    def test_non_admin_gets_403(self, admin_db: Path) -> None:
        """Non-admin authenticated user gets 403."""
        user_id = _insert_user(admin_db, "coach@example.com", is_admin=0)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 403

    def test_unauthenticated_redirects_to_login(self, admin_db: Path) -> None:
        """No session cookie redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


class TestAddTeamAuthGuard:
    """POST /admin/teams access control."""

    def test_non_admin_post_gets_403(self, admin_db: Path) -> None:
        """Non-admin POST gets 403."""
        user_id = _insert_user(admin_db, "nonadmin2@example.com", is_admin=0)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post(
                    "/admin/teams", data={"url_input": "abc123def456", "team_type": "tracked"}
                )
        assert response.status_code == 403

    def test_unauthenticated_post_redirects_to_login(self, admin_db: Path) -> None:
        """No session cookie on POST redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.post(
                    "/admin/teams", data={"url_input": "abc123def456", "team_type": "tracked"}
                )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# Team list display tests
# ---------------------------------------------------------------------------


class TestTeamListDisplay:
    """GET /admin/teams renders owned and opponent sections."""

    def test_page_shows_owned_teams(self, admin_db: Path) -> None:
        """Lincoln Program table contains seeded owned teams."""
        user_id = _insert_user(admin_db, "admin2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert response.status_code == 200
        assert "LSB Varsity 2026" in response.text
        assert "LSB JV 2026" in response.text

    def test_page_shows_lincoln_program_section(self, admin_db: Path) -> None:
        """Page contains 'Lincoln Program' section heading."""
        user_id = _insert_user(admin_db, "admin3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "Lincoln Program" in response.text

    def test_page_shows_opponent_connections_section(self, admin_db: Path) -> None:
        """Page contains 'Opponent Connections' summary section."""
        user_id = _insert_user(admin_db, "admin4@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "Opponent Connections" in response.text or "Manage connections" in response.text

    def test_opponent_section_links_to_opponents_page(self, admin_db: Path) -> None:
        """Opponent connections section links to /admin/opponents."""
        user_id = _insert_user(admin_db, "admin5@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "/admin/opponents" in response.text

    def test_active_team_shows_active_status(self, admin_db: Path) -> None:
        """Active team shows 'Active' in status column."""
        user_id = _insert_user(admin_db, "admin6@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "Active" in response.text

    def test_flash_msg_shows(self, admin_db: Path) -> None:
        """?msg= query param renders as a flash message."""
        user_id = _insert_user(admin_db, "admin7@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams?msg=Team+added+successfully")
        assert "Team added successfully" in response.text

    def test_flash_error_shows(self, admin_db: Path) -> None:
        """?error= query param renders as an error banner."""
        user_id = _insert_user(admin_db, "admin8@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams?error=Something+went+wrong")
        assert "Something went wrong" in response.text

    def test_each_team_has_edit_link(self, admin_db: Path) -> None:
        """Each team row has an Edit link pointing to /admin/teams/{team_id}/edit."""
        user_id = _insert_user(admin_db, "admin9@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "/admin/teams/lsb-varsity-2026/edit" in response.text
        assert "/admin/teams/lsb-jv-2026/edit" in response.text


# ---------------------------------------------------------------------------
# POST /admin/teams -- success and error paths
# ---------------------------------------------------------------------------


_SAMPLE_PROFILE = TeamProfile(
    public_id="abc123def456",
    name="Riverside Tigers",
    sport="baseball",
    city="Riverside",
    state="CA",
)

_SAMPLE_PROFILE_NO_LOCATION = TeamProfile(
    public_id="abc123def456",
    name="Mystery Team",
    sport="baseball",
    city=None,
    state=None,
)


class TestAddTeamSuccess:
    """POST /admin/teams successful team creation."""

    def test_valid_url_creates_team_and_redirects(self, admin_db: Path) -> None:
        """Valid URL resolves team and redirects to /admin/teams with msg."""
        user_id = _insert_user(admin_db, "addteam1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team", return_value=_SAMPLE_PROFILE
            ):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token}
                ) as client:
                    response = client.post(
                        "/admin/teams",
                        data={
                            "url_input": "https://web.gc.com/teams/abc123def456/riverside-tigers",
                            "level": "varsity",
                            "team_type": "tracked",
                        },
                    )
        assert response.status_code == 303
        assert "/admin/teams" in response.headers["location"]
        assert "msg=" in response.headers["location"]

    def test_created_team_is_in_database(self, admin_db: Path) -> None:
        """After successful POST, team row exists in database."""
        user_id = _insert_user(admin_db, "addteam2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team", return_value=_SAMPLE_PROFILE
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    client.post(
                        "/admin/teams",
                        data={
                            "url_input": "abc123def456",
                            "level": "jv",
                            "team_type": "tracked",
                        },
                    )
        team = _get_team(admin_db, "abc123def456")
        assert team is not None
        assert team["name"] == "Riverside Tigers"
        assert team["public_id"] == "abc123def456"
        assert team["is_owned"] == 0
        assert team["is_active"] == 1
        assert team["source"] == "gamechanger"

    def test_owned_team_sets_is_owned_1(self, admin_db: Path) -> None:
        """team_type=owned resolves UUID via reverse bridge and sets is_owned=1."""
        user_id = _insert_user(admin_db, "addteam3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)
        resolved_uuid = "00000000-0000-0000-0000-000000000001"

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch("src.api.routes.admin.resolve_team", return_value=_SAMPLE_PROFILE):
                with patch(
                    "src.api.routes.admin.resolve_public_id_to_uuid",
                    return_value=resolved_uuid,
                ):
                    with TestClient(app, cookies={"session": token}) as client:
                        client.post(
                            "/admin/teams",
                            data={
                                "url_input": "abc123def456",
                                "level": "varsity",
                                "team_type": "owned",
                            },
                        )
        # Owned team: team_id is the resolved UUID, not the public_id slug
        team = _get_team(admin_db, resolved_uuid)
        assert team is not None
        assert team["is_owned"] == 1
        assert team["public_id"] == "abc123def456"

    def test_success_message_includes_location(self, admin_db: Path) -> None:
        """Success redirect URL includes team name and city/state."""
        user_id = _insert_user(admin_db, "addteam4@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team", return_value=_SAMPLE_PROFILE
            ):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token}
                ) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123def456", "team_type": "tracked"},
                    )
        location = response.headers["location"]
        assert "Riverside+Tigers" in location or "Riverside%20Tigers" in location

    def test_success_message_without_location(self, admin_db: Path) -> None:
        """When city/state unavailable, message just shows team name."""
        user_id = _insert_user(admin_db, "addteam5@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team",
                return_value=_SAMPLE_PROFILE_NO_LOCATION,
            ):
                with TestClient(
                    app, follow_redirects=False, cookies={"session": token}
                ) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123def456", "team_type": "tracked"},
                    )
        location = response.headers["location"]
        assert "Mystery" in location


# ---------------------------------------------------------------------------
# POST /admin/teams -- error paths
# ---------------------------------------------------------------------------


class TestAddTeamErrors:
    """POST /admin/teams error handling."""

    def test_invalid_url_shows_parse_error(self, admin_db: Path) -> None:
        """Invalid URL input shows a parsing error message on the page."""
        user_id = _insert_user(admin_db, "erradmin1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(
                    "/admin/teams",
                    data={"url_input": "not-a-valid-url!!!", "team_type": "tracked"},
                )
        assert response.status_code == 200
        assert "error" in response.text.lower() or "invalid" in response.text.lower()

    def test_team_not_found_shows_error(self, admin_db: Path) -> None:
        """TeamNotFoundError shows 'Team not found' error message."""
        user_id = _insert_user(admin_db, "erradmin2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team",
                side_effect=TeamNotFoundError("not found"),
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123def456", "team_type": "tracked"},
                    )
        assert response.status_code == 200
        assert "Team not found on GameChanger" in response.text

    def test_api_error_shows_error(self, admin_db: Path) -> None:
        """GameChangerAPIError shows 'Could not reach' error message."""
        user_id = _insert_user(admin_db, "erradmin3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team",
                side_effect=GameChangerAPIError("timeout"),
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": "abc123def456", "team_type": "tracked"},
                    )
        assert response.status_code == 200
        assert "Could not reach GameChanger API" in response.text

    def test_duplicate_non_placeholder_shows_error(self, admin_db: Path) -> None:
        """Posting a public_id that already exists as a real team shows already-exists error."""
        # Insert an existing real team with public_id matching what would be resolved
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, public_id, is_owned, source, is_active) "
            "VALUES (?, ?, ?, 0, 'gamechanger', 1)",
            ("existingpublicid1", "Existing Team", "existingpublicid1"),
        )
        conn.commit()
        conn.close()

        user_id = _insert_user(admin_db, "erradmin4@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            # resolve_team should NOT be called since duplicate check fires first
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(
                    "/admin/teams",
                    data={"url_input": "existingpublicid1", "team_type": "tracked"},
                )
        assert response.status_code == 200
        assert "already in the system" in response.text


# ---------------------------------------------------------------------------
# POST /admin/teams -- UUID resolution paths (AC-7)
# ---------------------------------------------------------------------------

_OWNED_UUID = "00000000-0000-0000-0000-000000000042"
_OWNED_PUBLIC_ID = "abc123def456"
_OWNED_PROFILE = TeamProfile(
    public_id=_OWNED_PUBLIC_ID,
    name="Riverside Tigers",
    sport="baseball",
    city="Riverside",
    state="CA",
)


class TestUuidResolution:
    """POST /admin/teams UUID resolution for owned teams (AC-7)."""

    def test_owned_team_public_id_input_resolves_uuid_as_team_id(
        self, admin_db: Path
    ) -> None:
        """AC-1: owned team added via public_id slug stores UUID as team_id."""
        user_id = _insert_user(admin_db, "uuid1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch("src.api.routes.admin.resolve_team", return_value=_OWNED_PROFILE):
                with patch(
                    "src.api.routes.admin.resolve_public_id_to_uuid",
                    return_value=_OWNED_UUID,
                ):
                    with TestClient(app, cookies={"session": token}) as client:
                        response = client.post(
                            "/admin/teams",
                            data={
                                "url_input": _OWNED_PUBLIC_ID,
                                "level": "varsity",
                                "team_type": "owned",
                            },
                            follow_redirects=False,
                        )
        assert response.status_code == 303
        team = _get_team(admin_db, _OWNED_UUID)
        assert team is not None
        assert team["team_id"] == _OWNED_UUID
        assert team["public_id"] == _OWNED_PUBLIC_ID
        assert team["is_owned"] == 1

    def test_owned_team_uuid_input_uses_uuid_as_team_id(self, admin_db: Path) -> None:
        """AC-2: owned team added via UUID input stores UUID as team_id."""
        user_id = _insert_user(admin_db, "uuid2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch("src.api.routes.admin.resolve_team", return_value=_OWNED_PROFILE):
                with patch(
                    "src.api.routes.admin.resolve_uuid_to_public_id",
                    return_value=_OWNED_PUBLIC_ID,
                ):
                    with TestClient(app, cookies={"session": token}) as client:
                        response = client.post(
                            "/admin/teams",
                            data={
                                "url_input": _OWNED_UUID,
                                "level": "varsity",
                                "team_type": "owned",
                            },
                            follow_redirects=False,
                        )
        assert response.status_code == 303
        team = _get_team(admin_db, _OWNED_UUID)
        assert team is not None
        assert team["team_id"] == _OWNED_UUID
        assert team["public_id"] == _OWNED_PUBLIC_ID
        assert team["is_owned"] == 1

    def test_non_owned_team_uses_slug_as_team_id(self, admin_db: Path) -> None:
        """AC-3: non-owned (tracked) team stores public_id as team_id, no bridge call."""
        user_id = _insert_user(admin_db, "uuid3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch("src.api.routes.admin.resolve_team", return_value=_OWNED_PROFILE):
                with patch(
                    "src.api.routes.admin.resolve_public_id_to_uuid"
                ) as mock_bridge:
                    with TestClient(app, cookies={"session": token}) as client:
                        response = client.post(
                            "/admin/teams",
                            data={
                                "url_input": _OWNED_PUBLIC_ID,
                                "team_type": "tracked",
                            },
                            follow_redirects=False,
                        )
        assert response.status_code == 303
        # Bridge should NOT be called for non-owned teams
        mock_bridge.assert_not_called()
        team = _get_team(admin_db, _OWNED_PUBLIC_ID)
        assert team is not None
        assert team["team_id"] == _OWNED_PUBLIC_ID
        assert team["public_id"] == _OWNED_PUBLIC_ID
        assert team["is_owned"] == 0

    def test_non_owned_uuid_input_rejected(self, admin_db: Path) -> None:
        """AC-3.5: UUID input for non-owned team shows clear error."""
        user_id = _insert_user(admin_db, "uuid4@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(
                    "/admin/teams",
                    data={"url_input": _OWNED_UUID, "team_type": "tracked"},
                )
        assert response.status_code == 200
        assert "uuid" in response.text.lower() or "non-owned" in response.text.lower()

    def test_owned_reverse_bridge_403_shows_error(self, admin_db: Path) -> None:
        """AC-4: 403 from reverse bridge shows clear 'not on your account' error."""
        from src.gamechanger.bridge import BridgeForbiddenError

        user_id = _insert_user(admin_db, "uuid5@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_public_id_to_uuid",
                side_effect=BridgeForbiddenError("403 Forbidden"),
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": _OWNED_PUBLIC_ID, "team_type": "owned"},
                    )
        assert response.status_code == 200
        assert "not found" in response.text.lower() or "account" in response.text.lower()

    def test_owned_uuid_duplicate_check_by_team_id(self, admin_db: Path) -> None:
        """AC-5: re-adding owned team (UUID already in team_id) shows already-exists error."""
        # Pre-insert the owned team with UUID as team_id
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, public_id, is_owned, source, is_active) "
            "VALUES (?, ?, ?, 1, 'gamechanger', 1)",
            (_OWNED_UUID, "Riverside Tigers", _OWNED_PUBLIC_ID),
        )
        conn.commit()
        conn.close()

        user_id = _insert_user(admin_db, "uuid6@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_public_id_to_uuid",
                return_value=_OWNED_UUID,
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.post(
                        "/admin/teams",
                        data={"url_input": _OWNED_PUBLIC_ID, "team_type": "owned"},
                    )
        assert response.status_code == 200
        assert "already in the system" in response.text


# ---------------------------------------------------------------------------
# POST /admin/teams -- placeholder upgrade path
# ---------------------------------------------------------------------------


class TestPlaceholderUpgrade:
    """POST /admin/teams upgrades a discovered placeholder instead of creating a duplicate."""

    def test_placeholder_is_upgraded_not_duplicated(self, admin_db: Path) -> None:
        """When a discovered placeholder matches resolved name, it is upgraded in place."""
        # Insert a discovered placeholder
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, is_owned, source, is_active, public_id) "
            "VALUES (?, ?, 0, 'discovered', 0, NULL)",
            ("old-placeholder-id", "Riverside Tigers"),
        )
        conn.commit()
        conn.close()

        user_id = _insert_user(admin_db, "upgrade1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team", return_value=_SAMPLE_PROFILE
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    client.post(
                        "/admin/teams",
                        data={"url_input": "abc123def456", "team_type": "tracked"},
                    )

        # The old placeholder row should no longer exist with old team_id
        old_row = _get_team(admin_db, "old-placeholder-id")
        assert old_row is None, "Old placeholder row should be gone after upgrade"

        # The new team_id (public_id) row should exist
        new_row = _get_team(admin_db, "abc123def456")
        assert new_row is not None
        assert new_row["public_id"] == "abc123def456"
        assert new_row["source"] == "gamechanger"
        assert new_row["is_active"] == 1
        assert new_row["name"] == "Riverside Tigers"

    def test_placeholder_upgrade_no_duplicate_rows(self, admin_db: Path) -> None:
        """After upgrade, only one team row exists for the team name."""
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, is_owned, source, is_active, public_id) "
            "VALUES (?, ?, 0, 'discovered', 0, NULL)",
            ("placeholder-two", "Riverside Tigers"),
        )
        conn.commit()
        conn.close()

        user_id = _insert_user(admin_db, "upgrade2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with patch(
                "src.api.routes.admin.resolve_team", return_value=_SAMPLE_PROFILE
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    client.post(
                        "/admin/teams",
                        data={"url_input": "abc123def456", "team_type": "tracked"},
                    )

        conn = sqlite3.connect(str(admin_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM teams WHERE LOWER(name) = 'riverside tigers'"
        ).fetchone()[0]
        conn.close()
        assert count == 1, f"Expected 1 row for Riverside Tigers, got {count}"


# ---------------------------------------------------------------------------
# GET /admin/teams/{team_id}/edit -- edit team form (E-042-04)
# ---------------------------------------------------------------------------


class TestEditTeamForm:
    """GET /admin/teams/{team_id}/edit access, rendering, and 404 handling."""

    def test_admin_gets_200_for_existing_team(self, admin_db: Path) -> None:
        """Admin with valid session can access the edit form for an existing team."""
        user_id = _insert_user(admin_db, "editteam1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams/lsb-varsity-2026/edit")
        assert response.status_code == 200

    def test_form_prefilled_with_team_name(self, admin_db: Path) -> None:
        """Edit form contains the team's current name as a pre-filled value."""
        user_id = _insert_user(admin_db, "editteam2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams/lsb-varsity-2026/edit")
        assert "LSB Varsity 2026" in response.text

    def test_form_shows_level_and_status(self, admin_db: Path) -> None:
        """Edit form shows current level and Active/Inactive status."""
        user_id = _insert_user(admin_db, "editteam3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams/lsb-varsity-2026/edit")
        # level "varsity" should appear as selected option in form
        assert "varsity" in response.text
        # Status should show Active (seeded with is_active=1)
        assert "Active" in response.text

    def test_nonexistent_team_returns_404(self, admin_db: Path) -> None:
        """AC-4: GET edit for a nonexistent team_id returns 404."""
        user_id = _insert_user(admin_db, "editteam4@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams/does-not-exist/edit")
        assert response.status_code == 404

    def test_non_admin_gets_403(self, admin_db: Path) -> None:
        """AC-3: non-admin gets 403 on edit form."""
        user_id = _insert_user(admin_db, "editteam5@example.com", is_admin=0)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.get("/admin/teams/lsb-varsity-2026/edit")
        assert response.status_code == 403

    def test_unauthenticated_redirects_to_login(self, admin_db: Path) -> None:
        """AC-3: unauthenticated request redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/admin/teams/lsb-varsity-2026/edit")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# POST /admin/teams/{team_id}/edit -- update team (E-042-04)
# ---------------------------------------------------------------------------


class TestUpdateTeam:
    """POST /admin/teams/{team_id}/edit updates team and redirects."""

    def test_post_edit_updates_name_and_redirects(self, admin_db: Path) -> None:
        """AC-5, AC-6: POST updates name and redirects to /admin/teams?msg=Team+updated."""
        user_id = _insert_user(admin_db, "updateteam1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    "/admin/teams/lsb-varsity-2026/edit",
                    data={"name": "LSB Varsity Updated", "level": "varsity", "team_type": "owned"},
                )
        assert response.status_code == 303
        assert "/admin/teams" in response.headers["location"]
        assert "msg=Team+updated" in response.headers["location"]

    def test_post_edit_persists_changes(self, admin_db: Path) -> None:
        """AC-5: updated name, level, and is_owned are saved to the database."""
        user_id = _insert_user(admin_db, "updateteam2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                client.post(
                    "/admin/teams/lsb-jv-2026/edit",
                    data={"name": "LSB JV Renamed", "level": "jv", "team_type": "tracked"},
                )

        team = _get_team(admin_db, "lsb-jv-2026")
        assert team is not None
        assert team["name"] == "LSB JV Renamed"
        assert team["is_owned"] == 0

    def test_post_edit_nonexistent_team_returns_404(self, admin_db: Path) -> None:
        """AC-5: POST to nonexistent team returns 404."""
        user_id = _insert_user(admin_db, "updateteam3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(
                    "/admin/teams/no-such-team/edit",
                    data={"name": "Ghost Team", "level": "", "team_type": "tracked"},
                )
        assert response.status_code == 404

    def test_post_edit_non_admin_gets_403(self, admin_db: Path) -> None:
        """AC-7: non-admin POST gets 403."""
        user_id = _insert_user(admin_db, "updateteam4@example.com", is_admin=0)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    "/admin/teams/lsb-varsity-2026/edit",
                    data={"name": "Hacked", "level": "", "team_type": "tracked"},
                )
        assert response.status_code == 403

    def test_post_edit_unauthenticated_redirects(self, admin_db: Path) -> None:
        """AC-7: unauthenticated POST redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.post(
                    "/admin/teams/lsb-varsity-2026/edit",
                    data={"name": "Hacked", "level": "", "team_type": "tracked"},
                )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# POST /admin/teams/{team_id}/toggle-active -- toggle is_active (E-042-04)
# ---------------------------------------------------------------------------


class TestToggleTeamActive:
    """POST /admin/teams/{team_id}/toggle-active flips is_active and redirects."""

    def test_toggle_deactivates_active_team(self, admin_db: Path) -> None:
        """AC-8, AC-9: toggling an active team deactivates it and redirects with 'deactivated'."""
        user_id = _insert_user(admin_db, "toggle1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        # lsb-varsity-2026 is seeded as active
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post("/admin/teams/lsb-varsity-2026/toggle-active")

        assert response.status_code == 303
        assert "/admin/teams" in response.headers["location"]
        assert "deactivated" in response.headers["location"]

        team = _get_team(admin_db, "lsb-varsity-2026")
        assert team is not None
        assert team["is_active"] == 0

    def test_toggle_activates_inactive_team(self, admin_db: Path) -> None:
        """AC-8, AC-9: toggling an inactive team activates it and redirects with 'activated'."""
        # Insert an inactive team
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, is_owned, source, is_active) "
            "VALUES ('inactive-team-1', 'Inactive Team', 0, 'gamechanger', 0)"
        )
        conn.commit()
        conn.close()

        user_id = _insert_user(admin_db, "toggle2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post("/admin/teams/inactive-team-1/toggle-active")

        assert response.status_code == 303
        assert "activated" in response.headers["location"]

        team = _get_team(admin_db, "inactive-team-1")
        assert team is not None
        assert team["is_active"] == 1

    def test_toggle_nonexistent_team_returns_404(self, admin_db: Path) -> None:
        """Toggle on nonexistent team_id returns 404."""
        user_id = _insert_user(admin_db, "toggle3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post("/admin/teams/no-such-team/toggle-active")
        assert response.status_code == 404

    def test_toggle_non_admin_gets_403(self, admin_db: Path) -> None:
        """AC-10: non-admin POST gets 403."""
        user_id = _insert_user(admin_db, "toggle4@example.com", is_admin=0)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post("/admin/teams/lsb-varsity-2026/toggle-active")
        assert response.status_code == 403

    def test_toggle_unauthenticated_redirects(self, admin_db: Path) -> None:
        """AC-10: unauthenticated POST redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.post("/admin/teams/lsb-varsity-2026/toggle-active")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# Team list -- activate/deactivate buttons (E-042-04 AC-11)
# ---------------------------------------------------------------------------


class TestTeamListToggleButtons:
    """AC-11: teams list shows Activate/Deactivate buttons per row."""

    def test_active_team_shows_deactivate_button(self, admin_db: Path) -> None:
        """Active teams show a Deactivate button linking to toggle endpoint."""
        user_id = _insert_user(admin_db, "togglebtn1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "Deactivate" in response.text
        assert "/admin/teams/lsb-varsity-2026/toggle-active" in response.text

    def test_inactive_team_shows_activate_button(self, admin_db: Path) -> None:
        """Inactive teams show an Activate button."""
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, is_owned, source, is_active) "
            "VALUES ('sleeping-team', 'Sleeping Team', 1, 'gamechanger', 0)"
        )
        conn.commit()
        conn.close()

        user_id = _insert_user(admin_db, "togglebtn2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "Activate" in response.text
        assert "/admin/teams/sleeping-team/toggle-active" in response.text


# ---------------------------------------------------------------------------
# POST /admin/teams/{team_id}/discover-opponents (E-042-05)
# ---------------------------------------------------------------------------


_DISCOVER_GAMES_RESPONSE = [
    {"id": "g1", "opponent_team": {"name": "Riverside Tigers"}},
    {"id": "g2", "opponent_team": {"name": "Jr Bluejays 15U"}},
    {"id": "g3", "opponent_team": {"name": "Riverside Tigers"}},  # duplicate
]


def _insert_team_with_public_id(db_path: Path, team_id: str, name: str, public_id: str) -> None:
    """Insert an owned active team with a public_id.

    Args:
        db_path: Path to the database.
        team_id: Team primary key.
        name: Team display name.
        public_id: GameChanger public_id slug.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO teams (team_id, name, is_owned, source, is_active, public_id) "
        "VALUES (?, ?, 1, 'gamechanger', 1, ?)",
        (team_id, name, public_id),
    )
    conn.commit()
    conn.close()


class TestDiscoverOpponentsRoute:
    """AC-8 through AC-12: POST /admin/teams/{team_id}/discover-opponents."""

    def test_creates_new_opponent_rows(self, admin_db: Path) -> None:
        """AC-9: newly discovered opponents are inserted as placeholder rows."""
        _insert_team_with_public_id(admin_db, "lsb-varsity-pub", "LSB Varsity", "abc123pub")
        user_id = _insert_user(admin_db, "disc1@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch(
            "src.api.routes.admin.discover_opponents",
            return_value=[
                DiscoveredOpponent(name="Riverside Tigers"),
                DiscoveredOpponent(name="Jr Bluejays 15U"),
            ],
        ):
            with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
                with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                    response = client.post("/admin/teams/lsb-varsity-pub/discover-opponents")

        assert response.status_code == 303

        conn = sqlite3.connect(str(admin_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM teams WHERE source = 'discovered'"
        ).fetchall()
        conn.close()
        names = {r["name"] for r in rows}
        assert "Riverside Tigers" in names
        assert "Jr Bluejays 15U" in names

    def test_skips_existing_team_by_name(self, admin_db: Path) -> None:
        """AC-10: opponents already in DB (by case-insensitive name) are not duplicated."""
        _insert_team_with_public_id(admin_db, "lsb-varsity-pub2", "LSB Varsity 2", "abc456pub")
        # Pre-insert one opponent
        conn = sqlite3.connect(str(admin_db))
        conn.execute(
            "INSERT INTO teams (team_id, name, is_owned, source, is_active) "
            "VALUES ('existing-opp', 'Riverside Tigers', 0, 'gamechanger', 0)"
        )
        conn.commit()
        conn.close()

        user_id = _insert_user(admin_db, "disc2@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch(
            "src.api.routes.admin.discover_opponents",
            return_value=[
                DiscoveredOpponent(name="Riverside Tigers"),  # already exists
                DiscoveredOpponent(name="New Opponent FC"),   # new
            ],
        ):
            with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
                with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                    client.post("/admin/teams/lsb-varsity-pub2/discover-opponents")

        conn = sqlite3.connect(str(admin_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM teams WHERE LOWER(name) = 'riverside tigers'"
        ).fetchone()[0]
        conn.close()
        assert count == 1  # no duplicate

    def test_redirect_message_shows_correct_count(self, admin_db: Path) -> None:
        """AC-11: redirect URL contains count of newly added opponents."""
        _insert_team_with_public_id(admin_db, "lsb-varsity-pub3", "LSB Varsity 3", "abc789pub")
        user_id = _insert_user(admin_db, "disc3@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch(
            "src.api.routes.admin.discover_opponents",
            return_value=[
                DiscoveredOpponent(name="Team Alpha"),
                DiscoveredOpponent(name="Team Beta"),
            ],
        ):
            with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
                with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                    response = client.post("/admin/teams/lsb-varsity-pub3/discover-opponents")

        assert "2" in response.headers["location"]
        assert "Discovered" in response.headers["location"]

    def test_no_public_id_redirects_with_error(self, admin_db: Path) -> None:
        """AC-12: team without public_id redirects with an error message."""
        user_id = _insert_user(admin_db, "disc4@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                # lsb-varsity-2026 has no public_id in seed data
                response = client.post("/admin/teams/lsb-varsity-2026/discover-opponents")

        assert response.status_code == 303
        assert "error" in response.headers["location"]
        assert "no+public+ID" in response.headers["location"] or "public+ID" in response.headers["location"]

    def test_non_admin_gets_403(self, admin_db: Path) -> None:
        """AC-13: non-admin POST gets 403."""
        _insert_team_with_public_id(admin_db, "lsb-varsity-pub4", "LSB Varsity 4", "abcdefpub")
        user_id = _insert_user(admin_db, "disc5@example.com", is_admin=0)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post("/admin/teams/lsb-varsity-pub4/discover-opponents")

        assert response.status_code == 403

    def test_unauthenticated_redirects_to_login(self, admin_db: Path) -> None:
        """AC-13: unauthenticated POST redirects to /auth/login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.post("/admin/teams/lsb-varsity-2026/discover-opponents")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_api_error_redirects_with_error_message(self, admin_db: Path) -> None:
        """API error redirects with an appropriate error flash message."""
        _insert_team_with_public_id(admin_db, "lsb-varsity-pub5", "LSB Varsity 5", "abcxyzpub")
        user_id = _insert_user(admin_db, "disc6@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch(
            "src.api.routes.admin.discover_opponents",
            side_effect=GameChangerAPIError("timeout"),
        ):
            with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db), "DEV_USER_EMAIL": ""}):
                with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                    response = client.post("/admin/teams/lsb-varsity-pub5/discover-opponents")

        assert response.status_code == 303
        assert "error" in response.headers["location"]


# ---------------------------------------------------------------------------
# Discover Opponents button in team list (E-042-05 AC-7)
# ---------------------------------------------------------------------------


class TestDiscoverOpponentsButton:
    """AC-7: Discover Opponents button appears for active teams with public_id."""

    def test_discover_button_shown_for_active_team_with_public_id(self, admin_db: Path) -> None:
        """Active team with public_id gets a Discover Opponents button."""
        _insert_team_with_public_id(admin_db, "lsb-btn-test", "LSB Button Test", "btnpub123")
        user_id = _insert_user(admin_db, "disc7@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")

        assert "discover-opponents" in response.text
        assert "Discover Opponents" in response.text

    def test_discover_button_hidden_for_team_without_public_id(self, admin_db: Path) -> None:
        """Active team without public_id does NOT show Discover Opponents button."""
        user_id = _insert_user(admin_db, "disc8@example.com", is_admin=1)
        token = _insert_session(admin_db, user_id)

        # lsb-varsity-2026 from seed has no public_id
        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")

        # Button should NOT appear for the seed teams (no public_id)
        assert "discover-opponents" not in response.text


# ---------------------------------------------------------------------------
# bulk_create_opponents -- long-name collision safety (Fix P1-2)
# ---------------------------------------------------------------------------


class TestBulkCreateOpponentsLongName:
    """Verify team_id generation is collision-safe for very long opponent names."""

    def _call_bulk_create(self, admin_db: Path, names: list[str]) -> int:
        from src.api.db import bulk_create_opponents

        with patch.dict("os.environ", {"DATABASE_PATH": str(admin_db)}):
            return bulk_create_opponents(names)

    def test_long_name_team_id_within_50_chars(self, admin_db: Path) -> None:
        """team_id generated for a 60-char name must be <= 50 chars."""
        long_name = "A" * 60 + " Baseball Club"
        count = self._call_bulk_create(admin_db, [long_name])
        assert count == 1

        conn = sqlite3.connect(str(admin_db))
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name = ?", (long_name,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert len(row[0]) <= 50

    def test_long_name_suffix_preserved(self, admin_db: Path) -> None:
        """The 6-char hex suffix must not be truncated for long names."""
        long_name = "B" * 70 + " Sports Academy"
        count = self._call_bulk_create(admin_db, [long_name])
        assert count == 1

        conn = sqlite3.connect(str(admin_db))
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name = ?", (long_name,)
        ).fetchone()
        conn.close()
        assert row is not None
        team_id = row[0]
        # Suffix is the last 6 chars after the final "-"
        parts = team_id.rsplit("-", 1)
        assert len(parts) == 2
        suffix = parts[1]
        assert len(suffix) == 6
        assert all(c in "0123456789abcdef" for c in suffix)

    def test_two_long_names_with_same_prefix_dont_collide(self, admin_db: Path) -> None:
        """Two names that produce the same slug prefix get distinct team_ids."""
        # Both names start with 50+ identical chars; only differ at the end
        prefix = "C" * 55
        name_a = prefix + " Tigers"
        name_b = prefix + " Eagles"
        count = self._call_bulk_create(admin_db, [name_a, name_b])
        assert count == 2

        conn = sqlite3.connect(str(admin_db))
        rows = conn.execute(
            "SELECT team_id FROM teams WHERE name IN (?, ?)", (name_a, name_b)
        ).fetchall()
        conn.close()
        ids = [r[0] for r in rows]
        assert len(ids) == 2
        assert ids[0] != ids[1]
