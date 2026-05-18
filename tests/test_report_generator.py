"""Tests for the report generation pipeline (E-172-02, E-176-02, E-185-01)."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
from src.reports.generator import (
    GenerationResult,
    cascade_delete_team,
    cleanup_orphan_teams,
    _crawl_and_load_spray,
    _create_report_row,
    _query_batting,
    _query_freshness,
    _query_pitching,
    _query_recent_games,
    _query_record,
    _query_roster,
    _query_runs_avg,
    _resolve_gc_uuid,
    _snapshot_team_ids,
    _update_report_failed,
    _update_report_ready,
    generate_report,
    list_reports,
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


def _seed_season(db, season_id="2026-spring-hs"):
    db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, 'spring', 2026)",
        (season_id, season_id),
    )
    db.commit()


def _seed_player(db, player_id="p1", first="John", last="Smith"):
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first, last),
    )
    db.commit()


def _seed_roster(db, team_id, player_id="p1", season_id="2026-spring-hs", jersey="12"):
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) VALUES (?, ?, ?, ?)",
        (team_id, player_id, season_id, jersey),
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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
# E-199: Plays-stage auth expiry is non-fatal
# ---------------------------------------------------------------------------


class TestPlaysStageAuthExpiry:
    """AC-5: Auth expiry during plays stage does not fail the report."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        # Plays stage raises CredentialExpiredError
        mock_plays.side_effect = CredentialExpiredError("token expired")

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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    def test_credential_expired_sets_failed(
        self, mock_ensure, mock_client_cls, mock_get_conn, db, tmp_path
    ):
        """AC-8: CredentialExpiredError produces a clear error message."""
        from src.gamechanger.client import CredentialExpiredError

        _seed_team(db)

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
            ("g1", "2026-spring-hs", team_id, opp_id, 5, 3, "2026-03-20"),
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026-spring-hs", opp_id, team_id, 3, 7, "2026-03-21"),
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g3", "2026-spring-hs", team_id, opp_id, 2, 4, "2026-03-22"),
        )
        db.commit()

        record = _query_record(db, team_id, "2026-spring-hs")
        assert record is not None
        assert record["wins"] == 2
        assert record["losses"] == 1

    def test_query_recent_games(self, db):
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        for i in range(7):
            db.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"g{i}", "2026-spring-hs", team_id, opp_id, 5 + i, 3, f"2026-03-{20+i:02d}"),
            )
        db.commit()

        games = _query_recent_games(db, team_id, "2026-spring-hs", limit=5)
        assert len(games) == 5
        assert games[0]["result"] == "W"

    def test_query_freshness(self, db):
        team_id = _seed_team(db)
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026-spring-hs", team_id, opp_id, 5, 3, "2026-03-25"),
        )
        db.commit()

        date, count = _query_freshness(db, team_id, "2026-spring-hs")
        assert date == "2026-03-25"
        assert count == 1

    def test_query_batting(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p1", "Jane", "Doe")
        _seed_roster(db, team_id, "p1", "2026-spring-hs", "7")
        db.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb, hbp, shf) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p1", team_id, "2026-spring-hs", 10, 30, 10, 2, 1, 1, 5, 3, 8, 2, 1, 0),
        )
        db.commit()

        db.row_factory = sqlite3.Row
        batting = _query_batting(db, team_id, "2026-spring-hs")
        assert len(batting) == 1
        assert batting[0]["name"] == "Jane Doe"
        assert batting[0]["ab"] == 30
        assert batting[0]["jersey_number"] == "7"

    def test_query_pitching_with_rates(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p2", "John", "Smith")
        _seed_roster(db, team_id, "p2", "2026-spring-hs", "12")
        db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, pitches, total_strikes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p2", team_id, "2026-spring-hs", 5, 45, 20, 8, 10, 30, 300, 180),
        )
        db.commit()

        db.row_factory = sqlite3.Row
        pitching = _query_pitching(db, team_id, "2026-spring-hs")
        assert len(pitching) == 1
        assert pitching[0]["name"] == "John Smith"
        # Rate fields should be computed
        assert "era" in pitching[0]
        assert "k9" in pitching[0]
        assert "whip" in pitching[0]
        assert "strike_pct" in pitching[0]
        # ERA = (8 * 27) / 45 = 4.80
        assert pitching[0]["era"] == "4.80"

    def test_query_roster(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p1", "Jane", "Doe")
        _seed_roster(db, team_id, "p1", "2026-spring-hs", "7")

        db.row_factory = sqlite3.Row
        roster = _query_roster(db, team_id, "2026-spring-hs")
        assert len(roster) == 1
        assert roster[0]["name"] == "Jane Doe"
        assert roster[0]["jersey_number"] == "7"


# ---------------------------------------------------------------------------
# list_reports function
# ---------------------------------------------------------------------------


class TestListReportsFunction:
    """Test the list_reports query function."""

    @patch("src.reports.generator.get_connection")
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
        """Happy path: crawler.crawl_team + loader.load_all are called."""
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

        _crawl_and_load_spray(client, "abc123", "2026-spring-hs")

        mock_crawler.crawl_team.assert_called_once_with(
            "abc123", season_id="2026-spring-hs", gc_uuid=None,
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
            _crawl_and_load_spray(client, "abc123", "2026-spring-hs")

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
        _crawl_and_load_spray(client, "abc123", "2026-spring-hs")

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

        _crawl_and_load_spray(client, "abc123", "2026-spring-hs", gc_uuid="resolved-uuid")

        mock_crawler.crawl_team.assert_called_once_with(
            "abc123", season_id="2026-spring-hs", gc_uuid="resolved-uuid",
            games_data=None,
        )


# ===========================================================================
# E-186-02: gc_uuid resolution via POST /search
# ===========================================================================


class TestResolveGcUuid:
    """Test _resolve_gc_uuid function."""

    def test_successful_resolution_returns_gc_uuid(self):
        """AC-1: Search returns a hit matching public_id -> returns result.id."""
        client = MagicMock()
        client.post_json.return_value = {
            "hits": [
                {
                    "result": {
                        "id": "resolved-gc-uuid-123",
                        "public_id": "my-team-slug",
                        "name": "Test Team",
                    }
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
                {"result": {"id": "target-uuid", "public_id": "target-slug"}}
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
            "result": {
                "id": "ac053e2c-ee27-4f55-9b16-ed77c1bdfebb",
                "public_id": "yecaUcoSVpJa",
                "name": "Lincoln Northwest JV/Reserve Falcons",
            }
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
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2026-spring-hs', '2026 Spring HS', 'spring-hs', 2026)"
        )
        conn_template.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        conn_template.commit()
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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.GameChangerClient", return_value=mock_client),
            patch("src.reports.generator.ensure_team_row", return_value=1),
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
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, gp, ab, h, bb, hbp, shf) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p1", team_id, "2026-spring-hs", 10, 50, 15, 10, 2, 1),  # PA=63
        )
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, gp, ab, h, bb, hbp, shf) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p2", team_id, "2026-spring-hs", 10, 20, 8, 3, 0, 0),  # PA=23
        )
        db.commit()
        db.row_factory = sqlite3.Row
        batting = _query_batting(db, team_id, "2026-spring-hs")
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
        db.execute(
            "INSERT INTO player_season_pitching "
            "(player_id, team_id, season_id, gp_pitcher, ip_outs, er, so, bb, h, pitches, total_strikes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p1", team_id, "2026-spring-hs", 8, 60, 5, 40, 10, 20, 400, 250),
        )
        db.execute(
            "INSERT INTO player_season_pitching "
            "(player_id, team_id, season_id, gp_pitcher, ip_outs, er, so, bb, h, pitches, total_strikes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("p2", team_id, "2026-spring-hs", 5, 30, 3, 15, 8, 12, 200, 120),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        pitching = _query_pitching(db, team_id, "2026-spring-hs")
        assert len(pitching) == 2
        assert pitching[0]["name"] == "Ace Pitcher"  # 60 outs first
        assert pitching[1]["name"] == "Relief Pitcher"  # 30 outs second


class TestBattingCSColumn:
    """AC-1: Batting query includes CS."""

    def test_batting_includes_cs(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        _seed_player(db, "p1", "Jane", "Doe")
        db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, gp, ab, h, sb, cs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("p1", team_id, "2026-spring-hs", 10, 30, 10, 5, 3),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        batting = _query_batting(db, team_id, "2026-spring-hs")
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
            ("g1", "2026-spring-hs", team_id, opp_id, 7, 3, "2026-03-25"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        games = _query_recent_games(db, team_id, "2026-spring-hs")
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
            ("g1", "2026-spring-hs", opp_id, team_id, 3, 7, "2026-03-25"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        games = _query_recent_games(db, team_id, "2026-spring-hs")
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
            ("g1", "2026-spring-hs", team_id, opp_id, 5, 2, "2026-03-25"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        games = _query_recent_games(db, team_id, "2026-spring-hs")
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
            ("g1", "2026-spring-hs", team_id, opp_id, 7, 3, "2026-03-20"),
        )
        # Game 2: away, scored 5, allowed 2
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026-spring-hs", opp_id, team_id, 2, 5, "2026-03-21"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        scored, allowed = _query_runs_avg(db, team_id, "2026-spring-hs")
        assert scored == 6.0   # (7 + 5) / 2
        assert allowed == 2.5  # (3 + 2) / 2

    def test_runs_avg_no_games(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        db.row_factory = sqlite3.Row
        scored, allowed = _query_runs_avg(db, team_id, "2026-spring-hs")
        assert scored is None
        assert allowed is None

    def test_runs_avg_scoped_to_team_and_season(self, db):
        """Verify WHERE filters exclude other teams and seasons."""
        team_id = _seed_team(db, name="Target", public_id="target1")
        other_id = _seed_team(db, name="Other", public_id="other1")
        opp_id = _seed_team(db, name="Opponent", public_id="opp-x")
        _seed_season(db, season_id="2026-spring-hs")
        db.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2025-spring-hs', '2025-spring-hs', 'spring', 2025)"
        )
        db.commit()
        # Target team, target season: scored 10, allowed 2
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026-spring-hs", team_id, opp_id, 10, 2, "2026-03-20"),
        )
        # Other team, same season: scored 20, allowed 0 (should be excluded)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026-spring-hs", other_id, opp_id, 20, 0, "2026-03-20"),
        )
        # Target team, wrong season: scored 30, allowed 1 (should be excluded)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g3", "2025-spring-hs", team_id, opp_id, 30, 1, "2025-03-20"),
        )
        db.commit()
        db.row_factory = sqlite3.Row
        scored, allowed = _query_runs_avg(db, team_id, "2026-spring-hs")
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

        db_path = str(tmp_path / "test.db")

        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_get_conn.side_effect = lambda: _fresh_conn()

        # Mock client: post_json returns a search hit matching public_id
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.post_json.return_value = {
            "hits": [
                {
                    "result": {
                        "id": "resolved-uuid-abc",
                        "public_id": "abc123",
                        "name": "Test Tigers",
                    }
                }
            ]
        }

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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


class TestSnapshotTeamIds:
    """Test _snapshot_team_ids helper."""

    def test_returns_all_team_ids(self, db):
        _seed_team(db, "Team A", "a1")
        _seed_team(db, "Team B", "b2")
        ids = _snapshot_team_ids(db)
        assert len(ids) == 2

    def test_empty_table(self, db):
        ids = _snapshot_team_ids(db)
        assert ids == set()


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
            ("g1", "2026-spring-hs", subject_id, orphan_id, 5, 3, "2026-03-20"),
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
            "chart_type, x, y) VALUES ('g1', ?, 'p2', '2026-spring-hs', ?, 'offensive', 0.5, 0.5)",
            (orphan_id, subject_id),
        )
        # Roster and season stats for orphan
        db.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) "
            "VALUES (?, 'p2', '2026-spring-hs', '99')",
            (orphan_id,),
        )
        db.execute(
            "INSERT INTO player_season_batting (player_id, team_id, season_id, gp, ab, h) "
            "VALUES ('p2', ?, '2026-spring-hs', 5, 20, 8)",
            (orphan_id,),
        )
        db.execute(
            "INSERT INTO player_season_pitching (player_id, team_id, season_id, gp_pitcher, ip_outs) "
            "VALUES ('p2', ?, '2026-spring-hs', 2, 12)",
            (orphan_id,),
        )
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
        # Orphan season stats deleted (team-scoped data always cleaned)
        assert db.execute(
            "SELECT team_id FROM player_season_batting WHERE team_id = ?", (orphan_id,)
        ).fetchone() is None
        assert db.execute(
            "SELECT team_id FROM player_season_pitching WHERE team_id = ?", (orphan_id,)
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
            ("g1", "2026-spring-hs", subject_id, orphan_id, 5, 3, "2026-03-20"),
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
            ("g-orphan-only", "2026-spring-hs", orphan_id, orphan2_id, 1, 2, "2026-03-21"),
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
            "away_team_id, status) VALUES ('g-shared', '2026-spring-hs', "
            "'2026-03-15', 1, ?, 'completed')",
            (orphan_id,),
        )
        # Plays for the shared game
        db.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id) VALUES ('g-shared', 1, 1, "
            "'top', '2026-spring-hs', 1, 1, 'p-shared', 'p-shared')"
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
            ("g-cross", "2026-spring-hs", orphan_id, orphan2_id, 5, 3, "2026-04-01"),
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
            ("g-shared", "2026-spring-hs", stub_id, tracked_id, 5, 3, "2026-04-01"),
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
            ("g-survive", "2026-spring-hs", stub_id, tracked_id, "2026-04-01"),
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
            ("g-solo", "2026-spring-hs", stub_id, stub_id, "2026-04-01"),
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
            ("g-multi", "2026-spring-hs", oa, ob, "2026-04-01"),
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


class TestCleanupNonFatal:
    """AC-3: Cleanup failure is non-fatal."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
        _seed_season(db)
        _seed_player(db, "p1", "Test", "Player")
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
        mock_loader = MagicMock()

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
                "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
                "VALUES ('2026', '2026', 'default', 2026)"
            )
            conn.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
                "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("g1", "2026", 1, opp_id, 7, 3, "2026-03-20"),
            )
            conn.commit()
            conn.close()
            return LoadResult(loaded=5)

        mock_loader.load_team.side_effect = _load_side_effect

        cleanup_called = []
        original_cleanup = cleanup_orphan_teams

        def _tracking_cleanup(conn, orphan_ids):
            cleanup_called.append(orphan_ids.copy())
            return original_cleanup(conn, orphan_ids)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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
    @patch("src.reports.generator.ensure_team_row", return_value=1)
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
        # Team 2: already owns the public_id we'd try to backfill
        db.execute(
            "INSERT INTO teams (name, public_id, season_year, membership_type) "
            "VALUES ('Waverly Duplicate', 'Xj9LlYlJklcl', 2026, 'tracked')"
        )
        _seed_season(db)
        db.execute(
            "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
            "VALUES (1, '2026-spring-hs', 'full', '2026-03-28T00:00:00Z', 'completed')"
        )
        db.commit()

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
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(team_id=1, season_id="2025-spring-hs", games_crawled=5, games=[], boxscores={})
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


# ---------------------------------------------------------------------------
# E-228-03: Standalone path -- dedup-gap fix + positioning recompute
# ---------------------------------------------------------------------------
# `load_real_schema` (in tests/conftest.py) applies the
# 002_batter_positioning.sql migration as part of the base schema setup
# (E-228-05), so individual fixtures here do NOT need to re-apply it.


def _seed_minimal_pipeline_inputs(
    db: sqlite3.Connection,
    *,
    team_id: int = 1,
    season_id: str = "2026-spring-hs",
    public_id: str = "abc123",
    team_name: str = "Test Tigers",
) -> None:
    """Seed the minimum rows needed for `generate_report` mock-paths to run.

    Covers: programs (implicit -- not needed), seasons, teams, scouting_runs.
    """
    db.execute(
        "INSERT INTO teams (id, name, public_id, season_year, membership_type) "
        "VALUES (?, ?, ?, 2026, 'tracked')",
        (team_id, team_name, public_id),
    )
    db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'spring-hs', 2026)",
        (season_id, season_id),
    )
    db.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
        "VALUES (?, ?, 'full', '2026-03-28T00:00:00Z', 'completed')",
        (team_id, season_id),
    )
    db.commit()


class TestStandalonePositioningWiring:
    """E-228-03: standalone path runs dedup-then-recompute after spray/plays."""

    @pytest.fixture()
    def db_path(self, tmp_path):
        """Disk-backed DB with 001 base schema + 002 batter_positioning."""
        path = tmp_path / "test.db"
        conn = sqlite3.connect(str(path))
        load_real_schema(conn)
        conn.commit()
        conn.close()
        return path

    def _fresh_conn_factory(self, db_path):
        def _factory():
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn
        return _factory

    def _mock_pipeline(self, mock_client_cls):
        from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
        from src.gamechanger.loaders import LoadResult

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026-spring-hs",
            games_crawled=5, games=[], boxscores={},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)
        return mock_crawler, mock_loader

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_dedup_called_before_compute_positioning(
        self, mock_derive, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path,
    ):
        """AC-1+AC-2: dedup_team_players runs BEFORE compute_positioning,
        both receive (conn, team_id, season_id)."""
        conn = sqlite3.connect(str(db_path))
        _seed_minimal_pipeline_inputs(conn)
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        # Track call order across both targets.
        call_order: list[tuple[str, int, str]] = []

        def _dedup_capture(_conn, team_id, season_id, *, manage_transaction=True):
            assert manage_transaction is True, "AC-1: must use manage_transaction=True"
            call_order.append(("dedup", team_id, season_id))
            return 0

        def _compute_capture(_conn, team_id, season_id):
            call_order.append(("compute", team_id, season_id))
            return []

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator.dedup_team_players",
                  side_effect=_dedup_capture) as _dedup_mock,
            patch("src.reports.generator.compute_positioning",
                  side_effect=_compute_capture) as _compute_mock,
        ):
            result = generate_report("abc123")

        assert result.success is True

        # AC-1: dedup called with (team_id, season_id) and manage_transaction=True.
        assert _dedup_mock.call_count == 1
        # AC-2: compute_positioning called with (conn, team_id, season_id).
        assert _compute_mock.call_count == 1

        # AC-1 ordering: dedup precedes compute_positioning.
        assert call_order == [
            ("dedup", 1, "2026-spring-hs"),
            ("compute", 1, "2026-spring-hs"),
        ]

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_compute_positioning_failure_is_non_fatal(
        self, mock_derive, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path, caplog,
    ):
        """AC-3: a raise from compute_positioning is logged at WARNING and
        report generation continues to success."""
        import logging

        conn = sqlite3.connect(str(db_path))
        _seed_minimal_pipeline_inputs(conn)
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        caplog.set_level(logging.WARNING, logger="src.reports.generator")

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch("src.reports.generator.dedup_team_players", return_value=0),
            patch(
                "src.reports.generator.compute_positioning",
                side_effect=RuntimeError("synthetic engine failure"),
            ),
        ):
            result = generate_report("abc123")

        # AC-3: report still succeeds.
        assert result.success is True
        # AC-3: failure logged at WARNING.
        warnings = [
            rec for rec in caplog.records
            if rec.levelno == logging.WARNING
            and "Positioning recompute failed" in rec.getMessage()
        ]
        assert warnings, "expected WARNING log for non-fatal recompute failure"

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_dedup_failure_is_non_fatal_and_recompute_still_runs(
        self, mock_derive, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path, caplog,
    ):
        """Dedup failure must not block the recompute (engine still runs).

        Symmetric to the AC-3 non-fatal recompute contract for the dedup
        sweep, matching the pattern in `run_scouting_sync`.
        """
        import logging

        conn = sqlite3.connect(str(db_path))
        _seed_minimal_pipeline_inputs(conn)
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        caplog.set_level(logging.WARNING, logger="src.reports.generator")
        recompute_invoked = []

        def _compute_capture(_conn, team_id, season_id):
            recompute_invoked.append((team_id, season_id))
            return []

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            patch(
                "src.reports.generator.dedup_team_players",
                side_effect=RuntimeError("synthetic dedup failure"),
            ),
            patch(
                "src.reports.generator.compute_positioning",
                side_effect=_compute_capture,
            ),
        ):
            result = generate_report("abc123")

        assert result.success is True
        # Recompute ran even though dedup raised.
        assert recompute_invoked == [(1, "2026-spring-hs")]
        warnings = [
            rec for rec in caplog.records
            if rec.levelno == logging.WARNING
            and "Standalone player-dedup failed" in rec.getMessage()
        ]
        assert warnings, "expected WARNING log for non-fatal dedup failure"

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_positioning_rows_written_with_real_engine(
        self, mock_derive, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path,
    ):
        """AC-2 end-to-end: real `compute_positioning` populates
        `batter_positioning` for the report team."""
        conn = sqlite3.connect(str(db_path))
        _seed_minimal_pipeline_inputs(conn)
        # Seed a player + roster and 15 left-outfield BIPs so the real engine
        # produces at least one populated per-position row (LF takes the lean).
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES (?, 'Hank', 'Aaron')",
            ("p1",),
        )
        conn.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) "
            "VALUES (1, 'p1', '2026-spring-hs')",
        )
        for i in range(15):
            conn.execute(
                """
                INSERT INTO spray_charts (
                    player_id, team_id, perspective_team_id, chart_type,
                    play_result, play_type, x, y, season_id, event_gc_id
                ) VALUES ('p1', 1, 1, 'offensive', 'single', 'fly_ball',
                          50.0, 100.0, '2026-spring-hs', ?)
                """,
                (f"evt-{i}",),
            )
        conn.commit()
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            # No patch on dedup_team_players or compute_positioning -- real engine runs.
        ):
            result = generate_report("abc123")

        assert result.success is True

        # batter_positioning should be populated for player p1 (6 position rows
        # under the v2 schema). E-229-02 retired call_state/team_state_call;
        # the v2 row carries direction_deviation, depth_deviation, zone_id.
        verify_conn = self._fresh_conn_factory(db_path)()
        verify_conn.row_factory = sqlite3.Row
        rows = verify_conn.execute(
            "SELECT position, zone_id, direction_deviation, depth_deviation, "
            "       bip_count "
            "FROM batter_positioning "
            "WHERE player_id = ? AND team_id = ? AND season_id = ?",
            ("p1", 1, "2026-spring-hs"),
        ).fetchall()
        verify_conn.close()
        assert len(rows) == 6
        # bip_count is per-batter (15), denormalized.
        for r in rows:
            assert r["bip_count"] == 15
        # End-to-end shape check: 6 rows with v2 columns present and
        # the engine produced ordinal-bucket deviations + zone letters
        # (or NULL for at-star batters). The wiring contract is what
        # this test exercises; specific zone-letter assertions belong
        # in the engine tests (tests/test_positioning_engine.py).
        for r in rows:
            assert "zone_id" in dict(r)
            assert "direction_deviation" in dict(r)
            assert "depth_deviation" in dict(r)

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_duplicate_player_merged_before_recompute(
        self, mock_derive, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path,
    ):
        """AC-4: a cross-perspective duplicate player is merged BEFORE the
        recompute, and `batter_positioning` reflects the merged BIP count."""
        conn = sqlite3.connect(str(db_path))
        _seed_minimal_pipeline_inputs(conn)
        # Seed two duplicate players on the same team's roster: canonical
        # 'Johnny Smith' and duplicate 'John Smith' (prefix-match detection).
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES ('canonical', 'Johnny', 'Smith')"
        )
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES ('duplicate', 'John', 'Smith')"
        )
        conn.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) "
            "VALUES (1, 'canonical', '2026-spring-hs')"
        )
        conn.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id) "
            "VALUES (1, 'duplicate', '2026-spring-hs')"
        )
        # Seed 8 left-outfield BIPs for canonical + 8 for duplicate -- separately
        # each is below the 10-BIP per-batter thin gate, but merged they are 16
        # (passes the per-batter gate AND the LF subset's direction gate).
        for i in range(8):
            conn.execute(
                """
                INSERT INTO spray_charts (
                    player_id, team_id, perspective_team_id, chart_type,
                    play_result, play_type, x, y, season_id, event_gc_id
                ) VALUES ('canonical', 1, 1, 'offensive', 'single', 'fly_ball',
                          50.0, 100.0, '2026-spring-hs', ?)
                """,
                (f"evt-canon-{i}",),
            )
        for i in range(8):
            conn.execute(
                """
                INSERT INTO spray_charts (
                    player_id, team_id, perspective_team_id, chart_type,
                    play_result, play_type, x, y, season_id, event_gc_id
                ) VALUES ('duplicate', 1, 1, 'offensive', 'single', 'fly_ball',
                          50.0, 100.0, '2026-spring-hs', ?)
                """,
                (f"evt-dup-{i}",),
            )
        conn.commit()
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
            # Real dedup_team_players AND compute_positioning -- no patches here.
        ):
            result = generate_report("abc123")

        assert result.success is True

        verify_conn = self._fresh_conn_factory(db_path)()
        verify_conn.row_factory = sqlite3.Row
        # The duplicate row should have been deleted (merged into canonical).
        remaining_dups = verify_conn.execute(
            "SELECT player_id FROM players WHERE player_id = 'duplicate'"
        ).fetchall()
        # batter_positioning should have rows only under the canonical player
        # and bip_count should be 16 (8 canonical + 8 merged-in duplicate).
        # E-229-02 retired call_state; the v2 query reads v2 columns only.
        rows = verify_conn.execute(
            "SELECT position, bip_count, zone_id FROM batter_positioning "
            "WHERE player_id = 'canonical' AND team_id = 1",
        ).fetchall()
        no_dup_rows = verify_conn.execute(
            "SELECT COUNT(*) c FROM batter_positioning WHERE player_id = 'duplicate'"
        ).fetchone()["c"]
        verify_conn.close()

        assert remaining_dups == [], "duplicate player should have been merged out"
        assert len(rows) == 6, "canonical should have one batter_positioning row per position"
        # bip_count is denormalized -- every row carries 16.
        for r in rows:
            assert r["bip_count"] == 16
        # Confirm: no orphan batter_positioning rows under the duplicate player_id.
        assert no_dup_rows == 0


# ---------------------------------------------------------------------------
# E-228-05: _query_batter_positioning
# ---------------------------------------------------------------------------


class TestQueryBatterPositioning:
    """E-228-05: the report query function that reads `batter_positioning`
    JOIN players LEFT JOIN team_rosters for the standalone perspective."""

    @pytest.fixture()
    def conn(self, tmp_path):
        path = tmp_path / "test.db"
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        load_real_schema(conn)
        # Common seed: one team, one season, two players (with + without jersey).
        conn.execute(
            "INSERT INTO teams (id, name, public_id, season_year, membership_type) "
            "VALUES (1, 'Eastlake Bears', 'eastlake', 2026, 'tracked')"
        )
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES ('2026-spring-hs', '2026', 'spring-hs', 2026)"
        )
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES ('p1', 'Hank', 'Ramirez')"
        )
        conn.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES ('p2', 'Test', 'Thompson')"
        )
        conn.execute(
            "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) "
            "VALUES (1, 'p1', '2026-spring-hs', '7')"
        )
        # p2 intentionally has no roster row -- left join should yield NULL jersey.
        # Six batter_positioning rows for p1 (one per covered position).
        # AC-10(f) per E-229-02: INSERTs use the v2 column set (zone_id,
        # direction_deviation, depth_deviation, is_thin, bip_count,
        # hr_count). Retired columns (call_state, team_state_call,
        # direction_shade, depth_shade, zone_concentration) are gone.
        positions = ("SS", "2B", "3B", "LF", "CF", "RF")
        for position in positions:
            conn.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id, position,
                    direction_deviation, depth_deviation, zone_id,
                    is_thin, bip_count, hr_count
                ) VALUES ('p1', 1, '2026-spring-hs', 1, ?, -1, 0, 'B',
                          0, 38, 2)
                """,
                (position,),
            )
        # Six rows for p2 (same team_id and perspective_team_id, different
        # player -- both p1 and p2 surface in the standalone perspective
        # result. Cross-perspective exclusion is tested separately in
        # test_filters_by_perspective_team_id_matching_team_id below.
        for position in positions:
            conn.execute(
                """
                INSERT INTO batter_positioning (
                    player_id, team_id, season_id, perspective_team_id, position,
                    direction_deviation, depth_deviation, zone_id,
                    is_thin, bip_count, hr_count
                ) VALUES ('p2', 1, '2026-spring-hs', 1, ?, 0, 0, NULL,
                          0, 27, 0)
                """,
                (position,),
            )
        conn.commit()
        yield conn
        conn.close()

    def test_returns_one_row_per_player_position(self, conn):
        from src.reports.generator import _query_batter_positioning
        rows = _query_batter_positioning(conn, 1, "2026-spring-hs")
        # 2 players * 6 positions = 12 rows.
        assert len(rows) == 12
        assert {r["player_id"] for r in rows} == {"p1", "p2"}
        assert {r["position"] for r in rows} == {"SS", "2B", "3B", "LF", "CF", "RF"}

    def test_includes_player_name_and_jersey_columns(self, conn):
        from src.reports.generator import _query_batter_positioning
        rows = _query_batter_positioning(conn, 1, "2026-spring-hs")
        p1 = [r for r in rows if r["player_id"] == "p1"][0]
        assert p1["first_name"] == "Hank"
        assert p1["last_name"] == "Ramirez"
        assert p1["jersey_number"] == "7"
        # p2 has no roster row -- jersey_number is NULL via LEFT JOIN.
        p2 = [r for r in rows if r["player_id"] == "p2"][0]
        assert p2["jersey_number"] is None
        assert p2["last_name"] == "Thompson"

    def test_returns_full_batter_positioning_column_set(self, conn):
        """Query must surface every non-PK column the renderer/Tier 2 reads.

        E-229-02 scrubbed the SELECT to the v2 column set: retired the v1
        categorical columns (call_state, team_state_call, direction_shade,
        depth_shade, zone_concentration) per epic TN-13.
        """
        from src.reports.generator import _query_batter_positioning
        rows = _query_batter_positioning(conn, 1, "2026-spring-hs")
        expected_keys = {
            "player_id", "position",
            "direction_deviation", "depth_deviation", "zone_id",
            "bip_count", "hr_count", "is_thin",
            "first_name", "last_name", "jersey_number",
        }
        assert set(rows[0].keys()) == expected_keys

    def test_filters_by_perspective_team_id_matching_team_id(self, conn):
        """Standalone perspective: perspective_team_id == team_id."""
        from src.reports.generator import _query_batter_positioning
        # Add a row for a different perspective (e.g. a member team scouting).
        conn.execute(
            """
            INSERT INTO teams (id, name, membership_type)
            VALUES (99, 'Other LSB', 'member')
            """
        )
        conn.execute(
            """
            INSERT INTO batter_positioning (
                player_id, team_id, season_id, perspective_team_id, position,
                direction_deviation, depth_deviation, zone_id,
                is_thin, bip_count, hr_count
            ) VALUES ('p1', 1, '2026-spring-hs', 99, 'SS', 0, 0, NULL,
                      0, 30, 0)
            """
        )
        conn.commit()
        rows = _query_batter_positioning(conn, 1, "2026-spring-hs")
        # Still 12 rows -- the other-perspective row is excluded.
        assert len(rows) == 12
        # No row from perspective_team_id=99 surfaced.
        # (Query doesn't return perspective_team_id, but the count guarantees it.)

    def test_returns_empty_list_when_no_rows(self, conn):
        from src.reports.generator import _query_batter_positioning
        rows = _query_batter_positioning(conn, 1, "2027-fall")
        assert rows == []


# ---------------------------------------------------------------------------
# E-229 dev-validation fix: scouting report ships the 6 positioning data
# keys consumed by `_build_positioning_context`. Without the wiring, the
# scouting report's positioning_cards.html partial renders empty <svg>
# slots and a blank opponent-context body even though the parallel
# 4-page bundle at data/reports/{slug}/index.html renders correctly.
# ---------------------------------------------------------------------------


def _seed_positioning_payload_inputs(
    db: sqlite3.Connection,
    *,
    team_id: int = 1,
    season_id: str = "2026-spring-hs",
    public_id: str = "abc123",
    team_name: str = "Test Tigers",
) -> None:
    """Seed enough rows for the positioning payload to populate.

    Adds the minimum-pipeline rows PLUS one player with a roster row PLUS
    a full team_position_aggregate set across the 6 covered positions
    PLUS one outlier `batter_positioning` row so the cards have an
    outlier sidebar entry.
    """
    _seed_minimal_pipeline_inputs(
        db, team_id=team_id, season_id=season_id,
        public_id=public_id, team_name=team_name,
    )
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) "
        "VALUES ('p1', 'Hank', 'Ramirez')"
    )
    db.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number) "
        "VALUES (?, 'p1', ?, '7')",
        (team_id, season_id),
    )
    # Aggregates: bip_count=60 across all 6 positions yields "Full" tier.
    from src.reports.positioning import COVERED_POSITIONS
    for position in COVERED_POSITIONS:
        db.execute(
            """
            INSERT INTO team_position_aggregate (
                team_id, season_id, perspective_team_id, position,
                star_x, star_y, bip_count, is_low_confidence
            ) VALUES (?, ?, ?, ?, 160.0, 200.0, 60, 0)
            """,
            (team_id, season_id, team_id, position),
        )
    # One outlier batter row at LF zone A; default rows for the rest.
    db.execute(
        """
        INSERT INTO batter_positioning (
            player_id, team_id, season_id, perspective_team_id, position,
            direction_deviation, depth_deviation, zone_id,
            is_thin, bip_count, hr_count
        ) VALUES ('p1', ?, ?, ?, 'LF', -1, -1, 'A', 0, 20, 0)
        """,
        (team_id, season_id, team_id),
    )
    for position in ("CF", "RF", "3B", "SS", "2B"):
        db.execute(
            """
            INSERT INTO batter_positioning (
                player_id, team_id, season_id, perspective_team_id, position,
                direction_deviation, depth_deviation, zone_id,
                is_thin, bip_count, hr_count
            ) VALUES ('p1', ?, ?, ?, ?, 0, 0, NULL, 0, 20, 0)
            """,
            (team_id, season_id, team_id, position),
        )
    db.commit()


class TestScoutingReportPositioningPayload:
    """E-229 dev-validation fix: `generate_report` populates the 6
    positioning data keys consumed by the renderer's
    `_build_positioning_context`.

    Before this fix, the scouting report's positioning_cards.html partial
    fell back to empty defaults for `positioning_card_svgs`,
    `positioning_compass_key_svg`, `positioning_coverage_cue`, and the
    three `positioning_opponent_context_*` keys -- so the rendered HTML
    shipped empty <svg> slots and a blank opponent-context body.
    """

    @pytest.fixture()
    def db_path(self, tmp_path):
        path = tmp_path / "test.db"
        c = sqlite3.connect(str(path))
        load_real_schema(c)
        c.commit()
        c.close()
        return path

    def _fresh_conn_factory(self, db_path):
        def _factory():
            c = sqlite3.connect(str(db_path))
            c.execute("PRAGMA foreign_keys=ON;")
            return c
        return _factory

    def _mock_pipeline(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026-spring-hs",
            games_crawled=5, games=[], boxscores={},
        )
        from src.gamechanger.loaders import LoadResult
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)
        return mock_crawler, mock_loader

    # ------------------------------------------------------------------
    # Test 1 -- caller-audit: the data dict passed to render_report
    # must contain the 6 new positioning keys. Captures the dict via
    # a MagicMock that wraps render_report.
    # ------------------------------------------------------------------
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_data_dict_includes_six_positioning_keys(
        self, mock_derive, mock_plays, mock_spray, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path,
    ):
        """Caller-audit: every kwarg added to `_build_positioning_context`
        in the renderer must be populated by `generate_report`. The
        symmetric path (`generate_positioning_bundle`) already populates
        these via F2; this test ensures the scouting report does too.
        """
        conn = sqlite3.connect(str(db_path))
        _seed_positioning_payload_inputs(conn)
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        captured: dict[str, object] = {}

        def _capture_render(data):
            captured.update(data)
            return "<html>captured</html>"

        with (
            patch("src.reports.generator.ScoutingCrawler",
                  return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader",
                  return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR",
                  tmp_path / "data" / "reports"),
            patch("src.reports.generator.render_report",
                  side_effect=_capture_render),
            patch("src.reports.generator.dedup_team_players", return_value=0),
            patch("src.reports.generator.compute_positioning", return_value=[]),
        ):
            result = generate_report("abc123")

        assert result.success is True

        # All 6 positioning data keys must be present.
        required_keys = [
            "positioning_card_svgs",
            "positioning_compass_key_svg",
            "positioning_coverage_cue",
            "positioning_opponent_context_coverage_line",
            "positioning_opponent_context_stats",
            "positioning_opponent_context_tier_line",
        ]
        for key in required_keys:
            assert key in captured, (
                f"render_report data missing positioning key: {key}"
            )

        # Per-card SVGs: one entry per covered position. (Test fixture
        # patches dedup/compute but leaves render_report's inputs as
        # produced by the actual payload builder against seeded data.)
        from src.reports.positioning import COVERED_POSITIONS
        svgs = captured["positioning_card_svgs"]
        assert isinstance(svgs, dict)
        for position in COVERED_POSITIONS:
            assert position in svgs, (
                f"positioning_card_svgs missing position {position}"
            )
            assert svgs[position].startswith("<svg"), (
                f"positioning_card_svgs[{position}] should be an SVG, "
                f"got: {svgs[position][:60]!r}"
            )

        # Compass key must be a non-empty SVG.
        assert captured["positioning_compass_key_svg"].startswith("<svg"), (
            "positioning_compass_key_svg should be an inline SVG"
        )

        # Opponent-context stats: fixed 4-row order from `_build_opponent_context`.
        stats = captured["positioning_opponent_context_stats"]
        assert isinstance(stats, list)
        labels = [s["label"] for s in stats]
        assert labels == [
            "Record",
            "Runs / game",
            "Runs allowed / game",
            "Team BIPs",
        ]

        # Tier line should reference the "Full" tier given bip_count=60
        # + is_low_confidence=0 in the fixture.
        assert "Coverage tier:" in captured[
            "positioning_opponent_context_tier_line"
        ]
        assert "Full" in captured[
            "positioning_opponent_context_tier_line"
        ]

    # ------------------------------------------------------------------
    # Test 2 -- smoke regression: full render pipeline against seeded
    # data, asserting the rendered HTML contains real SVG markup at
    # the 6 card slots AND the compass-key SVG AND the opponent-context
    # stat rows. This is the test that would fail on the pre-fix code
    # (the scouting report shipped empty SVGs and a blank context).
    # ------------------------------------------------------------------
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_rendered_html_contains_positioning_svgs_and_context(
        self, mock_derive, mock_plays, mock_spray, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path,
    ):
        """Smoke regression: the rendered scouting report HTML must
        contain (a) inline <svg> elements at each of the 6 card slots,
        (b) the compass-key SVG's letters A-H, and (c) the four
        opponent-context stat labels. This test would fail against the
        pre-fix `generate_report` -- the SVG slots were empty and the
        opponent-context body was blank.
        """
        conn = sqlite3.connect(str(db_path))
        _seed_positioning_payload_inputs(conn)
        # Add a few completed games so the opponent-context stats have
        # numeric values to compute (Record / Runs per game). Two team
        # IDs already seeded: opponent (1) + a member team (we insert
        # one inline here).
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (99, 'LSB Varsity', 'member')"
        )
        for idx, (home, away, hs, as_) in enumerate([
            (1, 99, 8, 2),
            (99, 1, 5, 6),
            (1, 99, 7, 4),
        ]):
            conn.execute(
                """
                INSERT INTO games (
                    game_id, season_id, home_team_id, away_team_id,
                    home_score, away_score, game_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (f"g{idx}", "2026-spring-hs", home, away, hs, as_,
                 f"2026-03-{idx + 1:02d}"),
            )
        conn.commit()
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        # Capture the rendered HTML by intercepting Path.write_text via
        # the file-system write performed inside `generate_report`.
        # Simpler: read the file from disk after the call completes.
        with (
            patch("src.reports.generator.ScoutingCrawler",
                  return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader",
                  return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR",
                  tmp_path / "data" / "reports"),
            patch("src.reports.generator.dedup_team_players", return_value=0),
            patch("src.reports.generator.compute_positioning", return_value=[]),
            # Bundle render writes to disk; non-fatal failure is fine but
            # we patch it to keep the test focused on the scouting
            # report's render path (and to avoid weasyprint/PDF deps).
            patch("src.reports.generator._write_positioning_bundle"),
        ):
            result = generate_report("abc123")

        assert result.success is True
        assert result.slug is not None

        # Read the rendered scouting report file from disk.
        report_path = tmp_path / "data" / "reports" / f"{result.slug}.html"
        assert report_path.exists(), (
            f"scouting report not written at {report_path}"
        )
        html = report_path.read_text(encoding="utf-8")

        # ---- a) Inline <svg> bodies on the 6 position cards. The
        # template wraps each field SVG in `<div class="positioning-card-svg-slot">`
        # for cards 1-4 + 5-6, and emits `{{ card.svg | safe }}` inside.
        # The compass-key slot uses `{{ positioning.compass_key_svg | safe }}`.
        # Total expected <svg roots: 6 cards + 1 compass key = at least 7.
        svg_open_count = html.count("<svg")
        assert svg_open_count >= 7, (
            f"expected >=7 <svg elements (6 cards + compass key), "
            f"got {svg_open_count}"
        )

        # ---- b) Compass-key SVG body should contain letters A-H. Scope
        # to the compass-key slot div so we don't accidentally match
        # zone-letter cells elsewhere.
        compass_start = html.find(
            'class="positioning-card compass-key"',
        )
        assert compass_start > 0, "compass-key slot div not rendered"
        compass_svg_start = html.find("<svg", compass_start)
        compass_svg_end = html.find("</svg>", compass_svg_start) + len("</svg>")
        compass_body = html[compass_svg_start:compass_svg_end]
        for letter in "ABCDEFGH":
            assert f">{letter}<" in compass_body, (
                f"compass-key SVG missing letter {letter}"
            )

        # ---- c) Opponent-context stat labels (4 rows in fixed order).
        for stat_label in (
            "Record",
            "Runs / game",
            "Runs allowed / game",
            "Team BIPs",
        ):
            assert stat_label in html, (
                f"rendered HTML missing opponent-context stat: {stat_label}"
            )

        # ---- d) Coverage tier line.
        assert "Coverage tier:" in html
        assert "Full" in html

    # ------------------------------------------------------------------
    # Test 3 -- non-fatal payload failure must not break report
    # generation. Confirms the wrapped try/except contract.
    # ------------------------------------------------------------------
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    @patch(
        "src.reports.generator.derive_season_id_for_team",
        return_value=("2026-spring-hs", 2026),
    )
    def test_payload_failure_is_non_fatal(
        self, mock_derive, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, db_path, tmp_path, caplog,
    ):
        """If the positioning payload helper raises, the report still
        succeeds with empty positioning slots (matching prior degraded
        behavior). A WARNING is logged so the failure isn't silent.
        """
        import logging

        conn = sqlite3.connect(str(db_path))
        _seed_minimal_pipeline_inputs(conn)
        conn.close()

        mock_get_conn.side_effect = self._fresh_conn_factory(db_path)
        mock_crawler, mock_loader = self._mock_pipeline(mock_client_cls)

        caplog.set_level(logging.WARNING, logger="src.reports.generator")

        with (
            patch("src.reports.generator.ScoutingCrawler",
                  return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader",
                  return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR",
                  tmp_path / "data" / "reports"),
            patch("src.reports.generator.dedup_team_players", return_value=0),
            patch("src.reports.generator.compute_positioning", return_value=[]),
            patch(
                "src.reports.generator._build_scouting_report_positioning_payload",
                side_effect=RuntimeError("synthetic payload failure"),
            ),
        ):
            result = generate_report("abc123")

        assert result.success is True
        warnings = [
            rec for rec in caplog.records
            if rec.levelno == logging.WARNING
            and "Positioning payload build failed" in rec.getMessage()
        ]
        assert warnings, (
            "expected WARNING log for non-fatal payload failure"
        )


