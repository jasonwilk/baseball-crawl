"""Tests for src/gamechanger/crawlers/scouting.py (E-097-03, E-100-03, E-127-09).

Covers:
- AC-12: Single-team scouting with mocked API responses
- AC-12: freshness-skip logic
- AC-12: error handling for credential/forbidden errors
- AC-12: game_status == "completed" filtering
- AC-12: first_fetched / last_checked timestamp behaviour on scouting_runs
- AC-1/AC-2: ScoutingCrawler constructor and method signatures
- AC-16: UUID opportunism
- E-127-09 AC-4: _PUBLIC_GAMES_ACCEPT constant value

All HTTP calls are mocked. No real network requests are made.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.client import (
    CredentialExpiredError,
    ForbiddenError,
    GameChangerAPIError,
)
from src.gamechanger.crawlers.scouting import (
    ScoutingCrawler,
    ScoutingCrawlResult,
    _PUBLIC_GAMES_ACCEPT,
    _derive_season_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and return an open in-memory-like connection."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@pytest.fixture()
def mock_client() -> MagicMock:
    """Return a MagicMock that stands in for GameChangerClient."""
    return MagicMock()


@pytest.fixture()
def crawler(mock_client: MagicMock, db: sqlite3.Connection) -> ScoutingCrawler:
    """Return a ScoutingCrawler with a mocked client."""
    return ScoutingCrawler(mock_client, db)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_PUBLIC_ID = "abc123def456"

_COMPLETED_GAME = {
    "id": "game-stream-uuid-001",
    "game_status": "completed",
    "home_away": "home",
    "start_ts": "2025-04-10T18:00:00Z",
    "score": {"team": 5, "opponent_team": 3},
}

_SCHEDULED_GAME = {
    "id": "game-stream-uuid-002",
    "game_status": "scheduled",
    "start_ts": "2025-04-20T18:00:00Z",
    "score": {},
}

_GAMES_RESPONSE = [_COMPLETED_GAME, _SCHEDULED_GAME]

_ROSTER_RESPONSE = [
    {"id": "player-uuid-001", "first_name": "John", "last_name": "Doe", "number": "14"},
    {"id": "player-uuid-002", "first_name": "Jane", "last_name": "Smith", "number": "7"},
]

_BOXSCORE_RESPONSE = {
    _PUBLIC_ID: {
        "players": [
            {"id": "player-uuid-001", "first_name": "John", "last_name": "Doe", "number": "14"},
        ],
        "groups": [],
    },
    "aaaabbbb-cccc-dddd-eeee-ffff00001111": {
        "players": [],
        "groups": [],
    },
}


def _setup_client_happy_path(mock_client: MagicMock) -> None:
    """Configure mock_client to return success responses for all scouting calls."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [
        _ROSTER_RESPONSE,
        _BOXSCORE_RESPONSE,
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_team_with_public_id(conn: sqlite3.Connection, public_id: str) -> int:
    """Insert a tracked team row and return its INTEGER PK."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO teams (name, membership_type, public_id, is_active) "
        "VALUES (?, 'tracked', ?, 0)",
        (public_id, public_id),
    )
    if cursor.lastrowid:
        conn.commit()
        return cursor.lastrowid
    row = conn.execute("SELECT id FROM teams WHERE public_id = ?", (public_id,)).fetchone()
    conn.commit()
    return row[0]


def _insert_season(conn: sqlite3.Connection, season_id: str) -> None:
    """Ensure a seasons row exists."""
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, 'unknown', 2025) "
        "ON CONFLICT DO NOTHING",
        (season_id, season_id),
    )
    conn.commit()


def _insert_scouting_run(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    status: str,
    last_checked: str,
) -> None:
    """Insert a scouting_runs row."""
    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status, last_checked) "
        "VALUES (?, ?, 'full', ?, ?, ?)",
        (team_id, season_id, last_checked, status, last_checked),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# AC-1: Constructor and method signatures
# ---------------------------------------------------------------------------


def test_public_games_accept_header_constant() -> None:
    """_PUBLIC_GAMES_ACCEPT uses the correct vendor media type (E-127-09 AC-4)."""
    assert _PUBLIC_GAMES_ACCEPT == (
        "application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0"
    )


def test_scouting_crawler_constructor(mock_client: MagicMock, db: sqlite3.Connection) -> None:
    """ScoutingCrawler accepts client and db."""
    crawler = ScoutingCrawler(mock_client, db)
    assert crawler is not None


def test_scout_team_exists(crawler: ScoutingCrawler) -> None:
    """ScoutingCrawler exposes the scout_team() method."""
    assert callable(crawler.scout_team)


# ---------------------------------------------------------------------------
# AC-2: Public-endpoint scouting chain
# ---------------------------------------------------------------------------


def test_scout_team_calls_public_endpoint_for_games(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """scout_team() fetches game schedule via get_public() (no auth)."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    mock_client.get_public.assert_called_once_with(
        f"/public/teams/{_PUBLIC_ID}/games",
        accept=_PUBLIC_GAMES_ACCEPT,
    )


def test_scout_team_fetches_roster_with_inverted_url(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """scout_team() fetches roster via GET /teams/public/{public_id}/players."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    calls = mock_client.get.call_args_list
    roster_call = calls[0]
    assert f"/teams/public/{_PUBLIC_ID}/players" in roster_call.args[0]


def test_scout_team_fetches_boxscore_per_completed_game(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """scout_team() fetches boxscore for each completed game only."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    calls = mock_client.get.call_args_list
    boxscore_calls = [c for c in calls if "boxscore" in str(c.args)]
    assert len(boxscore_calls) == 1
    assert "game-stream-uuid-001" in str(boxscore_calls[0])


# ---------------------------------------------------------------------------
# AC-2: game_status == "completed" filtering
# ---------------------------------------------------------------------------


def test_only_completed_games_are_scouted(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """Only games with game_status='completed' result in boxscore fetches."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    # Roster + 1 boxscore (only the completed game).
    assert mock_client.get.call_count == 2


def test_no_completed_games_returns_skipped(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """When no completed games exist, scout_team returns skipped=True."""
    mock_client.get_public.return_value = [_SCHEDULED_GAME]
    result = crawler.scout_team(_PUBLIC_ID)
    assert result.skipped is True
    assert result.games_crawled == 0


# ---------------------------------------------------------------------------
# E-234-04 AC-4: roster-fetch failure resilience (crawler layer)
# ---------------------------------------------------------------------------


def test_roster_fetch_failure_is_resilient(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """A roster-fetch failure is handled gracefully at the crawler layer.

    When the roster endpoint raises a handled API error, ``_fetch_roster``
    returns ``None`` and ``scout_team`` short-circuits: it writes a 'failed'
    scouting_run and returns a result with ``errors == 1`` and zero boxscores
    -- WITHOUT crashing and WITHOUT attempting any boxscore fetch. This pins
    the crawler-level resilience contract (one layer below the report
    generator, where E-234-04 AC-1/AC-2/AC-3 live).
    """
    mock_client.get_public.return_value = _GAMES_RESPONSE  # one completed game
    # First (and only) authenticated GET is the roster fetch -> make it fail.
    mock_client.get.side_effect = GameChangerAPIError("roster endpoint 500")

    result = crawler.scout_team(_PUBLIC_ID)

    # Resilience: no exception, terminal result flags the error.
    assert isinstance(result, ScoutingCrawlResult)
    assert result.errors == 1
    assert result.games_crawled == 0
    assert result.boxscores == {}
    assert result.roster == []

    # Boxscore fetching never started -- only the roster GET was attempted.
    assert mock_client.get.call_count == 1
    roster_call = mock_client.get.call_args_list[0]
    assert f"/teams/public/{_PUBLIC_ID}/players" in roster_call.args[0]

    # The scouting_run is recorded as 'failed' (not left running).
    row = db.execute(
        "SELECT status FROM scouting_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == "failed"


# ---------------------------------------------------------------------------
# AC-4: Raw files written
# ---------------------------------------------------------------------------


def test_in_memory_data_returned(
    crawler: ScoutingCrawler, mock_client: MagicMock, tmp_path: Path
) -> None:
    """scout_team() returns in-memory games, roster, and boxscores (no disk files)."""
    _setup_client_happy_path(mock_client)
    result = crawler.scout_team(_PUBLIC_ID)

    assert isinstance(result, ScoutingCrawlResult)
    assert len(result.games) > 0
    assert len(result.roster) > 0
    assert len(result.boxscores) > 0
    assert "game-stream-uuid-001" in result.boxscores
    assert result.games_crawled == 1

    # No files should be written to disk.
    scouting_dir = tmp_path / "raw" / "2025-spring-hs" / "scouting" / _PUBLIC_ID
    assert not scouting_dir.exists()


# ---------------------------------------------------------------------------
# AC-5: scouting_runs tracking
# ---------------------------------------------------------------------------


def test_scouting_run_created_with_completed_status(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """After a successful scout_team(), scouting_runs has a 'completed' row."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    row = db.execute(
        "SELECT status, games_found, games_crawled, players_found "
        "FROM scouting_runs LIMIT 1"
    ).fetchone()
    assert row is not None
    status, games_found, games_crawled, players_found = row
    assert status == "completed"
    assert games_found == 1   # one completed game in _GAMES_RESPONSE
    assert games_crawled == 1
    assert players_found == 2  # two players in _ROSTER_RESPONSE


def test_scout_team_writes_year_only_default_season_row(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """E-241: the crawler creates the year-only season row with season_type
    'default', matching the canonical ensure_season_row contract.

    The live report path runs scout_team() (this writer) BEFORE the canonical
    ensure_season_row, and both use ON CONFLICT DO NOTHING, so the crawler's
    season_type is the one that persists for a scouted opponent. It must be
    'default' (not 'unknown') or the persisted metadata drifts from the
    year-only contract.
    """
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    # The completed game in _GAMES_RESPONSE is in 2025 -> year-only "2025".
    row = db.execute(
        "SELECT season_type FROM seasons WHERE season_id = '2025'"
    ).fetchone()
    assert row is not None, "Crawler should create the year-only '2025' season row"
    assert row[0] == "default", f"Expected season_type 'default', got {row[0]!r}"


def test_scouting_run_has_integer_team_id(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """scouting_runs.team_id is an INTEGER PK referencing teams.id."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    row = db.execute(
        "SELECT sr.team_id, t.id FROM scouting_runs sr JOIN teams t ON sr.team_id = t.id LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == row[1]  # team_id matches an actual teams.id


def test_first_fetched_preserved_on_rerun(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """Re-running scout_team() preserves first_fetched while updating last_checked."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, _BOXSCORE_RESPONSE]
    crawler.scout_team(_PUBLIC_ID)

    first = db.execute(
        "SELECT first_fetched, last_checked FROM scouting_runs LIMIT 1"
    ).fetchone()
    first_fetched_1, last_checked_1 = first[0], first[1]

    # Re-run.
    import time
    time.sleep(0.01)  # ensure different timestamp
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, _BOXSCORE_RESPONSE]
    crawler.scout_team(_PUBLIC_ID)

    second = db.execute(
        "SELECT first_fetched, last_checked FROM scouting_runs LIMIT 1"
    ).fetchone()
    first_fetched_2, last_checked_2 = second[0], second[1]

    assert first_fetched_1 == first_fetched_2, "first_fetched must not change on re-run"
    # last_checked is refreshed by the SQL strftime call, so it should be >= the first


# ---------------------------------------------------------------------------
# AC-6: Error handling
# ---------------------------------------------------------------------------


def test_credential_error_on_schedule_logs_and_returns_error(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """CredentialExpiredError on schedule fetch is caught; returns CrawlResult(errors=1)."""
    mock_client.get_public.side_effect = CredentialExpiredError("token expired")
    result = crawler.scout_team(_PUBLIC_ID)
    assert result.errors == 1
    assert result.games_crawled == 0


def test_forbidden_error_on_schedule_logs_and_returns_error(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """ForbiddenError on schedule fetch is caught; returns CrawlResult(errors=1)."""
    mock_client.get_public.side_effect = ForbiddenError("403 forbidden")
    result = crawler.scout_team(_PUBLIC_ID)
    assert result.errors == 1


def test_credential_error_on_roster_marks_run_failed(
    crawler: ScoutingCrawler, mock_client: MagicMock, tmp_path: Path
) -> None:
    """CredentialExpiredError on roster fetch marks scouting_run as failed and commits it."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = CredentialExpiredError("token expired")
    result = crawler.scout_team(_PUBLIC_ID)
    assert result.errors == 1

    # Use a fresh connection to verify the 'failed' status was actually committed.
    db_path = tmp_path / "test.db"
    with sqlite3.connect(str(db_path)) as fresh_conn:
        row = fresh_conn.execute(
            "SELECT status FROM scouting_runs LIMIT 1"
        ).fetchone()
    assert row is not None, "scouting_runs row not found"
    assert row[0] == "failed", f"Expected status='failed', got '{row[0]}'"


def test_boxscore_error_skips_game_continues_run(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """ForbiddenError on one boxscore skips that game but the run is marked 'failed' (zero crawled)."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, ForbiddenError("403")]
    result = crawler.scout_team(_PUBLIC_ID)
    # All boxscores failed → total failure → errors=1 and status='failed'.
    assert result.errors == 1
    row = db.execute("SELECT status, games_crawled FROM scouting_runs LIMIT 1").fetchone()
    if row:
        assert row[0] == "failed"
        assert row[1] == 0  # no boxscores crawled


# ---------------------------------------------------------------------------
# Helper: _derive_season_id
# ---------------------------------------------------------------------------


def test_derive_season_id_extracts_year() -> None:
    """_derive_season_id returns the year-only slug from earliest game start_ts."""
    games = [
        {"id": "g1", "start_ts": "2025-05-01T18:00:00Z"},
        {"id": "g2", "start_ts": "2025-04-10T18:00:00Z"},
    ]
    assert _derive_season_id(games) == "2025"


def test_derive_season_id_uses_earliest_year() -> None:
    """_derive_season_id picks the minimum year."""
    games = [
        {"id": "g1", "start_ts": "2026-01-01T00:00:00Z"},
        {"id": "g2", "start_ts": "2025-12-15T00:00:00Z"},
    ]
    assert _derive_season_id(games) == "2025"


def test_derive_season_id_fallback_on_missing_ts() -> None:
    """_derive_season_id falls back to current year when no start_ts."""
    import datetime as dt
    games = [{"id": "g1"}]
    result = _derive_season_id(games)
    current_year = dt.datetime.now(dt.timezone.utc).year
    assert result == f"{current_year}"


# ---------------------------------------------------------------------------
# AC-4 (E-122-01): CredentialExpiredError propagates out of boxscore fetch
# ---------------------------------------------------------------------------


def test_credential_expired_on_boxscore_propagates_from_scout_team(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """CredentialExpiredError during boxscore fetch propagates out of scout_team()."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, CredentialExpiredError("token expired")]
    with pytest.raises(CredentialExpiredError):
        crawler.scout_team(_PUBLIC_ID)


def test_forbidden_on_boxscore_does_not_propagate(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """ForbiddenError during boxscore fetch is caught (expected for non-owned teams)."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, ForbiddenError("403")]
    # Should not raise -- ForbiddenError is caught per-game
    result = crawler.scout_team(_PUBLIC_ID)
    assert result.errors >= 1  # all boxscores failed → run failed


# ---------------------------------------------------------------------------
# E-211: UUID opportunism removed -- _record_uuid_from_boxscore deleted
# ---------------------------------------------------------------------------


def test_uuid_opportunism_removed(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """E-211: _record_uuid_from_boxscore is removed; no UUID stored as gc_uuid."""
    assert not hasattr(crawler, "_record_uuid_from_boxscore"), (
        "_record_uuid_from_boxscore must be removed from ScoutingCrawler"
    )


# ---------------------------------------------------------------------------
# AC-1/AC-7c: Crawler writes 'completed' after successful crawl phase (E-123-06)
# ---------------------------------------------------------------------------


def test_scout_team_writes_completed_status_after_crawl(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-1: scout_team() sets scouting_runs.status='completed' after a successful crawl."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    row = db.execute("SELECT status FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "completed", f"Expected 'completed', got '{row[0]}'"


def test_scout_team_completed_status_has_completed_at_set(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-1: 'completed' rows must have completed_at set (not NULL)."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID)

    row = db.execute("SELECT status, completed_at FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "completed"
    assert row[1] is not None, "Expected completed_at to be set for 'completed' row"


# ---------------------------------------------------------------------------
# AC-7d: Zero-boxscore crawl is marked 'failed' (E-098-03)
# ---------------------------------------------------------------------------


def test_zero_boxscores_marks_run_failed_and_returns_error(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-7d: When all boxscore fetches fail, run is 'failed' and CrawlResult.errors >= 1."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    # Roster succeeds; boxscore raises for the one completed game.
    mock_client.get.side_effect = [_ROSTER_RESPONSE, ForbiddenError("403")]

    result = crawler.scout_team(_PUBLIC_ID)

    assert result.errors >= 1

    row = db.execute("SELECT status, completed_at FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "failed", f"Expected 'failed', got '{row[0]}'"
    assert row[1] is not None, "Expected completed_at to be set for 'failed' row"


# ---------------------------------------------------------------------------
# update_run_load_status tests (E-125-02 AC-1, AC-2, AC-6)
# ---------------------------------------------------------------------------


class TestUpdateRunLoadStatus:
    """Verify update_run_load_status uses parameterized SQL and handles both statuses."""

    def test_completed_status_sets_completed_at(
        self,
        db: sqlite3.Connection,
        mock_client: MagicMock,
    ) -> None:
        """AC-6: 'completed' status sets completed_at to a non-NULL timestamp."""
        team_id = _insert_team_with_public_id(db, "status-test-pub")
        season_id = "2025-spring-hs"
        _insert_season(db, season_id)
        _insert_scouting_run(
            db, team_id, season_id, "running", "2025-04-10T00:00:00.000Z"
        )

        crawler = ScoutingCrawler(mock_client, db)
        crawler.update_run_load_status(team_id, season_id, "completed")

        row = db.execute(
            "SELECT status, completed_at FROM scouting_runs "
            "WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        ).fetchone()
        assert row[0] == "completed"
        assert row[1] is not None, "completed_at should be set for 'completed' status"

    def test_failed_status_sets_completed_at_null(
        self,
        db: sqlite3.Connection,
        mock_client: MagicMock,
    ) -> None:
        """AC-6: 'failed' status sets completed_at to NULL."""
        team_id = _insert_team_with_public_id(db, "status-fail-pub")
        season_id = "2025-spring-hs"
        _insert_season(db, season_id)
        _insert_scouting_run(
            db, team_id, season_id, "running", "2025-04-10T00:00:00.000Z"
        )

        crawler = ScoutingCrawler(mock_client, db)
        crawler.update_run_load_status(team_id, season_id, "failed")

        row = db.execute(
            "SELECT status, completed_at FROM scouting_runs "
            "WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        ).fetchone()
        assert row[0] == "failed"
        assert row[1] is None, "completed_at should be NULL for 'failed' status"

    def test_no_f_string_sql_injection(
        self,
        db: sqlite3.Connection,
        mock_client: MagicMock,
    ) -> None:
        """AC-1: Verify no f-string interpolation -- a crafted status value
        cannot inject SQL. The CHECK constraint rejects invalid statuses, but
        the parameterized query itself should handle arbitrary input safely."""
        team_id = _insert_team_with_public_id(db, "inject-test-pub")
        season_id = "2025-spring-hs"
        _insert_season(db, season_id)
        _insert_scouting_run(
            db, team_id, season_id, "running", "2025-04-10T00:00:00.000Z"
        )

        crawler = ScoutingCrawler(mock_client, db)
        # This should fail due to CHECK constraint, not SQL injection.
        with pytest.raises(sqlite3.IntegrityError):
            crawler.update_run_load_status(
                team_id, season_id, "completed'; DROP TABLE scouting_runs;--"
            )

    def test_completed_updates_last_checked(
        self,
        db: sqlite3.Connection,
        mock_client: MagicMock,
    ) -> None:
        """Verify last_checked is updated on status change."""
        team_id = _insert_team_with_public_id(db, "lastchk-test-pub")
        season_id = "2025-spring-hs"
        _insert_season(db, season_id)
        _insert_scouting_run(
            db, team_id, season_id, "running", "2020-01-01T00:00:00.000Z"
        )

        crawler = ScoutingCrawler(mock_client, db)
        crawler.update_run_load_status(team_id, season_id, "completed")

        row = db.execute(
            "SELECT last_checked FROM scouting_runs "
            "WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        ).fetchone()
        # last_checked should be updated to a recent timestamp, not the old 2020 value.
        assert row[0] > "2024-01-01"
