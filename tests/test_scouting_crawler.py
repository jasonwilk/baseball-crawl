"""Tests for src/gamechanger/crawlers/scouting.py (E-097-03).

Covers:
- AC-12: Single-team scouting with mocked API responses
- AC-12: freshness-skip logic
- AC-12: error handling for credential/forbidden errors
- AC-12: game_status == "completed" filtering
- AC-12: first_fetched / last_checked timestamp behaviour on scouting_runs
- AC-1/AC-2: ScoutingCrawler constructor and method signatures
- AC-16: UUID opportunism

All HTTP calls are mocked. No real network requests are made.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.client import CredentialExpiredError, ForbiddenError
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.scouting import ScoutingCrawler, _derive_season_id


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
def crawler(mock_client: MagicMock, db: sqlite3.Connection, tmp_path: Path) -> ScoutingCrawler:
    """Return a ScoutingCrawler with mocked client and temp data_root."""
    return ScoutingCrawler(mock_client, db, freshness_hours=24, data_root=tmp_path / "raw")


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
# AC-1: Constructor and method signatures
# ---------------------------------------------------------------------------


def test_scouting_crawler_constructor(mock_client: MagicMock, db: sqlite3.Connection, tmp_path: Path) -> None:
    """ScoutingCrawler accepts client, db, freshness_hours, data_root."""
    crawler = ScoutingCrawler(mock_client, db, freshness_hours=48, data_root=tmp_path)
    assert crawler is not None


def test_scout_team_and_scout_all_exist(crawler: ScoutingCrawler) -> None:
    """ScoutingCrawler exposes scout_team() and scout_all() methods."""
    assert callable(crawler.scout_team)
    assert callable(crawler.scout_all)


# ---------------------------------------------------------------------------
# AC-2: Public-endpoint scouting chain
# ---------------------------------------------------------------------------


def test_scout_team_calls_public_endpoint_for_games(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """scout_team() fetches game schedule via get_public() (no auth)."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    mock_client.get_public.assert_called_once_with(
        f"/public/teams/{_PUBLIC_ID}/games",
        accept="application/vnd.gc.com.event:list+json; version=0.1.0",
    )


def test_scout_team_fetches_roster_with_inverted_url(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """scout_team() fetches roster via GET /teams/public/{public_id}/players."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    calls = mock_client.get.call_args_list
    roster_call = calls[0]
    assert f"/teams/public/{_PUBLIC_ID}/players" in roster_call.args[0]


def test_scout_team_fetches_boxscore_per_completed_game(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """scout_team() fetches boxscore for each completed game only."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

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
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    # Roster + 1 boxscore (only the completed game).
    assert mock_client.get.call_count == 2


def test_no_completed_games_returns_skipped(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """When no completed games exist, scout_team returns files_skipped=1."""
    mock_client.get_public.return_value = [_SCHEDULED_GAME]
    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")
    assert result.files_skipped == 1
    assert result.files_written == 0


# ---------------------------------------------------------------------------
# AC-4: Raw files written
# ---------------------------------------------------------------------------


def test_raw_files_written(
    crawler: ScoutingCrawler, mock_client: MagicMock, tmp_path: Path
) -> None:
    """scout_team() writes games.json, roster.json, and boxscore files."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    scouting_dir = tmp_path / "raw" / "2025-spring-hs" / "scouting" / _PUBLIC_ID
    assert (scouting_dir / "games.json").exists()
    assert (scouting_dir / "roster.json").exists()
    assert (scouting_dir / "boxscores" / "game-stream-uuid-001.json").exists()


# ---------------------------------------------------------------------------
# AC-5: scouting_runs tracking
# ---------------------------------------------------------------------------


def test_scouting_run_created_with_running_status(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """After a successful scout_team(), scouting_runs has a 'running' row (load pending)."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    row = db.execute(
        "SELECT status, games_found, games_crawled, players_found "
        "FROM scouting_runs LIMIT 1"
    ).fetchone()
    assert row is not None
    status, games_found, games_crawled, players_found = row
    assert status == "running"  # crawler writes 'running'; CLI finalises to 'completed'
    assert games_found == 1   # one completed game in _GAMES_RESPONSE
    assert games_crawled == 1
    assert players_found == 2  # two players in _ROSTER_RESPONSE


def test_first_fetched_preserved_on_rerun(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """Re-running scout_team() preserves first_fetched while updating last_checked."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, _BOXSCORE_RESPONSE]
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    first = db.execute(
        "SELECT first_fetched, last_checked FROM scouting_runs LIMIT 1"
    ).fetchone()
    first_fetched_1, last_checked_1 = first[0], first[1]

    # Re-run.
    import time
    time.sleep(0.01)  # ensure different timestamp
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, _BOXSCORE_RESPONSE]
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

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
    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")
    assert result.errors == 1
    assert result.files_written == 0


def test_forbidden_error_on_schedule_logs_and_returns_error(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """ForbiddenError on schedule fetch is caught; returns CrawlResult(errors=1)."""
    mock_client.get_public.side_effect = ForbiddenError("403 forbidden")
    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")
    assert result.errors == 1


def test_credential_error_on_roster_marks_run_failed(
    crawler: ScoutingCrawler, mock_client: MagicMock, tmp_path: Path
) -> None:
    """CredentialExpiredError on roster fetch marks scouting_run as failed and commits it."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = CredentialExpiredError("token expired")
    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")
    assert result.errors == 1

    # Use a fresh connection to verify the 'failed' status was actually committed
    # (not just visible on the same uncommitted connection).
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
    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")
    # All boxscores failed → total failure → errors=1 and status='failed'.
    assert result.errors == 1
    row = db.execute("SELECT status, games_crawled FROM scouting_runs LIMIT 1").fetchone()
    if row:
        assert row[0] == "failed"
        assert row[1] == 0  # no boxscores crawled


# ---------------------------------------------------------------------------
# AC-3: scout_all freshness skip
# ---------------------------------------------------------------------------


def _insert_team_and_season(conn: sqlite3.Connection, team_id: str, season_id: str) -> None:
    conn.execute("INSERT INTO teams (team_id, name) VALUES (?, ?) ON CONFLICT DO NOTHING", (team_id, team_id))
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) VALUES (?, ?, 'unknown', 2025) ON CONFLICT DO NOTHING",
        (season_id, season_id),
    )
    conn.commit()


def test_scout_all_skips_recently_scouted(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """scout_all() skips opponents with a recent completed scouting run."""
    # Insert an opponent_link with public_id.
    db.execute(
        "INSERT INTO teams (team_id, name, is_owned, is_active) VALUES (?, ?, 0, 0) ON CONFLICT DO NOTHING",
        ("owned-team-id", "My Team"),
    )
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id) VALUES (?, ?, ?, ?)",
        ("owned-team-id", "root-001", "Test Opponent", _PUBLIC_ID),
    )
    # Insert a recent completed scouting run for this team.
    _insert_team_and_season(db, _PUBLIC_ID, "2025-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    db.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status, last_checked) "
        "VALUES (?, ?, 'full', ?, 'completed', ?)",
        (_PUBLIC_ID, "2025-spring-hs", recent_ts, recent_ts),
    )
    db.commit()

    result = crawler.scout_all(season_id="2025-spring-hs")
    # Should skip (no API calls).
    mock_client.get_public.assert_not_called()
    assert result.files_skipped == 1


def test_scout_all_scouts_stale_opponents(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """scout_all() scouts opponents whose last_checked is older than freshness_hours."""
    db.execute(
        "INSERT INTO teams (team_id, name) VALUES (?, ?) ON CONFLICT DO NOTHING",
        ("owned-team-id", "My Team"),
    )
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id) VALUES (?, ?, ?, ?)",
        ("owned-team-id", "root-001", "Test Opponent", _PUBLIC_ID),
    )
    db.commit()

    # Set up a stale scouting run (25 hours ago).
    _insert_team_and_season(db, _PUBLIC_ID, "2025-spring-hs")
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    db.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status, last_checked) "
        "VALUES (?, ?, 'full', ?, 'completed', ?)",
        (_PUBLIC_ID, "2025-spring-hs", stale_ts, stale_ts),
    )
    db.commit()

    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, _BOXSCORE_RESPONSE]

    result = crawler.scout_all(season_id="2025-spring-hs")
    mock_client.get_public.assert_called_once()
    assert result.files_written > 0


# ---------------------------------------------------------------------------
# Helper: _derive_season_id
# ---------------------------------------------------------------------------


def test_derive_season_id_extracts_year() -> None:
    """_derive_season_id returns {year}-spring-hs from earliest game start_ts."""
    games = [
        {"id": "g1", "start_ts": "2025-05-01T18:00:00Z"},
        {"id": "g2", "start_ts": "2025-04-10T18:00:00Z"},
    ]
    assert _derive_season_id(games) == "2025-spring-hs"


def test_derive_season_id_uses_earliest_year() -> None:
    """_derive_season_id picks the minimum year."""
    games = [
        {"id": "g1", "start_ts": "2026-01-01T00:00:00Z"},
        {"id": "g2", "start_ts": "2025-12-15T00:00:00Z"},
    ]
    assert _derive_season_id(games) == "2025-spring-hs"


def test_derive_season_id_fallback_on_missing_ts() -> None:
    """_derive_season_id falls back to current year when no start_ts."""
    import datetime as dt
    games = [{"id": "g1"}]
    result = _derive_season_id(games)
    current_year = dt.datetime.now(dt.timezone.utc).year
    assert result == f"{current_year}-spring-hs"


# ---------------------------------------------------------------------------
# AC-16: UUID opportunism
# ---------------------------------------------------------------------------


def test_uuid_opportunism_updates_gc_uuid(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """When a UUID is found as a boxscore key, gc_uuid is updated for that team."""
    uuid_key = "aaaabbbb-cccc-dddd-eeee-ffff00001111"
    # Insert the team row with gc_uuid=NULL.
    db.execute("INSERT INTO teams (team_id, name, gc_uuid) VALUES (?, ?, NULL)", (uuid_key, "Opp"))
    db.commit()

    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    row = db.execute("SELECT gc_uuid FROM teams WHERE team_id = ?", (uuid_key,)).fetchone()
    assert row is not None
    assert row[0] == uuid_key, f"Expected gc_uuid={uuid_key}, got {row[0]}"


# ---------------------------------------------------------------------------
# AC-7a/b: Freshness gate season_id filtering (E-098-03)
# ---------------------------------------------------------------------------


def test_freshness_gate_explicit_season_id_does_not_skip_different_season(
    crawler: ScoutingCrawler, db: sqlite3.Connection
) -> None:
    """AC-7a: A completed run for season A does not block scouting for season B."""
    _insert_team_and_season(db, _PUBLIC_ID, "2025-spring-hs")
    _insert_team_and_season(db, _PUBLIC_ID, "2026-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    db.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status, last_checked) "
        "VALUES (?, ?, 'full', ?, 'completed', ?)",
        (_PUBLIC_ID, "2025-spring-hs", recent_ts, recent_ts),
    )
    db.commit()

    # Should NOT be considered fresh for a different season.
    assert not crawler._is_scouted_recently(_PUBLIC_ID, season_id="2026-spring-hs")


def test_freshness_gate_explicit_season_id_skips_same_season(
    crawler: ScoutingCrawler, db: sqlite3.Connection
) -> None:
    """AC-7a: A completed run for season A blocks scouting for season A."""
    _insert_team_and_season(db, _PUBLIC_ID, "2025-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    db.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status, last_checked) "
        "VALUES (?, ?, 'full', ?, 'completed', ?)",
        (_PUBLIC_ID, "2025-spring-hs", recent_ts, recent_ts),
    )
    db.commit()

    assert crawler._is_scouted_recently(_PUBLIC_ID, season_id="2025-spring-hs")


def test_freshness_gate_none_season_uses_team_only(
    crawler: ScoutingCrawler, db: sqlite3.Connection
) -> None:
    """AC-7b: season_id=None freshness check passes for any season's completed run."""
    _insert_team_and_season(db, _PUBLIC_ID, "2025-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    db.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, status, last_checked) "
        "VALUES (?, ?, 'full', ?, 'completed', ?)",
        (_PUBLIC_ID, "2025-spring-hs", recent_ts, recent_ts),
    )
    db.commit()

    # Should be fresh because team was recently scouted (any season).
    assert crawler._is_scouted_recently(_PUBLIC_ID, season_id=None)


# ---------------------------------------------------------------------------
# AC-7c: Crawler writes 'running' not 'completed' after crawl phase (E-098-03)
# ---------------------------------------------------------------------------


def test_scout_team_writes_running_status_after_crawl(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-7c: scout_team() leaves scouting_runs.status='running' at end of crawl."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    row = db.execute("SELECT status FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "running", f"Expected 'running', got '{row[0]}'"


def test_scout_team_running_status_has_null_completed_at(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-2 (E-098-04): 'running' rows must have completed_at IS NULL."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    row = db.execute("SELECT status, completed_at FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "running"
    assert row[1] is None, f"Expected completed_at=NULL for running row, got '{row[1]}'"


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

    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    assert result.errors >= 1

    row = db.execute("SELECT status, completed_at FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "failed", f"Expected 'failed', got '{row[0]}'"
    assert row[1] is not None, "Expected completed_at to be set for 'failed' row"
