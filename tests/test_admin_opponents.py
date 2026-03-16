# synthetic-test-data
"""Tests for admin opponent link routes -- updated for E-100-04.

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
- E-091-01: Guard connect endpoint against overwriting resolved links
- E-091-03: Duplicate public_id check scoped to our_team_id

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
# Schema SQL -- E-100 fresh-start schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS _migrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        filename   TEXT    NOT NULL UNIQUE,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    INSERT OR IGNORE INTO _migrations (filename) VALUES ('001_initial_schema.sql');

    CREATE TABLE IF NOT EXISTS programs (
        program_id   TEXT PRIMARY KEY,
        name         TEXT NOT NULL,
        program_type TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS teams (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        program_id      TEXT REFERENCES programs(program_id),
        membership_type TEXT NOT NULL DEFAULT 'tracked',
        classification  TEXT,
        public_id       TEXT,
        gc_uuid         TEXT,
        source          TEXT NOT NULL DEFAULT 'gamechanger',
        is_active       INTEGER NOT NULL DEFAULT 1,
        last_synced     TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        email           TEXT UNIQUE NOT NULL,
        hashed_password TEXT,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_team_access (
        user_id INTEGER NOT NULL REFERENCES users(id),
        team_id INTEGER NOT NULL REFERENCES teams(id),
        UNIQUE(user_id, team_id)
    );

    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        expires_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS opponent_links (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        our_team_id       INTEGER NOT NULL REFERENCES teams(id),
        root_team_id      TEXT NOT NULL,
        opponent_name     TEXT NOT NULL,
        resolved_team_id  INTEGER REFERENCES teams(id),
        public_id         TEXT,
        resolution_method TEXT CHECK(resolution_method IN ('auto', 'manual') OR resolution_method IS NULL),
        resolved_at       TEXT,
        is_hidden         INTEGER NOT NULL DEFAULT 0,
        created_at        TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(our_team_id, root_team_id)
    );
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    """Create a seeded test database.

    Returns:
        Tuple of (db_path, team_ids) where team_ids maps name to INTEGER id.
    """
    db_path = tmp_path / "test_opponents.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)

    # Seed programs
    conn.execute(
        "INSERT OR IGNORE INTO programs (program_id, name, program_type) "
        "VALUES ('lsb-hs', 'Lincoln Standing Bear HS', 'hs')"
    )

    # Seed teams with INTEGER PKs
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, source, is_active) "
        "VALUES ('LSB Varsity 2026', 'member', 'ownedPubId001', 'gamechanger', 1)"
    )
    varsity_id = cur.lastrowid

    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id, source, is_active) "
        "VALUES ('LSB JV 2026', 'member', NULL, 'gamechanger', 1)"
    )
    jv_id = cur.lastrowid

    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, source, is_active) "
        "VALUES ('Northside Eagles', 'tracked', 'gamechanger', 0)"
    )
    northside_id = cur.lastrowid

    # Three opponent_links rows: auto, manual, unlinked
    conn.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id,
             public_id, resolution_method, resolved_at, is_hidden)
        VALUES (?, 'gc-root-001', 'Northside Eagles', ?, 'a1GFM9Ku0BbF', 'auto',
                '2026-03-01 00:00:00', 0)
        """,
        (varsity_id, northside_id),
    )
    conn.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id,
             public_id, resolution_method, resolved_at, is_hidden)
        VALUES (?, 'gc-root-002', 'Westview Tigers', NULL, 'QTiLIb2Lui3b', 'manual',
                '2026-03-05 00:00:00', 0)
        """,
        (jv_id,),
    )
    conn.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id,
             public_id, resolution_method, resolved_at, is_hidden)
        VALUES (?, 'gc-root-003', 'Ridgecrest Rockets', NULL, NULL, NULL, NULL, 0)
        """,
        (varsity_id,),
    )

    conn.commit()
    conn.close()

    team_ids = {
        "varsity": varsity_id,
        "jv": jv_id,
        "northside": northside_id,
    }
    return db_path, team_ids


def _insert_user(db_path: Path, email: str) -> int:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, '')", (email,)
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
        "INSERT INTO sessions (session_id, user_id, expires_at) "
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


def _insert_opponent_link(
    db_path: Path,
    our_team_id: int,
    root_team_id: str,
    opponent_name: str,
    public_id: str | None = None,
    resolution_method: str | None = None,
) -> int:
    """Insert an opponent_links row and return its id."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO opponent_links"
        " (our_team_id, root_team_id, opponent_name, public_id, resolution_method)"
        " VALUES (?, ?, ?, ?, ?)",
        (our_team_id, root_team_id, opponent_name, public_id, resolution_method),
    )
    conn.commit()
    link_id = cursor.lastrowid
    conn.close()
    return link_id


def _admin_env(db_path: Path, admin_email: str) -> dict[str, str]:
    return {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": admin_email}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def opp_db(tmp_path: Path) -> Path:
    """Full schema database with opponent_links seed rows."""
    db_path, _ = _make_db(tmp_path)
    return db_path


@pytest.fixture()
def opp_db_with_ids(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    """Full schema database with team integer IDs returned."""
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-1: Listing page with filter pills and team_id scoping
# ---------------------------------------------------------------------------


class TestOpponentListing:
    """GET /admin/opponents listing renders correctly (AC-1)."""

    def test_listing_requires_auth(self, opp_db: Path) -> None:
        """Unauthenticated request to /admin/opponents redirects to login."""
        with patch.dict("os.environ", {"DATABASE_PATH": str(opp_db)}):
            with TestClient(app, follow_redirects=False) as client:
                response = client.get("/admin/opponents")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_listing_shows_all_opponents_by_default(self, opp_db: Path) -> None:
        """GET /admin/opponents with no filter shows all three opponent rows."""
        admin_id = _insert_user(opp_db, "admin@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "admin@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert response.status_code == 200
        assert "Northside Eagles" in response.text
        assert "Westview Tigers" in response.text
        assert "Ridgecrest Rockets" in response.text

    def test_listing_shows_summary_counts(self, opp_db: Path) -> None:
        """Filter pills show correct counts: total=3, full=2, scoresheet=1."""
        admin_id = _insert_user(opp_db, "counts@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "counts@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "All (3)" in response.text
        assert "Full stats (2)" in response.text
        assert "Scoresheet only (1)" in response.text

    def test_listing_filter_full_shows_only_linked(self, opp_db: Path) -> None:
        """?filter=full returns only rows with public_id set."""
        admin_id = _insert_user(opp_db, "filterfull@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "filterfull@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents?filter=full")
        assert "Northside Eagles" in response.text
        assert "Westview Tigers" in response.text
        assert "Ridgecrest Rockets" not in response.text

    def test_listing_filter_scoresheet_shows_only_unlinked(self, opp_db: Path) -> None:
        """?filter=scoresheet returns only rows with public_id NULL."""
        admin_id = _insert_user(opp_db, "filtersheet@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "filtersheet@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents?filter=scoresheet")
        assert "Ridgecrest Rockets" in response.text
        assert "Northside Eagles" not in response.text
        assert "Westview Tigers" not in response.text

    def test_listing_team_id_scoping(self, opp_db_with_ids: tuple) -> None:
        """?team_id=<int> shows only that team's opponent links."""
        opp_db, team_ids = opp_db_with_ids
        jv_id = team_ids["jv"]
        admin_id = _insert_user(opp_db, "scopetest@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "scopetest@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/opponents?team_id={jv_id}")
        assert "Westview Tigers" in response.text
        assert "Northside Eagles" not in response.text
        assert "Ridgecrest Rockets" not in response.text


# ---------------------------------------------------------------------------
# AC-2: Sub-nav includes Opponents tab
# ---------------------------------------------------------------------------


class TestSubNav:
    """All admin templates include the Opponents sub-nav tab (AC-2)."""

    def test_users_page_has_opponents_tab(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "subnav1@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "subnav1@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/users")
        assert "/admin/opponents" in response.text

    def test_teams_page_has_opponents_tab(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "subnav2@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "subnav2@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "/admin/opponents" in response.text

    def test_edit_user_page_has_opponents_tab(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "subnav3@test.com")
        coach_id = _insert_user(opp_db, "coach3@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "subnav3@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/users/{coach_id}/edit")
        assert "/admin/opponents" in response.text

    def test_edit_team_page_has_opponents_tab(self, opp_db_with_ids: tuple) -> None:
        opp_db, team_ids = opp_db_with_ids
        varsity_id = team_ids["varsity"]
        admin_id = _insert_user(opp_db, "subnav4@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "subnav4@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/teams/{varsity_id}/edit")
        assert "/admin/opponents" in response.text

    def test_opponents_page_has_opponents_tab(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "subnav5@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "subnav5@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "/admin/opponents" in response.text


# ---------------------------------------------------------------------------
# AC-3: Badge states
# ---------------------------------------------------------------------------


class TestBadgeStates:
    """Three visual badge states render correctly (AC-3)."""

    def test_auto_resolved_shows_full_stats_auto(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "badge1@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "badge1@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "auto" in response.text
        assert "Full stats" in response.text

    def test_manual_link_shows_full_stats_manual(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "badge2@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "badge2@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "manual" in response.text

    def test_unlinked_shows_scoresheet_only(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "badge3@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "badge3@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert "Scoresheet only" in response.text


# ---------------------------------------------------------------------------
# AC-4: Connect button for unlinked rows
# ---------------------------------------------------------------------------


class TestConnectButton:
    """Unlinked rows display a Connect action button (AC-4)."""

    def test_unlinked_row_has_connect_link(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "connect1@test.com")
        token = _insert_session(opp_db, admin_id)
        unlinked_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert unlinked_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "connect1@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert f"/admin/opponents/{unlinked_id}/connect" in response.text

    def test_auto_resolved_row_has_no_connect_link(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "connect2@test.com")
        token = _insert_session(opp_db, admin_id)
        auto_id = _get_link_id_by_name(opp_db, "Northside Eagles")
        assert auto_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "connect2@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")
        assert f"/admin/opponents/{auto_id}/connect" not in response.text


# ---------------------------------------------------------------------------
# AC-5: Connect form page
# ---------------------------------------------------------------------------


class TestConnectForm:
    """GET /admin/opponents/{id}/connect shows URL-paste form (AC-5)."""

    def test_connect_form_renders(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "form1@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "form1@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/opponents/{link_id}/connect")
        assert response.status_code == 200
        assert "Ridgecrest Rockets" in response.text
        assert "GameChanger" in response.text

    def test_connect_form_404_for_invalid_id(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "form2@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "form2@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents/9999/connect")
        assert response.status_code == 404

    def test_connect_form_links_to_confirm(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "form3@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "form3@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/opponents/{link_id}/connect")
        assert f"/admin/opponents/{link_id}/connect/confirm" in response.text


# ---------------------------------------------------------------------------
# AC-6 & AC-7: Confirm page parses URL and fetches team info
# ---------------------------------------------------------------------------


class TestConnectConfirm:
    """Confirm page parses URL and fetches team info (AC-6, AC-7)."""

    def test_confirm_shows_team_profile_on_success(self, opp_db: Path) -> None:
        from src.gamechanger.team_resolver import TeamProfile

        admin_id = _insert_user(opp_db, "confirm1@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        mock_profile = TeamProfile(
            public_id="NewTeam001",
            name="Ridgecrest Rockets",
            sport="baseball",
        )

        with patch.dict("os.environ", _admin_env(opp_db, "confirm1@test.com")):
            with patch("src.api.routes.admin.resolve_team", return_value=mock_profile):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.get(
                        f"/admin/opponents/{link_id}/connect/confirm",
                        params={"url": "https://web.gc.com/teams/NewTeam001/slug"},
                    )
        assert response.status_code == 200
        assert "Ridgecrest Rockets" in response.text
        assert "NewTeam001" in response.text

    def test_confirm_shows_error_for_invalid_url(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "confirm2@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        with patch.dict("os.environ", _admin_env(opp_db, "confirm2@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(
                    f"/admin/opponents/{link_id}/connect/confirm",
                    params={"url": "not-a-valid-url-at-all!!"},
                )
        assert response.status_code == 200
        assert "try again" in response.text.lower()

    def test_confirm_shows_error_for_api_failure(self, opp_db: Path) -> None:
        from src.gamechanger.team_resolver import GameChangerAPIError

        admin_id = _insert_user(opp_db, "confirm3@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        with patch.dict("os.environ", _admin_env(opp_db, "confirm3@test.com")):
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
        from src.gamechanger.team_resolver import TeamNotFoundError

        admin_id = _insert_user(opp_db, "confirm4@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        with patch.dict("os.environ", _admin_env(opp_db, "confirm4@test.com")):
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
        """Confirm page shows error for a URL belonging to a member team."""
        admin_id = _insert_user(opp_db, "confirm5@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        # ownedPubId001 is the public_id of LSB Varsity (membership_type='member')
        with patch.dict("os.environ", _admin_env(opp_db, "confirm5@test.com")):
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

        admin_id = _insert_user(opp_db, "confirm6@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")

        # a1GFM9Ku0BbF is already used by Northside Eagles (auto-resolved)
        mock_profile = TeamProfile(
            public_id="a1GFM9Ku0BbF",
            name="Northside Eagles",
            sport="baseball",
        )

        with patch.dict("os.environ", _admin_env(opp_db, "confirm6@test.com")):
            with patch("src.api.routes.admin.resolve_team", return_value=mock_profile):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.get(
                        f"/admin/opponents/{link_id}/connect/confirm",
                        params={"url": "https://web.gc.com/teams/a1GFM9Ku0BbF/slug"},
                    )
        assert response.status_code == 200
        assert "Warning" in response.text or "duplicate" in response.text.lower()
        assert "Northside Eagles" in response.text


# ---------------------------------------------------------------------------
# AC-8: POST /connect saves link; duplicate warning; own-team rejection
# ---------------------------------------------------------------------------


class TestConnectPost:
    """POST /admin/opponents/{id}/connect saves the link correctly (AC-8)."""

    def test_connect_saves_manual_link(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "post1@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "post1@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
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

    def test_connect_redirects_to_listing_with_team_id(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "post3@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "post3@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "RidgeCrest02"},
                )
        assert response.status_code == 303
        assert "/admin/opponents" in response.headers["location"]
        assert "team_id" in response.headers["location"]

    def test_connect_rejects_owned_team_public_id(self, opp_db: Path) -> None:
        """POST /connect returns 400 when public_id belongs to a member team."""
        admin_id = _insert_user(opp_db, "post4@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "post4@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "ownedPubId001"},  # belongs to LSB Varsity member
                )
        assert response.status_code == 400

    def test_connect_duplicate_public_id_warns_but_succeeds(self, opp_db: Path) -> None:
        """POST /connect with duplicate public_id redirects with warning message."""
        admin_id = _insert_user(opp_db, "post5@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None

        # a1GFM9Ku0BbF already used by Northside Eagles
        with patch.dict("os.environ", _admin_env(opp_db, "post5@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "a1GFM9Ku0BbF"},
                )
        assert response.status_code == 303
        location = response.headers["location"]
        assert "msg=" in location
        assert "Northside" in location

        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["public_id"] == "a1GFM9Ku0BbF"


# ---------------------------------------------------------------------------
# E-091-03: Duplicate public_id check scoped to our_team_id
# ---------------------------------------------------------------------------


class TestDuplicatePublicIdScopedToTeam:
    """Duplicate public_id check is scoped to our_team_id (E-091-03)."""

    def test_cross_team_same_public_id_no_warning_on_save_post(
        self, opp_db_with_ids: tuple
    ) -> None:
        """POST /connect on JV team does not warn for cross-team same public_id."""
        opp_db, team_ids = opp_db_with_ids
        jv_id = team_ids["jv"]
        admin_id = _insert_user(opp_db, "e091cross1@test.com")
        token = _insert_session(opp_db, admin_id)

        # Insert an unlinked JV opponent
        link_id = _insert_opponent_link(
            opp_db,
            our_team_id=jv_id,
            root_team_id="gc-root-jv-x01",
            opponent_name="Northside Eagles JV",
        )

        # a1GFM9Ku0BbF is used by varsity/Northside Eagles (auto), but not JV
        with patch.dict("os.environ", _admin_env(opp_db, "e091cross1@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "a1GFM9Ku0BbF"},
                )

        assert response.status_code == 303
        location = response.headers["location"]
        # No "note:" warning in the redirect message
        assert "note" not in location.lower()

        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["public_id"] == "a1GFM9Ku0BbF"

    def test_same_team_duplicate_public_id_warns_on_save_post(
        self, opp_db: Path
    ) -> None:
        """POST /connect warns when the same team already uses the public_id."""
        admin_id = _insert_user(opp_db, "e091same1@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")
        assert link_id is not None  # belongs to varsity, unlinked

        # a1GFM9Ku0BbF already used by Northside Eagles on the same varsity team
        with patch.dict("os.environ", _admin_env(opp_db, "e091same1@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    f"/admin/opponents/{link_id}/connect",
                    data={"public_id": "a1GFM9Ku0BbF"},
                )

        assert response.status_code == 303
        location = response.headers["location"]
        assert "Northside" in location

        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["public_id"] == "a1GFM9Ku0BbF"

    def test_cross_team_same_public_id_no_warning_on_confirm_get(
        self, opp_db_with_ids: tuple
    ) -> None:
        """Confirm page does not show duplicate warning for a cross-team reuse."""
        from src.gamechanger.team_resolver import TeamProfile

        opp_db, team_ids = opp_db_with_ids
        jv_id = team_ids["jv"]
        admin_id = _insert_user(opp_db, "e091cross2@test.com")
        token = _insert_session(opp_db, admin_id)

        link_id = _insert_opponent_link(
            opp_db,
            our_team_id=jv_id,
            root_team_id="gc-root-jv-x02",
            opponent_name="Northside Eagles JV Confirm",
        )

        mock_profile = TeamProfile(
            public_id="a1GFM9Ku0BbF",
            name="Northside Eagles",
            sport="baseball",
        )

        with patch.dict("os.environ", _admin_env(opp_db, "e091cross2@test.com")):
            with patch("src.api.routes.admin.resolve_team", return_value=mock_profile):
                with TestClient(app, cookies={"session": token}) as client:
                    response = client.get(
                        f"/admin/opponents/{link_id}/connect/confirm",
                        params={"url": "https://web.gc.com/teams/a1GFM9Ku0BbF/slug"},
                    )

        assert response.status_code == 200
        assert "Warning" not in response.text
        assert "duplicate" not in response.text.lower()


# ---------------------------------------------------------------------------
# AC-9: Disconnect only for manual links; 400 for auto
# ---------------------------------------------------------------------------


class TestDisconnect:
    """POST /admin/opponents/{id}/disconnect only for manual links (AC-9)."""

    def test_disconnect_manual_link_clears_public_id(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "disc1@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Westview Tigers")  # manual link
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "disc1@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 303

        row = _get_link_row(opp_db, link_id)
        assert row is not None
        assert row["public_id"] is None
        assert row["resolution_method"] is None
        assert row["resolved_team_id"] is None

    def test_disconnect_manual_link_redirects_to_listing(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "disc2@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Westview Tigers")
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "disc2@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 303
        assert "/admin/opponents" in response.headers["location"]

    def test_disconnect_auto_link_returns_400(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "disc3@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Northside Eagles")  # auto link
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "disc3@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 400

    def test_disconnect_unlinked_returns_400(self, opp_db: Path) -> None:
        admin_id = _insert_user(opp_db, "disc4@test.com")
        token = _insert_session(opp_db, admin_id)
        link_id = _get_link_id_by_name(opp_db, "Ridgecrest Rockets")  # unlinked
        assert link_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "disc4@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.post(f"/admin/opponents/{link_id}/disconnect")
        assert response.status_code == 400

    def test_disconnect_shows_disconnect_button_only_for_manual(
        self, opp_db: Path
    ) -> None:
        admin_id = _insert_user(opp_db, "disc5@test.com")
        token = _insert_session(opp_db, admin_id)
        manual_id = _get_link_id_by_name(opp_db, "Westview Tigers")
        auto_id = _get_link_id_by_name(opp_db, "Northside Eagles")
        assert manual_id is not None
        assert auto_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "disc5@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/opponents")

        assert f"/admin/opponents/{manual_id}/disconnect" in response.text
        assert f"/admin/opponents/{auto_id}/disconnect" not in response.text


# ---------------------------------------------------------------------------
# AC-10: Teams edit page shows summary count + "Manage connections" link
# ---------------------------------------------------------------------------


class TestTeamsEditSimplified:
    """Teams edit page shows summary count + 'Manage connections' link (AC-10)."""

    def test_teams_list_shows_manage_opponents_link(self, opp_db: Path) -> None:
        """GET /admin/teams shows Manage connections link to opponents."""
        admin_id = _insert_user(opp_db, "ac10a@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "ac10a@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get("/admin/teams")
        assert "/admin/opponents" in response.text

    def test_edit_team_shows_connection_count_and_link(
        self, opp_db_with_ids: tuple
    ) -> None:
        """GET /admin/teams/{id}/edit shows per-team connection count and manage link."""
        opp_db, team_ids = opp_db_with_ids
        varsity_id = team_ids["varsity"]
        admin_id = _insert_user(opp_db, "ac10b@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "ac10b@test.com")):
            with TestClient(app, cookies={"session": token}) as client:
                response = client.get(f"/admin/teams/{varsity_id}/edit")
        # varsity has 2 opponent links (Northside auto + Ridgecrest unlinked)
        assert "Manage connections" in response.text
        assert f"team_id={varsity_id}" in response.text


# ---------------------------------------------------------------------------
# E-091-01: Guard connect endpoint against overwriting resolved links
# ---------------------------------------------------------------------------


class TestConnectGuardAgainstResolved:
    """POST /connect rejects already-resolved links (E-091-01)."""

    def test_connect_already_resolved_auto_returns_400(self, opp_db: Path) -> None:
        """POST /connect on an auto-resolved link returns HTTP 400."""
        admin_id = _insert_user(opp_db, "guard1@test.com")
        token = _insert_session(opp_db, admin_id)
        auto_id = _get_link_id_by_name(opp_db, "Northside Eagles")
        assert auto_id is not None

        with patch.dict("os.environ", _admin_env(opp_db, "guard1@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    f"/admin/opponents/{auto_id}/connect",
                    data={"public_id": "SomeOtherId"},
                )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# A-P2a: discover-opponents route coverage
# ---------------------------------------------------------------------------


class TestDiscoverOpponents:
    """POST /admin/teams/{id}/discover-opponents returns discovered opponents (A-P2a)."""

    def test_discover_opponents_returns_flash_with_count(
        self, opp_db_with_ids: tuple
    ) -> None:
        """POST discover-opponents redirects with correct count of new opponents found."""
        from src.gamechanger.team_resolver import DiscoveredOpponent

        opp_db, team_ids = opp_db_with_ids
        varsity_id = team_ids["varsity"]
        admin_id = _insert_user(opp_db, "discover1@test.com")
        token = _insert_session(opp_db, admin_id)

        discovered = [
            DiscoveredOpponent(name="Rival Team A"),
            DiscoveredOpponent(name="Rival Team B"),
        ]
        with patch(
            "src.api.routes.admin.discover_opponents",
            return_value=discovered,
        ) as mock_discover:
            with patch(
                "src.api.routes.admin.bulk_create_opponents",
                return_value=2,
            ) as mock_bulk:
                with patch.dict("os.environ", _admin_env(opp_db, "discover1@test.com")):
                    with TestClient(
                        app, follow_redirects=False, cookies={"session": token}
                    ) as client:
                        response = client.post(
                            f"/admin/teams/{varsity_id}/discover-opponents"
                        )

        assert response.status_code == 303
        assert "msg=" in response.headers["location"]
        assert "2" in response.headers["location"]
        mock_discover.assert_called_once_with("ownedPubId001")
        mock_bulk.assert_called_once_with(["Rival Team A", "Rival Team B"])

    def test_discover_opponents_no_public_id_redirects_with_error(
        self, opp_db_with_ids: tuple
    ) -> None:
        """POST discover-opponents for team with no public_id redirects with error."""
        opp_db, team_ids = opp_db_with_ids
        jv_id = team_ids["jv"]  # JV team has public_id=NULL
        admin_id = _insert_user(opp_db, "discover2@test.com")
        token = _insert_session(opp_db, admin_id)

        with patch.dict("os.environ", _admin_env(opp_db, "discover2@test.com")):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token}
            ) as client:
                response = client.post(
                    f"/admin/teams/{jv_id}/discover-opponents"
                )

        assert response.status_code == 303
        assert "error=" in response.headers["location"]
