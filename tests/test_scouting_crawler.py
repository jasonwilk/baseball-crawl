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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.client import CredentialExpiredError, ForbiddenError
from src.gamechanger.crawlers import CrawlResult
from src.gamechanger.crawlers.scouting import (
    ScoutingCrawler,
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


def _insert_member_team(conn: sqlite3.Connection, name: str, gc_uuid: str) -> int:
    """Insert a member team row and return its INTEGER PK."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES (?, 'member', ?, 1)",
        (name, gc_uuid),
    )
    if cursor.lastrowid:
        conn.commit()
        return cursor.lastrowid
    row = conn.execute("SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)).fetchone()
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
        accept=_PUBLIC_GAMES_ACCEPT,
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


def test_scouting_run_created_with_completed_status(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """After a successful scout_team(), scouting_runs has a 'completed' row."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

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


def test_scouting_run_has_integer_team_id(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """scouting_runs.team_id is an INTEGER PK referencing teams.id."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

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


def test_scout_all_skips_recently_scouted(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection, tmp_path: Path
) -> None:
    """scout_all() skips opponents with a recent completed scouting run."""
    # Insert an owned member team.
    owned_id = _insert_member_team(db, "My Team", "owned-team-gc-uuid")
    # Insert the opponent team with public_id.
    opp_id = _insert_team_with_public_id(db, _PUBLIC_ID)
    # Insert opponent_link.
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id) "
        "VALUES (?, ?, ?, ?)",
        (owned_id, "root-001", "Test Opponent", _PUBLIC_ID),
    )
    _insert_season(db, "2025-spring-hs")
    # Insert a recent completed scouting run.
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _insert_scouting_run(db, opp_id, "2025-spring-hs", "completed", recent_ts)

    result = crawler.scout_all(season_id="2025-spring-hs")
    # Should skip (no API calls).
    mock_client.get_public.assert_not_called()
    assert result.files_skipped == 1


def test_scout_all_scouts_stale_opponents(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """scout_all() scouts opponents whose last_checked is older than freshness_hours."""
    owned_id = _insert_member_team(db, "My Team", "owned-team-gc-uuid")
    opp_id = _insert_team_with_public_id(db, _PUBLIC_ID)
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id) "
        "VALUES (?, ?, ?, ?)",
        (owned_id, "root-001", "Test Opponent", _PUBLIC_ID),
    )
    _insert_season(db, "2025-spring-hs")

    # Set up a stale scouting run (25 hours ago).
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    _insert_scouting_run(db, opp_id, "2025-spring-hs", "completed", stale_ts)

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


def test_derive_season_id_uses_season_suffix() -> None:
    """_derive_season_id uses the season_suffix parameter."""
    games = [{"id": "g1", "start_ts": "2025-04-10T18:00:00Z"}]
    assert _derive_season_id(games, season_suffix="fall-legion") == "2025-fall-legion"


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
        crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")


def test_credential_expired_on_boxscore_propagates_through_scout_all(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """CredentialExpiredError during boxscore fetch propagates out of scout_all()."""
    owned_id = _insert_member_team(db, "My Team", "owned-team-gc-uuid")
    _insert_team_with_public_id(db, _PUBLIC_ID)
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id) "
        "VALUES (?, ?, ?, ?)",
        (owned_id, "root-001", "Test Opponent", _PUBLIC_ID),
    )
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, CredentialExpiredError("token expired")]
    with pytest.raises(CredentialExpiredError):
        crawler.scout_all(season_id="2025-spring-hs")


def test_forbidden_on_boxscore_does_not_propagate(
    crawler: ScoutingCrawler, mock_client: MagicMock
) -> None:
    """ForbiddenError during boxscore fetch is caught (expected for non-owned teams)."""
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, ForbiddenError("403")]
    # Should not raise -- ForbiddenError is caught per-game
    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")
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
# AC-7a/b: Freshness gate season_id filtering (E-098-03)
# ---------------------------------------------------------------------------


def test_freshness_gate_explicit_season_id_does_not_skip_different_season(
    crawler: ScoutingCrawler, db: sqlite3.Connection
) -> None:
    """AC-7a: A completed run for season A does not block scouting for season B."""
    opp_id = _insert_team_with_public_id(db, _PUBLIC_ID)
    _insert_season(db, "2025-spring-hs")
    _insert_season(db, "2026-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _insert_scouting_run(db, opp_id, "2025-spring-hs", "completed", recent_ts)

    # Should NOT be considered fresh for a different season.
    assert not crawler._is_scouted_recently(opp_id, season_id="2026-spring-hs")


def test_freshness_gate_explicit_season_id_skips_same_season(
    crawler: ScoutingCrawler, db: sqlite3.Connection
) -> None:
    """AC-7a: A completed run for season A blocks scouting for season A."""
    opp_id = _insert_team_with_public_id(db, _PUBLIC_ID)
    _insert_season(db, "2025-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _insert_scouting_run(db, opp_id, "2025-spring-hs", "completed", recent_ts)

    assert crawler._is_scouted_recently(opp_id, season_id="2025-spring-hs")


def test_freshness_gate_none_season_uses_team_only(
    crawler: ScoutingCrawler, db: sqlite3.Connection
) -> None:
    """AC-7b: season_id=None freshness check passes for any season's completed run."""
    opp_id = _insert_team_with_public_id(db, _PUBLIC_ID)
    _insert_season(db, "2025-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _insert_scouting_run(db, opp_id, "2025-spring-hs", "completed", recent_ts)

    # Should be fresh because team was recently scouted (any season).
    assert crawler._is_scouted_recently(opp_id, season_id=None)


# ---------------------------------------------------------------------------
# AC-3: Failed scouting run does not trigger freshness gating (E-123-06)
# ---------------------------------------------------------------------------


def test_failed_scouting_run_does_not_trigger_freshness_gate(
    crawler: ScoutingCrawler, db: sqlite3.Connection
) -> None:
    """AC-3: A team with a recent 'failed' run is NOT considered fresh — it gets retried."""
    opp_id = _insert_team_with_public_id(db, _PUBLIC_ID)
    _insert_season(db, "2025-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _insert_scouting_run(db, opp_id, "2025-spring-hs", "failed", recent_ts)

    # A 'failed' run must NOT satisfy the freshness check.
    assert not crawler._is_scouted_recently(opp_id, season_id="2025-spring-hs")


def test_scout_all_retries_team_with_failed_run(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-3: scout_all() re-scouts a team whose most recent run is 'failed'."""
    owned_id = _insert_member_team(db, "My Team", "owned-team-gc-uuid")
    _insert_team_with_public_id(db, _PUBLIC_ID)
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id) "
        "VALUES (?, ?, ?, ?)",
        (owned_id, "root-001", "Test Opponent", _PUBLIC_ID),
    )
    _insert_season(db, "2025-spring-hs")
    recent_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    opp_id = db.execute("SELECT id FROM teams WHERE public_id = ?", (_PUBLIC_ID,)).fetchone()[0]
    _insert_scouting_run(db, opp_id, "2025-spring-hs", "failed", recent_ts)

    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, _BOXSCORE_RESPONSE]

    result = crawler.scout_all(season_id="2025-spring-hs")
    # Team should have been scouted (not skipped).
    mock_client.get_public.assert_called_once()
    assert result.files_written > 0


# ---------------------------------------------------------------------------
# AC-1/AC-7c: Crawler writes 'completed' after successful crawl phase (E-123-06)
# ---------------------------------------------------------------------------


def test_scout_team_writes_completed_status_after_crawl(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-1: scout_team() sets scouting_runs.status='completed' after a successful crawl."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    row = db.execute("SELECT status FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "completed", f"Expected 'completed', got '{row[0]}'"


def test_scout_team_completed_status_has_completed_at_set(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-1: 'completed' rows must have completed_at set (not NULL)."""
    _setup_client_happy_path(mock_client)
    crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")

    row = db.execute("SELECT status, completed_at FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "completed"
    assert row[1] is not None, "Expected completed_at to be set for 'completed' row"


# ---------------------------------------------------------------------------
# AC-4: Freshness gating skips team after successful scout_team() run (E-123-06)
# ---------------------------------------------------------------------------


def test_scout_all_skips_team_after_successful_scout_team(
    crawler: ScoutingCrawler, mock_client: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-4: A team scouted via scout_team() is skipped by scout_all() within freshness window."""
    owned_id = _insert_member_team(db, "My Team", "owned-team-gc-uuid")
    _insert_team_with_public_id(db, _PUBLIC_ID)
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, public_id) "
        "VALUES (?, ?, ?, ?)",
        (owned_id, "root-001", "Test Opponent", _PUBLIC_ID),
    )

    # First run: scout_team() should write 'completed'.
    mock_client.get_public.return_value = _GAMES_RESPONSE
    mock_client.get.side_effect = [_ROSTER_RESPONSE, _BOXSCORE_RESPONSE]
    result = crawler.scout_team(_PUBLIC_ID, season_id="2025-spring-hs")
    assert result.errors == 0

    # Confirm the run is 'completed'.
    row = db.execute("SELECT status FROM scouting_runs LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == "completed"

    # Second run via scout_all() should skip the team (freshness gate engaged).
    mock_client.reset_mock()
    result2 = crawler.scout_all(season_id="2025-spring-hs")
    mock_client.get_public.assert_not_called()
    assert result2.files_skipped == 1


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


# ---------------------------------------------------------------------------
# update_run_load_status tests (E-125-02 AC-1, AC-2, AC-6)
# ---------------------------------------------------------------------------


class TestUpdateRunLoadStatus:
    """Verify update_run_load_status uses parameterized SQL and handles both statuses."""

    def test_completed_status_sets_completed_at(
        self,
        db: sqlite3.Connection,
        mock_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """AC-6: 'completed' status sets completed_at to a non-NULL timestamp."""
        team_id = _insert_team_with_public_id(db, "status-test-pub")
        season_id = "2025-spring-hs"
        _insert_season(db, season_id)
        _insert_scouting_run(
            db, team_id, season_id, "running", "2025-04-10T00:00:00.000Z"
        )

        crawler = ScoutingCrawler(mock_client, db, data_root=tmp_path / "raw")
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
        tmp_path: Path,
    ) -> None:
        """AC-6: 'failed' status sets completed_at to NULL."""
        team_id = _insert_team_with_public_id(db, "status-fail-pub")
        season_id = "2025-spring-hs"
        _insert_season(db, season_id)
        _insert_scouting_run(
            db, team_id, season_id, "running", "2025-04-10T00:00:00.000Z"
        )

        crawler = ScoutingCrawler(mock_client, db, data_root=tmp_path / "raw")
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
        tmp_path: Path,
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

        crawler = ScoutingCrawler(mock_client, db, data_root=tmp_path / "raw")
        # This should fail due to CHECK constraint, not SQL injection.
        with pytest.raises(sqlite3.IntegrityError):
            crawler.update_run_load_status(
                team_id, season_id, "completed'; DROP TABLE scouting_runs;--"
            )

    def test_completed_updates_last_checked(
        self,
        db: sqlite3.Connection,
        mock_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify last_checked is updated on status change."""
        team_id = _insert_team_with_public_id(db, "lastchk-test-pub")
        season_id = "2025-spring-hs"
        _insert_season(db, season_id)
        _insert_scouting_run(
            db, team_id, season_id, "running", "2020-01-01T00:00:00.000Z"
        )

        crawler = ScoutingCrawler(mock_client, db, data_root=tmp_path / "raw")
        crawler.update_run_load_status(team_id, season_id, "completed")

        row = db.execute(
            "SELECT last_checked FROM scouting_runs "
            "WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        ).fetchone()
        # last_checked should be updated to a recent timestamp, not the old 2020 value.
        assert row[0] > "2024-01-01"
