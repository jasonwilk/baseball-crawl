# synthetic-test-data
"""Tests for cascade delete and confirmation page -- E-150-01 AC-9.

AC-9 requires:
  (a) Cascade deletion removes all FK-dependent rows for a team with data
      across all affected tables.
  (b) Shared-opponent detection identifies member teams that reference a
      tracked team via team_opponents or opponent_links.
  (c) Orphaned-opponent detection identifies tracked opponents that would be
      linked from no member team after the member team is deleted.
  (d) GET confirmation route returns correct row counts and template context
      for a team with data.
  (e) GET confirmation route returns zero counts for a team with no data.

Run with:
    pytest tests/test_admin_delete_cascade.py -v
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
"""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_cascade.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(_SEED_SQL)
    conn.commit()
    conn.close()
    return db_path


def _insert_user(db_path: Path, email: str) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, '')", (email,)
    )
    conn.commit()
    uid = cursor.lastrowid
    conn.close()
    return uid


def _insert_session(db_path: Path, user_id: int) -> str:
    raw = secrets.token_hex(32)
    hashed = hash_token(raw)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, datetime('now', '+7 days'))",
        (hashed, user_id),
    )
    conn.commit()
    conn.close()
    return raw


def _insert_team(db_path: Path, name: str, membership_type: str = "tracked") -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, ?)",
        (name, membership_type),
    )
    conn.commit()
    tid = cursor.lastrowid
    conn.close()
    return tid


def _insert_season(db_path: Path, season_id: str = "2026-spring") -> str:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (season_id, "Spring 2026", "spring-hs", 2026),
    )
    conn.commit()
    conn.close()
    return season_id


def _insert_player(db_path: Path, player_id: str = "p1") -> str:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, "Test", "Player"),
    )
    conn.commit()
    conn.close()
    return player_id


def _insert_game(
    db_path: Path,
    game_id: str,
    home_team_id: int,
    away_team_id: int,
    season_id: str,
) -> str:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id) VALUES (?, ?, ?, ?, ?)",
        (game_id, season_id, "2026-05-01", home_team_id, away_team_id),
    )
    conn.commit()
    conn.close()
    return game_id


def _count_rows(db_path: Path, table: str, where: str, params: tuple) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
    conn.close()
    return count


def _admin_env(db_path: Path, email: str = "admin@example.com") -> dict[str, str]:
    return {"DATABASE_PATH": str(db_path), "ADMIN_EMAIL": email}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    return _make_db(tmp_path)


# ---------------------------------------------------------------------------
# AC-9(a): Cascade deletion removes all FK-dependent rows
# ---------------------------------------------------------------------------


class TestCascadeDeletion:
    """AC-9(a): Full 4-phase cascade removes all dependent rows."""

    def test_cascade_removes_all_data_rows(self, db: Path) -> None:
        """POST /admin/teams/{id}/delete removes rows from every affected table."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        player_id = _insert_player(db, "p1")
        player2_id = _insert_player(db, "p2")

        team_id = _insert_team(db, "Delete Me", membership_type="member")
        opp_id = _insert_team(db, "Opponent", membership_type="tracked")

        game_id = _insert_game(db, "game-001", team_id, opp_id, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")

        # Phase 1 targets: player_game_batting, player_game_pitching, spray_charts (game-linked)
        conn.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id) VALUES (?, ?, ?)",
            (game_id, player_id, team_id),
        )
        conn.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id) VALUES (?, ?, ?)",
            (game_id, player2_id, opp_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id) VALUES (?, ?, ?)",
            (game_id, player_id, team_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id) VALUES (?, ?, ?)",
            (game_id, player2_id, opp_id),
        )
        conn.execute(
            "INSERT INTO spray_charts (game_id, team_id) VALUES (?, ?)",
            (game_id, team_id),
        )

        # Phase 3 targets: player_season_batting, player_season_pitching,
        #   spray_charts (team_id only), team_rosters, scouting_runs,
        #   crawl_jobs, user_team_access, coaching_assignments,
        #   team_opponents, opponent_links
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id) VALUES (?, ?, ?)",
            (player_id, team_id, season_id),
        )
        conn.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id) VALUES (?, ?, ?)",
            (player_id, team_id, season_id),
        )
        conn.execute(
            "INSERT INTO spray_charts (team_id) VALUES (?)",
            (team_id,),
        )
        conn.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) VALUES (?, ?, ?)",
            (team_id, player_id, season_id),
        )
        conn.execute(
            "INSERT INTO scouting_runs (team_id, season_id) VALUES (?, ?)",
            (team_id, season_id),
        )
        conn.execute(
            "INSERT INTO crawl_jobs (team_id, sync_type, status) VALUES (?, ?, ?)",
            (team_id, "member_crawl", "completed"),
        )
        conn.execute(
            "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (admin_id, team_id),
        )
        conn.execute(
            "INSERT INTO coaching_assignments (user_id, team_id) VALUES (?, ?)",
            (admin_id, team_id),
        )
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (team_id, opp_id),
        )
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id) VALUES (?, ?, ?, ?)",
            (team_id, "root-001", "Opponent", opp_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.post(
                    f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF}
                )

        assert resp.status_code == 303

        # Phase 4: team row is gone
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 0

        # Phase 1: game-child rows are gone (both team sides)
        assert _count_rows(db, "player_game_batting", "game_id = ?", (game_id,)) == 0
        assert _count_rows(db, "player_game_pitching", "game_id = ?", (game_id,)) == 0

        # Phase 2: game row is gone
        assert _count_rows(db, "games", "game_id = ?", (game_id,)) == 0

        # Phase 3: direct team_id rows are gone
        assert _count_rows(db, "player_season_batting", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "player_season_pitching", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "spray_charts", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "team_rosters", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "scouting_runs", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "crawl_jobs", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "user_team_access", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "coaching_assignments", "team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "team_opponents", "our_team_id = ?", (team_id,)) == 0
        assert _count_rows(db, "opponent_links", "our_team_id = ?", (team_id,)) == 0

    def test_phase1_removes_opponent_side_game_stats(self, db: Path) -> None:
        """Phase 1 deletes opponent-side player_game_batting rows for affected games."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        player_id = _insert_player(db, "p1")

        team_id = _insert_team(db, "Team To Delete", membership_type="member")
        opp_id = _insert_team(db, "Opponent Team", membership_type="tracked")

        game_id = _insert_game(db, "g-001", team_id, opp_id, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Opponent-side batting row -- should be deleted in Phase 1
        conn.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id) VALUES (?, ?, ?)",
            (game_id, player_id, opp_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                client.post(f"/admin/teams/{team_id}/delete", data={"csrf_token": _CSRF})

        # The opponent-side row is gone even though team_id = opp_id (not team_id)
        assert _count_rows(db, "player_game_batting", "team_id = ?", (opp_id,)) == 0


# ---------------------------------------------------------------------------
# AC-9(b): Shared-opponent detection
# ---------------------------------------------------------------------------


class TestSharedOpponentDetection:
    """AC-9(b): _get_delete_confirmation_data detects shared-opponent linkages."""

    def test_shared_via_team_opponents(self, db: Path) -> None:
        """A tracked team referenced in team_opponents shows the member team name."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        member_id = _insert_team(db, "LSB Varsity", membership_type="member")
        tracked_id = _insert_team(db, "River Hawks", membership_type="tracked")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (member_id, tracked_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{tracked_id}/delete")

        assert resp.status_code == 200
        assert "LSB Varsity" in resp.text
        assert "Shared Opponent Warning" in resp.text

    def test_shared_via_opponent_links(self, db: Path) -> None:
        """A tracked team resolved in opponent_links shows the member team name."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        member_id = _insert_team(db, "LSB JV", membership_type="member")
        tracked_id = _insert_team(db, "Summit Wolves", membership_type="tracked")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, resolved_team_id) VALUES (?, ?, ?, ?)",
            (member_id, "root-999", "Summit Wolves", tracked_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{tracked_id}/delete")

        assert resp.status_code == 200
        assert "LSB JV" in resp.text
        assert "Shared Opponent Warning" in resp.text

    def test_no_shared_warning_for_unlinked_tracked_team(self, db: Path) -> None:
        """A tracked team with no linkages shows no shared-opponent warning."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        tracked_id = _insert_team(db, "Unlinked Opponent", membership_type="tracked")

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{tracked_id}/delete")

        assert resp.status_code == 200
        assert "Shared Opponent Warning" not in resp.text

    def test_member_team_shows_no_shared_warning(self, db: Path) -> None:
        """Member teams never show the shared-opponent warning."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        member_id = _insert_team(db, "LSB Freshman", membership_type="member")

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{member_id}/delete")

        assert resp.status_code == 200
        assert "Shared Opponent Warning" not in resp.text


# ---------------------------------------------------------------------------
# AC-9(c): Orphaned-opponent detection
# ---------------------------------------------------------------------------


class TestOrphanedOpponentDetection:
    """AC-9(c): _get_delete_confirmation_data detects opponents that become orphaned."""

    def test_orphaned_opponent_appears_in_notice(self, db: Path) -> None:
        """An opponent linked only from the member team being deleted is listed."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        member_id = _insert_team(db, "LSB Varsity", membership_type="member")
        orphan_id = _insert_team(db, "Solo Opponent", membership_type="tracked")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (member_id, orphan_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{member_id}/delete")

        assert resp.status_code == 200
        assert "Solo Opponent" in resp.text
        assert "Orphaned Opponents Notice" in resp.text

    def test_shared_opponent_not_listed_as_orphaned(self, db: Path) -> None:
        """An opponent linked from multiple member teams is not listed as orphaned."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        member_id = _insert_team(db, "LSB Varsity", membership_type="member")
        other_member_id = _insert_team(db, "LSB JV", membership_type="member")
        shared_opp_id = _insert_team(db, "Shared Opponent", membership_type="tracked")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (member_id, shared_opp_id),
        )
        conn.execute(
            "INSERT INTO team_opponents (our_team_id, opponent_team_id) VALUES (?, ?)",
            (other_member_id, shared_opp_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{member_id}/delete")

        assert resp.status_code == 200
        assert "Shared Opponent" not in resp.text or "Orphaned Opponents Notice" not in resp.text
        # More precise: orphaned notice is absent because shared_opp is still linked from other_member
        assert "Orphaned Opponents Notice" not in resp.text

    def test_tracked_team_shows_no_orphaned_notice(self, db: Path) -> None:
        """Tracked teams never show the orphaned opponents notice."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        tracked_id = _insert_team(db, "River Hawks", membership_type="tracked")

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{tracked_id}/delete")

        assert resp.status_code == 200
        assert "Orphaned Opponents Notice" not in resp.text


# ---------------------------------------------------------------------------
# AC-9(d): GET confirmation route -- team with data
# ---------------------------------------------------------------------------


class TestConfirmDeleteRouteWithData:
    """AC-9(d): GET /admin/teams/{id}/delete returns correct counts for a team with data."""

    def test_get_shows_row_counts_for_team_with_games(self, db: Path) -> None:
        """Confirmation page displays the correct game count and opponent count."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        player_id = _insert_player(db, "p1")

        team_id = _insert_team(db, "Data Rich Team", membership_type="member")
        opp_id = _insert_team(db, "The Other Side", membership_type="tracked")

        _insert_game(db, "g-data-001", team_id, opp_id, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id) VALUES (?, ?, ?)",
            (player_id, team_id, season_id),
        )
        conn.execute(
            "INSERT INTO crawl_jobs (team_id, sync_type, status) VALUES (?, ?, ?)",
            (team_id, "member_crawl", "completed"),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{team_id}/delete")

        assert resp.status_code == 200
        assert "Data Rich Team" in resp.text
        # 1 game row count appears in the table
        assert ">1<" in resp.text
        # Member badge
        assert "Member" in resp.text
        # Confirm Delete button present
        assert "Confirm Delete" in resp.text
        # Cancel link present
        assert "Cancel" in resp.text

    def test_get_shows_team_name_and_membership(self, db: Path) -> None:
        """Confirmation page shows team name and membership badge."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        team_id = _insert_team(db, "Eastside Eagles", membership_type="tracked")

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{team_id}/delete")

        assert resp.status_code == 200
        assert "Eastside Eagles" in resp.text
        assert "Tracked" in resp.text


# ---------------------------------------------------------------------------
# AC-9(e): GET confirmation route -- team with no data
# ---------------------------------------------------------------------------


class TestConfirmDeleteRouteZeroData:
    """AC-9(e): GET /admin/teams/{id}/delete returns zero counts for a no-data team."""

    def test_get_shows_zero_counts_for_empty_team(self, db: Path) -> None:
        """All row counts are zero and the zero-data note is displayed."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        team_id = _insert_team(db, "Empty Team", membership_type="tracked")

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{team_id}/delete")

        assert resp.status_code == 200
        assert "Empty Team" in resp.text
        # Zero-data note
        assert "No associated data" in resp.text
        # Total = 0
        assert ">0<" in resp.text

    def test_get_requires_admin(self, db: Path) -> None:
        """Non-admin gets 403 on GET /admin/teams/{id}/delete."""
        user_id = _insert_user(db, "coach@example.com")
        token = _insert_session(db, user_id)

        team_id = _insert_team(db, "Some Team", membership_type="tracked")

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db), "ADMIN_EMAIL": "other@example.com"},
        ):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get(f"/admin/teams/{team_id}/delete")

        assert resp.status_code == 403

    def test_get_returns_404_for_unknown_team(self, db: Path) -> None:
        """GET /admin/teams/999999/delete returns 404."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, follow_redirects=False, cookies={"session": token, "csrf_token": _CSRF}
            ) as client:
                resp = client.get("/admin/teams/999999/delete")

        assert resp.status_code == 404
