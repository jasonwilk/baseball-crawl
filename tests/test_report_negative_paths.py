"""Negative-path characterization tests for ``generate_report()`` (E-234-04).

These tests PIN THE CURRENT BEHAVIOR of the report pipeline under failure and
degraded-data conditions so Epic B's quality-gate work lands as a visible,
asserted diff. They characterize what the code does TODAY -- including the
known ready-but-empty degradation -- and must NOT require any ``src/`` fix to
pass (epic Non-Goals; story AC-5).

Cases (generator boundary):
* AC-1: zero completed games / zero loaded -> the **known** ready-but-empty
  outcome (before-anchor for Epic B's no-completed-games gate).
* AC-2: public-profile fetch failure -> generation still reaches a ready
  terminal outcome using the DB team-name fallback.
* AC-3: auth expiry at the crawl stage -> the report fails and downstream
  stages (load / spray / plays / render) do NOT run.

The roster-fetch-failure case lives one layer down in
``tests/test_scouting_crawler.py`` (it is a ``ScoutingCrawler`` concern, not a
generator-boundary one).

All seams are mocked at module level (the established
``tests/test_report_generator.py`` pattern). No real network or credentials:
``src.http.session.create_session`` is always patched so the best-effort public
profile fetch never touches the network.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.gamechanger.client import CredentialExpiredError
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
from src.gamechanger.loaders import LoadResult
from src.reports.generator import generate_report
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Fixtures / helpers (mirror tests/test_report_generator.py)
# ---------------------------------------------------------------------------
@pytest.fixture()
def db(tmp_path):
    """Disk-backed DB with the production schema (FK enforcement on)."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    load_real_schema(conn)
    conn.commit()
    yield conn
    conn.close()


def _seed_team(db, name="Test Tigers", public_id="abc123"):
    cursor = db.execute(
        "INSERT INTO teams (name, public_id, season_year, membership_type) "
        "VALUES (?, ?, 2026, 'tracked')",
        (name, public_id),
    )
    db.commit()
    return cursor.lastrowid


def _seed_season(db, season_id="2026-spring-hs"):
    db.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'spring', 2026)",
        (season_id, season_id),
    )
    db.commit()


def _seed_scouting_run(db, team_id=1, season_id="2026-spring-hs"):
    db.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status) "
        "VALUES (?, ?, 'full', '2026-03-28T00:00:00Z', 'completed')",
        (team_id, season_id),
    )
    db.commit()


def _fresh_conn_factory(db_path):
    """Return a callable producing fresh FK-enabled connections.

    ``generate_report`` wraps each ``get_connection()`` in ``closing(...)``, so
    the side_effect must hand back a NEW connection per call.
    """

    def _fresh_conn():
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    return _fresh_conn


def _session_that_fails():
    """A mock requests session whose .get raises (public profile fetch fails)."""
    session = MagicMock()
    session.get.side_effect = RuntimeError("network blocked in test")
    return session


# ---------------------------------------------------------------------------
# AC-1: ready-but-empty (KNOWN BUG -- Epic B before-anchor)
# ---------------------------------------------------------------------------
class TestNoCompletedGamesReadyButEmpty:
    """Characterize the ready-but-empty outcome of a zero-games crawl."""

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>empty</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_zero_games_zero_errors_yields_ready_but_empty(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, mock_create_session, db, tmp_path,
    ):
        """KNOWN BUG / Epic B before-anchor: a crawl returning zero completed
        games with **zero errors**, plus a load of zero rows with zero errors,
        passes BOTH error-gated guards (crawl-failure guard fires only on
        ``errors > 0 AND games_crawled == 0`` at generator.py:1098; load guard
        only on ``errors > 0`` at generator.py:1113). Generation therefore
        proceeds to the post-load render step and emits a status='ready' but
        EMPTY report.

        This asserts CURRENT behavior, NOT desired behavior. Epic B's
        no-completed-games quality gate is expected to change this outcome
        (e.g. to a 'failed'/'empty' terminal state); when it does, THIS test is
        the visible before-anchor that should be updated in the same change.
        """
        _seed_team(db)
        _seed_season(db)
        _seed_scouting_run(db)

        mock_get_conn.side_effect = _fresh_conn_factory(str(tmp_path / "test.db"))
        mock_create_session.return_value = _session_that_fails()
        mock_client_cls.return_value = MagicMock()

        mock_crawler = MagicMock()
        # Zero completed games, zero errors -- the ready-but-empty trigger.
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026-spring-hs",
            games_crawled=0, errors=0, games=[], boxscores={},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=0)  # errors=0

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        # CURRENT behavior: success + a 'ready' report row despite zero data.
        assert result.success is True, (
            "Before-anchor: zero-games crawl currently yields success=True "
            "(ready-but-empty). If this changed, Epic B's gate likely landed."
        )
        assert result.slug is not None

        verify_conn = _fresh_conn_factory(str(tmp_path / "test.db"))()
        row = verify_conn.execute(
            "SELECT status, error_message FROM reports WHERE slug = ?",
            (result.slug,),
        ).fetchone()
        verify_conn.close()
        assert row[0] == "ready", (
            "Before-anchor: empty report currently persists status='ready'."
        )
        assert row[1] is None

        # The render stage ran even though there was no data to render.
        mock_render.assert_called_once()


# ---------------------------------------------------------------------------
# AC-2: public-profile fetch failure -> ready via team-name fallback
# ---------------------------------------------------------------------------
class TestPublicProfileFetchFailure:
    """Extend the api-fail coverage: terminal/ready outcome + name fallback.

    ``test_report_generator.py::test_ac3_no_backfill_when_api_fails`` already
    asserts the no-public_id-backfill branch. This characterizes the
    *uncovered* behavior: generation still reaches a ready terminal state and
    the report title falls back to the DB team name when the public profile is
    unavailable.
    """

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>ok</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_profile_failure_reaches_ready_with_name_fallback(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, mock_create_session, db, tmp_path,
    ):
        db_name = "Waverly Vikings Varsity 2026"
        _seed_team(db, name=db_name)
        _seed_season(db)
        _seed_scouting_run(db)

        mock_get_conn.side_effect = _fresh_conn_factory(str(tmp_path / "test.db"))
        # Public profile fetch FAILS -> team_name_from_api stays None.
        mock_create_session.return_value = _session_that_fails()
        mock_client_cls.return_value = MagicMock()

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026-spring-hs",
            games_crawled=5, errors=0, games=[], boxscores={},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=5)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        # Reaches a ready terminal outcome despite the profile fetch failing.
        assert result.success is True
        verify_conn = _fresh_conn_factory(str(tmp_path / "test.db"))()
        status = verify_conn.execute(
            "SELECT status FROM reports WHERE slug = ?", (result.slug,)
        ).fetchone()[0]
        verify_conn.close()
        assert status == "ready"

        # Team-name fallback: with no API name, the title uses the DB team name.
        assert result.title == f"Scouting Report — {db_name}"


# ---------------------------------------------------------------------------
# AC-3: auth expiry at the crawl stage -> which stages ran
# ---------------------------------------------------------------------------
class TestAuthExpiryStageExecution:
    """Characterize stage execution when auth expires at the crawl stage.

    Complements the existing auth-expiry tests (which assert the error message
    and the non-fatal plays-stage case) by asserting WHICH pipeline stages did
    and did not run when ``scout_team`` raises ``CredentialExpiredError``.
    """

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row", return_value=1)
    @patch("src.reports.generator.render_report", return_value="<html>x</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_auth_expiry_at_crawl_skips_downstream_stages(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, mock_create_session, db, tmp_path,
    ):
        _seed_team(db)
        _seed_season(db)
        _seed_scouting_run(db)

        mock_get_conn.side_effect = _fresh_conn_factory(str(tmp_path / "test.db"))
        mock_create_session.return_value = _session_that_fails()
        mock_client_cls.return_value = MagicMock()

        mock_crawler = MagicMock()
        # Auth expires at the crawl stage.
        mock_crawler.scout_team.side_effect = CredentialExpiredError("token expired")
        mock_loader = MagicMock()

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        # Terminal outcome: failure with an auth-related message.
        assert result.success is False
        assert result.error_message is not None
        assert "expired" in result.error_message.lower()

        # The crawl stage WAS reached...
        mock_crawler.scout_team.assert_called_once()
        # ...but every downstream stage was skipped.
        mock_loader.load_team.assert_not_called()
        mock_spray.assert_not_called()
        mock_plays.assert_not_called()
        mock_render.assert_not_called()

        # The report row is terminal 'failed' (not stuck in 'generating').
        verify_conn = _fresh_conn_factory(str(tmp_path / "test.db"))()
        status = verify_conn.execute(
            "SELECT status FROM reports ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        verify_conn.close()
        assert status == "failed"
