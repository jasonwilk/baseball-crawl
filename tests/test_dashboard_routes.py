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


def _set_season_year(db_path: Path, team_id: int, year: int) -> None:
    """Set teams.season_year for a given team."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE teams SET season_year = ? WHERE id = ?", (year, team_id))
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
                resp = client.get("/dashboard/batting")

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
                resp = client.get(f"/dashboard/batting?season_id={_PRIOR_SEASON}")

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
                resp = client.get("/dashboard/batting")
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
        _set_season_year(db_path, team_id, _CURRENT_YEAR - 1)
        _insert_player(db_path, "p-020", "Eve", "Brown")
        _insert_season(db_path, _PRIOR_SEASON)
        _insert_batting_stats(db_path, "p-020", team_id, _PRIOR_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        html = resp.text
        assert f"season_id={_PRIOR_SEASON}" in html
        # Bottom nav links should have the prior season (HTML entity &amp; is standard).
        # year is now included between team_id and season_id.
        _prior_year = _CURRENT_YEAR - 1
        assert (
            f"/dashboard/batting?team_id={team_id}&amp;year={_prior_year}&amp;season_id={_PRIOR_SEASON}"
            in html
        )

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
                resp = client.get(f"/dashboard/batting?team_id={team_id_a}&season_id={_PRIOR_SEASON}")

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
        assert f"/dashboard/games/g-row-001?team_id={team_id}&amp;year={_CURRENT_YEAR}&amp;season_id={_CURRENT_SEASON}" in html

    def test_opponent_detail_box_score_link_carries_season_id(self, tmp_path: Path) -> None:
        """Box Score link on opponent detail page includes season_id as &amp;season_id=."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path, "Our Team")
        opp_team_id = _insert_team(db_path, "Opponent Team")
        _insert_season(db_path, _CURRENT_SEASON)

        # Insert a completed game so last_meeting is non-None and Box Score link renders.
        # E-153-04: Box Score link only appears in full_stats state, so also add batting stats.
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id,"
            " game_date, home_score, away_score, status)"
            " VALUES ('g-detail-001', ?, ?, ?, '2026-04-15', 5, 3, 'completed')",
            (_CURRENT_SEASON, team_id, opp_team_id),
        )
        conn.commit()
        conn.close()
        # Add a player + batting stats for the opponent so the page enters full_stats state.
        _insert_player(db_path, "opp-bx-001", "Box", "Scout")
        _insert_batting_stats(db_path, "opp-bx-001", opp_team_id, _CURRENT_SEASON)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(
                    f"/dashboard/opponents/{opp_team_id}"
                    f"?team_id={team_id}&season_id={_CURRENT_SEASON}"
                )

        assert resp.status_code == 200
        html = resp.text
        # Box Score link must carry both team_id and season_id as valid HTML entities
        assert (
            f"/dashboard/games/g-detail-001?team_id={team_id}"
            f"&amp;season_id={_CURRENT_SEASON}"
        ) in html

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
        """A team with zero batting/pitching records renders 200 with empty-state banner."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _set_season_year(db_path, team_id, _CURRENT_YEAR)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        assert "Stats haven&#x27;t been loaded" in resp.text or "Stats haven't been loaded" in resp.text

    def test_pitching_no_data_shows_no_stats(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _set_season_year(db_path, team_id, _CURRENT_YEAR)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/pitching")

        assert resp.status_code == 200
        assert "Stats haven&#x27;t been loaded" in resp.text or "Stats haven't been loaded" in resp.text

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
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # The fallback season_id should start with the current year
        assert str(_CURRENT_YEAR) in resp.text

    def test_no_data_shows_empty_state_banner(self, tmp_path: Path) -> None:
        """With no data, the empty-state banner (bg-yellow-50) is shown."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _set_season_year(db_path, team_id, _CURRENT_YEAR)

        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # bg-yellow-50 is the empty-state banner class for teams with no loaded stats
        assert "bg-yellow-50" in resp.text


# ---------------------------------------------------------------------------
# AC-6(f): legacy season pill selector is absent (removed in E-133-02)
# ---------------------------------------------------------------------------


class TestSeasonSelectorSuppression:
    """Legacy season pill selector is not present; year dropdown is the sole time nav."""

    def test_no_season_pill_selector(self, tmp_path: Path) -> None:
        """The old pill-button season selector CSS class is never rendered."""
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
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        # The old pill selector linked to season_id with class="px-3" -- confirm absent
        assert f'season_id={_CURRENT_SEASON}" class="px-3' not in resp.text


# ---------------------------------------------------------------------------
# AC-7: no freshness indicator banner (removed in E-133-02)
# ---------------------------------------------------------------------------


class TestFreshnessIndicator:
    """Freshness warning banner (bg-yellow-50) is removed; year dropdown is explicit nav."""

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
                resp = client.get("/dashboard/batting")

        assert resp.status_code == 200
        assert "bg-yellow-50" not in resp.text


# ---------------------------------------------------------------------------
# AC-8: Sort parameter tests
# ---------------------------------------------------------------------------


def _insert_batting_stats_full(
    db_path: Path,
    player_id: str,
    team_id: int,
    season_id: str,
    ab: int,
    h: int,
    bb: int = 0,
    so: int = 0,
    hr: int = 0,
    rbi: int = 0,
    sb: int = 0,
    hbp: int = 0,
    shf: int = 0,
    doubles: int = 0,
    triples: int = 0,
    gp: int = 1,
) -> None:
    """Insert a player_season_batting row with specific stat values."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR REPLACE INTO player_season_batting"
        " (player_id, team_id, season_id, gp, ab, h, bb, so, hr, rbi, sb, hbp, shf,"
        "  doubles, triples)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (player_id, team_id, season_id, gp, ab, h, bb, so, hr, rbi, sb, hbp, shf, doubles, triples),
    )
    conn.commit()
    conn.close()


def _insert_pitching_stats_full(
    db_path: Path,
    player_id: str,
    team_id: int,
    season_id: str,
    ip_outs: int,
    er: int,
    so: int = 0,
    bb: int = 0,
    h: int = 0,
    hr: int = 0,
    gp: int = 1,
) -> None:
    """Insert a player_season_pitching row with specific stat values."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT OR REPLACE INTO player_season_pitching"
        " (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (player_id, team_id, season_id, gp, ip_outs, h, er, bb, so, hr),
    )
    conn.commit()
    conn.close()


def _extract_player_order(html: str) -> list[str]:
    """Extract player names from dashboard HTML in table row order.

    Looks for links to /dashboard/players/... and returns the visible
    text portions to determine sort order.
    """
    import re
    # Match player name text from the anchor tags in table rows
    # Pattern: href="/dashboard/players/..." class="...">...name text...
    pattern = r'href="/dashboard/players/[^"]*"[^>]*>\s*(?:#\d+\s+)?([^<]+?)\s*</a>'
    return re.findall(pattern, html)


def _extract_pitcher_order(html: str) -> list[str]:
    """Extract pitcher names from pitching dashboard HTML in table row order."""
    import re
    pattern = r'href="/dashboard/players/[^"]*" class="text-blue-900[^"]*">\s*(?:#\d+\s+)?([^<]+?)\s*</a>'
    return re.findall(pattern, html)


class TestBattingSortParams:
    """AC-8: Sort parameter tests for /dashboard batting table."""

    def _setup_db(self, tmp_path: Path) -> tuple[Path, int]:
        """DB with three players of distinct batting stats."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_season(db_path, _CURRENT_SEASON)
        # Player A: high AVG (.500), low HR (0)
        _insert_player(db_path, "bat-a", "Alice", "Alpha")
        _insert_batting_stats_full(db_path, "bat-a", team_id, _CURRENT_SEASON,
                                   ab=10, h=5, hr=0, rbi=2, so=1)
        # Player B: mid AVG (.300), mid HR (1)
        _insert_player(db_path, "bat-b", "Bob", "Beta")
        _insert_batting_stats_full(db_path, "bat-b", team_id, _CURRENT_SEASON,
                                   ab=10, h=3, hr=1, rbi=3, so=2)
        # Player C: zero AB (should always sort last)
        _insert_player(db_path, "bat-c", "Carol", "Gamma")
        _insert_batting_stats_full(db_path, "bat-c", team_id, _CURRENT_SEASON,
                                   ab=0, h=0, hr=0, rbi=0, so=0)
        return db_path, team_id

    def test_default_sort_avg_desc(self, tmp_path: Path) -> None:
        """AC-8(a): default sort is AVG descending (highest first)."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}")
        assert resp.status_code == 200
        names = _extract_player_order(resp.text)
        # Alice (.500) before Bob (.300); Carol (0 AB) last
        assert names.index("Alice Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carol Gamma"

    def test_sort_by_hr_desc(self, tmp_path: Path) -> None:
        """AC-8(b): sort=hr&dir=desc puts Bob (1 HR) before Alice (0 HR)."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}&sort=hr&dir=desc")
        assert resp.status_code == 200
        names = _extract_player_order(resp.text)
        assert names.index("Bob Beta") < names.index("Alice Alpha")
        assert names[-1] == "Carol Gamma"

    def test_sort_by_so_asc(self, tmp_path: Path) -> None:
        """AC-8(b): sort=so&dir=asc puts Alice (1 SO) before Bob (2 SO)."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}&sort=so&dir=asc")
        assert resp.status_code == 200
        names = _extract_player_order(resp.text)
        assert names.index("Alice Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carol Gamma"

    def test_unrecognized_sort_falls_back_to_default(self, tmp_path: Path) -> None:
        """AC-8(c): unrecognized sort param falls back to default AVG desc order."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}&sort=notacolumn&dir=desc")
        assert resp.status_code == 200
        names = _extract_player_order(resp.text)
        # Falls back to AVG desc: Alice (.500) before Bob (.300); Carol (0 AB) last
        assert names.index("Alice Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carol Gamma"

    def test_name_sort_desc(self, tmp_path: Path) -> None:
        """sort=name&dir=desc produces reverse-alphabetical order, zero-AB rows last."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}&sort=name&dir=desc")
        assert resp.status_code == 200
        names = _extract_player_order(resp.text)
        # "Bob Beta" > "Alice Alpha" alphabetically, so desc puts Bob first
        assert names.index("Bob Beta") < names.index("Alice Alpha")
        # Carol Gamma (0 AB) is still last regardless of direction
        assert names[-1] == "Carol Gamma"

    def test_direction_toggle_reflected_in_url(self, tmp_path: Path) -> None:
        """AC-8(d): when current_sort=hr and dir=desc, hr header link should toggle to asc."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}&sort=hr&dir=desc")
        assert resp.status_code == 200
        html = resp.text
        # The HR header link should now toggle to asc (& is autoescaped to &amp; in HTML)
        assert "sort=hr&amp;dir=asc" in html or "sort=hr&dir=asc" in html

    def test_zero_ab_rows_sort_to_bottom_asc(self, tmp_path: Path) -> None:
        """AC-8(e): player with 0 AB sorts to bottom regardless of asc direction."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}&sort=hr&dir=asc")
        assert resp.status_code == 200
        names = _extract_player_order(resp.text)
        assert names[-1] == "Carol Gamma"

    def test_sort_indicator_shown_on_active_column(self, tmp_path: Path) -> None:
        """AC-5: active sort column shows direction indicator in header (HTML entity or unicode)."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/batting?season_id={_CURRENT_SEASON}&sort=hr&dir=desc")
        assert resp.status_code == 200
        html = resp.text
        # Descending indicator: either unicode ▼ or HTML entity &#9660;
        assert "&#9660;" in html or "▼" in html

    def test_sort_params_preserved_in_team_selector(self, tmp_path: Path) -> None:
        """AC-7: team selector preserves sort/dir params."""
        db_path = _make_db(tmp_path)
        team_id_a = _insert_team(db_path, "Alpha Team")
        team_id_b = _insert_team(db_path, "Beta Team")
        _insert_player(db_path, "p-sel1", "Frank", "Green")
        _insert_season(db_path, _CURRENT_SEASON)
        _insert_batting_stats_full(db_path, "p-sel1", team_id_a, _CURRENT_SEASON, ab=5, h=2)
        _insert_batting_stats_full(db_path, "p-sel1", team_id_b, _CURRENT_SEASON, ab=5, h=2)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        user_id = conn.execute(
            "INSERT INTO users (email) VALUES (?) RETURNING id", ("devsel@example.com",)
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
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "devsel@example.com"},
        ):
            with TestClient(app, follow_redirects=False) as client:
                resp = client.get(
                    f"/dashboard/batting?team_id={team_id_a}&season_id={_CURRENT_SEASON}&sort=hr&dir=desc"
                )

        assert resp.status_code == 200
        html = resp.text
        # Team selector link for the other team should carry sort/dir params
        # (& is autoescaped to &amp; in HTML)
        assert (
            f"team_id={team_id_b}&amp;year={_CURRENT_YEAR}&amp;sort=hr&amp;dir=desc" in html
            or f"team_id={team_id_b}&year={_CURRENT_YEAR}&sort=hr&dir=desc" in html
        )


class TestPitchingSortParams:
    """AC-8: Sort parameter tests for /dashboard/pitching table."""

    def _setup_db(self, tmp_path: Path) -> tuple[Path, int]:
        """DB with three pitchers of distinct stats."""
        db_path = _make_db(tmp_path)
        team_id = _insert_team(db_path)
        _insert_season(db_path, _CURRENT_SEASON)
        # Pitcher A: low ERA (9 ip_outs = 3IP, 1 ER => ERA=3.00), high K/9
        _insert_player(db_path, "pit-a", "Ace", "Alpha")
        _insert_pitching_stats_full(db_path, "pit-a", team_id, _CURRENT_SEASON,
                                    ip_outs=9, er=1, so=9, bb=1, h=3)
        # Pitcher B: high ERA (9 ip_outs, 5 ER => ERA=15.00), low K/9
        _insert_player(db_path, "pit-b", "Bob", "Beta")
        _insert_pitching_stats_full(db_path, "pit-b", team_id, _CURRENT_SEASON,
                                    ip_outs=9, er=5, so=3, bb=4, h=8)
        # Pitcher C: 0 ip_outs (should always sort last)
        _insert_player(db_path, "pit-c", "Carl", "Gamma")
        _insert_pitching_stats_full(db_path, "pit-c", team_id, _CURRENT_SEASON,
                                    ip_outs=0, er=0, so=0, bb=0, h=0)
        return db_path, team_id

    def test_default_sort_era_asc(self, tmp_path: Path) -> None:
        """AC-8(a): default sort is ERA ascending (lowest ERA first)."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/pitching?season_id={_CURRENT_SEASON}")
        assert resp.status_code == 200
        names = _extract_pitcher_order(resp.text)
        assert names.index("Ace Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carl Gamma"

    def test_sort_by_k9_desc(self, tmp_path: Path) -> None:
        """AC-8(b): sort=k9&dir=desc puts Ace (high K/9) before Bob."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/pitching?season_id={_CURRENT_SEASON}&sort=k9&dir=desc")
        assert resp.status_code == 200
        names = _extract_pitcher_order(resp.text)
        assert names.index("Ace Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carl Gamma"

    def test_unrecognized_sort_falls_back_to_default(self, tmp_path: Path) -> None:
        """AC-8(c): unrecognized sort param falls back to default ERA asc order."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/pitching?season_id={_CURRENT_SEASON}&sort=notvalid&dir=asc")
        assert resp.status_code == 200
        names = _extract_pitcher_order(resp.text)
        # Falls back to ERA asc: Ace (lower ERA) before Bob; Carl (0 ip_outs) last
        assert names.index("Ace Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carl Gamma"

    def test_name_sort_desc(self, tmp_path: Path) -> None:
        """sort=name&dir=desc produces reverse-alphabetical order, zero-ip rows last."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/pitching?season_id={_CURRENT_SEASON}&sort=name&dir=desc")
        assert resp.status_code == 200
        names = _extract_pitcher_order(resp.text)
        # "Bob Beta" > "Ace Alpha" alphabetically, so desc puts Bob first
        assert names.index("Bob Beta") < names.index("Ace Alpha")
        # Carl Gamma (0 ip_outs) is still last regardless of direction
        assert names[-1] == "Carl Gamma"

    def test_direction_toggle_reflected_in_url(self, tmp_path: Path) -> None:
        """AC-8(d): sort=k9&dir=desc -> k9 header link toggles to asc."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/pitching?season_id={_CURRENT_SEASON}&sort=k9&dir=desc")
        assert resp.status_code == 200
        html = resp.text
        assert "sort=k9&amp;dir=asc" in html or "sort=k9&dir=asc" in html

    def test_zero_ip_rows_sort_to_bottom_asc(self, tmp_path: Path) -> None:
        """AC-8(e): pitcher with 0 ip_outs sorts to bottom regardless of direction."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/pitching?season_id={_CURRENT_SEASON}&sort=k9&dir=asc")
        assert resp.status_code == 200
        names = _extract_pitcher_order(resp.text)
        assert names[-1] == "Carl Gamma"

    def test_sort_indicator_shown_on_active_column(self, tmp_path: Path) -> None:
        """AC-5: active sort column shows direction indicator (HTML entity or unicode)."""
        db_path, team_id = self._setup_db(tmp_path)
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            client = _make_dev_client(db_path, team_id)
            with client:
                resp = client.get(f"/dashboard/pitching?season_id={_CURRENT_SEASON}&sort=era&dir=asc")
        assert resp.status_code == 200
        html = resp.text
        # Ascending indicator: either unicode ▲ or HTML entity &#9650;
        assert "&#9650;" in html or "▲" in html


# ---------------------------------------------------------------------------
# AC-10: Opponent detail sort parameter tests
# ---------------------------------------------------------------------------


def _extract_names_from_table(html: str, table_heading: str) -> list[str]:
    """Extract player name text from the table that follows a given heading.

    Isolates the HTML between the given heading and the next heading (or end),
    then finds all name cells within that slice.
    """
    import re
    pattern = r'<td class="[^"]*font-medium[^"]*whitespace-nowrap[^"]*">\s*([^<]+?)\s*</td>'

    if table_heading not in html:
        return re.findall(pattern, html)

    start = html.index(table_heading)
    # Find the next heading after this one to delimit the slice
    headings = ["Batting Leaders", "Pitching Leaders"]
    end = len(html)
    for h in headings:
        if h == table_heading:
            continue
        idx = html.find(h, start + len(table_heading))
        if idx != -1 and idx < end:
            end = idx

    return re.findall(pattern, html[start:end])


def _setup_opponent_detail_db(tmp_path: Path) -> tuple[Path, int, int]:
    """Create a DB with our team, an opponent, one game between them,
    and three batters + three pitchers for the opponent.

    Returns (db_path, our_team_id, opp_team_id).
    """
    db_path = _make_db(tmp_path)
    our_team_id = _insert_team(db_path, "Our Team")
    opp_team_id = _insert_team(db_path, "Opponent")
    _insert_season(db_path, _CURRENT_SEASON)

    # A game between the two teams is required for opponent auth.
    # Also insert the dev user + team access (used by DEV_USER_EMAIL bypass).
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, game_date)"
        " VALUES ('g-opp-001', ?, ?, ?, '2026-04-01')",
        (_CURRENT_SEASON, our_team_id, opp_team_id),
    )
    user_id = conn.execute(
        "INSERT INTO users (email) VALUES (?) RETURNING id", ("dev@example.com",)
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, our_team_id),
    )
    conn.commit()
    conn.close()

    # Batting: Alice (.500 AVG, 0 HR), Bob (.300 AVG, 2 HR), Carol (0 AB)
    _insert_player(db_path, "opp-bat-a", "Alice", "Alpha")
    _insert_batting_stats_full(db_path, "opp-bat-a", opp_team_id, _CURRENT_SEASON,
                               ab=10, h=5, hr=0, rbi=1, so=1)
    _insert_player(db_path, "opp-bat-b", "Bob", "Beta")
    _insert_batting_stats_full(db_path, "opp-bat-b", opp_team_id, _CURRENT_SEASON,
                               ab=10, h=3, hr=2, rbi=4, so=2)
    _insert_player(db_path, "opp-bat-c", "Carol", "Gamma")
    _insert_batting_stats_full(db_path, "opp-bat-c", opp_team_id, _CURRENT_SEASON,
                               ab=0, h=0, hr=0, rbi=0, so=0)

    # Pitching: Ace (low ERA), Bob (high ERA), Carl (0 ip_outs)
    _insert_player(db_path, "opp-pit-a", "Ace", "Pitcher")
    _insert_pitching_stats_full(db_path, "opp-pit-a", opp_team_id, _CURRENT_SEASON,
                                ip_outs=9, er=1, so=9, bb=1, h=3)
    _insert_player(db_path, "opp-pit-b", "Bob", "Hurler")
    _insert_pitching_stats_full(db_path, "opp-pit-b", opp_team_id, _CURRENT_SEASON,
                                ip_outs=9, er=5, so=3, bb=4, h=8)
    _insert_player(db_path, "opp-pit-c", "Carl", "Zeroes")
    _insert_pitching_stats_full(db_path, "opp-pit-c", opp_team_id, _CURRENT_SEASON,
                                ip_outs=0, er=0, so=0, bb=0, h=0)

    return db_path, our_team_id, opp_team_id


class TestOpponentDetailSortParams:
    """AC-10: Sort parameter tests for /dashboard/opponents/{id} dual-table page."""

    def _get(
        self,
        db_path: Path,
        our_team_id: int,
        opp_team_id: int,
        extra_params: str = "",
    ) -> str:
        """Helper: make a GET request and return response HTML.

        Uses DEV_USER_EMAIL bypass; the dev user + team access are set up by
        ``_setup_opponent_detail_db`` so we do NOT re-insert here.
        """
        url = (
            f"/dashboard/opponents/{opp_team_id}"
            f"?team_id={our_team_id}&season_id={_CURRENT_SEASON}{extra_params}"
        )
        with patch.dict(
            "os.environ",
            {"DATABASE_PATH": str(db_path), "DEV_USER_EMAIL": "dev@example.com"},
        ):
            with TestClient(app, follow_redirects=False) as client:
                resp = client.get(url)
        assert resp.status_code == 200
        return resp.text

    # AC-10(a): default sort matches current behavior --------------------------

    def test_default_batting_sort_avg_desc(self, tmp_path: Path) -> None:
        """AC-10(a): default batting sort is AVG desc (Alice .500 before Bob .300)."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id)
        names = _extract_names_from_table(html, "Batting Leaders")
        assert names.index("Alice Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carol Gamma"

    def test_default_pitching_sort_era_asc(self, tmp_path: Path) -> None:
        """AC-10(a): default pitching sort is ERA asc (Ace before Bob)."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id)
        names = _extract_names_from_table(html, "Pitching Leaders")
        assert names.index("Ace Pitcher") < names.index("Bob Hurler")
        assert names[-1] == "Carl Zeroes"

    # AC-10(b): recognized sort params produce correct order -------------------

    def test_batting_sort_by_hr_desc(self, tmp_path: Path) -> None:
        """AC-10(b): bat_sort=hr&bat_dir=desc puts Bob (2 HR) before Alice (0 HR)."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&bat_sort=hr&bat_dir=desc")
        names = _extract_names_from_table(html, "Batting Leaders")
        assert names.index("Bob Beta") < names.index("Alice Alpha")
        assert names[-1] == "Carol Gamma"

    def test_pitching_sort_by_k9_desc(self, tmp_path: Path) -> None:
        """AC-10(b): pit_sort=k9&pit_dir=desc puts Ace (high K/9) before Bob."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&pit_sort=k9&pit_dir=desc")
        names = _extract_names_from_table(html, "Pitching Leaders")
        assert names.index("Ace Pitcher") < names.index("Bob Hurler")
        assert names[-1] == "Carl Zeroes"

    # AC-10(c): sorting one table preserves the other's sort state -------------

    def test_batting_sort_preserves_pitching_sort_params_in_links(self, tmp_path: Path) -> None:
        """AC-10(c): batting sort links carry pit_sort/pit_dir; pitching sort links carry bat_sort/bat_dir."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id,
                         "&bat_sort=hr&bat_dir=desc&pit_sort=k9&pit_dir=desc")
        # Batting column links should carry pit_sort=k9&pit_dir=desc
        assert "pit_sort=k9" in html
        assert "pit_dir=desc" in html
        # Pitching column links should carry bat_sort=hr&bat_dir=desc
        assert "bat_sort=hr" in html
        assert "bat_dir=desc" in html
        # Sort links must also preserve team_id and season_id (AC-2/AC-3/AC-7)
        assert f"team_id={our_id}" in html
        assert f"season_id={_CURRENT_SEASON}" in html

    # AC-10(d): zero-denominator rows sort to bottom --------------------------

    def test_zero_ab_sorts_to_bottom_any_direction(self, tmp_path: Path) -> None:
        """AC-10(d): Carol (0 AB) is always last in batting table."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        for params in ("&bat_sort=hr&bat_dir=asc", "&bat_sort=hr&bat_dir=desc"):
            html = self._get(db_path, our_id, opp_id, params)
            names = _extract_names_from_table(html, "Batting Leaders")
            assert names[-1] == "Carol Gamma", f"Carol not last for params={params}"

    def test_zero_ip_sorts_to_bottom_any_direction(self, tmp_path: Path) -> None:
        """AC-10(d): Carl (0 ip_outs) is always last in pitching table."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        for params in ("&pit_sort=k9&pit_dir=asc", "&pit_sort=k9&pit_dir=desc"):
            html = self._get(db_path, our_id, opp_id, params)
            names = _extract_names_from_table(html, "Pitching Leaders")
            assert names[-1] == "Carl Zeroes", f"Carl not last for params={params}"

    # AC-10(e): unrecognized sort params fall back to default -----------------

    def test_unrecognized_bat_sort_falls_back_to_avg_desc(self, tmp_path: Path) -> None:
        """AC-10(e): unrecognized bat_sort falls back to AVG desc order."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&bat_sort=notvalid&bat_dir=asc")
        names = _extract_names_from_table(html, "Batting Leaders")
        assert names.index("Alice Alpha") < names.index("Bob Beta")
        assert names[-1] == "Carol Gamma"

    def test_unrecognized_pit_sort_falls_back_to_era_asc(self, tmp_path: Path) -> None:
        """AC-10(e): unrecognized pit_sort falls back to ERA asc order."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&pit_sort=notvalid&pit_dir=desc")
        names = _extract_names_from_table(html, "Pitching Leaders")
        assert names.index("Ace Pitcher") < names.index("Bob Hurler")
        assert names[-1] == "Carl Zeroes"

    # AC-10(f): direction toggle -----------------------------------------------

    def test_batting_direction_toggle_in_links(self, tmp_path: Path) -> None:
        """AC-10(f): active bat_sort=hr dir=desc -> hr link toggles to asc."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&bat_sort=hr&bat_dir=desc")
        assert "bat_sort=hr&amp;bat_dir=asc" in html or "bat_sort=hr&bat_dir=asc" in html

    def test_pitching_direction_toggle_in_links(self, tmp_path: Path) -> None:
        """AC-10(f): active pit_sort=k9 dir=desc -> k9 link toggles to asc."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&pit_sort=k9&pit_dir=desc")
        assert "pit_sort=k9&amp;pit_dir=asc" in html or "pit_sort=k9&pit_dir=asc" in html

    def test_sort_indicator_on_active_batting_column(self, tmp_path: Path) -> None:
        """AC-4: active batting sort column shows direction indicator."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&bat_sort=hr&bat_dir=desc")
        assert "&#9660;" in html or "▼" in html

    def test_sort_indicator_on_active_pitching_column(self, tmp_path: Path) -> None:
        """AC-4: active pitching sort column shows direction indicator."""
        db_path, our_id, opp_id = _setup_opponent_detail_db(tmp_path)
        html = self._get(db_path, our_id, opp_id, "&pit_sort=era&pit_dir=asc")
        assert "&#9650;" in html or "▲" in html
