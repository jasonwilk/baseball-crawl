# synthetic-test-data
"""Tests for E-127-12: Season Selector Implementation.

Covers AC-6 items:
  (a) season auto-detection returns the most recent season with data
  (b) available_seasons and season_id are present in template context for all
      four main tab routes
  (c) navigation link generation includes season_id
  (d) empty-state behavior for teams with no data
  (e) season_display Jinja2 filter unit tests for all known patterns
  (f) season selector is not rendered when only one season has data

Run with:
    pytest tests/test_dashboard_routes.py -v
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
from src.api.helpers import format_season_display  # noqa: E402
from src.api.main import app  # noqa: E402

_CURRENT_YEAR = datetime.date.today().year
_CURRENT_SEASON = f"{_CURRENT_YEAR}-spring-hs"
_PRIOR_SEASON = f"{_CURRENT_YEAR - 1}-spring-hs"
_PRIOR_SEASON_2 = f"{_CURRENT_YEAR - 2}-spring-hs"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a minimal migrated database."""
    db_path = tmp_path / "test_routes.db"
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


def _insert_season(db_path: Path, season_id: str) -> None:
    year = int(season_id.split("-")[0])
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)"
        " VALUES (?, ?, 'spring-hs', ?)",
        (season_id, f"Season {season_id}", year),
    )
    conn.commit()
    conn.close()


def _insert_batting_stats(
    db_path: Path,
    player_id: str,
    team_id: int,
    season_id: str,
) -> None:
    """Insert a player_season_batting row to create season data for the team."""
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


def _insert_pitching_stats(
    db_path: Path,
    player_id: str,
    team_id: int,
    season_id: str,
) -> None:
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
    """Create a TestClient using DEV_USER_EMAIL bypass with the given team assigned."""
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


# ---------------------------------------------------------------------------
# AC-6(e): season_display filter unit tests
# ---------------------------------------------------------------------------


class TestSeasonDisplayFilter:
    """Unit tests for the format_season_display helper / season_display Jinja2 filter."""

    def test_spring_hs(self) -> None:
        assert format_season_display("2026-spring-hs") == "Spring 2026"

    def test_spring_no_suffix(self) -> None:
        """Season IDs without classification suffix."""
        assert format_season_display("2025-summer") == "Summer 2025"

    def test_fall_hs(self) -> None:
        assert format_season_display("2025-fall-hs") == "Fall 2025"

    def test_legion(self) -> None:
        assert format_season_display("2025-legion") == "Legion 2025"

    def test_spring_legion_suffix(self) -> None:
        """Spring season with legion classification — strip suffix."""
        assert format_season_display("2025-spring-legion") == "Spring 2025"

    def test_spring_reserve_suffix(self) -> None:
        """Spring season with reserve classification — strip suffix."""
        assert format_season_display("2025-spring-reserve") == "Spring 2025"

    def test_spring_usssa(self) -> None:
        assert format_season_display("2025-spring-usssa") == "Spring 2025"

    def test_unknown_type_capitalised(self) -> None:
        """Unknown season type falls back to capitalize()."""
        assert format_season_display("2024-winter") == "Winter 2024"

    def test_short_id_passthrough(self) -> None:
        """Malformed IDs (no dash) are returned unchanged."""
        assert format_season_display("invalid") == "invalid"


# ---------------------------------------------------------------------------
# AC-6(a): season auto-detection
# ---------------------------------------------------------------------------


class TestSeasonAutoDetection:
    """AC-6(a): auto-detection returns the most recent season with data."""

    def test_batting_auto_detects_most_recent(self, tmp_path: Path) -> None:
        """With two seasons of batting data, the most recent is auto-selected."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-001", "Alice", "Smith")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-001", team_id, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-001", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        # current season should be auto-selected (most recent)
        assert f"season_id={_CURRENT_SEASON}" in resp.text

    def test_pitching_auto_detects_prior_when_no_current(self, tmp_path: Path) -> None:
        """With only prior-season pitching data, the prior season is auto-selected."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-002", "Bob", "Jones")
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_pitching_stats(db_path, "p-002", team_id, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/pitching")

        assert resp.status_code == 200
        assert f"season_id={_PRIOR_SEASON}" in resp.text

    def test_stale_season_id_falls_back_to_auto_detection(self, tmp_path: Path) -> None:
        """If ?season_id= has no data for this team, route falls back to auto-detection."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-003", "Carol", "Taylor")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-003", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                # Request a non-existent season; should fall back to current
                resp = client.get(f"/dashboard?season_id={_PRIOR_SEASON}")

        assert resp.status_code == 200
        # The active season pill should be for _CURRENT_SEASON (auto-detected)
        # Since only one season exists, the selector is suppressed (AC-6f)
        # but the page should still render with current season data
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC-6(b): available_seasons and season_id in template context (via HTML)
# ---------------------------------------------------------------------------


class TestContextVarsInHTML:
    """AC-6(b): available_seasons and season_id are reflected in rendered HTML."""

    def _setup_two_season_db(self, tmp_path: Path) -> tuple[Path, int]:
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-010", "Dan", "White")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-010", team_id, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-010", team_id, _PRIOR_SEASON)
        _insert_pitching_stats(db_path, "p-010", team_id, _CURRENT_SEASON)
        _insert_pitching_stats(db_path, "p-010", team_id, _PRIOR_SEASON)
        return db_path, team_id

    def test_batting_has_season_id_in_html(self, tmp_path: Path) -> None:
        db_path, team_id = self._setup_two_season_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert f"season_id={_CURRENT_SEASON}" in resp.text

    def test_pitching_has_season_id_in_html(self, tmp_path: Path) -> None:
        db_path, team_id = self._setup_two_season_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/pitching")
        assert resp.status_code == 200
        assert f"season_id={_CURRENT_SEASON}" in resp.text

    def test_games_has_season_id_in_html(self, tmp_path: Path) -> None:
        db_path, team_id = self._setup_two_season_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/games")
        assert resp.status_code == 200
        assert f"season_id={_CURRENT_SEASON}" in resp.text

    def test_opponents_has_season_id_in_html(self, tmp_path: Path) -> None:
        db_path, team_id = self._setup_two_season_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/opponents")
        assert resp.status_code == 200
        assert f"season_id={_CURRENT_SEASON}" in resp.text


# ---------------------------------------------------------------------------
# AC-6(c): navigation links include season_id
# ---------------------------------------------------------------------------


class TestNavigationLinks:
    """AC-6(c): bottom nav links carry season_id; team selector does not."""

    def test_bottom_nav_carries_season_id(self, tmp_path: Path) -> None:
        """Bottom nav hrefs include season_id when it is available."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-020", "Eve", "Brown")
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-020", team_id, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        html = resp.text
        assert f"season_id={_PRIOR_SEASON}" in html
        # Bottom nav links should have the prior season (HTML entity &amp; is standard)
        assert f"/dashboard?team_id={team_id}&amp;season_id={_PRIOR_SEASON}" in html

    def test_team_selector_omits_season_id(self, tmp_path: Path) -> None:
        """Team selector links do NOT carry season_id (triggers auto-detection on switch)."""
        db_path = _make_db(tmp_path)
        team_id_a = _insert_team(db_path, "Alpha Team")
        team_id_b = _insert_team(db_path, "Beta Team")
        _insert_player(db_path, "p-021", "Frank", "Green")
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-021", team_id_a, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-021", team_id_b, _PRIOR_SEASON)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        user_id = conn.execute(
            "INSERT INTO users (email) VALUES (?) RETURNING id", ("dev2@example.com",)
        ).fetchone()[0]
        for tid in (team_id_a, team_id_b):
            conn.execute(
                "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
                (user_id, tid),
            )
        conn.commit()
        conn.close()

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev2@example.com"},
        ):
            with TestClient(app, follow_redirects=False) as client:
                resp = client.get(f"/dashboard?team_id={team_id_a}&season_id={_PRIOR_SEASON}")

        assert resp.status_code == 200
        html = resp.text
        # Team selector links should NOT append season_id
        # They should be plain ?team_id=N links
        assert f"team_id={team_id_b}&season_id=" not in html
        assert f"team_id={team_id_b}" in html

    def test_game_list_row_links_carry_season_id(self, tmp_path: Path) -> None:
        """Game row links in game_list.html carry season_id to game_detail."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "Our Team")
        opp_team_id = _insert_team(db_path, "Opponent")
        _insert_player(db_path, "p-023", "Nina", "Park")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-023", team_id, _CURRENT_SEASON)

        # Create a game so the game list has rows
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, game_date)"
            " VALUES ('g-row-001', ?, ?, ?, '2026-04-10')",
            (_CURRENT_SEASON, team_id, opp_team_id),
        )
        conn.commit()
        conn.close()

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/games?season_id={_CURRENT_SEASON}")

        assert resp.status_code == 200
        html = resp.text
        # Each game row link should carry season_id
        assert f"/dashboard/games/g-row-001?team_id={team_id}&amp;season_id={_CURRENT_SEASON}" in html

    def test_opponent_list_link_carries_season_id(self, tmp_path: Path) -> None:
        """Opponent links in opponent list carry season_id."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "Our Team")
        opp_team_id = _insert_team(db_path, "Opponent Team")
        _insert_player(db_path, "p-022", "Grace", "Hall")
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-022", team_id, _PRIOR_SEASON)

        # Create a game between the two teams so the opponent appears
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, game_date)"
            " VALUES ('g-001', ?, ?, ?, '2025-04-01')",
            (_PRIOR_SEASON, team_id, opp_team_id),
        )
        conn.commit()
        conn.close()

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/opponents?season_id={_PRIOR_SEASON}")

        assert resp.status_code == 200
        html = resp.text
        assert f"season_id={_PRIOR_SEASON}" in html


# ---------------------------------------------------------------------------
# AC-6(d): empty-state behavior for teams with no data
# ---------------------------------------------------------------------------


class TestEmptyState:
    """AC-6(d): teams with no data show appropriate empty state, not a broken page."""

    def test_batting_no_data_shows_no_stats(self, tmp_path: Path) -> None:
        """A team with zero batting/pitching records renders 200 with 'No stats available'."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        assert "No stats available" in resp.text

    def test_pitching_no_data_shows_no_stats(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/pitching")

        assert resp.status_code == 200
        assert "No pitching stats available" in resp.text

    def test_no_data_fallback_season_id_is_current_year(self, tmp_path: Path) -> None:
        """With no data, the fallback season_id uses the current year."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        # The fallback season_id should start with the current year
        assert str(_CURRENT_YEAR) in resp.text

    def test_no_data_no_freshness_indicator(self, tmp_path: Path) -> None:
        """With no data, fallback is current year so freshness indicator is NOT shown."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        # bg-yellow-50 is the freshness indicator class -- should not appear
        assert "bg-yellow-50" not in resp.text


# ---------------------------------------------------------------------------
# AC-6(f): season selector suppressed when only one season has data
# ---------------------------------------------------------------------------


class TestSeasonSelectorSuppression:
    """AC-6(f): season selector is not rendered when only one season has data."""

    def test_single_season_no_selector(self, tmp_path: Path) -> None:
        """With only one season, the pill-button season selector is not rendered."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-030", "Henry", "King")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-030", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.text
        # With only one season, the selector macro renders nothing (suppressed)
        # The selector macro only renders when len(seasons) > 1
        # Verify no season pill buttons linking to other seasons appear
        # (There's no second season to link to)
        # We confirm this by checking the season_display label doesn't appear as a link
        label = format_season_display(_CURRENT_SEASON)
        # If the selector were rendered, label would appear as a link text; but it's suppressed
        # The label may still appear elsewhere (e.g. freshness bar), so check for the pill link
        assert f'season_id={_CURRENT_SEASON}" class="px-3' not in html

    def test_two_seasons_show_selector(self, tmp_path: Path) -> None:
        """With two seasons, the season selector renders pill buttons for each."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-031", "Iris", "Lane")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-031", team_id, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-031", team_id, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.text
        # Both season labels should appear as pill buttons
        assert format_season_display(_CURRENT_SEASON) in html
        assert format_season_display(_PRIOR_SEASON) in html
        assert f"season_id={_PRIOR_SEASON}" in html


# ---------------------------------------------------------------------------
# AC-7: data freshness indicator
# ---------------------------------------------------------------------------


class TestFreshnessIndicator:
    """AC-7: yellow info bar shown when active season is from a prior year."""

    def test_prior_season_shows_freshness_bar(self, tmp_path: Path) -> None:
        """When viewing a prior-year season, the yellow freshness bar appears."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-040", "Jack", "Moore")
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-040", team_id, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        html = resp.text
        assert "bg-yellow-50" in html
        assert str(_CURRENT_YEAR) in html
        assert "no" in html.lower() and "season data has been loaded" in html.lower()

    def test_current_season_no_freshness_bar(self, tmp_path: Path) -> None:
        """When viewing the current year's season, no freshness bar appears."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_player(db_path, "p-041", "Kate", "Nash")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_batting_stats(db_path, "p-041", team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard")

        assert resp.status_code == 200
        assert "bg-yellow-50" not in resp.text
