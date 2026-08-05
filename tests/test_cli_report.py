"""Tests for bb report CLI commands (E-172-02)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.report import _apply_opponent_mapping, app
from src.gamechanger.team_resolver import TeamProfile
from src.reports.generator import GenerationResult
from src.reports.lifecycle import CleanupResult
from tests.conftest import load_real_schema

runner = CliRunner()


class TestGenerateCommand:
    """Test bb report generate CLI command."""

    def test_success_prints_url(self):
        mock_result = GenerationResult(
            success=True,
            slug="abc123def456",
            title="Scouting Report — Test Tigers",
            url="https://bbstats.ai/reports/abc123def456",
            outcome="ready",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "https://web.gc.com/teams/test/tigers"])

        assert result.exit_code == 0
        assert "abc123def456" in result.output
        assert "https://bbstats.ai/reports/abc123def456" in result.output
        assert "Test Tigers" in result.output

    def test_success_prints_reference_date(self):
        """E-256-05 AC-4: the printed reference date is Step 1d's headline
        invariant (E-256-11 asserts it equals today in the operating timezone).

        The machine-assertable shape is the literal prefix ``Reference date:``
        followed by an ISO-8601 ``YYYY-MM-DD``.
        """
        mock_result = GenerationResult(
            success=True,
            slug="abc123def456",
            title="Scouting Report — Test Tigers",
            url="https://bbstats.ai/reports/abc123def456",
            reference_date="2026-07-09",
            outcome="ready",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 0
        assert "Reference date: 2026-07-09" in result.output

    def test_success_without_reference_date_omits_the_line(self):
        """A legacy/failed-derivation result must not print an empty date line --
        Step 1d would then assert against `Reference date: `."""
        mock_result = GenerationResult(
            success=True,
            slug="abc",
            title="T",
            url="u",
            outcome="ready",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 0
        assert "Reference date:" not in result.output

    def test_failure_prints_error_and_exits_1(self):
        mock_result = GenerationResult(
            success=False,
            error_message="Scouting crawl failed.",
            outcome="failed",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 1
        assert "Scouting crawl failed" in result.output

    def test_no_games_m_zero_exits_zero_and_prints_url(self):
        """E-236-05 AC-4/AC-6 + Phase 4b MEDIUM: a no_games outcome is a
        shareable page, so the CLI exits 0 and prints the URL. M=0 (no games on
        record) reads as such."""
        mock_result = GenerationResult(
            success=False,
            slug="ng123",
            title="Scouting Report — Rival Varsity",
            url="https://bbstats.ai/reports/ng123",
            error_message=(
                "No completed games found for Rival Varsity this season. "
                "If this looks wrong, verify the team URL and try again."
            ),
            outcome="no_games",
            completed_games=0,
            completed_games_with_data=0,
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 0
        assert "https://bbstats.ai/reports/ng123" in result.output
        assert "No games on record" in result.output

    def test_no_games_m_positive_says_no_box_score_data(self):
        """Phase 4b MEDIUM: the modal M>0/N=0 case (games WERE played, box-score
        data missing) must NOT print the misleading 'No completed games found'
        line; it must convey games played + no box score data, exit 0 + URL."""
        mock_result = GenerationResult(
            success=False,
            slug="ng456",
            title="Scouting Report — Rival Varsity",
            url="https://bbstats.ai/reports/ng456",
            error_message=(
                "No completed games found for Rival Varsity this season. "
                "If this looks wrong, verify the team URL and try again."
            ),
            outcome="no_games",
            completed_games=8,
            completed_games_with_data=0,
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 0
        assert "https://bbstats.ai/reports/ng456" in result.output
        # Honest M-vs-N message: games played, box-score data missing.
        assert "Played 8 games this season" in result.output
        assert "no box score data" in result.output
        # Must NOT print the misleading "no completed games found" for M>0.
        assert "No completed games found" not in result.output

    def test_credential_error_prints_refresh_hint(self):
        mock_result = GenerationResult(
            success=False,
            slug="some-slug",
            error_message="Authentication credentials expired — refresh with `bb creds setup web`",
        )
        with patch("src.cli.report.generate_report", return_value=mock_result):
            result = runner.invoke(app, ["generate", "abc123"])

        assert result.exit_code == 1
        assert "bb creds setup web" in result.output


class TestListCommand:
    """Test bb report list CLI command."""

    def test_list_shows_table(self):
        mock_reports = [
            {
                "slug": "s1",
                "title": "Report A",
                "status": "ready",
                "generated_at": "2026-03-28T12:00:00Z",
                "expires_at": "2026-04-11T12:00:00Z",
                "url": "https://bbstats.ai/reports/s1",
                "is_expired": False,
            },
        ]
        with patch("src.cli.report.list_reports", return_value=mock_reports):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Report A" in result.output
        assert "ready" in result.output

    def test_list_shows_expired_label(self):
        mock_reports = [
            {
                "slug": "old",
                "title": "Old Report",
                "status": "ready",
                "generated_at": "2026-01-01T12:00:00Z",
                "expires_at": "2026-01-15T12:00:00Z",
                "url": "https://bbstats.ai/reports/old",
                "is_expired": True,
            },
        ]
        with patch("src.cli.report.list_reports", return_value=mock_reports):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "expired" in result.output

    def test_list_empty(self):
        with patch("src.cli.report.list_reports", return_value=[]):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No reports found" in result.output

    def test_no_games_report_shows_shareable_url(self):
        """Phase 4b MEDIUM-2: a no_games report exposes its URL (shareable
        page), while a failed report does not. A wide console avoids Rich
        truncating the URL cell."""
        from rich.console import Console

        mock_reports = [
            {
                "slug": "ng1", "title": "No Games Report", "status": "no_games",
                "generated_at": "2026-03-28T12:00:00Z",
                "expires_at": "2026-04-11T12:00:00Z",
                "url": "https://bbstats.ai/reports/ng1", "is_expired": False,
            },
            {
                "slug": "f1", "title": "Failed Report", "status": "failed",
                "generated_at": "2026-03-28T12:00:00Z",
                "expires_at": "2026-04-11T12:00:00Z",
                "url": "https://bbstats.ai/reports/f1", "is_expired": False,
            },
        ]
        with (
            patch("src.cli.report.list_reports", return_value=mock_reports),
            patch("src.cli.report.console", Console(width=200)),
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "reports/ng1" in result.output  # no_games link shown
        assert "reports/f1" not in result.output  # failed stays unlinked

    def test_help_text(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "report" in result.output.lower()


class TestCleanupCommand:
    """Test bb report cleanup CLI command (E-238-07)."""

    def test_cleanup_reports_files_removed(self):
        """AC-4: the command invokes the helper and reports the file count."""
        with patch(
            "src.cli.report.cleanup_expired_reports",
            return_value=CleanupResult(files_removed=3, errors=0),
        ) as mock_cleanup:
            result = runner.invoke(app, ["cleanup"])

        mock_cleanup.assert_called_once()
        assert result.exit_code == 0
        assert "3" in result.output
        assert "removed" in result.output.lower()

    def test_cleanup_reports_zero(self):
        """A no-op sweep (nothing expired) still exits 0 and reports 0."""
        with patch(
            "src.cli.report.cleanup_expired_reports",
            return_value=CleanupResult(files_removed=0, errors=0),
        ):
            result = runner.invoke(app, ["cleanup"])

        assert result.exit_code == 0
        assert "0" in result.output

    def test_cleanup_reports_errors(self):
        """Per-file errors are surfaced (without failing the command)."""
        with patch(
            "src.cli.report.cleanup_expired_reports",
            return_value=CleanupResult(files_removed=1, errors=2),
        ):
            result = runner.invoke(app, ["cleanup"])

        assert result.exit_code == 0
        assert "1" in result.output
        assert "2" in result.output

    def test_cleanup_helper_failure_surfaces_nonzero_exit(self):
        """Error path: if the helper raises, the command exits non-zero.

        ``bb report cleanup`` is an explicit operator action (unlike the
        opportunistic call), so a hard failure should not be silently
        swallowed -- the operator must see it.
        """
        with patch(
            "src.cli.report.cleanup_expired_reports",
            side_effect=RuntimeError("db unavailable"),
        ):
            result = runner.invoke(app, ["cleanup"])

        assert result.exit_code != 0
        assert result.exception is not None

    def test_cleanup_help(self):
        result = runner.invoke(app, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "expired" in result.output.lower()


# ---------------------------------------------------------------------------
# bb report map-opponent (E-240-05)
# ---------------------------------------------------------------------------

_ROOT = "root-aaaa-0000"
_PUBLIC_ID = "dD9PtF0YbKad"


def _seed_db_with_pending(
    db_path: Path, *, team_ids: tuple[int, ...] = (1,), root_team_id: str = _ROOT
) -> None:
    """Create a disk DB with the real schema + a pending opponent_links row per team."""
    conn = sqlite3.connect(str(db_path))
    try:
        load_real_schema(conn)
        for tid in team_ids:
            conn.execute(
                "INSERT INTO teams (id, name, membership_type) "
                "VALUES (?, ?, 'member')",
                (tid, f"LSB Team {tid}"),
            )
            conn.execute(
                "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
                "VALUES (?, ?, ?)",
                (tid, root_team_id, "Typed Opp Name"),
            )
        conn.commit()
    finally:
        conn.close()


def _set_link_method(
    db_path: Path, method: str | None, public_id: str | None, root_team_id: str = _ROOT
) -> None:
    """Force the seeded link row(s) into an already-resolved state.

    Lets a CLI test start from a wrong `search` auto-resolution -- the state
    `map-opponent` now overrides -- rather than from the pending row
    `_seed_db_with_pending` creates.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE opponent_links SET resolution_method = ?, public_id = ? "
            "WHERE root_team_id = ?",
            (method, public_id, root_team_id),
        )
        conn.commit()
    finally:
        conn.close()


def _link_rows(db_path: Path, root_team_id: str = _ROOT) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM opponent_links WHERE root_team_id = ? ORDER BY our_team_id",
            (root_team_id,),
        ).fetchall()
    finally:
        conn.close()


@pytest.fixture()
def mapped_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A disk DB with one pending opponent_links row, wired via DATABASE_PATH."""
    db_path = tmp_path / "app.db"
    _seed_db_with_pending(db_path)
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    return db_path


def _profile(name: str = "Resolved Opp HS") -> TeamProfile:
    return TeamProfile(public_id=_PUBLIC_ID, name=name, sport="baseball")


def _team_seeded_conn() -> sqlite3.Connection:
    """An in-memory DB with the real schema and one member team (id=1).

    Shared by the two in-memory `_apply_opponent_mapping` test classes so the
    schema/team boilerplate exists once. Distinct from `_seed_db_with_pending`,
    which is DISK-backed for the `DATABASE_PATH`-wired CLI tests -- these
    connections are handed straight to the helper under test.
    """
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB', 'member')"
    )
    conn.commit()
    return conn


class TestApplyOpponentMappingHelper:
    """Direct tests of the pure DB helper (in-memory, no CLI)."""

    def _conn(self) -> sqlite3.Connection:
        conn = _team_seeded_conn()
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
            "VALUES (1, ?, 'Typed')",
            (_ROOT,),
        )
        conn.commit()
        return conn

    def test_positive_update_sets_public_id_method_resolved_at(self):
        conn = self._conn()
        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id=_PUBLIC_ID, method="operator"
        )
        # One row, and it was a PENDING fill -- prior state (None, None).
        assert applied == [(None, None)]
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM opponent_links WHERE root_team_id = ?", (_ROOT,)
        ).fetchone()
        assert row["public_id"] == _PUBLIC_ID
        assert row["resolution_method"] == "operator"
        assert row["resolved_at"] is not None
        # root_team_id is preserved as-is and never written into a gc_uuid column
        # (opponent_links has no gc_uuid column; this asserts namespace safety).
        assert row["root_team_id"] == _ROOT

    def test_no_presence_update_nulls_public_id_sets_method(self):
        conn = self._conn()
        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id=None, method="no_presence"
        )
        assert applied == [(None, None)]
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM opponent_links WHERE root_team_id = ?", (_ROOT,)
        ).fetchone()
        assert row["public_id"] is None
        assert row["resolution_method"] == "no_presence"
        assert row["resolved_at"] is not None

    def test_no_pending_row_returns_zero_and_writes_nothing(self):
        conn = self._conn()
        applied = _apply_opponent_mapping(
            conn, "different-root", public_id=_PUBLIC_ID, method="operator"
        )
        assert applied == []
        # The seeded row for _ROOT is untouched.
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM opponent_links WHERE root_team_id = ?", (_ROOT,)
        ).fetchone()
        assert row["resolution_method"] is None

    def test_operator_resolved_row_not_clobbered(self):
        """An `operator` mapping is terminal here -- re-mapping refuses.

        NOTE the scope, which narrowed deliberately: "already resolved" is no
        longer one class. A `search` row IS now re-mappable (see
        TestSearchOverride below); `operator` / `progenitor` / `no_presence` are
        not. This test covers `operator` only -- do not read it as covering
        already-resolved rows in general.
        """
        conn = self._conn()
        # First resolve positively.
        _apply_opponent_mapping(conn, _ROOT, public_id=_PUBLIC_ID, method="operator")
        # A second call finds no ELIGIBLE row (operator is not overridable) -> [].
        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id="other-slug", method="operator"
        )
        assert applied == []
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM opponent_links WHERE root_team_id = ?", (_ROOT,)
        ).fetchone()
        assert row["public_id"] == _PUBLIC_ID  # unchanged


class TestSearchOverride:
    """A rung-(c) `search` resolution is correctable; nothing else is.

    The gap this closes: `search` auto-accepts on a single TEAM hit with no name
    or season corroboration, so it is the one method that can be confidently
    wrong -- and before this, `map-opponent` refused it, leaving hand-written SQL
    as the only recovery.
    """

    def _conn(self) -> sqlite3.Connection:
        return _team_seeded_conn()

    def _seed(
        self,
        conn: sqlite3.Connection,
        root: str,
        method: str | None,
        public_id: str | None,
        our_team_id: int = 1,
    ) -> None:
        conn.execute(
            "INSERT INTO opponent_links "
            "(our_team_id, root_team_id, opponent_name, public_id, resolution_method) "
            "VALUES (?, ?, 'Typed', ?, ?)",
            (our_team_id, root, public_id, method),
        )
        conn.commit()

    def _method_of(self, conn: sqlite3.Connection, root: str) -> tuple:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT public_id, resolution_method FROM opponent_links "
            "WHERE root_team_id = ?",
            (root,),
        ).fetchone()
        return (row["public_id"], row["resolution_method"])

    def test_search_resolved_row_is_overridden_and_prior_state_reported(self):
        conn = self._conn()
        self._seed(conn, _ROOT, "search", "wrong-slug")

        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id=_PUBLIC_ID, method="operator"
        )

        # The return value carries the DISPLACED state so the caller can say
        # what it replaced -- an override must never be silent.
        assert applied == [("wrong-slug", "search")]
        assert self._method_of(conn, _ROOT) == (_PUBLIC_ID, "operator")

    def test_map_opponent_override_does_not_touch_a_different_opponent(self):
        """🔒 SQL-precedence guard. Fails if the WHERE parentheses are dropped.

        `AND` binds tighter than `OR`, so an unparenthesized
        `root_team_id = ? AND resolution_method IS NULL OR resolution_method = ?`
        parses as
        `(root_team_id = ? AND ... IS NULL) OR (resolution_method = ?)`
        and rewrites EVERY search-resolved row in the table -- including this
        second opponent, which the operator never named.
        """
        conn = self._conn()
        self._seed(conn, _ROOT, "search", "wrong-slug")
        self._seed(conn, "other-root", "search", "other-teams-slug")

        _apply_opponent_mapping(conn, _ROOT, public_id=_PUBLIC_ID, method="operator")

        # The named opponent moved...
        assert self._method_of(conn, _ROOT) == (_PUBLIC_ID, "operator")
        # ...and the bystander did NOT.
        assert self._method_of(conn, "other-root") == ("other-teams-slug", "search")

    def test_no_presence_row_is_still_refused(self):
        """The resurrection bug: `no_presence` must NEVER become eligible.

        A `no_presence` row carries public_id NULL, so a predicate widened to
        `resolution_method IS NOT NULL` -- or gated on public_id -- would re-open
        an opponent the operator explicitly declared absent from GameChanger.
        """
        conn = self._conn()
        self._seed(conn, _ROOT, "no_presence", None)

        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id=_PUBLIC_ID, method="operator"
        )

        assert applied == []
        assert self._method_of(conn, _ROOT) == (None, "no_presence")

    def test_progenitor_row_is_still_refused(self):
        """A progenitor mapping came from GC's own registry link -- not ours to override."""
        conn = self._conn()
        self._seed(conn, _ROOT, "progenitor", "registry-slug")

        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id=_PUBLIC_ID, method="operator"
        )

        assert applied == []
        assert self._method_of(conn, _ROOT) == ("registry-slug", "progenitor")

    def test_override_spans_every_team_facing_the_opponent(self):
        """The key is root_team_id ALONE, so all our teams' rows move together.

        Pre-existing, deliberate behavior -- pinned here because the override
        makes it reach ALREADY-RESOLVED rows for the first time.
        """
        conn = self._conn()
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) VALUES (2, 'LSB JV', 'member')"
        )
        self._seed(conn, _ROOT, "search", "wrong-slug", our_team_id=1)
        self._seed(conn, _ROOT, "search", "wrong-slug", our_team_id=2)

        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id=_PUBLIC_ID, method="operator"
        )

        assert applied == [("wrong-slug", "search"), ("wrong-slug", "search")]
        rows = conn.execute(
            "SELECT resolution_method FROM opponent_links WHERE root_team_id = ?",
            (_ROOT,),
        ).fetchall()
        assert [r[0] for r in rows] == ["operator", "operator"]

    def test_pending_and_search_rows_are_both_eligible_together(self):
        """A mixed set (one team pending, another search-resolved) all moves."""
        conn = self._conn()
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) VALUES (2, 'LSB JV', 'member')"
        )
        self._seed(conn, _ROOT, None, None, our_team_id=1)
        self._seed(conn, _ROOT, "search", "wrong-slug", our_team_id=2)

        applied = _apply_opponent_mapping(
            conn, _ROOT, public_id=_PUBLIC_ID, method="operator"
        )

        assert applied == [(None, None), ("wrong-slug", "search")]


class TestMapOpponentCommand:
    """CLI-level tests for bb report map-opponent."""

    def test_positive_bare_public_id_updates_and_shows_name(self, mapped_db: Path):
        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(app, ["map-opponent", _ROOT, _PUBLIC_ID])

        assert result.exit_code == 0
        assert "Resolved Opp HS" in result.output  # AC-5 name display
        rows = _link_rows(mapped_db)
        assert rows[0]["public_id"] == _PUBLIC_ID
        assert rows[0]["resolution_method"] == "operator"
        assert rows[0]["resolved_at"] is not None

    def test_override_reports_what_it_replaced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """An override must ANNOUNCE the displaced mapping -- never silent.

        CLI-level on purpose: `TestSearchOverride` pins the helper's return
        value, but the operator only ever sees the printed line, and a return
        value nobody renders is not a warning.
        """
        db_path = tmp_path / "app.db"
        _seed_db_with_pending(db_path)
        _set_link_method(db_path, "search", "wrong-slug")
        monkeypatch.setenv("DATABASE_PATH", str(db_path))

        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(app, ["map-opponent", _ROOT, _PUBLIC_ID])

        assert result.exit_code == 0
        assert "Replaced" in result.output
        assert "search" in result.output
        assert "wrong-slug" in result.output  # the displaced public_id, named
        assert _link_rows(db_path)[0]["public_id"] == _PUBLIC_ID

    def test_pending_fill_reports_no_replacement(self, mapped_db: Path):
        """The converse: an ordinary fill displaced nothing, so it must NOT
        claim to have replaced anything (the seeded row is pending)."""
        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(app, ["map-opponent", _ROOT, _PUBLIC_ID])

        assert result.exit_code == 0
        assert "Replaced" not in result.output

    def test_override_across_two_teams_reports_once_with_a_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """One wrong `search` mapping shared by two teams -> ONE line, count 2.

        The message names only the root_team_id and the prior state, so it is
        byte-identical per row; printing it twice would be one fact twice.
        """
        db_path = tmp_path / "app.db"
        _seed_db_with_pending(db_path, team_ids=(1, 2))
        _set_link_method(db_path, "search", "wrong-slug")
        monkeypatch.setenv("DATABASE_PATH", str(db_path))

        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(app, ["map-opponent", _ROOT, _PUBLIC_ID])

        assert result.exit_code == 0
        assert result.output.count("Replaced") == 1
        assert "across 2 team(s)" in result.output

    def test_partial_apply_warns_about_untouched_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A split-method opponent must not report a partial apply as complete.

        Rung (a) depends on each team's own registry, so one team's row can be
        `progenitor` while another's is `search`. Correcting the `search` row
        leaves the other pointing at the old team -- and "across 1 team(s)"
        alone reads as done.
        """
        db_path = tmp_path / "app.db"
        _seed_db_with_pending(db_path, team_ids=(1, 2))
        # Team 1 -> search (correctable); team 2 -> progenitor (not).
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE opponent_links SET resolution_method='search', "
            "public_id='wrong-slug' WHERE our_team_id=1"
        )
        conn.execute(
            "UPDATE opponent_links SET resolution_method='progenitor', "
            "public_id='registry-slug' WHERE our_team_id=2"
        )
        conn.commit()
        conn.close()
        monkeypatch.setenv("DATABASE_PATH", str(db_path))

        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(app, ["map-opponent", _ROOT, _PUBLIC_ID])

        assert result.exit_code == 0
        assert "Left unchanged" in result.output
        assert "progenitor" in result.output
        rows = _link_rows(db_path)
        assert rows[0]["public_id"] == _PUBLIC_ID  # team 1 corrected
        assert rows[1]["public_id"] == "registry-slug"  # team 2 untouched

    def test_positive_full_url_target_parsed(self, mapped_db: Path):
        url = f"https://web.gc.com/teams/{_PUBLIC_ID}/2026-some-slug"
        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(app, ["map-opponent", _ROOT, url])

        assert result.exit_code == 0
        rows = _link_rows(mapped_db)
        assert rows[0]["public_id"] == _PUBLIC_ID  # AC-4: URL -> public_id

    def test_uuid_target_rejected(self, mapped_db: Path):
        uuid = "72bb77d8-54ca-42d2-8547-9da4880d0cb4"
        result = runner.invoke(app, ["map-opponent", _ROOT, uuid])

        assert result.exit_code == 2
        assert "UUID" in result.output
        # No write occurred.
        rows = _link_rows(mapped_db)
        assert rows[0]["resolution_method"] is None

    def test_multi_team_updates_all_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        db_path = tmp_path / "app.db"
        _seed_db_with_pending(db_path, team_ids=(1, 2, 3))
        monkeypatch.setenv("DATABASE_PATH", str(db_path))

        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(app, ["map-opponent", _ROOT, _PUBLIC_ID])

        assert result.exit_code == 0
        assert "3 team(s)" in result.output  # AC-2
        rows = _link_rows(db_path)
        assert len(rows) == 3
        assert all(r["public_id"] == _PUBLIC_ID for r in rows)
        assert all(r["resolution_method"] == "operator" for r in rows)

    def test_no_presence_form_sets_no_presence_state(self, mapped_db: Path):
        result = runner.invoke(app, ["map-opponent", _ROOT, "--no-presence"])

        assert result.exit_code == 0
        assert "no GameChanger presence" in result.output
        rows = _link_rows(mapped_db)
        assert rows[0]["public_id"] is None
        assert rows[0]["resolution_method"] == "no_presence"
        assert rows[0]["resolved_at"] is not None

    def test_no_presence_with_target_errors(self, mapped_db: Path):
        result = runner.invoke(
            app, ["map-opponent", _ROOT, _PUBLIC_ID, "--no-presence"]
        )
        assert result.exit_code == 2
        assert "no <target>" in result.output
        rows = _link_rows(mapped_db)
        assert rows[0]["resolution_method"] is None  # no write

    def test_missing_target_without_no_presence_errors(self, mapped_db: Path):
        result = runner.invoke(app, ["map-opponent", _ROOT])
        assert result.exit_code == 2
        assert "Missing <target>" in result.output
        rows = _link_rows(mapped_db)
        assert rows[0]["resolution_method"] is None

    def test_no_pending_row_positive_errors_and_no_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        db_path = tmp_path / "app.db"
        _seed_db_with_pending(db_path)  # pending row exists for _ROOT only
        monkeypatch.setenv("DATABASE_PATH", str(db_path))

        with patch("src.cli.report.resolve_team", return_value=_profile()):
            result = runner.invoke(
                app, ["map-opponent", "unknown-root", _PUBLIC_ID]
            )

        assert result.exit_code == 1
        assert "No mappable opponent" in result.output
        # The real pending row is untouched.
        rows = _link_rows(db_path)
        assert rows[0]["resolution_method"] is None

    def test_no_pending_row_no_presence_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        db_path = tmp_path / "app.db"
        _seed_db_with_pending(db_path)
        monkeypatch.setenv("DATABASE_PATH", str(db_path))

        result = runner.invoke(
            app, ["map-opponent", "unknown-root", "--no-presence"]
        )
        assert result.exit_code == 1
        assert "No mappable opponent" in result.output

    def test_name_lookup_failure_still_applies_mapping(self, mapped_db: Path):
        """AC-5: a failed display-name lookup warns but does not abort."""
        from src.gamechanger.exceptions import TeamNotFoundError

        with patch(
            "src.cli.report.resolve_team",
            side_effect=TeamNotFoundError("404"),
        ):
            result = runner.invoke(app, ["map-opponent", _ROOT, _PUBLIC_ID])

        assert result.exit_code == 0
        assert "Warning" in result.output
        rows = _link_rows(mapped_db)
        assert rows[0]["public_id"] == _PUBLIC_ID
        assert rows[0]["resolution_method"] == "operator"

    def test_help(self):
        result = runner.invoke(app, ["map-opponent", "--help"])
        assert result.exit_code == 0
        assert "root_team_id" in result.output.lower()


class TestMapOpponentLadderTerminality:
    """AC-7: a subsequent ladder run reuses the operator mapping (both forms)."""

    def _conn_with_team(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        load_real_schema(conn)
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB', 'member')"
        )
        conn.execute(
            "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
            "VALUES (1, ?, 'Typed')",
            (_ROOT,),
        )
        conn.commit()
        return conn

    def test_operator_positive_mapping_auto_resolves_on_next_run(self):
        from src.gamechanger.crawlers.opponents import OpponentRecord
        from src.gamechanger.opponent_ladder import (
            ResolutionOutcome,
            resolve_opponent,
        )

        conn = self._conn_with_team()
        _apply_opponent_mapping(conn, _ROOT, public_id=_PUBLIC_ID, method="operator")

        client = MagicMock()  # must NOT be called
        registry = [
            OpponentRecord(
                root_team_id=_ROOT,
                name="Typed",
                progenitor_team_id="prog-x",
                has_progenitor=True,
                owning_team_id="own",
                is_hidden=False,
            )
        ]
        result = resolve_opponent(
            conn=conn,
            client=client,
            our_team_id=1,
            opponent_id=_ROOT,
            opponent_name="Typed",
            registry=registry,
        )

        assert result.outcome is ResolutionOutcome.RESOLVED
        assert result.public_id == _PUBLIC_ID
        assert result.method == "operator"
        assert result.from_cache is True
        client.get.assert_not_called()

    def test_no_presence_mapping_is_terminal_not_reattempted(self):
        from src.gamechanger.crawlers.opponents import OpponentRecord
        from src.gamechanger.opponent_ladder import (
            ResolutionOutcome,
            resolve_opponent,
        )

        conn = self._conn_with_team()
        _apply_opponent_mapping(conn, _ROOT, public_id=None, method="no_presence")

        client = MagicMock()  # must NOT be called (resurrection-bug guard)
        registry = [
            OpponentRecord(
                root_team_id=_ROOT,
                name="Typed",
                progenitor_team_id="prog-x",
                has_progenitor=True,
                owning_team_id="own",
                is_hidden=False,
            )
        ]
        result = resolve_opponent(
            conn=conn,
            client=client,
            our_team_id=1,
            opponent_id=_ROOT,
            opponent_name="Typed",
            registry=registry,
        )

        # no_presence is terminal: NOT re-attempted.
        client.get.assert_not_called()
        client.post_json.assert_not_called()
        assert result.from_cache is True
        assert result.method == "no_presence"
        assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
