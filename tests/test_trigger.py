# synthetic-test-data
"""Tests for src/pipeline/trigger.py -- background crawl trigger functions.

Verifies that crawl_jobs rows are updated to the correct terminal status
and that teams.last_synced is updated on success (and NOT updated on failure)
for both run_member_sync and run_scouting_sync.

HTTP and pipeline modules are mocked; a real SQLite database is used to
verify DB state changes.

Run with:
    pytest tests/test_trigger.py -v
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.gamechanger.crawlers import CrawlResult  # noqa: E402
from src.gamechanger.loaders import LoadResult  # noqa: E402
from src.pipeline import trigger  # noqa: E402


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    """Create a migrated test database with a single member team."""
    db_path = tmp_path / "test_trigger.db"
    run_migrations(db_path=db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB Varsity', 'member')"
        )
        conn.commit()
    return db_path


def _insert_crawl_job(db_path: Path, team_id: int, sync_type: str) -> int:
    """Insert a running crawl_job row and return its id."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        cur = conn.execute(
            "INSERT INTO crawl_jobs (team_id, sync_type, status, started_at) "
            "VALUES (?, ?, 'running', datetime('now'))",
            (team_id, sync_type),
        )
        conn.commit()
        return cur.lastrowid


def _get_crawl_job(db_path: Path, job_id: int) -> dict:
    """Return status, completed_at, error_message for a crawl_jobs row."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute(
            "SELECT status, completed_at, error_message FROM crawl_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return {"status": row[0], "completed_at": row[1], "error_message": row[2]}


def _get_last_synced(db_path: Path, team_id: int) -> str | None:
    """Return teams.last_synced for the given team, or None if not set."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute(
            "SELECT last_synced FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
    return row[0] if row else None


def _insert_scouting_run(
    db_path: Path, team_id: int, season_id: str = "2025"
) -> None:
    """Pre-insert a scouting_runs row visible after the mock crawl completes.

    Uses a far-future last_checked so that trigger.py's
    ``last_checked >= started_at`` filter always matches.
    """
    with closing(sqlite3.connect(str(db_path))) as conn:
        # seasons FK required
        conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
            "VALUES (?, 'Spring 2025', 'spring-hs', 2025)",
            (season_id,),
        )
        conn.execute(
            "INSERT INTO scouting_runs "
            "(team_id, season_id, status, last_checked) "
            "VALUES (?, ?, 'running', '2099-12-31T00:00:00.000Z')",
            (team_id, season_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# run_member_sync
# ---------------------------------------------------------------------------


class TestMemberSync:
    def test_auth_failure_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch(
                "src.pipeline.trigger._refresh_auth_token",
                side_effect=RuntimeError("no credentials"),
            ),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "Auth refresh failed" in job["error_message"]
        assert "no credentials" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_pipeline_raises_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch(
                "src.pipeline.trigger.crawl_module.run",
                side_effect=RuntimeError("crawl exploded"),
            ),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "crawl exploded" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_nonzero_exit_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=1),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "crawl_exit=1" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_success_marks_job_completed_updates_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        assert job["completed_at"] is not None
        assert job["error_message"] is None
        assert _get_last_synced(db_path, 1) is not None


# ---------------------------------------------------------------------------
# run_scouting_sync
# ---------------------------------------------------------------------------


class TestScoutingSync:
    def test_auth_failure_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch(
                "src.pipeline.trigger._refresh_auth_token",
                side_effect=RuntimeError("no credentials"),
            ),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "Auth refresh failed" in job["error_message"]
        assert _get_last_synced(db_path, 1) is None

    def test_crawl_errors_marks_job_failed_no_last_synced(self, tmp_path: Path) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(errors=1, files_written=0)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert _get_last_synced(db_path, 1) is None

    def test_load_failure_marks_job_failed_updates_scouting_run(
        self, tmp_path: Path
    ) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")
        _insert_scouting_run(db_path, team_id=1, season_id="2025")

        scouting_dir = tmp_path / "raw" / "2025" / "scouting" / "test-team-slug"
        scouting_dir.mkdir(parents=True)

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(files_written=3)
        mock_loader = MagicMock()
        mock_loader.load_team.side_effect = RuntimeError("load crashed")

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
            patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
            patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        mock_crawler.update_run_load_status.assert_called_once_with(1, "2025", "failed")
        assert _get_last_synced(db_path, 1) is None

    def test_success_marks_job_completed_updates_last_synced(
        self, tmp_path: Path
    ) -> None:
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")
        _insert_scouting_run(db_path, team_id=1, season_id="2025")

        scouting_dir = tmp_path / "raw" / "2025" / "scouting" / "test-team-slug"
        scouting_dir.mkdir(parents=True)

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(files_written=3)
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
            patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
            patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
        ):
            trigger.run_scouting_sync(1, "test-team-slug", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        assert job["completed_at"] is not None
        assert job["error_message"] is None
        mock_crawler.update_run_load_status.assert_called_once_with(1, "2025", "completed")
        assert _get_last_synced(db_path, 1) is not None


# ---------------------------------------------------------------------------
# E-147-03: Self-healing season_year propagation
# ---------------------------------------------------------------------------


def _get_season_year(db_path: Path, team_id: int) -> int | None:
    """Return teams.season_year for the given team."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute(
            "SELECT season_year FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
    return row[0] if row else None


def _set_team_gc_uuid(db_path: Path, team_id: int, gc_uuid: str) -> None:
    """Set gc_uuid on a team row."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("UPDATE teams SET gc_uuid = ? WHERE id = ?", (gc_uuid, team_id))
        conn.commit()


def _set_team_public_id(db_path: Path, team_id: int, public_id: str) -> None:
    """Set public_id on a team row."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("UPDATE teams SET public_id = ? WHERE id = ?", (public_id, team_id))
        conn.commit()


def _set_season_year(db_path: Path, team_id: int, year: int) -> None:
    """Set season_year on a team row."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("UPDATE teams SET season_year = ? WHERE id = ?", (year, team_id))
        conn.commit()


class TestMemberSyncSeasonYearHeal:
    """E-147-03 AC-1: member sync heals NULL season_year."""

    def test_null_season_year_updated_on_sync(self, tmp_path: Path) -> None:
        """When season_year is NULL and gc_uuid exists, sync populates it."""
        db_path = _make_db(tmp_path)
        _set_team_gc_uuid(db_path, 1, "gc-uuid-123")
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_client = MagicMock()
        mock_client.get.return_value = {"season_year": 2026}

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token", return_value=mock_client),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        assert _get_season_year(db_path, 1) == 2026
        mock_client.get.assert_called_once_with(
            "/teams/gc-uuid-123",
            accept="application/vnd.gc.com.team+json; version=0.10.0",
        )

    def test_non_null_season_year_not_overwritten(self, tmp_path: Path) -> None:
        """When season_year is already set, sync does not make the API call."""
        db_path = _make_db(tmp_path)
        _set_team_gc_uuid(db_path, 1, "gc-uuid-123")
        _set_season_year(db_path, 1, 2025)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_client = MagicMock()

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token", return_value=mock_client),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        assert _get_season_year(db_path, 1) == 2025
        mock_client.get.assert_not_called()

    def test_no_gc_uuid_skips_gracefully(self, tmp_path: Path) -> None:
        """When gc_uuid is NULL, no API call is made."""
        db_path = _make_db(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_client = MagicMock()

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token", return_value=mock_client),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        assert _get_season_year(db_path, 1) is None
        mock_client.get.assert_not_called()


class TestScoutingSyncSeasonYearHeal:
    """E-147-03 AC-2: scouting sync heals NULL season_year."""

    def test_null_season_year_updated_on_scouting_sync(self, tmp_path: Path) -> None:
        """When season_year is NULL, scouting sync populates via resolve_team."""
        db_path = _make_db(tmp_path)
        _set_team_public_id(db_path, 1, "test-slug")
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")
        _insert_scouting_run(db_path, 1)

        from src.gamechanger.team_resolver import TeamProfile
        mock_profile = TeamProfile(public_id="test-slug", name="Test", sport="baseball", year=2026)

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(files_written=3)
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

        scouting_dir = tmp_path / "raw" / "2025" / "scouting" / "test-slug"
        scouting_dir.mkdir(parents=True)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.resolve_team", return_value=mock_profile),
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
            patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
            patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
        ):
            trigger.run_scouting_sync(1, "test-slug", job_id)

        assert _get_season_year(db_path, 1) == 2026

    def test_non_null_season_year_not_overwritten_scouting(self, tmp_path: Path) -> None:
        """When season_year is already set, scouting sync does not call resolve_team."""
        db_path = _make_db(tmp_path)
        _set_team_public_id(db_path, 1, "test-slug")
        _set_season_year(db_path, 1, 2025)
        job_id = _insert_crawl_job(db_path, 1, "scouting_crawl")
        _insert_scouting_run(db_path, 1)

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = CrawlResult(files_written=3)
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)

        scouting_dir = tmp_path / "raw" / "2025" / "scouting" / "test-slug"
        scouting_dir.mkdir(parents=True)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.resolve_team") as mock_resolve,
            patch("src.pipeline.trigger.ScoutingCrawler", return_value=mock_crawler),
            patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
            patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
        ):
            trigger.run_scouting_sync(1, "test-slug", job_id)

        assert _get_season_year(db_path, 1) == 2025
        mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# E-147-03: Season year mismatch warning guard
# ---------------------------------------------------------------------------


class TestSeasonYearMismatchWarning:
    """E-147-03 AC-3: loaders emit WARNING on year mismatch."""

    def test_mismatch_warning_logged(self, tmp_path: Path) -> None:
        """warn_season_year_mismatch emits WARNING when years differ."""
        from src.gamechanger.loaders import warn_season_year_mismatch

        db_path = tmp_path / "test_warn.db"
        run_migrations(db_path=db_path)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute(
                "INSERT INTO teams (id, name, membership_type, season_year) "
                "VALUES (1, 'Test Team', 'member', 2025)"
            )
            conn.commit()

            import logging
            with patch.object(logging.getLogger("src.gamechanger.loaders"), "warning") as mock_warn:
                warn_season_year_mismatch(conn, 1, "2026-spring-hs", "TestLoader")
            mock_warn.assert_called_once()
            call_msg = mock_warn.call_args[0][0] % mock_warn.call_args[0][1:]
            assert "mismatch" in call_msg.lower()
            assert "2025" in call_msg
            assert "2026" in call_msg

    def test_no_warning_when_years_match(self, tmp_path: Path) -> None:
        """No warning when teams.season_year matches the data year."""
        from src.gamechanger.loaders import warn_season_year_mismatch

        db_path = tmp_path / "test_warn.db"
        run_migrations(db_path=db_path)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute(
                "INSERT INTO teams (id, name, membership_type, season_year) "
                "VALUES (1, 'Test Team', 'member', 2025)"
            )
            conn.commit()

            import logging
            with patch.object(logging.getLogger("src.gamechanger.loaders"), "warning") as mock_warn:
                warn_season_year_mismatch(conn, 1, "2025-spring-hs", "TestLoader")
            mock_warn.assert_not_called()

    def test_no_warning_when_season_year_null(self, tmp_path: Path) -> None:
        """No warning when teams.season_year is NULL."""
        from src.gamechanger.loaders import warn_season_year_mismatch

        db_path = tmp_path / "test_warn.db"
        run_migrations(db_path=db_path)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute(
                "INSERT INTO teams (id, name, membership_type) "
                "VALUES (1, 'Test Team', 'member')"
            )
            conn.commit()

            import logging
            with patch.object(logging.getLogger("src.gamechanger.loaders"), "warning") as mock_warn:
                warn_season_year_mismatch(conn, 1, "2026-spring-hs", "TestLoader")
            mock_warn.assert_not_called()


# ---------------------------------------------------------------------------
# CLI scouting season_year self-heal
# ---------------------------------------------------------------------------


class TestCliScoutingSeasonYearHeal:
    """CLI scouting pipeline heals season_year via _heal_season_year_cli."""

    def _make_tracked_db(self, tmp_path: Path) -> Path:
        db_path = tmp_path / "test_cli_heal.db"
        run_migrations(db_path=db_path)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute(
                "INSERT INTO teams (id, name, membership_type, public_id) "
                "VALUES (1, 'Opponent A', 'tracked', 'opp-slug-a')"
            )
            conn.execute(
                "INSERT INTO teams (id, name, membership_type, public_id) "
                "VALUES (2, 'Opponent B', 'tracked', 'opp-slug-b')"
            )
            conn.commit()
        return db_path

    def test_single_team_heal(self, tmp_path: Path) -> None:
        """_heal_season_year_cli heals a single team by public_id."""
        from src.cli.data import _heal_season_year_cli

        db_path = self._make_tracked_db(tmp_path)
        mock_profile = MagicMock()
        mock_profile.year = 2025

        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            with patch("src.gamechanger.team_resolver.resolve_team", return_value=mock_profile) as mock_resolve:
                _heal_season_year_cli(conn, "opp-slug-a")

            row = conn.execute("SELECT season_year FROM teams WHERE id = 1").fetchone()
            assert row[0] == 2025
            mock_resolve.assert_called_once_with("opp-slug-a")

            # Team 2 should be untouched
            row2 = conn.execute("SELECT season_year FROM teams WHERE id = 2").fetchone()
            assert row2[0] is None

    def test_all_teams_heal(self, tmp_path: Path) -> None:
        """_heal_season_year_cli heals all tracked teams when team=None."""
        from src.cli.data import _heal_season_year_cli

        db_path = self._make_tracked_db(tmp_path)
        mock_profile = MagicMock()
        mock_profile.year = 2026

        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            with patch("src.gamechanger.team_resolver.resolve_team", return_value=mock_profile) as mock_resolve:
                _heal_season_year_cli(conn, None)

            row1 = conn.execute("SELECT season_year FROM teams WHERE id = 1").fetchone()
            row2 = conn.execute("SELECT season_year FROM teams WHERE id = 2").fetchone()
            assert row1[0] == 2026
            assert row2[0] == 2026
            assert mock_resolve.call_count == 2

    def test_already_populated_skipped(self, tmp_path: Path) -> None:
        """Teams with season_year already set are not healed."""
        from src.cli.data import _heal_season_year_cli

        db_path = self._make_tracked_db(tmp_path)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("UPDATE teams SET season_year = 2024 WHERE id = 1")
            conn.commit()

            with patch("src.gamechanger.team_resolver.resolve_team") as mock_resolve:
                _heal_season_year_cli(conn, "opp-slug-a")

            mock_resolve.assert_not_called()
            row = conn.execute("SELECT season_year FROM teams WHERE id = 1").fetchone()
            assert row[0] == 2024

    def test_pre_migration_db_degrades_gracefully(self, tmp_path: Path) -> None:
        """On a DB without the season_year column, heal silently returns."""
        from src.cli.data import _heal_season_year_cli

        db_path = tmp_path / "test_pre_mig.db"
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute(
                "CREATE TABLE teams ("
                "  id INTEGER PRIMARY KEY,"
                "  name TEXT NOT NULL,"
                "  membership_type TEXT NOT NULL DEFAULT 'tracked',"
                "  public_id TEXT"
                ")"
            )
            conn.execute(
                "INSERT INTO teams (id, name, public_id) VALUES (1, 'Old Team', 'old-slug')"
            )
            conn.commit()

            # Should not raise -- OperationalError is caught internally
            _heal_season_year_cli(conn, "old-slug")
            _heal_season_year_cli(conn, None)


# ---------------------------------------------------------------------------
# E-152-02: Opponent discovery wired into run_member_sync
# ---------------------------------------------------------------------------

# A valid UUID for the test member team.
_TEST_GC_UUID = "72bb77d8-54ca-42d2-8547-9da4880d0cb4"
_TEST_SEASON_ID = "2026-spring-hs"


def _make_db_with_season(
    tmp_path: Path,
    gc_uuid: str = _TEST_GC_UUID,
    season_id: str = _TEST_SEASON_ID,
) -> Path:
    """Create a migrated test DB with a member team + seasons row."""
    db_path = tmp_path / "test_trigger_disc.db"
    run_migrations(db_path=db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute(
            "INSERT INTO seasons (season_id, name, season_type, year) "
            "VALUES (?, 'Spring 2026', 'spring-hs', 2026)",
            (season_id,),
        )
        conn.execute(
            "INSERT INTO teams (id, name, membership_type, gc_uuid, is_active) "
            "VALUES (1, 'LSB Varsity', 'member', ?, 1)",
            (gc_uuid,),
        )
        conn.commit()
    return db_path


class TestMemberSyncOpponentDiscovery:
    """E-152-02: Schedule seeder + OpponentResolver wired into run_member_sync."""

    def test_ac2_seeder_called_before_resolver(self, tmp_path: Path) -> None:
        """AC-2: Both seeder and resolver called; seeder executes before resolver."""
        db_path = _make_db_with_season(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")
        call_order: list[str] = []

        def _mock_seeder(*_args, **_kwargs) -> int:
            call_order.append("seeder")
            return 3

        mock_resolver_instance = MagicMock()
        mock_resolver_instance.resolve.side_effect = lambda: call_order.append("resolver")
        mock_resolver_class = MagicMock(return_value=mock_resolver_instance)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.seed_schedule_opponents", side_effect=_mock_seeder),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        assert call_order == ["seeder", "resolver"], (
            f"Expected seeder then resolver; got: {call_order}"
        )
        assert mock_resolver_instance.resolve.call_count == 1

    def test_ac2_resolve_unlinked_not_called(self, tmp_path: Path) -> None:
        """AC-2: resolve_unlinked() must NOT be called -- only resolve()."""
        db_path = _make_db_with_season(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_resolver_instance = MagicMock()
        mock_resolver_instance.resolve.return_value = None
        mock_resolver_class = MagicMock(return_value=mock_resolver_instance)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.seed_schedule_opponents", return_value=0),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        mock_resolver_instance.resolve_unlinked.assert_not_called()

    def test_ac3_opponent_count_matches_schedule(self, tmp_path: Path) -> None:
        """AC-3: opponent_links count matches distinct opponents in schedule.json."""
        db_path = _make_db_with_season(tmp_path)

        # Write a fake schedule.json with 3 distinct opponents across 5 events.
        season_dir = tmp_path / "raw" / _TEST_SEASON_ID / "teams" / _TEST_GC_UUID
        season_dir.mkdir(parents=True)
        schedule = [
            {"event": {"event_type": "game"}, "pregame_data": {"opponent_id": "opp-a", "opponent_name": "Team A"}},
            {"event": {"event_type": "game"}, "pregame_data": {"opponent_id": "opp-b", "opponent_name": "Team B"}},
            {"event": {"event_type": "game"}, "pregame_data": {"opponent_id": "opp-a", "opponent_name": "Team A"}},  # duplicate
            {"event": {"event_type": "game"}, "pregame_data": {"opponent_id": "opp-c", "opponent_name": "Team C"}},
            {"event": {"event_type": "practice"}},  # skipped
        ]
        (season_dir / "schedule.json").write_text(json.dumps(schedule), encoding="utf-8")

        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_resolver_instance = MagicMock()
        mock_resolver_instance.resolve.return_value = None
        mock_resolver_class = MagicMock(return_value=mock_resolver_instance)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
            patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        with closing(sqlite3.connect(str(db_path))) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM opponent_links WHERE our_team_id = 1"
            ).fetchone()[0]
        assert count == 3, f"Expected 3 unique opponents; got {count}"

    def test_ac4a_seeder_failure_nonfatal_job_completes(self, tmp_path: Path) -> None:
        """AC-4a: Seeder failure is non-fatal -- job completes and resolver still runs."""
        db_path = _make_db_with_season(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_resolver_instance = MagicMock()
        mock_resolver_instance.resolve.return_value = None
        mock_resolver_class = MagicMock(return_value=mock_resolver_instance)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch(
                "src.pipeline.trigger.seed_schedule_opponents",
                side_effect=RuntimeError("seeder crash"),
            ),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        assert _get_last_synced(db_path, 1) is not None
        # Resolver still runs after seeder failure.
        assert mock_resolver_instance.resolve.call_count == 1

    def test_ac4b_credential_expired_propagates_marks_job_failed(
        self, tmp_path: Path
    ) -> None:
        """AC-4b: CredentialExpiredError from resolver propagates; job marked failed."""
        from src.gamechanger.client import CredentialExpiredError as CrError

        db_path = _make_db_with_season(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_resolver_instance = MagicMock()
        mock_resolver_instance.resolve.side_effect = CrError("token dead")
        mock_resolver_class = MagicMock(return_value=mock_resolver_instance)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.seed_schedule_opponents", return_value=0),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
        ):
            with pytest.raises(CrError):
                trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "failed"
        assert "Credential expired" in job["error_message"]

    def test_ac4c_non_auth_resolver_errors_dont_fail_job(
        self, tmp_path: Path
    ) -> None:
        """AC-4c: Non-auth resolver errors handled internally; job completes normally."""
        from src.gamechanger.crawlers.opponent_resolver import ResolveResult

        db_path = _make_db_with_season(tmp_path)
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_resolver_instance = MagicMock()
        # Resolver returns normally with per-opponent errors (handled internally).
        mock_resolver_instance.resolve.return_value = ResolveResult(resolved=3, errors=2)
        mock_resolver_class = MagicMock(return_value=mock_resolver_instance)

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.seed_schedule_opponents", return_value=5),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        assert _get_last_synced(db_path, 1) is not None

    def test_ac5_idempotent_discovery_no_duplicates(self, tmp_path: Path) -> None:
        """AC-5: Two syncs with the same schedule produce no duplicate opponent_links rows."""
        db_path = _make_db_with_season(tmp_path)

        # Write a fake schedule.json with 2 distinct opponents (real seeder, no mock).
        season_dir = tmp_path / "raw" / _TEST_SEASON_ID / "teams" / _TEST_GC_UUID
        season_dir.mkdir(parents=True)
        schedule = [
            {"event": {"event_type": "game"}, "pregame_data": {"opponent_id": "opp-a", "opponent_name": "Team A"}},
            {"event": {"event_type": "game"}, "pregame_data": {"opponent_id": "opp-b", "opponent_name": "Team B"}},
            {"event": {"event_type": "game"}, "pregame_data": {"opponent_id": "opp-a", "opponent_name": "Team A"}},  # duplicate
        ]
        (season_dir / "schedule.json").write_text(json.dumps(schedule), encoding="utf-8")

        mock_resolver_instance = MagicMock()
        mock_resolver_instance.resolve.return_value = None
        mock_resolver_class = MagicMock(return_value=mock_resolver_instance)

        for run_num in (1, 2):
            job_id = _insert_crawl_job(db_path, 1, "member_crawl")
            with (
                patch("src.pipeline.trigger.get_db_path", return_value=db_path),
                patch("src.pipeline.trigger._refresh_auth_token"),
                patch("src.pipeline.trigger.crawl_module.run", return_value=0),
                patch("src.pipeline.trigger.load_module.run", return_value=0),
                patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
                patch("src.pipeline.trigger._DATA_ROOT", tmp_path / "raw"),
            ):
                trigger.run_member_sync(1, "LSB Varsity", job_id)
            job = _get_crawl_job(db_path, job_id)
            assert job["status"] == "completed", f"Run {run_num} failed unexpectedly"

        # No duplicate rows: exactly 2 distinct opponents in opponent_links.
        with closing(sqlite3.connect(str(db_path))) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM opponent_links WHERE our_team_id = 1"
            ).fetchone()[0]
        assert count == 2, f"Expected 2 unique opponent rows; got {count}"

    def test_ac6_resolver_receives_filtered_config(self, tmp_path: Path) -> None:
        """AC-6: OpponentResolver receives CrawlConfig filtered to only the syncing team."""
        gc_uuid_2 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        db_path = _make_db_with_season(tmp_path)

        # Add a second member team.
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute(
                "INSERT INTO teams (id, name, membership_type, gc_uuid, is_active) "
                "VALUES (2, 'LSB JV', 'member', ?, 1)",
                (gc_uuid_2,),
            )
            conn.commit()

        job_id = _insert_crawl_job(db_path, 1, "member_crawl")
        captured: dict = {}

        def _mock_resolver_factory(client, config, db):
            captured["config"] = config
            inst = MagicMock()
            inst.resolve.return_value = None
            return inst

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.seed_schedule_opponents", return_value=0),
            patch("src.pipeline.trigger.OpponentResolver", _mock_resolver_factory),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        assert "config" in captured, "OpponentResolver was never constructed"
        cfg = captured["config"]
        assert len(cfg.member_teams) == 1, (
            f"Expected 1 team in filtered config; got {len(cfg.member_teams)}"
        )
        assert cfg.member_teams[0].internal_id == 1

    def test_discovery_skipped_when_no_seasons_configured(
        self, tmp_path: Path
    ) -> None:
        """Discovery is skipped gracefully when no seasons row exists; job completes."""
        db_path = _make_db(tmp_path)  # no seasons row
        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_seeder = MagicMock()
        mock_resolver_class = MagicMock()

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.seed_schedule_opponents", mock_seeder),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        mock_seeder.assert_not_called()
        mock_resolver_class.assert_not_called()

    def test_discovery_skipped_when_no_gc_uuid(self, tmp_path: Path) -> None:
        """Discovery is skipped gracefully when the team has no gc_uuid; job completes."""
        db_path = tmp_path / "test_no_uuid.db"
        run_migrations(db_path=db_path)
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.execute(
                "INSERT INTO seasons (season_id, name, season_type, year) "
                "VALUES ('2026-spring-hs', 'Spring 2026', 'spring-hs', 2026)"
            )
            # Team has no gc_uuid (membership_type='member' but gc_uuid NULL).
            conn.execute(
                "INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB Varsity', 'member')"
            )
            conn.commit()

        job_id = _insert_crawl_job(db_path, 1, "member_crawl")

        mock_seeder = MagicMock()
        mock_resolver_class = MagicMock()

        with (
            patch("src.pipeline.trigger.get_db_path", return_value=db_path),
            patch("src.pipeline.trigger._refresh_auth_token"),
            patch("src.pipeline.trigger.crawl_module.run", return_value=0),
            patch("src.pipeline.trigger.load_module.run", return_value=0),
            patch("src.pipeline.trigger.seed_schedule_opponents", mock_seeder),
            patch("src.pipeline.trigger.OpponentResolver", mock_resolver_class),
        ):
            trigger.run_member_sync(1, "LSB Varsity", job_id)

        job = _get_crawl_job(db_path, job_id)
        assert job["status"] == "completed"
        mock_seeder.assert_not_called()
        mock_resolver_class.assert_not_called()


