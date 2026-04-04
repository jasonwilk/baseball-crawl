"""Tests for the report generation pipeline (E-172-02, E-176-02, E-185-01)."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.reports.generator import (
    GenerationResult,
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
    """Create an in-memory DB with the required schema for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Minimal schema for the tables we touch
    conn.executescript("""
        CREATE TABLE programs (
            program_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            program_type TEXT NOT NULL,
            org_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            program_id TEXT REFERENCES programs(program_id),
            gc_uuid TEXT UNIQUE,
            public_id TEXT UNIQUE,
            season_year INTEGER,
            membership_type TEXT DEFAULT 'tracked',
            classification TEXT,
            active INTEGER DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE seasons (
            season_id TEXT PRIMARY KEY,
            name TEXT,
            season_type TEXT,
            year INTEGER
        );
        CREATE TABLE players (
            player_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            bats TEXT,
            throws TEXT
        );
        CREATE TABLE team_rosters (
            team_id INTEGER,
            player_id TEXT,
            season_id TEXT,
            jersey_number TEXT,
            position TEXT,
            PRIMARY KEY (team_id, player_id, season_id)
        );
        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            season_id TEXT,
            home_team_id INTEGER,
            away_team_id INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            game_date TEXT,
            status TEXT DEFAULT 'completed'
        );
        CREATE TABLE player_season_batting (
            player_id TEXT,
            team_id INTEGER,
            season_id TEXT,
            gp INTEGER DEFAULT 0,
            games_tracked INTEGER DEFAULT 0,
            ab INTEGER DEFAULT 0,
            h INTEGER DEFAULT 0,
            doubles INTEGER DEFAULT 0,
            triples INTEGER DEFAULT 0,
            hr INTEGER DEFAULT 0,
            rbi INTEGER DEFAULT 0,
            r INTEGER DEFAULT 0,
            bb INTEGER DEFAULT 0,
            so INTEGER DEFAULT 0,
            sb INTEGER DEFAULT 0,
            tb INTEGER DEFAULT 0,
            hbp INTEGER DEFAULT 0,
            shf INTEGER DEFAULT 0,
            cs INTEGER DEFAULT 0,
            PRIMARY KEY (player_id, team_id, season_id)
        );
        CREATE TABLE player_season_pitching (
            player_id TEXT,
            team_id INTEGER,
            season_id TEXT,
            gp_pitcher INTEGER DEFAULT 0,
            games_tracked INTEGER DEFAULT 0,
            ip_outs INTEGER DEFAULT 0,
            h INTEGER DEFAULT 0,
            r INTEGER DEFAULT 0,
            er INTEGER DEFAULT 0,
            bb INTEGER DEFAULT 0,
            so INTEGER DEFAULT 0,
            wp INTEGER DEFAULT 0,
            hbp INTEGER DEFAULT 0,
            pitches INTEGER DEFAULT 0,
            total_strikes INTEGER DEFAULT 0,
            bf INTEGER DEFAULT 0,
            gs INTEGER,
            PRIMARY KEY (player_id, team_id, season_id)
        );
        CREATE TABLE player_game_batting (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL REFERENCES games(game_id),
            player_id TEXT NOT NULL REFERENCES players(player_id),
            team_id INTEGER NOT NULL REFERENCES teams(id),
            ab INTEGER, r INTEGER, h INTEGER, rbi INTEGER,
            bb INTEGER, so INTEGER,
            UNIQUE(game_id, player_id)
        );
        CREATE TABLE player_game_pitching (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL REFERENCES games(game_id),
            player_id TEXT NOT NULL REFERENCES players(player_id),
            team_id INTEGER NOT NULL REFERENCES teams(id),
            ip_outs INTEGER, h INTEGER, er INTEGER, bb INTEGER, so INTEGER,
            UNIQUE(game_id, player_id)
        );
        CREATE TABLE spray_charts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT REFERENCES games(game_id),
            team_id INTEGER,
            player_id TEXT,
            season_id TEXT,
            chart_type TEXT,
            x REAL,
            y REAL,
            play_result TEXT,
            play_type TEXT
        );
        CREATE TABLE scouting_runs (
            team_id INTEGER,
            season_id TEXT,
            run_type TEXT,
            started_at TEXT,
            completed_at TEXT,
            status TEXT,
            last_checked TEXT,
            games_found INTEGER,
            games_crawled INTEGER,
            players_found INTEGER,
            error_message TEXT,
            PRIMARY KEY (team_id, season_id, run_type)
        );
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'generating',
            generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            expires_at TEXT NOT NULL,
            report_path TEXT,
            error_message TEXT
        );
        CREATE INDEX idx_reports_slug ON reports(slug);
        CREATE INDEX idx_reports_team_id ON reports(team_id);
        CREATE TABLE plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL REFERENCES games(game_id),
            play_order INTEGER NOT NULL,
            inning INTEGER NOT NULL,
            half TEXT NOT NULL,
            season_id TEXT NOT NULL,
            batting_team_id INTEGER NOT NULL REFERENCES teams(id),
            batter_id TEXT NOT NULL REFERENCES players(player_id),
            pitcher_id TEXT REFERENCES players(player_id),
            outcome TEXT,
            pitch_count INTEGER NOT NULL DEFAULT 0,
            is_first_pitch_strike INTEGER NOT NULL DEFAULT 0,
            is_qab INTEGER NOT NULL DEFAULT 0,
            home_score INTEGER,
            away_score INTEGER,
            did_score_change INTEGER,
            outs_after INTEGER,
            did_outs_change INTEGER,
            UNIQUE(game_id, play_order)
        );
        CREATE TABLE play_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            play_id INTEGER NOT NULL REFERENCES plays(id),
            event_order INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            pitch_result TEXT,
            is_first_pitch INTEGER NOT NULL DEFAULT 0,
            raw_template TEXT,
            UNIQUE(play_id, event_order)
        );
        CREATE TABLE reconciliation_discrepancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL REFERENCES games(game_id),
            run_id TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            player_id TEXT NOT NULL,
            signal_name TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE crawl_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            status TEXT
        );
        CREATE TABLE coaching_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            team_id INTEGER
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            role TEXT,
            hashed_password TEXT
        );
        CREATE TABLE user_team_access (
            user_id INTEGER,
            team_id INTEGER,
            UNIQUE(user_id, team_id)
        );
        CREATE TABLE team_opponents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            our_team_id INTEGER,
            opponent_team_id INTEGER,
            UNIQUE(our_team_id, opponent_team_id)
        );
        CREATE TABLE opponent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            our_team_id INTEGER,
            root_team_id TEXT NOT NULL,
            opponent_name TEXT NOT NULL,
            resolved_team_id INTEGER,
            resolution_method TEXT,
            resolved_at TEXT,
            is_hidden INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()
    yield conn
    conn.close()


def _seed_team(db, name="Test Tigers", public_id="abc123"):
    """Insert a team and return its id."""
    cursor = db.execute(
        "INSERT INTO teams (name, public_id, season_year) VALUES (?, ?, 2026)",
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

    def test_no_re_import(self):
        """AC-6: import re should be removed (was only used by _UUID_RE)."""
        import src.reports.generator as gen_module
        import inspect

        source = inspect.getsource(gen_module)
        # Check there is no 'import re' at module level
        assert "\nimport re\n" not in source


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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
        _seed_season(db)
        # Add games: 2 wins, 1 loss
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026-spring-hs", team_id, 999, 5, 3, "2026-03-20"),
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026-spring-hs", 999, team_id, 3, 7, "2026-03-21"),
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g3", "2026-spring-hs", team_id, 999, 2, 4, "2026-03-22"),
        )
        db.commit()

        record = _query_record(db, team_id, "2026-spring-hs")
        assert record is not None
        assert record["wins"] == 2
        assert record["losses"] == 1

    def test_query_recent_games(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        for i in range(7):
            db.execute(
                "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"g{i}", "2026-spring-hs", team_id, 999, 5 + i, 3, f"2026-03-{20+i:02d}"),
            )
        db.commit()

        games = _query_recent_games(db, team_id, "2026-spring-hs", limit=5)
        assert len(games) == 5
        assert games[0]["result"] == "W"

    def test_query_freshness(self, db):
        team_id = _seed_team(db)
        _seed_season(db)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026-spring-hs", team_id, 999, 5, 3, "2026-03-25"),
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
            "abc123", season_id="2026-spring-hs", gc_uuid=None
        )
        mock_loader.load_all.assert_called_once()
        # Verify load_all received public_id and season_id kwargs
        call_kwargs = mock_loader.load_all.call_args
        assert call_kwargs[1]["public_id"] == "abc123"
        assert call_kwargs[1]["season_id"] == "2026-spring-hs"

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
            "abc123", season_id="2026-spring-hs", gc_uuid="resolved-uuid"
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
        conn_template.execute("PRAGMA foreign_keys=ON;")
        conn_template.executescript("""
            CREATE TABLE IF NOT EXISTS programs (
                program_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                program_type TEXT NOT NULL,
                org_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                program_id TEXT REFERENCES programs(program_id),
                gc_uuid TEXT UNIQUE,
                public_id TEXT UNIQUE,
                season_year INTEGER,
                membership_type TEXT DEFAULT 'tracked',
                classification TEXT,
                active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS seasons (
                season_id TEXT PRIMARY KEY, name TEXT, season_type TEXT, year INTEGER
            );
            CREATE TABLE IF NOT EXISTS scouting_runs (
                team_id INTEGER, season_id TEXT, run_type TEXT,
                started_at TEXT, completed_at TEXT, status TEXT,
                last_checked TEXT, games_found INTEGER, games_crawled INTEGER,
                players_found INTEGER, error_message TEXT,
                PRIMARY KEY (team_id, season_id, run_type)
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                team_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'generating',
                generated_at TEXT,
                expires_at TEXT,
                report_path TEXT,
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY, season_id TEXT,
                home_team_id INTEGER, away_team_id INTEGER,
                home_score INTEGER, away_score INTEGER,
                game_date TEXT, status TEXT
            );
            CREATE TABLE IF NOT EXISTS players (
                player_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT,
                bats TEXT, throws TEXT
            );
            CREATE TABLE IF NOT EXISTS player_season_batting (
                player_id TEXT, team_id INTEGER, season_id TEXT,
                gp INTEGER DEFAULT 0, games_tracked INTEGER DEFAULT 0,
                ab INTEGER DEFAULT 0, h INTEGER DEFAULT 0, doubles INTEGER DEFAULT 0,
                triples INTEGER DEFAULT 0, hr INTEGER DEFAULT 0, rbi INTEGER DEFAULT 0,
                r INTEGER DEFAULT 0, bb INTEGER DEFAULT 0, so INTEGER DEFAULT 0,
                sb INTEGER DEFAULT 0, tb INTEGER DEFAULT 0, hbp INTEGER DEFAULT 0,
                shf INTEGER DEFAULT 0, cs INTEGER DEFAULT 0,
                PRIMARY KEY (player_id, team_id, season_id)
            );
            CREATE TABLE IF NOT EXISTS player_season_pitching (
                player_id TEXT, team_id INTEGER, season_id TEXT,
                gp_pitcher INTEGER DEFAULT 0, games_tracked INTEGER DEFAULT 0,
                ip_outs INTEGER DEFAULT 0, h INTEGER DEFAULT 0, r INTEGER DEFAULT 0,
                er INTEGER DEFAULT 0, bb INTEGER DEFAULT 0, so INTEGER DEFAULT 0,
                wp INTEGER DEFAULT 0, hbp INTEGER DEFAULT 0,
                pitches INTEGER DEFAULT 0, total_strikes INTEGER DEFAULT 0,
                bf INTEGER DEFAULT 0,
                PRIMARY KEY (player_id, team_id, season_id)
            );
            CREATE TABLE IF NOT EXISTS team_rosters (
                team_id INTEGER, player_id TEXT, season_id TEXT,
                jersey_number TEXT, position TEXT,
                PRIMARY KEY (team_id, player_id, season_id)
            );
            CREATE TABLE IF NOT EXISTS spray_charts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER, player_id TEXT, season_id TEXT,
                chart_type TEXT, x REAL, y REAL, play_result TEXT, play_type TEXT
            );
            CREATE TABLE IF NOT EXISTS plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                play_order INTEGER NOT NULL,
                inning INTEGER NOT NULL,
                half TEXT NOT NULL,
                season_id TEXT NOT NULL,
                batting_team_id INTEGER NOT NULL,
                batter_id TEXT NOT NULL,
                pitcher_id TEXT,
                outcome TEXT,
                pitch_count INTEGER NOT NULL DEFAULT 0,
                is_first_pitch_strike INTEGER NOT NULL DEFAULT 0,
                is_qab INTEGER NOT NULL DEFAULT 0,
                home_score INTEGER,
                away_score INTEGER,
                did_score_change INTEGER,
                outs_after INTEGER,
                did_outs_change INTEGER,
                UNIQUE(game_id, play_order)
            );
            CREATE TABLE IF NOT EXISTS play_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                play_id INTEGER NOT NULL,
                event_order INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                UNIQUE(play_id, event_order)
            );
            CREATE TABLE IF NOT EXISTS reconciliation_discrepancies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL, run_id TEXT NOT NULL,
                team_id INTEGER NOT NULL, player_id TEXT NOT NULL,
                signal_name TEXT NOT NULL, category TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS crawl_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, team_id INTEGER, status TEXT
            );
            CREATE TABLE IF NOT EXISTS coaching_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, team_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS user_team_access (
                user_id INTEGER, team_id INTEGER, UNIQUE(user_id, team_id)
            );
            CREATE TABLE IF NOT EXISTS opponent_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                our_team_id INTEGER, root_team_id TEXT NOT NULL,
                opponent_name TEXT NOT NULL, resolved_team_id INTEGER,
                resolution_method TEXT, resolved_at TEXT
            );
        """)
        # Seed team WITH gc_uuid already set
        conn_template.execute(
            "INSERT INTO teams (name, public_id, gc_uuid, season_year) "
            "VALUES ('Test Tigers', 'abc123', 'existing-uuid-999', 2026)"
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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

    def test_null_opponent_name_fallback(self, db):
        team_id = _seed_team(db, name="Us", public_id="us123")
        # Insert opponent with NULL name
        cursor = db.execute(
            "INSERT INTO teams (name, public_id, season_year) VALUES (NULL, 'unk999', 2026)"
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
        _seed_season(db)
        # Game 1: home, scored 7, allowed 3
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026-spring-hs", team_id, 999, 7, 3, "2026-03-20"),
        )
        # Game 2: away, scored 5, allowed 2
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026-spring-hs", 999, team_id, 2, 5, "2026-03-21"),
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
            ("g1", "2026-spring-hs", team_id, 999, 10, 2, "2026-03-20"),
        )
        # Other team, same season: scored 20, allowed 0 (should be excluded)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g2", "2026-spring-hs", other_id, 999, 20, 0, "2026-03-20"),
        )
        # Target team, wrong season: scored 30, allowed 1 (should be excluded)
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g3", "2025-spring-hs", team_id, 999, 30, 1, "2025-03-20"),
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
            "INSERT INTO teams (name, public_id, season_year) "
            "VALUES ('Test Tigers', 'abc123', 2026)"
        )
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
            "INSERT INTO teams (name, public_id, season_year) "
            "VALUES ('Orphan Team', 'orphan1', 2026)"
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
            "INSERT INTO player_game_batting (game_id, player_id, team_id, ab, h) "
            "VALUES ('g1', 'p1', ?, 4, 2)",
            (subject_id,),
        )
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, ab, h) "
            "VALUES ('g1', 'p2', ?, 3, 1)",
            (orphan_id,),
        )
        # Spray chart for the game
        db.execute(
            "INSERT INTO spray_charts (game_id, team_id, player_id, season_id, "
            "chart_type, x, y) VALUES ('g1', ?, 'p2', '2026-spring-hs', 'offensive', 0.5, 0.5)",
            (orphan_id,),
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
            "INSERT INTO teams (name, public_id, season_year) "
            "VALUES ('Orphan', 'orphan2', 2026)"
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
            "INSERT INTO teams (name, public_id, season_year) "
            "VALUES ('Orphan', 'orp1', 2026)"
        )
        orphan_id = cursor.lastrowid
        db.commit()

        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("g1", "2026-spring-hs", subject_id, orphan_id, 5, 3, "2026-03-20"),
        )
        db.execute(
            "INSERT INTO player_game_batting (game_id, player_id, team_id, ab, h) "
            "VALUES ('g1', 'p1', ?, 4, 2)",
            (subject_id,),
        )
        db.execute(
            "INSERT INTO player_game_pitching (game_id, player_id, team_id, ip_outs, er) "
            "VALUES ('g1', 'p2', ?, 9, 2)",
            (orphan_id,),
        )
        db.commit()

        # Should not raise FK constraint error — orphan retained (shared game)
        count = cleanup_orphan_teams(db, {orphan_id})
        assert count == 0  # orphan team kept due to shared game FK

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
            "batting_team_id, batter_id, pitcher_id) VALUES ('g-shared', 1, 1, "
            "'top', '2026-spring-hs', 1, 'p-shared', 'p-shared')"
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
        mock_loader = MagicMock()

        # Make loader create an orphan team during load
        def _load_side_effect(scouting_dir, team_id, season_id):
            conn = original_fresh()
            conn.execute(
                "INSERT INTO teams (name, public_id, season_year) "
                "VALUES ('Orphan', 'orphan99', 2026)"
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
        mock_loader = MagicMock()

        # Loader creates orphan team + game so queries have data to find.
        # The DB season_id is derived from team metadata (season_year=2026,
        # no program) = "2026".
        def _load_side_effect(scouting_dir, team_id, season_id):
            conn = _fresh_conn()
            cursor = conn.execute(
                "INSERT INTO teams (name, public_id, season_year) "
                "VALUES ('Opponent', 'opp99', 2026)"
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
        mock_crawler.scout_team.return_value = CrawlResult(files_written=5)
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
