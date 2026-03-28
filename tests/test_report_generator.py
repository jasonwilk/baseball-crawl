"""Tests for the report generation pipeline (E-172-02)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.reports.generator import (
    GenerationResult,
    _build_boxscore_uuid_map,
    _create_report_row,
    _query_batting,
    _query_freshness,
    _query_pitching,
    _query_recent_games,
    _query_record,
    _query_roster,
    _resolve_and_crawl_spray,
    _update_report_failed,
    _update_report_ready,
    generate_report,
    list_reports,
)


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
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            gc_uuid TEXT UNIQUE,
            public_id TEXT UNIQUE,
            season_year INTEGER,
            membership_type TEXT DEFAULT 'tracked',
            classification TEXT,
            active INTEGER DEFAULT 1
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
            PRIMARY KEY (player_id, team_id, season_id)
        );
        CREATE TABLE spray_charts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    @patch("src.reports.generator._resolve_and_crawl_spray")
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
# Boxscore UUID extraction and fallback spray crawl
# ---------------------------------------------------------------------------


class TestBuildBoxscoreUuidMap:
    """Test _build_boxscore_uuid_map extracts opponent UUIDs from boxscore files."""

    def test_extracts_uuid_keys(self, tmp_path):
        """UUID keys (not matching public_id) are extracted per event_id."""
        public_id = "abc123"
        season_id = "2026-spring-hs"
        bs_dir = tmp_path / season_id / "scouting" / public_id / "boxscores"
        bs_dir.mkdir(parents=True)

        # Write two boxscore files with public_id + opponent UUID keys
        (bs_dir / "event-1.json").write_text(json.dumps({
            public_id: {"players": {}},
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee": {"players": {}},
        }))
        (bs_dir / "event-2.json").write_text(json.dumps({
            public_id: {"players": {}},
            "11111111-2222-3333-4444-555555555555": {"players": {}},
        }))

        with patch("src.reports.generator._DATA_ROOT", tmp_path):
            result = _build_boxscore_uuid_map(public_id, season_id)

        assert result == {
            "event-1": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "event-2": "11111111-2222-3333-4444-555555555555",
        }

    def test_returns_empty_when_no_boxscores_dir(self, tmp_path):
        with patch("src.reports.generator._DATA_ROOT", tmp_path):
            result = _build_boxscore_uuid_map("no-such-team", "2026-spring-hs")
        assert result == {}

    def test_skips_malformed_json(self, tmp_path):
        public_id = "teamX"
        season_id = "2026-spring-hs"
        bs_dir = tmp_path / season_id / "scouting" / public_id / "boxscores"
        bs_dir.mkdir(parents=True)

        (bs_dir / "bad.json").write_text("not valid json")
        (bs_dir / "good.json").write_text(json.dumps({
            public_id: {},
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee": {},
        }))

        with patch("src.reports.generator._DATA_ROOT", tmp_path):
            result = _build_boxscore_uuid_map(public_id, season_id)

        assert len(result) == 1
        assert "good" in result

    def test_skips_boxscore_with_no_uuid_key(self, tmp_path):
        """Boxscores that have only non-UUID keys produce no mapping."""
        public_id = "teamY"
        season_id = "2026-spring-hs"
        bs_dir = tmp_path / season_id / "scouting" / public_id / "boxscores"
        bs_dir.mkdir(parents=True)

        (bs_dir / "event-1.json").write_text(json.dumps({
            public_id: {},
            "other-slug": {},
        }))

        with patch("src.reports.generator._DATA_ROOT", tmp_path):
            result = _build_boxscore_uuid_map(public_id, season_id)

        assert result == {}


class TestResolveAndCrawlSprayFallback:
    """Test that _resolve_and_crawl_spray falls back to boxscore UUIDs."""

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator._resolve_gc_uuid_via_search", return_value=(None, None))
    @patch("src.reports.generator._build_boxscore_uuid_map")
    @patch("src.reports.generator._crawl_spray_via_boxscore_uuids")
    @patch("src.reports.generator.ScoutingSprayChartLoader")
    def test_fallback_to_boxscore_uuids_when_search_fails(
        self,
        mock_loader_cls,
        mock_crawl_via_bs,
        mock_build_map,
        mock_search,
        mock_get_conn,
        db,
    ):
        """When gc_uuid is NULL and search returns no match, use boxscore UUIDs."""
        team_id = _seed_team(db)

        # DB returns gc_uuid=NULL
        mock_get_conn.return_value = db

        uuid_map = {"event-1": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
        mock_build_map.return_value = uuid_map

        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        client = MagicMock()

        _resolve_and_crawl_spray(
            client,
            team_id=team_id,
            public_id="abc123",
            season_id="2026-spring-hs",
            team_info={"name": "Test Tigers", "season_year": 2026},
        )

        # Search was attempted
        mock_search.assert_called_once_with(client, "Test Tigers", 2026)
        # Boxscore UUID map was built
        mock_build_map.assert_called_once_with("abc123", "2026-spring-hs")
        # Crawl via boxscore UUIDs was called
        mock_crawl_via_bs.assert_called_once_with(
            client, "abc123", "2026-spring-hs", uuid_map
        )
        # Loader was called
        mock_loader.load_all.assert_called_once()

    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator._resolve_gc_uuid_via_search", return_value=(None, None))
    @patch("src.reports.generator._build_boxscore_uuid_map", return_value={})
    @patch("src.reports.generator._crawl_spray_via_boxscore_uuids")
    def test_no_boxscores_logs_warning_and_returns(
        self,
        mock_crawl_via_bs,
        mock_build_map,
        mock_search,
        mock_get_conn,
        db,
    ):
        """When search fails AND no boxscore files exist, spray is omitted."""
        team_id = _seed_team(db)
        mock_get_conn.return_value = db

        client = MagicMock()

        _resolve_and_crawl_spray(
            client,
            team_id=team_id,
            public_id="abc123",
            season_id="2026-spring-hs",
            team_info={"name": "Test Tigers", "season_year": 2026},
        )

        # Boxscore UUID crawl should NOT be called
        mock_crawl_via_bs.assert_not_called()

    @patch("src.reports.generator._resolve_gc_uuid_via_search")
    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    @patch("src.reports.generator.ScoutingSprayChartLoader")
    def test_gc_uuid_from_search_uses_normal_path(
        self,
        mock_loader_cls,
        mock_crawler_cls,
        mock_search,
        db,
        tmp_path,
    ):
        """When search resolves gc_uuid, the normal crawler path is used."""
        team_id = _seed_team(db)

        db_path = str(tmp_path / "test.db")
        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_search.return_value = ("resolved-uuid-1234", "abc123")

        mock_crawler = MagicMock()
        mock_crawler_cls.return_value = mock_crawler
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        client = MagicMock()

        with patch("src.reports.generator.get_connection", side_effect=_fresh_conn):
            _resolve_and_crawl_spray(
                client,
                team_id=team_id,
                public_id="abc123",
                season_id="2026-spring-hs",
                team_info={"name": "Test Tigers", "season_year": 2026},
            )

        # Normal crawler was used with the resolved gc_uuid
        mock_crawler.crawl_team.assert_called_once_with(
            "abc123", season_id="2026-spring-hs", gc_uuid="resolved-uuid-1234"
        )

    @patch("src.reports.generator.ScoutingSprayChartCrawler")
    @patch("src.reports.generator.ScoutingSprayChartLoader")
    def test_gc_uuid_already_in_db_skips_search(
        self,
        mock_loader_cls,
        mock_crawler_cls,
        db,
        tmp_path,
    ):
        """When gc_uuid is already in the DB, search is not attempted."""
        db.execute(
            "INSERT INTO teams (name, public_id, gc_uuid, season_year) VALUES (?, ?, ?, 2026)",
            ("DB Team", "dbteam", "existing-uuid-5678"),
        )
        db.commit()
        team_id = db.execute(
            "SELECT id FROM teams WHERE public_id = 'dbteam'"
        ).fetchone()[0]

        db_path = str(tmp_path / "test.db")
        def _fresh_conn():
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn

        mock_crawler = MagicMock()
        mock_crawler_cls.return_value = mock_crawler
        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        client = MagicMock()

        with (
            patch("src.reports.generator.get_connection", side_effect=_fresh_conn),
            patch("src.reports.generator._resolve_gc_uuid_via_search") as mock_search,
        ):
            _resolve_and_crawl_spray(
                client,
                team_id=team_id,
                public_id="dbteam",
                season_id="2026-spring-hs",
                team_info={"name": "DB Team", "season_year": 2026},
            )
            mock_search.assert_not_called()

        mock_crawler.crawl_team.assert_called_once()
