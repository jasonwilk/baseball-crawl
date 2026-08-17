"""Tests for the report generation pipeline (E-172-02, E-176-02, E-185-01)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.db.teams import EnsureTeamResult
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
from src.gamechanger.loaders.game_loader import GameLoader
from src.gamechanger.types import TeamRef
import src.reports.generator as _gen
from src.api.helpers import era_basis_innings
from src.gamechanger.exceptions import ForbiddenError
from src.gamechanger.opponent_ladder import TEAM_DETAIL_ACCEPT
from src.reports.generator import (
    GenerationResult,
    _ReportGeneration,
    _SprayOutcome,
    _check_rate_plausibility,
    _compute_pitching_rates,
    _crawl_and_load_spray,
    _create_report_row,
    _extract_innings_per_game,
    _log_rate_plausibility_warnings,
    _query_batting,
    _query_freshness,
    _query_pitching,
    _query_recent_games,
    _query_record,
    _query_roster,
    _query_runs_avg,
    _resolve_gc_uuid,
    _update_report_failed,
    _update_report_ready,
    generate_report,
)

# E-256-04 / TN-13: the lifecycle + deletion stack moved to the client-free
# src/reports/lifecycle.py. Tests that exercise the reaper or the expiry sweep
# must also patch `src.reports.lifecycle._REPO_ROOT` / `._REPORTS_DIR`, because
# those functions now read *lifecycle's* module globals.
from src.reports.lifecycle import (
    CleanupResult,
    ReaperResult,
    STALE_GENERATING_SECONDS,
    cascade_delete_team,
    cleanup_expired_reports,
    cleanup_orphan_teams,
    list_reports,
    reap_stale_generating_reports,
)
from tests.conftest import load_real_schema

# Verify removed functions are no longer importable (AC-1, AC-2)
_REMOVED_NAMES = [
    "_resolve_and_crawl_spray",
    "_build_boxscore_uuid_map",
    "_crawl_spray_via_boxscore_uuids",
    "_resolve_gc_uuid_via_search",
    "_UUID_RE",
    "_PLAYER_STATS_ACCEPT",
    # E-235-04: the global pre/post team-id snapshot diff was replaced by an
    # in-memory per-run created-set; the snapshot helper no longer exists.
    "_snapshot_team_ids",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path):
    """Create a disk-backed DB with the production schema for testing.

    Uses load_real_schema so FK enforcement matches production -- tests that
    insert into child tables must first seed the required parent rows.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    load_real_schema(conn)
    conn.commit()
    yield conn
    conn.close()


def _seed_team(db, name="Test Tigers", public_id="abc123"):
    """Insert a team and return its id."""
    cursor = db.execute(
        "INSERT INTO teams (name, public_id, season_year, membership_type) "
        "VALUES (?, ?, 2026, 'tracked')",
        (name, public_id),
    )
    db.commit()
    return cursor.lastrowid


def _seed_season(db, season_id="2026"):
    db.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES (?, ?, 2026)",
        (season_id, season_id),
    )
    db.commit()


def _seed_player(db, player_id="p1", first="John", last="Smith"):
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first, last),
    )
    db.commit()


def _seed_roster(db, team_id, player_id="p1", season_id="2026", jersey="12"):
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) VALUES (?, ?, ?, ?)",
        (team_id, player_id, season_id, jersey),
    )
    db.commit()


def _seed_completed_game(db, season_id="2026", team_id=1, game_id="seed-g1"):
    """Seed one completed game WITH per-game stat data in the team's DERIVED season.

    The E-235-03 no-completed-games gate (a) aborts when ``_query_freshness``
    counts zero completed games with data (N=0). Pipeline tests that mock the
    loader insert no real game rows, so without this the gate would fire. The
    derived season for the default seeded team (season_year=2026, no program)
    is the year-only ``'2026'``. ``home``/``away`` both reference the subject
    team.

    A bare ``games`` row is NOT "with data": after E-235 Phase 4b HIGH-1,
    ``_query_freshness`` requires a ``player_game_batting``/``player_game_pitching``
    row for the team (a completed games row can exist with zero stat rows). So
    this helper also seeds one real batting line, making N>0 honest.
    """
    db.execute(
        "INSERT INTO seasons (season_id, name, year) "
        "VALUES (?, ?, 2026) ON CONFLICT(season_id) DO NOTHING",
        (season_id, season_id),
    )
    db.execute(
        "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
        "home_score, away_score, game_date) VALUES (?, ?, ?, ?, 5, 3, '2026-04-01')",
        (game_id, season_id, team_id, team_id),
    )
    player_id = f"{game_id}-p1"
    db.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, 'Seed', 'Player')",
        (player_id,),
    )
    db.execute(
        "INSERT INTO player_game_batting "
        "(game_id, player_id, team_id, perspective_team_id, ab, h) "
        "VALUES (?, ?, ?, ?, 3, 1)",
        (game_id, player_id, team_id, team_id),
    )
    db.commit()


def _seed_game(db, team_id, game_id="g1", season_id="2026", game_date="2026-04-01"):
    """Insert a minimal completed game (home=away=team) to hang per-game stat
    rows on. Since the E-259-01 cutover the season readers derive from
    ``player_game_*``, so a per-game stat row needs a parent ``games`` row whose
    ``season_id`` matches the query scope."""
    db.execute(
        "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
        "home_score, away_score, game_date) VALUES (?, ?, ?, ?, 5, 3, ?)",
        (game_id, season_id, team_id, team_id, game_date),
    )
    db.commit()


# ---------------------------------------------------------------------------
# AC-1, AC-2: Removed inline spray functions and constants
# ---------------------------------------------------------------------------


class TestRemovedInlineSprayCode:
    """Verify the old inline spray functions and constants are gone."""

    def test_removed_names_not_in_module(self):
        import src.reports.generator as gen_module

        for name in _REMOVED_NAMES:
            assert not hasattr(gen_module, name), (
                f"{name} should have been removed from generator.py"
            )


# ---------------------------------------------------------------------------
# AC-9(a): Successful generation creates file and DB row
# ---------------------------------------------------------------------------


class TestReportRowManagement:
    """Test reports table row lifecycle."""

    def test_create_report_row(self, db):
        team_id = _seed_team(db)
        row_id = _create_report_row(
            db, "test-slug", team_id, "Test Report",
            "2026-03-28T12:00:00Z", "2026-04-11T12:00:00Z",
        )
        assert row_id is not None

        row = db.execute("SELECT * FROM reports WHERE id = ?", (row_id,)).fetchone()
        assert row is not None
        assert row[1] == "test-slug"  # slug
        assert row[4] == "generating"  # status

    def test_update_report_ready(self, db):
        team_id = _seed_team(db)
        row_id = _create_report_row(
            db, "slug-ready", team_id, "Test",
            "2026-03-28T12:00:00Z", "2026-04-11T12:00:00Z",
        )
        _update_report_ready(db, row_id, "reports/slug-ready.html")

        row = db.execute("SELECT status, report_path FROM reports WHERE id = ?", (row_id,)).fetchone()
        assert row[0] == "ready"
        assert row[1] == "reports/slug-ready.html"

    def test_update_report_failed(self, db):
        team_id = _seed_team(db)
        row_id = _create_report_row(
            db, "slug-fail", team_id, "Test",
            "2026-03-28T12:00:00Z", "2026-04-11T12:00:00Z",
        )
        _update_report_failed(db, row_id, "Something went wrong")

        row = db.execute(
            "SELECT status, error_message FROM reports WHERE id = ?", (row_id,)
        ).fetchone()
        assert row[0] == "failed"
        assert row[1] == "Something went wrong"


# ---------------------------------------------------------------------------
# AC-9(a) E2E: Successful generation creates file + DB row
# ---------------------------------------------------------------------------


class TestGenerateReportE2E:
    """End-to-end test for successful report generation."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_success_creates_file_and_ready_row(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """Successful generation: file on disk, DB row status='ready', result.success."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        _seed_team(db)
        _seed_season(db)
        # Seed a scouting_runs row so _query_season_id finds a season
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")
        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        # Mock scouting pipeline
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        assert result.success is True
        assert result.slug is not None
        assert result.url is not None
        assert "/reports/" in result.url
        assert result.title is not None

        # Verify file was written
        report_file = tmp_path / "data" / "reports" / f"{result.slug}.html"
        assert report_file.exists()
        assert report_file.read_text() == "<html>test</html>"

        # Verify DB row is 'ready' with report_path
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT status, report_path FROM reports WHERE slug = ?",
            (result.slug,),
        ).fetchone()
        verify_conn.close()
        assert row[0] == "ready"
        assert row[1] == f"reports/{result.slug}.html"


# ---------------------------------------------------------------------------
# E-235-02: report_generation_runs population (AC-1, AC-5, AC-7)
# ---------------------------------------------------------------------------


def _read_run_record(db_path: str, slug: str) -> dict | None:
    """Return the report_generation_runs row for ``slug`` as a dict (or None)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT rgr.* FROM report_generation_runs rgr
            JOIN reports r ON r.id = rgr.report_id
            WHERE r.slug = ?
            """,
            (slug,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


class TestRunRecordPopulation:
    """AC-7: the run record is populated for successful and degraded runs."""

    @staticmethod
    def _setup(db, tmp_path, *, seed_game=True):
        _seed_team(db)
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        # A completed game in the derived season ('2026') keeps the no-games
        # gate from firing for the non-no-games scenarios.
        if seed_game:
            _seed_completed_game(db)

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_successful_run_record_is_complete(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """AC-1/AC-5: a successful generation finalizes the run with per-stage
        statuses + per-game counts (M from the schedule, spray games)."""
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        # M = 2 completed games on the schedule (3rd is scheduled, not counted).
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=2,
            games=[
                {"game_status": "completed"},
                {"game_status": "completed"},
                {"game_status": "scheduled"},
            ],
            boxscores={"g1": {}, "g2": {}},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=10)
        # Spray succeeds with 4 games of spray data.
        mock_spray.return_value = _SprayOutcome(status="completed", games_crawled=4)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        assert result.success is True
        run = _read_run_record(db_path, result.slug)
        assert run is not None, "no report_generation_runs row was written"
        assert run["overall_status"] == "completed"
        assert run["started_at"] is not None
        assert run["completed_at"] is not None
        assert run["error_stage"] is None
        assert run["error_message"] is None
        # Per-stage statuses.
        assert run["crawl_status"] == "completed"
        assert run["load_status"] == "completed"
        assert run["load_errors"] == 0  # E-236-09 AC-1: clean load -> 0 errors
        assert run["plays_status"] == "completed"
        assert run["reconciliation_status"] == "completed"
        assert run["spray_status"] == "completed"
        # Per-game counts (M from the schedule; N is an int >= 0).
        assert run["completed_games"] == 2
        assert run["spray_games"] == 4
        assert run["plays_games_expected"] == 2
        assert isinstance(run["completed_games_with_data"], int)
        assert isinstance(run["plays_games_covered"], int)

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_spray_failure_is_degraded_not_fatal(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """AC-7: a spray failure records spray_status='failed' but the
        generation still completes (overall_status='completed')."""
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=2,
            games=[{"game_status": "completed"}], boxscores={},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)
        # Spray FAILS (non-fatal).
        mock_spray.return_value = _SprayOutcome(status="failed", games_crawled=0)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        assert result.success is True, "spray failure must not fail the generation"
        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["overall_status"] == "completed"
        assert run["spray_status"] == "failed"
        assert run["spray_games"] == 0
        # The earlier stages still completed.
        assert run["crawl_status"] == "completed"
        assert run["load_status"] == "completed"

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays")
    def test_plays_failure_is_degraded_not_fatal(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """HIGH-2: a SWALLOWED plays/reconcile failure (recon_out.failed set, []
        returned) records plays_status='failed' + reconciliation_status='failed'
        -- NOT 'completed' -- while the generation still completes."""
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=2,
            games=[{"game_status": "completed"}], boxscores={"g1": {}},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)
        mock_spray.return_value = _SprayOutcome(status="completed", games_crawled=2)

        # Simulate _crawl_and_load_plays swallowing a real failure: it flags the
        # out-param and returns [] (exactly the HIGH-2 internal contract).
        def _plays_fail(*_args, recon_out=None, **_kwargs):
            if recon_out is not None:
                recon_out.failed = True
            return []

        mock_plays.side_effect = _plays_fail

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        assert result.success is True, "plays failure must not fail the generation"
        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["overall_status"] == "completed"
        assert run["plays_status"] == "failed"
        assert run["reconciliation_status"] == "failed"
        # Earlier stages still completed.
        assert run["crawl_status"] == "completed"
        assert run["load_status"] == "completed"

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_partial_load_records_partial_not_completed(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """E-236-09 AC-3/AC-6 (error-path): a load that processed rows but
        reported errors > 0 (e.g. a per-player sqlite3.Error) records
        load_status='partial' + load_errors>0 -- NOT the old hardcoded
        'completed' that overstated success. Same bug class as #1, one stage
        over."""
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=2,
            games=[{"game_status": "completed"}], boxscores={"g1": {}},
        )
        # Some rows loaded AND errors > 0 -> PARTIAL (not total failure).
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5, errors=2)
        mock_spray.return_value = _SprayOutcome(status="completed", games_crawled=2)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        # Partial load is non-fatal -- generation still completes.
        assert result.success is True
        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["load_status"] == "partial"
        assert run["load_errors"] == 2

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_scored_but_empty_clean_load_records_completed(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """E-236-09 AC-4/AC-6 (false-alarm guard): the realistic scored-but-empty
        boxscore (DE sub-case A: team keys present, stat groups empty -> game
        counted, errors=0) records load_status='completed', NOT 'partial'.
        LoadResult.errors does NOT increment for sub-case A (DE+SE consensus),
        so the error-driven status is safe against the plays/spray false-alarm
        class. loaded=1 here is the bare scored-but-empty GAMES ROW (no player
        rows); status MUST derive from the error signal, never from that count."""
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=1,
            games=[{"game_status": "completed"}], boxscores={"g1": {}},
        )
        # Sub-case A: just the game row counted, zero player rows, zero errors.
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=1, errors=0)
        mock_spray.return_value = _SprayOutcome(status="completed", games_crawled=1)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        assert result.success is True
        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["load_status"] == "completed"  # NOT falsely 'partial'
        assert run["load_errors"] == 0

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_total_load_failure_records_failed(
        self, mock_spray, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """E-236-09 AC-5 (defensive): a total load failure (loaded==0 AND
        errors>0 -- DE sub-case B, a degenerate keyless/unreadable boxscore)
        maps to load_status='failed' via the explicit total-failure signal
        BEFORE the classifier (TN-1 precedence), and the run finalizes failed.
        Defensive: api-scout confirmed GC's real 'missing game' is an HTTP 404
        the crawler skips, so this keyless-body path is correct-but-unreached."""
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=1,
            games=[{"game_status": "completed"}], boxscores={"g1": {}},
        )
        # Zero loaded AND errors>0 -> the load stage's OWN total-failure signal.
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=0, errors=1)
        mock_spray.return_value = _SprayOutcome(status="completed", games_crawled=0)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        assert result.success is False
        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["load_status"] == "failed"
        assert run["load_errors"] == 1
        assert run["overall_status"] == "failed"
        assert run["error_stage"] == "load"

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    def test_fatal_crawl_marks_run_failed(
        self, mock_ensure, mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """AC-1/AC-3: a fatal crawl (errors>0 AND games_crawled==0) finalizes
        the run as failed with error_stage='crawl'."""
        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        # Fatal: errors > 0 AND games_crawled == 0.
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=0, errors=1,
            games=[], boxscores={},
        )

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        assert result.success is False
        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["overall_status"] == "failed"
        assert run["crawl_status"] == "failed"
        assert run["error_stage"] == "crawl"
        assert run["completed_at"] is not None
        # M is recorded even on the fatal path (0 completed games here).
        assert run["completed_games"] == 0

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_partial_crawl_records_partial_status(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """E-236-03 AC-1/AC-2: a partial boxscore crawl (M>0,
        0 < boxscores_fetched < M) records crawl_status='partial' and the
        boxscores_fetched count -- NOT 'completed' as it was before this story.
        """
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        # M = 2 completed games on the schedule, but only 1 boxscore fetched.
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=1, errors=0,
            games=[{"game_status": "completed"}, {"game_status": "completed"}],
            boxscores={"g1": {}},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)
        mock_spray.return_value = _SprayOutcome(status="completed", games_crawled=1)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        run = _read_run_record(db_path, result.slug)
        assert run is not None
        # AC-2: partial, not "completed".
        assert run["crawl_status"] == "partial"
        # AC-1: boxscores_fetched written + lands (real-schema round-trip,
        # proves it is in the _RUN_RECORD_COLUMNS allowlist).
        assert run["boxscores_fetched"] == 1
        assert run["completed_games"] == 2

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_full_crawl_records_completed_and_boxscores_fetched(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """E-236-03 AC-1/AC-4: a fully-fetched crawl (boxscores_fetched == M,
        M>0) records crawl_status='completed' and boxscores_fetched == M."""
        from src.gamechanger.loaders import LoadResult

        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=2, errors=0,
            games=[{"game_status": "completed"}, {"game_status": "completed"}],
            boxscores={"g1": {}, "g2": {}},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=10)
        mock_spray.return_value = _SprayOutcome(status="completed", games_crawled=2)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["crawl_status"] == "completed"
        assert run["boxscores_fetched"] == 2
        assert run["completed_games"] == 2

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    def test_all_blocked_crawl_fails_not_no_games(
        self, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """E-236-03 AC-3/AC-5/AC-6 (SQ1, FINAL): an all-blocked crawl (M>0,
        boxscores_fetched == 0) with ZERO crawl errors surfaces as a HARD
        FAILURE -- crawl_status='failed', overall_status='failed',
        outcome='failed', reports.status='failed' (the FAILED branch, NOT
        no_games), no shareable page rendered -- instead of slipping silently to
        a misleading no_games outcome.

        errors=0 is deliberate: it proves the count-based gate
        (boxscores_fetched == 0 AND completed_games > 0) fires on its own, not
        via the pre-existing errors>0 disjunct.
        """
        self._setup(db, tmp_path)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        # All-blocked: M = 2 completed games, but every boxscore fetch blocked
        # (games_crawled == 0) and NO crawl-level error flag set (errors == 0).
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=0, errors=0,
            games=[{"game_status": "completed"}, {"game_status": "completed"}],
            boxscores={},
        )

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        # AC-3/AC-5: the failure branch is taken.
        assert result.success is False
        assert result.outcome == "failed"
        run = _read_run_record(db_path, result.slug)
        assert run is not None
        assert run["crawl_status"] == "failed"
        assert run["overall_status"] == "failed"
        assert run["error_stage"] == "crawl"
        assert run["boxscores_fetched"] == 0
        assert run["completed_games"] == 2

        # AC-6: the report row is FAILED (not no_games) and no shareable page
        # was rendered -- the full render stage never ran.
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT status, report_path FROM reports WHERE slug = ?",
            (result.slug,),
        ).fetchone()
        verify_conn.close()
        assert row[0] == "failed", "all-blocked must persist 'failed', NOT 'no_games'"
        mock_render.assert_not_called()


# ---------------------------------------------------------------------------
# E-199: Plays-stage auth expiry is non-fatal
# ---------------------------------------------------------------------------


class TestPlaysStageAuthExpiry:
    """AC-5: Auth expiry during plays stage does not fail the report."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_auth_expiry_in_plays_stage_yields_success(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        from src.gamechanger.client import CredentialExpiredError
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult
        from src.reports.generator import generate_report

        _seed_team(db)
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        # Plays stage raises CredentialExpiredError
        mock_plays.side_effect = CredentialExpiredError("token expired")
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        assert result.success is True
        assert result.slug is not None


# ---------------------------------------------------------------------------
# AC-9(b): Failed generation sets 'failed' with error message
# ---------------------------------------------------------------------------


class TestGenerateReportFailures:
    """Test failure modes of generate_report."""

    def test_invalid_url_returns_failure(self):
        result = generate_report("")
        assert not result.success
        assert result.error_message is not None

    def test_uuid_url_returns_failure(self):
        result = generate_report("72bb77d8-54ca-42d2-8547-9da4880d0cb4")
        assert not result.success
        assert "UUID" in result.error_message

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    def test_credential_expired_sets_failed(
        self, mock_ensure, mock_client_cls, mock_get_conn, db, tmp_path
    ):
        """AC-8: CredentialExpiredError produces a clear error message."""
        from src.gamechanger.client import CredentialExpiredError

        _seed_team(db)
        # E-273-02: generate_report's opportunistic cleanup_expired_reports runs
        # the orphan-reclamation pass at generation START. This fixture pins
        # ensure_team_row to id=1 (below), so team 1 must survive that sweep. In
        # production the target team is created fresh AFTER cleanup, so it is
        # never swept -- the pin is a test artifact this compensates for.
        #
        # E-277-01: team 1 stays 'tracked' (the PRODUCTION shape) and is pinned
        # by a reachability ROOT instead. E-273-02 flipped it to 'member', which
        # kept the test green but stopped it covering the shape production
        # actually uses. opponent_links is the pinning mechanism for all three
        # restored fixtures in this file: it is the pre-existing load-bearing
        # root, so a future epic revisiting the newer audit root cannot fail
        # these tests for reasons unrelated to what they test.
        db.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
            "VALUES (1, 'root-pin-cred', 'Pinned Opp')"
        )
        db.commit()

        # Return a fresh (unclosed) connection for each get_connection() call
        # since closing() will close it at block exit.
        db_path = str(tmp_path / "test.db")
        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        # Seed the reports table in the on-disk DB via db fixture
        # (the fixture already created it at tmp_path/test.db)

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        with patch("src.reports.generator.ScoutingCrawler") as mock_crawler_cls:
            mock_crawler = MagicMock()
            mock_crawler.scout_team.side_effect = CredentialExpiredError("expired")
            mock_crawler_cls.return_value = mock_crawler

            result = generate_report("abc123")

        assert not result.success
        assert "credentials expired" in result.error_message.lower()
        assert "bb creds setup web" in result.error_message

        # Verify the report row was set to failed
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT status, error_message FROM reports WHERE slug = ?",
            (result.slug,),
        ).fetchone()
        verify_conn.close()
        assert row[0] == "failed"


# ---------------------------------------------------------------------------
# AC-9(c): CLI prints the public URL on success
# ---------------------------------------------------------------------------


class TestCLIOutput:
    """Test CLI command output (via typer test runner)."""

    def test_generate_prints_url_on_success(self):
        """AC-9(c): Verify CLI output contains the URL."""
        from typer.testing import CliRunner
        from src.cli.report import app

        runner = CliRunner()

        mock_result = GenerationResult(
            success=True,
            slug="test-slug-123",
            title="Scouting Report — Test Team",
            url="https://bbstats.ai/reports/test-slug-123",
            outcome="ready",  # E-236-05: CLI generate branches on outcome
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "https://web.gc.com/teams/abc/test"])

        assert result.exit_code == 0
        assert "test-slug-123" in result.output
        assert "https://bbstats.ai/reports/test-slug-123" in result.output

    def test_generate_prints_error_on_failure(self):
        from typer.testing import CliRunner
        from src.cli.report import app

        runner = CliRunner()

        mock_result = GenerationResult(
            success=False,
            error_message="Something went wrong",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 1
        assert "Something went wrong" in result.output


# ---------------------------------------------------------------------------
# AC-9(d): bb report list displays report rows
# ---------------------------------------------------------------------------


class TestListReports:
    """Test bb report list command."""

    def test_list_displays_reports(self):
        from typer.testing import CliRunner
        from src.cli.report import app

        runner = CliRunner()

        mock_reports = [
            {
                "slug": "slug1",
                "title": "Report A",
                "status": "ready",
                "generated_at": "2026-03-28T12:00:00Z",
                "expires_at": "2026-04-11T12:00:00Z",
                "url": "https://bbstats.ai/reports/slug1",
                "is_expired": False,
            },
            {
                "slug": "slug2",
                "title": "Report B",
                "status": "failed",
                "generated_at": "2026-03-27T12:00:00Z",
                "expires_at": "2026-04-10T12:00:00Z",
                "url": "https://bbstats.ai/reports/slug2",
                "is_expired": False,
            },
        ]
        with patch("src.cli.report.list_reports", return_value=mock_reports):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Report A" in result.output
        assert "Report B" in result.output

    def test_list_empty(self):
        from typer.testing import CliRunner
        from src.cli.report import app

        runner = CliRunner()

        with patch("src.cli.report.list_reports", return_value=[]):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No reports found" in result.output


def _seed_report_row(db, team_id, *, slug="rep-x", status="ready", error_message=None):
    cur = db.execute(
        "INSERT INTO reports (slug, team_id, title, status, generated_at, "
        "expires_at, report_path, error_message) VALUES "
        "(?, ?, 'Rep', ?, '2026-03-28T12:00:00Z', '2999-01-01T00:00:00Z', NULL, ?)",
        (slug, team_id, status, error_message),
    )
    db.commit()
    return cur.lastrowid


def _seed_run_row(db, report_id, **cols):
    keys = ["report_id", *cols.keys()]
    placeholders = ",".join("?" for _ in keys)
    db.execute(
        f"INSERT INTO report_generation_runs ({','.join(keys)}) VALUES ({placeholders})",
        [report_id, *cols.values()],
    )
    db.commit()


class TestListReportsWithRunsJoin:
    """E-235-06 / TN-6: the shared list_reports_with_runs join and the CLI
    list_reports() wrapper surface run-record columns + the report-level
    error_message, and stay NULL-safe for legacy reports with no run row."""

    def test_join_surfaces_run_columns_and_flags(self, db):
        from src.api.db import list_reports_with_runs

        team_id = _seed_team(db)
        _seed_season(db)  # season_id_used FK-references seasons(season_id)
        rid = _seed_report_row(db, team_id, slug="complete", status="ready")
        _seed_run_row(
            db, rid,
            overall_status="completed", crawl_status="completed",
            load_status="completed", spray_status="completed", spray_games=5,
            plays_status="completed", plays_games_expected=10,
            plays_games_covered=8, reconciliation_status="completed",
            discrepancies_found=3, discrepancies_corrected=2,
            completed_games=12, completed_games_with_data=11,
            season_id_used="2026",
            identity_match_method="name_only",
            error_stage="load", error_message="run-level msg",
        )

        rows = list_reports_with_runs(db)
        assert len(rows) == 1
        r = rows[0]
        assert r["overall_status"] == "completed"
        assert r["completed_games"] == 12
        assert r["completed_games_with_data"] == 11
        assert r["spray_games"] == 5
        assert r["plays_games_covered"] == 8
        assert r["discrepancies_corrected"] == 2
        assert r["identity_match_method"] == "name_only"
        # Report-level error_message is distinct from the aliased run message.
        assert "error_message" in r
        assert r["run_error_message"] == "run-level msg"
        assert r["error_stage"] == "load"

    def test_join_null_safe_for_report_without_run(self, db):
        from src.api.db import list_reports_with_runs

        team_id = _seed_team(db)
        _seed_report_row(db, team_id, slug="legacy", status="ready")

        rows = list_reports_with_runs(db)
        assert len(rows) == 1
        r = rows[0]
        # LEFT join -> every run column is NULL, no crash.
        assert r["overall_status"] is None
        assert r["completed_games"] is None
        assert r["identity_match_method"] is None
        assert r["run_error_message"] is None

    def test_cli_list_reports_gains_error_message_and_run_cols(self, tmp_path, monkeypatch):
        """AC-3: the CLI list_reports() now returns error_message + the joined
        run columns (it selected neither before), decorated with url/is_expired."""
        import sqlite3 as _sqlite3

        import src.reports.lifecycle as gen  # list_reports moved here (E-256-04)
        from tests.conftest import load_real_schema

        db_path = tmp_path / "cli_list.db"
        seed = _sqlite3.connect(str(db_path))
        load_real_schema(seed)
        team_id = _seed_team(seed)
        rid = _seed_report_row(
            seed, team_id, slug="failed-1", status="failed", error_message="boom"
        )
        _seed_run_row(
            seed, rid, overall_status="failed", error_stage="load",
            error_message="load failed",
        )
        seed.close()

        def _open():
            c = _sqlite3.connect(str(db_path))
            c.execute("PRAGMA foreign_keys=ON")
            return c

        monkeypatch.setattr(gen, "get_connection", _open)

        result = gen.list_reports()
        assert len(result) == 1
        r = result[0]
        assert r["error_message"] == "boom"        # report-level, newly returned
        assert r["overall_status"] == "failed"      # joined run column
        assert r["run_error_message"] == "load failed"
        assert "url" in r and "is_expired" in r      # CLI decoration preserved


class TestEnsureTeamRowIdentityDowngrade:
    """IDEA-127: _ensure_team_row downgrades identity_match_method from
    name_only to anchor when a name-only opponent stub is resolved to a REAL
    public_id anchor within the same run -- so the operator wrong-team badge
    does not fire on a correctly-resolved team. A genuinely unresolved
    name-only match (no public_id to back-fill) must still record name_only.
    """

    def _seed_name_only_stub(self, db_path, name="Summer Sluggers"):
        """Seed a tracked team with NULL public_id/gc_uuid (a game-loader
        name-only opponent stub) and return its id."""
        conn = sqlite3.connect(str(db_path))
        load_real_schema(conn)
        cursor = conn.execute(
            "INSERT INTO teams (name, public_id, gc_uuid, season_year, membership_type) "
            "VALUES (?, NULL, NULL, 2026, 'tracked')",
            (name,),
        )
        stub_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return stub_id

    def _make_ctx(self, public_id, name="Summer Sluggers", season_year=2026):
        ctx = _gen._ReportGeneration("https://web.gc.com/teams/summer-sluggers")
        ctx.public_id = public_id
        ctx.team_name_from_api = name
        ctx.season_year_from_api = season_year
        return ctx

    def test_name_only_stub_downgraded_to_anchor_on_public_id_backfill(self, tmp_path):
        """AC-2 positive: a name-only stub the run resolves (real public_id
        back-filled) records 'anchor', and the anchor is persisted."""
        db_path = tmp_path / "downgrade.db"
        stub_id = self._seed_name_only_stub(db_path)

        def _factory(*_a, **_k):
            c = sqlite3.connect(str(db_path))
            c.execute("PRAGMA foreign_keys=ON")
            return c

        ctx = self._make_ctx(public_id="realpub123")
        with patch("src.reports.generator.get_connection", side_effect=_factory):
            ctx._ensure_team_row()

        # Matched the stub by name, then established a real anchor -> downgraded.
        assert ctx.team_id == stub_id
        assert ctx.identity_match_method == "anchor"
        check = sqlite3.connect(str(db_path))
        row = check.execute(
            "SELECT public_id FROM teams WHERE id=?", (stub_id,)
        ).fetchone()
        check.close()
        assert row[0] == "realpub123"

    def test_unresolved_name_only_still_records_name_only(self, tmp_path):
        """AC-2 negative / SE guard: with public_id=None the back-fill UPDATE
        sets NULL->NULL (rowcount=1) but establishes NO anchor, so the stamp
        must stay name_only -- the downgrade guards on self.public_id IS NOT
        NULL, not rowcount alone."""
        db_path = tmp_path / "unresolved.db"
        stub_id = self._seed_name_only_stub(db_path)

        def _factory(*_a, **_k):
            c = sqlite3.connect(str(db_path))
            c.execute("PRAGMA foreign_keys=ON")
            return c

        ctx = self._make_ctx(public_id=None)
        with patch("src.reports.generator.get_connection", side_effect=_factory):
            ctx._ensure_team_row()

        assert ctx.team_id == stub_id
        assert ctx.identity_match_method == "name_only"
        check = sqlite3.connect(str(db_path))
        row = check.execute(
            "SELECT public_id FROM teams WHERE id=?", (stub_id,)
        ).fetchone()
        check.close()
        assert row[0] is None  # no anchor established

    def test_existing_public_id_anchor_not_disturbed(self, tmp_path):
        """Regression: a team already carrying a public_id resolves via the
        anchor path and is not touched by the downgrade branch (back-fill
        rowcount=0), staying 'anchor'."""
        db_path = tmp_path / "anchor.db"
        conn = sqlite3.connect(str(db_path))
        load_real_schema(conn)
        cursor = conn.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES (?, 'realpub123', 2026, 'tracked')",
            ("Summer Sluggers",),
        )
        team_id = cursor.lastrowid
        conn.commit()
        conn.close()

        def _factory(*_a, **_k):
            c = sqlite3.connect(str(db_path))
            c.execute("PRAGMA foreign_keys=ON")
            return c

        ctx = self._make_ctx(public_id="realpub123")
        with patch("src.reports.generator.get_connection", side_effect=_factory):
            ctx._ensure_team_row()

        assert ctx.team_id == team_id
        assert ctx.identity_match_method == "anchor"


# ---------------------------------------------------------------------------
# E-273-03: team+report creation atomicity (TN-5/TN-6)
# ---------------------------------------------------------------------------


class TestTeamReportAtomicity:
    """The scouted team row and its 'generating' reports row are created in ONE
    transaction, so a team is never visible without its protecting report.
    """

    def test_team_invisible_until_report_committed_then_both_land(self, tmp_path):
        """AC-1: with run()'s shared connection, the teams row and reports/run
        rows are NOT visible to a separate connection until the single commit --
        then all three land together, FK-linked in order teams -> reports -> run.
        """
        db_path = tmp_path / "atomic.db"
        seed = sqlite3.connect(str(db_path))
        load_real_schema(seed)
        seed.close()

        ctx = _gen._ReportGeneration("newpub123")
        ctx.public_id = "newpub123"
        ctx.team_name_from_api = "New Team"
        ctx.season_year_from_api = 2026

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        observer = sqlite3.connect(str(db_path))

        # Mirror run()'s atomic block: both writes on ONE connection, no commit
        # until both have run.
        ctx._ensure_team_row(conn)
        ctx._create_report_and_run_record(conn)

        # Nothing is visible on a separate connection yet -- a single uncommitted
        # transaction, so the team cannot be seen without its report.
        assert observer.execute(
            "SELECT COUNT(*) FROM teams WHERE public_id='newpub123'"
        ).fetchone()[0] == 0
        assert observer.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0
        assert observer.execute(
            "SELECT COUNT(*) FROM report_generation_runs"
        ).fetchone()[0] == 0

        conn.commit()

        # All three now land together, FK-linked.
        team_row = observer.execute(
            "SELECT id FROM teams WHERE public_id='newpub123'"
        ).fetchone()
        assert team_row is not None
        report_row = observer.execute(
            "SELECT id, team_id, status FROM reports"
        ).fetchone()
        assert report_row is not None
        assert report_row[1] == team_row[0]  # reports.team_id -> teams.id
        assert report_row[2] == "generating"
        run_row = observer.execute(
            "SELECT report_id FROM report_generation_runs"
        ).fetchone()
        assert run_row is not None
        assert run_row[0] == report_row[0]  # run.report_id -> reports.id

        conn.close()
        observer.close()

    def test_run_rolls_back_team_when_report_creation_fails(self, tmp_path):
        """AC-2 (error path -- the airtight-gate AC): a failure injected between
        the team write and the reports write leaves NEITHER row committed, so a
        scouted team is never orphaned without its 'generating' reports row.
        """
        db_path = tmp_path / "rollback.db"
        seed = sqlite3.connect(str(db_path))
        load_real_schema(seed)
        seed.close()

        def _factory(*_a, **_k):
            c = sqlite3.connect(str(db_path))
            c.execute("PRAGMA foreign_keys=ON")
            return c

        ctx = _gen._ReportGeneration("newpub123")

        with (
            patch("src.reports.generator.get_connection", side_effect=_factory),
            patch.object(
                _gen._ReportGeneration,
                "_fetch_public_team_info",
                lambda self: setattr(self, "team_name_from_api", "New Team"),
            ),
            patch(
                "src.reports.generator._create_report_row",
                side_effect=RuntimeError("injected report-creation failure"),
            ),
            pytest.raises(RuntimeError),
        ):
            ctx.run()

        # The team INSERT rode the same uncommitted transaction as the failed
        # report write, so it rolled back -- no orphaned team, no report, no run.
        check = sqlite3.connect(str(db_path))
        assert check.execute(
            "SELECT COUNT(*) FROM teams WHERE public_id='newpub123'"
        ).fetchone()[0] == 0
        assert check.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0
        assert check.execute(
            "SELECT COUNT(*) FROM report_generation_runs"
        ).fetchone()[0] == 0
        check.close()


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------


class TestQueryHelpers:
    """Test the individual DB query functions."""

    def test_query_record(self, db):
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        # Add games: 2 wins, 1 loss
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", team_id, opp_id, 5, 3, "2026-03-20"),
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026", opp_id, team_id, 3, 7, "2026-03-21"),
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g3", "2026", team_id, opp_id, 2, 4, "2026-03-22"),
        )
        db.commit()

        record = _query_record(db, team_id, "2026")
        assert record is not None
        assert record["wins"] == 2
        assert record["losses"] == 1
        assert record["ties"] == 0  # E-278-01 widened the contract

    def test_query_record_counts_a_tie_for_both_teams(self, db):
        """AC-1: equal non-null scores contribute 1 tie, 0 wins, 0 losses.

        Before E-278-01 a tie fell through both strict `>` and `<` arms and
        counted as NEITHER -- it vanished from the record entirely, so a coach
        seeing a "T" in the last-five strip found no tie anywhere in the season
        total above it. Asserted from BOTH sides because a tie is symmetric and
        a team-side branch would be a natural way to get it wrong.
        """
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("tie-home", "2026", team_id, opp_id, 4, 4, "2026-03-20"),
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("win", "2026", team_id, opp_id, 5, 3, "2026-03-21"),
        )
        db.commit()

        record = _query_record(db, team_id, "2026")
        assert record == {"wins": 1, "losses": 0, "ties": 1}
        # The same game is a tie from the opponent's side too -- 0 wins, 0
        # losses, 1 tie. A per-team-side tie branch would break this half.
        assert _query_record(db, opp_id, "2026") == {
            "wins": 0, "losses": 1, "ties": 1,
        }

    def test_record_ignores_stat_row_coverage(self, db):
        """AC-3 REGRESSION PIN: the record counts games PLAYED, not games with DATA.

        ⚠️ If this test fails, do NOT make it pass by adjusting the fixture.
        It goes red when a stat-row `EXISTS`, perspective, or coverage condition
        is added to `_query_record` -- which domain review REJECTED (epic TN-7)
        and which measurement condemned: 20 genuine completed-and-scored games
        across 12 of 28 teams carry no stat rows from their own perspective (17
        charted only from the opposing side), so such a gate would silently
        delete 20 real games from twelve coaches' records.

        The two databases here differ ONLY in stat-row presence: this one has
        zero rows in `player_game_batting` and `player_game_pitching`, and its
        record must equal the record computed for the identical games with stat
        rows present.
        """
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        for gid, hs, aws, date in [
            ("s1", 5, 3, "2026-03-20"),
            ("s2", 2, 4, "2026-03-21"),
            ("s3", 6, 6, "2026-03-22"),
        ]:
            db.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, "
                "away_team_id, home_score, away_score, game_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (gid, "2026", team_id, opp_id, hs, aws, date),
            )
        db.commit()

        # Precondition: the stat tables really are empty, so this test cannot
        # pass by accidentally having coverage.
        assert db.execute("SELECT COUNT(*) FROM player_game_batting").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM player_game_pitching").fetchone()[0] == 0

        assert _query_record(db, team_id, "2026") == {
            "wins": 1, "losses": 1, "ties": 1,
        }

    def test_query_recent_games(self, db):
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        for i in range(7):
            db.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"g{i}", "2026", team_id, opp_id, 5 + i, 3, f"2026-03-{20+i:02d}"),
            )
        db.commit()

        games = _query_recent_games(db, team_id, "2026", limit=5)
        assert len(games) == 5
        assert games[0]["result"] == "W"

    def test_query_freshness(self, db):
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        _seed_player(db, "p1", "Jane", "Doe")
        # g1: completed AND has a per-game stat row -> counted.
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", team_id, opp_id, 5, 3, "2026-03-25"),
        )
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES ('g1', 'p1', ?, ?, 3, 1)",
            (team_id, team_id),
        )
        # g2: completed but NO stat rows (scores from schedule, empty boxscore)
        # -> must NOT count toward N, and must not advance the freshness date,
        # even though it is later (E-235 Phase 4b HIGH-1).
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026", team_id, opp_id, 7, 2, "2026-03-28"),
        )
        db.commit()

        date, count = _query_freshness(db, team_id, "2026")
        assert count == 1  # only g1 has stat data
        assert date == "2026-03-25"  # g2 (statless, later) excluded from MAX

    def test_query_freshness_zero_when_games_have_no_stats(self, db):
        """HIGH-1: completed games with no stat rows -> N=0 (gate-(a) fires)."""
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-y")
        _seed_season(db)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", team_id, opp_id, 5, 3, "2026-03-25"),
        )
        db.commit()

        date, count = _query_freshness(db, team_id, "2026")
        assert count == 0
        assert date is None

    def test_query_batting(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p1", "Jane", "Doe")
        _seed_roster(db, team_id, "p1", "2026", "7")
        # Per-game rows summing to the season line (E-259-01: reader SUMs
        # player_game_batting). Split across two games so games=2 is a real SUM.
        _seed_game(db, team_id, "g1")
        _seed_game(db, team_id, "g2")
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb, hbp, shf) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g1", "p1", team_id, team_id, 15, 5, 1, 1, 1, 3, 2, 4, 1, 1, 0),
        )
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb, hbp, shf) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g2", "p1", team_id, team_id, 15, 5, 1, 0, 0, 2, 1, 4, 1, 0, 0),
        )
        db.commit()

        db.row_factory = sqlite3.Row
        batting = _query_batting(db, team_id, "2026")
        assert len(batting) == 1
        assert batting[0]["name"] == "Jane Doe"
        assert batting[0]["ab"] == 30
        assert batting[0]["jersey_number"] == "7"

    def test_query_pitching_with_rates(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p2", "John", "Smith")
        _seed_roster(db, team_id, "p2", "2026", "12")
        # Per-game rows summing to the season line (E-259-01: reader SUMs
        # player_game_pitching).
        _seed_game(db, team_id, "g1")
        _seed_game(db, team_id, "g2")
        db.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, appearance_order, ip_outs, h, er, bb, so, pitches, total_strikes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g1", "p2", team_id, team_id, 1, 24, 11, 4, 5, 16, 160, 96),
        )
        db.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, appearance_order, ip_outs, h, er, bb, so, pitches, total_strikes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g2", "p2", team_id, team_id, 1, 21, 9, 4, 5, 14, 140, 84),
        )
        db.commit()

        db.row_factory = sqlite3.Row
        pitching = _query_pitching(db, team_id, "2026")
        assert len(pitching) == 1
        assert pitching[0]["name"] == "John Smith"
        # Rate fields should be computed
        assert "era" in pitching[0]
        assert "k9" in pitching[0]
        assert "whip" in pitching[0]
        assert "strike_pct" in pitching[0]
        # ERA (E-264): _seed_team leaves innings_per_game NULL, so the basis
        # falls back to 7 -> ERA = (8 * 7 * 3) / 45 = (8 * 21) / 45 = 3.73.
        assert pitching[0]["era"] == "3.73"
        # strike_pct = (total_strikes / pitches) * 100 = (180 / 300) * 100 = 60.0%
        # (preserves the value-level strike_pct coverage formerly in the deleted
        #  dashboard-side tests/test_strike_pct.py -- E-239-02 AC-6b)
        assert pitching[0]["strike_pct"] == "60.0%"

    def test_query_roster(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p1", "Jane", "Doe")
        _seed_roster(db, team_id, "p1", "2026", "7")

        db.row_factory = sqlite3.Row
        roster = _query_roster(db, team_id, "2026")
        assert len(roster) == 1
        assert roster[0]["name"] == "Jane Doe"
        assert roster[0]["jersey_number"] == "7"


# ---------------------------------------------------------------------------
# list_reports function
# ---------------------------------------------------------------------------


class TestListReportsFunction:
    """Test the list_reports query function."""

    @patch("src.reports.lifecycle.get_connection")
    def test_list_reports_returns_sorted(self, mock_get_conn, db):
        team_id = _seed_team(db)
        _create_report_row(
            db, "slug-old", team_id, "Old Report",
            "2026-03-27T12:00:00Z", "2026-04-10T12:00:00Z",
        )
        _create_report_row(
            db, "slug-new", team_id, "New Report",
            "2026-03-28T12:00:00Z", "2026-04-11T12:00:00Z",
        )
        mock_get_conn.return_value = db

        reports = list_reports()
        assert len(reports) == 2
        assert reports[0]["slug"] == "slug-new"  # Newest first
        assert reports[1]["slug"] == "slug-old"
        assert "url" in reports[0]
        assert "is_expired" in reports[0]


# ---------------------------------------------------------------------------
# _crawl_and_load_spray pipeline delegation (E-176-02)
# ---------------------------------------------------------------------------


class TestCrawlAndLoadSpray:
    """Test that _crawl_and_load_spray delegates to the scouting spray pipeline."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    @patch("src.reports.generator.ScoutingSprayChartLoader")
    def test_delegates_to_scouting_spray_pipeline(
        self,
        mock_loader_cls,
        mock_crawler_cls,
        mock_get_conn,
        db,
        tmp_path,
    ):
        """Happy path: crawler.crawl_team + loader.load_from_data are called."""
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_crawler = MagicMock()
        mock_crawler_cls.return_value = mock_crawler
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        client = MagicMock()

        _crawl_and_load_spray(client, "abc123", "2026")

        mock_crawler.crawl_team.assert_called_once_with(
            "abc123", season_id="2026", gc_uuid=None,
            games_data=None,
        )
        mock_loader.load_from_data.assert_called_once()
        call_kwargs = mock_loader.load_from_data.call_args
        assert call_kwargs[1]["public_id"] == "abc123"

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    def test_credential_expired_propagates(
        self,
        mock_crawler_cls,
        mock_get_conn,
        db,
        tmp_path,
    ):
        """AC-4: CredentialExpiredError is NOT caught -- it propagates."""
        from src.gamechanger.client import CredentialExpiredError

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_crawler = MagicMock()
        mock_crawler.crawl_team.side_effect = CredentialExpiredError("expired")
        mock_crawler_cls.return_value = mock_crawler

        client = MagicMock()

        with pytest.raises(CredentialExpiredError):
            _crawl_and_load_spray(client, "abc123", "2026")

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    def test_other_exceptions_caught_non_fatal(
        self,
        mock_crawler_cls,
        mock_get_conn,
        db,
        tmp_path,
    ):
        """AC-4: Non-credential exceptions are caught; spray failure is non-fatal."""
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_crawler = MagicMock()
        mock_crawler.crawl_team.side_effect = RuntimeError("network error")
        mock_crawler_cls.return_value = mock_crawler

        client = MagicMock()

        # Should NOT raise -- non-fatal
        _crawl_and_load_spray(client, "abc123", "2026")

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    @patch("src.reports.generator.ScoutingSprayChartLoader")
    def test_gc_uuid_passed_through_to_crawler(
        self,
        mock_loader_cls,
        mock_crawler_cls,
        mock_get_conn,
        db,
        tmp_path,
    ):
        """AC-4: gc_uuid parameter is forwarded to crawl_team."""
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_crawler = MagicMock()
        mock_crawler_cls.return_value = mock_crawler
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        client = MagicMock()

        _crawl_and_load_spray(client, "abc123", "2026", gc_uuid="resolved-uuid")

        mock_crawler.crawl_team.assert_called_once_with(
            "abc123", season_id="2026", gc_uuid="resolved-uuid",
            games_data=None,
        )


# ---------------------------------------------------------------------------
# E-236-04: spray-stage honesty -- spray_games_with_data + error-driven status
# ---------------------------------------------------------------------------


def _make_spray_gen():
    """Build a minimal _ReportGeneration carrying only what _spray_stage reads."""
    gen = _gen._ReportGeneration.__new__(_gen._ReportGeneration)
    gen.report_id = 123
    gen.client = object()
    gen.public_id = "abc123"
    gen.season_id = "2026"
    gen.resolved_gc_uuid = None
    gen.team_id = 1

    class _CR:
        games = []

    gen.crawl_result = _CR()
    gen.spray_games = None
    # _spray_stage reads load_result.redirect_map (E-244); load always runs
    # before the spray stage in production, so None mirrors a redirect-free run.
    gen.load_result = None
    return gen


def _run_spray_stage(outcome):
    """Run _spray_stage with _crawl_and_load_spray faked to return ``outcome``.

    Returns the merged dict of fields written to the run record.
    """
    gen = _make_spray_gen()
    captured: dict = {}

    def fake_update(report_id, **fields):
        captured.update(fields)

    with patch.object(_gen, "_update_run_record", fake_update), patch.object(
        _gen, "_crawl_and_load_spray", return_value=outcome
    ):
        gen._spray_stage()
    return captured


class TestSprayStageHonesty:
    """spray_status is ERROR-driven, NOT coverage-driven (AC-2..AC-4)."""

    def test_completed_when_null_charts_zero_errors(self):
        """AC-1/AC-3 (key false-alarm guard): a coverage shortfall
        (spray_games_with_data < spray_games) with ZERO errors -- the modal
        scorekeeper-didn't-chart case -- stays "completed", NOT "partial".
        """
        outcome = _SprayOutcome(
            status="completed", games_crawled=5, errors=0,
            spray_games_with_data=1,
        )
        captured = _run_spray_stage(outcome)
        assert captured["spray_status"] == "completed"
        # AC-1: informational coverage recorded, distinct from spray_games.
        assert captured["spray_games"] == 5
        assert captured["spray_games_with_data"] == 1

    def test_completed_when_zero_coverage_zero_errors(self):
        """AC-3 extreme: NO games charted at all (spray_games_with_data == 0)
        but no error -> still "completed"."""
        outcome = _SprayOutcome(
            status="completed", games_crawled=3, errors=0,
            spray_games_with_data=0,
        )
        captured = _run_spray_stage(outcome)
        assert captured["spray_status"] == "completed"
        assert captured["spray_games_with_data"] == 0

    def test_failed_on_total_crawl_failure(self):
        """AC-4: an existing spray CRAWL failure (status=='failed',
        spray_games==0) maps to "failed" BEFORE the classifier (TN-1
        precedence), so expected==0 -> completed does NOT mask it."""
        outcome = _SprayOutcome(status="failed", games_crawled=0, errors=1)
        captured = _run_spray_stage(outcome)
        assert captured["spray_status"] == "failed"
        assert captured["spray_games"] == 0

    def test_partial_on_load_error_not_coverage(self):
        """AC-2: status flips off "completed" only on a real error signal. A
        crawl with games but a non-zero error count -> "partial" (errors>0),
        proving status is error-driven (coverage alone never does this)."""
        outcome = _SprayOutcome(
            status="completed", games_crawled=4, errors=2,
            spray_games_with_data=4,
        )
        captured = _run_spray_stage(outcome)
        assert captured["spray_status"] == "partial"


class TestSprayInformationalCount:
    """_crawl_and_load_spray computes a perspective-filtered coverage count."""

    @staticmethod
    def _seed_spray_row(db, *, game_id, perspective_team_id, player_id,
                        team_id=None, season_id="2026",
                        chart_type="offensive"):
        # team_id defaults to perspective_team_id (the own-perspective case).
        # season_id + chart_type are now part of the count predicate (Phase 4b
        # MEDIUM: the count must mirror _query_spray_charts), so the seed must
        # set them; callers override to exercise the cross-season / defensive
        # exclusions.
        db.execute(
            "INSERT INTO spray_charts (game_id, player_id, team_id, "
            "perspective_team_id, season_id, chart_type, play_result) "
            "VALUES (?, ?, ?, ?, ?, ?, 'Single')",
            (game_id, player_id,
             team_id if team_id is not None else perspective_team_id,
             perspective_team_id, season_id, chart_type),
        )
        db.commit()

    def _setup_two_perspectives(self, db):
        """Seed spray rows: team 1 has 2 distinct games, team 2 has 1."""
        _seed_team(db, name="Our Team", public_id="abc123")   # id 1
        _seed_team(db, name="Other Team", public_id="xyz789")  # id 2
        _seed_season(db)
        for pid in ("p1", "p2", "p3"):
            _seed_player(db, player_id=pid)
        for gid in ("g1", "g2", "g3"):
            db.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, "
                "away_team_id, game_date) VALUES (?, '2026', 1, 2, "
                "'2026-04-01')",
                (gid,),
            )
        db.commit()
        # Perspective 1: rows for g1 (two rows) and g2 -> 2 distinct games.
        self._seed_spray_row(db, game_id="g1", perspective_team_id=1, player_id="p1")
        self._seed_spray_row(db, game_id="g1", perspective_team_id=1, player_id="p2")
        self._seed_spray_row(db, game_id="g2", perspective_team_id=1, player_id="p1")
        # Perspective 2: rows for g3 -> 1 distinct game (must NOT be counted).
        self._seed_spray_row(db, game_id="g3", perspective_team_id=2, player_id="p3")

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    @patch("src.reports.generator.ScoutingSprayChartLoader")
    def test_count_is_perspective_filtered(
        self, mock_loader_cls, mock_crawler_cls, mock_get_conn, db, tmp_path,
    ):
        """AC-1/AC-6: spray_games_with_data counts distinct games with spray rows
        for THIS team's perspective only -- cross-perspective rows excluded."""
        from src.gamechanger.loaders import LoadResult

        # The ``db`` fixture is already disk-backed at tmp_path/test.db and the
        # seed helpers commit, so the rows are on disk -- point fresh connections
        # at the SAME file. (Do NOT db.backup() onto the same path: that
        # deadlocks SQLite.)
        self._setup_two_perspectives(db)
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        mock_get_conn.side_effect = lambda: _fresh_conn()
        # Crawl "succeeds" (no error, some games) and load reports no errors.
        mock_crawler = MagicMock()
        mock_crawler.crawl_team.return_value = MagicMock(
            errors=0, games_crawled=3, spray_data={},
        )
        mock_crawler_cls.return_value = mock_crawler
        mock_loader = MagicMock()
        mock_loader.load_from_data.return_value = LoadResult(loaded=0, errors=0)
        mock_loader_cls.return_value = mock_loader

        outcome = _crawl_and_load_spray(
            MagicMock(), "abc123", "2026", team_id=1,
        )

        assert outcome.status == "completed"
        assert outcome.errors == 0
        # Only perspective 1's 2 distinct games -- NOT perspective 2's g3.
        assert outcome.spray_games_with_data == 2

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    @patch("src.reports.generator.ScoutingSprayChartLoader")
    def test_count_excludes_cross_season_and_defensive_rows(
        self, mock_loader_cls, mock_crawler_cls, mock_get_conn, db, tmp_path,
    ):
        """Phase 4b MEDIUM: the count predicate must mirror _query_spray_charts
        (team_id + season_id + chart_type='offensive' + perspective). Rows that
        the rendered offensive spray line would NOT show -- a DEFENSIVE chart in
        the report's season, and an OFFENSIVE chart in a DIFFERENT season -- must
        be EXCLUDED from the coverage count. This is the Codex-reproduced bug;
        before the fix the count inflated past the 2 truly-rendered games."""
        from src.gamechanger.loaders import LoadResult

        self._setup_two_perspectives(db)  # team 1 / persp 1: g1, g2 offensive 2026
        db_path = str(tmp_path / "test.db")

        # Extra games for the exclusion rows (game_id FKs to games).
        for gid in ("g4", "g5"):
            db.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, "
                "away_team_id, game_date) VALUES (?, '2026', 1, 2, "
                "'2026-04-02')",
                (gid,),
            )
        db.commit()
        # g4: own team/perspective, current season, but DEFENSIVE chart -> excluded.
        self._seed_spray_row(
            db, game_id="g4", perspective_team_id=1, player_id="p1",
            chart_type="defensive",
        )
        # g5: own team/perspective, OFFENSIVE, but a DIFFERENT season -> excluded.
        self._seed_spray_row(
            db, game_id="g5", perspective_team_id=1, player_id="p1",
            season_id="2025",
        )

        def _fresh_conn():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_crawler = MagicMock()
        mock_crawler.crawl_team.return_value = MagicMock(
            errors=0, games_crawled=4, spray_data={},
        )
        mock_crawler_cls.return_value = mock_crawler
        mock_loader = MagicMock()
        mock_loader.load_from_data.return_value = LoadResult(loaded=0, errors=0)
        mock_loader_cls.return_value = mock_loader

        outcome = _crawl_and_load_spray(
            MagicMock(), "abc123", "2026", team_id=1,
        )

        # Still exactly 2 -- the defensive row (g4) and the cross-season row (g5)
        # are NOT counted, matching what the offensive spray line renders.
        assert outcome.spray_games_with_data == 2

    def test_spray_games_with_data_write_lands(self, tmp_path):
        """CR carry-forward: spray_games_with_data must be in
        _RUN_RECORD_COLUMNS or _update_run_record silently drops it. Round-trip
        through the real schema to prove the write lands."""
        assert "spray_games_with_data" in _gen._RUN_RECORD_COLUMNS

        db_path = str(tmp_path / "rr.db")
        conn = sqlite3.connect(db_path)
        load_real_schema(conn)
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) VALUES (1, 'T', 'tracked')"
        )
        conn.execute(
            "INSERT INTO reports (id, slug, team_id, title, status, "
            "generated_at, expires_at) VALUES "
            "(1, 's', 1, 't', 'generating', "
            "'2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO report_generation_runs (report_id, started_at, "
            "overall_status) VALUES (1, '2026-01-01T00:00:00Z', 'running')"
        )
        conn.commit()
        conn.close()

        def _fresh():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        with patch.object(_gen, "get_connection", side_effect=_fresh):
            _gen._update_run_record(
                1, spray_status="completed", spray_games_with_data=2,
            )

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT spray_status, spray_games_with_data FROM "
            "report_generation_runs WHERE report_id = 1"
        ).fetchone()
        conn.close()
        assert row == ("completed", 2)


# ===========================================================================
# E-186-02: gc_uuid resolution via POST /search
# ===========================================================================


class TestResolveGcUuid:
    """Test _resolve_gc_uuid function."""

    def test_successful_resolution_returns_gc_uuid(self):
        """AC-1: Search returns a hit matching public_id -> returns result.id."""
        client = MagicMock()
        # The MATCHING hit needs the envelope type: the loop checks public_id
        # first and entity class second, so non-matching filler hits never
        # reach the class check and are left as-is.
        client.post_json.return_value = {
            "hits": [
                {
                    "type": "team",
                    "result": {
                        "id": "resolved-gc-uuid-123",
                        "public_id": "my-team-slug",
                        "name": "Test Team",
                    },
                },
                {
                    "result": {
                        "id": "other-uuid",
                        "public_id": "other-team",
                        "name": "Other Team",
                    }
                },
            ]
        }

        result = _resolve_gc_uuid(client, "Test Team", "my-team-slug")

        assert result == "resolved-gc-uuid-123"
        client.post_json.assert_called_once()

    def test_no_match_returns_none(self):
        """AC-2: No hit matches public_id -> returns None."""
        client = MagicMock()
        client.post_json.return_value = {
            "hits": [
                {
                    "result": {
                        "id": "some-uuid",
                        "public_id": "different-team",
                        "name": "Different Team",
                    }
                },
            ]
        }

        result = _resolve_gc_uuid(client, "Test Team", "my-team-slug")

        assert result is None

    def test_empty_hits_returns_none(self):
        """No hits at all -> returns None."""
        client = MagicMock()
        client.post_json.return_value = {"hits": []}

        result = _resolve_gc_uuid(client, "Test Team", "my-team-slug")

        assert result is None

    def test_credential_expired_propagates(self):
        """AC-6: CredentialExpiredError propagates."""
        from src.gamechanger.client import CredentialExpiredError

        client = MagicMock()
        client.post_json.side_effect = CredentialExpiredError("expired")

        with pytest.raises(CredentialExpiredError):
            _resolve_gc_uuid(client, "Test Team", "my-team-slug")

    def test_search_failure_returns_none(self):
        """AC-6: Network/API errors are caught, returns None."""
        client = MagicMock()
        client.post_json.side_effect = RuntimeError("network error")

        result = _resolve_gc_uuid(client, "Test Team", "my-team-slug")

        assert result is None

    def test_unexpected_response_shape_returns_none(self):
        """AC-6: Unexpected response shape (not a dict) returns None."""
        client = MagicMock()
        client.post_json.return_value = "not a dict"

        result = _resolve_gc_uuid(client, "Test Team", "my-team-slug")

        assert result is None

    def test_uses_correct_content_type_and_params(self):
        """Verify the search call uses the correct GC content type."""
        client = MagicMock()
        client.post_json.return_value = {"hits": []}

        _resolve_gc_uuid(client, "Test Team", "my-team-slug")

        client.post_json.assert_called_once_with(
            "/search",
            body={"name": "Test Team"},
            params={"start_at_page": 0, "search_source": "search"},
            content_type="application/vnd.gc.com.post_search+json; version=0.0.0",
        )

    def test_pagination_match_on_page_1(self):
        """AC-1: Match found on page 1 after 25 non-matching hits on page 0."""
        client = MagicMock()
        non_matching_hits = [
            {"result": {"id": f"uuid-{i}", "public_id": f"other-{i}"}}
            for i in range(25)
        ]
        matching_page = {
            "hits": [
                {
                    "type": "team",
                    "result": {"id": "target-uuid", "public_id": "target-slug"},
                }
            ]
        }
        client.post_json.side_effect = [
            {"hits": non_matching_hits},
            matching_page,
        ]

        result = _resolve_gc_uuid(client, "Some Team", "target-slug")

        assert result == "target-uuid"
        assert client.post_json.call_count == 2
        # Verify page numbers
        calls = client.post_json.call_args_list
        assert calls[0][1]["params"]["start_at_page"] == 0
        assert calls[1][1]["params"]["start_at_page"] == 1

    def test_pagination_short_circuit_on_partial_page(self):
        """AC-2: Partial page (< 25 hits) with no match -> return None, no page 1."""
        client = MagicMock()
        client.post_json.return_value = {
            "hits": [
                {"result": {"id": "uuid-1", "public_id": "other-team"}}
            ]
        }

        result = _resolve_gc_uuid(client, "Test Team", "target-slug")

        assert result is None
        client.post_json.assert_called_once()

    def test_pagination_cap_at_max_pages(self):
        """AC-3: 25 non-matching hits on each of 5 pages -> None after 5 requests."""
        client = MagicMock()
        full_page = {
            "hits": [
                {"result": {"id": f"uuid-{i}", "public_id": f"other-{i}"}}
                for i in range(25)
            ]
        }
        client.post_json.return_value = full_page

        result = _resolve_gc_uuid(client, "Test Team", "target-slug")

        assert result is None
        assert client.post_json.call_count == 5
        # Verify pages 0-4 were requested
        for i, call in enumerate(client.post_json.call_args_list):
            assert call[1]["params"]["start_at_page"] == i

    # ---- E-225-02 regression tests ----

    def test_e225_dirty_name_short_circuits_after_page_zero_fallback(self):
        """E-225-02 AC-1a: dirty name + empty page-0 (raw + fallback) -> 2 calls."""
        client = MagicMock()
        client.post_json.return_value = {"hits": []}

        result = _resolve_gc_uuid(
            client,
            "Lincoln Northwest JV/Reserve Falcons",
            "yecaUcoSVpJa",
        )

        assert result is None
        assert client.post_json.call_count == 2
        assert (
            client.post_json.call_args_list[0].kwargs["body"]["name"]
            == "Lincoln Northwest JV/Reserve Falcons"
        )
        assert (
            client.post_json.call_args_list[1].kwargs["body"]["name"]
            == "Lincoln Northwest JV Reserve Falcons"
        )

    def test_e225_slash_name_resolves_via_fallback(self):
        """E-225-02 AC-5: slash-name resolves to gc_uuid via normalized fallback."""
        client = MagicMock()
        canonical_hit = {
            "type": "team",
            "result": {
                "id": "ac053e2c-ee27-4f55-9b16-ed77c1bdfebb",
                "public_id": "yecaUcoSVpJa",
                "name": "Lincoln Northwest JV/Reserve Falcons",
            },
        }
        client.post_json.side_effect = [
            {"hits": []},
            {"hits": [canonical_hit]},
        ]

        result = _resolve_gc_uuid(
            client,
            "Lincoln Northwest JV/Reserve Falcons",
            "yecaUcoSVpJa",
        )

        assert result == "ac053e2c-ee27-4f55-9b16-ed77c1bdfebb"
        assert client.post_json.call_count == 2
        assert (
            client.post_json.call_args_list[0].kwargs["body"]["name"]
            == "Lincoln Northwest JV/Reserve Falcons"
        )
        assert (
            client.post_json.call_args_list[1].kwargs["body"]["name"]
            == "Lincoln Northwest JV Reserve Falcons"
        )

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._resolve_gc_uuid")
    def test_existing_gc_uuid_skips_search(
        self,
        mock_resolve,
        mock_spray,
        mock_get_conn,
        tmp_path,
    ):
        """AC-7(c): Team with non-NULL gc_uuid skips the search call entirely."""
        db_path = str(tmp_path / "test.db")
        conn_template = sqlite3.connect(db_path)
        load_real_schema(conn_template)
        # Seed team WITH gc_uuid already set (member team -- existing gc_uuid used directly)
        conn_template.execute(
            "INSERT INTO teams (name, public_id, gc_uuid, season_year, membership_type) "
            "VALUES ('Test Tigers', 'abc123', 'existing-uuid-999', 2026, 'member')"
        )
        conn_template.execute(
            "INSERT INTO seasons (season_id, name, year) "
            "VALUES ('2026', '2026 Spring HS', 2026)"
        )
        conn_template.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        conn_template.commit()
        _seed_completed_game(conn_template)  # N>0 so the no-games gate does not fire
        conn_template.close()

        def _fresh_conn():
            c = sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        mock_get_conn.side_effect = lambda: _fresh_conn()

        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        mock_client = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.GameChangerClient", return_value=mock_client),
            patch("src.reports.generator.ensure_team_row_with_provenance",
                  return_value=EnsureTeamResult(1, "anchor", False)),
            patch("src.reports.generator.render_report", return_value="<html>test</html>"),
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        assert result.success is True
        # _resolve_gc_uuid should never be called -- existing gc_uuid skips search
        mock_resolve.assert_not_called()
        # Spray pipeline should receive the existing gc_uuid
        mock_spray.assert_called_once()
        _, spray_kwargs = mock_spray.call_args
        assert spray_kwargs.get("gc_uuid") == "existing-uuid-999"


# ===========================================================================
# E-185-01: Sort order, CS column, runs avg, recent form opponent names
# ===========================================================================


class TestBattingSortOrder:
    """AC-9: Batting sorted by PA descending."""

    def test_batting_sorted_by_pa_desc(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        # Player with higher PA should come first
        _seed_player(db, "p1", "High", "PA")
        _seed_player(db, "p2", "Low", "PA")
        # E-259-01: reader SUMs player_game_batting; the PA-proxy ORDER BY is now
        # an expression over the per-game SUM.
        _seed_game(db, team_id, "g1")
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h, bb, hbp, shf) "
            "VALUES ('g1', ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p1", team_id, team_id, 50, 15, 10, 2, 1),  # PA=63
        )
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h, bb, hbp, shf) "
            "VALUES ('g1', ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p2", team_id, team_id, 20, 8, 3, 0, 0),  # PA=23
        )
        db.commit()
        db.row_factory = sqlite3.Row
        batting = _query_batting(db, team_id, "2026")
        assert len(batting) == 2
        assert batting[0]["name"] == "High PA"
        assert batting[1]["name"] == "Low PA"


class TestPitchingSortOrder:
    """AC-9: Pitching sorted by ip_outs DESC."""

    def test_pitching_sorted_by_ip_outs_desc(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p1", "Ace", "Pitcher")
        _seed_player(db, "p2", "Relief", "Pitcher")
        # E-259-01: reader SUMs player_game_pitching; the ip_outs ORDER BY is now
        # an expression over the per-game SUM.
        _seed_game(db, team_id, "g1")
        db.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, appearance_order, ip_outs, er, so, bb, h, pitches, total_strikes) "
            "VALUES ('g1', ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
            ("p1", team_id, team_id, 60, 5, 40, 10, 20, 400, 250),
        )
        db.execute(
            "INSERT INTO player_game_pitching "
            "(game_id, player_id, team_id, perspective_team_id, appearance_order, ip_outs, er, so, bb, h, pitches, total_strikes) "
            "VALUES ('g1', ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
            ("p2", team_id, team_id, 30, 3, 15, 8, 12, 200, 120),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        pitching = _query_pitching(db, team_id, "2026")
        assert len(pitching) == 2
        assert pitching[0]["name"] == "Ace Pitcher"  # 60 outs first
        assert pitching[1]["name"] == "Relief Pitcher"  # 30 outs second


class TestBattingCSColumn:
    """AC-1: Batting query includes CS."""

    def test_batting_includes_cs(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p1", "Jane", "Doe")
        # E-259-01: reader SUMs player_game_batting (cs included in the SUM).
        _seed_game(db, team_id, "g1")
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h, sb, cs) "
            "VALUES ('g1', ?, ?, ?, ?, ?, ?, ?)",
            ("p1", team_id, team_id, 30, 10, 5, 3),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        batting = _query_batting(db, team_id, "2026")
        assert batting[0]["cs"] == 3


class TestRecentFormOpponentNames:
    """AC-6: Recent form includes opponent_name and is_home."""

    def test_opponent_name_resolved(self, db):
        team_id = _seed_team(db, name="Us", public_id="us123")
        opp_id = _seed_team(db, name="Rival Team", public_id="rival456")
        _seed_season(db)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", team_id, opp_id, 7, 3, "2026-03-25"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        games = _query_recent_games(db, team_id, "2026")
        assert len(games) == 1
        assert games[0]["opponent_name"] == "Rival Team"
        assert games[0]["is_home"] is True

    def test_away_game(self, db):
        team_id = _seed_team(db, name="Us", public_id="us123")
        opp_id = _seed_team(db, name="Away Rival", public_id="away789")
        _seed_season(db)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", opp_id, team_id, 3, 7, "2026-03-25"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        games = _query_recent_games(db, team_id, "2026")
        assert games[0]["opponent_name"] == "Away Rival"
        assert games[0]["is_home"] is False

    def test_empty_opponent_name_fallback(self, db):
        """teams.name is NOT NULL under the real schema, but TEXT NOT NULL
        permits empty strings. The `or "Unknown"` fallback at generator.py:308
        treats empty-string names as falsy, so the function should substitute
        "Unknown" in that case (the previous NULL-name test is unreachable
        under FK + NOT NULL, per E-221-02)."""
        team_id = _seed_team(db, name="Us", public_id="us123")
        # Insert opponent with EMPTY name (NOT NULL allows empty string).
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('', 'unk999', 2026, 'tracked')"
        )
        opp_id = cursor.lastrowid
        db.commit()
        _seed_season(db)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", team_id, opp_id, 5, 2, "2026-03-25"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        games = _query_recent_games(db, team_id, "2026")
        assert games[0]["opponent_name"] == "Unknown"


class TestRunsAvg:
    """AC-8: Average runs scored and allowed."""

    def test_runs_avg_basic(self, db):
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        # Game 1: home, scored 7, allowed 3
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", team_id, opp_id, 7, 3, "2026-03-20"),
        )
        # Game 2: away, scored 5, allowed 2
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026", opp_id, team_id, 2, 5, "2026-03-21"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        scored, allowed = _query_runs_avg(db, team_id, "2026")
        assert scored == 6.0   # (7 + 5) / 2
        assert allowed == 2.5  # (3 + 2) / 2

    def test_runs_avg_no_games(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        db.row_factory = sqlite3.Row
        scored, allowed = _query_runs_avg(db, team_id, "2026")
        assert scored is None
        assert allowed is None

    def test_runs_avg_scoped_to_team_and_season(self, db):
        """Verify WHERE filters exclude other teams and seasons."""
        team_id = _seed_team(db, name="Target", public_id="target1")
        other_id = _seed_team(db, name="Other", public_id="other1")
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db, season_id="2026")
        db.execute(
            "INSERT INTO seasons (season_id, name, year) "
            "VALUES ('2025', '2025', 2025)"
        )
        db.commit()
        # Target team, target season: scored 10, allowed 2
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", team_id, opp_id, 10, 2, "2026-03-20"),
        )
        # Other team, same season: scored 20, allowed 0 (should be excluded)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026", other_id, opp_id, 20, 0, "2026-03-20"),
        )
        # Target team, wrong season: scored 30, allowed 1 (should be excluded)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g3", "2025", team_id, opp_id, 30, 1, "2025-03-20"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        scored, allowed = _query_runs_avg(db, team_id, "2026")
        assert scored == 10.0
        assert allowed == 2.0


# ===========================================================================
# E-187-01: gc_uuid resolution wiring integration test
# ===========================================================================


class TestResolveGcUuidIntegration:
    """AC-4: gc_uuid resolution persists to DB and flows to spray crawler."""

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_resolved_gc_uuid_persisted_and_passed_to_spray(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        mock_create_session, db, tmp_path,
    ):
        """Given a team with gc_uuid=NULL, search match persists gc_uuid and
        passes it to _crawl_and_load_spray."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        # Seed team WITHOUT gc_uuid
        db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Test Tigers', 'abc123', 2026, 'tracked')"
        )
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        # Mock client: post_json returns a TEAM search hit matching public_id
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.post_json.return_value = {
            "hits": [
                {
                    "type": "team",
                    "result": {
                        "id": "resolved-uuid-abc",
                        "public_id": "abc123",
                        "name": "Test Tigers",
                    },
                }
            ]
        }

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("abc123")

        assert result.success is True

        # Verify gc_uuid was persisted to the teams table
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT gc_uuid FROM teams WHERE id = 1"
        ).fetchone()
        verify_conn.close()
        assert row[0] == "resolved-uuid-abc"

        # Verify _crawl_and_load_spray received the resolved gc_uuid
        mock_spray.assert_called_once()
        _, spray_kwargs = mock_spray.call_args
        assert spray_kwargs.get("gc_uuid") == "resolved-uuid-abc"


# ===========================================================================
# E-188-01: Post-load orphan cleanup
# ===========================================================================


class TestConcurrentGenerationCreatedSet:
    """E-235-04 / TN-4: orphan cleanup uses a per-run in-memory created-set.

    The old orphan determination snapshotted every team id before the run and
    diffed against a post-run snapshot, so any team another generation created
    in the meantime was wrongly attributed to this run and deleted. The
    created-set records only the teams THIS run INSERTed, threaded through
    ``ScoutingLoader`` -> ``GameLoader`` -> ``ensure_team_row_with_provenance``,
    closing the (cross-process) race.
    """

    def test_concurrent_runs_do_not_delete_each_others_created_teams(self, db):
        """AC-1 (defining outcome): two generations interleaved at the
        orphan-determination boundary must NOT delete each other's
        freshly-created teams.

        Drives the real threading path (``GameLoader._ensure_team_row`` ->
        created-set) for two simultaneous runs, then runs run A's orphan
        cleanup and asserts run B's just-created team survives. Under the old
        global snapshot diff, run A's post-snapshot would have included run B's
        team and deleted it.
        """
        # Each run scouts its own anchor (report) team -- both pre-exist.
        report_a = _seed_team(db, "Report Team A", "rpt-a")
        report_b = _seed_team(db, "Report Team B", "rpt-b")
        db.commit()

        set_a: set[int] = set()
        set_b: set[int] = set()
        loader_a = GameLoader(
            db,
            owned_team_ref=TeamRef(id=report_a, gc_uuid=None, public_id="rpt-a"),
            created_team_ids=set_a,
        )
        loader_b = GameLoader(
            db,
            owned_team_ref=TeamRef(id=report_b, gc_uuid=None, public_id="rpt-b"),
            created_team_ids=set_b,
        )

        # --- Interleave at the orphan-determination window ---
        # Run A's scouting load inserts an opponent stub.
        opp_a = loader_a._ensure_team_row("opp-a-id", opponent_name="Opp A")
        # Run B inserts ITS opponent stub before run A reaches cleanup -- the
        # exact window the old pre/post snapshot diff captured and misattributed.
        opp_b = loader_b._ensure_team_row("opp-b-id", opponent_name="Opp B")
        db.commit()

        # Each run recorded only the team it actually INSERTed.
        assert set_a == {opp_a}
        assert set_b == {opp_b}
        assert opp_a != opp_b

        # Run A determines orphans from its OWN created-set (minus its anchor)
        # and cleans up. Run B's team is not in run A's set.
        orphans_a = set_a - {report_a}
        cleanup_orphan_teams(db, orphans_a)

        remaining = {row[0] for row in db.execute("SELECT id FROM teams")}
        assert opp_a not in remaining          # run A cleans up its own stub
        assert opp_b in remaining              # run B's team SURVIVES (AC-1)
        assert report_a in remaining
        assert report_b in remaining

    def test_created_set_records_inserts_not_matches(self, db):
        """AC-3 / DE-2: the created-set captures INSERTed teams only, never
        MATCHED ones -- so two runs referencing the same pre-existing opponent
        do not both claim (and risk deleting) it.
        """
        report = _seed_team(db, "Report Team", "rpt")
        # A pre-existing tracked opponent (season_year 2026, matching the seed
        # default) that the scouting load will reference, not create.
        shared_opp = _seed_team(db, "Shared Opp", "shared-opp")
        db.commit()

        created: set[int] = set()
        loader = GameLoader(
            db,
            owned_team_ref=TeamRef(id=report, gc_uuid=None, public_id="rpt"),
            created_team_ids=created,
        )

        # name+season_year+tracked match -> existing id returned, NOT inserted.
        matched = loader._ensure_team_row("shared-opp", opponent_name="Shared Opp")
        assert matched == shared_opp
        assert created == set()

        # A genuinely new opponent IS recorded.
        new_opp = loader._ensure_team_row("new-opp-id", opponent_name="Brand New Opp")
        assert created == {new_opp}

    def test_created_set_none_disables_recording(self, db):
        """A GameLoader built without a created-set (the default for all
        non-report callers) inserts teams normally and records nothing.
        """
        report = _seed_team(db, "Report Team", "rpt")
        db.commit()

        loader = GameLoader(
            db, owned_team_ref=TeamRef(id=report, gc_uuid=None, public_id="rpt"),
        )
        assert loader._created_team_ids is None
        # Insert still works (return is a valid team id) -- no crash.
        opp = loader._ensure_team_row("opp-id", opponent_name="Some Opp")
        assert isinstance(opp, int)


class TestScoutingLoaderCreatedSetThreading:
    """E-235-04 / TN-4 (SE-F5): the created-set threads ScoutingLoader ->
    GameLoader so opponent stubs created during the in-memory scouting load are
    recorded for run-scoped orphan cleanup."""

    def test_scouting_loader_threads_created_set_to_game_loader(self, db):
        """The set passed to ``ScoutingLoader`` is handed to the ``GameLoader``
        it builds, so stub inserts during boxscore loading are recorded."""
        from src.gamechanger.loaders.scouting_loader import ScoutingLoader

        report = _seed_team(db, "Report Team", "rpt")
        db.commit()

        created: set[int] = set()
        loader = ScoutingLoader(db, created_team_ids=created)
        # The loader stores the set and (when it builds a GameLoader) passes it
        # through. Verify the wiring: a GameLoader built with this set records
        # an insert into the SAME set object the ScoutingLoader holds.
        assert loader._created_team_ids is created
        game_loader = GameLoader(
            db,
            owned_team_ref=TeamRef(id=report, gc_uuid=None, public_id="rpt"),
            created_team_ids=loader._created_team_ids,
        )
        opp = game_loader._ensure_team_row("opp-id", opponent_name="Threaded Opp")
        assert created == {opp}

    def test_compute_orphans_uses_created_set_excluding_report_team(self):
        """``_ReportGeneration._compute_orphans`` derives orphans from the
        per-run created-set (minus the report team) -- no global snapshot."""
        from src.reports.generator import _ReportGeneration

        gen = _ReportGeneration("some-public-id")
        gen.team_id = 5
        gen.created_team_ids = {5, 10, 11}  # 5 == report team
        gen._compute_orphans()
        assert gen.orphan_ids == {10, 11}


class TestRestDayReferenceDateIsVenueLocal:
    """E-256-05: the rest-day / workload reference date is venue-local, not UTC.

    `generated_at` is a UTC instant. Slicing its first ten characters yields the
    UTC calendar date, which after ~19:00 America/Chicago has already rolled to
    tomorrow. An evening generation therefore computed pitcher rest days and the
    7-day `pitches_7d` window against a date the coach has not reached yet.

    The falsifying input is a late-UTC `generated_at`: 2026-07-10T02:30:00Z is
    2026-07-09 at 21:30 in the operating timezone. Every consumer must see
    2026-07-09. Restore any `generated_at[:10]` at any consumer and that consumer
    sees 2026-07-10 instead -- which is exactly the partial-fix failure this
    story's caller-audit exists to catch.
    """

    _LATE_UTC = "2026-07-10T02:30:00Z"   # 21:30 on 07-09 in America/Chicago
    _LOCAL = "2026-07-09"
    _UTC_SLICE = "2026-07-10"            # what the bug produced

    def _run_stage(self, db, tmp_path, monkeypatch):
        """Drive the real `_query_render_save` and capture what each consumer got."""
        from datetime import date as _date

        from src.reports.generator import _ReportGeneration

        monkeypatch.setenv("OPERATING_TIMEZONE", "America/Chicago")
        monkeypatch.setenv("FEATURE_PREDICTED_STARTER", "1")

        team_id = _seed_team(db)
        _seed_season(db)
        db.commit()

        # The stage opens (and `closing()`s) several connections; hand it a fresh
        # one each time so it never closes the fixture's.
        def _fresh_conn():
            conn = sqlite3.connect(str(tmp_path / "test.db"))
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        self._date = _date

        captured: dict[str, object] = {}

        def _fake_workload(t, s, ref, *, db=None):
            captured["workload_ref"] = ref
            return {}

        def _fake_history(t, s, *, db=None):
            return [{"player_id": "p1", "game_date": "2026-07-01"}]

        def _fake_profiles(rows):
            return {"p1": {}}

        def _fake_prediction(profiles, history, *, reference_date, workload, league):
            captured["prediction_ref"] = reference_date
            return None

        def _fake_tier2(pred, rows, *, team_name, team_record, reference_date, public_id):
            captured["tier2_ref"] = reference_date
            return None, None

        def _capture_render(data):
            captured["render_generation_date"] = data["generation_date"]
            return "<html></html>"

        gen = _ReportGeneration("https://web.gc.com/teams/abc")
        gen.team_id = team_id
        gen.season_id = "2026"
        gen.report_id = 1
        gen.slug = "ref-date"
        gen.generated_at = self._LATE_UTC
        gen.expires_at = "2026-07-24T02:30:00Z"
        gen.team_info = {"name": "Test Tigers"}
        gen.title = "Test Tigers"
        gen.public_id = "abc123"

        with (
            patch("src.reports.generator.get_connection", side_effect=_fresh_conn),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator.get_pitching_workload", _fake_workload),
            patch("src.reports.generator.get_pitching_history", _fake_history),
            patch("src.reports.generator.build_pitcher_profiles", _fake_profiles),
            patch("src.reports.starter_prediction.compute_starter_prediction", _fake_prediction),
            patch("src.reports.generator._run_tier2_enrichment", _fake_tier2),
            patch("src.reports.generator.render_report", _capture_render),
            patch("src.reports.generator._update_report_ready"),
            patch("src.reports.generator._update_run_record"),
            patch("src.reports.generator._finalize_run_record"),
        ):
            result = gen._query_render_save()

        return result, captured

    def test_all_consumers_receive_the_venue_local_date(self, db, tmp_path, monkeypatch):
        """AC-1/AC-3: every consumer of the reference date sees the LOCAL date."""
        result, captured = self._run_stage(db, tmp_path, monkeypatch)
        assert result.outcome == "ready", result.error_message
        local = self._date.fromisoformat(self._LOCAL)

        # 1. the 7-day pitches_7d window (a string; SQL date(ref, '-6 days'))
        assert captured["workload_ref"] == self._LOCAL
        # 2. rest-day math in the starter prediction (a date)
        assert captured["prediction_ref"] == local
        # 3. rest-day math in the Tier-2 enrichment (a date)
        assert captured["tier2_ref"] == local
        # 4. the coach-facing "Generated <date>" footer
        assert captured["render_generation_date"] == self._LOCAL

        # None of them saw the UTC slice.
        assert self._UTC_SLICE not in {
            captured["workload_ref"],
            str(captured["prediction_ref"]),
            str(captured["tier2_ref"]),
            captured["render_generation_date"],
        }

    def test_result_carries_the_reference_date(self, db, tmp_path, monkeypatch):
        """AC-4: the ready result surfaces the date `bb report generate` prints."""
        result, _ = self._run_stage(db, tmp_path, monkeypatch)
        assert result.reference_date == self._LOCAL


class TestPublicSeasonCapture:
    """E-272-02 AC-6: `team_season.season` is captured off the public-API
    payload alongside the year, with no schema change and no extra request."""

    def _fetch(self, payload):
        gen = _ReportGeneration("https://web.gc.com/teams/abc")
        gen.public_id = "abc"
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        session = MagicMock()
        session.get.return_value = resp
        with patch("src.http.session.create_session", return_value=session):
            gen._fetch_public_team_info()
        # Still exactly one public-API call -- no new crawling (AC-6).
        assert session.get.call_count == 1
        return gen

    def test_init_defaults_season_to_none(self):
        assert _ReportGeneration("https://web.gc.com/teams/abc").season_from_api is None

    def test_season_captured_alongside_year(self):
        gen = self._fetch({
            "name": "Norfolk Motor Company Seniors 18U",
            "team_season": {"year": 2026, "season": "summer"},
            "ngb": "[]",
            "age_group": "18U",
        })
        assert gen.season_from_api == "summer"
        assert gen.season_year_from_api == 2026

    def test_season_absent_from_team_season_is_none(self):
        gen = self._fetch({"name": "Lincoln Reserve", "team_season": {"year": 2026}})
        assert gen.season_from_api is None
        assert gen.season_year_from_api == 2026

    def test_no_team_season_object_is_none(self):
        gen = self._fetch({"name": "Lincoln Reserve"})
        assert gen.season_from_api is None


class TestSeasonThreadedIntoLeagueDetection:
    """E-272-02 AC-6: the captured season reaches `detect_league_level`, so the
    SAME opponent name resolves to a different league by season.

    Drives the real `_query_render_save` and captures the `league` handed to
    `compute_starter_prediction` -- dropping the `season=` kwarg at the call
    site makes the summer case fall back to `nsaa_subvarsity` and fails here.
    """

    def _resolved_league(self, db, tmp_path, monkeypatch, *, team_name, season):
        monkeypatch.setenv("OPERATING_TIMEZONE", "America/Chicago")
        monkeypatch.setenv("FEATURE_PREDICTED_STARTER", "1")

        team_id = _seed_team(db)
        _seed_season(db)
        db.commit()

        def _fresh_conn():
            conn = sqlite3.connect(str(tmp_path / "test.db"))
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        captured: dict[str, object] = {}

        def _fake_history(t, s, *, db=None):
            return [{"player_id": "p1", "game_date": "2026-07-01"}]

        def _fake_prediction(profiles, history, *, reference_date, workload, league):
            captured["league"] = league
            return None

        def _fake_tier2(pred, rows, *, team_name, team_record, reference_date,
                        public_id):
            return None, None

        gen = _ReportGeneration("https://web.gc.com/teams/abc")
        gen.team_id = team_id
        gen.season_id = "2026"
        gen.report_id = 1
        gen.slug = "season-thread"
        gen.generated_at = "2026-07-10T02:30:00Z"
        gen.expires_at = "2026-07-24T02:30:00Z"
        gen.team_info = {"name": team_name}
        gen.title = team_name
        gen.public_id = "abc123"
        # What _fetch_public_team_info would have captured.
        gen.team_name_from_api = team_name
        gen.ngb_from_api = "[]"
        gen.age_group_from_api = None
        gen.season_from_api = season

        with (
            patch("src.reports.generator.get_connection", side_effect=_fresh_conn),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator.get_pitching_workload",
                  lambda t, s, ref, *, db=None: {}),
            patch("src.reports.generator.get_pitching_history", _fake_history),
            patch("src.reports.generator.build_pitcher_profiles",
                  lambda rows: {"p1": {}}),
            patch("src.reports.starter_prediction.compute_starter_prediction",
                  _fake_prediction),
            patch("src.reports.generator._run_tier2_enrichment", _fake_tier2),
            patch("src.reports.generator.render_report", lambda data: "<html></html>"),
            patch("src.reports.generator._update_report_ready"),
            patch("src.reports.generator._update_run_record"),
            patch("src.reports.generator._finalize_run_record"),
        ):
            result = gen._query_render_save()

        assert result.outcome == "ready", result.error_message
        return captured["league"]

    def test_summer_reserve_resolves_nrbl(self, db, tmp_path, monkeypatch):
        assert self._resolved_league(
            db, tmp_path, monkeypatch,
            team_name="Anytown Reserve", season="summer",
        ) == "nrbl"

    def test_absent_season_reserve_resolves_nsaa_subvarsity(
        self, db, tmp_path, monkeypatch,
    ):
        """AC-6: the report still generates with no season present."""
        assert self._resolved_league(
            db, tmp_path, monkeypatch,
            team_name="Anytown Reserve", season=None,
        ) == "nsaa_subvarsity"

    def test_summer_varsity_resolves_legion(self, db, tmp_path, monkeypatch):
        assert self._resolved_league(
            db, tmp_path, monkeypatch,
            team_name="Anytown Varsity", season="summer",
        ) == "legion"


class TestCleanupOrphanTeams:
    """AC-1, AC-2, AC-4: FK-safe orphan deletion."""

    def test_deletes_orphan_teams_and_dependent_rows(self, db):
        """AC-1: Orphan teams and all dependent data are deleted."""
        # Subject team (should survive)
        subject_id = _seed_team(db, "Subject Team", "subject1")
        _seed_season(db)
        _seed_player(db, "p1", "Subject", "Player")

        # Orphan team
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan Team', 'orphan1', 2026, 'tracked')"
        )
        orphan_id = cursor.lastrowid
        db.commit()

        _seed_player(db, "p2", "Orphan", "Player")

        # Game between subject and orphan
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", subject_id, orphan_id, 5, 3, "2026-03-20"),
        )
        db.commit()

        # Per-game batting for both teams (both reference game g1)
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES ('g1', 'p1', ?, ?, 4, 2)",
            (subject_id, subject_id),
        )
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES ('g1', 'p2', ?, ?, 3, 1)",
            (orphan_id, subject_id),
        )
        # Spray chart for the game
        db.execute(
            "INSERT INTO spray_charts (game_id, team_id, player_id, season_id, perspective_team_id, "
            "chart_type, x, y) VALUES ('g1', ?, 'p2', '2026', ?, 'offensive', 0.5, 0.5)",
            (orphan_id, subject_id),
        )
        # Roster and season stats for orphan
        db.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) "
            "VALUES (?, 'p2', '2026', '99')",
            (orphan_id,),
        )
        # player_season_* dropped in E-259-03 -- no stored season rows to seed.
        # E-220 remediation: seed a game_perspectives row for the shared game.
        # When cleanup processes game-scoped data, game_perspectives must be
        # deleted before games, otherwise FK check on games deletion fails.
        # (This row persists since the shared game is retained, but if cleanup
        # ever DOES delete the game the helper must handle it.)
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES ('g1', ?)",
            (subject_id,),
        )
        db.commit()

        count = cleanup_orphan_teams(db, {orphan_id})

        # Orphan team retained -- it still has a game FK reference (shared game)
        assert count == 0
        assert db.execute("SELECT id FROM teams WHERE id = ?", (orphan_id,)).fetchone() is not None
        # Subject team still exists
        assert db.execute("SELECT id FROM teams WHERE id = ?", (subject_id,)).fetchone() is not None
        # Shared game preserved (subject team is a participant)
        assert db.execute("SELECT game_id FROM games WHERE game_id = 'g1'").fetchone() is not None
        # Per-game batting preserved (game still exists)
        assert db.execute("SELECT id FROM player_game_batting WHERE game_id = 'g1'").fetchone() is not None
        # Spray chart preserved (game still exists)
        assert db.execute("SELECT id FROM spray_charts WHERE game_id = 'g1'").fetchone() is not None
        # Orphan roster deleted (team-scoped data always cleaned)
        assert db.execute(
            "SELECT team_id FROM team_rosters WHERE team_id = ?", (orphan_id,)
        ).fetchone() is None
        # Players NOT deleted (shared across teams)
        assert db.execute("SELECT player_id FROM players WHERE player_id = 'p2'").fetchone() is not None

    def test_pre_existing_teams_preserved(self, db):
        """AC-2: Only teams in orphan_ids are deleted; pre-existing teams untouched."""
        pre_existing_id = _seed_team(db, "Pre-existing", "pre1")
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan', 'orphan2', 2026, 'tracked')"
        )
        orphan_id = cursor.lastrowid
        db.commit()

        cleanup_orphan_teams(db, {orphan_id})

        # Pre-existing team still there
        assert db.execute(
            "SELECT id FROM teams WHERE id = ?", (pre_existing_id,)
        ).fetchone() is not None
        # Orphan gone
        assert db.execute(
            "SELECT id FROM teams WHERE id = ?", (orphan_id,)
        ).fetchone() is None

    def test_empty_orphan_set_is_noop(self, db):
        """No orphans means no deletions."""
        team_id = _seed_team(db)
        count = cleanup_orphan_teams(db, set())
        assert count == 0
        assert db.execute("SELECT id FROM teams WHERE id = ?", (team_id,)).fetchone() is not None

    def test_fk_safe_deletion_order(self, db):
        """AC-4: Deletes respect FK constraints with PRAGMA foreign_keys=ON."""
        # This test verifies that the deletion order doesn't violate FK constraints.
        # The db fixture already has PRAGMA foreign_keys=ON.
        subject_id = _seed_team(db, "Subject", "subj1")
        _seed_season(db)
        _seed_player(db, "p1", "A", "Player")
        _seed_player(db, "p2", "B", "Player")

        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan', 'orp1', 2026, 'tracked')"
        )
        orphan_id = cursor.lastrowid
        db.commit()

        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026", subject_id, orphan_id, 5, 3, "2026-03-20"),
        )
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES ('g1', 'p1', ?, ?, 4, 2)",
            (subject_id, subject_id),
        )
        db.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, er) "
            "VALUES ('g1', 'p2', ?, ?, 9, 2)",
            (orphan_id, subject_id),
        )
        # E-220 remediation: add a SECOND orphan team so we can create a
        # second game between two orphans -- that game WILL be deleted in
        # Phase 1, exercising the game_perspectives FK check.
        cursor2 = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan2', 'orp2', 2026, 'tracked')"
        )
        orphan2_id = cursor2.lastrowid
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g-orphan-only", "2026", orphan_id, orphan2_id, 1, 2, "2026-03-21"),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-orphan-only", orphan_id),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-orphan-only", orphan2_id),
        )
        db.commit()

        # Should not raise FK constraint error -- orphan-vs-orphan game deleted,
        # its game_perspectives rows must be deleted first.
        count = cleanup_orphan_teams(db, {orphan_id, orphan2_id})
        # The orphan-vs-orphan game should be gone (and its game_perspectives rows).
        assert db.execute(
            "SELECT 1 FROM games WHERE game_id = 'g-orphan-only'"
        ).fetchone() is None, "orphan-vs-orphan game should have been deleted"
        assert db.execute(
            "SELECT 1 FROM game_perspectives WHERE game_id = 'g-orphan-only'"
        ).fetchone() is None, "game_perspectives for deleted game should be gone"
        # orphan_id still retained due to shared game g1 (subject team participates)
        assert db.execute("SELECT 1 FROM teams WHERE id = ?", (orphan_id,)).fetchone() is not None

    def test_preserves_shared_game_with_non_orphan(self, db):
        """Orphan cleanup preserves games where a non-orphan team participates."""
        _seed_team(db)  # team_id=1 (non-orphan / report team)
        _seed_season(db)

        # Create orphan team
        db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Orphan Opp', 'tracked', 0)"
        )
        orphan_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Player for game data
        db.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES ('p-shared', 'Shared', 'Player')"
        )

        # Game between report team (1) and orphan -- shared game
        db.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
            "away_team_id, status) VALUES ('g-shared', '2026', "
            "'2026-03-15', 1, ?, 'completed')",
            (orphan_id,),
        )
        # Plays for the shared game
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id) VALUES ('g-shared', 1, 1, "
            "'top', '2026', 1, 1, 'p-shared', 'p-shared')"
        )
        db.commit()

        # Cleanup orphan -- should NOT delete the shared game or its plays
        count = cleanup_orphan_teams(db, {orphan_id})

        # Orphan team row retained (still referenced by shared game FK)
        assert db.execute(
            "SELECT 1 FROM teams WHERE id = ?", (orphan_id,)
        ).fetchone() is not None
        assert count == 0  # no teams actually deleted

        # Shared game and plays preserved (report team is still a participant)
        assert db.execute(
            "SELECT 1 FROM games WHERE game_id = 'g-shared'"
        ).fetchone() is not None
        assert db.execute(
            "SELECT 1 FROM plays WHERE game_id = 'g-shared'"
        ).fetchone() is not None




class TestCrossPerspectiveScopedDelete:
    """Round 6 Cluster 2: scoped game-scoped delete helper.

    DE's reframing: _delete_game_scoped_data_for_perspectives must only
    delete rows owned by the given perspectives, preserving other
    perspectives' rows and the games row itself when those other
    perspectives still exist.
    """

    def test_cleanup_orphan_teams_preserves_other_perspective_rows(self, db):
        """Two teams share a game in different perspectives; cleanup one
        must NOT delete the other's rows.
        """
        _seed_season(db)
        _seed_player(db, "p-orphan", "Orphan", "Batter")
        _seed_player(db, "p-other", "Other", "Batter")
        _seed_team(db, "Report Team", "rpt")  # id=1 (non-orphan)

        # Create an orphan team
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan', 'orph-x', 2026, 'tracked')"
        )
        orphan_id = cursor.lastrowid

        # Game between orphan and a THIRD team (so it's orphan-vs-other, not shared
        # with the report team).  Note: the cleanup only processes orphan-vs-orphan
        # games; games where orphan vs non-orphan are preserved entirely.
        # Use a scenario where BOTH participants are orphans so cleanup processes
        # the game, but seed rows from a non-orphan perspective that must survive.
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan2', 'orph-y', 2026, 'tracked')"
        )
        orphan2_id = cursor.lastrowid
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g-cross", "2026", orphan_id, orphan2_id, 5, 3, "2026-04-01"),
        )

        # Orphan perspective rows (will be deleted)
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES (?, ?, ?, ?, 4, 2)",
            ("g-cross", "p-orphan", orphan_id, orphan_id),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-cross", orphan_id),
        )
        # Report team (non-orphan) loaded the same game from ITS perspective.
        # These rows must survive -- they are NOT in the orphan set.
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES (?, ?, ?, ?, 3, 1)",
            ("g-cross", "p-other", orphan_id, 1),  # report-team perspective
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-cross", 1),
        )
        db.commit()

        # Cleanup only the orphans
        cleanup_orphan_teams(db, {orphan_id, orphan2_id})

        # Orphan-perspective rows deleted
        orphan_rows = db.execute(
            "SELECT COUNT(*) FROM player_game_batting "
            "WHERE game_id = 'g-cross' AND perspective_team_id = ?",
            (orphan_id,),
        ).fetchone()[0]
        assert orphan_rows == 0, (
            "orphan-perspective rows should be deleted"
        )
        # Report-team-perspective rows preserved
        other_rows = db.execute(
            "SELECT COUNT(*) FROM player_game_batting "
            "WHERE game_id = 'g-cross' AND perspective_team_id = 1"
        ).fetchone()[0]
        assert other_rows == 1, (
            "non-orphan perspective rows must be preserved"
        )
        # game_perspectives: orphan row gone, report team row preserved
        gp_orphan = db.execute(
            "SELECT COUNT(*) FROM game_perspectives "
            "WHERE game_id = 'g-cross' AND perspective_team_id = ?",
            (orphan_id,),
        ).fetchone()[0]
        gp_other = db.execute(
            "SELECT COUNT(*) FROM game_perspectives "
            "WHERE game_id = 'g-cross' AND perspective_team_id = 1"
        ).fetchone()[0]
        assert gp_orphan == 0
        assert gp_other == 1

    def test_cascade_delete_team_preserves_other_perspective_rows(self, db):
        """Stub team + tracked team share a game.  Cascade-delete stub;
        tracked team's perspective rows for the shared game survive.
        """
        _seed_season(db)
        _seed_player(db, "p-stub", "Stub", "Player")
        _seed_player(db, "p-other", "Other", "Player")

        # Stub team -- eligible for cleanup (no public_id, no gc_uuid, inactive)
        cursor = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Stub', 'tracked', 0)"
        )
        stub_id = cursor.lastrowid
        # Tracked opponent (separate, different perspective)
        cursor = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Tracked', 'tracked', 1)"
        )
        tracked_id = cursor.lastrowid

        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g-shared", "2026", stub_id, tracked_id, 5, 3, "2026-04-01"),
        )

        # Stub perspective rows
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES (?, ?, ?, ?, 4, 2)",
            ("g-shared", "p-stub", stub_id, stub_id),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-shared", stub_id),
        )
        # Tracked team perspective rows (must survive)
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES (?, ?, ?, ?, 3, 1)",
            ("g-shared", "p-other", tracked_id, tracked_id),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-shared", tracked_id),
        )
        db.commit()

        cascade_delete_team(db, stub_id)

        # Stub's rows are gone
        assert db.execute(
            "SELECT COUNT(*) FROM player_game_batting "
            "WHERE perspective_team_id = ?", (stub_id,)
        ).fetchone()[0] == 0
        # Tracked team's rows survive
        assert db.execute(
            "SELECT COUNT(*) FROM player_game_batting "
            "WHERE perspective_team_id = ?", (tracked_id,)
        ).fetchone()[0] == 1, (
            "tracked team's perspective rows must survive stub cascade delete"
        )

    def test_cascade_delete_team_preserves_games_row_when_other_perspective_remains(self, db):
        """After stub cascade delete, the games row survives because tracked
        team still has a perspective row in game_perspectives.
        """
        _seed_season(db)
        cursor = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Stub', 'tracked', 0)"
        )
        stub_id = cursor.lastrowid
        cursor = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Tracked', 'tracked', 1)"
        )
        tracked_id = cursor.lastrowid

        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "game_date) VALUES (?, ?, ?, ?, ?)",
            ("g-survive", "2026", stub_id, tracked_id, "2026-04-01"),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-survive", stub_id),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-survive", tracked_id),
        )
        db.commit()

        cascade_delete_team(db, stub_id)

        # games row survives because tracked team still has a perspective row
        assert db.execute(
            "SELECT COUNT(*) FROM games WHERE game_id = 'g-survive'"
        ).fetchone()[0] == 1, (
            "games row must survive when another perspective remains"
        )
        # tracked team's game_perspectives row survives
        assert db.execute(
            "SELECT COUNT(*) FROM game_perspectives "
            "WHERE game_id = 'g-survive' AND perspective_team_id = ?",
            (tracked_id,),
        ).fetchone()[0] == 1

    def test_cascade_delete_team_drops_games_row_when_last_perspective(self, db):
        """When stub is the SOLE perspective for a game, deleting the stub
        removes the games row.
        """
        _seed_season(db)
        cursor = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Stub', 'tracked', 0)"
        )
        stub_id = cursor.lastrowid

        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "game_date) VALUES (?, ?, ?, ?, ?)",
            ("g-solo", "2026", stub_id, stub_id, "2026-04-01"),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-solo", stub_id),
        )
        db.commit()

        cascade_delete_team(db, stub_id)

        # games row gone -- no other perspective remained
        assert db.execute(
            "SELECT COUNT(*) FROM games WHERE game_id = 'g-solo'"
        ).fetchone()[0] == 0, (
            "games row should be deleted when last perspective is removed"
        )

    def test_cleanup_orphan_teams_handles_multi_orphan_perspective_list(self, db):
        """Two orphans with rows from both perspectives.  Cleanup must
        delete all orphan-perspective rows across both.
        """
        _seed_season(db)
        _seed_player(db, "p-a", "A", "Player")
        _seed_player(db, "p-b", "B", "Player")
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan A', 'oa', 2026, 'tracked')"
        )
        oa = cursor.lastrowid
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Orphan B', 'ob', 2026, 'tracked')"
        )
        ob = cursor.lastrowid

        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "game_date) VALUES (?, ?, ?, ?, ?)",
            ("g-multi", "2026", oa, ob, "2026-04-01"),
        )
        # Rows from both orphan perspectives
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab) "
            "VALUES (?, ?, ?, ?, ?)",
            ("g-multi", "p-a", oa, oa, 4),
        )
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab) "
            "VALUES (?, ?, ?, ?, ?)",
            ("g-multi", "p-b", ob, ob, 3),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-multi", oa),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
            ("g-multi", ob),
        )
        db.commit()

        cleanup_orphan_teams(db, {oa, ob})

        # All orphan-perspective rows gone
        total = db.execute(
            "SELECT COUNT(*) FROM player_game_batting WHERE game_id = 'g-multi'"
        ).fetchone()[0]
        assert total == 0, f"expected 0 rows across both orphan perspectives, got {total}"
        # game_perspectives cleared
        gp_total = db.execute(
            "SELECT COUNT(*) FROM game_perspectives WHERE game_id = 'g-multi'"
        ).fetchone()[0]
        assert gp_total == 0
        # games row deleted (no remaining perspective)
        games_total = db.execute(
            "SELECT COUNT(*) FROM games WHERE game_id = 'g-multi'"
        ).fetchone()[0]
        assert games_total == 0


class TestFH1SharedGameDeletionGuard:
    """E-253-01 F-H1: deleting X must not destroy a live-report team's shared-game data.

    Setup shared by the tests: teams X (deletion target, its report already
    removed by the caller) and Y (holds a live ``reports`` row) played a shared
    game G (home=X, away=Y). Under Y's perspective the game's ``plays`` include
    X's at-bats (``batting_team_id = X``) -- those pitches feed Y's pitcher
    FPS%/P-BF. The unbounded anchor pass in ``_delete_team_anchor_and_orphan_data``
    deletes ``plays`` by ``batting_team_id = X`` across ALL perspectives, so
    without the guard Y's rows are collateral damage; whole-game plays
    idempotency then never re-fetches them (permanent silent hole).
    """

    @staticmethod
    def _seed_shared_game(db, *, y_has_report: bool):
        """Seed X, Y, shared game G, and Y-perspective + X-perspective plays.

        Returns ``(x_id, y_id)``. When ``y_has_report`` is True a ``reports``
        row is inserted for Y (the F-H1 guard's trigger).
        """
        _seed_season(db)
        _seed_player(db, "x-bat", "Xavier", "Batter")   # bats for X
        _seed_player(db, "y-pit", "Yuri", "Pitcher")     # pitches for Y
        _seed_player(db, "y-bat", "Yves", "Batter")      # bats for Y

        # X: deletion target -- inactive stub, its own report already deleted.
        x_id = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('X Stub', 'tracked', 0)"
        ).lastrowid
        # Y: still holds a live report.
        y_id = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Y Report Team', 'tracked', 1)"
        ).lastrowid

        if y_has_report:
            db.execute(
                "INSERT INTO reports (slug, team_id, title, expires_at) "
                "VALUES ('y-live', ?, 'Y Report', '2099-01-01T00:00:00Z')",
                (y_id,),
            )

        # Shared game G: X home, Y away.
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES ('G', '2026', ?, ?, 4, 6, "
            "'2026-04-01')",
            (x_id, y_id),
        )
        for pid in (x_id, y_id):
            db.execute(
                "INSERT INTO game_perspectives (game_id, perspective_team_id) "
                "VALUES ('G', ?)",
                (pid,),
            )

        # --- Y's perspective (must survive X's deletion) --------------------
        # X batting under Y's perspective: the FPS%/P-BF-bearing rows.
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id, "
            "pitch_count, is_first_pitch_strike) "
            "VALUES ('G', 1, 1, 'top', '2026', ?, ?, 'x-bat', 'y-pit', 5, 1)",
            (x_id, y_id),
        )
        y_persp_x_bat_play = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO play_events (play_id, event_order, event_type, "
            "pitch_result, is_first_pitch) VALUES (?, 1, 'pitch', 'strike_looking', 1)",
            (y_persp_x_bat_play,),
        )
        # Y batting under Y's perspective (also must survive; untouched anchor).
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id, "
            "pitch_count, is_first_pitch_strike) "
            "VALUES ('G', 2, 1, 'bottom', '2026', ?, ?, 'y-bat', 'x-bat', 3, 0)",
            (y_id, y_id),
        )
        # X's batting line as recorded under Y's perspective.
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES ('G', 'x-bat', ?, ?, 4, 2)",
            (x_id, y_id),
        )

        # --- X's own perspective (correctly deleted with X) -----------------
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id, "
            "pitch_count, is_first_pitch_strike) "
            "VALUES ('G', 1, 1, 'top', '2026', ?, ?, 'x-bat', 'y-pit', 5, 1)",
            (x_id, x_id),
        )
        db.commit()
        return x_id, y_id

    def test_anchor_pass_destroys_shared_game_plays_without_guard(self, db):
        """The hole: with NO live report protecting Y, the anchor pass wipes Y's
        X-batting plays (the pre-guard F-H1 destruction this story prevents).
        """
        x_id, y_id = self._seed_shared_game(db, y_has_report=False)

        # Baseline: Y's perspective has the X-batting FPS-bearing row.
        before = db.execute(
            "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ? "
            "AND batting_team_id = ?",
            (y_id, x_id),
        ).fetchone()[0]
        assert before == 1

        cascade_delete_team(db, x_id)

        # Unprotected: Y's X-batting rows are gone -- demonstrates the hole the
        # guard closes (this is the destruction, reproduced).
        after = db.execute(
            "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ? "
            "AND batting_team_id = ?",
            (y_id, x_id),
        ).fetchone()[0]
        assert after == 0, (
            "sanity: without a live report the anchor pass destroys the "
            "X-batting rows -- confirms the guard, not luck, is what saves them"
        )

    def test_guard_preserves_shared_game_plays_under_live_report(self, db):
        """AC-1: Y holds a live report -> Y's X-batting plays (and their
        play_events) survive X's deletion; Y's FPS%/P-BF query is unchanged.
        """
        x_id, y_id = self._seed_shared_game(db, y_has_report=True)

        def fps_query():
            # FPS% / P-BF surrogate: over Y's pitcher, sum first-pitch strikes
            # and count batters faced, from Y-perspective plays.
            row = db.execute(
                "SELECT COALESCE(SUM(is_first_pitch_strike), 0), COUNT(*) "
                "FROM plays WHERE perspective_team_id = ? AND pitcher_id = 'y-pit'",
                (y_id,),
            ).fetchone()
            return (row[0], row[1])

        before = fps_query()
        y_persp_play_ids_before = {
            r[0] for r in db.execute(
                "SELECT id FROM plays WHERE perspective_team_id = ?", (y_id,)
            ).fetchall()
        }

        cascade_delete_team(db, x_id)

        # AC-1: Y's X-batting rows survive, identical to before.
        assert fps_query() == before, "Y's FPS%/P-BF inputs must be unchanged"
        y_persp_play_ids_after = {
            r[0] for r in db.execute(
                "SELECT id FROM plays WHERE perspective_team_id = ?", (y_id,)
            ).fetchall()
        }
        assert y_persp_play_ids_after == y_persp_play_ids_before
        # The X-batting FPS-bearing play specifically survives.
        assert db.execute(
            "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ? "
            "AND batting_team_id = ?",
            (y_id, x_id),
        ).fetchone()[0] == 1
        # Its play_events survive too (guard applied to the subquery).
        assert db.execute(
            "SELECT COUNT(*) FROM play_events pe JOIN plays p ON pe.play_id = p.id "
            "WHERE p.perspective_team_id = ? AND p.batting_team_id = ?",
            (y_id, x_id),
        ).fetchone()[0] == 1
        # X's batting line under Y's perspective survives.
        assert db.execute(
            "SELECT COUNT(*) FROM player_game_batting "
            "WHERE perspective_team_id = ? AND team_id = ?",
            (y_id, x_id),
        ).fetchone()[0] == 1
        # X's OWN perspective rows are gone.
        assert db.execute(
            "SELECT COUNT(*) FROM plays WHERE perspective_team_id = ?", (x_id,)
        ).fetchone()[0] == 0

    def test_guard_retains_x_team_row_and_shared_game_without_integrity_error(self, db):
        """AC-2: X's teams row and the shared game/anchor rows are RETAINED
        (FK-safety survivor path); the operation raises no IntegrityError.
        """
        x_id, y_id = self._seed_shared_game(db, y_has_report=True)

        # Completes cleanly (no sqlite3.IntegrityError raised).
        cascade_delete_team(db, x_id)

        # X's teams row retained (still FK-referenced by the shared game + spared
        # plays that reference batting_team_id = X).
        assert db.execute(
            "SELECT 1 FROM teams WHERE id = ?", (x_id,)
        ).fetchone() is not None
        # Shared game row retained (Y's perspective keeps it alive).
        assert db.execute(
            "SELECT 1 FROM games WHERE game_id = 'G'"
        ).fetchone() is not None

    def test_true_orphan_fully_cleaned_up(self, db):
        """AC-3: a team sharing NO game with any live-report team is fully
        cleaned up -- the guard does not regress orphan deletion.
        """
        _seed_season(db)
        _seed_player(db, "z-bat", "Zed", "Batter")
        # An unrelated live report exists, but for a team that shares no game.
        other_id = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Unrelated Report Team', 'tracked', 1)"
        ).lastrowid
        db.execute(
            "INSERT INTO reports (slug, team_id, title, expires_at) "
            "VALUES ('other-live', ?, 'Other', '2099-01-01T00:00:00Z')",
            (other_id,),
        )
        # True orphan X: solo game, sole perspective, its own report deleted.
        x_id = db.execute(
            "INSERT INTO teams (name, membership_type, is_active) "
            "VALUES ('Orphan X', 'tracked', 0)"
        ).lastrowid
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "game_date) VALUES ('go', '2026', ?, ?, '2026-04-02')",
            (x_id, x_id),
        )
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id) "
            "VALUES ('go', 1, 1, 'top', '2026', ?, ?, 'z-bat')",
            (x_id, x_id),
        )
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES ('go', ?)",
            (x_id,),
        )
        db.commit()

        cascade_delete_team(db, x_id)

        # X and all its data are gone.
        assert db.execute(
            "SELECT 1 FROM teams WHERE id = ?", (x_id,)
        ).fetchone() is None
        assert db.execute(
            "SELECT COUNT(*) FROM plays WHERE game_id = 'go'"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM games WHERE game_id = 'go'"
        ).fetchone()[0] == 0


class TestCleanupNonFatal:
    """AC-3: Cleanup failure is non-fatal."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_cleanup_error_does_not_fail_report(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """AC-3: Cleanup DB error -> report still marked 'ready'."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        _seed_team(db)
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        # Track connection call count to inject failure on the cleanup connection
        call_count = [0]
        original_fresh = _fresh_conn

        def _tracked_conn():
            call_count[0] += 1
            conn = original_fresh()
            return conn

        mock_get_conn.side_effect = _tracked_conn

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()

        # Make loader create an orphan team during load
        def _load_side_effect(crawl_result, **kwargs):
            conn = original_fresh()
            conn.execute(
                "INSERT INTO teams (name, public_id, season_year, membership_type) "
                "VALUES ('Orphan', 'orphan99', 2026, 'tracked')"
            )
            conn.commit()
            conn.close()
            return LoadResult(loaded=5)

        mock_loader.load_team.side_effect = _load_side_effect

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch(
                "src.reports.generator.cleanup_orphan_teams",
                side_effect=sqlite3.OperationalError("disk I/O error"),
            ),
        ):
            result = generate_report("abc123")

        # Report should still succeed despite cleanup failure
        assert result.success is True

        verify_conn = original_fresh()
        row = verify_conn.execute(
            "SELECT status FROM reports WHERE slug = ?", (result.slug,)
        ).fetchone()
        verify_conn.close()
        assert row[0] == "ready"


class TestQueryBeforeCleanup:
    """AC-6: Game-dependent queries execute before cleanup."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_queries_run_before_cleanup(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        db, tmp_path,
    ):
        """AC-6: Verify queries see game data that cleanup will delete."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        _seed_team(db)
        # E-273-02: the opportunistic cleanup at generate_report START runs the
        # orphan-reclamation pass. This test pins ensure_team_row to id=1, so
        # team 1 must survive that sweep (its game is only created later, during
        # load).
        #
        # E-277-01: team 1 stays 'tracked' (the PRODUCTION shape), pinned by a
        # reachability ROOT rather than by the 'member' flip E-273-02 used --
        # see the note in test_credential_expired_sets_failed for why
        # opponent_links is the mechanism for all three restored fixtures.
        db.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
            "VALUES (1, 'root-pin-queries', 'Pinned Opp')"
        )
        _seed_season(db)
        _seed_player(db, "p1", "Test", "Player")
        # E-273-02: root p1 on the surviving team so the generate-START
        # reclamation does not sweep it as a bare orphan player before the loader
        # writes its game stat row (the loader only creates players in reality).
        _seed_roster(db, 1, "p1")
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()

        # The real ScoutingLoader records every opponent stub it INSERTs into
        # the per-run created-set (E-235-04). Capture the set the generator
        # passes to the loader constructor so the mock can record into it,
        # faithfully reproducing that contract.
        captured: dict = {}

        def _make_loader(conn, created_team_ids=None):
            captured["set"] = created_team_ids
            return mock_loader

        # Loader creates orphan team + game so queries have data to find.
        # The DB season_id is derived from team metadata (season_year=2026,
        # no program) = "2026".
        def _load_side_effect(crawl_result, **kwargs):
            conn = _fresh_conn()
            cursor = conn.execute(
                "INSERT INTO teams (name, public_id, season_year, membership_type) "
                "VALUES ('Opponent', 'opp99', 2026, 'tracked')"
            )
            opp_id = cursor.lastrowid
            conn.execute(
                "INSERT OR IGNORE INTO seasons (season_id, name, year) "
                "VALUES ('2026', '2026', 2026)"
            )
            conn.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
                "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("g1", "2026", 1, opp_id, 7, 3, "2026-03-20"),
            )
            # A real loader writes per-game stat rows alongside the games row;
            # seed one so the game counts as "with data" (N>0) post-HIGH-1 and
            # the no-games gate does not fire on this AC-6 query/cleanup test.
            conn.execute(
                "INSERT INTO player_game_batting "
                "(game_id, player_id, team_id, perspective_team_id, ab, h) "
                "VALUES ('g1', 'p1', 1, 1, 3, 1)",
            )
            conn.commit()
            conn.close()
            # As the real loader would: record the INSERTed stub for run-scoped
            # orphan cleanup.
            if captured.get("set") is not None:
                captured["set"].add(opp_id)
            return LoadResult(loaded=5)

        mock_loader.load_team.side_effect = _load_side_effect

        cleanup_called = []
        original_cleanup = cleanup_orphan_teams

        def _tracking_cleanup(conn, orphan_ids):
            cleanup_called.append(orphan_ids.copy())
            return original_cleanup(conn, orphan_ids)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", side_effect=_make_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch(
                "src.reports.generator.cleanup_orphan_teams",
                side_effect=_tracking_cleanup,
            ),
        ):
            result = generate_report("abc123")

        assert result.success is True
        # Cleanup was called (orphan detected)
        assert len(cleanup_called) == 1
        # The rendered report should contain data from the game that existed
        # during query time (the render_report mock was called, confirming
        # the query block completed before cleanup)
        mock_render.assert_called_once()
        render_data = mock_render.call_args[0][0]
        # Record should show the game that cleanup will delete
        assert render_data["team"]["record"] is not None
        assert render_data["team"]["record"]["wins"] == 1


# ===========================================================================
# E-202-01: public_id backfill in report generator force-update block
# ===========================================================================


class TestPublicIdBackfill:
    """Tests for public_id backfill after step-3 (name+season_year) match."""

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_ac1_backfills_public_id_when_null(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        mock_create_session, db, tmp_path,
    ):
        """AC-1: Team with matching name+season_year but NULL public_id gets
        public_id backfilled from the generator's input slug."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        # Seed team WITHOUT public_id (simulates step-3 match)
        db.execute(
            "INSERT INTO teams (name, season_year, membership_type) "
            "VALUES ('Waverly Vikings Varsity 2026', 2026, 'tracked')"
        )
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        # Mock public API to return matching name
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "Waverly Vikings Varsity 2026",
            "team_season": {"year": 2026},
        }
        mock_session.get.return_value = mock_resp
        mock_create_session.return_value = mock_session

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("Xj9LlYlJklcl")

        assert result.success is True

        # AC-1 + AC-4: Verify public_id was backfilled
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT public_id FROM teams WHERE id = 1"
        ).fetchone()
        verify_conn.close()
        assert row[0] == "Xj9LlYlJklcl"

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_ac2_does_not_overwrite_existing_public_id(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        mock_create_session, db, tmp_path,
    ):
        """AC-2: Team with non-NULL public_id keeps original value; the
        AND public_id IS NULL guard prevents overwrite."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        # Seed team WITH existing public_id
        db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Waverly Vikings Varsity 2026', 'existing-slug', 2026, 'tracked')"
        )
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "Waverly Vikings Varsity 2026",
            "team_season": {"year": 2026},
        }
        mock_session.get.return_value = mock_resp
        mock_create_session.return_value = mock_session

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("DiFfErEnTsLuG1")

        assert result.success is True

        # AC-2: Verify public_id was NOT overwritten
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT public_id FROM teams WHERE id = 1"
        ).fetchone()
        verify_conn.close()
        assert row[0] == "existing-slug"

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_ac3_no_backfill_when_api_fails(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        mock_create_session, db, tmp_path,
    ):
        """AC-3: When the public API call fails, no public_id backfill is attempted."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        # Seed team WITHOUT public_id
        db.execute(
            "INSERT INTO teams (name, season_year, membership_type) "
            "VALUES ('Waverly Vikings Varsity 2026', 2026, 'tracked')"
        )
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        # Mock public API to FAIL
        mock_session = MagicMock()
        mock_session.get.side_effect = RuntimeError("network error")
        mock_create_session.return_value = mock_session

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("Xj9LlYlJklcl")

        assert result.success is True

        # AC-3: public_id should still be NULL (no backfill attempted)
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT public_id FROM teams WHERE id = 1"
        ).fetchone()
        verify_conn.close()
        assert row[0] is None

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_ac6_name_season_year_updated_regardless_of_public_id(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        mock_create_session, db, tmp_path,
    ):
        """AC-6: name and season_year are updated even when public_id is already set.
        The backfill guard does not interfere with the unconditional name/season_year update."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        # Seed team with OLD name and existing public_id
        db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Old Name', 'existing-slug', 2025, 'tracked')"
        )
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        # Public API updates season_year to 2026 -> derived season '2026'.
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "New Name",
            "team_season": {"year": 2026},
        }
        mock_session.get.return_value = mock_resp
        mock_create_session.return_value = mock_session

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("DiFfErEnTsLuG1")

        assert result.success is True

        # AC-6: name and season_year updated, public_id unchanged
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT name, season_year, public_id FROM teams WHERE id = 1"
        ).fetchone()
        verify_conn.close()
        assert row[0] == "New Name"
        assert row[1] == 2026
        assert row[2] == "existing-slug"

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>test</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    def test_unique_collision_does_not_abort_report(
        self, mock_spray, mock_render, mock_ensure, mock_client_cls, mock_get_conn,
        mock_create_session, db, tmp_path,
    ):
        """Edge case: another team already owns the public_id being backfilled.
        The UNIQUE constraint violation should be caught and the report should
        still generate successfully."""
        from src.gamechanger.crawlers import CrawlResult
        from src.gamechanger.loaders import LoadResult

        # Team 1: NULL public_id (target for backfill)
        db.execute(
            "INSERT INTO teams (name, season_year, membership_type) "
            "VALUES ('Waverly Vikings Varsity 2026', 2026, 'tracked')"
        )
        # Team 2: already owns the public_id we'd try to backfill. The
        # orphan-reclamation pass runs at generate_report START and would sweep
        # this gameless duplicate before the backfill, destroying the UNIQUE
        # collision the test exercises.
        #
        # E-277-01: team 2 stays 'tracked' -- the PRODUCTION shape for a
        # duplicate opponent row -- and is pinned by a reachability ROOT
        # instead. E-273-02 flipped it to 'member', which kept the test green
        # but stopped it covering the shape a real collision has: a real
        # colliding duplicate is 'tracked', and this test is the only coverage
        # of the backfill's IntegrityError path.
        db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Waverly Duplicate', 'Xj9LlYlJklcl', 2026, 'tracked')"
        )
        db.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
            "VALUES (2, 'root-pin-collision', 'Pinned Opp')"
        )
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)  # N>0 so the no-games gate does not fire

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "Waverly Vikings Varsity 2026",
            "team_season": {"year": 2026},
        }
        mock_session.get.return_value = mock_resp
        mock_create_session.return_value = mock_session

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            result = generate_report("Xj9LlYlJklcl")

        # Report should succeed despite UNIQUE collision on backfill
        assert result.success is True

        # Team 1 public_id should still be NULL (backfill failed gracefully)
        verify_conn = _fresh_conn()
        row = verify_conn.execute(
            "SELECT public_id FROM teams WHERE id = 1"
        ).fetchone()
        verify_conn.close()
        assert row[0] is None


# ── Tier-2 enrichment status observability (E-233-04) ────────────────────


class TestTier2EnrichmentStatus:
    """The three TN-4 outcomes are distinguishable and operator-detectable."""

    def _args(self):
        # E-253-07: the helper now gates on prediction.confidence, so pass a
        # real NON-suppress StarterPrediction. The patched enrich_prediction /
        # is_llm_available still drive the success/unavailable/failed outcome.
        from src.reports.starter_prediction import StarterPrediction
        return (StarterPrediction(confidence="high"), [{"game_id": "g1"}])

    def test_unavailable_no_key_status(self):
        """is_llm_available() False → (None, unavailable-no-key); not a failure."""
        from src.reports.generator import (
            TIER2_UNAVAILABLE_NO_KEY,
            _run_tier2_enrichment,
        )

        pred, history = self._args()
        with patch("src.llm.openrouter.is_llm_available", return_value=False):
            result, status = _run_tier2_enrichment(
                pred, history,
                team_name="Gretna 216 Reserve",
                team_record="10-2", reference_date=None, public_id="abc123",
            )

        assert result is None
        assert status == TIER2_UNAVAILABLE_NO_KEY

    def test_success_status(self):
        """enrich_prediction returns → (EnrichedPrediction, success)."""
        from src.reports.generator import TIER2_SUCCESS, _run_tier2_enrichment

        pred, history = self._args()
        sentinel = object()  # helper returns enrich_prediction's result verbatim
        with (
            patch("src.llm.openrouter.is_llm_available", return_value=True),
            patch(
                "src.reports.llm_analysis.enrich_prediction",
                return_value=sentinel,
            ) as mock_enrich,
        ):
            result, status = _run_tier2_enrichment(
                pred, history,
                team_name="Gretna 216 Reserve",
                team_record="10-2", reference_date=None, public_id="abc123",
            )

        assert result is sentinel
        assert status == TIER2_SUCCESS
        mock_enrich.assert_called_once()
        # E-243-04 FIX: the real opponent name is forwarded to the prompt (not
        # the "this opponent" placeholder).
        assert mock_enrich.call_args.kwargs["team_name"] == "Gretna 216 Reserve"

    def test_failed_status_on_llmerror(self, caplog):
        """enrich_prediction raises LLMError → (None, failed); WARNING + exc_info (AC-2)."""
        import logging

        from src.llm.openrouter import LLMError
        from src.reports.generator import TIER2_FAILED, _run_tier2_enrichment

        pred, history = self._args()
        with (
            patch("src.llm.openrouter.is_llm_available", return_value=True),
            patch(
                "src.reports.llm_analysis.enrich_prediction",
                side_effect=LLMError("unparseable after retry"),
            ),
            caplog.at_level(logging.WARNING, logger="src.reports.generator"),
        ):
            result, status = _run_tier2_enrichment(
                pred, history,
                team_name="Gretna 216 Reserve",
                team_record="10-2", reference_date=None, public_id="abc123",
            )

        # AC-5: non-fatal — caller still renders Tier-1 (prediction is None).
        assert result is None
        assert status == TIER2_FAILED
        # AC-2: WARNING preserved with exc_info carrying the specific cause.
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        assert warnings[0].exc_info is not None

    def test_failed_status_is_cause_agnostic(self):
        """A non-LLMError exception ALSO maps to failed (read from except, not type)."""
        from src.reports.generator import TIER2_FAILED, _run_tier2_enrichment

        pred, history = self._args()
        with (
            patch("src.llm.openrouter.is_llm_available", return_value=True),
            patch(
                "src.reports.llm_analysis.enrich_prediction",
                side_effect=RuntimeError("unexpected boom"),
            ),
        ):
            result, status = _run_tier2_enrichment(
                pred, history,
                team_name="Gretna 216 Reserve",
                team_record="10-2", reference_date=None, public_id="abc123",
            )

        assert result is None
        assert status == TIER2_FAILED


class TestTier2SuppressGate:
    """E-253-07 / TN-2: a suppressed (or absent) Tier-1 prediction skips Tier-2
    enrichment entirely -- no LLM call, no cost -- and yields a NULL status
    ('did not run'). Both suppress reasons are covered (AC-1/AC-3)."""

    @staticmethod
    def _suppressed(reason: str):
        from src.reports.starter_prediction import StarterPrediction
        return StarterPrediction(confidence="suppress", suppress_reason=reason)

    @pytest.mark.parametrize("reason", ["insufficient_data", "unsupported_level"])
    def test_suppress_skips_llm_and_returns_null_status(self, reason):
        """AC-1/AC-3: on suppress the LLM client is never invoked; status None."""
        from src.reports.generator import _run_tier2_enrichment

        with (
            patch("src.llm.openrouter.is_llm_available") as mock_avail,
            patch("src.reports.llm_analysis.enrich_prediction") as mock_enrich,
        ):
            result, status = _run_tier2_enrichment(
                self._suppressed(reason), [{"game_id": "g1"}],
                team_name="Rival High", team_record="3-1",
                reference_date=None, public_id="abc123",
            )

        assert result is None
        assert status is None  # NULL: enrichment did not run (not a failure)
        # No cost: neither the availability check nor the enrichment ran.
        mock_avail.assert_not_called()
        mock_enrich.assert_not_called()

    def test_absent_prediction_skips_llm(self):
        """A None Tier-1 prediction also skips enrichment (no LLM call)."""
        from src.reports.generator import _run_tier2_enrichment

        with (
            patch("src.llm.openrouter.is_llm_available") as mock_avail,
            patch("src.reports.llm_analysis.enrich_prediction") as mock_enrich,
        ):
            result, status = _run_tier2_enrichment(
                None, [{"game_id": "g1"}],
                team_name="Rival High", team_record="3-1",
                reference_date=None, public_id="abc123",
            )

        assert result is None
        assert status is None
        mock_avail.assert_not_called()
        mock_enrich.assert_not_called()

    @pytest.mark.parametrize("reason", ["insufficient_data", "unsupported_level"])
    def test_enrich_prediction_defensive_guard_raises_without_llm(self, reason):
        """Defensive half: enrich_prediction itself refuses a suppressed
        prediction BEFORE any API call (the caller must gate; this is a
        contract tripwire)."""
        from src.reports.llm_analysis import enrich_prediction

        with patch("src.reports.llm_analysis.query_openrouter") as mock_query:
            with pytest.raises(ValueError, match="suppressed"):
                enrich_prediction(self._suppressed(reason), [{"game_id": "g1"}])
        mock_query.assert_not_called()


# ---------------------------------------------------------------------------
# E-235-03: quality gates (b) season-fallback, (c) identity, footer data
# ---------------------------------------------------------------------------


class TestQualityGatesFlags:
    """AC-3/AC-4/AC-5: gate (b)/(c) run-record flags + footer render inputs."""

    @staticmethod
    def _run(db, tmp_path, mock_get_conn, mock_client_cls, *, capture=None):
        """Drive a successful generation (N>0 via a seeded game). Returns the
        GenerationResult. ``capture`` (if given) records the render data dict."""
        _seed_team(db)
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()
        _seed_completed_game(db)

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()
        mock_client_cls.return_value = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026", games_crawled=1,
            games=[{"game_status": "completed"}], boxscores={},
        )
        from src.gamechanger.loaders import LoadResult
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        render_patch = (
            patch("src.reports.generator.render_report", side_effect=capture)
            if capture is not None
            else patch("src.reports.generator.render_report", return_value="<html>ok</html>")
        )
        with (
            render_patch,
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._crawl_and_load_spray",
                  return_value=_SprayOutcome("completed", 1)),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
        ):
            return generate_report("abc123")

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    def test_season_id_used_recorded_without_fallback_telemetry(
        self, mock_ensure, mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """E-241-01: the default team (season_year set, no program) resolves to
        the year-only season_id "2026" and records season_id_used; the
        season_fallback telemetry is no longer captured (E-241-02 dropped the
        column entirely via migration 006)."""
        result = self._run(db, tmp_path, mock_get_conn, mock_client_cls)
        assert result.success is True
        run = _read_run_record(str(tmp_path / "test.db"), result.slug)
        assert run["season_id_used"] == "2026"
        # season_fallback column dropped by migration 006 (E-241-02): it is no
        # longer part of the run record at all.
        assert "season_fallback" not in run

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "name_only", False))
    def test_gate_c_name_only_identity_flagged(
        self, mock_ensure, mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """AC-4: a name-only team match records identity_match_method='name_only'
        (stashed at ensure_team_row, written when the run row is created)."""
        result = self._run(db, tmp_path, mock_get_conn, mock_client_cls)
        assert result.success is True
        run = _read_run_record(str(tmp_path / "test.db"), result.slug)
        assert run["identity_match_method"] == "name_only"

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    def test_footer_inputs_threaded_into_render_data(
        self, mock_ensure, mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """AC-5: the render data dict carries M/N/K, spray availability, and the
        derived degraded_confidence boolean for story 07's footer."""
        captured: dict = {}

        def _capture(data):
            captured["data"] = data
            return "<html>ok</html>"

        result = self._run(
            db, tmp_path, mock_get_conn, mock_client_cls, capture=_capture,
        )
        assert result.success is True
        data = captured["data"]
        assert data["completed_games"] == 1  # M
        assert data["completed_games_with_data"] == 1  # N (the seeded game)
        assert "plays_game_count" in data  # K
        # spray_available reflects spray rows actually loaded (none in this
        # mocked run) -- it is a bool keyed off the queried spray_charts.
        assert data["spray_available"] is False
        # E-236-06 AC-2 / E-241-01: clean modal data (default team ->
        # identity_match_method="anchor", NOT name-only) does NOT trip the
        # coach-facing degraded line. The season-fallback signal was never part
        # of the degraded_confidence term, and its operator telemetry is now
        # removed entirely. Only a name-only identity match degrades confidence.
        assert data["degraded_confidence"] is False

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "name_only", False))
    def test_name_only_identity_degrades_confidence(
        self, mock_ensure, mock_client_cls, mock_get_conn, db, tmp_path,
    ):
        """E-236-06 AC-3: a name-only identity match still trips the coach-
        facing degraded-confidence line (behavior preserved after dropping the
        season_fallback term)."""
        captured: dict = {}

        def _capture(data):
            captured["data"] = data
            return "<html>ok</html>"

        result = self._run(
            db, tmp_path, mock_get_conn, mock_client_cls, capture=_capture,
        )
        assert result.success is True
        assert captured["data"]["degraded_confidence"] is True


# ---------------------------------------------------------------------------
# E-238-07: expired-report file cleanup
# ---------------------------------------------------------------------------


def _iso_offset_days(days: int) -> str:
    """Return an ISO-8601 UTC timestamp ``days`` from now (negative = past).

    Uses the canonical ``UTC_ISO_FORMAT`` rather than a local literal: this
    builds the same ``expires_at`` strings the app writes, and a divergent copy
    would keep passing against a format the code no longer emits (E-256-03).
    """
    from datetime import datetime, timedelta, timezone

    from src.util.timezone import UTC_ISO_FORMAT

    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return dt.strftime(UTC_ISO_FORMAT)


def _insert_report_row(
    conn,
    slug: str,
    team_id: int,
    expires_at: str,
    report_path: str | None,
    status: str = "ready",
) -> None:
    """Insert a reports row with the given expiry and path."""
    conn.execute(
        "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at, report_path) "
        "VALUES (?, ?, 'Test Report', ?, ?, ?, ?)",
        (slug, team_id, status, _iso_offset_days(-30), expires_at, report_path),
    )
    conn.commit()


def _write_report_file(tmp_path, slug: str) -> Path:
    """Create data/reports/{slug}.html under tmp_path and return its Path."""
    reports_dir = tmp_path / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    file_path = reports_dir / f"{slug}.html"
    file_path.write_text("<html><body>report</body></html>", encoding="utf-8")
    return file_path


class TestCleanupExpiredReports:
    """E-238-07: cleanup_expired_reports() unlinks expired files, keeps rows."""

    def _fresh_conn_factory(self, tmp_path):
        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        return _fresh_conn

    def test_expired_file_removed_row_kept_path_nulled(self, db, tmp_path):
        """AC-1/AC-5: expired file unlinked, row KEPT, report_path NULLed."""
        team_id = _seed_team(db)
        file_path = _write_report_file(tmp_path, "exp1")
        _insert_report_row(
            db, "exp1", team_id, _iso_offset_days(-1), "reports/exp1.html"
        )

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=self._fresh_conn_factory(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            result = cleanup_expired_reports()

        assert isinstance(result, CleanupResult)
        assert result.files_removed == 1
        assert result.errors == 0
        # File is gone from disk.
        assert not file_path.exists()
        # Row is KEPT, but report_path is NULLed (still shows as expired).
        verify = self._fresh_conn_factory(tmp_path)()
        row = verify.execute(
            "SELECT status, report_path FROM reports WHERE slug = ?", ("exp1",)
        ).fetchone()
        verify.close()
        assert row is not None  # row kept
        assert row[1] is None  # report_path nulled

    def test_not_yet_expired_untouched(self, db, tmp_path):
        """AC-2/AC-6: a not-yet-expired report's file and path are preserved
        (so its share link still serves)."""
        team_id = _seed_team(db)
        file_path = _write_report_file(tmp_path, "live1")
        _insert_report_row(
            db, "live1", team_id, _iso_offset_days(+7), "reports/live1.html"
        )

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=self._fresh_conn_factory(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            result = cleanup_expired_reports()

        assert result.files_removed == 0
        assert result.errors == 0
        # Live report's file remains on disk.
        assert file_path.exists()
        # report_path preserved -> share link still serves.
        verify = self._fresh_conn_factory(tmp_path)()
        row = verify.execute(
            "SELECT report_path FROM reports WHERE slug = ?", ("live1",)
        ).fetchone()
        verify.close()
        assert row[0] == "reports/live1.html"

    def test_per_file_error_isolation(self, db, tmp_path):
        """AC-1/Technical Approach: one unremovable file does not abort the sweep.

        Two expired reports A and B. A's unlink raises; B's succeeds (real
        unlink). The sweep must process BOTH: A is counted as an error and
        keeps its report_path (retry later); B is removed and its path nulled.
        """
        team_id = _seed_team(db)
        file_a = _write_report_file(tmp_path, "errA")
        file_b = _write_report_file(tmp_path, "okB")
        _insert_report_row(db, "errA", team_id, _iso_offset_days(-2), "reports/errA.html")
        _insert_report_row(db, "okB", team_id, _iso_offset_days(-2), "reports/okB.html")

        real_unlink = Path.unlink

        def flaky_unlink(self, *args, **kwargs):
            if self.name == "errA.html":
                raise OSError("file is locked")
            return real_unlink(self, *args, **kwargs)

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=self._fresh_conn_factory(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
            patch.object(Path, "unlink", flaky_unlink),
        ):
            result = cleanup_expired_reports()

        # Sweep completed over BOTH rows despite A raising.
        assert result.errors == 1
        assert result.files_removed == 1
        # A's file remains (unlink raised); B's file is really gone.
        assert file_a.exists()
        assert not file_b.exists()
        # A keeps its report_path (retry later); B's path is nulled.
        verify = self._fresh_conn_factory(tmp_path)()
        rows = dict(
            verify.execute(
                "SELECT slug, report_path FROM reports WHERE slug IN ('errA', 'okB')"
            ).fetchall()
        )
        verify.close()
        assert rows["errA"] == "reports/errA.html"  # kept for retry
        assert rows["okB"] is None  # nulled

    def test_null_report_path_rows_ignored(self, db, tmp_path):
        """AC-1: rows with NULL report_path are not selected (nothing to unlink)."""
        team_id = _seed_team(db)
        _insert_report_row(db, "nopath", team_id, _iso_offset_days(-5), None)

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=self._fresh_conn_factory(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            result = cleanup_expired_reports()

        assert result.files_removed == 0
        assert result.errors == 0

    def test_opportunistic_cleanup_failure_does_not_block_generation(self, tmp_path):
        """AC-3/AC-6: a cleanup failure at generate_report() start is swallowed
        and generation proceeds (here, to a normal parse-stage failure result)."""
        with patch(
            "src.reports.generator.cleanup_expired_reports",
            side_effect=RuntimeError("cleanup boom"),
        ):
            # A bare UUID fails fast at the parse stage -- but only if the
            # opportunistic cleanup exception was swallowed first (AC-3).
            result = generate_report("123e4567-e89b-12d3-a456-426614174000")

        assert isinstance(result, GenerationResult)
        assert result.success is False
        # Proves generation ran past the swallowed cleanup error to the parser.
        assert "UUID" in (result.error_message or "")


class TestCleanupConnectionSeam:
    """E-256-04 (CR round 1): generate_report must INJECT its connection into the
    opportunistic sweep, not let the sweep resolve one from lifecycle's globals.

    `get_connection` is a module global. Once `cleanup_expired_reports` moved to
    `src/reports/lifecycle.py`, a no-arg call resolved `lifecycle.get_connection`
    -- the REAL `data/app.db` -- while every generation test sandboxes only
    `generator.get_connection`. `generate_report` swallows all cleanup exceptions
    by design, so the detachment could never surface as a test failure: the sweep
    would silently run against production data, unlinking real report HTML.

    Both assertions below are falsifying inputs. Revert the fix (call
    `cleanup_expired_reports()` with no argument) and BOTH fail: the lifecycle
    connection factory gets called, and the expired file survives because the
    sweep read a different database.
    """

    def test_generate_report_injects_connection_into_cleanup(self, db, tmp_path):
        team_id = _seed_team(db)
        file_path = _write_report_file(tmp_path, "seam1")
        _insert_report_row(
            db, "seam1", team_id, _iso_offset_days(-1), "reports/seam1.html"
        )

        def _sandbox_conn():
            conn = sqlite3.connect(str(tmp_path / "test.db"))
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        with (
            # The ONLY connection seam a generation test patches.
            patch("src.reports.generator.get_connection", side_effect=_sandbox_conn),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
            # Left deliberately UNPATCHED-as-a-factory: if the sweep reaches for
            # this, it has escaped the caller's sandbox.
            patch("src.reports.lifecycle.get_connection") as lifecycle_get_connection,
            # Short-circuit the pipeline; this test is about the sweep only.
            patch("src.reports.generator._ReportGeneration") as mock_pipeline,
        ):
            mock_pipeline.return_value.run.return_value = GenerationResult(
                success=False, error_message="stub"
            )
            generate_report("https://web.gc.com/teams/abc123")

        # 1. The sweep never opened its own connection -- it used the injected one.
        lifecycle_get_connection.assert_not_called()

        # 2. It therefore acted on the caller's database: the expired file is gone
        #    and its report_path is NULLed.
        assert not file_path.exists()
        verify = _sandbox_conn()
        row = verify.execute(
            "SELECT report_path FROM reports WHERE slug = ?", ("seam1",)
        ).fetchone()
        verify.close()
        assert row is not None      # row kept
        assert row[0] is None       # report_path NULLed

    def test_borrowed_connection_row_factory_is_restored(self, db, tmp_path):
        """E-256-04 (CR round 2): a BORROWED connection is caller-owned state.

        Both sweeps set `row_factory = sqlite3.Row` for their own reads. When they
        owned the connection that died with it; a borrowed one outlives the call.
        `_conn_scope` saves and restores it, so the borrow is non-destructive.

        Falsifying input: drop the save/restore and the caller's row_factory comes
        back as `sqlite3.Row` instead of the sentinel it set.
        """
        def _sentinel_factory(cursor, row):  # noqa: ARG001 -- identity is the point
            return row

        borrowed = sqlite3.connect(str(tmp_path / "test.db"))
        borrowed.row_factory = _sentinel_factory
        try:
            with patch("src.reports.lifecycle._REPO_ROOT", tmp_path):
                # Exercises BOTH nested scopes: cleanup forwards `conn` to the
                # reaper, so the connection is borrowed twice before returning.
                cleanup_expired_reports(borrowed)

            assert borrowed.row_factory is _sentinel_factory
        finally:
            borrowed.close()

    def test_owned_connection_needs_no_restore(self, db, tmp_path):
        """The `conn=None` branch opens and closes its own connection, so there is
        nothing to restore -- and no caller state to damage.

        Also pins the open-and-close COUNT: cleanup forwards `None` to the reaper,
        so each opens its own. That is the pre-move behaviour the CLI and
        app-startup callers still rely on.
        """
        opened = []

        def _factory():
            conn = sqlite3.connect(str(tmp_path / "test.db"))
            conn.execute("PRAGMA foreign_keys=ON;")
            opened.append(conn)
            return conn

        with (
            patch("src.reports.lifecycle.get_connection", side_effect=_factory),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            cleanup_expired_reports()

        assert len(opened) == 2  # reaper, then cleanup


class TestReapStaleGenerating:
    """E-252-08: reap reports stuck at status='generating' to 'failed'."""

    def _fresh_conn(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _insert_generating(self, conn, slug, team_id, generated_at, report_path=None):
        conn.execute(
            "INSERT INTO reports (slug, team_id, title, status, generated_at, "
            "expires_at, report_path) VALUES (?, ?, 'Test Report', 'generating', ?, ?, ?)",
            (slug, team_id, generated_at, _iso_offset_days(+14), report_path),
        )
        conn.commit()

    def test_stale_generating_reaped_to_failed(self, db, tmp_path):
        """AC-1: a 'generating' row whose start is older than the threshold is
        transitioned to 'failed' with an operator-readable reaped message."""
        team_id = _seed_team(db)
        self._insert_generating(db, "stale1", team_id, _iso_offset_days(-1))

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=lambda: self._fresh_conn(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            result = reap_stale_generating_reports()

        assert isinstance(result, ReaperResult)
        assert result.reaped == 1
        verify = self._fresh_conn(tmp_path)
        row = verify.execute(
            "SELECT status, error_message FROM reports WHERE slug = 'stale1'"
        ).fetchone()
        verify.close()
        assert row[0] == "failed"
        assert "Reaped" in (row[1] or "")

    def test_the_row_is_freed_even_when_the_orphan_unlink_fails(self, db, tmp_path):
        """A failing unlink must NOT leave the row stuck at 'generating'.

        The UPDATE and the unlink share one per-row try/except that swallows and
        continues. With the unlink FIRST, an unlink failure skipped the UPDATE
        and the row stayed 'generating' forever -- which since 2026-08-16 wedges
        POST /admin/reports/generate permanently (it refuses on any 'generating'
        row) with no UI escape, because the delete affordance is itself gated on
        status != 'generating'. Flipping the row first makes a failed unlink cost
        a stray file instead of the product.
        """
        team_id = _seed_team(db)
        self._insert_generating(db, "unlinkfail", team_id, _iso_offset_days(-1))
        reports_dir = tmp_path / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "unlinkfail.html").write_text("<html>partial</html>")

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=lambda: self._fresh_conn(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
            patch("src.reports.lifecycle._REPORTS_DIR", reports_dir),
            patch("pathlib.Path.unlink", side_effect=PermissionError("read-only fs")),
        ):
            result = reap_stale_generating_reports()

        verify = self._fresh_conn(tmp_path)
        status = verify.execute(
            "SELECT status FROM reports WHERE slug = 'unlinkfail'"
        ).fetchone()[0]
        verify.close()

        assert status == "failed", (
            "a failed orphan unlink left the row stuck at 'generating', which "
            "permanently wedges the admin generate page"
        )
        assert result.errors == 1

    def test_fresh_generating_left_untouched(self, db, tmp_path):
        """AC-2: a 'generating' row WITHIN the threshold (a live generation) is NOT
        reaped -- the reaper must not kill an in-progress generation."""
        team_id = _seed_team(db)
        self._insert_generating(db, "fresh1", team_id, _iso_offset_days(0))  # now

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=lambda: self._fresh_conn(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            result = reap_stale_generating_reports()

        assert result.reaped == 0
        verify = self._fresh_conn(tmp_path)
        row = verify.execute(
            "SELECT status FROM reports WHERE slug = 'fresh1'"
        ).fetchone()
        verify.close()
        assert row[0] == "generating"  # live generation untouched

    def test_reaper_fires_via_cleanup_trigger(self, db, tmp_path):
        """AC-3/AC-6: the reaper runs on its real no-operator-action trigger --
        invoke cleanup_expired_reports() and observe the stale row transition."""
        team_id = _seed_team(db)
        self._insert_generating(db, "viacleanup", team_id, _iso_offset_days(-1))

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=lambda: self._fresh_conn(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            cleanup_expired_reports()  # the opportunistic trigger

        verify = self._fresh_conn(tmp_path)
        row = verify.execute(
            "SELECT status FROM reports WHERE slug = 'viacleanup'"
        ).fetchone()
        verify.close()
        assert row[0] == "failed"

    def test_reaper_unlinks_orphan_html(self, db, tmp_path):
        """A stuck 'generating' row's orphan partial HTML (written before the ready
        update set report_path, so report_path is NULL) is unlinked by the reaper --
        cleanup_expired_reports (keyed on report_path IS NOT NULL) never could."""
        team_id = _seed_team(db)
        orphan = _write_report_file(tmp_path, "orphan1")  # data/reports/orphan1.html
        self._insert_generating(db, "orphan1", team_id, _iso_offset_days(-1), report_path=None)
        assert orphan.exists()

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=lambda: self._fresh_conn(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
            # The reaper resolves the orphan via the named _REPORTS_DIR constant
            # (computed from _REPO_ROOT at import time), so redirect it too.
            patch("src.reports.lifecycle._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = reap_stale_generating_reports()

        assert result.reaped == 1
        assert result.files_removed == 1
        assert not orphan.exists()  # orphan HTML removed

    def test_reaper_idempotent_and_terminal_rows_immune(self, db, tmp_path):
        """AC-6/TN-8: running twice does not corrupt; already-'ready' and already-
        'failed' rows are never touched by the reaper."""
        team_id = _seed_team(db)
        self._insert_generating(db, "stale2", team_id, _iso_offset_days(-1))
        _insert_report_row(
            db, "ready2", team_id, _iso_offset_days(+7), "reports/ready2.html", status="ready"
        )
        db.execute(
            "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at) "
            "VALUES ('failed2', ?, 'T', 'failed', ?, ?)",
            (team_id, _iso_offset_days(-1), _iso_offset_days(+7)),
        )
        db.commit()

        with (
            patch("src.reports.lifecycle.get_connection",
                  side_effect=lambda: self._fresh_conn(tmp_path)),
            patch("src.reports.lifecycle._REPO_ROOT", tmp_path),
        ):
            first = reap_stale_generating_reports()
            second = reap_stale_generating_reports()

        assert first.reaped == 1
        assert second.reaped == 0  # idempotent: nothing left to reap on the re-run
        verify = self._fresh_conn(tmp_path)
        rows = dict(verify.execute("SELECT slug, status FROM reports").fetchall())
        verify.close()
        assert rows["stale2"] == "failed"
        assert rows["ready2"] == "ready"    # a completed report is immune
        assert rows["failed2"] == "failed"  # a terminal failure is immune

    def test_stale_generating_seconds_constant(self):
        """AC-5: the threshold is the single named constant (1 hour), and is well
        below the 14-day report expiry."""
        from src.reports.generator import _EXPIRY_DAYS

        assert STALE_GENERATING_SECONDS == 3600
        assert STALE_GENERATING_SECONDS < _EXPIRY_DAYS * 24 * 3600


# ---------------------------------------------------------------------------
# E-247-05: plays-scope consolidation -- golden characterization (HARD GATE)
# ---------------------------------------------------------------------------
#
# The three _query_plays_* functions share one scope builder (_plays_scope).
# These queries produce stat DENOMINATORS (charted-PA, perspective scoping,
# season scope), so any scope-branch divergence is silent stat corruption.
# This pins the exact result sets for BOTH scopes -- game_ids-IN and
# season-JOIN -- on a dataset crafted to exercise every scope dimension:
#   - charted vs un-charted PAs (pitch_count 0 vs >0): charted-PA denominators
#   - two perspectives on the same plays: perspective_team_id scoping
#   - a NULL pitcher row: pitcher_id IS NOT NULL filter
#   - g3 = an off-team season game: the home/away restriction (pitching/FPS/
#     coverage exclude it) vs the batting_team_id scope (batting includes it),
#     which is exactly the divergence the two scope flavors must preserve.
#
# Cross-source equivalence to the pre-refactor queries (each of the three, in
# all scopes) was additionally proven byte-identical via an importlib pre-vs-post
# diff during development (E-247-05 AC-2).

_PLAYS_SCOPE_SEASON = "2025"


def _seed_plays_scope_dataset(db):
    """Build the representative plays dataset; return the scouted team id."""
    team = db.execute(
        "INSERT INTO teams (name, membership_type, is_active, season_year) "
        "VALUES ('T', 'tracked', 1, 2025)"
    ).lastrowid
    other = db.execute(
        "INSERT INTO teams (name, membership_type, is_active, season_year) "
        "VALUES ('O', 'tracked', 1, 2025)"
    ).lastrowid
    db.execute(
        "INSERT OR IGNORE INTO seasons (season_id, name, year) "
        "VALUES (?, ?, 2025)",
        (_PLAYS_SCOPE_SEASON, _PLAYS_SCOPE_SEASON),
    )
    for pid in ("pitA", "pitB", "batA", "batB"):
        db.execute(
            "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'F', 'L')",
            (pid,),
        )
    for pid in ("pitA", "pitB"):  # team_rosters drives the FPS roster JOIN
        db.execute(
            "INSERT INTO team_rosters (player_id, team_id, season_id) VALUES (?, ?, ?)",
            (pid, team, _PLAYS_SCOPE_SEASON),
        )
    # g1/g2 are the team's own games; g3 is an off-team season game.
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES ('g1', ?, '2025-04-01', ?, ?, 'completed')",
        (_PLAYS_SCOPE_SEASON, team, other),
    )
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES ('g2', ?, '2025-04-02', ?, ?, 'completed')",
        (_PLAYS_SCOPE_SEASON, other, team),
    )
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) "
        "VALUES ('g3', ?, '2025-04-03', ?, ?, 'completed')",
        (_PLAYS_SCOPE_SEASON, other, other),
    )
    # (game, order, batter, pitcher, batting_team, perspective, pc, fps, qab)
    rows = [
        ("g1", 1, "batA", "pitA", team, team, 3, 1, 1),
        ("g1", 2, "batA", "pitA", team, team, 0, 0, 1),    # un-charted PA
        ("g1", 3, "batB", "pitB", other, team, 5, 0, 0),
        ("g1", 4, "batB", None, other, team, 2, 0, 1),     # NULL pitcher
        ("g2", 1, "batA", "pitB", team, team, 4, 1, 0),
        ("g2", 2, "batB", "pitA", other, team, 0, 0, 1),   # un-charted PA
        ("g1", 5, "batA", "pitA", team, other, 9, 1, 1),   # other perspective
        ("g2", 3, "batA", "pitB", team, other, 9, 1, 1),   # other perspective
        ("g3", 1, "batA", "pitA", team, team, 7, 1, 1),    # off-team season game
    ]
    for g, o, b, p, bt, persp, pc, fps, qab in rows:
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, batter_id, pitcher_id, outcome, pitch_count, "
            "is_first_pitch_strike, is_qab, perspective_team_id) "
            "VALUES (?, ?, 1, 'top', ?, ?, ?, ?, 'x', ?, ?, ?, ?)",
            (g, o, _PLAYS_SCOPE_SEASON, bt, b, p, pc, fps, qab, persp),
        )
    db.commit()
    return team


def test_plays_scope_golden_game_ids_scope(db):
    """AC-2: pinned result sets for the game_ids-IN scope (exact games g1+g2)."""
    from src.reports.generator import (
        _query_plays_batting_stats,
        _query_plays_pitching_stats,
        _query_plays_team_stats,
    )

    team = _seed_plays_scope_dataset(db)
    gids = ["g1", "g2"]

    assert _query_plays_pitching_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=gids) == {
        "pitA": {"fps_pct": 1.0, "pitches_per_bf": 3.0},
        "pitB": {"fps_pct": 0.5, "pitches_per_bf": 4.5},
    }
    assert _query_plays_batting_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=gids) == {
        "batA": {"qab_pct": 2 / 3, "pitches_per_pa": 3.5},
    }
    assert _query_plays_team_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=gids) == {
        "team_fps_pct": 2 / 3,
        "team_pitches_per_pa": 3.5,
        "team_qab_pct": 2 / 3,
        "has_plays_data": True,
        "plays_game_count": 2,
        "pitch_charted_game_count": 2,
    }


def test_plays_scope_golden_season_scope(db):
    """AC-2: pinned result sets for the season-JOIN scope (game_ids=None).

    Differs from the game_ids scope by g3: batting (batting_team_id-scoped)
    includes it, while pitching/FPS/coverage (home/away-restricted) exclude it
    -- the exact scope divergence the builder must preserve.
    """
    from src.reports.generator import (
        _query_plays_batting_stats,
        _query_plays_pitching_stats,
        _query_plays_team_stats,
    )

    team = _seed_plays_scope_dataset(db)

    # Pitching/FPS/coverage exclude g3 (not the team's own game) -> same as game_ids.
    assert _query_plays_pitching_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=None) == {
        "pitA": {"fps_pct": 1.0, "pitches_per_bf": 3.0},
        "pitB": {"fps_pct": 0.5, "pitches_per_bf": 4.5},
    }
    # Batting includes g3 (batA batted for the team) -> denominators grow.
    assert _query_plays_batting_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=None) == {
        "batA": {"qab_pct": 0.75, "pitches_per_pa": 14 / 3},
    }
    assert _query_plays_team_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=None) == {
        "team_fps_pct": 2 / 3,
        "team_pitches_per_pa": 14 / 3,
        "team_qab_pct": 0.75,
        "has_plays_data": True,
        "plays_game_count": 2,
        "pitch_charted_game_count": 2,
    }


def test_plays_scope_empty_game_ids_returns_empty(db):
    """AC-2: empty game_ids short-circuits to empty/zero results (guard preserved)."""
    from src.reports.generator import (
        _EMPTY_PLAYS_TEAM,
        _query_plays_batting_stats,
        _query_plays_pitching_stats,
        _query_plays_team_stats,
    )

    team = _seed_plays_scope_dataset(db)

    assert _query_plays_pitching_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=[]) == {}
    assert _query_plays_batting_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=[]) == {}
    team_empty = _query_plays_team_stats(db, team, _PLAYS_SCOPE_SEASON, game_ids=[])
    assert team_empty == _EMPTY_PLAYS_TEAM
    # AC-3: the empty payload is a fresh copy, not the shared constant object.
    assert team_empty is not _EMPTY_PLAYS_TEAM


class TestCheckRatePlausibility:
    """E-257-03 / TN-4: report-time plausibility WARNING guard.

    Fast unit tests over the pure helper (AC-4) -- NOT a full generate_report()
    drive (avoids the disk-backed-fixture deadlock gotcha in testing.md). A thin
    caller-side test confirms the messages reach WARNING via the module logger.
    ``team_fps_pct`` is a FRACTION (0-1); bounds are 0.30-0.75 and P/PA 3.0-4.5.
    """

    # ── Out-of-range: each rate flagged (AC-1) ───────────────────────────
    def test_fps_pct_above_max_flagged(self):
        # 0.912 == 91.2% -- an 18x-off-shaped headline, well above the 75% ceiling.
        msgs = _check_rate_plausibility(
            {"team_fps_pct": 0.912, "team_pitches_per_pa": 3.8}
        )
        assert len(msgs) == 1
        assert "team_fps_pct" in msgs[0]
        assert "91.2%" in msgs[0]
        assert "30-75%" in msgs[0]
        assert "review before sharing" in msgs[0]

    def test_fps_pct_below_min_flagged(self):
        # 0.20 == 20%, below the widened 30% floor.
        msgs = _check_rate_plausibility(
            {"team_fps_pct": 0.20, "team_pitches_per_pa": 3.8}
        )
        assert len(msgs) == 1
        assert "team_fps_pct" in msgs[0]
        assert "20.0%" in msgs[0]

    def test_pitches_per_pa_above_max_flagged(self):
        msgs = _check_rate_plausibility(
            {"team_fps_pct": 0.55, "team_pitches_per_pa": 5.5}
        )
        assert len(msgs) == 1
        assert "team_pitches_per_pa" in msgs[0]
        assert "5.50" in msgs[0]
        assert "3.0-4.5" in msgs[0]
        assert "review before sharing" in msgs[0]

    def test_pitches_per_pa_below_min_flagged(self):
        msgs = _check_rate_plausibility(
            {"team_fps_pct": 0.55, "team_pitches_per_pa": 1.5}
        )
        assert len(msgs) == 1
        assert "team_pitches_per_pa" in msgs[0]
        assert "1.50" in msgs[0]

    def test_both_out_of_range_yields_two_messages(self):
        msgs = _check_rate_plausibility(
            {"team_fps_pct": 0.912, "team_pitches_per_pa": 1.5}
        )
        assert len(msgs) == 2

    # ── In-range / boundary: no false alarm (AC-2) ───────────────────────
    def test_both_in_range_no_messages(self):
        assert _check_rate_plausibility(
            {"team_fps_pct": 0.55, "team_pitches_per_pa": 3.8}
        ) == []

    def test_bounds_are_inclusive(self):
        # Exactly at each edge is in-range (inclusive comparison).
        assert _check_rate_plausibility(
            {"team_fps_pct": 0.30, "team_pitches_per_pa": 3.0}
        ) == []
        assert _check_rate_plausibility(
            {"team_fps_pct": 0.75, "team_pitches_per_pa": 4.5}
        ) == []

    # ── None rates (no charted data) are skipped, not flagged (AC-2) ──────
    def test_none_rates_are_skipped(self):
        assert _check_rate_plausibility(
            {"team_fps_pct": None, "team_pitches_per_pa": None}
        ) == []

    def test_missing_keys_are_skipped(self):
        # A partial/absent mapping does not raise and flags nothing.
        assert _check_rate_plausibility({}) == []

    def test_one_none_one_out_of_range(self):
        # None FPS skipped; the out-of-range P/PA still flags.
        msgs = _check_rate_plausibility(
            {"team_fps_pct": None, "team_pitches_per_pa": 5.5}
        )
        assert len(msgs) == 1
        assert "team_pitches_per_pa" in msgs[0]

    # ── Caller-side: the REAL wiring helper logs at WARNING (AC-4) ───────
    # Exercises the actual call-site helper the generator invokes (not a
    # re-implemented loop), so removing/breaking the guard call fails a test.
    # Still no full generate_report() drive (deadlock gotcha avoided).
    def test_out_of_range_messages_logged_at_warning(self, caplog):
        import logging

        slug = "empire-netting-abc123"
        data = {"team_fps_pct": 0.912, "team_pitches_per_pa": 1.5}
        with caplog.at_level(logging.WARNING, logger="src.reports.generator"):
            _log_rate_plausibility_warnings(data, slug)

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 2
        assert all(slug in r.getMessage() for r in warnings)

    def test_in_range_emits_no_warning(self, caplog):
        import logging

        data = {"team_fps_pct": 0.55, "team_pitches_per_pa": 3.8}
        with caplog.at_level(logging.WARNING, logger="src.reports.generator"):
            _log_rate_plausibility_warnings(data, "in-range-slug")

        assert [r for r in caplog.records if r.levelname == "WARNING"] == []


# ---------------------------------------------------------------------------
# E-264-02: ERA basis correction (compute site + post-resolution fetch)
# ---------------------------------------------------------------------------
class TestEraBasisComputeSite:
    """AC-3/AC-4: ERA uses the team's innings_per_game basis (fallback 7); K/9
    and WHIP are UNCHANGED."""

    def test_era_basis_innings_helper(self):
        assert era_basis_innings(6) == 6
        assert era_basis_innings(7) == 7
        # NULL (never fetched) -> fallback 7, NOT a crash on ``None * 3``.
        assert era_basis_innings(None) == 7

    def test_compute_rates_uses_stored_basis_six(self):
        rows = [{
            "ip_outs": 18, "er": 2, "so": 5, "bb": 1, "h": 2,
            "pitches": 100, "total_strikes": 60, "innings_per_game": 6,
        }]
        _compute_pitching_rates(rows)
        assert rows[0]["era"] == "2.00"   # 2 * 6*3 / 18
        assert rows[0]["k9"] == "7.5"     # 5 * 27 / 18  (K/9 UNCHANGED)
        assert rows[0]["whip"] == "0.50"  # (1+2)*3 / 18 (WHIP UNCHANGED)

    def test_compute_rates_stored_basis_seven(self):
        rows = [{
            "ip_outs": 21, "er": 3, "so": 6, "bb": 2, "h": 4,
            "pitches": 100, "total_strikes": 60, "innings_per_game": 7,
        }]
        _compute_pitching_rates(rows)
        assert rows[0]["era"] == "3.00"   # 3 * 7*3 / 21

    def test_compute_rates_null_basis_falls_back_to_seven(self):
        rows = [{
            "ip_outs": 18, "er": 2, "so": 5, "bb": 1, "h": 2,
            "pitches": 100, "total_strikes": 60, "innings_per_game": None,
        }]
        _compute_pitching_rates(rows)
        assert rows[0]["era"] == "2.33"   # 2 * 21 / 18 (fallback 7)
        assert rows[0]["k9"] == "7.5"     # unchanged

    def test_compute_rates_missing_key_falls_back_to_seven(self):
        # A row with no innings_per_game key at all is defensively fallback-7.
        rows = [{
            "ip_outs": 21, "er": 3, "so": 6, "bb": 2, "h": 4,
            "pitches": 100, "total_strikes": 60,
        }]
        _compute_pitching_rates(rows)
        assert rows[0]["era"] == "3.00"   # 3 * 21 / 21 (fallback 7)


class TestExtractInningsPerGame:
    """AC-2: robust extraction of the ERA basis from the team-detail payload."""

    def test_happy_path(self):
        data = {"settings": {"scorekeeping": {"bats": {"innings_per_game": 6}}}}
        assert _extract_innings_per_game(data) == 6

    def test_missing_leaf_returns_none(self):
        assert _extract_innings_per_game(
            {"settings": {"scorekeeping": {"bats": {}}}}
        ) is None

    def test_missing_intermediate_returns_none(self):
        assert _extract_innings_per_game({"settings": {}}) is None
        assert _extract_innings_per_game({}) is None

    def test_non_dict_at_any_hop_returns_none(self):
        assert _extract_innings_per_game(None) is None
        assert _extract_innings_per_game("nope") is None
        assert _extract_innings_per_game(
            {"settings": {"scorekeeping": {"bats": "x"}}}
        ) is None

    def test_bool_rejected(self):
        # isinstance(True, int) is True in Python -- a bool must NOT be accepted.
        assert _extract_innings_per_game(
            {"settings": {"scorekeeping": {"bats": {"innings_per_game": True}}}}
        ) is None

    def test_non_int_value_returns_none(self):
        assert _extract_innings_per_game(
            {"settings": {"scorekeeping": {"bats": {"innings_per_game": "6"}}}}
        ) is None


class TestFetchAndStoreInningsPerGame:
    """AC-1/AC-2: post-resolution basis fetch + NULL-safe no-clobber store."""

    def _make_gen(self, team_id, gc_uuid, public_id, name, client):
        gen = _ReportGeneration("https://web.gc.com/o/x/team/abc")
        gen.team_id = team_id
        gen.public_id = public_id
        gen.resolved_gc_uuid = gc_uuid
        gen.team_info = {"name": name}
        gen.client = client
        return gen

    def _conn_factory(self, db_path):
        def _fresh():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn
        return _fresh

    def _seed(self, db, gc_uuid="uuid-1", public_id="pub1", ipg=None):
        cur = db.execute(
            "INSERT INTO teams (name, gc_uuid, public_id, membership_type, "
            "innings_per_game) VALUES ('Test', ?, ?, 'tracked', ?)",
            (gc_uuid, public_id, ipg),
        )
        db.commit()
        return cur.lastrowid

    def _read_ipg(self, db, team_id):
        return db.execute(
            "SELECT innings_per_game FROM teams WHERE id = ?", (team_id,)
        ).fetchone()[0]

    def test_stores_fetched_basis(self, db, tmp_path):
        """AC-1: a resolvable team whose GC exposes the basis -> stored."""
        team_id = self._seed(db, ipg=None)
        db_path = str(tmp_path / "test.db")
        client = MagicMock()
        client.get.return_value = {
            "settings": {"scorekeeping": {"bats": {"innings_per_game": 6}}}
        }
        gen = self._make_gen(team_id, "uuid-1", "pub1", "Test", client)
        with patch(
            "src.reports.generator.get_connection",
            side_effect=self._conn_factory(db_path),
        ):
            gen._fetch_and_store_innings_per_game()
        client.get.assert_called_once_with(
            "/teams/uuid-1", accept=TEAM_DETAIL_ACCEPT
        )
        assert self._read_ipg(db, team_id) == 6

    def test_forbidden_leaves_prior_basis_unchanged(self, db, tmp_path):
        """AC-2: a raised 403 is caught; a prior stored basis is KEPT."""
        team_id = self._seed(db, ipg=7)
        db_path = str(tmp_path / "test.db")
        client = MagicMock()
        client.get.side_effect = ForbiddenError("403")
        gen = self._make_gen(team_id, "uuid-1", "pub1", "Test", client)
        with patch(
            "src.reports.generator.get_connection",
            side_effect=self._conn_factory(db_path),
        ):
            gen._fetch_and_store_innings_per_game()  # must not raise
        assert self._read_ipg(db, team_id) == 7

    def test_forbidden_never_fetched_stays_null(self, db, tmp_path):
        """AC-2: a 403 on a never-fetched team leaves the basis NULL (ERA->7)."""
        team_id = self._seed(db, ipg=None)
        db_path = str(tmp_path / "test.db")
        client = MagicMock()
        client.get.side_effect = ForbiddenError("403")
        gen = self._make_gen(team_id, "uuid-1", "pub1", "Test", client)
        with patch(
            "src.reports.generator.get_connection",
            side_effect=self._conn_factory(db_path),
        ):
            gen._fetch_and_store_innings_per_game()
        assert self._read_ipg(db, team_id) is None

    def test_generic_exception_is_caught(self, db, tmp_path):
        """AC-2: any unexpected fetch failure is non-fatal."""
        team_id = self._seed(db, ipg=None)
        db_path = str(tmp_path / "test.db")
        client = MagicMock()
        client.get.side_effect = RuntimeError("boom")
        gen = self._make_gen(team_id, "uuid-1", "pub1", "Test", client)
        with patch(
            "src.reports.generator.get_connection",
            side_effect=self._conn_factory(db_path),
        ):
            gen._fetch_and_store_innings_per_game()  # must not raise
        assert self._read_ipg(db, team_id) is None

    def test_absent_field_leaves_basis_null(self, db, tmp_path):
        """AC-2: fetch succeeds but the field is absent -> no write."""
        team_id = self._seed(db, ipg=None)
        db_path = str(tmp_path / "test.db")
        client = MagicMock()
        client.get.return_value = {"settings": {}}
        gen = self._make_gen(team_id, "uuid-1", "pub1", "Test", client)
        with patch(
            "src.reports.generator.get_connection",
            side_effect=self._conn_factory(db_path),
        ):
            gen._fetch_and_store_innings_per_game()
        assert self._read_ipg(db, team_id) is None

    def test_no_clobber_of_stored_basis(self, db, tmp_path):
        """AC-2/TN-4: a re-fetch returning a DIFFERENT basis does NOT overwrite
        an already-stored integer (backfill is strictly NULL->value)."""
        team_id = self._seed(db, ipg=6)
        db_path = str(tmp_path / "test.db")
        client = MagicMock()
        client.get.return_value = {
            "settings": {"scorekeeping": {"bats": {"innings_per_game": 9}}}
        }
        gen = self._make_gen(team_id, "uuid-1", "pub1", "Test", client)
        with patch(
            "src.reports.generator.get_connection",
            side_effect=self._conn_factory(db_path),
        ):
            gen._fetch_and_store_innings_per_game()
        assert self._read_ipg(db, team_id) == 6  # retained, not clobbered to 9


# ---------------------------------------------------------------------------
# E-270-03: the destructive path, driven through the REAL generate_report()
# ---------------------------------------------------------------------------
# Report generation became DESTRUCTIVE in E-267 (reconcile-at-load hard-deletes
# across three grains) and again in E-273 (orphan reclamation), yet every other
# test in this file stubs the crawler or the loader and therefore cannot see it.
# This class drives ``generate_report()`` itself, twice, with only the HTTP
# TRANSPORT faked -- so ``GameChangerClient``, ``ScoutingCrawler``,
# ``ScoutingLoader``, ``ensure_team_row_with_provenance`` and all three retire
# helpers are the real thing.
#
# The seam is respx (transport-level), NOT a fake ``GameChangerClient``. See the
# class docstring for why that deviates from the story's TN-6 in the
# strictly-more-real direction, and what it cost.


class _RecordingSpy:
    """Call-through wrapper that records each RETURN value.

    ``unittest.mock`` records arguments but not per-call return values, and the
    attribution this story needs (E-270-03 AC-6) is entirely about what each
    retire helper REPORTED it removed. Behavior is unchanged -- the real callable
    runs and its result is passed straight back.
    """

    def __init__(self, real):
        self._real = real
        self.results: list = []
        #: Per-call keyword arguments, parallel to ``results``. Needed by
        #: E-276-04, which must know WHICH game each player-line call was for --
        #: the result object carries no game id. Additive: nothing that predates
        #: it reads this.
        self.calls: list[dict] = []

    def __call__(self, *args, **kwargs):
        result = self._real(*args, **kwargs)
        self.results.append(result)
        self.calls.append(kwargs)
        return result

    def reset(self) -> None:
        self.results.clear()
        self.calls.clear()


class TestGenerateReportDestructiveReconcile:
    """AC-1..AC-6: two real generations, the second one shrunk, over a real DB.

    **Seam (deviation from TN-6, deliberate).** TN-6 prescribes patching
    ``src.reports.generator.GameChangerClient`` with a hand-built fake and
    sourcing payloads from ``data/raw/``. Neither is used here:

    * ``data/raw/`` is gitignored and does NOT exist in an epic worktree, so it
      cannot be a payload source. ``tests/fixtures/e2e/`` holds the same
      payloads, committed and anonymized, and is already the source of truth for
      ``tests/test_report_e2e.py``.
    * Given committed real-shape payloads, faking the HTTP transport (respx)
      keeps strictly MORE of the pipeline real than faking the client --
      ``GameChangerClient`` itself, its URL construction, and its response
      parsing all stay live. TN-6's keep-real set is a subset of this one, so
      the deviation cannot weaken the test; it only removes the hand-built fake
      that TN-6 itself calls "the single largest effort item in the epic".

    **Why the payloads are extended, not used as-is.** The committed fixture has
    2 completed games; AC-4's sizing needs >= 4 so that dropping one clears
    ``FLOOR_RATIO``. The two extra games REUSE a real fixture boxscore verbatim
    under a new game id and date, so every payload the crawler parses keeps a
    real GameChanger shape -- the property TN-6 actually cares about, since a
    parse failure aborts before the reconcile and leaves a green, worthless
    test. The roster gains ONE synthetic entry (same shape) that appears in no
    boxscore; see ``_roster``.

    **Attribution (AC-6) is positive AND negative.** ``generate_report`` now runs
    two independent hard-deleting passes, so "the rows are gone" identifies no
    culprit. Both directions are asserted: each retire helper is spied and must
    REPORT the specific id it retired, and the E-273 reclamation is spied and
    must have run (``deferred is False``) while deleting nothing.
    """

    _E2E_DIR = Path(__file__).resolve().parent / "fixtures" / "e2e"
    _PUBLIC_ID = "ExampleTm001"
    _OWN_KEY = "ExampleTm001"
    _BASE = "https://api.team-manager.gc.com"

    # The two committed games, then two clones of the second. Distinct dates and
    # opponents keep GameLoader's date+team-pair dedup from collapsing them.
    #
    # The synthetic ids below keep the committed fixture's ALL-NUMERIC final
    # segment, and that is not cosmetic. An earlier draft ended that segment
    # with two hex letters after ten zeros, which isolates a run of exactly ten
    # digits bounded by non-digits -- precisely the ``us_phone`` shape
    # ``src/safety/pii_scanner.py`` blocks, and it blocked this file's commit.
    # Twelve digits is safe because every ten-digit window inside it is bounded
    # by another digit. Keep that segment all-numeric when adding ids here (and
    # note that writing an offending id in a COMMENT trips the scanner too --
    # describe the shape rather than quoting one).
    _GAME_A = "00000000-0000-4000-8000-000000000002"
    _GAME_B = "00000000-0000-4000-8000-000000000004"
    _GAME_C = "00000000-0000-4000-8000-000000000901"
    _GAME_D = "00000000-0000-4000-8000-000000000902"

    #: Dropped from the schedule on run 2 -> game-grain retire.
    _DROPPED_GAME = _GAME_D
    #: Roster-only player (in no boxscore), dropped on run 2 -> roster retire.
    _ROSTER_ONLY_PLAYER = "00000000-0000-4000-8000-000000000903"

    def _load(self, name: str):
        import json

        return json.loads((self._E2E_DIR / name).read_text(encoding="utf-8"))

    # -- payload builders -------------------------------------------------

    def _schedule(self, *, drop_game: str | None = None) -> list[dict]:
        """The FULL schedule array: 4 completed games (AC-4 sizing)."""
        base = self._load("public_team_games.json")
        clone_src = base[1]
        extra = []
        for gid, day, opp in (
            (self._GAME_C, "2026-04-02", "Example Opponent Three"),
            (self._GAME_D, "2026-04-09", "Example Opponent Four"),
        ):
            g = dict(clone_src)
            g["id"] = gid
            g["start_ts"] = f"{day}T21:30:00.000Z"
            g["end_ts"] = f"{day}T22:30:00.000Z"
            g["opponent_team"] = {"name": opp, "avatar_url": ""}
            extra.append(g)
        games = [*base, *extra]
        if drop_game is not None:
            games = [g for g in games if g["id"] != drop_game]
        return games

    def _boxscore(self, game_id: str, *, drop_player: str | None = None) -> dict:
        """One game's boxscore; ``drop_player`` removes that player's stat rows.

        Only the ``stats`` entries are removed, not the ``players`` roster of the
        block -- that is exactly the shape GameChanger produces when a player
        stops appearing in a game's line, and it is what the player-line grain
        diffs against.
        """
        src = self._GAME_A if game_id == self._GAME_A else self._GAME_B
        payload = self._load(f"boxscore_{src}.json")
        if drop_player is None:
            return payload
        block = payload[self._OWN_KEY]
        for group in block.get("groups", []):
            group["stats"] = [
                s for s in group.get("stats", []) if s.get("player_id") != drop_player
            ]
            group["extra"] = [
                s for s in group.get("extra", []) if s.get("player_id") != drop_player
            ]
        return payload

    def _roster(self, *, drop_player: str | None = None) -> list[dict]:
        """Committed roster (17) PLUS one synthetic roster-only player.

        The synthetic entry is the one dropped on run 2. It deliberately appears
        in NO boxscore: every committed roster player does appear in one, so
        dropping any of them would be re-created by the jersey backfill and
        retired again as CHURN on every run. A player who was only ever on the
        roster is an unambiguous DEPARTURE, which is the case this grain exists
        for and the one an operator would recognise.
        """
        roster = list(self._load("roster_players.json"))
        roster.append(
            {
                "id": self._ROSTER_ONLY_PLAYER,
                "first_name": "Roster",
                "last_name": "Only",
                "number": "99",
                "avatar_url": "",
            }
        )
        if drop_player is not None:
            roster = [p for p in roster if p["id"] != drop_player]
        return roster

    def _first_player_with_stats(self, game_id: str) -> str:
        """A player id carrying real stat rows in ``game_id``'s own-team block."""
        block = self._boxscore(game_id)[self._OWN_KEY]
        for group in block.get("groups", []):
            if group.get("category") == "lineup":
                ids = [s["player_id"] for s in group.get("stats", [])]
                assert len(ids) >= 3, (
                    "AC-4 requires the still-present game's block to carry >= 3 "
                    f"player lines; fixture has {len(ids)}"
                )
                return ids[0]
        raise AssertionError("no lineup group in the fixture boxscore")

    def _churn_map(self, game_id: str) -> dict[str, str]:
        """``{original player_id: brand-new player_id}`` for one game's own block.

        The replacements keep the committed fixture's ALL-NUMERIC 12-digit final
        segment, for the PII-scanner reason documented at the game ids above, and
        start well clear of the synthetic ids already in use.
        """
        block = self._boxscore(game_id)[self._OWN_KEY]
        originals = sorted(
            {
                stat["player_id"]
                for group in block.get("groups", [])
                for stat in group.get("stats", [])
                if stat.get("player_id")
            }
        )
        return {
            pid: f"00000000-0000-4000-8000-{910 + i:012d}"
            for i, pid in enumerate(originals)
        }

    def _boxscore_with_churn(self, game_id: str) -> dict:
        """The same game, with every own-block player id RE-ISSUED.

        This is the shape the subset-shaped scenario structurally cannot produce:
        run 2 introduces ids that were never in run 1, so the post-upsert prior
        set is strictly larger than the pre-upsert one and the two gate
        populations diverge. Dropping players can never do that.

        **Names are re-derived, not carried over.** Re-using the committed names
        would give each churn id a matching last name and an identical first
        name, which ``dedup_team_players`` merges -- and the test would then be
        measuring the dedup sweep rather than the reconcile.
        """
        payload = self._boxscore(game_id)
        mapping = self._churn_map(game_id)
        block = payload[self._OWN_KEY]
        for entry in block.get("players", []):
            new_id = mapping.get(entry.get("id"))
            if new_id:
                entry["id"] = new_id
                entry["first_name"] = f"Churn{new_id[-4:]}"
                entry["last_name"] = f"Reissued{new_id[-4:]}"
        for group in block.get("groups", []):
            for bucket in ("stats", "extra"):
                for stat in group.get(bucket, []):
                    new_id = mapping.get(stat.get("player_id"))
                    if new_id:
                        stat["player_id"] = new_id
        return payload

    # -- transport --------------------------------------------------------

    def _register(self, router, state: dict) -> None:
        """Serve every endpoint the live pipeline touches, per crawl phase.

        Routes read ``state['shrunk']`` at REQUEST time, which is what makes the
        two successive ``generate_report()`` calls see different payloads through
        one router.
        """
        import httpx

        def _json(builder):
            def _responder(request):  # noqa: ARG001
                return httpx.Response(200, json=builder())

            return _responder

        router.get(f"{self._BASE}/public/teams/{self._PUBLIC_ID}").mock(
            side_effect=_json(lambda: self._load("public_team_profile.json"))
        )
        router.get(f"{self._BASE}/public/teams/{self._PUBLIC_ID}/games").mock(
            side_effect=_json(
                lambda: self._schedule(
                    drop_game=self._DROPPED_GAME if state["shrunk"] else None
                )
            )
        )
        router.get(f"{self._BASE}/teams/public/{self._PUBLIC_ID}/players").mock(
            side_effect=_json(
                lambda: self._roster(
                    drop_player=(
                        self._ROSTER_ONLY_PLAYER if state["shrunk"] else None
                    )
                )
            )
        )
        # POST /search: zero hits is fine and keeps the non-fatal gc_uuid-resolve
        # path live rather than patching the stage out (TN-6).
        router.post(url__startswith=f"{self._BASE}/search").mock(
            side_effect=_json(lambda: {"hits": {"hits": []}})
        )
        for gid in (self._GAME_A, self._GAME_B, self._GAME_C, self._GAME_D):
            router.get(
                f"{self._BASE}/game-stream-processing/{gid}/boxscore"
            ).mock(
                side_effect=_json(
                    lambda gid=gid: (
                        self._boxscore_with_churn(gid)
                        if state.get("churn") and gid == self._GAME_A
                        else self._boxscore(
                            gid,
                            drop_player=(
                                state["dropped_line_player"]
                                if state["shrunk"] and gid == self._GAME_A
                                else None
                            ),
                        )
                    )
                )
            )

    # -- DB helpers -------------------------------------------------------

    @staticmethod
    def _rows(conn_factory, sql: str, params: tuple = ()) -> list[tuple]:
        conn = conn_factory()
        try:
            return list(conn.execute(sql, params))
        finally:
            conn.close()

    def _subject_team_id(self, conn_factory) -> int:
        """The ``teams.id`` the pipeline created for our ``public_id``.

        Every set-equality assertion below is scoped to THIS team, because all
        three retire helpers are team-scoped. An unscoped query also sweeps in
        the opponent teams and their backfilled roster/line rows, which move for
        reasons that have nothing to do with the grain under test -- e.g.
        retiring game D leaves that opponent's own rows behind by design.
        """
        rows = self._rows(
            conn_factory, "SELECT id FROM teams WHERE public_id = ?", (self._PUBLIC_ID,)
        )
        assert len(rows) == 1, f"expected exactly one subject team row, got {rows}"
        return rows[0][0]

    def _game_ids(self, conn_factory) -> set[str]:
        return {r[0] for r in self._rows(conn_factory, "SELECT game_id FROM games")}

    def _roster_player_ids(self, conn_factory) -> set[str]:
        return {
            r[0]
            for r in self._rows(
                conn_factory,
                "SELECT player_id FROM team_rosters WHERE team_id = ?",
                (self._subject_team_id(conn_factory),),
            )
        }

    def _batting_player_ids(self, conn_factory, game_id: str) -> set[str]:
        return {
            r[0]
            for r in self._rows(
                conn_factory,
                "SELECT player_id FROM player_game_batting "
                "WHERE game_id = ? AND team_id = ?",
                (game_id, self._subject_team_id(conn_factory)),
            )
        }

    def test_second_shrunk_generation_retires_all_three_grains_and_still_renders(
        self, tmp_path, monkeypatch
    ):
        """AC-1..AC-6 in one run: two real generations, three real retires."""
        import sqlite3 as _sqlite3

        import respx

        from src.db import reconcile_at_load as _recon
        from src.gamechanger.loaders import game_loader as _game_loader
        from src.reports import lifecycle as _lifecycle
        from src.reports.renderer import render_report as _real_render

        # -- real disk-backed DB, production schema ----------------------
        db_path = str(tmp_path / "test.db")
        seed = _sqlite3.connect(db_path)
        load_real_schema(seed)
        seed.commit()
        seed.close()

        def _conn_factory():
            c = _sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        # NOTE (TN-6 E-273 item 2): nothing is pre-seeded. A bare
        # ``membership_type='tracked'`` team with no report and no games is an
        # ORPHAN by E-273's predicate and would be swept at run-1 start. Letting
        # the real pipeline create every row avoids that by construction.

        monkeypatch.setenv("GAMECHANGER_BASE_URL", self._BASE)
        monkeypatch.setenv("GAMECHANGER_REFRESH_TOKEN_WEB", "fake-refresh")
        monkeypatch.setenv("GAMECHANGER_CLIENT_ID_WEB", "fake-client-id")
        monkeypatch.setenv("GAMECHANGER_CLIENT_KEY_WEB", "fake-client-key")
        monkeypatch.setenv("GAMECHANGER_DEVICE_ID_WEB", "fake-device-id")
        monkeypatch.delenv("PROXY_ENABLED", raising=False)

        dropped_line_player = self._first_player_with_stats(self._GAME_A)
        state = {"shrunk": False, "dropped_line_player": dropped_line_player}
        rendered: list[dict] = []

        spy_game = _RecordingSpy(_recon.retire_absent_games)
        spy_roster = _RecordingSpy(_recon.retire_departed_roster_players)
        spy_lines = _RecordingSpy(_recon.retire_absent_player_lines)
        spy_reclaim = _RecordingSpy(_lifecycle.reclaim_orphan_reference_data)

        def _capturing_render(data):
            rendered.append(data)
            return _real_render(data)

        with respx.mock(assert_all_called=False) as router:
            self._register(router, state)
            with (
                patch(
                    "src.gamechanger.token_manager.TokenManager.get_access_token",
                    return_value="fake-token-e270",
                ),
                patch("src.http.session.time.sleep", return_value=None),
                patch("src.reports.generator.get_connection", side_effect=_conn_factory),
                patch("src.api.db.get_connection", side_effect=_conn_factory),
                patch(
                    "src.reports.generator.render_report",
                    side_effect=_capturing_render,
                ),
                patch("src.reports.generator._REPO_ROOT", tmp_path),
                patch(
                    "src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"
                ),
                # Out of scope per TN-6; they need plays/spray payloads this
                # fixture does not carry.
                patch(
                    "src.reports.generator._crawl_and_load_spray", return_value=None
                ),
                patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
                # -- attribution spies (AC-6). Call-through: behavior unchanged.
                patch.object(_recon, "retire_absent_games", spy_game),
                patch.object(
                    _recon, "retire_departed_roster_players", spy_roster
                ),
                # game_loader imports this at MODULE level, so patching the
                # reconcile_at_load attribute would NOT be seen there.
                patch.object(
                    _game_loader, "retire_absent_player_lines", spy_lines
                ),
                patch.object(
                    _lifecycle, "reclaim_orphan_reference_data", spy_reclaim
                ),
            ):
                from src.reports.generator import generate_report

                # ---- RUN 1: the full crawl -------------------------------
                result_one = generate_report(self._PUBLIC_ID)
                assert result_one.success is True, result_one.error_message

                games_after_one = self._game_ids(_conn_factory)
                roster_after_one = self._roster_player_ids(_conn_factory)
                lines_after_one = self._batting_player_ids(_conn_factory, self._GAME_A)

                # The fixture actually loaded -- if the real crawler had failed
                # to PARSE these payloads the pipeline would abort here and
                # every assertion below would pass vacuously against an empty
                # prior set (TN-6's silent-defeat mode).
                assert len(games_after_one) == 4, games_after_one
                assert self._DROPPED_GAME in games_after_one
                assert self._ROSTER_ONLY_PLAYER in roster_after_one
                assert dropped_line_player in lines_after_one
                assert len(lines_after_one) >= 3, lines_after_one
                # Every boxscore PARSED, not just the schedule: each of the four
                # games carries real stat rows. A boxscore the crawler could not
                # parse is skipped silently, which would leave this grain with
                # nothing to diff on run 2 and make AC-2 pass for the wrong
                # reason.
                for gid in games_after_one:
                    assert self._batting_player_ids(_conn_factory, gid), (
                        f"game {gid} loaded no batting lines -- its boxscore did "
                        "not parse, so the fixture is not exercising the pipeline"
                    )

                spy_game.reset()
                spy_roster.reset()
                spy_lines.reset()
                spy_reclaim.reset()

                # ---- RUN 2: the shrunk crawl -----------------------------
                state["shrunk"] = True
                result_two = generate_report(self._PUBLIC_ID)

        # ---- AC-3: the destructive re-run still produces a report --------
        assert result_two.success is True, result_two.error_message
        assert result_two.outcome == "ready"
        assert len(rendered) == 2, "render_report did not run on both generations"
        report_files = list((tmp_path / "data" / "reports").glob("*.html"))
        assert report_files, "no report HTML was written"
        # ``all``, not ``any``: with ``any`` a run-2 render that produced an
        # EMPTY file would still pass on the strength of run 1's file -- the
        # "passes for the wrong reason" shape this whole test exists to remove.
        assert all(f.stat().st_size > 0 for f in report_files), [
            (f.name, f.stat().st_size) for f in report_files
        ]

        # ---- AC-2: every grain's rows are GONE ---------------------------
        games_after_two = self._game_ids(_conn_factory)
        roster_after_two = self._roster_player_ids(_conn_factory)
        lines_after_two = self._batting_player_ids(_conn_factory, self._GAME_A)

        assert self._DROPPED_GAME not in games_after_two, "game-grain retire did not fire"
        assert games_after_two == games_after_one - {self._DROPPED_GAME}
        assert self._ROSTER_ONLY_PLAYER not in roster_after_two, (
            "roster-grain retire did not fire"
        )
        assert dropped_line_player not in lines_after_two, (
            "player-line-grain retire did not fire"
        )
        # Only the dropped entries went -- a retire that took the neighbours
        # would also satisfy the three assertions above.
        assert roster_after_two == roster_after_one - {self._ROSTER_ONLY_PLAYER}
        assert lines_after_two == lines_after_one - {dropped_line_player}

        # The retired game's child surface went with it (whole-game delete).
        assert not self._rows(
            _conn_factory,
            "SELECT 1 FROM player_game_batting WHERE game_id = ?",
            (self._DROPPED_GAME,),
        )
        assert not self._rows(
            _conn_factory,
            "SELECT 1 FROM game_perspectives WHERE game_id = ?",
            (self._DROPPED_GAME,),
        )

        # ---- AC-6: attribute the deletions to the RETIRE ------------------
        # Positive: each grain's helper REPORTS the id it retired. Absence of a
        # row is not attribution when two hard-deleting passes are in play.
        assert spy_game.results, "the game-grain retire helper was never called"
        game_retired = [
            gid for r in spy_game.results for gid in r.retired_game_ids
        ]
        assert game_retired == [self._DROPPED_GAME], game_retired

        assert spy_roster.results, "the roster-grain retire helper was never called"
        roster_retired = [
            pid for r in spy_roster.results for pid in r.retired_player_ids
        ]
        assert roster_retired == [self._ROSTER_ONLY_PLAYER], roster_retired

        assert spy_lines.results, "the player-line retire helper was never called"
        line_retired = [
            pid
            for r in spy_lines.results
            for ids in r.retired.values()
            for pid in ids
        ]
        assert line_retired == [dropped_line_player], line_retired

        # Negative: the OTHER destructive pass ran and took nothing. ``deferred``
        # must be False -- a deferred sweep also deletes nothing, so without this
        # the negative half would pass while proving only that the reclamation
        # never actually ran.
        #
        # WHY THIS IS NOT A TAUTOLOGY, and the seam that keeps it honest: the
        # reclamation only sees the temp DB because ``generate_report`` resolves
        # ``get_connection`` in the GENERATOR namespace and passes that borrowed
        # connection in (``generator.py:1518``). ``lifecycle.py:32`` imports
        # ``get_connection`` at MODULE level, so patching ``src.api.db`` -- which
        # this test also does -- would NOT rebind it. If a future edit makes
        # ``cleanup_expired_reports`` or the reclamation open its OWN connection,
        # this block silently stops proving attribution: it would run against the
        # real ``data/app.db``, find nothing orphaned, and report exactly the
        # ``deferred=False`` / ``(0, 0, 0)`` asserted here -- passing, with no
        # failing test anywhere to signal the degradation.
        assert spy_reclaim.results, "the E-273 reclamation never ran on run 2"
        for reclaim_result in spy_reclaim.results:
            assert reclaim_result.deferred is False, (
                "reclamation was deferred -- it did not actually run, so it "
                "cannot be exonerated as the deleter"
            )
            assert (
                reclaim_result.teams_deleted,
                reclaim_result.players_deleted,
                reclaim_result.roster_rows_deleted,
            ) == (0, 0, 0), reclaim_result

    def test_second_generation_that_RE_ISSUES_player_ids_retires_nothing(
        self, tmp_path, monkeypatch
    ):
        """E-276-04: the churn shape, at the seam where the defect reached live data.

        The sibling above drives a run 2 that is a strict SUBSET of run 1 -- it
        drops a game, a roster player and a line player. That is why the class
        was passing for the right reason and still could not see this defect:
        with no new ids, the post-upsert prior set EQUALS the pre-upsert one and
        both gate populations agree. **Dropping players can never produce the
        divergence; only re-issuing ids can.**

        Here run 2 re-issues every own-block player id for one game. The gate's
        protected population is the pre-upsert snapshot, whose overlap with the
        fresh block is zero, so the grain REFUSES and the prior lines survive.

        Pre-fix the same input hard-deletes them: the live population is twice
        the block with an overlap of exactly half, which clears the floor at
        equality and permits.

        **⚠️ Assertion steer INVERTS here (TN-18).** There is no structural
        retire record at ``generate_report()`` level, so a seam spy is the only
        positive signal separating a genuine refusal from *the reconcile never
        running for that game* -- and "the rows survived" is satisfied by both.
        The E-244 redirect footgun makes the never-ran case live rather than
        theoretical. A clean result object rules out the blew-up case only.
        """
        import sqlite3 as _sqlite3

        import respx

        from src.db import reconcile_at_load as _recon
        from src.gamechanger.loaders import game_loader as _game_loader
        from src.reports import lifecycle as _lifecycle
        from src.reports.renderer import render_report as _real_render

        db_path = str(tmp_path / "test.db")
        seed = _sqlite3.connect(db_path)
        load_real_schema(seed)
        seed.commit()
        seed.close()

        def _conn_factory():
            c = _sqlite3.connect(db_path)
            c.execute("PRAGMA foreign_keys=ON;")
            return c

        monkeypatch.setenv("GAMECHANGER_BASE_URL", self._BASE)
        monkeypatch.setenv("GAMECHANGER_REFRESH_TOKEN_WEB", "fake-refresh")
        monkeypatch.setenv("GAMECHANGER_CLIENT_ID_WEB", "fake-client-id")
        monkeypatch.setenv("GAMECHANGER_CLIENT_KEY_WEB", "fake-client-key")
        monkeypatch.setenv("GAMECHANGER_DEVICE_ID_WEB", "fake-device-id")
        monkeypatch.delenv("PROXY_ENABLED", raising=False)

        # Neither shrink flag is set: the schedule and roster are unchanged
        # across both runs, so ONLY the player-line grain is exercised and a
        # surviving line cannot be explained by some other pass declining.
        state = {"shrunk": False, "dropped_line_player": None, "churn": False}
        rendered: list[dict] = []
        spy_lines = _RecordingSpy(_recon.retire_absent_player_lines)
        spy_reclaim = _RecordingSpy(_lifecycle.reclaim_orphan_reference_data)

        def _capturing_render(data):
            rendered.append(data)
            return _real_render(data)

        with respx.mock(assert_all_called=False) as router:
            self._register(router, state)
            with (
                patch(
                    "src.gamechanger.token_manager.TokenManager.get_access_token",
                    return_value="fake-token-e276",
                ),
                patch("src.http.session.time.sleep", return_value=None),
                patch("src.reports.generator.get_connection", side_effect=_conn_factory),
                patch("src.api.db.get_connection", side_effect=_conn_factory),
                patch(
                    "src.reports.generator.render_report",
                    side_effect=_capturing_render,
                ),
                patch("src.reports.generator._REPO_ROOT", tmp_path),
                patch(
                    "src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"
                ),
                patch(
                    "src.reports.generator._crawl_and_load_spray", return_value=None
                ),
                patch("src.reports.generator._crawl_and_load_plays", return_value=[]),
                # MODULE-level import in game_loader, so patching the
                # reconcile_at_load attribute would NOT be seen at the call site.
                patch.object(
                    _game_loader, "retire_absent_player_lines", spy_lines
                ),
                patch.object(
                    _lifecycle, "reclaim_orphan_reference_data", spy_reclaim
                ),
            ):
                from src.reports.generator import generate_report

                result_one = generate_report(self._PUBLIC_ID)
                assert result_one.success is True, result_one.error_message

                lines_after_one = self._batting_player_ids(_conn_factory, self._GAME_A)
                # The fixture actually loaded. Without this the run-2 assertions
                # pass vacuously against an empty prior set -- the silent-defeat
                # mode this class's docstring names.
                assert len(lines_after_one) >= 3, lines_after_one

                churn_map = self._churn_map(self._GAME_A)
                # The map spans the whole own block (lineup AND pitching); the
                # batting table holds only the batters, so COVERAGE is the
                # property, not equality. A pitcher who never batted is in the
                # map and legitimately absent here.
                assert lines_after_one <= set(churn_map), (
                    "the churn map does not cover every loaded batting line, so "
                    "run 2 would not be a TOTAL re-issue for this grain"
                )
                assert not (set(churn_map.values()) & lines_after_one), (
                    "the re-issued ids must be genuinely new"
                )
                churned_batters = {churn_map[pid] for pid in lines_after_one}

                spy_lines.reset()
                spy_reclaim.reset()

                state["churn"] = True
                result_two = generate_report(self._PUBLIC_ID)

        # AC-2: a refusal, not a pipeline failure -- it still renders.
        assert result_two.success is True, result_two.error_message
        assert result_two.outcome == "ready"
        assert len(rendered) == 2, "render_report did not run on both generations"

        # AC-2 positive signal: the reconcile RAN for this game and REFUSED.
        # "The rows survived" alone is satisfied by a reconcile that never ran.
        game_a_calls = [
            (kwargs, result)
            for kwargs, result in zip(spy_lines.calls, spy_lines.results, strict=True)
            if kwargs.get("game_id") == self._GAME_A
        ]
        assert game_a_calls, (
            "the player-line reconcile never ran for the churned game -- the "
            "E-244 redirect footgun makes this a live alternative, and it "
            "produces the same surviving rows as a genuine refusal"
        )
        for _kwargs, result in game_a_calls:
            assert result.retired == {}, f"lines were retired: {result.retired}"
            assert result.refusals, "the grain neither retired nor refused"

        # AC-1: the prior lines SURVIVE, and the re-issued ids landed beside
        # them. Pre-fix the originals are hard-deleted and this set equality
        # fails.
        lines_after_two = self._batting_player_ids(_conn_factory, self._GAME_A)
        assert lines_after_one <= lines_after_two, (
            "prior lines were hard-deleted by a re-issued id churn -- the gate "
            "measured the post-upsert population"
        )
        assert lines_after_two == lines_after_one | churned_batters

        # The other destructive pass ran and took nothing, so it cannot be
        # mistaken for the reason the lines are still here.
        assert spy_reclaim.results, "the E-273 reclamation never ran on run 2"
        for reclaim_result in spy_reclaim.results:
            assert reclaim_result.deferred is False

