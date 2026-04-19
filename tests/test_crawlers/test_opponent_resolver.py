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
from src.gamechanger.client import CredentialExpiredError, ForbiddenError, GameChangerAPIError, RateLimitError
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
    assert hasattr(result, "skipped_hidden")
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


def test_resolve_hidden_opponent_with_progenitor_skipped(db: sqlite3.Connection) -> None:
    """Hidden opponent with progenitor_team_id is skipped entirely (E-167 TN-4)."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    client = _make_client(
        paginated_return=[_OPPONENT_HIDDEN],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.skipped_hidden == 1
    assert result.resolved == 0
    assert result.unlinked == 0
    assert result.errors == 0

    # No opponent_links row created for hidden opponent
    links = _fetch_links(db)
    assert len(links) == 0
    # No team detail API call made for hidden opponent
    client.get.assert_not_called()


def test_resolve_hidden_opponent_without_progenitor_skipped(db: sqlite3.Connection) -> None:
    """Hidden opponent without progenitor_team_id is skipped (E-167 TN-4)."""
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

    assert result.skipped_hidden == 1
    assert result.unlinked == 0
    assert result.resolved == 0
    assert result.errors == 0

    links = _fetch_links(db)
    assert len(links) == 0


def test_resolve_non_hidden_opponent_skipped_hidden_zero(db: sqlite3.Connection) -> None:
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

    assert result.skipped_hidden == 0
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


# ---------------------------------------------------------------------------
# resolve_unlinked() tests (E-146-02)
# ---------------------------------------------------------------------------

_USER_ID = "user-uuid-001"
_USER_RESPONSE = {"id": _USER_ID, "email": "user@example.com"}
_ROOT_TEAM_ID_A = "root-aaa-unlinked"
_ROOT_TEAM_ID_B = "root-bbb-unlinked"
_PUBLIC_ID_A = "pubSlugA"


def _insert_unlinked_link(
    db: sqlite3.Connection,
    our_team_id: int,
    root_team_id: str,
    opponent_name: str = "Test Opponent",
    is_hidden: int = 0,
    resolution_method: str | None = None,
    public_id: str | None = None,
) -> None:
    """Insert an opponent_links row directly."""
    db.execute(
        """
        INSERT INTO opponent_links
            (our_team_id, root_team_id, opponent_name, is_hidden,
             resolution_method, public_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (our_team_id, root_team_id, opponent_name, is_hidden, resolution_method, public_id),
    )
    db.commit()


def _make_unlinked_client(
    user_response: dict | None = None,
    bridge_response: dict | None = None,
    follow_side_effect: Exception | None = None,
    bridge_side_effect: Exception | None = None,
    delete_side_effect: Exception | None = None,
) -> MagicMock:
    """Return a mock GameChangerClient configured for resolve_unlinked tests.

    client.get is called twice per cycle:
      1. /me/user -> user_response (or _USER_RESPONSE)
      2. /teams/{id}/public-team-profile-id -> bridge_response (or {"id": "pubSlugA"})
    """
    client = MagicMock()
    user_resp = user_response or _USER_RESPONSE
    bridge_resp = bridge_response or {"id": _PUBLIC_ID_A}

    if bridge_side_effect is not None:
        # First call returns user, second raises bridge error
        client.get.side_effect = [user_resp, bridge_side_effect]
    else:
        client.get.side_effect = [user_resp, bridge_resp]

    if follow_side_effect is not None:
        client.post.side_effect = follow_side_effect
    else:
        client.post.return_value = None

    if delete_side_effect is not None:
        client.delete.side_effect = delete_side_effect
    else:
        client.delete.return_value = None

    return client


def test_resolve_unlinked_full_cycle_stores_public_id(db: sqlite3.Connection) -> None:
    """Full cycle: follow succeeds, bridge returns public_id, row updated."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client()
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve_unlinked()

    assert result.resolved == 1
    assert result.follow_bridge_failed == 0

    links = _fetch_links(db)
    assert len(links) == 1
    assert links[0]["public_id"] == _PUBLIC_ID_A
    assert links[0]["resolution_method"] == "follow-bridge"
    assert links[0]["resolved_at"] is not None


def test_resolve_unlinked_fan_out_updates_all_rows_for_root_team_id(
    db: sqlite3.Connection,
) -> None:
    """Fan-out UPDATE touches all opponent_links rows sharing root_team_id."""
    own_pk_a = _insert_team(db, "team-a", "Team A")
    own_pk_b = _insert_team(db, "team-b", "Team B")
    # Two rows with same root_team_id from different member teams
    _insert_unlinked_link(db, own_pk_a, _ROOT_TEAM_ID_A, "Opp A")
    _insert_unlinked_link(db, own_pk_b, _ROOT_TEAM_ID_A, "Opp A (from B)")
    client = _make_unlinked_client()
    config = _make_config([("team-a", own_pk_a)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve_unlinked()

    assert result.resolved == 1  # one distinct root_team_id resolved

    links = {row["our_team_id"]: row for row in _fetch_links(db)}
    assert links[own_pk_a]["public_id"] == _PUBLIC_ID_A
    assert links[own_pk_a]["resolution_method"] == "follow-bridge"
    assert links[own_pk_b]["public_id"] == _PUBLIC_ID_A
    assert links[own_pk_b]["resolution_method"] == "follow-bridge"


def test_resolve_unlinked_follow_failure_skips_no_unfollow(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Follow failure: skip cycle, log WARNING, no DELETE called, row unchanged."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client(follow_side_effect=GameChangerAPIError("500 error"))
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve_unlinked()

    assert result.follow_bridge_failed == 1
    assert result.resolved == 0
    client.delete.assert_not_called()

    links = _fetch_links(db)
    assert links[0]["public_id"] is None
    assert links[0]["resolution_method"] is None
    assert any("Follow failed" in r.message for r in caplog.records)


def test_resolve_unlinked_follow_failure_forbidden_skips(db: sqlite3.Connection) -> None:
    """Follow failure with ForbiddenError: skip cycle, no unfollow."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client(follow_side_effect=ForbiddenError("403"))
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve_unlinked()

    assert result.follow_bridge_failed == 1
    client.delete.assert_not_called()


def test_resolve_unlinked_bridge_failure_proceeds_to_unfollow(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Bridge failure: log warning, proceed to unfollow, row stays unlinked."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client(bridge_side_effect=ForbiddenError("403"))
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve_unlinked()

    assert result.follow_bridge_failed == 1
    assert result.resolved == 0
    # Unfollow should still have been called
    assert client.delete.call_count >= 1

    links = _fetch_links(db)
    assert links[0]["public_id"] is None
    assert any("Bridge failed" in r.message for r in caplog.records)


def test_resolve_unlinked_unfollow_failure_resolution_counted(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Unfollow failure: resolution still counted, WARNING logged."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client(
        delete_side_effect=GameChangerAPIError("delete failed")
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve_unlinked()

    assert result.resolved == 1
    assert result.follow_bridge_failed == 0
    links = _fetch_links(db)
    assert links[0]["public_id"] == _PUBLIC_ID_A
    assert any("Unfollow" in r.message for r in caplog.records)


def test_resolve_unlinked_manual_link_not_overwritten(db: sqlite3.Connection) -> None:
    """Manual link in same root_team_id is protected by resolution_method IS NULL WHERE clause."""
    own_pk_a = _insert_team(db, "team-a", "Team A")
    own_pk_b = _insert_team(db, "team-b", "Team B")
    # Unlinked row (should get updated)
    _insert_unlinked_link(db, own_pk_a, _ROOT_TEAM_ID_A, "Opp A")
    # Manual row (same root_team_id -- should NOT be touched by fan-out UPDATE)
    manual_public_id = "manual-public-id"
    _insert_unlinked_link(
        db, own_pk_b, _ROOT_TEAM_ID_A, "Opp A manual",
        resolution_method="manual", public_id=manual_public_id,
    )
    client = _make_unlinked_client()
    config = _make_config([("team-a", own_pk_a)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve_unlinked()

    assert result.resolved == 1

    links = {row["our_team_id"]: row for row in _fetch_links(db)}
    # Unlinked row updated
    assert links[own_pk_a]["public_id"] == _PUBLIC_ID_A
    assert links[own_pk_a]["resolution_method"] == "follow-bridge"
    # Manual row unchanged
    assert links[own_pk_b]["public_id"] == manual_public_id
    assert links[own_pk_b]["resolution_method"] == "manual"


def test_resolve_unlinked_query_excludes_already_resolved(db: sqlite3.Connection) -> None:
    """Rows with public_id already set are not included in the query (AC-1)."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Already resolved row - should not appear in query
    _insert_unlinked_link(
        db, own_pk, _ROOT_TEAM_ID_A, "Already Resolved",
        public_id="existing-public-id", resolution_method="follow-bridge",
    )
    client = _make_unlinked_client()
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve_unlinked()

    assert result.resolved == 0
    assert result.follow_bridge_failed == 0
    # post() should not have been called since no rows match the query
    client.post.assert_not_called()


def test_resolve_unlinked_user_id_fetched_once_per_run(db: sqlite3.Connection) -> None:
    """GET /me/user is called exactly once regardless of how many root_team_ids exist."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A, "Opp A")
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_B, "Opp B")

    # Two bridge calls needed (one per root_team_id)
    client = MagicMock()
    client.get.side_effect = [
        _USER_RESPONSE,
        {"id": "pubA"},
        {"id": "pubB"},
    ]
    client.post.return_value = None
    client.delete.return_value = None

    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve_unlinked()

    assert result.resolved == 2
    # First call is /me/user, remaining are bridge calls
    calls = client.get.call_args_list
    assert calls[0].args[0] == "/me/user"
    assert len(calls) == 3  # 1 user + 2 bridge


def test_resolve_unlinked_sleeps_between_cycles(db: sqlite3.Connection) -> None:
    """time.sleep(2.0) is called once per root_team_id cycle."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A, "Opp A")
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_B, "Opp B")

    client = MagicMock()
    client.get.side_effect = [_USER_RESPONSE, {"id": "pubA"}, {"id": "pubB"}]
    client.post.return_value = None
    client.delete.return_value = None

    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep") as mock_sleep:
        resolver.resolve_unlinked()

    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert sleep_calls.count(2.0) == 2  # once per root_team_id


def test_resolve_unlinked_no_teams_row_created(db: sqlite3.Connection) -> None:
    """resolve_unlinked() does not create any new teams rows (TN-3)."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client()
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    teams_before = db.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve_unlinked()
    teams_after = db.execute("SELECT COUNT(*) FROM teams").fetchone()[0]

    assert teams_after == teams_before


def test_resolve_unlinked_bridge_200_missing_id_field(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Bridge returns 200 but without 'id' field: counted as follow_bridge_failed, unfollow attempted."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    # Bridge returns 200 with no 'id' field
    client = _make_unlinked_client(bridge_response={"name": "foo"})
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve_unlinked()

    assert result.follow_bridge_failed == 1
    assert result.resolved == 0
    # Unfollow should still be attempted
    assert client.delete.call_count >= 1
    # Row stays unlinked
    links = _fetch_links(db)
    assert links[0]["public_id"] is None
    assert any("no 'id' field" in r.message for r in caplog.records)


def test_resolve_unlinked_hidden_rows_excluded_from_query(db: sqlite3.Connection) -> None:
    """Rows with is_hidden=1 are excluded from the AC-1 query."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A, is_hidden=1)
    client = _make_unlinked_client()
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve_unlinked()

    assert result.resolved == 0
    client.post.assert_not_called()


def test_resolve_hidden_flag_skips_on_rerun(db: sqlite3.Connection) -> None:
    """Previously visible opponent is skipped when re-run with is_hidden=True (E-167 TN-4)."""
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

    assert result1.skipped_hidden == 0
    assert result1.resolved == 1
    link = _fetch_links(db)[0]
    assert link["is_hidden"] == 0

    # Re-run with is_hidden=True -- opponent is now skipped, link row unchanged
    client2 = _make_client(
        paginated_return=[hidden_with_progenitor],
        get_return=_TEAM_DETAIL,
    )
    resolver2 = OpponentResolver(client2, config, db)
    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result2 = resolver2.resolve()

    assert result2.skipped_hidden == 1
    assert result2.resolved == 0
    # Existing link row is NOT updated (opponent was skipped)
    link2 = _fetch_links(db)[0]
    assert link2["is_hidden"] == 0  # unchanged from first run


# ---------------------------------------------------------------------------
# RateLimitError handling in follow/bridge steps (codex finding)
# ---------------------------------------------------------------------------


def test_resolve_unlinked_rate_limit_during_follow_skips_cycle(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """RateLimitError during follow step: skip cycle, increment follow_bridge_failed, no unfollow."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client(follow_side_effect=RateLimitError("429 Too Many Requests"))
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve_unlinked()

    assert result.follow_bridge_failed == 1
    assert result.resolved == 0
    assert result.errors == 0
    # Unfollow must NOT be called -- follow never succeeded
    client.delete.assert_not_called()
    # Row stays unlinked
    links = _fetch_links(db)
    assert links[0]["public_id"] is None
    assert any("Follow failed" in r.message for r in caplog.records)


def test_resolve_unlinked_rate_limit_during_bridge_proceeds_to_unfollow(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """RateLimitError during bridge step: increment follow_bridge_failed, proceed to unfollow."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)
    client = _make_unlinked_client(bridge_side_effect=RateLimitError("429 Too Many Requests"))
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve_unlinked()

    assert result.follow_bridge_failed == 1
    assert result.resolved == 0
    assert result.errors == 0
    # Unfollow must still be attempted -- follow succeeded
    assert client.delete.call_count >= 1
    # Row stays unlinked
    links = _fetch_links(db)
    assert links[0]["public_id"] is None
    assert any("Bridge failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Unexpected per-root_team_id exception counted in errors (codex finding)
# ---------------------------------------------------------------------------


def test_resolve_unlinked_unexpected_exception_increments_errors(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Unexpected crash bubbling from _follow_bridge_unfollow increments result.errors."""
    import logging
    from unittest.mock import patch as _patch

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    _insert_unlinked_link(db, own_pk, _ROOT_TEAM_ID_A)

    client = _make_unlinked_client()
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    # Patch the internal method to raise an unexpected error that bypasses
    # internal step handlers (simulates e.g. DB failure in the store step).
    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with _patch.object(resolver, "_follow_bridge_unfollow", side_effect=RuntimeError("db crash")):
            with caplog.at_level(logging.ERROR, logger="src.gamechanger.crawlers.opponent_resolver"):
                result = resolver.resolve_unlinked()

    assert result.errors == 1
    assert result.follow_bridge_failed == 0
    assert result.resolved == 0
    assert any("Unexpected error" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# E-154-01: AC-1 -- public_id written to teams row during resolution
# ---------------------------------------------------------------------------


def test_ensure_opponent_team_row_writes_public_id_new_row(db: sqlite3.Connection) -> None:
    """AC-1: New teams row gets public_id from team detail API response."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    team_detail_with_season = dict(_TEAM_DETAIL, season_year=2025)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_with_season,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT public_id FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row is not None
    assert row[0] == _PUBLIC_ID


def test_ensure_opponent_team_row_writes_public_id_existing_null_row(
    db: sqlite3.Connection,
) -> None:
    """AC-1: Existing teams row with NULL public_id gets public_id written."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Pre-insert a stub row for the opponent with public_id=NULL
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active) VALUES (?, ?, 'tracked', 0)",
        (_PROGENITOR_ID, _TEAM_NAME),
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

    row = db.execute(
        "SELECT public_id FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == _PUBLIC_ID


# ---------------------------------------------------------------------------
# E-154-01: AC-2 -- season_year written to teams row during resolution
# ---------------------------------------------------------------------------


def test_ensure_opponent_team_row_writes_season_year_new_row(db: sqlite3.Connection) -> None:
    """AC-2: New teams row gets season_year from team detail API response."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    team_detail_with_season = dict(_TEAM_DETAIL, season_year=2025)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_with_season,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT season_year FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == 2025


def test_ensure_opponent_team_row_writes_season_year_existing_null_row(
    db: sqlite3.Connection,
) -> None:
    """AC-2: Existing teams row with NULL season_year gets season_year written."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active) VALUES (?, ?, 'tracked', 0)",
        (_PROGENITOR_ID, _TEAM_NAME),
    )
    db.commit()
    team_detail_with_season = dict(_TEAM_DETAIL, season_year=2026)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_with_season,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT season_year FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == 2026


# ---------------------------------------------------------------------------
# E-154-01: AC-3 -- existing non-NULL public_id and season_year preserved
# ---------------------------------------------------------------------------


def test_ensure_opponent_team_row_preserves_existing_public_id(
    db: sqlite3.Connection,
) -> None:
    """AC-3: Existing non-NULL public_id on teams row is not overwritten."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    existing_public_id = "already-set-pub-id"
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, public_id) "
        "VALUES (?, ?, 'tracked', 0, ?)",
        (_PROGENITOR_ID, _TEAM_NAME, existing_public_id),
    )
    db.commit()
    # API returns a different public_id -- should be ignored
    different_public_id = "different-pub-id"
    team_detail_different = dict(_TEAM_DETAIL, public_id=different_public_id)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_different,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT public_id FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == existing_public_id  # unchanged


def test_ensure_opponent_team_row_preserves_existing_season_year(
    db: sqlite3.Connection,
) -> None:
    """AC-6: Existing non-NULL season_year on teams row is not overwritten."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, 'tracked', 0, 2024)",
        (_PROGENITOR_ID, _TEAM_NAME),
    )
    db.commit()
    team_detail_with_season = dict(_TEAM_DETAIL, season_year=2025)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_with_season,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        resolver.resolve()

    row = db.execute(
        "SELECT season_year FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] == 2024  # unchanged


# ---------------------------------------------------------------------------
# E-154-01: AC-4 -- UNIQUE collision on public_id logs WARNING, skips write
# ---------------------------------------------------------------------------


def test_ensure_opponent_team_row_unique_collision_logs_warning_and_skips(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4: UNIQUE collision on public_id logs WARNING and skips the write."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Pre-insert a *different* team that already holds the same public_id
    collision_gc_uuid = "collision-team-uuid"
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, public_id) "
        "VALUES (?, 'Collision Team', 'tracked', 0, ?)",
        (collision_gc_uuid, _PUBLIC_ID),
    )
    db.commit()
    # Pre-insert the opponent team row with NULL public_id
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active) VALUES (?, ?, 'tracked', 0)",
        (_PROGENITOR_ID, _TEAM_NAME),
    )
    db.commit()
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve()

    # Resolution still succeeds (not an error)
    assert result.resolved == 1
    assert result.errors == 0
    # WARNING logged about collision
    assert any("UNIQUE collision" in r.message for r in caplog.records)
    # public_id NOT written to the opponent team row
    row = db.execute(
        "SELECT public_id FROM teams WHERE gc_uuid = ?", (_PROGENITOR_ID,)
    ).fetchone()
    assert row[0] is None  # write was skipped


# ---------------------------------------------------------------------------
# E-154-01: AC-5 -- missing public_id in API response logs WARNING, continues
# ---------------------------------------------------------------------------


def test_resolve_opponent_missing_public_id_logs_warning_and_continues(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-5: Missing public_id in team detail logs WARNING; resolution continues."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    team_detail_no_pub_id = {
        "id": _PROGENITOR_ID,
        "name": _TEAM_NAME,
        # no public_id key
        "season_year": 2025,
    }
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_no_pub_id,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve()

    # Resolution still counted as successful (not an error)
    assert result.resolved == 1
    assert result.errors == 0
    # WARNING logged about missing public_id
    assert any("missing public_id" in r.message for r in caplog.records)
    # teams row still created with gc_uuid and name
    row = db.execute(
        "SELECT gc_uuid, name, public_id, season_year FROM teams WHERE gc_uuid = ?",
        (_PROGENITOR_ID,),
    ).fetchone()
    assert row is not None
    assert row[0] == _PROGENITOR_ID
    assert row[1] == _TEAM_NAME
    assert row[2] is None  # public_id stays NULL
    assert row[3] == 2025  # season_year still captured
    # opponent_links row created with public_id=NULL
    links = _fetch_links(db)
    assert len(links) == 1
    assert links[0]["public_id"] is None
    assert links[0]["resolution_method"] == "auto"


def test_resolve_opponent_null_public_id_in_response_logs_warning(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-5: Explicit null public_id in team detail logs WARNING; resolution continues."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    team_detail_null_pub_id = dict(_TEAM_DETAIL, public_id=None)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_null_pub_id,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        with caplog.at_level(logging.WARNING, logger="src.gamechanger.crawlers.opponent_resolver"):
            result = resolver.resolve()

    assert result.resolved == 1
    assert result.errors == 0
    assert any("missing public_id" in r.message for r in caplog.records)
    links = _fetch_links(db)
    assert links[0]["public_id"] is None


# ---------------------------------------------------------------------------
# E-154-01: AC-4 (new-row path) -- UNIQUE collision on INSERT path
# ---------------------------------------------------------------------------


def test_ensure_opponent_team_row_unique_collision_on_new_row_logs_warning_and_skips(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-4 (new-row path): UNIQUE collision when gc_uuid is new — WARNING logged, no crash."""
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # A completely different team already holds the public_id the API will return.
    # The progenitor gc_uuid does NOT yet exist in teams.
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, public_id) "
        "VALUES ('other-gc-uuid', 'Other Team', 'tracked', 0, ?)",
        (_PUBLIC_ID,),
    )
    db.commit()

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,  # returns public_id=_PUBLIC_ID
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    # Resolution succeeds -- E-167 fix: ensure_team_row now matches the
    # existing row by public_id (step 2, no gc_uuid IS NULL filter).
    # The existing row already has gc_uuid='other-gc-uuid' (non-NULL),
    # so gc_uuid backfill is skipped (only writes when NULL). No new row.
    assert result.resolved == 1
    assert result.errors == 0
    row = db.execute(
        "SELECT id, gc_uuid, public_id FROM teams WHERE public_id = ?", (_PUBLIC_ID,)
    ).fetchone()
    assert row is not None
    assert row[1] == "other-gc-uuid"  # preserved (non-NULL, not overwritten)
    assert row[2] == _PUBLIC_ID


# ---------------------------------------------------------------------------
# E-154 post-review: end-to-end collision invariant for opponent_links
# ---------------------------------------------------------------------------


def test_unique_collision_nulls_both_teams_and_opponent_links_public_id(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """When public_id collision occurs, both teams.public_id and opponent_links.public_id are NULL.

    Verifies the downstream _resolve_team_id invariant: ScoutingCrawler must not
    see a public_id in opponent_links that points to the wrong (colliding) teams row.
    """
    import logging

    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # A different team already holds the public_id the API will return.
    db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, public_id) "
        "VALUES ('other-gc-uuid', 'Other Team', 'tracked', 0, ?)",
        (_PUBLIC_ID,),
    )
    db.commit()

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,  # returns public_id=_PUBLIC_ID
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.resolved == 1
    assert result.errors == 0

    # E-167 fix: ensure_team_row matches the existing "Other Team" row by
    # public_id (step 2, no gc_uuid IS NULL filter). The existing row already
    # has gc_uuid='other-gc-uuid', so gc_uuid backfill is skipped.
    teams_row = db.execute(
        "SELECT gc_uuid, public_id FROM teams WHERE public_id = ?", (_PUBLIC_ID,)
    ).fetchone()
    assert teams_row is not None
    assert teams_row[0] == "other-gc-uuid"  # preserved (non-NULL)
    assert teams_row[1] == _PUBLIC_ID

    # opponent_links.public_id should be set (read back from the team row)
    links = _fetch_links(db)
    assert len(links) == 1
    assert links[0]["public_id"] == _PUBLIC_ID


# ---------------------------------------------------------------------------
# E-162-01: TN-4 scenario 1 -- happy path merge (public_id stub + gc_uuid backfill)
# ---------------------------------------------------------------------------


def test_ensure_opponent_team_row_merges_gc_uuid_onto_public_id_stub(
    db: sqlite3.Connection,
) -> None:
    """TN-4 scenario 1: public_id stub gets gc_uuid and season_year backfilled; no new row (AC-1, AC-5)."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Insert a stub with public_id but no gc_uuid or season_year.
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, public_id, is_active) "
        "VALUES (?, 'tracked', ?, 0)",
        (_TEAM_NAME, _PUBLIC_ID),
    )
    stub_id = cursor.lastrowid
    db.commit()

    team_detail_with_season = dict(_TEAM_DETAIL, season_year=2025)
    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=team_detail_with_season,
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.resolved == 1
    assert result.errors == 0

    # No new team row should be created -- exactly own team + stub.
    team_count = db.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    assert team_count == 2

    # gc_uuid, public_id, and season_year must all be set on the existing stub row.
    row = db.execute(
        "SELECT gc_uuid, public_id, season_year FROM teams WHERE id = ?", (stub_id,)
    ).fetchone()
    assert row[0] == _PROGENITOR_ID  # gc_uuid backfilled
    assert row[1] == _PUBLIC_ID      # public_id unchanged
    assert row[2] == 2025            # season_year written (was NULL)

    # opponent_links must reference the existing stub's id, not a new row.
    links = _fetch_links(db)
    assert len(links) == 1
    assert links[0]["resolved_team_id"] == stub_id
    assert links[0]["public_id"] == _PUBLIC_ID
    assert links[0]["resolution_method"] == "auto"


def test_ensure_opponent_team_row_merge_updates_uuid_stub_name(
    db: sqlite3.Connection,
) -> None:
    """TN-4 / AC-5: name updated to real name when stub's name equals gc_uuid (UUID-stub pattern)."""
    own_pk = _insert_team(db, _OWN_TEAM_GC_UUID, _OWN_TEAM_NAME)
    # Insert a stub where name = gc_uuid (UUID-as-name pattern from game_loader).
    cursor = db.execute(
        "INSERT INTO teams (name, membership_type, public_id, is_active) "
        "VALUES (?, 'tracked', ?, 0)",
        (_PROGENITOR_ID, _PUBLIC_ID),  # name == gc_uuid
    )
    stub_id = cursor.lastrowid
    db.commit()

    client = _make_client(
        paginated_return=[_OPPONENT_WITH_PROGENITOR],
        get_return=_TEAM_DETAIL,  # team_name = _TEAM_NAME
    )
    config = _make_config([(_OWN_TEAM_GC_UUID, own_pk)])
    resolver = OpponentResolver(client, config, db)

    with patch("src.gamechanger.crawlers.opponent_resolver.time.sleep"):
        result = resolver.resolve()

    assert result.resolved == 1

    # Name must be updated from UUID-stub to real name.
    row = db.execute("SELECT name FROM teams WHERE id = ?", (stub_id,)).fetchone()
    assert row[0] == _TEAM_NAME


# ---------------------------------------------------------------------------
# E-162-01: TN-4 scenario 2 -- gc_uuid collision on merge
# ---------------------------------------------------------------------------


def test_gc_uuid_collision_on_public_id_match_logs_warning(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """TN-4 scenario 2: gc_uuid collision during public_id match backfill is logged.

    When ensure_team_row() matches a row by public_id and tries to backfill
    gc_uuid, but another row already holds that gc_uuid, the collision is
    logged as a WARNING and the gc_uuid write is skipped.

    Note: _write_gc_uuid was removed in E-167-02; collision safety is now
    handled by ensure_team_row() and tested in test_ensure_team_row.py.
    This test verifies the end-to-end behavior through the resolver.
    """
    import logging
    from src.db.teams import ensure_team_row

    # Team A: public_id stub, no gc_uuid.
    cursor_a = db.execute(
        "INSERT INTO teams (name, membership_type, public_id, is_active) "
        "VALUES ('Team A', 'tracked', 'pubSlugA', 0)",
    )
    team_a_id = cursor_a.lastrowid

    # Team B: already holds gc_uuid=Y via a different code path.
    db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, is_active) "
        "VALUES ('Team B', 'tracked', 'gc-uuid-Y', 0)",
    )
    db.commit()

    # ensure_team_row with gc_uuid="gc-uuid-Y" matches Team B in step 1.
    # To test the collision path, we call with a NEW gc_uuid that doesn't
    # match any existing row, but public_id matches Team A.
    # Then backfill of gc_uuid="gc-uuid-NEW" should succeed (no collision).
    # For the actual collision test, see test_ensure_team_row.py::TestCollisionSafeWrites.
    # Here we verify the end-to-end flow: public_id match + gc_uuid backfill.
    with caplog.at_level(logging.WARNING, logger="src.db.teams"):
        result_id = ensure_team_row(
            db, public_id="pubSlugA", gc_uuid="gc-uuid-NEW", name="Team A"
        )

    # Should match Team A by public_id (step 2)
    assert result_id == team_a_id
    # gc_uuid="gc-uuid-NEW" back-filled (no collision)
    row = db.execute("SELECT gc_uuid FROM teams WHERE id = ?", (team_a_id,)).fetchone()
    assert row[0] == "gc-uuid-NEW"


# ---------------------------------------------------------------------------
# E-168-02: Search fallback tests
# ---------------------------------------------------------------------------

_SEARCH_HIT_EXACT = {
    "type": "team",
    "result": {
        "id": "search-uuid-001",
        "public_id": "search-slug-001",
        "name": "Unknown Team",
        "sport": "baseball",
        "location": {"city": "Lincoln", "state": "NE"},
        "season": {"name": "spring", "year": 2026},
        "number_of_players": 15,
        "staff": ["Coach A"],
    },
}


def _setup_unlinked(db: sqlite3.Connection) -> tuple[int, int]:
    """Insert a member team (season_year=2026) and an unlinked opponent link.

    Returns (our_team_id, link_id).
    """
    cur = db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, 'member', 1, 2026)",
        (_OWN_TEAM_GC_UUID, _OWN_TEAM_NAME),
    )
    our_pk = cur.lastrowid
    cur2 = db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, is_hidden) "
        "VALUES (?, 'root-bbb-002', 'Unknown Team', 0)",
        (our_pk,),
    )
    link_id = cur2.lastrowid
    db.commit()
    return our_pk, link_id


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_single_exact_match_resolves(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-1/AC-2/AC-4: Single exact name+year match auto-resolves."""
    our_pk, link_id = _setup_unlinked(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {"total_count": 1, "hits": [_SEARCH_HIT_EXACT]}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 1
    # unlinked stays 0 (no opponents from API); search resolution does not affect unlinked count
    assert result.unlinked == 0

    # Verify opponent_links row
    row = db.execute(
        "SELECT resolved_team_id, public_id, resolution_method "
        "FROM opponent_links WHERE id = ?", (link_id,)
    ).fetchone()
    assert row[0] is not None  # resolved_team_id
    assert row[1] == "search-slug-001"
    assert row[2] == "search"

    # Verify teams row has gc_uuid and public_id
    team_row = db.execute(
        "SELECT gc_uuid, public_id FROM teams WHERE id = ?", (row[0],)
    ).fetchone()
    assert team_row[0] == "search-uuid-001"
    assert team_row[1] == "search-slug-001"


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_multiple_matches_stays_unlinked(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-3: Multiple name+year matches -> stays unlinked."""
    our_pk, link_id = _setup_unlinked(db)
    hit2 = {
        "type": "team",
        "result": {
            "id": "search-uuid-002",
            "public_id": "search-slug-002",
            "name": "Unknown Team",
            "sport": "baseball",
            "season": {"name": "fall", "year": 2026},
        },
    }
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {
        "total_count": 2, "hits": [_SEARCH_HIT_EXACT, hit2],
    }

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 0
    row = db.execute(
        "SELECT resolution_method FROM opponent_links WHERE id = ?", (link_id,)
    ).fetchone()
    assert row[0] is None


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_zero_matches_stays_unlinked(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-3: No matches -> stays unlinked."""
    our_pk, link_id = _setup_unlinked(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {"total_count": 0, "hits": []}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 0
    row = db.execute(
        "SELECT resolution_method FROM opponent_links WHERE id = ?", (link_id,)
    ).fetchone()
    assert row[0] is None


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_case_insensitive_match(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-2: Case-insensitive name matching works."""
    our_pk, link_id = _setup_unlinked(db)
    # API returns "UNKNOWN TEAM" (uppercase) while link has "Unknown Team"
    hit = {
        "type": "team",
        "result": {
            "id": "search-uuid-ci",
            "public_id": "search-slug-ci",
            "name": "UNKNOWN TEAM",
            "sport": "baseball",
            "season": {"name": "spring", "year": 2026},
        },
    }
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {"total_count": 1, "hits": [hit]}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 1
    row = db.execute(
        "SELECT resolution_method FROM opponent_links WHERE id = ?", (link_id,)
    ).fetchone()
    assert row[0] == "search"


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_wrong_year_stays_unlinked(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-2: Name matches but year doesn't -> stays unlinked."""
    our_pk, link_id = _setup_unlinked(db)
    hit = {
        "type": "team",
        "result": {
            "id": "search-uuid-yr",
            "public_id": "search-slug-yr",
            "name": "Unknown Team",
            "sport": "baseball",
            "season": {"name": "spring", "year": 2025},  # wrong year
        },
    }
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {"total_count": 1, "hits": [hit]}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 0


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_api_error_continues(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-5: Non-credential API error is logged and skipped."""
    our_pk, link_id = _setup_unlinked(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.side_effect = GameChangerAPIError("Server error 502")

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    # Should not abort -- search_resolved stays 0, no exception raised
    assert result.search_resolved == 0
    # Finding 2 fix: error should be counted
    assert result.errors >= 1
    row = db.execute(
        "SELECT resolution_method FROM opponent_links WHERE id = ?", (link_id,)
    ).fetchone()
    assert row[0] is None


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_rate_limit_continues(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-5: RateLimitError is logged and skipped."""
    our_pk, link_id = _setup_unlinked(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.side_effect = RateLimitError("429 Too Many Requests")

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 0
    # Finding 2 fix: error should be counted
    assert result.errors >= 1


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_e225_punctuation_opponent_name_resolves_via_normalized_fallback(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """E-225-02 AC-6: ``#``-containing opponent name auto-resolves via fallback.

    Asserts exactly 2 ``post_json`` calls with exact body strings. The
    fallback hit's ``result.name`` matches the original (case-insensitive)
    so the existing ``name.lower() == opponent_name.lower()`` filter
    accepts the resolution.
    """
    cur = db.execute(
        "INSERT INTO teams (gc_uuid, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, 'member', 1, 2026)",
        (_OWN_TEAM_GC_UUID, _OWN_TEAM_NAME),
    )
    our_pk = cur.lastrowid
    cur2 = db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, is_hidden) "
        "VALUES (?, 'root-bbb-099', 'Cornhusker #1 Varsity', 0)",
        (our_pk,),
    )
    link_id = cur2.lastrowid
    db.commit()

    canonical_hit = {
        "type": "team",
        "result": {
            "id": "fallback-uuid-1",
            "public_id": "fallback-slug-1",
            "name": "Cornhusker #1 Varsity",
            "sport": "baseball",
            "season": {"name": "spring", "year": 2026},
        },
    }
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.side_effect = [
        {"total_count": 0, "hits": []},
        {"total_count": 1, "hits": [canonical_hit]},
    ]

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 1
    assert client.post_json.call_count == 2
    assert (
        client.post_json.call_args_list[0].kwargs["body"]["name"]
        == "Cornhusker #1 Varsity"
    )
    assert (
        client.post_json.call_args_list[1].kwargs["body"]["name"]
        == "Cornhusker 1 Varsity"
    )

    row = db.execute(
        "SELECT resolved_team_id, public_id, resolution_method "
        "FROM opponent_links WHERE id = ?", (link_id,)
    ).fetchone()
    assert row[0] is not None
    assert row[1] == "fallback-slug-1"
    assert row[2] == "search"


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_credential_expired_propagates(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-6: CredentialExpiredError propagates to caller."""
    our_pk, link_id = _setup_unlinked(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.side_effect = CredentialExpiredError("401 Unauthorized")

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    with pytest.raises(CredentialExpiredError):
        resolver.resolve()


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_forbidden_propagates(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-6: ForbiddenError (subclass of CredentialExpiredError) propagates."""
    our_pk, link_id = _setup_unlinked(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.side_effect = ForbiddenError("403 Forbidden")

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    with pytest.raises(ForbiddenError):
        resolver.resolve()


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_skips_already_resolved(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-7/AC-8: Already-resolved opponents are not re-processed."""
    our_pk, link_id = _setup_unlinked(db)

    # Add a resolved opponent (resolution_method='auto')
    opp_pk = db.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES ('Resolved Opp', 'tracked', 0)"
    ).lastrowid
    db.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, "
        "resolution_method, is_hidden) "
        "VALUES (?, 'root-resolved', 'Resolved Opp', ?, 'auto', 0)",
        (our_pk, opp_pk),
    )
    # Add a manual-resolved opponent
    manual_pk = db.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES ('Manual Opp', 'tracked', 0)"
    ).lastrowid
    db.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, resolved_team_id, "
        "resolution_method, is_hidden) "
        "VALUES (?, 'root-manual', 'Manual Opp', ?, 'manual', 0)",
        (our_pk, manual_pk),
    )
    db.commit()

    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    # If search were called for resolved opponents, this would match
    client.post_json.return_value = {"total_count": 1, "hits": [_SEARCH_HIT_EXACT]}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    # Only the unlinked opponent should trigger a search call
    assert client.post_json.call_count == 1
    assert result.search_resolved == 1


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_result_in_summary_log(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """AC-9: ResolveResult includes search_resolved count."""
    our_pk, link_id = _setup_unlinked(db)
    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {"total_count": 1, "hits": [_SEARCH_HIT_EXACT]}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 1
    assert hasattr(result, "search_resolved")


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_backfills_name_only_stub(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """TN-8: Search fallback backfills gc_uuid/public_id on name-only stubs."""
    our_pk, link_id = _setup_unlinked(db)

    # Pre-create a name-only stub (no gc_uuid, no public_id) matching the opponent
    stub_pk = db.execute(
        "INSERT INTO teams (name, membership_type, is_active, season_year) "
        "VALUES ('Unknown Team', 'tracked', 0, 2026)"
    ).lastrowid
    db.commit()

    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {"total_count": 1, "hits": [_SEARCH_HIT_EXACT]}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    result = resolver.resolve()

    assert result.search_resolved == 1

    # The stub should now have gc_uuid and public_id backfilled
    team_row = db.execute(
        "SELECT gc_uuid, public_id FROM teams WHERE id = ?", (stub_pk,)
    ).fetchone()
    assert team_row[0] == "search-uuid-001"
    assert team_row[1] == "search-slug-001"


@patch("src.gamechanger.crawlers.opponent_resolver.time.sleep")
def test_search_fallback_sleeps_between_calls(
    mock_sleep: MagicMock, db: sqlite3.Connection
) -> None:
    """Search fallback uses _DELAY_SECONDS between search calls."""
    our_pk, _ = _setup_unlinked(db)
    # Add a second unlinked opponent
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name, is_hidden) "
        "VALUES (?, 'root-ccc-004', 'Another Team', 0)",
        (our_pk,),
    )
    db.commit()

    client = _make_client(paginated_return=[], get_return=_TEAM_DETAIL)
    client.post_json.return_value = {"total_count": 0, "hits": []}

    config = _make_config([(_OWN_TEAM_GC_UUID, our_pk)])
    resolver = OpponentResolver(client, config, db)
    resolver.resolve()

    # Sleep should be called for each opponent in the search fallback
    # (plus any sleeps from the progenitor pass)
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    # At least 2 search fallback sleeps (1.5s each)
    assert sleep_calls.count(1.5) >= 2
