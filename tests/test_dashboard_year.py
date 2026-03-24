# synthetic-test-data
"""Tests for E-133-01: Year Dropdown UI and Route Integration.

Covers AC-9 items:
  (a) get_team_year_map DB function -- returns correct mapping, handles empty input,
      handles teams with no stat data
  (b) Route year filtering -- default year (current calendar), explicit year param,
      no-data fallback, team_id wins over year
  (c) Year propagation in template context -- active_year and available_years present

Run with:
    pytest tests/test_dashboard_year.py -v
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
from src.api import db as api_db  # noqa: E402
from src.api.main import app  # noqa: E402
from src.api.routes.dashboard import _resolve_year_and_team  # noqa: E402

_CURRENT_YEAR = datetime.date.today().year
_PRIOR_YEAR = _CURRENT_YEAR - 1
_CURRENT_SEASON = f"{_CURRENT_YEAR}-spring-hs"
_PRIOR_SEASON = f"{_PRIOR_YEAR}-spring-hs"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_year.db"
    run_migrations(db_path=db_path)
    return db_path


def _insert_team(db_path: Path, name: str = "LSB Varsity") -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES (?, 'member')", (name,)
    )
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    return team_id


def _insert_player(db_path: Path, player_id: str, first: str, last: str) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first, last),
    )
    conn.commit()
    conn.close()


def _insert_season(db_path: Path, season_id: str, year: int) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)"
        " VALUES (?, ?, 'spring-hs', ?)",
        (season_id, f"Season {season_id}", year),
    )
    conn.commit()
    conn.close()


def _insert_batting_stats(db_path: Path, player_id: str, team_id: int, season_id: str) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, bb, so)"
        " VALUES (?, ?, ?, 5, 18, 6, 2, 3)",
        (player_id, team_id, season_id),
    )
    conn.commit()
    conn.close()


def _set_season_year(db_path: Path, team_id: int, year: int) -> None:
    """Set teams.season_year for a given team (E-147-01 column-based year mapping)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE teams SET season_year = ? WHERE id = ?", (year, team_id))
    conn.commit()
    conn.close()


def _insert_pitching_stats(db_path: Path, player_id: str, team_id: int, season_id: str) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO player_season_pitching"
        " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so)"
        " VALUES (?, ?, ?, 3, 15, 8, 4, 5, 10)",
        (player_id, team_id, season_id),
    )
    conn.commit()
    conn.close()


def _make_dev_client(db_path: Path, team_id: int) -> TestClient:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    user_id = conn.execute(
        "INSERT INTO users (email) VALUES (?) RETURNING id", ("dev@example.com",)
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, team_id),
    )
    conn.commit()
    conn.close()
    return TestClient(app, follow_redirects=False)


def _make_dev_client_multi(db_path: Path, team_ids: list[int]) -> TestClient:
    """Create a dev client with multiple teams in user_team_access."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    user_id = conn.execute(
        "INSERT INTO users (email) VALUES (?) RETURNING id", ("dev@example.com",)
    ).fetchone()[0]
    for team_id in team_ids:
        conn.execute(
            "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
            (user_id, team_id),
        )
    conn.commit()
    conn.close()
    return TestClient(app, follow_redirects=False)


# ---------------------------------------------------------------------------
# AC-9(a): get_team_year_map DB function
# ---------------------------------------------------------------------------


class TestGetTeamYearMap:
    """Tests for db.get_team_year_map."""

    def test_returns_correct_mapping_from_batting(self, tmp_path: Path) -> None:
        """Team with batting stats gets correct year mapped."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "LSB Varsity")
        _insert_player(db_path, "p-y-001", "Alice", "Smith")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-y-001", team_id, _CURRENT_SEASON)

        with patch("src.api.db.get_db_path", return_value=db_path):
            result = api_db.get_team_year_map([team_id])

        assert result == {team_id: _CURRENT_YEAR}

    def test_returns_correct_mapping_from_season_year(self, tmp_path: Path) -> None:
        """Team with explicit season_year gets that year mapped (E-147-01)."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "LSB JV")
        _set_season_year(db_path, team_id, _PRIOR_YEAR)

        with patch("src.api.db.get_db_path", return_value=db_path):
            result = api_db.get_team_year_map([team_id])

        assert result == {team_id: _PRIOR_YEAR}

    def test_empty_team_ids_returns_empty_dict(self, tmp_path: Path) -> None:
        """Empty input returns empty dict without hitting the DB."""
        result = api_db.get_team_year_map([])
        assert result == {}

    def test_teams_with_no_stat_data_fall_back_to_current_year(self, tmp_path: Path) -> None:
        """Teams with no batting or pitching stats map to the current calendar year (E-142-02)."""
        db_path = _make_db(tmp_path)
        team_with_data = _insert_team(db_path, "LSB Varsity")
        team_no_data = _insert_team(db_path, "LSB JV")
        _insert_player(db_path, "p-y-003", "Carol", "Taylor")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-y-003", team_with_data, _CURRENT_SEASON)

        with patch("src.api.db.get_db_path", return_value=db_path):
            result = api_db.get_team_year_map([team_with_data, team_no_data])

        assert team_with_data in result
        assert result[team_with_data] == _CURRENT_YEAR
        assert team_no_data in result
        assert result[team_no_data] == _CURRENT_YEAR

    def test_multiple_teams_multiple_years(self, tmp_path: Path) -> None:
        """Multiple teams with different season_year values each get correct mapping."""
        db_path = _make_db(tmp_path)
        team_cur = _insert_team(db_path, "LSB Varsity")
        team_pri = _insert_team(db_path, "LSB JV")
        _set_season_year(db_path, team_cur, _CURRENT_YEAR)
        _set_season_year(db_path, team_pri, _PRIOR_YEAR)

        with patch("src.api.db.get_db_path", return_value=db_path):
            result = api_db.get_team_year_map([team_cur, team_pri])

        assert result[team_cur] == _CURRENT_YEAR
        assert result[team_pri] == _PRIOR_YEAR

    def test_stale_id_omitted_from_result(self, tmp_path: Path) -> None:
        """Team IDs not in the teams table are silently omitted."""
        db_path = _make_db(tmp_path)
        real_team = _insert_team(db_path, "Real Team")
        _set_season_year(db_path, real_team, _PRIOR_YEAR)
        stale_id = 9999  # does not exist in teams table

        with patch("src.api.db.get_db_path", return_value=db_path):
            result = api_db.get_team_year_map([real_team, stale_id])

        assert result[real_team] == _PRIOR_YEAR
        assert stale_id not in result


# ---------------------------------------------------------------------------
# Unit tests for _resolve_year_and_team
# ---------------------------------------------------------------------------


class TestResolveYearAndTeam:
    """Unit tests for the pure _resolve_year_and_team helper."""

    def test_team_id_wins_over_year_param(self) -> None:
        """When team_id is provided, it takes precedence (Path 2)."""
        team_year_map = {1: _CURRENT_YEAR, 2: _PRIOR_YEAR}
        permitted = [1, 2]
        # Even when year param says prior year, team_id=1 resolves to current year
        team, year = _resolve_year_and_team(team_year_map, permitted, team_id_param=1, year_param=_PRIOR_YEAR)
        assert team == 1
        assert year == _CURRENT_YEAR

    def test_explicit_year_filters_to_first_matching_team(self) -> None:
        """Explicit year param selects the first team in that year (Path 3)."""
        team_year_map = {1: _CURRENT_YEAR, 2: _PRIOR_YEAR}
        permitted = [1, 2]
        team, year = _resolve_year_and_team(team_year_map, permitted, team_id_param=None, year_param=_PRIOR_YEAR)
        assert team == 2
        assert year == _PRIOR_YEAR

    def test_default_year_is_current_calendar(self) -> None:
        """No params defaults to current calendar year (Path 4)."""
        team_year_map = {1: _CURRENT_YEAR, 2: _PRIOR_YEAR}
        permitted = [1, 2]
        team, year = _resolve_year_and_team(team_year_map, permitted, team_id_param=None, year_param=None)
        assert year == _CURRENT_YEAR
        assert team == 1

    def test_fallback_to_most_recent_when_no_current_data(self) -> None:
        """When no teams have current-year data, fall back to most recent year with data."""
        team_year_map = {1: _PRIOR_YEAR}
        permitted = [1]
        team, year = _resolve_year_and_team(team_year_map, permitted, team_id_param=None, year_param=None)
        assert team == 1
        assert year == _PRIOR_YEAR

    def test_invalid_year_falls_back_to_most_recent(self) -> None:
        """Explicit year with no matching teams falls back to most recent (Path 5)."""
        team_year_map = {1: _CURRENT_YEAR}
        permitted = [1]
        # year_param=1999 has no teams
        team, year = _resolve_year_and_team(team_year_map, permitted, team_id_param=None, year_param=1999)
        assert team == 1
        assert year == _CURRENT_YEAR

    def test_no_data_at_all_uses_first_team_and_current_year(self) -> None:
        """When team_year_map is empty, use first permitted team and current year."""
        team_year_map: dict[int, int] = {}
        permitted = [5]
        team, year = _resolve_year_and_team(team_year_map, permitted, team_id_param=None, year_param=None)
        assert team == 5
        assert year == _CURRENT_YEAR


# ---------------------------------------------------------------------------
# AC-9(b): Route year filtering (HTTP-level tests)
# ---------------------------------------------------------------------------


class TestRouteYearFiltering:
    """AC-9(b): Test year filtering through the HTTP routes."""

    def test_default_year_current_calendar_batting(self, tmp_path: Path) -> None:
        """With current-year data, /dashboard defaults to current year."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-r-001", "Alice", "Smith")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-r-001", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # Active year should appear in the response
        assert str(_CURRENT_YEAR) in resp.text

    def test_fallback_to_prior_year_when_no_current_data(self, tmp_path: Path) -> None:
        """When only prior-year data exists, route falls back to prior year."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _set_season_year(db_path, team_id, _PRIOR_YEAR)
        _insert_player(db_path, "p-r-002", "Bob", "Jones")
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-r-002", team_id, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # Prior year should appear (fallback)
        assert str(_PRIOR_YEAR) in resp.text

    def test_explicit_year_param_accepted(self, tmp_path: Path) -> None:
        """Explicit ?year= param is accepted and used for filtering."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-r-003", "Carol", "Taylor")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-r-003", team_id, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-r-003", team_id, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?year={_PRIOR_YEAR}")

        assert resp.status_code == 200

    def test_team_id_wins_when_both_params_present(self, tmp_path: Path) -> None:
        """team_id takes precedence over year param (TN-2 Path 2)."""
        db_path = _make_db(tmp_path)
        # Two teams: team_a in current year, team_b in prior year
        team_a = _insert_team(db_path, "LSB Varsity")
        team_b = _insert_team(db_path, "LSB JV")
        _set_season_year(db_path, team_a, _CURRENT_YEAR)
        _set_season_year(db_path, team_b, _PRIOR_YEAR)
        _insert_player(db_path, "p-r-010", "Dan", "White")
        _insert_player(db_path, "p-r-011", "Eve", "Brown")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-r-010", team_a, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-r-011", team_b, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_a, team_b])
            with client:
                # Request team_a with year=PRIOR_YEAR — team_a should still be active
                resp = client.get(f"/dashboard/batting?team_id={team_a}&year={_PRIOR_YEAR}")

        assert resp.status_code == 200
        # Page should show team_a's data (current year), not team_b's
        assert "LSB Varsity" in resp.text

    def test_year_filtering_all_four_routes(self, tmp_path: Path) -> None:
        """All four main routes accept year param without 4xx errors."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-r-020", "Frank", "Lee")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-r-020", team_id, _CURRENT_SEASON)
        _insert_pitching_stats(db_path, "p-r-020", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                for url in [
                    f"/dashboard?year={_CURRENT_YEAR}",
                    f"/dashboard/pitching?year={_CURRENT_YEAR}",
                    f"/dashboard/games?year={_CURRENT_YEAR}",
                    f"/dashboard/opponents?year={_CURRENT_YEAR}",
                ]:
                    resp = client.get(url)
                    assert resp.status_code == 200, f"Route {url} returned {resp.status_code}"

    def test_no_data_team_appears_in_team_pills_for_current_year(self, tmp_path: Path) -> None:
        """No-data team appears in team pills when dashboard is loaded for the current year (AC-4).

        A team with stat data anchors the current year in the year selector.
        A second team with no stat data falls back to the current year via the
        get_team_year_map fallback, so it must appear in the team pill list.
        """
        db_path = _make_db(tmp_path)
        team_with_data = _insert_team(db_path, "LSB Varsity")
        team_no_data = _insert_team(db_path, "LSB Freshman")
        _insert_player(db_path, "p-nd-001", "Sam", "Rivera")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-nd-001", team_with_data, _CURRENT_SEASON)
        # team_no_data has no stat rows -- relies on year-map fallback

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_with_data, team_no_data])
            with client:
                resp = client.get(f"/dashboard/batting?year={_CURRENT_YEAR}")

        assert resp.status_code == 200
        assert "LSB Freshman" in resp.text


# ---------------------------------------------------------------------------
# AC-9(c): Year propagation in template context
# ---------------------------------------------------------------------------


class TestYearPropagationInContext:
    """AC-9(c): active_year and available_years appear in rendered HTML."""

    def test_active_year_in_batting_html(self, tmp_path: Path) -> None:
        """active_year appears in /dashboard HTML output."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-c-001", "Grace", "Kim")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-c-001", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        assert str(_CURRENT_YEAR) in resp.text

    def test_year_dropdown_visible_with_two_teams_two_years(self, tmp_path: Path) -> None:
        """Year dropdown appears when permitted teams span multiple years.

        Each GC team entity has exactly one season; multiple years come from
        multiple teams assigned to the user.
        """
        db_path = _make_db(tmp_path)
        team_cur = _insert_team(db_path, "LSB Varsity")
        team_pri = _insert_team(db_path, "LSB Varsity Old")
        _set_season_year(db_path, team_cur, _CURRENT_YEAR)
        _set_season_year(db_path, team_pri, _PRIOR_YEAR)
        _insert_player(db_path, "p-c-010", "Hank", "Moore")
        _insert_player(db_path, "p-c-011", "Ina", "Clark")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-c-010", team_cur, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-c-011", team_pri, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # Year dropdown should be present (select with name="year")
        assert 'name="year"' in resp.text
        assert str(_CURRENT_YEAR) in resp.text
        assert str(_PRIOR_YEAR) in resp.text

    def test_year_dropdown_hidden_with_single_year(self, tmp_path: Path) -> None:
        """Year dropdown is hidden when only one year has data."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-c-020", "Iris", "Davis")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-c-020", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # No year dropdown when only one year (AC-4)
        assert 'name="year"' not in resp.text

    def test_year_in_bottom_nav_links(self, tmp_path: Path) -> None:
        """Bottom nav bar links include year when active_year is set."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-c-030", "Jack", "Wilson")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-c-030", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # Bottom nav should have year in links
        assert f"year={_CURRENT_YEAR}" in resp.text

    def test_year_in_team_pill_links(self, tmp_path: Path) -> None:
        """Team selector pill links include year when multiple teams exist."""
        db_path = _make_db(tmp_path)
        team_a = _insert_team(db_path, "LSB Varsity")
        team_b = _insert_team(db_path, "LSB JV")
        _insert_player(db_path, "p-c-040", "Kate", "Anderson")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-c-040", team_a, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-c-040", team_b, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_a, team_b])
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # Team pill links should include year
        assert f"team_id={team_a}&year={_CURRENT_YEAR}" in resp.text
        assert f"team_id={team_b}&year={_CURRENT_YEAR}" in resp.text


# ---------------------------------------------------------------------------
# Finding 1: Year-filtered team pills
# ---------------------------------------------------------------------------


class TestYearFilteredTeamPills:
    """When a year is selected, team pills show only teams with data in that year."""

    def test_prior_year_shows_only_prior_year_team(self, tmp_path: Path) -> None:
        """Selecting prior year hides current-year team pill."""
        db_path = _make_db(tmp_path)
        team_cur = _insert_team(db_path, "LSB Varsity")
        team_pri = _insert_team(db_path, "LSB Varsity Old")
        _set_season_year(db_path, team_cur, _CURRENT_YEAR)
        _set_season_year(db_path, team_pri, _PRIOR_YEAR)
        _insert_player(db_path, "p-f1-001", "Liam", "Ford")
        _insert_player(db_path, "p-f1-002", "Mia", "Grant")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-f1-001", team_cur, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-f1-002", team_pri, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get(f"/dashboard/batting?year={_PRIOR_YEAR}")

        assert resp.status_code == 200
        html = resp.text
        # Prior-year team pill should appear; current-year team should not
        assert f"team_id={team_pri}" in html
        assert f"team_id={team_cur}" not in html

    def test_current_year_shows_only_current_year_team(self, tmp_path: Path) -> None:
        """Selecting current year hides prior-year team pill."""
        db_path = _make_db(tmp_path)
        team_cur = _insert_team(db_path, "LSB JV")
        team_pri = _insert_team(db_path, "LSB JV Old")
        _set_season_year(db_path, team_cur, _CURRENT_YEAR)
        _set_season_year(db_path, team_pri, _PRIOR_YEAR)
        _insert_player(db_path, "p-f1-003", "Noah", "Hayes")
        _insert_player(db_path, "p-f1-004", "Olivia", "James")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-f1-003", team_cur, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-f1-004", team_pri, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get(f"/dashboard/batting?year={_CURRENT_YEAR}")

        assert resp.status_code == 200
        html = resp.text
        # Current-year team pill should appear; prior-year team should not
        assert f"team_id={team_cur}" in html
        assert f"team_id={team_pri}" not in html


# ---------------------------------------------------------------------------
# Finding 2: Detail page bottom nav carries year
# ---------------------------------------------------------------------------


class TestDetailPageBottomNav:
    """Detail pages pass active_year so the bottom nav bar carries the year param."""

    def test_player_profile_bottom_nav_carries_year(self, tmp_path: Path) -> None:
        """Player profile bottom nav includes year= when year param is passed."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "LSB Varsity")
        player_id = "p-f2-001"
        _insert_player(db_path, player_id, "Peter", "Reyes")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, player_id, team_id, _CURRENT_SEASON)
        # team_rosters entry required for player_profile authorization check
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, season_id)"
            " VALUES (?, ?, ?)",
            (team_id, player_id, _CURRENT_SEASON),
        )
        conn.commit()
        conn.close()

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(
                    f"/dashboard/players/{player_id}?year={_CURRENT_YEAR}"
                )

        assert resp.status_code == 200
        # Bottom nav builds links with active_year; verify year appears in nav href
        assert f"year={_CURRENT_YEAR}" in resp.text

    def test_game_detail_bottom_nav_carries_year(self, tmp_path: Path) -> None:
        """Game detail bottom nav includes year= when year param is passed."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "LSB Varsity")
        opp_id = _insert_team(db_path, "Opponent")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        game_id = "g-f2-001"
        # games.game_id is TEXT PRIMARY KEY
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id)"
            " VALUES (?, ?, '2026-04-01', ?, ?)",
            (game_id, _CURRENT_SEASON, team_id, opp_id),
        )
        conn.commit()
        conn.close()

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/games/{game_id}?year={_CURRENT_YEAR}")

        assert resp.status_code == 200
        assert f"year={_CURRENT_YEAR}" in resp.text


# ---------------------------------------------------------------------------
# E-147-04: Cohort-based dashboard navigation
# ---------------------------------------------------------------------------


class TestCohortNavigation:
    """E-147-04: current_year in context, back-link, and (current) label."""

    def _setup_multi_year(self, tmp_path: Path) -> tuple[Path, int, int]:
        """Create DB with two teams in different years."""
        db_path = _make_db(tmp_path)
        team_cur = _insert_team(db_path, "LSB Varsity 2026")
        team_pri = _insert_team(db_path, "LSB Varsity 2025")
        _set_season_year(db_path, team_cur, _CURRENT_YEAR)
        _set_season_year(db_path, team_pri, _PRIOR_YEAR)
        _insert_player(db_path, "p-e147-01", "Alex", "Smith")
        _insert_player(db_path, "p-e147-02", "Ben", "Jones")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-e147-01", team_cur, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-e147-02", team_pri, _PRIOR_SEASON)
        _insert_pitching_stats(db_path, "p-e147-01", team_cur, _CURRENT_SEASON)
        _insert_pitching_stats(db_path, "p-e147-02", team_pri, _PRIOR_SEASON)
        return db_path, team_cur, team_pri

    def test_current_year_in_context_batting(self, tmp_path: Path) -> None:
        """AC-1/AC-5: /dashboard passes current_year to template context."""
        db_path, team_cur, team_pri = self._setup_multi_year(tmp_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        html = resp.text
        # "(current)" label should appear in dropdown for current year
        assert f"{_CURRENT_YEAR} (current)" in html

    def test_historical_view_shows_back_link(self, tmp_path: Path) -> None:
        """AC-3: Viewing a historical year shows '← Current season' back-link."""
        db_path, team_cur, team_pri = self._setup_multi_year(tmp_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get(f"/dashboard/batting?year={_PRIOR_YEAR}")

        assert resp.status_code == 200
        html = resp.text
        assert "Current season" in html

    def test_current_year_no_back_link(self, tmp_path: Path) -> None:
        """AC-3: Current year view does NOT show the back-link."""
        db_path, team_cur, team_pri = self._setup_multi_year(tmp_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get(f"/dashboard/batting?year={_CURRENT_YEAR}")

        assert resp.status_code == 200
        assert "Current season" not in resp.text

    def test_single_year_no_current_label(self, tmp_path: Path) -> None:
        """AC-6: Single year → static span, no '(current)' label, no dropdown."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "LSB JV")
        _set_season_year(db_path, team_id, _CURRENT_YEAR)
        _insert_player(db_path, "p-e147-03", "Chris", "Lee")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_batting_stats(db_path, "p-e147-03", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        html = resp.text
        assert "(current)" not in html
        assert "Current season" not in html

    def test_back_link_on_pitching_route(self, tmp_path: Path) -> None:
        """AC-5: Back-link works on /dashboard/pitching too."""
        db_path, team_cur, team_pri = self._setup_multi_year(tmp_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get(f"/dashboard/pitching?year={_PRIOR_YEAR}")

        assert resp.status_code == 200
        assert "Current season" in resp.text

    def test_stale_bookmark_fallback(self, tmp_path: Path) -> None:
        """AC-2: ?year=1999 (no matching teams) falls back to current year silently."""
        db_path, team_cur, team_pri = self._setup_multi_year(tmp_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get("/dashboard/batting?year=1999")

        assert resp.status_code == 200
        html = resp.text
        # Should fall back to current year — current team pill should appear
        assert f"team_id={team_cur}" in html


# ---------------------------------------------------------------------------
# Remediation: _pick_season_for_year and cohort/season alignment
# ---------------------------------------------------------------------------


class TestPickSeasonForYear:
    """Unit tests for _pick_season_for_year helper."""

    def test_picks_matching_year(self) -> None:
        from src.api.routes.dashboard import _pick_season_for_year

        seasons = [
            {"season_id": "2026-spring-hs"},
            {"season_id": "2025-spring-hs"},
        ]
        assert _pick_season_for_year(seasons, 2025, 2026) == "2025-spring-hs"

    def test_falls_back_to_first_when_no_match(self) -> None:
        from src.api.routes.dashboard import _pick_season_for_year

        seasons = [{"season_id": "2026-spring-hs"}]
        assert _pick_season_for_year(seasons, 2024, 2026) == "2026-spring-hs"

    def test_empty_seasons_uses_fallback_year(self) -> None:
        from src.api.routes.dashboard import _pick_season_for_year

        assert _pick_season_for_year([], 2025, 2026) == "2026-spring-hs"


class TestCohortSeasonAlignment:
    """When ?year=PRIOR selects a prior-year cohort, season_id should match."""

    def test_prior_year_uses_prior_season(self, tmp_path: Path) -> None:
        """Selecting year=PRIOR should use PRIOR-spring-hs season for stats."""
        db_path = _make_db(tmp_path)
        team_cur = _insert_team(db_path, "LSB Varsity")
        team_pri = _insert_team(db_path, "LSB Varsity Old")
        _set_season_year(db_path, team_cur, _CURRENT_YEAR)
        _set_season_year(db_path, team_pri, _PRIOR_YEAR)

        _insert_player(db_path, "p-cs-001", "Alpha", "One")
        _insert_player(db_path, "p-cs-002", "Beta", "Two")
        _insert_season(db_path, _CURRENT_SEASON, _CURRENT_YEAR)
        _insert_season(db_path, _PRIOR_SEASON, _PRIOR_YEAR)
        _insert_batting_stats(db_path, "p-cs-001", team_cur, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-cs-002", team_pri, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client_multi(db_path, [team_cur, team_pri])
            with client:
                resp = client.get(f"/dashboard/batting?year={_PRIOR_YEAR}")

        assert resp.status_code == 200
        html = resp.text
        # Prior year player should be visible, current year player should not
        assert "Beta" in html
        assert "Alpha" not in html
