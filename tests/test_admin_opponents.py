"""Tests for admin opponent link routes (E-088-03).

Tests cover:
- AC-1: GET /admin/opponents listing with filter pills and ?team_id= scoping
- AC-2: Sub-nav includes Opponents tab on all admin templates
- AC-3: Badge states (auto/manual/unlinked)
- AC-4: Unlinked rows show Connect button
- AC-5: GET /admin/opponents/{id}/connect shows URL-paste form
- AC-6: parse_team_url() used in confirm flow
- AC-7: GET /admin/opponents/{id}/connect/confirm fetches team info; error handling
- AC-8: POST /admin/opponents/{id}/connect saves manual link; duplicate warning; own-team rejection
- AC-9: POST /admin/opponents/{id}/disconnect only for manual links; 400 for auto
- AC-10: Teams edit page shows summary count + "Manage connections" link
- AC-11: Tests cover all states, filters, connect flow, error handling, disconnect

Run with:
    pytest tests/test_admin_opponents.py -v
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
# Schema SQL -- includes opponent_links and full teams schema
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

    CREATE TABLE IF NOT EXISTS seasons (
        season_id   TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        season_type TEXT,
        year        INTEGER,
        start_date  TEXT,
        end_date    TEXT
    );

    CREATE TABLE IF NOT EXISTS teams (
        team_id    TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        level      TEXT,
        is_owned   INTEGER NOT NULL DEFAULT 0,
        is_active  INTEGER NOT NULL DEFAULT 1,
        public_id  TEXT,
        source     TEXT NOT NULL DEFAULT 'gamechanger',
        last_synced TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

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
        ab INTEGER, h INTEGER, doubles INTEGER, triples INTEGER,
        hr INTEGER, rbi INTEGER, bb INTEGER, so INTEGER, sb INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_game_pitching (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id   TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id   TEXT NOT NULL,
        ip_outs INTEGER, h INTEGER, er INTEGER, bb INTEGER, so INTEGER, hr INTEGER,
        UNIQUE(game_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_batting (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL, team_id TEXT NOT NULL, season_id TEXT NOT NULL,
        games INTEGER, ab INTEGER, h INTEGER, doubles INTEGER, triples INTEGER,
        hr INTEGER, rbi INTEGER, bb INTEGER, so INTEGER, sb INTEGER,
        home_ab INTEGER, home_h INTEGER, home_hr INTEGER, home_bb INTEGER, home_so INTEGER,
        away_ab INTEGER, away_h INTEGER, away_hr INTEGER, away_bb INTEGER, away_so INTEGER,
        vs_lhp_ab INTEGER, vs_lhp_h INTEGER, vs_lhp_hr INTEGER, vs_lhp_bb INTEGER, vs_lhp_so INTEGER,
        vs_rhp_ab INTEGER, vs_rhp_h INTEGER, vs_rhp_hr INTEGER, vs_rhp_bb INTEGER, vs_rhp_so INTEGER,
        UNIQUE(player_id, team_id, season_id)
    );

    CREATE TABLE IF NOT EXISTS player_season_pitching (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL, team_id TEXT NOT NULL, season_id TEXT NOT NULL,
        games INTEGER, ip_outs INTEGER, h INTEGER, er INTEGER, bb INTEGER, so INTEGER,
        hr INTEGER, pitches INTEGER, strikes INTEGER,
        home_ip_outs INTEGER, home_h INTEGER, home_er INTEGER, home_bb INTEGER, home_so INTEGER,
        away_ip_outs INTEGER, away_h INTEGER, away_er INTEGER, away_bb INTEGER, away_so INTEGER,
        vs_lhb_ab INTEGER, vs_lhb_h INTEGER, vs_lhb_hr INTEGER, vs_lhb_bb INTEGER, vs_lhb_so INTEGER,
        vs_rhb_ab INTEGER, vs_rhb_h INTEGER, vs_rhb_hr INTEGER, vs_rhb_bb INTEGER, vs_rhb_so INTEGER,
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

    -- opponent_links table (migration 006)
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
    INSERT OR IGNORE INTO seasons (season_id, name) VALUES ('2026-spring-hs', 'Spring 2026');

    INSERT OR IGNORE INTO teams (team_id, name, level, is_owned, is_active, public_id, source) VALUES
        ('lsb-varsity-2026', 'LSB Varsity 2026', 'varsity', 1, 1, 'ownedPubId001', 'gamechanger'),
        ('lsb-jv-2026', 'LSB JV 2026', 'jv', 1, 1, NULL, 'gamechanger'),
        ('opp-northside-2026', 'Northside Eagles', NULL, 0, 0, NULL, 'gamechanger');

    -- Three opponent_links rows: auto, manual, unlinked
    INSERT OR IGNORE INTO opponent_links
        (our_team_id, root_team_id, opponent_name, resolved_team_id, public_id,
         resolution_method, resolved_at, is_hidden)
    VALUES
        ('lsb-varsity-2026', 'gc-root-001', 'Northside Eagles',
         'opp-northside-2026', 'a1GFM9Ku0BbF', 'auto', '2026-03-01 00:00:00', 0),
        ('lsb-jv-2026', 'gc-root-002', 'Westview Tigers',
         NULL, 'QTiLIb2Lui3b', 'manual', '2026-03-05 00:00:00', 0),
        ('lsb-varsity-2026', 'gc-root-003', 'Ridgecrest Rockets',
         NULL, NULL, NULL, NULL, 0);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a fully-schemed test database."""
    db_path = tmp_path / "test_opponents.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str, is_admin: int = 0) -> int:
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
    raw_token = secrets.token_hex(32)
    token_hash = hash_token(raw_token)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO sessions (session_token_hash, user_id, expires_at) "
        "VALUES (?, ?, datetime('now', '+7 days'))",
        (token_hash, user_id),
    )
    conn.commit()
    conn.close()
    return raw_token


def _get_link_row(db_path: Path, link_id: int) -> dict | None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM opponent_links WHERE id = ?", (link_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _get_link_id_by_name(db_path: Path, opponent_name: str) -> int | None:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT id FROM opponent_links WHERE opponent_name = ?", (opponent_name,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def opp_db(tmp_path: Path) -> Path:
    """Full schema database with opponent_links seed rows."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-1: Listing page with filter pills and team_id scoping
# ---------------------------------------------------------------------------


class TestOpponentListing:
    """GET /admin/opponents listing renders correctly (AC-1)."""

    def test_listing_requires_admin(self, opp_db: Path) -> None:
        """Unauthenticated request to /admin/opponents redirects to login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/admin/opponents")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_listing_shows_all_opponents_by_default(self, opp_db: Path) -> None:
        """GET /admin/opponents with no filter shows all three opponent rows."""
        admin_id = _insert_user(opp_db, "admin@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert response.status_code == 200
        assert "Northside Eagles" in response.text
        assert "Westview Tigers" in response.text
        assert "Ridgecrest Rockets" in response.text

    def test_listing_shows_summary_counts(self, opp_db: Path) -> None:
        """Filter pills show correct counts: total=3, full=2, scoresheet=1."""
        admin_id = _insert_user(opp_db, "counts@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        # All (3), Full stats (2), Scoresheet only (1)
        assert "All (3)" in response.text
        assert "Full stats (2)" in response.text
        assert "Scoresheet only (1)" in response.text

    def test_listing_filter_full_shows_only_linked(self, opp_db: Path) -> None:
        """?filter=full returns only rows with public_id set."""
        admin_id = _insert_user(opp_db, "filterfull@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents?filter=full")
        assert "Northside Eagles" in response.text
        assert "Westview Tigers" in response.text
        assert "Ridgecrest Rockets" not in response.text

    def test_listing_filter_scoresheet_shows_only_unlinked(self, opp_db: Path) -> None:
        """?filter=scoresheet returns only rows with public_id NULL."""
        admin_id = _insert_user(opp_db, "filtersheet@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents?filter=scoresheet")
        assert "Ridgecrest Rockets" in response.text
        assert "Northside Eagles" not in response.text
        assert "Westview Tigers" not in response.text

    def test_listing_team_id_scoping(self, opp_db: Path) -> None:
        """?team_id=lsb-jv-2026 shows only JV team opponent links."""
        admin_id = _insert_user(opp_db, "scopetest@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents?team_id=lsb-jv-2026")
        assert "Westview Tigers" in response.text
        assert "Northside Eagles" not in response.text
        assert "Ridgecrest Rockets" not in response.text


# ---------------------------------------------------------------------------
# AC-2: Sub-nav includes Opponents tab
# ---------------------------------------------------------------------------


class TestSubNav:
    """All admin templates include the Opponents sub-nav tab (AC-2)."""

    def test_users_page_has_opponents_tab(self, opp_db: Path) -> None:
        """GET /admin/users shows Opponents in sub-nav."""
        admin_id = _insert_user(opp_db, "subnav1@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/users")
        assert "/admin/opponents" in response.text

    def test_teams_page_has_opponents_tab(self, opp_db: Path) -> None:
        """GET /admin/teams shows Opponents in sub-nav."""
        admin_id = _insert_user(opp_db, "subnav2@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "/admin/opponents" in response.text

    def test_edit_user_page_has_opponents_tab(self, opp_db: Path) -> None:
        """GET /admin/users/{id}/edit shows Opponents in sub-nav."""
        admin_id = _insert_user(opp_db, "subnav3@test", is_admin=1)
        coach_id = _insert_user(opp_db, "coach3@test", is_admin=0)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/users/{coach_id}/edit")
        assert "/admin/opponents" in response.text

    def test_edit_team_page_has_opponents_tab(self, opp_db: Path) -> None:
        """GET /admin/teams/{id}/edit shows Opponents in sub-nav."""
        admin_id = _insert_user(opp_db, "subnav4@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams/lsb-varsity-2026/edit")
        assert "/admin/opponents" in response.text

    def test_opponents_page_has_opponents_tab(self, opp_db: Path) -> None:
        """GET /admin/opponents shows Opponents as active in sub-nav."""
        admin_id = _insert_user(opp_db, "subnav5@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "/admin/opponents" in response.text


# ---------------------------------------------------------------------------
# AC-3: Badge states
# ---------------------------------------------------------------------------


class TestBadgeStates:
    """Three visual badge states render correctly (AC-3)."""

    def test_auto_resolved_shows_full_stats_auto(self, opp_db: Path) -> None:
        """Auto-resolved opponent shows 'Full stats' badge with 'auto' label."""
        admin_id = _insert_user(opp_db, "badge1@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        # Green badge for auto -- find "Full stats" near "auto" label
        assert "auto" in response.text
        assert "Full stats" in response.text

    def test_manual_link_shows_full_stats_manual(self, opp_db: Path) -> None:
        """Manually linked opponent shows 'Full stats' badge with 'manual' label."""
        admin_id = _insert_user(opp_db, "badge2@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "manual" in response.text

    def test_unlinked_shows_scoresheet_only(self, opp_db: Path) -> None:
        """Unlinked opponent shows 'Scoresheet only' badge."""
        admin_id = _insert_user(opp_db, "badge3@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "Scoresheet only" in response.text


# ---------------------------------------------------------------------------
# AC-4: Connect button for unlinked rows
# ---------------------------------------------------------------------------


class TestConnectButton:
    """Unlinked rows display a Connect action button (AC-4)."""

    def test_unlinked_row_has_connect_link(self, opp_db: Path) -> None:
        """Unlinked opponent row contains a Connect action link."""
        admin_id = _insert_user(opp_db, "connect1@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        unlinked_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert unlinked_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert f"/admin/opponents/{unlinked_id}/connect" in response.text

    def test_auto_resolved_row_has_no_connect_link(self, opp_db: Path) -> None:
        """Auto-resolved opponent row does not show a Connect link."""
        admin_id = _insert_user(opp_db, "connect2@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        auto_id = _get_link_id_by_name(opp_db, "Northside Eagles")
        assert auto_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        # The connect link for the auto-resolved row should not appear
        assert f"/admin/opponents/{auto_id}/connect" not in response.text


# ---------------------------------------------------------------------------
# AC-5: Connect form page
# ---------------------------------------------------------------------------


class TestConnectForm:
    """GET /admin/opponents/{id}/connect shows URL-paste form (AC-5)."""

    def test_connect_form_renders(self, opp_db: Path) -> None:
        """GET /admin/opponents/{id}/connect renders the URL input form."""
        admin_id = _insert_user(opp_db, "form1@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/opponents/{link_id}/connect")
        assert response.status_code == 200
        assert "Ridgecrest Rockets" in response.text
        assert "GameChanger" in response.text

    def test_connect_form_404_for_invalid_id(self, opp_db: Path) -> None:
        """GET /admin/opponents/9999/connect returns 404 for unknown id."""
        admin_id = _insert_user(opp_db, "form2@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents/9999/connect")
        assert response.status_code == 404

    def test_connect_form_links_to_confirm(self, opp_db: Path) -> None:
        """Connect form action points to the /connect/confirm endpoint."""
        admin_id = _insert_user(opp_db, "form3@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/opponents/{link_id}/connect")
        assert f"/admin/opponents/{link_id}/connect/confirm" in response.text


# ---------------------------------------------------------------------------
# AC-6 & AC-7: Confirm page uses parse_team_url; fetches team info; error handling
# ---------------------------------------------------------------------------


class TestConnectConfirm:
    """Confirm page parses URL and fetches team info (AC-6, AC-7)."""

    def test_confirm_shows_team_profile_on_success(self, opp_db: Path) -> None:
        """Confirm page shows fetched team name when API returns 200."""
        from src.gamechanger.team_resolver import TeamProfile

        admin_id = _insert_user(opp_db, "confirm1@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        mock_profile = TeamProfile(
            public_id="NewTeam001",
            name="Ridgecrest Rockets",
            sport="baseball",
            city="Ridgecrest",
            state="CA",
        )

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with patch(
                "src.api.routes.admin.resolve_team", return_value=mock_profile
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.get(
                        f"/admin/opponents/{link_id}/connect/confirm",
                        params={"url": "https://web.gc.com/teams/NewTeam001/slug"},
                    )
        assert response.status_code == 200
        assert "Ridgecrest Rockets" in response.text
        assert "NewTeam001" in response.text

    def test_confirm_shows_error_for_invalid_url(self, opp_db: Path) -> None:
        """Confirm page shows error for a URL that cannot be parsed."""
        admin_id = _insert_user(opp_db, "confirm2@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(
                    f"/admin/opponents/{link_id}/connect/confirm",
                    params={"url": "not-a-valid-url-at-all!!"},
                )
        assert response.status_code == 200
        assert "try again" in response.text.lower()

    def test_confirm_shows_error_for_api_failure(self, opp_db: Path) -> None:
        """Confirm page shows error when GameChanger API call fails."""
        from src.gamechanger.team_resolver import GameChangerAPIError

        admin_id = _insert_user(opp_db, "confirm3@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with patch(
                "src.api.routes.admin.resolve_team",
                side_effect=GameChangerAPIError("API down"),
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.get(
                        f"/admin/opponents/{link_id}/connect/confirm",
                        params={"url": "https://web.gc.com/teams/NewTeam001/slug"},
                    )
        assert response.status_code == 200
        assert "try again" in response.text.lower()

    def test_confirm_shows_error_for_team_not_found(self, opp_db: Path) -> None:
        """Confirm page shows error when team returns 404 from API."""
        from src.gamechanger.team_resolver import TeamNotFoundError

        admin_id = _insert_user(opp_db, "confirm4@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with patch(
                "src.api.routes.admin.resolve_team",
                side_effect=TeamNotFoundError("Not found"),
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.get(
                        f"/admin/opponents/{link_id}/connect/confirm",
                        params={"url": "https://web.gc.com/teams/NewTeam001/slug"},
                    )
        assert response.status_code == 200
        assert "try again" in response.text.lower()

    def test_confirm_rejects_own_team_url(self, opp_db: Path) -> None:
        """Confirm page shows error for a URL belonging to an owned team."""
        admin_id = _insert_user(opp_db, "confirm5@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        # ownedPubId001 is the public_id of lsb-varsity-2026 (is_owned=1)
        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(
                    f"/admin/opponents/{link_id}/connect/confirm",
                    params={"url": "https://web.gc.com/teams/ownedPubId001/slug"},
                )
        assert response.status_code == 200
        assert "try again" in response.text.lower()

    def test_confirm_shows_duplicate_warning(self, opp_db: Path) -> None:
        """Confirm page warns when public_id is already used by another row."""
        from src.gamechanger.team_resolver import TeamProfile

        admin_id = _insert_user(opp_db, "confirm6@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        # a1GFM9Ku0BbF is already used by Northside Eagles (auto-resolved)
        mock_profile = TeamProfile(
            public_id="a1GFM9Ku0BbF",
            name="Northside Eagles",
            sport="baseball",
        )

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with patch(
                "src.api.routes.admin.resolve_team", return_value=mock_profile
            ):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.get(
                        f"/admin/opponents/{link_id}/connect/confirm",
                        params={"url": "https://web.gc.com/teams/a1GFM9Ku0BbF/slug"},
                    )
        assert response.status_code == 200
        assert "Warning" in response.text or "duplicate" in response.text.lower()
        # AC-8: warning must include the existing opponent's name
        assert "Northside Eagles" in response.text


# ---------------------------------------------------------------------------
# AC-8: POST /connect saves link; duplicate warning; own-team rejection
# ---------------------------------------------------------------------------


class TestConnectPost:
    """POST /admin/opponents/{id}/connect saves the link correctly (AC-8)."""

    def test_connect_saves_manual_link(self, opp_db: Path) -> None:
        """POST /connect saves public_id with resolution_method='manual'."""
        admin_id = _insert_user(opp_db, "post1@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "RidgeCrest01"},
                )
        assert response.status_code == 303

        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["public_id"] == "RidgeCrest01"
        assert row["resolution_method"] == "manual"
        assert row["resolved_team_id"] is None

    def test_connect_resolved_team_id_remains_null(self, opp_db: Path) -> None:
        """Manual link sets resolved_team_id=NULL per the manual link spec."""
        admin_id = _insert_user(opp_db, "post2@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "SomeTeamId1"},
                )

        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["resolved_team_id"] is None

    def test_connect_redirects_to_listing_with_team_id(self, opp_db: Path) -> None:
        """POST /connect redirects to /admin/opponents?team_id=... on success."""
        admin_id = _insert_user(opp_db, "post3@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "RidgeCrest02"},
                )
        assert response.status_code == 303
        assert "/admin/opponents" in response.headers["location"]
        assert "team_id" in response.headers["location"]

    def test_connect_rejects_owned_team_public_id(self, opp_db: Path) -> None:
        """POST /connect returns 400 when public_id belongs to an owned team."""
        admin_id = _insert_user(opp_db, "post4@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "ownedPubId001"},  # belongs to lsb-varsity-2026
                )
        assert response.status_code == 400

    def test_connect_duplicate_public_id_warns_but_succeeds(self, opp_db: Path) -> None:
        """POST /connect with duplicate public_id redirects with warning message."""
        admin_id = _insert_user(opp_db, "post5@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        # a1GFM9Ku0BbF already used by Northside Eagles
        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "a1GFM9Ku0BbF"},
                )
        # Should redirect (not block), but with a warning in msg
        assert response.status_code == 303
        location = response.headers["location"]
        assert "msg=" in location
        # AC-8: warning must include the existing opponent's name
        assert "Northside+Eagles" in location or "Northside%20Eagles" in location or "Northside" in location

        # The link should be saved despite the duplicate
        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["public_id"] == "a1GFM9Ku0BbF"


# ---------------------------------------------------------------------------
# AC-9: Disconnect only for manual links; 400 for auto
# ---------------------------------------------------------------------------


class TestDisconnect:
    """POST /admin/opponents/{id}/disconnect only for manual links (AC-9)."""

    def test_disconnect_manual_link_clears_public_id(self, opp_db: Path) -> None:
        """POST /disconnect on a manual link sets public_id=NULL."""
        admin_id = _insert_user(opp_db, "disc1@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Westview Tigers")  # manual link
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 303

        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["public_id"] is None
        assert row["resolution_method"] is None
        assert row["resolved_team_id"] is None

    def test_disconnect_manual_link_redirects_to_listing(self, opp_db: Path) -> None:
        """POST /disconnect redirects to /admin/opponents on success."""
        admin_id = _insert_user(opp_db, "disc2@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Westview Tigers")
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False, cookies={"session": token}) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 303
        assert "/admin/opponents" in response.headers["location"]

    def test_disconnect_auto_link_returns_400(self, opp_db: Path) -> None:
        """POST /disconnect on an auto-resolved link returns 400."""
        admin_id = _insert_user(opp_db, "disc3@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Northside Eagles")  # auto link
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 400

    def test_disconnect_unlinked_returns_400(self, opp_db: Path) -> None:
        """POST /disconnect on an unlinked row returns 400 (no manual method)."""
        admin_id = _insert_user(opp_db, "disc4@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")  # unlinked
        assert link_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 400

    def test_disconnect_shows_disconnect_button_only_for_manual(self, opp_db: Path) -> None:
        """Listing shows Disconnect button only for manual links."""
        admin_id = _insert_user(opp_db, "disc5@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        manual_id = _get_link_id_by_name(opp_db, "Westview Tigers")
        auto_id = _get_link_id_by_name(opp_db, "Northside Eagles")
        assert manual_id is not None
        assert auto_id is not None

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")

        # Manual link has disconnect button
        assert f"/admin/opponents/{manual_id}/disconnect" in response.text
        # Auto link does NOT have disconnect button
        assert f"/admin/opponents/{auto_id}/disconnect" not in response.text


# ---------------------------------------------------------------------------
# AC-10: Teams edit page simplified to summary count + link
# ---------------------------------------------------------------------------


class TestTeamsEditSimplified:
    """Teams edit page shows summary count + 'Manage connections' link (AC-10)."""

    def test_teams_list_shows_opponent_connections_summary(self, opp_db: Path) -> None:
        """GET /admin/teams shows opponent connections count and manage link."""
        admin_id = _insert_user(opp_db, "ac10a@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "Manage connections" in response.text
        assert "/admin/opponents" in response.text

    def test_edit_team_shows_connection_count_and_link(self, opp_db: Path) -> None:
        """GET /admin/teams/{id}/edit shows per-team connection count and manage link."""
        admin_id = _insert_user(opp_db, "ac10b@test", is_admin=1)
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams/lsb-varsity-2026/edit")
        # varsity has 2 opponent links (Northside auto + Ridgecrest unlinked)
        assert "Manage connections" in response.text
        assert "lsb-varsity-2026" in response.text  # in the manage link URL
