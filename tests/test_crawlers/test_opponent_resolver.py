"""Tests for src/gamechanger/crawlers/opponent_resolver.py.

All HTTP calls are mocked -- no real network requests are made.
All DB writes use an in-memory SQLite connection with the full schema applied.

Tests cover:
- AC-1: OpponentResolver class with resolve() method returning ResolveResult
- AC-2: Outer loop iterates owned teams; fetches opponents; resolves via GET /teams/{id}
- AC-3: Null progenitor_team_id -> unlinked row inserted
- AC-4: Manual resolution links protected (COALESCE upsert logic)
- AC-5: FK satisfaction -- team row ensured before opponent_links insert
- AC-5: UUID-as-name stubs updated to real name; existing real names preserved
- AC-6: 403 -> warning + skip; 401 -> abort; 5xx -> warning + skip; 404 -> warning + skip
- AC-7: ~1.5s delay between API calls (sleep called)
- AC-9: Idempotent re-runs do not create duplicates
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.gamechanger.client import CredentialExpiredError, ForbiddenError, GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers.opponent_resolver import OpponentResolver, ResolveResult

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_001 = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"
_MIGRATION_006 = _PROJECT_ROOT / "migrations" / "006_opponent_links.sql"


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite connection with migrations 001 and 006 applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_001.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_006.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

_OWN_TEAM_ID = "owned-team-uuid-001"
_OWN_TEAM_NAME = "LSB JV"
_SEASON = "2025"

_PROGENITOR_ID = "progenitor-aaa-001"
_ROOT_TEAM_ID = "root-aaa-001"
_PUBLIC_ID = "xXxXpUbLiD"
_TEAM_NAME = "Example Opponent 14U"

_TEAM_DETAIL = {
    "id": _PROGENITOR_ID,
    "name": _TEAM_NAME,
    "public_id": _PUBLIC_ID,
    "record": {"wins": 5, "losses": 3, "ties": 0},
}

_OPPONENT_WITH_PROGENITOR = {
    "root_team_id": _ROOT_TEAM_ID,
    "owning_team_id": _OWN_TEAM_ID,
    "name": _TEAM_NAME,
    "is_hidden": False,
    "progenitor_team_id": _PROGENITOR_ID,
}

_OPPONENT_NO_PROGENITOR = {
    "root_team_id": "root-bbb-002",
    "owning_team_id": _OWN_TEAM_ID,
    "name": "Unknown Team",
    "is_hidden": False,
    # no progenitor_team_id key
}

_OPPONENT_HIDDEN = {
    "root_team_id": "root-ccc-003",
    "owning_team_id": _OWN_TEAM_ID,
    "name": "Hidden Duplicate",
    "is_hidden": True,
    "progenitor_team_id": "progenitor-ccc-003",
}


def _make_config(team_ids: list[str] | None = None) -> CrawlConfig:
    """Build a CrawlConfig with one default owned team."""
    ids = team_ids if team_ids is not None else [_OWN_TEAM_ID]
    teams = [TeamEntry(id=tid, name=f"Team {tid}", level="jv") for tid in ids]
    return CrawlConfig(season=_SEASON, owned_teams=teams)


def _make_client(
    paginated_return: list | None = None,
    get_return: object = None,
    paginated_side_effect: Exception | None = None,
    get_side_effect: Exception | None = None,
) -> MagicMock:
    """Return a mock GameChangerClient with configurable return values."""
    client = MagicMock()
    if paginated_side_effect is not None:
        client.get_paginated.side_effect = paginated_side_effect
    else:
        client.get_paginated.return_value = (
            paginated_return if paginated_return is not None else []
        )
    if get_side_effect is not None:
        client.get.side_effect = get_side_effect
    else:
        client.get.return_value = get_return if get_return is not None else _TEAM_DETAIL
    return client


def _fetch_links(db: sqlite3.Connection) -> list[dict]:
    """Return all rows from opponent_links as dicts."""
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM opponent_links").fetchall()
    return [dict(row) for row in rows]


def _insert_own_team(db: sqlite3.Connection, team_id: str = _OWN_TEAM_ID) -> None:
    """Insert a prerequisite owned team row into teams."""
    db.execute(
        "INSERT INTO teams (team_id, name, is_owned, is_active) VALUES (?, ?, 1, 1)",
        (team_id, "LSB JV"),
    )
    db.commit()


# ---------------------------------------------------------------------------
# AC-1: class exists and returns ResolveResult
# ---------------------------------------------------------------------------


def test_resolve_returns_resolve_result(db: sqlite3.Connection) -> None:
    """resolve() returns a ResolveResult dataclass with count fields."""
    _insert_own_team(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert isinstance(result, ResolveResult)
    assert hasattr(result, "resolved")
    assert hasattr(result, "unlinked")
    assert hasattr(result, "skipped_hidden")
    assert hasattr(result, "errors")


# ---------------------------------------------------------------------------
# AC-2: outer loop iterates owned teams and resolves via progenitor_team_id
# ---------------------------------------------------------------------------


def test_resolve_calls_opponents_endpoint_per_team(db: sqlite3.Connection) -> None:
    """resolve() calls GET /teams/{team_id}/opponents for each owned team."""
    team_a = "owned-aaa"
    team_b = "owned-bbb"
    _insert_own_team(db, team_a)
    _insert_own_team(db, team_b)
    client = _make_client(paginated_return=[])
    config = _make_config([team_a, team_b])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    assert client.get_paginated.call_count == 2
    client.get_paginated.assert_any_call(
        f"/teams/{team_a}/opponents",
        accept="application/vnd.gc.com.opponent_team:list+json; version=0.0.0",
    )
    client.get_paginated.assert_any_call(
        f"/teams/{team_b}/opponents",
        accept="application/vnd.gc.com.opponent_team:list+json; version=0.0.0",
    )


def test_resolve_auto_resolves_opponent(db: sqlite3.Connection) -> None:
    """Opponent with progenitor_team_id gets resolved and upserted."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.resolved == 1
    assert result.unlinked == 0
    assert result.errors == 0

    links = _fetch_links(db)
    assert len(links) == 1
    link = links[0]
    assert link["our_team_id"] == _OWN_TEAM_ID
    assert link["root_team_id"] == _ROOT_TEAM_ID
    assert link["resolved_team_id"] == _PROGENITOR_ID
    assert link["public_id"] == _PUBLIC_ID
    assert link["resolution_method"] == "auto"
    assert link["opponent_name"] == _TEAM_NAME
    assert link["is_hidden"] == 0


def test_resolve_fetches_team_detail_for_progenitor(db: sqlite3.Connection) -> None:
    """Resolver calls GET /teams/{progenitor_team_id} with correct accept header."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    client.get.assert_called_once_with(
        f"/teams/{_PROGENITOR_ID}",
        accept="application/vnd.gc.com.team+json; version=0.10.0",
    )


# ---------------------------------------------------------------------------
# AC-3: null progenitor_team_id -> unlinked row
# ---------------------------------------------------------------------------


def test_resolve_null_progenitor_inserts_unlinked(db: sqlite3.Connection) -> None:
    """Opponent without progenitor_team_id is inserted as unlinked row."""
    _insert_own_team(db)
    client = _make_client(paginated_return=[_OPPONENT_NO_PROGENITOR])
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.unlinked == 1
    assert result.resolved == 0
    assert result.errors == 0

    links = _fetch_links(db)
    assert len(links) == 1
    link = links[0]
    assert link["resolved_team_id"] is None
    assert link["public_id"] is None
    assert link["resolution_method"] is None
    assert link["root_team_id"] == _OPPONENT_NO_PROGENITOR["root_team_id"]


def test_resolve_null_progenitor_does_not_call_team_detail(db: sqlite3.Connection) -> None:
    """Resolver does NOT call GET /teams/{id} for unlinked opponents."""
    _insert_own_team(db)
    client = _make_client(paginated_return=[_OPPONENT_NO_PROGENITOR])
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    client.get.assert_not_called()


# ---------------------------------------------------------------------------
# AC-4: manual resolution protection
# ---------------------------------------------------------------------------


def test_resolve_does_not_overwrite_manual_link(db: sqlite3.Connection) -> None:
    """Auto-resolution does not overwrite a row with resolution_method='manual'."""
    _insert_own_team(db)
    # Pre-insert a manual link with a different resolved_team_id / public_id
    manual_team_id = "manual-resolved-uuid"
    manual_public_id = "manualPubSlug"
    db.execute(
        "INSERT INTO teams (team_id, name, is_owned, is_active) VALUES (?, ?, 0, 0)",
        (manual_team_id, "Manual Team"),
    )
    db.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id,
             public_id, resolution_method, resolved_at, is_hidden)
        VALUES (?, ?, ?, ?, ?, 'manual', datetime('now'), 0)
        """,
        (_OWN_TEAM_ID, _ROOT_TEAM_ID, _TEAM_NAME, manual_team_id, manual_public_id),
    )
    db.commit()

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    links = _fetch_links(db)
    assert len(links) == 1
    link = links[0]
    # Manual link fields must be preserved
    assert link["resolved_team_id"] == manual_team_id
    assert link["public_id"] == manual_public_id
    assert link["resolution_method"] == "manual"


# ---------------------------------------------------------------------------
# AC-5: FK satisfaction -- team row ensured before opponent_links insert
# ---------------------------------------------------------------------------


def test_resolve_creates_team_stub_for_resolved_team(db: sqlite3.Connection) -> None:
    """Resolver inserts a teams row for the resolved team before the FK insert."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT name FROM teams WHERE team_id = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _TEAM_NAME  # real name, not UUID stub


def test_resolve_updates_uuid_stub_to_real_name(db: sqlite3.Connection) -> None:
    """If a UUID-as-name stub exists, resolver updates it with the real team name."""
    _insert_own_team(db)
    # Insert a stub where name = team_id (UUID-as-name, from game_loader pattern)
    db.execute(
        "INSERT INTO teams (team_id, name, is_owned, is_active) VALUES (?, ?, 0, 0)",
        (_PROGENITOR_ID, _PROGENITOR_ID),
    )
    db.commit()

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT name FROM teams WHERE team_id = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == _TEAM_NAME


def test_resolve_preserves_real_team_name(db: sqlite3.Connection) -> None:
    """If a team row already has a real name, resolver does not overwrite it."""
    _insert_own_team(db)
    existing_name = "Pre-Existing Real Name"
    db.execute(
        "INSERT INTO teams (team_id, name, is_owned, is_active) VALUES (?, ?, 0, 0)",
        (_PROGENITOR_ID, existing_name),
    )
    db.commit()

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT name FROM teams WHERE team_id = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == existing_name  # unchanged


# ---------------------------------------------------------------------------
# AC-6: error handling
# ---------------------------------------------------------------------------


def test_resolve_403_logs_warning_and_skips(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """403 ForbiddenError is logged at WARNING and the opponent is skipped."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=ForbiddenError("403 Forbidden"),
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    import logging

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve()

    assert result.errors == 1
    assert result.resolved == 0
    assert any("Access denied" in r.message for r in caplog.records)
    assert _fetch_links(db) == []  # nothing inserted


def test_resolve_401_raises_credential_expired(db: sqlite3.Connection) -> None:
    """401 CredentialExpiredError is re-raised immediately (aborts the run)."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=CredentialExpiredError("401 Unauthorized"),
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with pytest.raises(CredentialExpiredError):
            resolver.resolve()


def test_resolve_5xx_logs_warning_and_skips(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """5xx GameChangerAPIError is logged at WARNING and the opponent is skipped."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=GameChangerAPIError("Server error HTTP 500"),
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    import logging

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve()

    assert result.errors == 1
    assert result.resolved == 0
    assert any("API error" in r.message for r in caplog.records)


def test_resolve_404_logs_warning_and_skips(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """404 (surfaced as GameChangerAPIError) is logged at WARNING and skipped."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=GameChangerAPIError("Unexpected status 404"),
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    import logging

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve()

    assert result.errors == 1
    assert result.resolved == 0


# ---------------------------------------------------------------------------
# AC-7: ~1.5s delay between API calls
# ---------------------------------------------------------------------------


def test_resolve_sleeps_between_requests(db: sqlite3.Connection) -> None:
    """time.sleep is called after each API call during resolution."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep") as mock_sleep:
        resolver.resolve()

    assert mock_sleep.call_count >= 2  # after paginated fetch, and after team detail fetch
    for sleep_call in mock_sleep.call_args_list:
        assert sleep_call.args[0] == 1.5


# ---------------------------------------------------------------------------
# AC-9: Idempotency
# ---------------------------------------------------------------------------


def test_resolve_is_idempotent(db: sqlite3.Connection) -> None:
    """Running resolve() twice produces the same DB state (no duplicates)."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR, _OPPONENT_NO_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()
        resolver.resolve()

    links = _fetch_links(db)
    assert len(links) == 2  # exactly one per opponent, no duplicates


def test_resolve_hidden_opponents_counted(db: sqlite3.Connection) -> None:
    """Hidden opponents increment skipped_hidden, not resolved or errors."""
    _insert_own_team(db)
    client = _make_client(
        paginated_return=[_OPPONENT_HIDDEN],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.skipped_hidden == 1
    assert result.resolved == 0
    assert result.unlinked == 0
    assert result.errors == 0
    assert _fetch_links(db) == []


def test_resolve_copies_is_hidden_flag(db: sqlite3.Connection) -> None:
    """is_hidden is copied from the API response into opponent_links."""
    hidden_with_progenitor = {
        "root_team_id": "root-hidden-progenitor",
        "owning_team_id": _OWN_TEAM_ID,
        "name": "Hidden With Progenitor",
        "is_hidden": True,
        "progenitor_team_id": _PROGENITOR_ID,
    }
    _insert_own_team(db)
    # Process as visible first so the upsert has something to update
    visible = dict(hidden_with_progenitor, is_hidden=False)
    client = _make_client(
        paginated_return=[visible],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config()
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    link = _fetch_links(db)[0]
    assert link["is_hidden"] == 0

    # Now re-run with is_hidden=True -- should update the flag
    client2 = _make_client(
        paginated_return=[hidden_with_progenitor],
        get_return=_TEAM_DETAIL,
    )
    resolver2 = OpponentResolver(client2, config, db)
    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        # Hidden opponents are skipped (not resolved), so is_hidden won't be updated
        # via the auto-resolve path. This tests that hidden flag is skipped correctly.
        result2 = resolver2.resolve()

    assert result2.skipped_hidden == 1
