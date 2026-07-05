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

from src.db.teams import EnsureTeamResult
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


def _seed_season(db, season_id="2026"):
    db.execute(
        "INSERT INTO seasons (season_id, name, year) "
        "VALUES (?, ?, 2026)",
        (season_id, season_id),
    )
    db.commit()


def _seed_scouting_run(db, team_id=1, season_id="2026"):
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
# AC-1: no-completed-games -> explicit no-games outcome (E-235-03 gate (a))
# ---------------------------------------------------------------------------
class TestNoCompletedGamesExplicitOutcome:
    """The zero-completed-games crawl now produces an explicit no-games
    outcome (E-235-03 gate (a)) -- the AFTER-anchor for what was previously the
    ready-but-empty before-anchor.
    """

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>empty</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_zero_games_yields_explicit_no_games_outcome(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, mock_create_session, db, tmp_path,
    ):
        """AFTER-anchor (E-235-03 gate (a)): a crawl returning zero completed
        games with zero errors, plus a load of zero rows, now produces the
        EXPLICIT no-games terminal outcome -- ``reports.status = 'no_games'``
        with a minimal shareable explanatory page -- instead of a silent
        ready-but-empty report. This is the ONE intended negative-path behavior
        change in Epic B (ROADMAP §6: gates are the only new behavior).
        """
        _seed_team(db)
        _seed_season(db)
        _seed_scouting_run(db)

        mock_get_conn.side_effect = _fresh_conn_factory(str(tmp_path / "test.db"))
        mock_create_session.return_value = _session_that_fails()
        mock_client_cls.return_value = MagicMock()

        mock_crawler = MagicMock()
        # Zero completed games, zero errors -- the no-games trigger.
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026",
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

        # AFTER behavior: explicit no-games outcome (NOT a ready report).
        assert result.success is False, (
            "no-games is an explicit terminal outcome, not a successful report"
        )
        # E-236-05 AC-5: the new outcome contract -- success stays False, the
        # finer-grained signal is "no_games".
        assert result.outcome == "no_games"
        assert result.slug is not None
        assert result.error_message is not None
        assert "No completed games found" in result.error_message

        verify_conn = _fresh_conn_factory(str(tmp_path / "test.db"))()
        row = verify_conn.execute(
            "SELECT status, report_path FROM reports WHERE slug = ?",
            (result.slug,),
        ).fetchone()
        verify_conn.close()
        assert row[0] == "no_games", (
            "gate (a): empty report now persists status='no_games', not 'ready'."
        )
        # A shareable explanatory page was written to disk (not a 404).
        assert row[1] == f"reports/{result.slug}.html"
        page = (tmp_path / "data" / row[1]).read_text(encoding="utf-8")
        # E-236-05 AC-2: M=0 (games=[], games_crawled=0) -> "no games on record".
        assert "No games on record" in page
        assert "check back later" not in page.lower()  # AC-3 negative

        # The full report render stage did NOT run (minimal page written instead).
        mock_render.assert_not_called()

    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>empty</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_no_games_run_record_distinguishes_m0_from_n0(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, mock_create_session, db, tmp_path,
    ):
        """AC-1: the run record captures completed_games (M) vs
        completed_games_with_data (N) so the operator can tell "no games played
        yet" (M=0) from "games played, none loaded" (M>0, N=0)."""
        _seed_team(db)
        _seed_season(db)
        _seed_scouting_run(db)

        mock_get_conn.side_effect = _fresh_conn_factory(str(tmp_path / "test.db"))
        mock_create_session.return_value = _session_that_fails()
        mock_client_cls.return_value = MagicMock()

        mock_crawler = MagicMock()
        # M = 2 completed games on the schedule, but zero loaded with data (N=0).
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026",
            games_crawled=2, errors=0,
            games=[{"game_status": "completed"}, {"game_status": "completed"}],
            boxscores={},
        )
        mock_loader = MagicMock()
        mock_loader.load_team.return_value = LoadResult(loaded=0)

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        assert result.success is False
        assert result.outcome == "no_games"  # E-236-05 AC-5
        verify_conn = _fresh_conn_factory(str(tmp_path / "test.db"))()
        verify_conn.row_factory = sqlite3.Row
        run = verify_conn.execute(
            "SELECT rgr.* FROM report_generation_runs rgr "
            "JOIN reports r ON r.id = rgr.report_id WHERE r.slug = ?",
            (result.slug,),
        ).fetchone()
        verify_conn.close()
        assert run is not None
        # M > 0 but N == 0 -> "games played, none loaded" sub-case.
        assert run["completed_games"] == 2
        assert run["completed_games_with_data"] == 0
        assert run["overall_status"] == "completed"

        # E-236-05 AC-2: the M>0/N=0 page interpolates M (games played = 2),
        # NOT N (0), and tells the coach box score data is unavailable.
        page_conn = _fresh_conn_factory(str(tmp_path / "test.db"))()
        prow = page_conn.execute(
            "SELECT report_path FROM reports WHERE slug = ?", (result.slug,),
        ).fetchone()
        page_conn.close()
        page = (tmp_path / "data" / prow[0]).read_text(encoding="utf-8")
        assert "has played 2 games this season" in page
        assert "no box score data is available in GameChanger" in page
        assert "has played 0 games" not in page  # must not interpolate N
        assert "check back later" not in page.lower()  # AC-3 negative

    @patch("src.reports.generator.cleanup_orphan_teams")
    @patch("src.http.session.create_session")
    @patch("src.reports.generator.get_connection")
    @patch("src.reports.generator.GameChangerClient")
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
    @patch("src.reports.generator.render_report", return_value="<html>x</html>")
    @patch("src.reports.generator._crawl_and_load_spray")
    @patch("src.reports.generator._crawl_and_load_plays", return_value=[])
    def test_no_games_abort_path_runs_orphan_cleanup(
        self, mock_plays, mock_spray, mock_render, mock_ensure,
        mock_client_cls, mock_get_conn, mock_create_session, mock_cleanup,
        db, tmp_path,
    ):
        """Path-symmetry: the no-games abort path still computes orphans and
        invokes cleanup (mirroring the normal render path), so a team a run
        created is not leaked just because the run produced no games."""
        _seed_team(db)
        _seed_season(db)
        _seed_scouting_run(db)

        db_path = str(tmp_path / "test.db")
        mock_get_conn.side_effect = _fresh_conn_factory(db_path)
        mock_create_session.return_value = _session_that_fails()
        mock_client_cls.return_value = MagicMock()

        mock_crawler = MagicMock()
        # Zero completed games with data -> the no-games gate fires.
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026",
            games_crawled=0, errors=0, games=[], boxscores={},
        )

        # The real ScoutingLoader records opponent stubs it INSERTs into the
        # per-run created-set (E-235-04). Capture the set the generator passes
        # to the loader constructor so the mock can record into it.
        captured: dict = {}

        # Loader creates an orphan team (id=2) during the load, as the real
        # scouting load does for opponent stubs.
        def _load_side_effect(crawl_result, **kwargs):
            conn = _fresh_conn_factory(db_path)()
            cursor = conn.execute(
                "INSERT INTO teams (name, public_id, season_year, membership_type) "
                "VALUES ('Orphan', 'orph9', 2026, 'tracked')"
            )
            opp_id = cursor.lastrowid
            conn.commit()
            conn.close()
            if captured.get("set") is not None:
                captured["set"].add(opp_id)
            return LoadResult(loaded=0)

        mock_loader = MagicMock()
        mock_loader.load_team.side_effect = _load_side_effect

        def _make_loader(conn, created_team_ids=None):
            captured["set"] = created_team_ids
            return mock_loader

        with (
            patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
            patch("src.reports.generator.ScoutingLoader", side_effect=_make_loader),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            result = generate_report("abc123")

        # No-games terminal outcome, AND orphan cleanup was invoked with the
        # loader-created orphan (id=2) -- the abort path is symmetric.
        assert result.success is False
        assert mock_cleanup.called, "abort path must still run orphan cleanup"
        cleaned_ids = mock_cleanup.call_args[0][1]
        assert 2 in cleaned_ids


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
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
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
        # A completed game WITH per-game stat data in the derived season ('2026',
        # from season_year=2026 with no program) so the no-games gate (a) does
        # not fire -- this test exercises the ready / name-fallback path. Post
        # E-235 Phase 4b HIGH-1, N requires a player_game_batting/pitching row,
        # so a bare games row alone is NOT "with data".
        db.execute(
            "INSERT INTO seasons (season_id, name, year) "
            "VALUES ('2026', '2026', 2026) ON CONFLICT(season_id) DO NOTHING"
        )
        db.execute(
            "INSERT INTO games (game_id, season_id, home_team_id, away_team_id, "
            "home_score, away_score, game_date) "
            "VALUES ('np-seed-g1', '2026', 1, 1, 5, 3, '2026-04-01')"
        )
        db.execute(
            "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
            "VALUES ('np-seed-p1', 'Seed', 'Player')"
        )
        db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES ('np-seed-g1', 'np-seed-p1', 1, 1, 3, 1)"
        )
        db.commit()

        mock_get_conn.side_effect = _fresh_conn_factory(str(tmp_path / "test.db"))
        # Public profile fetch FAILS -> team_name_from_api stays None.
        mock_create_session.return_value = _session_that_fails()
        mock_client_cls.return_value = MagicMock()

        mock_crawler = MagicMock()
        mock_crawler.scout_team.return_value = ScoutingCrawlResult(
            team_id=1, season_id="2026",
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
    @patch("src.reports.generator.ensure_team_row_with_provenance",
           return_value=EnsureTeamResult(1, "anchor", False))
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
