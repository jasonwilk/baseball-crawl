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
        """Cascade delete must remove the deleted team's perspective rows
        from plays, play_events, game_perspectives, and
        reconciliation_discrepancies without raising an FK error.

        Updated in E-221-05 for the perspective-aware semantics: when the
        game is owned by MORE than one perspective (here: team_id and
        opp_id both have game_perspectives entries), the games row is
        preserved because another perspective still depends on it.  The
        teams row is correspondingly retained because games.home_team_id
        still FK-references it.  Only the deleted team's perspective-
        scoped rows are cleaned; opp_id's perspective entry survives.
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

        # Seed plays data tagged with team_id's perspective.
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

        # Seed game_perspectives for BOTH teams -- this is the cross-
        # perspective preservation case: opp_id's entry survives the
        # cascade and keeps the games row (and therefore the teams row)
        # alive as an FK anchor.
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

        # Also seed batting/pitching data so the existing Phase 1 runs.
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

        # Team row is RETAINED: the surviving games row still FK-references
        # team_id via home_team_id, so the canonical cascade preserves the
        # teams row as an FK anchor (E-221-05 consolidation).
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 1
        # Games row is PRESERVED: opp_id still owns a game_perspectives entry,
        # so the NOT EXISTS guard in _delete_game_scoped_data_for_perspectives
        # skips the DELETE FROM games.
        assert _count_rows(db, "games", "game_id = ?", (game_id,)) == 1
        # team_id's perspective rows are cleaned from all four new tables
        # (this is what the original test was proving -- the E-220 proactive
        # audit cleanup of plays/play_events/game_perspectives/
        # reconciliation_discrepancies still works).
        assert _count_rows(
            db, "plays",
            "game_id = ? AND perspective_team_id = ?",
            (game_id, team_id),
        ) == 0
        assert _count_rows(db, "play_events", "play_id = ?", (play_id,)) == 0
        assert _count_rows(
            db, "game_perspectives",
            "game_id = ? AND perspective_team_id = ?",
            (game_id, team_id),
        ) == 0
        assert _count_rows(
            db, "reconciliation_discrepancies",
            "game_id = ? AND perspective_team_id = ?",
            (game_id, team_id),
        ) == 0
        # opp_id's perspective entry in game_perspectives is preserved --
        # it's what keeps the games row alive.
        assert _count_rows(
            db, "game_perspectives",
            "game_id = ? AND perspective_team_id = ?",
            (game_id, opp_id),
        ) == 1



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


# ---------------------------------------------------------------------------
# E-221-06 (R8-P1-2): reconciliation_discrepancies cascade regression bulwark
# ---------------------------------------------------------------------------


class TestReconciliationDiscrepanciesCascade:
    """E-221-06 / R8-P1-2: explicit regression gate for the
    ``reconciliation_discrepancies`` cleanup paths in the canonical cascade.

    The functional fix shipped in E-221-05 via the Option 2 refactor that
    delegates ``src/api/routes/admin.py::_delete_team_cascade`` to
    ``src/reports/generator.py::cascade_delete_team``.  The canonical helper's
    ``_delete_team_anchor_and_orphan_data`` function cleans reconciliation
    rows via two independent DELETE paths:

      - Pass 1 (perspective, ``generator.py:1445-1448``):
        ``DELETE FROM reconciliation_discrepancies WHERE perspective_team_id = ?``
      - Pass 2 (anchor, ``generator.py:1476-1478``):
        ``DELETE FROM reconciliation_discrepancies WHERE team_id = ?``

    E-221-05's test coverage hits these transitively through the E-221-04 RED
    test.  This class adds the explicit R8-P1-2 regression gate so a future
    refactor that accidentally drops one of the two passes fails fast with a
    named test rather than cascading into broader assertions.  Either pass
    being dropped would cause the admin team delete to FK-violate at Phase 4;
    these tests catch that.

    FK enforcement (AC-2) comes through the existing ``db`` fixture: ``_make_db``
    calls ``run_migrations`` which applies ``migrations/001_initial_schema.sql``
    via ``apply_migrations.py:131`` using
    ``executescript("PRAGMA foreign_keys=ON;\\n" + sql)`` -- byte-identical to
    ``tests/conftest.py::load_real_schema(conn)`` for AC-2 purposes.  Both
    tests also redundantly set ``PRAGMA foreign_keys=ON`` on every helper-
    opened connection before seeding.
    """

    def test_perspective_pass_cleans_rows_owned_by_deleted_team(
        self, db: Path
    ) -> None:
        """Pass 1 regression: a reconciliation row with
        ``perspective_team_id = T AND team_id = T`` is deleted when team T
        is deleted, the teams row is removed, and the HTTP handler returns
        303.  No FK violation at any step.

        Covers ``src/reports/generator.py:1445-1448`` (the perspective pass
        DELETE on reconciliation_discrepancies).
        """
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        pitcher_id = _insert_player(db, "p-recon-p1")

        team_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        opp_id = _insert_team(db, "Opponent", membership_type="tracked")
        game_id = _insert_game(
            db, "g-recon-own", team_id, opp_id, season_id,
        )

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Own-perspective reconciliation row: team_id = T, perspective = T.
        # This is the common path -- not cross-perspective, no confirm flag
        # required.  If _delete_team_anchor_and_orphan_data's Pass 1 regresses
        # (perspective DELETE on recon table removed), the Phase 4 teams row
        # delete fires the team_id FK constraint.
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-own', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, team_id, team_id, pitcher_id),
        )
        conn.commit()
        conn.close()

        # Fixture sanity check -- must have one recon row anchored to team T.
        assert _count_rows(
            db, "reconciliation_discrepancies",
            "game_id = ? AND perspective_team_id = ?",
            (game_id, team_id),
        ) == 1

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                resp = client.post(
                    f"/admin/teams/{team_id}/delete",
                    data={"csrf_token": _CSRF},
                )

        # AC-1(a): HTTP response 303 (delete succeeded, no FK violation).
        assert resp.status_code == 303, (
            f"expected 303 redirect after delete; got {resp.status_code}. "
            f"body: {resp.text[:500]}"
        )
        # AC-1(b): the reconciliation row is gone.
        assert _count_rows(
            db, "reconciliation_discrepancies",
            "perspective_team_id = ?",
            (team_id,),
        ) == 0, (
            "R8-P1-2 Pass 1 regression: reconciliation_discrepancies row "
            "with perspective_team_id = deleted team should be cleaned by "
            "_delete_team_anchor_and_orphan_data Pass 1."
        )
        # AC-1(c): the teams row is gone.
        assert _count_rows(
            db, "teams", "id = ?", (team_id,),
        ) == 0, (
            "teams row for the deleted team should be gone post-cascade"
        )

    def test_anchor_pass_cleans_rows_about_deleted_team(
        self, db: Path
    ) -> None:
        """Pass 2 regression: a reconciliation row with
        ``team_id = T AND perspective_team_id = OTHER`` (another team's
        scouting record ABOUT team T's player) is deleted when team T is
        deleted.  The row is NOT caught by Pass 1 (wrong perspective); it
        must be cleaned by Pass 2.  Covers
        ``src/reports/generator.py:1476-1478`` (the anchor pass DELETE on
        reconciliation_discrepancies).

        Without Pass 2, the Phase 4 teams row delete fires the
        ``reconciliation_discrepancies.team_id -> teams(id)`` FK constraint
        and the cascade raises ``IntegrityError``.  A cross-perspective
        ``player_game_batting`` row is also seeded so the cross-perspective
        detector in ``_get_delete_confirmation_data`` (admin.py:835-864)
        fires and the test exercises the ``confirm_cross_perspective=1``
        code path, matching the realistic UX flow for this scenario.
        """
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        pitcher_id = _insert_player(db, "p-recon-p2")
        batter_id = _insert_player(db, "p-recon-b2")

        team_id = _insert_team(db, "Subject Team", membership_type="tracked")
        other_id = _insert_team(db, "Owner Team", membership_type="member")
        game_id = _insert_game(
            db, "g-recon-xperspective", team_id, other_id, season_id,
        )

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Cross-perspective reconciliation row: anchored to team T (the one
        # being deleted) but tagged with another team's perspective.  This
        # is "owner team's scouting record about subject team's game".
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-xp', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, other_id, team_id, pitcher_id),
        )
        # Cross-perspective batting row with the same anchor shape; this is
        # what the cross-perspective detector (admin.py:835-864) looks at.
        # Its presence ensures the confirm_cross_perspective flag path is
        # exercised alongside the recon cleanup -- the detector does not
        # currently inspect reconciliation_discrepancies directly.
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, batter_id, team_id, other_id),
        )
        conn.commit()
        conn.close()

        # Fixture sanity check: one recon row anchored to T with foreign
        # perspective; one cross-persp batting row to trigger the detector.
        assert _count_rows(
            db, "reconciliation_discrepancies",
            "team_id = ? AND perspective_team_id = ?",
            (team_id, other_id),
        ) == 1
        assert _count_rows(
            db, "player_game_batting",
            "team_id = ? AND perspective_team_id = ?",
            (team_id, other_id),
        ) == 1

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                resp = client.post(
                    f"/admin/teams/{team_id}/delete",
                    data={
                        "csrf_token": _CSRF,
                        "confirm_cross_perspective": "1",
                    },
                )

        # AC-3(a): HTTP response 303 (delete succeeded, no FK violation).
        assert resp.status_code == 303, (
            f"expected 303 redirect after delete; got {resp.status_code}. "
            f"body: {resp.text[:500]}"
        )
        # AC-3(b): the cross-perspective reconciliation row anchored to T
        # is gone.  Specifically the team_id filter -- Pass 2 is what
        # cleans this.
        assert _count_rows(
            db, "reconciliation_discrepancies",
            "team_id = ?",
            (team_id,),
        ) == 0, (
            "R8-P1-2 Pass 2 regression: reconciliation_discrepancies row "
            "with team_id = deleted team (but foreign perspective_team_id) "
            "should be cleaned by _delete_team_anchor_and_orphan_data Pass 2."
        )
        # AC-3(c): the teams row is gone.
        assert _count_rows(
            db, "teams", "id = ?", (team_id,),
        ) == 0, (
            "teams row for the deleted team should be gone post-cascade"
        )
        # Sanity: the other team is untouched.
        assert _count_rows(
            db, "teams", "id = ?", (other_id,),
        ) == 1, (
            "the other team's row should be unaffected by deleting team T"
        )


# ---------------------------------------------------------------------------
# E-221 Phase 4b remediation (Codex review findings 1 and 2)
# ---------------------------------------------------------------------------


class TestE221Phase4bRemediation:
    """Phase 4b remediation tests for Codex-identified findings:

    - Finding 1 (MUST FIX): The informed-consent gate at
      ``_get_delete_confirmation_data`` did not inspect
      ``reconciliation_discrepancies``, so a team with ONLY foreign-owned
      reconciliation rows could silently bypass the confirmation screen and
      have another team's perspective data deleted without explicit operator
      consent.  Fix: add reconciliation_discrepancies to the
      ``cross_perspective_owners`` UNION at ``admin.py:835-868``.

    - Finding 2 (SHOULD FIX): After E-221-05's canonical cascade
      consolidation, ``cascade_delete_team`` can retain the teams row when
      cross-perspective games still reference it
      (``src/reports/generator.py:1540-1558``).  The admin delete HTTP handler
      previously flashed ``Team "X" deleted.`` unconditionally, which was a
      lie in the retention case.  Fix: post-cascade probe of the teams row
      and surface an accurate flash message.
    """

    def test_gate_detects_foreign_reconciliation_rows_only(
        self, db: Path
    ) -> None:
        """Finding 1 regression: a team whose ONLY cross-perspective
        footprint is in ``reconciliation_discrepancies`` must appear in
        ``cross_perspective_owners`` and trigger the confirmation gate.

        Pre-fix, a team with no cross-perspective batting/pitching/
        spray/plays rows but with a foreign-owned reconciliation row would
        see an empty ``cross_perspective_owners`` list and the
        ``has_cross_perspective`` gate would be False, allowing the delete
        to proceed without the ``confirm_cross_perspective`` flag.
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Subject", membership_type="tracked")
        owner_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        game_id = _insert_game(db, "g-recon-gate", team_id, owner_id, season_id)
        pitcher_id = _insert_player(db, "p-recon-only")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # ONE cross-perspective reconciliation row; nothing in any other
        # stat table.  Pre-fix, the gate query would find zero rows because
        # the UNION only looked at 4 tables.
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-gate', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, owner_id, team_id, pitcher_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_id)

        owners = preview.get("cross_perspective_owners", [])
        assert len(owners) == 1, (
            f"Finding 1: gate must detect the foreign-owned reconciliation "
            f"row. Expected 1 owner, got {owners}."
        )
        assert owners[0]["id"] == owner_id, (
            f"owner id should be {owner_id}, got {owners[0]['id']}"
        )
        assert owners[0]["name"] == "Lincoln Varsity"
        assert owners[0]["row_count"] == 1

    def test_gate_blocks_delete_with_reconciliation_only_cross_perspective(
        self, db: Path
    ) -> None:
        """Finding 1 end-to-end: the HTTP delete route must re-render the
        confirmation page (not execute the cascade) when the team's only
        cross-perspective footprint is foreign-owned reconciliation rows.

        Pre-fix, the gate returned empty ``cross_perspective_owners``, the
        ``has_cross_perspective`` check at ``admin.py:2416`` was False, and
        the delete proceeded silently.  Post-fix, the gate detects the
        reconciliation row and the route re-renders with
        ``warning=confirmation_required``.
        """
        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Subject", membership_type="tracked")
        owner_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        game_id = _insert_game(db, "g-recon-route", team_id, owner_id, season_id)
        pitcher_id = _insert_player(db, "p-recon-route")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-route', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, owner_id, team_id, pitcher_id),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app, follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                # POST WITHOUT confirm_cross_perspective -- pre-fix would
                # silently delete; post-fix must re-render the gate page.
                resp = client.post(
                    f"/admin/teams/{team_id}/delete",
                    data={"csrf_token": _CSRF},
                )

        assert resp.status_code == 200, (
            f"Finding 1: expected 200 re-render (gate fires on foreign recon "
            f"rows), got {resp.status_code}. body: {resp.text[:500]}"
        )
        # Response must name the specific owner team that owns the recon row.
        assert "Lincoln Varsity" in resp.text, (
            "confirmation page must name the cross-perspective owner"
        )
        # The team row must still exist (delete was blocked by the gate).
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 1, (
            "team should NOT have been deleted when gate fires"
        )
        # The reconciliation row must still exist.
        assert _count_rows(
            db, "reconciliation_discrepancies", "team_id = ?", (team_id,)
        ) == 1, "foreign-owned reconciliation row should survive the gate"

    def test_flash_message_reflects_team_row_retention(
        self, db: Path
    ) -> None:
        """Finding 2: when the cascade retains the teams row (because a
        surviving cross-perspective games row still FK-references it), the
        admin delete route must emit an accurate flash message -- not a
        blanket ``Team "X" deleted.`` lie.

        This test seeds the same cross-perspective games shape as the
        E-221-04 RED test, invokes the delete with
        ``confirm_cross_perspective=1``, and asserts:
          - HTTP 303 redirect to /admin/teams (delete succeeded)
          - The redirect query string includes the retention message
          - The teams row is still present (retention path active)
          - The games row is still present (preservation path active)
        """
        from urllib.parse import unquote_plus

        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_a_id = _insert_team(db, "Lincoln Varsity", membership_type="member")
        team_b_id = _insert_team(db, "Rival Varsity", membership_type="tracked")
        game_id = _insert_game(
            db, "g-retain-msg", team_a_id, team_b_id, season_id,
        )
        batter_b = _insert_player(db, "p-batter-b-f2")
        pitcher_b = _insert_player(db, "p-pitcher-b-f2")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Seed minimal team B perspective data so cascade_delete_team
        # preserves the game (team B's game_perspectives row survives).
        # Team A gets a game_perspectives entry so the confirmation gate
        # detects cross-perspective and requires the confirm flag.
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_a_id),
        )
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_b_id),
        )
        # Team B cross-perspective batting row anchored to team A's directory
        # -- triggers the gate's cross_perspective_owners detection and gives
        # team B a reason to exist in the cascade context.
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, batter_b, team_a_id, team_b_id),
        )
        # Team B own-perspective row so team B has stat coverage of its own.
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, pitcher_b, team_b_id, team_b_id),
        )
        conn.commit()
        conn.close()

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

        # Delete succeeded at the HTTP layer (303 redirect).
        assert resp.status_code == 303, (
            f"expected 303 redirect, got {resp.status_code}. "
            f"body: {resp.text[:500]}"
        )

        # Retention path active: team A's row is still present because the
        # preserved games row still FK-references it.
        assert _count_rows(db, "teams", "id = ?", (team_a_id,)) == 1, (
            "Finding 2 precondition: teams row should be retained because "
            "a surviving games row still FK-references it"
        )
        # Preservation path active: the games row survives because team B
        # still owns a game_perspectives entry.
        assert _count_rows(db, "games", "game_id = ?", (game_id,)) == 1, (
            "Finding 2 precondition: games row should be preserved when "
            "another perspective still owns it"
        )

        # Flash message must reflect retention, not a blanket "deleted" lie.
        location = resp.headers.get("location", "")
        decoded_location = unquote_plus(location)
        assert "retained" in decoded_location, (
            f"Finding 2: flash message should mention retention, got: "
            f"{decoded_location}"
        )
        # The old blanket "deleted." phrasing should NOT appear for this
        # retention case.  (The word "deleted" may appear as part of
        # "data removed" or similar, but not as the standalone past-tense
        # team-row-deleted assertion.)
        assert "Team \"Lincoln Varsity\" deleted." not in decoded_location, (
            f"Finding 2: retention case must not use the blanket "
            f"'Team \"X\" deleted.' flash message. Got: {decoded_location}"
        )

    def test_flash_message_reports_deleted_in_clean_path(
        self, db: Path
    ) -> None:
        """Finding 2 AC-2 parallel: the common path (no retention) must
        still emit the original ``Team "X" deleted.`` flash message.

        Seeds a clean team with no cross-perspective footprint, invokes
        delete, asserts the flash still says "deleted" and the team row is
        actually gone.
        """
        from urllib.parse import unquote_plus

        admin_id = _insert_user(db, "admin@example.com")
        token = _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_id = _insert_team(db, "Solo Team", membership_type="member")
        opp_id = _insert_team(db, "Opp Team", membership_type="tracked")
        _insert_game(db, "g-solo", team_id, opp_id, season_id)

        with patch.dict("os.environ", _admin_env(db)):
            with TestClient(
                app,
                follow_redirects=False,
                cookies={"session": token, "csrf_token": _CSRF},
            ) as client:
                resp = client.post(
                    f"/admin/teams/{team_id}/delete",
                    data={"csrf_token": _CSRF},
                )

        assert resp.status_code == 303, (
            f"expected 303 redirect, got {resp.status_code}"
        )
        # Clean path: team row actually removed.
        assert _count_rows(db, "teams", "id = ?", (team_id,)) == 0, (
            "clean path: teams row should be gone"
        )
        # Flash message should still say "deleted" (no retention).
        location = resp.headers.get("location", "")
        decoded_location = unquote_plus(location)
        assert 'Team "Solo Team" deleted.' in decoded_location, (
            f"Finding 2 regression: clean-path flash must still say "
            f"'Team \"X\" deleted.'. Got: {decoded_location}"
        )


# ---------------------------------------------------------------------------
# E-223-01: Perspective-aware confirmation counts
# ---------------------------------------------------------------------------


class TestPerspectiveAwareConfirmationCounts:
    """E-223-01 AC-6: confirmation counts mirror the cascade two-pass logic.

    The cascade deletes via two passes:
      Pass 1: WHERE perspective_team_id = T
      Pass 2: WHERE team_id = T (or batting_team_id for plays)

    Counts must use the union of both passes (deduplicated via OR).
    Cross-perspective rows (perspective_team_id != T AND team_id != T)
    must NOT be counted.  Scouting rows where perspective_team_id = T
    but the team is not a game participant must be counted.
    """

    def test_excludes_cross_perspective_rows(self, db: Path) -> None:
        """Rows where both perspective_team_id and team_id belong to OTHER
        teams must not be counted in the deleted team's confirmation.

        Pre-fix (game-subquery pattern): these rows were overcounted because
        they happened to be in a game the deleted team participated in.
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_t = _insert_team(db, "Team T", membership_type="member")
        team_o = _insert_team(db, "Opponent", membership_type="tracked")
        game_id = _insert_game(db, "g-cross-1", team_t, team_o, season_id)
        player_t = _insert_player(db, "p-t-1")
        player_o = _insert_player(db, "p-o-1")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Row owned by team T (own perspective, own anchor) -- should count
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_t, team_t, team_t),
        )
        # Cross-perspective row: perspective=O, anchor=O.
        # In the same game as team T, but NOT owned by T at all.
        # Pre-fix: counted because game was in the subquery.
        # Post-fix: correctly excluded.
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_o, team_o, team_o),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_t)

        assert preview["player_game_batting"] == 1, (
            f"expected 1 (own row only), got {preview['player_game_batting']}. "
            f"Cross-perspective row must not be counted."
        )

    def test_includes_scouting_rows_in_non_participant_games(
        self, db: Path
    ) -> None:
        """Scouting rows where perspective_team_id = T but the team is NOT a
        game participant must be counted.

        Pre-fix (game-subquery pattern): these rows were undercounted because
        the game's home/away teams did not include T.
        Post-fix: counted via the perspective_team_id = T branch.
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_t = _insert_team(db, "Scout Team", membership_type="member")
        team_a = _insert_team(db, "Away Team", membership_type="tracked")
        team_h = _insert_team(db, "Home Team", membership_type="tracked")
        # Game between two OTHER teams -- team_t is not a participant
        game_id = _insert_game(db, "g-scout-1", team_h, team_a, season_id)
        player_a = _insert_player(db, "p-scouted")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Scouting row: team_t scouted a game it didn't play in.
        # perspective_team_id = team_t, team_id = team_a
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_a, team_a, team_t),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_t)

        assert preview["player_game_batting"] == 1, (
            f"expected 1 (scouting row from non-participant game), "
            f"got {preview['player_game_batting']}. Scouting rows must be counted."
        )

    def test_no_double_counting_when_both_fks_match(self, db: Path) -> None:
        """When perspective_team_id = T AND team_id = T on the same row, the
        row must be counted exactly once (OR deduplicates naturally).
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_t = _insert_team(db, "Both FK Team", membership_type="member")
        team_o = _insert_team(db, "Opponent", membership_type="tracked")
        game_id = _insert_game(db, "g-both-fk", team_t, team_o, season_id)
        player = _insert_player(db, "p-both-fk")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Both FKs point to team_t -- must count as 1 row, not 2
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player, team_t, team_t),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_t)

        assert preview["player_game_batting"] == 1, (
            f"expected 1 (deduped), got {preview['player_game_batting']}. "
            f"OR should not double-count rows where both FKs match."
        )

    def test_all_seven_tables_use_perspective_counts(self, db: Path) -> None:
        """All seven stat tables use perspective-aware counts.  Seeds one
        cross-perspective row per table (perspective=O, anchor=O) alongside
        one own row (perspective=T, anchor=T) and verifies each table counts
        exactly 1 (the own row), excluding the cross-perspective row.
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_t = _insert_team(db, "Team T Full", membership_type="member")
        team_o = _insert_team(db, "Opponent Full", membership_type="tracked")
        game_id = _insert_game(db, "g-all-7", team_t, team_o, season_id)
        player_t = _insert_player(db, "p-t-all7")
        player_o = _insert_player(db, "p-o-all7")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")

        # player_game_batting: own + cross-perspective
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_t, team_t, team_t),
        )
        conn.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_o, team_o, team_o),
        )

        # player_game_pitching: own + cross-perspective
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_t, team_t, team_t),
        )
        conn.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, player_o, team_o, team_o),
        )

        # spray_charts: own + cross-perspective
        conn.execute(
            "INSERT INTO spray_charts "
            "(game_id, player_id, team_id, perspective_team_id, "
            "x, y, play_type, play_result) "
            "VALUES (?, ?, ?, ?, 0.5, 0.5, 'GB', 'OUT')",
            (game_id, player_t, team_t, team_t),
        )
        conn.execute(
            "INSERT INTO spray_charts "
            "(game_id, player_id, team_id, perspective_team_id, "
            "x, y, play_type, play_result) "
            "VALUES (?, ?, ?, ?, 0.5, 0.5, 'GB', 'OUT')",
            (game_id, player_o, team_o, team_o),
        )

        # plays: own (perspective=T, batting=T) + cross-perspective
        cur_own = conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "perspective_team_id, batting_team_id, batter_id) "
            "VALUES (?, 1, 1, 'top', ?, ?, ?, ?)",
            (game_id, season_id, team_t, team_t, player_t),
        )
        play_own_id = cur_own.lastrowid
        cur_cross = conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "perspective_team_id, batting_team_id, batter_id) "
            "VALUES (?, 2, 1, 'bottom', ?, ?, ?, ?)",
            (game_id, season_id, team_o, team_o, player_o),
        )
        play_cross_id = cur_cross.lastrowid

        # play_events: one under each play
        conn.execute(
            "INSERT INTO play_events "
            "(play_id, event_order, event_type) "
            "VALUES (?, 0, 'pitch')",
            (play_own_id,),
        )
        conn.execute(
            "INSERT INTO play_events "
            "(play_id, event_order, event_type) "
            "VALUES (?, 0, 'pitch')",
            (play_cross_id,),
        )

        # game_perspectives: own + other
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_t),
        )
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_o),
        )

        # reconciliation_discrepancies: own + cross-perspective
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-own', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, team_t, team_t, player_t),
        )
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(game_id, run_id, perspective_team_id, team_id, player_id, "
            "signal_name, category, status) "
            "VALUES (?, 'run-cross', ?, ?, ?, 'pitcher_bf', 'pitching', 'MATCH')",
            (game_id, team_o, team_o, player_o),
        )

        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_t)

        # Each table should count exactly 1 (the own row)
        assert preview["player_game_batting"] == 1, f"pgb: {preview['player_game_batting']}"
        assert preview["player_game_pitching"] == 1, f"pgp: {preview['player_game_pitching']}"
        assert preview["spray_charts"] == 1, f"sc: {preview['spray_charts']}"
        assert preview["plays"] == 1, f"plays: {preview['plays']}"
        assert preview["play_events"] == 1, (
            f"play_events: {preview['play_events']}"
        )
        assert preview["game_perspectives"] == 1, f"gp: {preview['game_perspectives']}"
        assert preview["reconciliation_discrepancies"] == 1, f"recon: {preview['reconciliation_discrepancies']}"

    def test_games_count_unchanged(self, db: Path) -> None:
        """AC-5: games_count uses team-participation, not perspective.
        Remains unchanged by the perspective-aware refactor.
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_t = _insert_team(db, "Games Team", membership_type="member")
        team_o = _insert_team(db, "Opp", membership_type="tracked")
        _insert_game(db, "g-gcount-1", team_t, team_o, season_id)
        _insert_game(db, "g-gcount-2", team_o, team_t, season_id)

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_t)

        assert preview["games"] == 2, (
            f"games_count should count participation, got {preview['games']}"
        )

    def test_play_events_cascade_through_plays(self, db: Path) -> None:
        """AC-3: play_events count cascades through plays using the same
        two-FK union (perspective_team_id OR batting_team_id on plays).
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_t = _insert_team(db, "PE Team", membership_type="member")
        team_o = _insert_team(db, "PE Opp", membership_type="tracked")
        game_id = _insert_game(db, "g-pe-casc", team_t, team_o, season_id)

        player_t = _insert_player(db, "p-pe-t")
        player_o = _insert_player(db, "p-pe-o")

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        # Play owned by team_t via perspective
        cur1 = conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "perspective_team_id, batting_team_id, batter_id) "
            "VALUES (?, 1, 1, 'top', ?, ?, ?, ?)",
            (game_id, season_id, team_t, team_o, player_o),
        )
        play_own_id = cur1.lastrowid
        # Play owned by team_t via batting (but perspective is O)
        cur2 = conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "perspective_team_id, batting_team_id, batter_id) "
            "VALUES (?, 2, 2, 'top', ?, ?, ?, ?)",
            (game_id, season_id, team_o, team_t, player_t),
        )
        play_bat_id = cur2.lastrowid
        # Play not owned by team_t at all
        cur3 = conn.execute(
            "INSERT INTO plays "
            "(game_id, play_order, inning, half, season_id, "
            "perspective_team_id, batting_team_id, batter_id) "
            "VALUES (?, 3, 3, 'top', ?, ?, ?, ?)",
            (game_id, season_id, team_o, team_o, player_o),
        )
        play_none_id = cur3.lastrowid
        # Events under each play (2 events per play)
        for pid in (play_own_id, play_bat_id, play_none_id):
            conn.execute(
                "INSERT INTO play_events (play_id, event_order, event_type) "
                "VALUES (?, 0, 'pitch')",
                (pid,),
            )
            conn.execute(
                "INSERT INTO play_events (play_id, event_order, event_type) "
                "VALUES (?, 1, 'pitch')",
                (pid,),
            )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_t)

        # 2 plays owned by T (perspective or batting), excluding the third
        assert preview["plays"] == 2, (
            f"expected 2 plays, got {preview['plays']}"
        )
        # 4 play_events (2 events per play * 2 owned plays)
        assert preview["play_events"] == 4, (
            f"expected 4 play_events, got {preview['play_events']}"
        )

    def test_game_perspectives_uses_perspective_only(self, db: Path) -> None:
        """AC-4: game_perspectives count uses perspective_team_id only,
        not any anchor FK.
        """
        from src.api.routes.admin import _get_delete_confirmation_data

        admin_id = _insert_user(db, "admin@example.com")
        _insert_session(db, admin_id)
        season_id = _insert_season(db)
        team_t = _insert_team(db, "GP Team", membership_type="member")
        team_o = _insert_team(db, "GP Opp", membership_type="tracked")
        game_id = _insert_game(db, "g-gp-only", team_t, team_o, season_id)

        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_t),
        )
        conn.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, team_o),
        )
        conn.commit()
        conn.close()

        with patch.dict("os.environ", _admin_env(db)):
            preview = _get_delete_confirmation_data(team_t)

        # Only the team_t perspective row should be counted
        assert preview["game_perspectives"] == 1, (
            f"expected 1 (own perspective only), got {preview['game_perspectives']}"
        )
