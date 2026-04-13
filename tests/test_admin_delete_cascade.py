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
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id) VALUES (?, ?, ?, ?)",
            (game_id, player_id, team_id, team_id),
        )
        conn.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id) VALUES (?, ?, ?, ?)",
            (game_id, player2_id, opp_id, team_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id) VALUES (?, ?, ?, ?)",
            (game_id, player_id, team_id, team_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id) VALUES (?, ?, ?, ?)",
            (game_id, player2_id, opp_id, team_id),
        )
        conn.execute(
            "INSERT INTO spray_charts (game_id, team_id, perspective_team_id) VALUES (?, ?, ?)",
            (game_id, team_id, team_id),
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
            "INSERT INTO spray_charts (team_id, perspective_team_id) VALUES (?, ?)",
            (team_id, team_id),
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
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id) VALUES (?, ?, ?, ?)",
            (game_id, player_id, opp_id, team_id),
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
        assert "Opponent" in resp.text


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



# ---------------------------------------------------------------------------
# E-220 proactive audit: admin cascade delete must handle new FK tables
# ---------------------------------------------------------------------------


class TestE220CascadeDeletion:
    """E-220 proactive audit finding: _delete_team_cascade() was missing
    plays, play_events, game_perspectives, and reconciliation_discrepancies
    deletion.  These tables all have FKs to games or plays, so DELETE FROM
    games would raise IntegrityError when any of them have rows.
    """

    def test_cascade_deletes_plays_and_children(self, db: Path) -> None:
        """Cascade delete must remove plays, play_events, game_perspectives,
        and reconciliation_discrepancies for games involving the team.

        RED test: without the fix, DELETE FROM games raises
        FOREIGN KEY constraint failed because the child tables still
        reference the game rows.
        """
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        player_batter_id = _insert_player(db, "p-batter")
        player_pitcher_id = _insert_player(db, "p-pitcher")

        team_id = _insert_team(db, "Delete Me", membership_type="member")
        opp_id = _insert_team(db, "Opponent", membership_type="tracked")
        game_id = _insert_game(db, "game-plays-001", team_id, opp_id, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")

        # Seed plays data (with perspective_team_id, both team perspectives)
        conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, batting_team_id, "
            "perspective_team_id, batter_id, pitcher_id) "
            "VALUES (?, 1, 1, 'top', ?, ?, ?, ?, ?)",
            (game_id, season_id, opp_id, team_id, player_batter_id, player_pitcher_id),
        )
        play_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # play_events row -- FK to plays.id
        conn.execute(
            "INSERT INTO play_events (play_id, event_order, event_type) "
            "VALUES (?, 1, 'pitch')",
            (play_id,),
        )

        # Seed game_perspectives -- FK to games.game_id
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            (game_id, team_id),
        )
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            (game_id, opp_id),
        )

        # Seed reconciliation_discrepancies -- FK to games.game_id
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, signal_name, category, status) "
            "VALUES (?, 'run-x', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, team_id, team_id, player_pitcher_id),
        )

        # Also seed batting/pitching/spray data so the existing Phase 1 runs.
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_batter_id, team_id, team_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_pitcher_id, team_id, team_id),
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

        # Must not raise FK error -- status should be 303 redirect after successful delete
        assert resp.status_code == 303, (
            f"Expected 303 redirect, got {resp.status_code}. "
            f"Response body: {resp.text[:500]}"
        )

        # Team row is gone
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 0
        # Phase 2: game is gone
        assert _count_rows(db, "games", "game_id = ?", (game_id,)) == 0
        # Phase 1 new tables: all children deleted
        assert _count_rows(db, "plays", "game_id = ?", (game_id,)) == 0
        assert _count_rows(db, "play_events", "play_id = ?", (play_id,)) == 0
        assert _count_rows(db, "game_perspectives", "game_id = ?", (game_id,)) == 0
        assert _count_rows(
            db, "reconciliation_discrepancies", "game_id = ?", (game_id,)
        ) == 0



# ---------------------------------------------------------------------------
# Round 6 Cluster 3: informed-consent cross-perspective delete (Option B)
# ---------------------------------------------------------------------------


class TestCrossPerspectiveOwnersPreview:
    """Round 6 Cluster 3: preview reports cross_perspective_owners list."""

    def test_delete_team_preview_reports_cross_perspective_owners(
        self, db: Path
    ) -> None:
        """Team T has rows where team_id=T, perspective_team_id=O.  The
        preview must list O with the correct row count.
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Subject", membership_type="tracked")
        owner_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        owner2_id = _insert_team(db, "Lincoln JV", membership_type="member")
        game_id = _insert_game(db, "g-cp1", team_id, owner_id, season_id)
        player = _insert_player(db, "p-1")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # team_id=subject, perspective_team_id=owner  (cross-perspective rows)
        # Insert 3 from Lincoln Varsity, 2 from Lincoln JV.
        for _ in range(3):
            conn.execute(
                "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
                "VALUES (?, 'Lv', 'Player')",
                (f"p-lv-{_}",),
            )
            conn.execute(
                "INSERT INTO player_game_batting "
                "(game_id, player_id, team_id, perspective_team_id) "
                "VALUES (?, ?, ?, ?)",
                (game_id, f"p-lv-{_}", team_id, owner_id),
            )
        for _ in range(2):
            conn.execute(
                "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
                "VALUES (?, 'Lj', 'Player')",
                (f"p-lj-{_}",),
            )
            conn.execute(
                "INSERT INTO player_game_batting "
                "(game_id, player_id, team_id, perspective_team_id) "
                "VALUES (?, ?, ?, ?)",
                (game_id, f"p-lj-{_}", team_id, owner2_id),
            )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_id)

        assert "cross_perspective_owners" in preview, (
            "preview must expose cross_perspective_owners field"
        )
        owners = preview["cross_perspective_owners"]
        assert len(owners) == 2, f"expected 2 owners, got {owners}"
        # Ordered by row_count DESC per DE's sketch
        assert owners[0]["name"] == "Lincoln Varsity"
        assert owners[0]["row_count"] == 3
        assert owners[0]["id"] == owner_id
        assert owners[1]["name"] == "Lincoln JV"
        assert owners[1]["row_count"] == 2
        assert owners[1]["id"] == owner2_id

    def test_delete_team_preview_empty_cross_perspective_for_clean_team(
        self, db: Path
    ) -> None:
        """Team with only own-perspective rows produces empty owners list."""
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Clean", membership_type="member")
        other_id = _insert_team(db, "Opponent", membership_type="tracked")
        game_id = _insert_game(db, "g-clean", team_id, other_id, season_id)
        player = _insert_player(db, "p-c")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Only own-perspective rows
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player, team_id, team_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_id)

        assert preview.get("cross_perspective_owners", []) == [], (
            "clean team should have empty cross_perspective_owners list"
        )


class TestCrossPerspectiveDeleteConfirmation:
    """Round 6 Cluster 3: route handler gates delete on named confirmation."""

    def test_delete_team_blocks_when_cross_perspective_confirmation_missing(
        self, db: Path
    ) -> None:
        """POST without confirm_cross_perspective when team has cross-persp
        rows re-renders the confirmation page WITHOUT performing delete.
        """
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Subject", membership_type="tracked")
        owner_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        game_id = _insert_game(db, "g-block", team_id, owner_id, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Cross-perspective row: team_id=subject but perspective_team_id=owner
        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES ('p-cp', 'CP', 'Player')"
        )
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, "p-cp", team_id, owner_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                # POST WITHOUT confirm_cross_perspective
                resp = client.post(
                    f"/admin/teams/{team_id}/delete",
                    data={"csrf_token": _CSRF},
                )

        # Re-renders the confirmation page (200 OK), not a 303 redirect
        assert resp.status_code == 200, (
            f"expected 200 re-render, got {resp.status_code}"
        )
        # Response body should mention the cross-perspective owner by name
        assert "Lincoln Varsity" in resp.text, (
            "response must name the specific owner team"
        )
        # The team row must still exist (not deleted)
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 1, (
            "team should NOT have been deleted"
        )
        # The cross-perspective rows must still exist
        assert _count_rows(
            db, "player_game_batting", "game_id = ?", (game_id,)
        ) == 1

    def test_delete_team_proceeds_with_cross_perspective_confirmation(
        self, db: Path
    ) -> None:
        """POST with confirm_cross_perspective=1 completes the delete.
        Both team_id=T rows and perspective_team_id=T rows are removed.
        """
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Subject", membership_type="tracked")
        owner_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        other_team = _insert_team(db, "Other Team", membership_type="tracked")
        game1 = _insert_game(db, "g-proceed1", team_id, owner_id, season_id)
        game2 = _insert_game(db, "g-proceed2", other_team, owner_id, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executemany(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES (?, 'X', 'X')",
            [("p-a",), ("p-b",)],
        )
        # Row 1: team_id=subject, perspective_team_id=owner (cross-persp "about" subject)
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game1, "p-a", team_id, owner_id),
        )
        # Row 2: team_id=other_team, perspective_team_id=subject
        #        (subject's own-perspective data "about" other_team)
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game2, "p-b", other_team, team_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                resp = client.post(
                    f"/admin/teams/{team_id}/delete",
                    data={"csrf_token": _CSRF, "confirm_cross_perspective": "1"},
                )

        assert resp.status_code == 303, (
            f"expected 303 redirect after successful delete, got {resp.status_code}"
        )
        # Subject team row gone
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 0
        # Row 1 (team_id=subject) is gone
        assert _count_rows(
            db, "player_game_batting", "game_id = ?", (game1,)
        ) == 0
        # Row 2 (perspective_team_id=subject) is gone -- its perspective FK
        # is the subject team, which no longer exists
        assert _count_rows(
            db, "player_game_batting", "perspective_team_id = ?", (team_id,)
        ) == 0

    def test_delete_team_proceeds_without_flag_when_no_cross_perspective(
        self, db: Path
    ) -> None:
        """Clean team (no cross-persp rows) deletes without the flag."""
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Clean", membership_type="member")
        opp_id = _insert_team(db, "Opp", membership_type="tracked")
        game_id = _insert_game(db, "g-clean2", team_id, opp_id, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES ('p-own', 'Own', 'Player')"
        )
        # Only own-perspective rows
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, "p-own", team_id, team_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                resp = client.post(
                    f"/admin/teams/{team_id}/delete",
                    data={"csrf_token": _CSRF},  # no confirm flag
                )

        assert resp.status_code == 303, (
            "clean team delete should proceed without the flag"
        )
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 0


# ---------------------------------------------------------------------------
# E-221-04 (R8-P1-1): cross-perspective stat rows must survive admin cascade
# ---------------------------------------------------------------------------


class TestCascadePreservesOtherPerspectiveRows:
    """E-221-04 / R8-P1-1: deleting team A must NOT wipe team B's perspective
    rows for a game they both loaded.

    E-220 round 8 discovered that ``_delete_team_cascade`` Phase 1a deletes
    perspective-carrying stat rows by ``game_id IN (...)`` without any
    ``perspective_team_id`` filter.  When two teams have both loaded the same
    game from their own boxscores (producing separate rows with distinct
    ``perspective_team_id`` values), deleting either team wipes BOTH
    perspectives' rows.  The fix (Story E-221-05) scopes Phase 1a by
    ``perspective_team_id = T`` on every affected DELETE.

    This test is the RED half of the RED-GREEN sequence.  It FAILS against
    the broken code E-221-04 is landing against and will PASS after E-221-05
    lands the Phase 1a scoping fix.  See TN-4 / TN-5 in the E-221 epic.
    """

    def test_delete_team_cascade_preserves_other_perspective_rows(
        self, db: Path
    ) -> None:
        """Given a game loaded from two perspectives, deleting team A must
        leave team B's perspective stat rows in all 5 tables intact, and
        must preserve the ``games`` row because team B still has an entry in
        ``game_perspectives``.

        Asserts:
          - (AC-1) Team A's perspective rows are gone from all 5 tables.
          - (AC-1) Team B's perspective rows are STILL PRESENT in:
                plays, spray_charts, player_game_batting,
                player_game_pitching, reconciliation_discrepancies
          - (AC-2) The games row for the shared game_id is preserved.
          - (AC-2) game_perspectives still has team B's entry for the game.

        Pre-E-221-05, this test FAILS because Phase 1a's unscoped DELETEs
        wipe team B's rows and Phase 2 unconditionally deletes the games row.
        """
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)

        # Team A is the delete target (member).  Team B is the peer that
        # also loaded the same game from its own perspective (tracked).
        team_a_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        team_b_id = _insert_team(db, "Rival Varsity", membership_type="tracked")

        # One shared game where team A is home, team B is away.
        game_id = _insert_game(
            db, "g-shared-xperspective", team_a_id, team_b_id, season_id,
        )

        # Distinct players for each perspective so UNIQUE(game_id, player_id,
        # perspective_team_id) never collides.
        batter_a = _insert_player(db, "p-batter-a")
        batter_b = _insert_player(db, "p-batter-b")
        pitcher_a = _insert_player(db, "p-pitcher-a")
        pitcher_b = _insert_player(db, "p-pitcher-b")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")

        # --- Seed team A's perspective of the game ---
        conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, batting_team_id, "
            "perspective_team_id, batter_id, pitcher_id) "
            "VALUES (?, 1, 1, 'top', ?, ?, ?, ?, ?)",
            (game_id, season_id, team_b_id, team_a_id, batter_b, pitcher_a),
        )
        play_id_a = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO play_events (play_id, event_order, event_type) "
            "VALUES (?, 1, 'pitch')",
            (play_id_a,),
        )
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, batter_b, team_b_id, team_a_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, pitcher_a, team_a_id, team_a_id),
        )
        conn.execute(
            "INSERT INTO spray_charts (game_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?)",
            (game_id, team_a_id, team_a_id),
        )
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-a', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, team_a_id, team_a_id, pitcher_a),
        )
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_a_id),
        )

        # --- Seed team B's perspective of the same game ---
        conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, batting_team_id, "
            "perspective_team_id, batter_id, pitcher_id) "
            "VALUES (?, 1, 1, 'top', ?, ?, ?, ?, ?)",
            (game_id, season_id, team_b_id, team_b_id, batter_a, pitcher_b),
        )
        play_id_b = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO play_events (play_id, event_order, event_type) "
            "VALUES (?, 1, 'pitch')",
            (play_id_b,),
        )
        # Team B's perspective rows anchor team_id to team B's directory
        # (NOT team A's), even when describing players who bat for team A.
        # Rationale: team_id is the FK to the "owning team" -- the directory
        # from which the scouting record was produced. When team A is
        # deleted, team B's records about team A's players/games must survive
        # because their FK anchor (team B) is untouched. The cascade deletes
        # by perspective_team_id = A, not by team_id = A.
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, batter_a, team_b_id, team_b_id),
        )
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, pitcher_b, team_b_id, team_b_id),
        )
        conn.execute(
            "INSERT INTO spray_charts (game_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?)",
            (game_id, team_b_id, team_b_id),
        )
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-b', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, team_b_id, team_b_id, pitcher_b),
        )
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_b_id),
        )
        conn.commit()
        conn.close()

        # Sanity check the fixture: each perspective-carrying table should
        # have one row per perspective before the cascade runs.  If this
        # fails, the fixture is broken and the test is meaningless.
        for table in (
            "plays", "player_game_batting", "player_game_pitching",
            "spray_charts", "reconciliation_discrepancies",
        ):
            pre_a = _count_rows(
                db, table, "perspective_team_id = ?", (team_a_id,),
            )
            pre_b = _count_rows(
                db, table, "perspective_team_id = ?", (team_b_id,),
            )
            assert pre_a == 1, f"fixture: {table} missing team A's row"
            assert pre_b == 1, f"fixture: {table} missing team B's row"

        # --- Run the cascade via the HTTP route with explicit cross-persp
        # confirmation (team A has cross-perspective rows from team B).
        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                resp = client.post(
                    f"/admin/teams/{team_a_id}/delete",
                    data={
                        "csrf_token": _CSRF,
                        "confirm_cross_perspective": "1",
                    },
                )

        assert resp.status_code == 303, (
            f"expected 303 redirect after delete; got {resp.status_code}. "
            f"body: {resp.text[:500]}"
        )

        # --- AC-1: team A's perspective rows are GONE from all 5 tables ---
        for table in (
            "plays", "player_game_batting", "player_game_pitching",
            "spray_charts", "reconciliation_discrepancies",
        ):
            assert _count_rows(
                db, table, "perspective_team_id = ?", (team_a_id,),
            ) == 0, f"team A's perspective rows should be deleted from {table}"

        # --- AC-1 (the bug): team B's perspective rows MUST survive ---
        for table in (
            "plays", "player_game_batting", "player_game_pitching",
            "spray_charts", "reconciliation_discrepancies",
        ):
            surviving = _count_rows(
                db, table, "perspective_team_id = ?", (team_b_id,),
            )
            assert surviving == 1, (
                f"R8-P1-1: team B's perspective row in {table} was wiped by "
                f"the unscoped `game_id IN (...)` DELETE in Phase 1a. "
                f"Expected 1 surviving row, got {surviving}."
            )

        # --- AC-2: the games row is preserved because team B still owns a
        # game_perspectives entry.  Pre-E-221-05, Phase 2 unconditionally
        # deletes games where team A is a participant, so this fails too.
        assert _count_rows(db, "games", "game_id = ?", (game_id,)) == 1, (
            "R8-P1-1 (AC-2): games row should be preserved because team B "
            "still has a game_perspectives entry. Pre-fix, Phase 2's "
            "`DELETE FROM games WHERE home_team_id = ? OR away_team_id = ?` "
            "removes it unconditionally."
        )
        assert _count_rows(
            db, "game_perspectives",
            "game_id = ? AND perspective_team_id = ?",
            (game_id, team_b_id),
        ) == 1, (
            "team B's game_perspectives entry should survive the cascade"
        )
        assert _count_rows(
            db, "teams", "id = ?", (team_b_id,),
        ) == 1, "team B row should be unaffected by deleting team A"
