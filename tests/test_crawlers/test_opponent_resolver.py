"""Tests for src/gamechanger/crawlers/opponent_resolver.py.

All HTTP calls are mocked -- no real network requests are made.
All DB writes use an in-memory SQLite connection with the full schema applied.

Tests cover:
- AC-1: OpponentResolver class with resolve() method returning ResolveResult
- AC-2: Outer loop iterates member teams; fetches opponents; resolves via GET /teams/{id}
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
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.client import CredentialExpiredError, ForbiddenError, GameChangerAPIError
from src.gamechanger.config import CrawlConfig, TeamEntry
from src.gamechanger.crawlers.opponent_resolver import OpponentResolver, ResolveResult

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """In-memory SQLite connection with full schema applied via run_migrations."""
    db_path = tmp_path / "test_opponent_resolver.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

_OWN_TEAM_GC_UUID = "owned-team-uuid-001"
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
    "owning_team_id": _OWN_TEAM_GC_UUID,
    "name": _TEAM_NAME,
    "is_hidden": False,
    "progenitor_team_id": _PROGENITOR_ID,
}

_OPPONENT_NO_PROGENITOR = {
    "root_team_id": "root-bbb-002",
    "owning_team_id": _OWN_TEAM_GC_UUID,
    "name": "Unknown Team",
    "is_hidden": False,
    # no progenitor_team_id key
}

_OPPONENT_HIDDEN = {
    "root_team_id": "root-ccc-003",
    "owning_team_id": _OWN_TEAM_GC_UUID,
    "name": "Hidden Duplicate",
    "is_hidden": True,
    "progenitor_team_id": "progenitor-ccc-003",
}


def _insert_team(
    db: sqlite3.Connection,
    gc_uuid: str,
    name: str = "Team",
    membership_type: str = "member",
    is_active: int = 1,
) -> int:
    """Insert a team row and return its INTEGER PK."""
    cursor = db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active) VALUES (?, ?, ?, ?)",
        (gc_uuid, name, membership_type, is_active),
    )
    db.commit()
    return cursor.lastrowid


def _make_config(team_pairs: list[tuple[str, int]] | None = None) -> CrawlConfig:
    """Build a CrawlConfig from a list of (gc_uuid, internal_id) pairs."""
    if team_pairs is None:
        # Default: not used directly; callers should pass pairs when internal_id matters
        team_pairs = [(_OWN_TEAM_GC_UUID, 0)]
    teams = [
        TeamEntry(id=gc_uuid, name=f"Team {gc_uuid}", classification="jv", internal_id=pk)
        for gc_uuid, pk in team_pairs
    ]
    return CrawlConfig(season=_SEASON, member_teams=teams)


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


# ---------------------------------------------------------------------------
# AC-1: class exists and returns ResolveResult
# ---------------------------------------------------------------------------


def test_resolve_returns_resolve_result(db: sqlite3.Connection) -> None:
    """resolve() returns a ResolveResult dataclass with count fields."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert isinstance(result, ResolveResult)
    assert hasattr(result, "resolved")
    assert hasattr(result, "unlinked")
    assert hasattr(result, "stored_hidden")
    assert hasattr(result, "errors")


# ---------------------------------------------------------------------------
# AC-2: outer loop iterates member teams and resolves via progenitor_team_id
# ---------------------------------------------------------------------------


def test_resolve_calls_opponents_endpoint_per_team(db: sqlite3.Connection) -> None:
    """resolve() calls GET /teams/{team_id}/opponents for each member team."""
    team_a = "owned-aaa"
    team_b = "owned-bbb"
    pk_a = _insert_team(db, team_a)
    pk_b = _insert_team(db, team_b)
    client = _make_client(paginated_return=[])
    config = _make_config([(team_a, pk_a), (team_b, pk_b)])
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
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.resolved == 1
    assert result.unlinked == 0
    assert result.errors == 0

    links = _fetch_links(db)
    assert len(links) == 1
    link = links[0]
    assert link["our_team_id"] == own_pk
    assert link["root_team_id"] == _ROOT_TEAM_ID
    # resolved_team_id is an INTEGER PK -- verify it's not None and check via teams table
    assert link["resolved_team_id"] is not None
    resolved_row = db.execute(
        "SELECT gc_uuid FROM teams WHERE id = ?", (link["resolved_team_id"],)
    ).fetchone()
    assert resolved_row is not None
    assert resolved_row[0] == _PROGENITOR_ID
    assert link["public_id"] == _PUBLIC_ID
    assert link["resolution_method"] == "auto"
    assert link["opponent_name"] == _TEAM_NAME
    assert link["is_hidden"] == 0


def test_resolve_fetches_team_detail_for_progenitor(db: sqlite3.Connection) -> None:
    """Resolver calls GET /teams/{progenitor_team_id} with correct accept header."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
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
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(paginated_return=[_OPPONENT_NO_PROGENITOR])
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
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
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(paginated_return=[_OPPONENT_NO_PROGENITOR])
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    client.get.assert_not_called()


# ---------------------------------------------------------------------------
# AC-4: manual resolution protection
# ---------------------------------------------------------------------------


def test_resolve_does_not_overwrite_manual_link(db: sqlite3.Connection) -> None:
    """Auto-resolution does not overwrite a row with resolution_method='manual'."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Pre-insert a manual resolved team and link
    manual_gc_uuid = "manual-resolved-uuid"
    manual_public_id = "manualPubSlug"
    manual_pk = _insert_team(db, manual_gc_uuid, "Manual Team", membership_type="tracked", is_active=0)
    db.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, resolved_team_id,
             public_id, resolution_method, resolved_at, is_hidden)
        VALUES (?, ?, ?, ?, ?, 'manual', datetime('now'), 0)
        """,
        (own_pk, _ROOT_TEAM_ID, _TEAM_NAME, manual_pk, manual_public_id),
    )
    db.commit()

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    links = _fetch_links(db)
    assert len(links) == 1
    link = links[0]
    # Manual link fields must be preserved
    assert link["resolved_team_id"] == manual_pk
    assert link["public_id"] == manual_public_id
    assert link["resolution_method"] == "manual"


# ---------------------------------------------------------------------------
# AC-5: FK satisfaction -- team row ensured before opponent_links insert
# ---------------------------------------------------------------------------


def test_resolve_creates_team_stub_for_resolved_team(db: sqlite3.Connection) -> None:
    """Resolver inserts a teams row for the resolved team before the FK insert."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _TEAM_NAME  # real name, not UUID stub


def test_resolve_updates_uuid_stub_to_real_name(db: sqlite3.Connection) -> None:
    """If a UUID-as-name stub exists, resolver updates it with the real team name."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Insert a stub where name = gc_uuid (UUID-as-name, from game_loader pattern)
    _insert_team(db, _PROGENITOR_ID, _PROGENITOR_ID, membership_type="tracked", is_active=0)

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == _TEAM_NAME


def test_resolve_preserves_real_team_name(db: sqlite3.Connection) -> None:
    """If a team row already has a real name, resolver does not overwrite it."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    existing_name = "Pre-Existing Real Name"
    _insert_team(db, _PROGENITOR_ID, existing_name, membership_type="tracked", is_active=0)

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT name FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == existing_name  # unchanged


# ---------------------------------------------------------------------------
# AC-6: error handling
# ---------------------------------------------------------------------------


def test_resolve_403_logs_warning_and_skips(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """403 ForbiddenError is logged at WARNING and the opponent is skipped."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=ForbiddenError("403 Forbidden"),
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
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
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=CredentialExpiredError("401 Unauthorized"),
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with pytest.raises(CredentialExpiredError):
            resolver.resolve()


def test_resolve_5xx_logs_warning_and_skips(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """5xx GameChangerAPIError is logged at WARNING and the opponent is skipped."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=GameChangerAPIError("Server error HTTP 500"),
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
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
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_side_effect=GameChangerAPIError("Unexpected status 404"),
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
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
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
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
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR, _OPPONENT_NO_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()
        resolver.resolve()

    links = _fetch_links(db)
    assert len(links) == 2  # exactly one per opponent, no duplicates


def test_resolve_hidden_opponent_with_progenitor_stored(db: sqlite3.Connection) -> None:
    """Hidden opponent with progenitor_team_id is stored with is_hidden=1."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_HIDDEN],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.stored_hidden == 1
    assert result.resolved == 1
    assert result.unlinked == 0
    assert result.errors == 0

    links = _fetch_links(db)
    assert len(links) == 1
    assert links[0]["is_hidden"] == 1
    assert links[0]["root_team_id"] == _OPPONENT_HIDDEN["root_team_id"]


def test_resolve_hidden_opponent_without_progenitor_stored(db: sqlite3.Connection) -> None:
    """Hidden opponent without progenitor_team_id is stored as unlinked with is_hidden=1."""
    hidden_no_progenitor = {
        "root_team_id": "root-hidden-no-prog",
        "owning_team_id": _OWN_TEAM_GC_UUID,
        "name": "Hidden No Progenitor",
        "is_hidden": True,
    }
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(paginated_return=[hidden_no_progenitor])
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.stored_hidden == 1
    assert result.unlinked == 1
    assert result.resolved == 0
    assert result.errors == 0

    links = _fetch_links(db)
    assert len(links) == 1
    assert links[0]["is_hidden"] == 1
    assert links[0]["resolved_team_id"] is None


def test_resolve_non_hidden_opponent_stored_hidden_zero(db: sqlite3.Connection) -> None:
    """Non-hidden opponent is stored with is_hidden=0 (existing behavior preserved)."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.stored_hidden == 0
    links = _fetch_links(db)
    assert links[0]["is_hidden"] == 0


# ---------------------------------------------------------------------------
# AC-3 (E-120-01): None internal_id raises ValueError, counted in result.errors
# ---------------------------------------------------------------------------


def test_resolve_team_none_internal_id_counted_as_error(db: sqlite3.Connection) -> None:
    """When TeamEntry.internal_id is None, resolve() counts one error (no silent 0 fallback)."""
    team_with_none_pk = TeamEntry(
        id=_OWN_TEAM_GC_UUID,
        name=_OWN_TEAM_NAME,
        classification="jv",
        internal_id=None,
    )
    config = CrawlConfig(season=_SEASON, member_teams=[team_with_none_pk])
    client = _make_client(paginated_return=[_OPPONENT_WITH_PROGENITOR], get_return=_TEAM_DETAIL)
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.errors == 1
    assert result.resolved == 0
    assert _fetch_links(db) == []


def test_resolve_copies_is_hidden_flag(db: sqlite3.Connection) -> None:
    """is_hidden is copied from the API response into opponent_links on update."""
    hidden_with_progenitor = {
        "root_team_id": "root-hidden-progenitor",
        "owning_team_id": _OWN_TEAM_GC_UUID,
        "name": "Hidden With Progenitor",
        "is_hidden": True,
        "progenitor_team_id": _PROGENITOR_ID,
    }
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Process as visible first
    visible = dict(hidden_with_progenitor, is_hidden=False)
    client = _make_client(
        paginated_return=[visible],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result1 = resolver.resolve()

    assert result1.stored_hidden == 0
    link = _fetch_links(db)[0]
    assert link["is_hidden"] == 0

    # Re-run with is_hidden=True -- upsert should update the flag
    client2 = _make_client(
        paginated_return=[hidden_with_progenitor],
        get_return=_TEAM_DETAIL,
    )
    resolver2 = OpponentResolver(client2, config, db)
    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result2 = resolver2.resolve()

    assert result2.stored_hidden == 1
    link2 = _fetch_links(db)[0]
    assert link2["is_hidden"] == 1
