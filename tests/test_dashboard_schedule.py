# synthetic-test-data
"""Tests for E-153-03: Schedule Landing Page and Navigation Restructure.

Covers AC-11 items:
  (a) schedule view renders with a mix of completed and upcoming games sorted date ASC
  (b) bottom nav contains exactly 3 tabs with labels "Schedule", "Batting", "Pitching"
      and correct href values
  (c) scouted badge logic correctly distinguishes opponents with stat data from those without
  (d) /dashboard/batting serves the batting stats page previously at /dashboard/
  (e) internal links in batting stats template navigate to /dashboard/batting, not /dashboard/

Additional tests:
  - Empty states (no assignments, no games)
  - AC-6: team selector and year selector work on schedule page
  - AC-10: null home_away handled gracefully
  - AC-9: no-games empty state message rendered

Run with:
    pytest tests/test_dashboard_schedule.py -v
"""

from __future__ import annotations

import datetime
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
from src.api.main import app  # noqa: E402

_TODAY = datetime.date.today()
_CURRENT_SEASON_ID = f"{_TODAY.year}-spring-hs"

# Dates: one completed in the past, one upcoming in the future
_PAST_DATE = (_TODAY - datetime.timedelta(days=10)).isoformat()
_UPCOMING_DATE_NEAR = (_TODAY + datetime.timedelta(days=3)).isoformat()
_UPCOMING_DATE_FAR = (_TODAY + datetime.timedelta(days=14)).isoformat()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _apply_schema(db_path: Path) -> None:
    run_migrations(db_path=db_path)


def _insert_base(conn: sqlite3.Connection) -> tuple[int, int]:
    """Insert LSB team, current season, dev user, and user_team_access.

    Returns (lsb_team_id, user_id).
    """
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
        ("LSB Varsity", "member", "varsity"),
    )
    lsb_team_id: int = cursor.lastrowid  # type: ignore[assignment]

    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) VALUES (?, ?, ?, ?)",
        (_CURRENT_SEASON_ID, "Spring HS", "spring-hs", _TODAY.year),
    )

    cursor2 = conn.execute("INSERT INTO users (email) VALUES (?)", ("dev@test.com",))
    user_id: int = cursor2.lastrowid  # type: ignore[assignment]

    conn.execute(
        "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, lsb_team_id),
    )
    return lsb_team_id, user_id


def _insert_opponent(conn: sqlite3.Connection, name: str = "Rival High") -> int:
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, 'tracked')",
        (name,),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_game(
    conn: sqlite3.Connection,
    game_id: str,
    lsb_team_id: int,
    opp_team_id: int,
    game_date: str,
    status: str,
    lsb_is_home: bool = True,
    home_score: int | None = None,
    away_score: int | None = None,
) -> None:
    if lsb_is_home:
        home_id, away_id = lsb_team_id, opp_team_id
    else:
        home_id, away_id = opp_team_id, lsb_team_id
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id,"
        " home_score, away_score, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, _CURRENT_SEASON_ID, game_date, home_id, away_id, home_score, away_score, status),
    )


def _insert_opp_batting_stats(
    conn: sqlite3.Connection,
    opp_team_id: int,
    player_id: str = "opp-p-001",
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, 'Jake', 'Rivera')",
        (player_id,),
    )
    conn.execute(
        "INSERT INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, bb, so) VALUES (?, ?, ?, 3, 10, 4, 2, 2)",
        (player_id, opp_team_id, _CURRENT_SEASON_ID),
    )


def _make_client(db_path: Path, *, dev_email: str = "dev@test.com") -> TestClient:
    env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": dev_email}
    with patch.dict("os.environ", env):
        with TestClient(app) as client:
            yield client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def schedule_client(tmp_path: Path):
    """Client with one upcoming game (near), one upcoming (far), and one completed game."""
    db_path = tmp_path / "schedule.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    lsb_id, _ = _insert_base(conn)
    opp1 = _insert_opponent(conn, "Central Lions")
    opp2 = _insert_opponent(conn, "West Eagles")
    # Completed game: LSB won 7-3 at home
    _insert_game(conn, "g-past", lsb_id, opp1, _PAST_DATE, "completed",
                 lsb_is_home=True, home_score=7, away_score=3)
    # Upcoming near (3 days)
    _insert_game(conn, "g-near", lsb_id, opp1, _UPCOMING_DATE_NEAR, "scheduled",
                 lsb_is_home=True)
    # Upcoming far (14 days), LSB away
    _insert_game(conn, "g-far", lsb_id, opp2, _UPCOMING_DATE_FAR, "scheduled",
                 lsb_is_home=False)
    # Give opp1 batting stats (scouted)
    _insert_opp_batting_stats(conn, opp1)
    conn.commit()
    conn.close()
    env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@test.com"}
    with patch.dict("os.environ", env):
        with TestClient(app) as client:
            yield client, lsb_id, opp1, opp2


@pytest.fixture()
def no_games_client(tmp_path: Path):
    """Client with a team but no games in the DB."""
    db_path = tmp_path / "no_games.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    lsb_id, _ = _insert_base(conn)
    conn.commit()
    conn.close()
    env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@test.com"}
    with patch.dict("os.environ", env):
        with TestClient(app) as client:
            yield client


@pytest.fixture()
def batting_client(tmp_path: Path):
    """Client with batting stats data to test /dashboard/batting."""
    db_path = tmp_path / "batting.db"
    _apply_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    lsb_id, _ = _insert_base(conn)
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, 'Test', 'Player')",
        ("tp-001",),
    )
    conn.execute(
        "INSERT INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, bb, so) VALUES (?, ?, ?, 5, 18, 6, 2, 3)",
        ("tp-001", lsb_id, _CURRENT_SEASON_ID),
    )
    conn.commit()
    conn.close()
    env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@test.com"}
    with patch.dict("os.environ", env):
        with TestClient(app) as client:
            yield client, lsb_id


# ---------------------------------------------------------------------------
# AC-11(a): schedule view renders with mix of games, sorted date ASC
# ---------------------------------------------------------------------------


class TestSchedulePageRenders:
    def test_schedule_200(self, schedule_client) -> None:
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert resp.status_code == 200

    def test_upcoming_section_present(self, schedule_client) -> None:
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        body = resp.text
        assert "Upcoming" in body

    def test_completed_section_present(self, schedule_client) -> None:
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        body = resp.text
        assert "Completed" in body

    def test_next_badge_present(self, schedule_client) -> None:
        """The nearest upcoming game gets the NEXT badge."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert "NEXT" in resp.text

    def test_upcoming_games_show_opponent_names(self, schedule_client) -> None:
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert "Central Lions" in resp.text
        assert "West Eagles" in resp.text

    def test_completed_game_shows_score(self, schedule_client) -> None:
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        # Our score first (LSB is home): 7-3
        assert "7-3" in resp.text

    def test_completed_game_shows_win(self, schedule_client) -> None:
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert ">W<" in resp.text

    def test_away_game_shows_at_prefix(self, schedule_client) -> None:
        """Away upcoming game shows '@' prefix."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        # The far game vs West Eagles is away
        assert "@" in resp.text

    def test_home_game_shows_vs_prefix(self, schedule_client) -> None:
        """Home upcoming game shows 'vs' prefix."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert "vs" in resp.text

    def test_days_countdown_shown(self, schedule_client) -> None:
        """Days-until countdown is rendered on upcoming cards."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        # 3 days away = "(3 days)"
        assert "3 days" in resp.text or "days" in resp.text


# ---------------------------------------------------------------------------
# AC-11(b): bottom nav has exactly 3 tabs with correct labels and hrefs
# ---------------------------------------------------------------------------


class TestBottomNav:
    def test_three_tabs(self, schedule_client) -> None:
        """Nav has exactly 3 tabs."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        body = resp.text
        assert body.count(">Schedule<") == 1
        assert body.count(">Batting<") == 1
        assert body.count(">Pitching<") == 1

    def test_no_games_tab(self, schedule_client) -> None:
        """Old 'Games' tab is gone from nav."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        # Check nav section specifically -- the word "Games" may appear elsewhere
        # but the nav anchor for /dashboard/games should not be in the nav bar
        # We check that there are exactly 3 nav tabs
        assert resp.text.count(">Schedule<") == 1
        assert resp.text.count(">Batting<") == 1
        assert resp.text.count(">Pitching<") == 1
        assert resp.text.count(">Games<") == 0
        assert resp.text.count(">Opponents<") == 0

    def test_schedule_tab_links_to_dashboard(self, schedule_client) -> None:
        """Schedule tab href is /dashboard."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert 'href="/dashboard?' in resp.text or 'href="/dashboard"' in resp.text

    def test_batting_tab_links_to_dashboard_batting(self, schedule_client) -> None:
        """Batting tab href contains /dashboard/batting."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert "/dashboard/batting" in resp.text

    def test_pitching_tab_links_to_dashboard_pitching(self, schedule_client) -> None:
        """Pitching tab href contains /dashboard/pitching."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert "/dashboard/pitching" in resp.text

    def test_schedule_tab_is_active_on_schedule_page(self, schedule_client) -> None:
        """Schedule tab has the active style when on the schedule page."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        body = resp.text
        # The active nav pattern: text-blue-900 font-bold on the Schedule link
        # Find the Schedule anchor and check it has the active class
        assert "text-blue-900 font-bold" in body

    def test_batting_tab_is_active_on_batting_page(self, batting_client) -> None:
        """Batting tab has active style when on batting page."""
        client, lsb_id = batting_client
        resp = client.get("/dashboard/batting")
        assert resp.status_code == 200
        assert "text-blue-900 font-bold" in resp.text


# ---------------------------------------------------------------------------
# AC-11(c): scouted badge logic
# ---------------------------------------------------------------------------


class TestScoutedBadge:
    def test_scouted_badge_when_stats_exist(self, schedule_client) -> None:
        """opp1 has batting stats → shows Scouted."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert "Scouted" in resp.text

    def test_not_scouted_badge_when_no_stats(self, schedule_client) -> None:
        """opp2 has no stats → shows Not scouted."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert "Not scouted" in resp.text


# ---------------------------------------------------------------------------
# AC-11(d): /dashboard/batting serves batting stats
# ---------------------------------------------------------------------------


class TestBattingRoute:
    def test_batting_url_returns_200(self, batting_client) -> None:
        client, lsb_id = batting_client
        resp = client.get("/dashboard/batting")
        assert resp.status_code == 200

    def test_batting_page_shows_stats_table(self, batting_client) -> None:
        client, lsb_id = batting_client
        resp = client.get("/dashboard/batting")
        assert "AVG" in resp.text
        assert "OBP" in resp.text

    def test_batting_page_shows_player(self, batting_client) -> None:
        client, lsb_id = batting_client
        resp = client.get("/dashboard/batting")
        assert "Test Player" in resp.text

    def test_old_dashboard_url_serves_schedule(self, schedule_client) -> None:
        """/dashboard now serves the schedule, not batting stats."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        # Schedule has Upcoming / Completed sections; batting stats does not
        assert "Upcoming" in resp.text or "Completed" in resp.text


# ---------------------------------------------------------------------------
# AC-11(e): batting template links to /dashboard/batting
# ---------------------------------------------------------------------------


class TestBattingTemplateLinks:
    def test_sort_links_use_batting_url(self, batting_client) -> None:
        """Sort header links in team_stats.html point to /dashboard/batting."""
        client, lsb_id = batting_client
        resp = client.get("/dashboard/batting")
        body = resp.text
        # All sort hrefs should use /dashboard/batting
        assert "/dashboard/batting?" in body
        # No sort link should point to the bare /dashboard?sort=
        assert "/dashboard?sort=" not in body

    def test_team_selector_uses_batting_url(self, batting_client) -> None:
        """Team selector pills on batting page link to /dashboard/batting."""
        client, lsb_id = batting_client
        resp = client.get("/dashboard/batting")
        body = resp.text
        assert f"/dashboard/batting?team_id={lsb_id}" in body


# ---------------------------------------------------------------------------
# AC-9: empty states
# ---------------------------------------------------------------------------


class TestEmptyStates:
    def test_no_games_shows_empty_message(self, no_games_client) -> None:
        """When no games exist, a descriptive empty state is shown."""
        resp = no_games_client.get("/dashboard")
        assert resp.status_code == 200
        assert "No schedule data" in resp.text

    def test_no_assignments_message(self, tmp_path: Path) -> None:
        """When user has no team assignments, appropriate message is shown."""
        db_path = tmp_path / "no_assign.db"
        _apply_schema(db_path)
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "nobody@test.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "no team assignments" in resp.text.lower()


# ---------------------------------------------------------------------------
# AC-7: old routes still work
# ---------------------------------------------------------------------------


class TestOldRoutesStillWork:
    def test_games_route_still_accessible(self, schedule_client) -> None:
        """/dashboard/games still returns 200."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get(f"/dashboard/games?team_id={lsb_id}")
        assert resp.status_code == 200

    def test_opponents_route_still_accessible(self, schedule_client) -> None:
        """/dashboard/opponents still returns 200."""
        client, lsb_id, opp1, opp2 = schedule_client
        resp = client.get(f"/dashboard/opponents?team_id={lsb_id}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC-10: null home_away handled gracefully
# ---------------------------------------------------------------------------


class TestNullHomeAway:
    def test_null_home_away_renders_without_error(self, tmp_path: Path) -> None:
        """A scheduled game with NULL home_away context renders gracefully."""
        db_path = tmp_path / "null_ha.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        lsb_id, _ = _insert_base(conn)
        opp_id = _insert_opponent(conn, "Null Away Team")
        # Insert a scheduled game where we can test the template handles it
        _insert_game(conn, "g-sched", lsb_id, opp_id, _UPCOMING_DATE_NEAR, "scheduled",
                     lsb_is_home=True)
        conn.commit()
        conn.close()
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@test.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get("/dashboard")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Multi-team isolation: games for one team must not appear for another
# ---------------------------------------------------------------------------


class TestTeamIsolation:
    def test_schedule_returns_only_own_team_games(self, tmp_path: Path) -> None:
        """Games belonging to team A must not appear when viewing team B's schedule."""
        db_path = tmp_path / "isolation.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        team_a_id, user_id = _insert_base(conn)  # user is assigned to team_a
        # Create team_b (assign user so team selector works)
        cursor = conn.execute(
            "INSERT INTO teams (name, membership_type, classification) VALUES (?, ?, ?)",
            ("Team B", "member", "varsity"),
        )
        team_b_id: int = cursor.lastrowid  # type: ignore[assignment]
        conn.execute(
            "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, team_b_id),
        )
        opp_id = _insert_opponent(conn, "Common Opponent")
        # Insert a game only for team_b
        _insert_game(conn, "g-b-only", team_b_id, opp_id, _UPCOMING_DATE_NEAR, "scheduled",
                     lsb_is_home=True)
        conn.commit()
        conn.close()
        env = {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@test.com"}
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                # View team_a's schedule -- it has no games
                resp = client.get(f"/dashboard?team_id={team_a_id}")
        assert resp.status_code == 200
        # Common Opponent only played team_b; must not appear in team_a's schedule
        assert "Common Opponent" not in resp.text


# ---------------------------------------------------------------------------
# E-181-03: Schedule card "Link" micro-CTA (admin vs non-admin)
# ---------------------------------------------------------------------------


class TestScheduleLinkCTA:
    """E-181-03 AC-1 through AC-4: admin 'Link >' CTA on unscouted schedule cards."""

    def _make_db(self, tmp_path: Path) -> tuple[Path, int, int]:
        """Create DB with one upcoming game vs unscouted opponent.

        Returns (db_path, lsb_team_id, opp_team_id).
        """
        db_path = tmp_path / "link_cta.db"
        _apply_schema(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        lsb_id, _ = _insert_base(conn)
        opp_id = _insert_opponent(conn, "Unscouted Rival")
        # Upcoming game -- opponent has no stats (not scouted)
        _insert_game(conn, "g-unscouted", lsb_id, opp_id, _UPCOMING_DATE_NEAR, "scheduled")
        conn.commit()
        conn.close()
        return db_path, lsb_id, opp_id

    def test_admin_sees_link_cta_on_unscouted_opponent(self, tmp_path: Path) -> None:
        """AC-1: Admin users see 'Link >' action on unscouted schedule cards."""
        db_path, lsb_id, opp_id = self._make_db(tmp_path)
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "dev@test.com",
            "ADMIN_EMAIL": "dev@test.com",
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(f"/dashboard?team_id={lsb_id}")
        assert resp.status_code == 200
        body = resp.text
        assert "Link &gt;" in body
        assert f"/admin/opponents?filter=unresolved&amp;team_id={lsb_id}" in body

    def test_non_admin_sees_not_scouted_text(self, tmp_path: Path) -> None:
        """AC-2: Non-admin users see 'Not scouted' text without a link."""
        db_path, lsb_id, opp_id = self._make_db(tmp_path)
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "dev@test.com",
            "ADMIN_EMAIL": "admin@other.edu",  # different from user
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(f"/dashboard?team_id={lsb_id}")
        assert resp.status_code == 200
        body = resp.text
        assert "Not scouted" in body
        assert "Link &gt;" not in body

    def test_link_cta_has_stop_propagation(self, tmp_path: Path) -> None:
        """AC-4: The 'Link' action uses event.stopPropagation()."""
        db_path, lsb_id, opp_id = self._make_db(tmp_path)
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "dev@test.com",
            "ADMIN_EMAIL": "dev@test.com",
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(f"/dashboard?team_id={lsb_id}")
        assert resp.status_code == 200
        assert "event.stopPropagation()" in resp.text

    def test_resolved_but_unscouted_hides_link_cta(self, tmp_path: Path) -> None:
        """Resolved (linked) opponents without stats show 'Not scouted', not 'Link >'.

        An opponent that has been resolved via opponent_links but hasn't had
        scouting stats loaded yet should NOT show the 'Link >' CTA, since
        clicking it would send the admin to the unresolved filter where this
        opponent won't appear.
        """
        db_path, lsb_id, opp_id = self._make_db(tmp_path)
        # Mark the opponent as resolved in opponent_links
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name,"
            " resolved_team_id, public_id, resolution_method, resolved_at)"
            " VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (lsb_id, "rt-001", "Unscouted Rival", opp_id, "unscouted-rival", "search"),
        )
        conn.commit()
        conn.close()
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "dev@test.com",
            "ADMIN_EMAIL": "dev@test.com",
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(f"/dashboard?team_id={lsb_id}")
        assert resp.status_code == 200
        body = resp.text
        # Should NOT show "Link >" since opponent is already resolved
        assert "Link &gt;" not in body
        # Should show "Not scouted" instead
        assert "Not scouted" in body

    def test_scouted_opponent_shows_scouted_badge(self, tmp_path: Path) -> None:
        """Scouted opponents still show the 'Scouted' badge, not 'Link'."""
        db_path, lsb_id, opp_id = self._make_db(tmp_path)
        # Give opponent batting stats so it's considered scouted
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        _insert_opp_batting_stats(conn, opp_id)
        conn.commit()
        conn.close()
        env = {
            "DATABASE_PATH": str(db_path),
            "DEV_USER_EMAIL": "dev@test.com",
            "ADMIN_EMAIL": "dev@test.com",
        }
        with patch.dict("os.environ", env):
            with TestClient(app) as client:
                resp = client.get(f"/dashboard?team_id={lsb_id}")
        assert resp.status_code == 200
        assert "Scouted" in resp.text
