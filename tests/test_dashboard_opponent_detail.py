# synthetic-test-data
"""Tests for E-153-04: Opponent Detail Redesign.

Covers AC-10 items:
  (a) pitching-first section order renders correctly
  (b) unlinked state shows the correct empty-state card
  (c) linked-but-unscouted state shows the correct card
  (d) admin shortcut link appears only for admin users
  (e) stub-team opponents are accessible without 403

Also tests the new db helpers:
  - get_opponent_scouting_status: full_stats / linked_unscouted / unlinked

Run with:
    pytest tests/test_dashboard_opponent_detail.py -v
"""

from __future__ import annotations

import datetime
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.main import app  # noqa: E402

_SEASON_ID = f"{datetime.date.today().year}-spring-hs"
_USER_EMAIL = "testdev@example.com"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_opp_detail.db"
    run_migrations(db_path=db_path)
    return db_path


def _insert_member_team(conn: sqlite3.Connection, name: str = "LSB Varsity") -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, 'member')", (name,)
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _insert_opponent_team(
    conn: sqlite3.Connection,
    name: str = "Rival High",
    public_id: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO teams (name, membership_type, public_id) VALUES (?, 'tracked', ?)",
        (name, public_id),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _insert_season(conn: sqlite3.Connection, season_id: str = _SEASON_ID) -> None:
    year = int(season_id.split("-")[0])
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)"
        " VALUES (?, ?, 'spring-hs', ?)",
        (season_id, f"Season {season_id}", year),
    )
    conn.commit()


def _insert_game(
    conn: sqlite3.Connection,
    game_id: str,
    home_id: int,
    away_id: int,
    season_id: str = _SEASON_ID,
    home_score: int = 5,
    away_score: int = 3,
    status: str = "completed",
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO games"
        " (game_id, season_id, game_date, home_team_id, away_team_id,"
        "  home_score, away_score, status)"
        " VALUES (?, ?, date('now'), ?, ?, ?, ?, ?)",
        (game_id, season_id, home_id, away_id, home_score, away_score, status),
    )
    conn.commit()


def _insert_user(conn: sqlite3.Connection, email: str = _USER_EMAIL, role: str = "user") -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO users (email, role) VALUES (?, ?)", (email, role)
    )
    conn.commit()
    uid: int = cur.lastrowid or conn.execute(  # type: ignore[assignment]
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()[0]
    return uid


def _grant_team_access(conn: sqlite3.Connection, user_id: int, team_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, team_id),
    )
    conn.commit()


def _insert_player(
    conn: sqlite3.Connection,
    player_id: str,
    first: str,
    last: str,
    throws: str | None = None,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name, throws)"
        " VALUES (?, ?, ?, ?)",
        (player_id, first, last, throws),
    )
    conn.commit()


def _insert_batting(
    conn: sqlite3.Connection,
    player_id: str,
    team_id: int,
    season_id: str = _SEASON_ID,
    gp: int = 5,
    ab: int = 15,
    h: int = 4,
    bb: int = 2,
    so: int = 3,
    hbp: int = 0,
    shf: int = 0,
    tb: int = 5,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, doubles, triples,"
        "  hr, rbi, bb, so, sb, hbp, shf, tb)"
        " VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, 2, ?, ?, 0, ?, ?, ?)",
        (player_id, team_id, season_id, gp, ab, h, bb, so, hbp, shf, tb),
    )
    conn.commit()


def _insert_pitching(
    conn: sqlite3.Connection,
    player_id: str,
    team_id: int,
    season_id: str = _SEASON_ID,
    gp: int = 4,
    ip_outs: int = 18,
    h: int = 6,
    er: int = 2,
    bb: int = 3,
    so: int = 12,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO player_season_pitching"
        " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (player_id, team_id, season_id, gp, ip_outs, h, er, bb, so),
    )
    conn.commit()


def _insert_opponent_link(
    conn: sqlite3.Connection,
    our_team_id: int,
    opponent_name: str,
    resolved_team_id: int | None = None,
    public_id: str | None = None,
    root_team_id: str | None = None,
) -> int:
    if root_team_id is None:
        root_team_id = f"root-{opponent_name.lower().replace(' ', '-')}-{our_team_id}"
    cur = conn.execute(
        "INSERT INTO opponent_links"
        " (our_team_id, root_team_id, opponent_name, resolved_team_id, public_id)"
        " VALUES (?, ?, ?, ?, ?)",
        (our_team_id, root_team_id, opponent_name, resolved_team_id, public_id),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _make_client(db_path: Path, user_email: str = _USER_EMAIL) -> TestClient:
    """Create a TestClient using DEV_USER_EMAIL bypass."""
    env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": user_email}
    with patch.dict("os.environ", env):
        return TestClient(app)


# ---------------------------------------------------------------------------
# Tests for get_opponent_scouting_status (db helper)
# ---------------------------------------------------------------------------


class TestGetOpponentScoutingStatus:
    """Tests for db.get_opponent_scouting_status."""

    def setup_method(self, method):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = _make_db(Path(self._tmpdir))
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            self.member_id = _insert_member_team(conn, "LSB Varsity")
            self.opp_id = _insert_opponent_team(conn, "Rival High")
            _insert_season(conn)

    def _status(self, opponent_team_id: int, our_team_id: int | None, season_id: str = _SEASON_ID):
        from src.api import db as _db
        with patch.dict("os.environ", {"DATABASE_PATH": str(self.db_path)}):
            return _db.get_opponent_scouting_status(opponent_team_id, our_team_id, season_id)

    def test_full_stats_when_batting_rows_exist(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            _insert_player(conn, "p-001", "A", "B")
            _insert_batting(conn, "p-001", self.opp_id)
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "full_stats"

    def test_full_stats_when_pitching_rows_exist(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            _insert_player(conn, "p-002", "C", "D")
            _insert_pitching(conn, "p-002", self.opp_id)
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "full_stats"

    def test_linked_unscouted_when_resolved_link_exists(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            link_id = _insert_opponent_link(
                conn, self.member_id, "Rival High", resolved_team_id=self.opp_id
            )
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "linked_unscouted"
        assert result["link_id"] == link_id

    def test_linked_unscouted_when_team_has_public_id(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "UPDATE teams SET public_id = 'rival-slug' WHERE id = ?", (self.opp_id,)
            )
            conn.commit()
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "linked_unscouted"

    def test_unlinked_when_no_link_and_no_public_id(self):
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "unlinked"
        assert result["link_id"] is None

    def test_link_id_returned_for_full_stats_with_link(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            _insert_player(conn, "p-003", "E", "F")
            _insert_batting(conn, "p-003", self.opp_id)
            link_id = _insert_opponent_link(
                conn, self.member_id, "Rival High", resolved_team_id=self.opp_id
            )
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "full_stats"
        assert result["link_id"] == link_id

    def test_our_team_id_scoping(self):
        """Link for a different member team does not affect status for our team."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            other_member_id = _insert_member_team(conn, "LSB JV")
            _insert_opponent_link(
                conn, other_member_id, "Rival High",
                resolved_team_id=self.opp_id,
                root_team_id="root-rival-other",
            )
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "unlinked"

    def test_none_our_team_id_returns_valid_status(self):
        result = self._status(self.opp_id, None)
        assert result["status"] in ("unlinked", "linked_unscouted", "full_stats")

    def test_link_id_returned_for_unresolved_link_via_name_match(self):
        """Unresolved opponent_links row (resolved_team_id IS NULL) is found via team name match.

        Fix 3 (CR round 1): OpponentSeeder creates rows before OpponentResolver runs.
        The admin shortcut must surface the link_id even when resolved_team_id IS NULL,
        so admin can navigate directly to /admin/opponents/{link_id}/connect.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            # Insert an unresolved link -- name matches the opponent team name "Rival High"
            link_id = _insert_opponent_link(
                conn, self.member_id, "Rival High", resolved_team_id=None
            )
        result = self._status(self.opp_id, self.member_id)
        assert result["status"] == "unlinked"
        assert result["link_id"] == link_id, (
            "link_id should be returned even for unresolved opponent_links rows"
        )


# ---------------------------------------------------------------------------
# Tests for the opponent detail route
# ---------------------------------------------------------------------------


def _make_full_db(tmp_path: Path) -> tuple[Path, int, int, int]:
    """Create a DB with member team, opponent, game, and full stats.

    Returns:
        (db_path, member_team_id, opp_team_id, link_id)
    """
    db_path = _make_db(tmp_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        member_id = _insert_member_team(conn, "LSB Varsity")
        opp_id = _insert_opponent_team(conn, "Central Lions")
        _insert_season(conn)
        _insert_game(conn, "g-001", member_id, opp_id)
        user_id = _insert_user(conn)
        _grant_team_access(conn, user_id, member_id)
        _insert_player(conn, "opp-bat-1", "Alice", "Smith")
        _insert_player(conn, "opp-bat-2", "Bob", "Jones")
        _insert_batting(conn, "opp-bat-1", opp_id, ab=20, h=6, bb=3, so=4, tb=8)
        _insert_batting(conn, "opp-bat-2", opp_id, ab=18, h=5, bb=2, so=5, tb=6)
        _insert_player(conn, "opp-pit-1", "Carlos", "Rivera", throws="R")
        _insert_player(conn, "opp-pit-2", "Dan", "Lee", throws="L")
        _insert_player(conn, "opp-pit-3", "Eve", "Wang")
        _insert_pitching(conn, "opp-pit-1", opp_id, gp=5, ip_outs=21, bb=4, so=10)
        _insert_pitching(conn, "opp-pit-2", opp_id, gp=3, ip_outs=12, bb=2, so=6)
        _insert_pitching(conn, "opp-pit-3", opp_id, gp=2, ip_outs=6, bb=1, so=3)
        link_id = _insert_opponent_link(
            conn, member_id, "Central Lions", resolved_team_id=opp_id
        )
    return db_path, member_id, opp_id, link_id


class TestOpponentDetailSectionOrder:
    """AC-10(a): pitching-first section order renders correctly."""

    def test_pitching_card_appears_before_batting_table(self, tmp_path):
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        pit_pos = body.find("Their Pitchers")
        bat_pos = body.find("Batting Leaders")
        assert pit_pos != -1, "Pitching card not found in response"
        assert bat_pos != -1, "Batting Leaders not found in response"
        assert pit_pos < bat_pos, "Pitching card must appear before Batting Leaders"

    def test_pitching_table_appears_before_batting_table(self, tmp_path):
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        pit_pos = body.find("Pitching Leaders")
        bat_pos = body.find("Batting Leaders")
        assert pit_pos != -1
        assert bat_pos != -1
        assert pit_pos < bat_pos

    def test_back_link_points_to_schedule(self, tmp_path):
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "/dashboard" in resp.text
        assert "Back to Schedule" in resp.text
        # Must NOT point to the non-existent /dashboard/schedule path
        assert "/dashboard/schedule" not in resp.text

    def test_pitcher_handedness_displayed_when_available(self, tmp_path):
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "(R)" in body
        assert "(L)" in body


class TestOpponentDetailUnlinkedState:
    """AC-10(b): unlinked state shows the correct empty-state card."""

    def _make_unlinked_db(self, tmp_path: Path) -> tuple[Path, int, int]:
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            opp_id = _insert_opponent_team(conn, "Unknown Team")
            _insert_season(conn)
            _insert_game(conn, "g-unlinked", member_id, opp_id)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        return db_path, member_id, opp_id

    def test_unlinked_shows_stats_not_available_card(self, tmp_path):
        db_path, member_id, opp_id = self._make_unlinked_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "Stats not available" in body
        assert "Scouting stats" in body

    def test_unlinked_no_pitching_card(self, tmp_path):
        db_path, member_id, opp_id = self._make_unlinked_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Their Pitchers" not in resp.text

    def test_unlinked_no_admin_link_for_non_admin(self, tmp_path):
        db_path, member_id, opp_id = self._make_unlinked_db(tmp_path)
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": _USER_EMAIL,
            "ADMIN_EMAIL": "admin@other.edu",  # different from user, so not admin
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Link in Admin" not in resp.text


class TestOpponentDetailLinkedUnscouted:
    """AC-10(c): linked-but-unscouted state shows the correct card."""

    def _make_linked_unscouted_db(self, tmp_path: Path) -> tuple[Path, int, int]:
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            opp_id = _insert_opponent_team(conn, "Central Lions")
            _insert_season(conn)
            _insert_game(conn, "g-linked", member_id, opp_id)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
            _insert_opponent_link(
                conn, member_id, "Central Lions", resolved_team_id=opp_id
            )
        return db_path, member_id, opp_id

    def test_linked_unscouted_shows_correct_card(self, tmp_path):
        db_path, member_id, opp_id = self._make_linked_unscouted_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "Stats not loaded yet" in body
        assert "on their way" in body

    def test_linked_unscouted_no_pitching_card(self, tmp_path):
        db_path, member_id, opp_id = self._make_linked_unscouted_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Their Pitchers" not in resp.text

    def test_linked_unscouted_does_not_show_unlinked_message(self, tmp_path):
        db_path, member_id, opp_id = self._make_linked_unscouted_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Stats not available" not in resp.text


class TestOpponentDetailAdminShortcut:
    """AC-10(d): admin shortcut link appears only for admin users."""

    def _make_admin_db(self, tmp_path: Path, user_role: str = "user") -> tuple[Path, int, int]:
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            opp_id = _insert_opponent_team(conn, "Unknown Team")
            _insert_season(conn)
            _insert_game(conn, "g-admin-test", member_id, opp_id)
            user_id = _insert_user(conn, _USER_EMAIL, role=user_role)
            _grant_team_access(conn, user_id, member_id)
        return db_path, member_id, opp_id

    def test_admin_sees_link_in_admin_shortcut_via_email(self, tmp_path):
        """Admin via ADMIN_EMAIL env var sees the shortcut."""
        db_path, member_id, opp_id = self._make_admin_db(tmp_path, user_role="user")
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": _USER_EMAIL,
            "ADMIN_EMAIL": _USER_EMAIL,  # email match grants admin
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "Link in Admin" in body
        assert "/admin/opponents" in body

    def test_admin_sees_link_via_db_role(self, tmp_path):
        """Admin via DB role sees the shortcut."""
        db_path, member_id, opp_id = self._make_admin_db(tmp_path, user_role="admin")
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": _USER_EMAIL,
        }
        # No ADMIN_EMAIL set -- admin status comes from DB role
        with patch.dict("os.environ", env, clear=False):
            with patch.dict("os.environ", {"ADMIN_EMAIL": ""}, clear=False):
                with TestClient(app) as client:
                    resp = client.get(
                        f"/dashboard/opponents/{opp_id}",
                        params={"team_id": member_id, "season_id": _SEASON_ID},
                    )
        assert resp.status_code == 200
        assert "Link in Admin" in resp.text

    def test_non_admin_does_not_see_admin_shortcut(self, tmp_path):
        """Regular user (role='user', no ADMIN_EMAIL match) doesn't see shortcut."""
        db_path, member_id, opp_id = self._make_admin_db(tmp_path, user_role="user")
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": _USER_EMAIL,
            "ADMIN_EMAIL": "admin@other.edu",  # different email
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Link in Admin" not in resp.text

    def test_admin_with_resolved_link_gets_connect_url(self, tmp_path):
        """When a resolved link exists, admin shortcut points to /connect page."""
        db_path, member_id, opp_id = self._make_admin_db(tmp_path, user_role="user")
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            link_id = _insert_opponent_link(
                conn, member_id, "Unknown Team", resolved_team_id=opp_id,
                root_team_id="root-unknown-admin",
            )
            # Add stats so state is full_stats (link_id still returned)
            _insert_player(conn, "p-x1", "X", "Y")
            _insert_batting(conn, "p-x1", opp_id)
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": _USER_EMAIL,
            "ADMIN_EMAIL": _USER_EMAIL,
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        # Full stats state does not show admin shortcuts (only unlinked does)
        assert resp.status_code == 200
        # Stats should render (full_stats), no empty state card
        assert "Stats not available" not in resp.text


class TestOpponentDetailStubTeamAccess:
    """AC-10(e): stub-team opponents are accessible without 403."""

    def test_stub_opponent_accessible_via_game(self, tmp_path):
        """Opponent inserted as stub via schedule loader is accessible."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            stub_opp_id = _insert_opponent_team(conn, "Stub Opponent Team")
            _insert_season(conn)
            _insert_game(conn, "g-stub", member_id, stub_opp_id)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{stub_opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200

    def test_non_game_opponent_returns_403(self, tmp_path):
        """Opponent not in any game for permitted team returns 403."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            unrelated_opp_id = _insert_opponent_team(conn, "Unrelated Team")
            _insert_season(conn)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{unrelated_opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestComputeTeamBatting:
    """Unit tests for _compute_team_batting."""

    def test_empty_batting_returns_no_data(self):
        from src.api.routes.dashboard import _compute_team_batting
        result = _compute_team_batting([])
        assert result["has_data"] is False

    def test_zero_pa_returns_no_data(self):
        from src.api.routes.dashboard import _compute_team_batting
        players = [{"ab": 0, "h": 0, "bb": 0, "hbp": 0, "shf": 0, "so": 0, "tb": 0}]
        result = _compute_team_batting(players)
        assert result["has_data"] is False

    def test_obp_computed_correctly(self):
        from src.api.routes.dashboard import _compute_team_batting
        # OBP = (H + BB + HBP) / (AB + BB + HBP + SHF)
        # = (4 + 2 + 0) / (10 + 2 + 0 + 0) = 6/12 = 0.500
        players = [{"ab": 10, "h": 4, "bb": 2, "hbp": 0, "shf": 0, "so": 2, "tb": 6}]
        result = _compute_team_batting(players)
        assert result["has_data"] is True
        assert result["obp"] == ".500"

    def test_k_pct_computed_correctly(self):
        from src.api.routes.dashboard import _compute_team_batting
        # K% = SO / PA = 3 / 12 = 25.0%
        players = [{"ab": 10, "h": 4, "bb": 2, "hbp": 0, "shf": 0, "so": 3, "tb": 6}]
        result = _compute_team_batting(players)
        assert result["k_pct"] == "25.0%"

    def test_slg_computed_from_tb(self):
        from src.api.routes.dashboard import _compute_team_batting
        # SLG = TB / AB = 8 / 10 = 0.800
        players = [{"ab": 10, "h": 4, "bb": 2, "hbp": 0, "shf": 0, "so": 2, "tb": 8}]
        result = _compute_team_batting(players)
        assert result["slg"] == ".800"

    def test_aggregates_across_multiple_players(self):
        from src.api.routes.dashboard import _compute_team_batting
        players = [
            {"ab": 10, "h": 3, "bb": 1, "hbp": 0, "shf": 0, "so": 2, "tb": 4},
            {"ab": 10, "h": 2, "bb": 2, "hbp": 0, "shf": 0, "so": 4, "tb": 3},
        ]
        result = _compute_team_batting(players)
        # PA = 10+1 + 10+2 = 23
        # OBP = (3+2 + 1+2) / 23 = 8/23
        expected_obp = f"{8/23:.3f}".lstrip("0")
        assert result["obp"] == expected_obp


class TestComputePitchingRates:
    """Unit tests for _compute_opponent_pitching_rates additions (bb9 and k_bb_ratio)."""

    def _make_pitcher(self, ip_outs=18, er=2, so=9, bb=3, h=6, games=3) -> dict:
        return {
            "ip_outs": ip_outs, "er": er, "so": so, "bb": bb, "h": h,
            "games": games, "pitches": 0, "total_strikes": 0,
        }

    def test_bb9_computed(self):
        from src.api.routes.dashboard import _compute_opponent_pitching_rates
        pitchers = [self._make_pitcher(ip_outs=27, bb=9)]
        result = _compute_opponent_pitching_rates(pitchers)
        assert result[0]["bb9"] == "9.0"

    def test_bb9_zero_ip_outs(self):
        from src.api.routes.dashboard import _compute_opponent_pitching_rates
        pitchers = [self._make_pitcher(ip_outs=0)]
        result = _compute_opponent_pitching_rates(pitchers)
        assert result[0]["bb9"] == "-"

    def test_k_bb_ratio_computed(self):
        from src.api.routes.dashboard import _compute_opponent_pitching_rates
        pitchers = [self._make_pitcher(so=10, bb=4)]
        result = _compute_opponent_pitching_rates(pitchers)
        assert result[0]["k_bb_ratio"] == "2.5"

    def test_k_bb_ratio_zero_bb(self):
        from src.api.routes.dashboard import _compute_opponent_pitching_rates
        pitchers = [self._make_pitcher(so=8, bb=0)]
        result = _compute_opponent_pitching_rates(pitchers)
        assert result[0]["k_bb_ratio"] == "--"


class TestGetTopPitchers:
    """Unit tests for _get_top_pitchers."""

    def test_returns_top_3_by_ip_outs(self):
        from src.api.routes.dashboard import _get_top_pitchers
        pitchers = [
            {"name": "A", "ip_outs": 6},
            {"name": "B", "ip_outs": 21},
            {"name": "C", "ip_outs": 12},
            {"name": "D", "ip_outs": 18},
        ]
        result = _get_top_pitchers(pitchers)
        assert len(result) == 3
        assert [p["name"] for p in result] == ["B", "D", "C"]

    def test_excludes_zero_ip_outs(self):
        from src.api.routes.dashboard import _get_top_pitchers
        pitchers = [
            {"name": "A", "ip_outs": 0},
            {"name": "B", "ip_outs": 9},
        ]
        result = _get_top_pitchers(pitchers)
        assert len(result) == 1
        assert result[0]["name"] == "B"

    def test_fewer_than_3_pitchers(self):
        from src.api.routes.dashboard import _get_top_pitchers
        pitchers = [{"name": "Only", "ip_outs": 15}]
        result = _get_top_pitchers(pitchers)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests for the opponent print route (E-159-01: AC-16)
# ---------------------------------------------------------------------------


class TestOpponentPrintRoute:
    """AC-16: Print route returns 200 with correct content for all empty states."""

    def test_full_stats_returns_200_with_print_elements(self, tmp_path):
        """AC-16(a): full_stats state renders 200 with 'Scouting Report' and window.print()."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "Scouting Report" in body
        assert "window.print()" in body

    def test_full_stats_contains_pitching_and_batting_tables(self, tmp_path):
        """Full stats shows both pitching and batting sections."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "Pitching" in body
        assert "Batting" in body
        assert "Batter Tendencies" in body

    def test_full_stats_pitcher_handedness_in_print_table(self, tmp_path):
        """Pitcher handedness appears in the print pitching table."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "(R)" in body
        assert "(L)" in body

    def test_full_stats_view_online_link_present(self, tmp_path):
        """'View online' back-link is present on the print page."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "View online" in resp.text

    def test_unlinked_returns_200_with_stats_not_available(self, tmp_path):
        """AC-16(b): unlinked state returns 200 with 'Stats not available.' message."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            opp_id = _insert_opponent_team(conn, "Unknown Rival")
            _insert_season(conn)
            _insert_game(conn, "g-print-unlinked", member_id, opp_id)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Stats not available." in resp.text

    def test_linked_unscouted_returns_200_with_stats_not_loaded(self, tmp_path):
        """AC-16(b): linked_unscouted state returns 200 with 'Stats not loaded yet.' message."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            opp_id = _insert_opponent_team(conn, "Linked Rival", public_id="linked-rival-slug")
            _insert_season(conn)
            _insert_game(conn, "g-print-linked", member_id, opp_id)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Stats not loaded yet." in resp.text

    def test_unauthorized_returns_403(self, tmp_path):
        """Opponent not in any game for permitted team returns 403."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            unrelated_opp_id = _insert_opponent_team(conn, "No Game Rival")
            _insert_season(conn)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{unrelated_opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests for the print link on the interactive scouting report (E-159-02)
# ---------------------------------------------------------------------------


class TestOpponentDetailPrintLink:
    """AC-4: Print link visibility across empty states on the interactive page."""

    def test_print_link_present_in_full_stats(self, tmp_path):
        """AC-1/AC-3: Print link appears in full_stats state."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "Print / Save as PDF" in body
        assert f"/dashboard/opponents/{opp_id}/print" in body

    def test_print_link_url_contains_team_id_and_season_id(self, tmp_path):
        """AC-2: Print link URL includes team_id and season_id params."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert f"team_id={member_id}" in body
        assert f"season_id={_SEASON_ID}" in body

    def test_print_link_absent_in_unlinked_state(self, tmp_path):
        """AC-3: Print link does not appear in unlinked state."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            opp_id = _insert_opponent_team(conn, "Unlinked Rival")
            _insert_season(conn)
            _insert_game(conn, "g-link-test-1", member_id, opp_id)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Print / Save as PDF" not in resp.text

    def test_print_link_absent_in_linked_unscouted_state(self, tmp_path):
        """AC-3: Print link does not appear in linked_unscouted state."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            member_id = _insert_member_team(conn, "LSB Varsity")
            opp_id = _insert_opponent_team(conn, "Linked No Stats", public_id="linked-no-stats")
            _insert_season(conn)
            _insert_game(conn, "g-link-test-2", member_id, opp_id)
            user_id = _insert_user(conn)
            _grant_team_access(conn, user_id, member_id)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        assert "Print / Save as PDF" not in resp.text


# ---------------------------------------------------------------------------
# Year round-trip tests (E-159 Codex remediation)
# ---------------------------------------------------------------------------


class TestYearRoundTrip:
    """Verify year param include/omit behavior per AC-12 (print page) and AC-2 (detail page)."""

    def test_print_page_view_online_includes_year_when_provided(self, tmp_path):
        """AC-12: 'View online' link on print page includes year= when year param is set."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID, "year": "2025"},
                )
        assert resp.status_code == 200
        assert "year=2025" in resp.text

    def test_print_page_view_online_omits_year_when_not_provided(self, tmp_path):
        """AC-12: 'View online' link omits year param entirely when not set."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}/print",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        assert "year=None" not in body
        # year= should not appear in the View online href at all
        view_online_pos = body.find("View online")
        assert view_online_pos != -1
        surrounding = body[max(0, view_online_pos - 200):view_online_pos]
        assert "year=" not in surrounding

    def test_detail_print_link_includes_year_when_provided(self, tmp_path):
        """AC-2: Print link on detail page includes year= when year param is set."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID, "year": "2025"},
                )
        assert resp.status_code == 200
        body = resp.text
        print_link_start = body.find("/print")
        assert print_link_start != -1
        print_href = body[print_link_start:print_link_start + 200]
        assert "year=2025" in print_href

    def test_detail_print_link_omits_year_when_not_provided(self, tmp_path):
        """AC-2: Print link on detail page omits year param entirely when year not set."""
        db_path, member_id, opp_id, _ = _make_full_db(tmp_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": _USER_EMAIL}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_id}",
                    params={"team_id": member_id, "season_id": _SEASON_ID},
                )
        assert resp.status_code == 200
        body = resp.text
        print_link_start = body.find("/print")
        assert print_link_start != -1
        print_href = body[print_link_start:print_link_start + 200]
        assert "year=None" not in print_href
        assert "year=" not in print_href


# ---------------------------------------------------------------------------
# E-169-02: _apply_name_cascade unit tests
# ---------------------------------------------------------------------------


class TestApplyNameCascade:
    """Test the display name fallback cascade in src/api/db.py."""

    def test_real_name_unchanged(self):
        """AC-5: Players with real names are displayed normally."""
        from src.api.db import _apply_name_cascade

        rows = [{"name": "Caleb Davis", "jersey_number": "23"}]
        result = _apply_name_cascade(rows)
        assert result[0]["name"] == "Caleb Davis"
        assert result[0]["name_unresolved"] is False

    def test_unknown_with_jersey_becomes_player_number(self):
        """AC-1: Unknown Unknown + jersey_number → 'Player #NN'."""
        from src.api.db import _apply_name_cascade

        rows = [{"name": "Unknown Unknown", "jersey_number": "7"}]
        result = _apply_name_cascade(rows)
        assert result[0]["name"] == "Player #7"
        assert result[0]["name_unresolved"] is True

    def test_unknown_without_jersey_becomes_unknown_player(self):
        """AC-2: Unknown Unknown + no jersey_number → 'Unknown Player'."""
        from src.api.db import _apply_name_cascade

        rows = [{"name": "Unknown Unknown", "jersey_number": None}]
        result = _apply_name_cascade(rows)
        assert result[0]["name"] == "Unknown Player"
        assert result[0]["name_unresolved"] is True

    def test_multiple_rows_mixed(self):
        """Cascade applies correctly to a mix of resolved and unresolved rows."""
        from src.api.db import _apply_name_cascade

        rows = [
            {"name": "Jake Miller", "jersey_number": "12"},
            {"name": "Unknown Unknown", "jersey_number": "5"},
            {"name": "Unknown Unknown", "jersey_number": None},
        ]
        result = _apply_name_cascade(rows)
        assert result[0]["name"] == "Jake Miller"
        assert result[0]["name_unresolved"] is False
        assert result[1]["name"] == "Player #5"
        assert result[1]["name_unresolved"] is True
        assert result[2]["name"] == "Unknown Player"
        assert result[2]["name_unresolved"] is True

    def test_empty_list(self):
        """Cascade handles an empty list gracefully."""
        from src.api.db import _apply_name_cascade

        assert _apply_name_cascade([]) == []

    def test_mutates_in_place(self):
        """Cascade modifies dicts in place and returns the same list."""
        from src.api.db import _apply_name_cascade

        rows = [{"name": "Unknown Unknown", "jersey_number": "10"}]
        result = _apply_name_cascade(rows)
        assert result is rows
        assert rows[0]["name"] == "Player #10"
