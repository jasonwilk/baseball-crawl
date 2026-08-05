# synthetic-test-data
"""Tests for src.gamechanger.opponent_ladder.

Covers each rung of the resolution ladder (TN-3), the key-absent eligibility
test, the opponent_id namespace guard, the registry-absent fall-through, the
placeholder classification + escaped-event-name fall-through, the
unambiguous-single-match vs. multiple/zero-hit search behavior, the persisted
opponent_links states (resolved-positive + rung-(d) pending; NEVER no_presence),
and the terminality gate keyed on resolution_method IS NOT NULL (incl. the
no_presence resurrection-bug regression).

No real HTTP -- the GameChangerClient is a MagicMock (the established pattern for
higher-level GameChanger helpers). The DB is the real production schema via
conftest.load_real_schema, so opponent_links / teams FK behavior is exercised
for real.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.gamechanger.crawlers.opponents import OpponentRecord
from src.gamechanger.exceptions import (
    CredentialExpiredError,
    ForbiddenError,
)
from src.gamechanger.opponent_ladder import (
    METHOD_PROGENITOR,
    METHOD_SEARCH,
    TEAM_DETAIL_ACCEPT,
    LadderResult,
    ResolutionOutcome,
    is_placeholder,
    resolve_opponent,
)
from tests.conftest import load_real_schema

_OUR_TEAM_ID = 1
_ROOT = "root-aaaa-0000"
_PROGENITOR = "prog-bbbb-1111"
_PUBLIC_ID = "dD9PtF0YbKad"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory DB with the production schema + a seeded own-team row."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, 'LSB JV', 'member')",
        (_OUR_TEAM_ID,),
    )
    conn.commit()
    return conn


def _linked_record(
    *, root_team_id: str = _ROOT, progenitor_team_id: str = _PROGENITOR
) -> OpponentRecord:
    return OpponentRecord(
        root_team_id=root_team_id,
        name="Linked Opp",
        progenitor_team_id=progenitor_team_id,
        has_progenitor=True,
        owning_team_id="owning-x",
        is_hidden=False,
    )


def _manual_record(*, root_team_id: str = _ROOT) -> OpponentRecord:
    return OpponentRecord(
        root_team_id=root_team_id,
        name="Manual Opp",
        progenitor_team_id=None,
        has_progenitor=False,
        owning_team_id="owning-x",
        is_hidden=False,
    )


def _search_hit(public_id: str, team_id: str = "11111111") -> dict[str, Any]:
    """A TEAM search hit. The envelope ``type`` is required -- rung (c) drops
    non-team hits before counting, and teams OMIT ``result.type`` entirely."""
    return {
        "type": "team",
        "result": {
            "name": "Found Team",
            "public_id": public_id,
            "id": team_id,
            "number_of_players": 14,
            "staff": ["Coach One"],
        },
    }


def _org_hit(public_id: str, org_id: str = "99999999") -> dict[str, Any]:
    """An ORGANIZATION search hit, mirroring the real shape: envelope
    ``type: "organization"``, a ``result.type`` SUBTYPE, and no
    ``number_of_players``/``staff`` keys (omitted, not null)."""
    return {
        "type": "organization",
        "result": {
            "name": "Found Team",
            "public_id": public_id,
            "id": org_id,
            "type": "travel",
        },
    }


def _link_row(db: sqlite3.Connection, root_team_id: str = _ROOT) -> sqlite3.Row:
    db.row_factory = sqlite3.Row
    row = db.execute(
        "SELECT * FROM opponent_links WHERE our_team_id = ? AND root_team_id = ?",
        (_OUR_TEAM_ID, root_team_id),
    ).fetchone()
    return row


# ---------------------------------------------------------------------------
# is_placeholder unit coverage (rung b pattern)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "TBD",
        "TBA",
        "Winner of Game 3",
        "Loser Bracket",
        "Seed 4",
        "Game 7",
        "Pool A",
        "Bracket Play",
        "Papio Tournament",
        "Cornhusker Invitational",
        "Summer Classic",
        "Prep Showcase",
    ],
)
def test_is_placeholder_matches_pattern(name: str) -> None:
    assert is_placeholder(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "Bellevue West",
        "Millard South Patriots",
        "Slumpbuster",  # escapes the pattern by design
        "Prep Baseball KC Challenge",  # 'Challenge' not in the set -> escapes
        "Gretna East",
        None,
        "",
    ],
)
def test_is_placeholder_rejects_real_and_escaped_names(name: str | None) -> None:
    assert is_placeholder(name) is False


# ---------------------------------------------------------------------------
# AC-1 / AC-2: rung (a) -- key-present progenitor reverse bridge
# ---------------------------------------------------------------------------


def test_rung_a_resolves_via_progenitor_with_correct_pin(
    db: sqlite3.Connection,
) -> None:
    client = MagicMock()
    client.get.return_value = {"public_id": _PUBLIC_ID, "name": "Resolved"}

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Linked Opp",
        registry=[_linked_record()],
    )

    assert result == LadderResult(
        outcome=ResolutionOutcome.RESOLVED,
        public_id=_PUBLIC_ID,
        method=METHOD_PROGENITOR,
        from_cache=False,
    )
    # AC-2: GET /teams/{progenitor_team_id} with the team+json 0.10.0 pin.
    client.get.assert_called_once()
    call = client.get.call_args
    assert call.args[0] == f"/teams/{_PROGENITOR}"
    assert call.kwargs["accept"] == TEAM_DETAIL_ACCEPT
    assert TEAM_DETAIL_ACCEPT == "application/vnd.gc.com.team+json; version=0.10.0"

    # AC-6: resolved-positive opponent_links row.
    row = _link_row(db)
    assert row["public_id"] == _PUBLIC_ID
    assert row["resolution_method"] == METHOD_PROGENITOR
    assert row["resolved_at"] is not None


def test_rung_a_eligibility_is_key_present_not_truthiness(
    db: sqlite3.Connection,
) -> None:
    """A registry record with has_progenitor False (key absent) skips rung (a).

    Even though such a record exists for this root_team_id, the ladder must NOT
    attempt the progenitor bridge -- it falls through to search/operator.
    """
    client = MagicMock()
    client.get.return_value = {"public_id": "should-not-be-used"}
    # Manual record: key absent. Name is a real (non-placeholder) name so it
    # falls to rung (c); search returns zero hits -> rung (d).
    client_search = [{"hits": []}]
    client.post_json.side_effect = client_search

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Manual Opp",
        registry=[_manual_record()],
    )

    # Rung (a) must NOT have called GET /teams/{...}.
    client.get.assert_not_called()
    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE


def test_rung_a_present_but_null_progenitor_falls_through(
    db: sqlite3.Connection,
) -> None:
    """has_progenitor True but progenitor_team_id None must not call the bridge."""
    record = OpponentRecord(
        root_team_id=_ROOT,
        name="Null Prog",
        progenitor_team_id=None,
        has_progenitor=True,  # key present, value null
        owning_team_id="owning-x",
        is_hidden=False,
    )
    client = MagicMock()
    client.post_json.side_effect = [{"hits": []}]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Null Prog",
        registry=[record],
    )

    client.get.assert_not_called()
    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE


# ---------------------------------------------------------------------------
# AC-3: opponent_id namespace guard + registry-absent fall-through
# ---------------------------------------------------------------------------


def test_opponent_id_never_passed_to_get_teams(db: sqlite3.Connection) -> None:
    """The opponent_id (root_team_id namespace) is NEVER a GET /teams/{id} arg.

    Rung (a) only ever calls GET /teams/{progenitor_team_id}; the opponent_id
    must not appear as a /teams/ path. Here the registry maps the opponent_id to
    a DIFFERENT progenitor, and we assert GET was called with the progenitor,
    never the opponent_id.
    """
    client = MagicMock()
    client.get.return_value = {"public_id": _PUBLIC_ID}

    resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Linked Opp",
        registry=[_linked_record()],
    )

    for call in client.get.call_args_list:
        assert call.args[0] != f"/teams/{_ROOT}"
        assert _ROOT not in call.args[0]
    assert client.get.call_args.args[0] == f"/teams/{_PROGENITOR}"


def test_registry_absent_falls_through_to_search(db: sqlite3.Connection) -> None:
    """opponent_id wholly absent from the registry -> no rung (a), fall through."""
    client = MagicMock()
    client.post_json.side_effect = [{"hits": [_search_hit(_PUBLIC_ID)]}]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Some Real Team",
        registry=[],  # empty registry
    )

    client.get.assert_not_called()  # rung (a) skipped
    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.method == METHOD_SEARCH
    assert result.public_id == _PUBLIC_ID


# ---------------------------------------------------------------------------
# AC-4: rung (b) placeholder -> deferred, NO opponent_links row
# ---------------------------------------------------------------------------


def test_placeholder_defers_and_persists_no_row(db: sqlite3.Connection) -> None:
    client = MagicMock()

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Winner of Game 5",
        registry=[_manual_record()],  # no progenitor, so rung (a) skips
    )

    assert result.outcome is ResolutionOutcome.DEFERRED_PLACEHOLDER
    assert result.public_id is None
    # No opponent_links row persisted (AC-4).
    assert _link_row(db) is None
    # No network call made for a placeholder.
    client.get.assert_not_called()
    client.post_json.assert_not_called()


def test_escaped_event_name_falls_through_not_chased(
    db: sqlite3.Connection,
) -> None:
    """An event name that ESCAPES the pattern is NOT deferred -- it reaches d."""
    client = MagicMock()
    client.post_json.side_effect = [{"hits": []}]  # zero hits -> rung (d)

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Slumpbuster",  # escapes the placeholder pattern
        registry=[_manual_record()],
    )

    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
    # A pending row WAS persisted (it fell through to rung d, not deferred).
    assert _link_row(db) is not None


# ---------------------------------------------------------------------------
# AC-5: rung (c) search -- single match vs. multiple/zero
# ---------------------------------------------------------------------------


def test_search_single_match_resolves(db: sqlite3.Connection) -> None:
    client = MagicMock()
    client.post_json.side_effect = [{"hits": [_search_hit(_PUBLIC_ID)]}]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Real Team Name",
        registry=[_manual_record()],
    )

    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.method == METHOD_SEARCH
    assert result.public_id == _PUBLIC_ID
    row = _link_row(db)
    assert row["public_id"] == _PUBLIC_ID
    assert row["resolution_method"] == METHOD_SEARCH


def test_search_multiple_matches_falls_to_operator_queue(
    db: sqlite3.Connection,
) -> None:
    client = MagicMock()
    client.post_json.side_effect = [
        {"hits": [_search_hit("slug-a", "id-a"), _search_hit("slug-b", "id-b")]}
    ]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Ambiguous Team",
        registry=[_manual_record()],
    )

    # 2+ hits is ambiguous -> rung (d), NOT a wrong-team auto-ingest.
    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
    row = _link_row(db)
    assert row["public_id"] is None
    assert row["resolution_method"] is None


def test_search_single_organization_hit_does_not_resolve(
    db: sqlite3.Connection,
) -> None:
    """Rung (c) must NOT return an organization's public_id.

    This is the case the uniqueness bar cannot catch: it fires exactly when a
    name matches ONE thing, which is when an organization name matches
    uniquely (measured: 2 of 15 organization names returned a single hit, both
    the organization). Organizations carry a public_id, so the pre-filter
    result would otherwise look like a clean single match.
    """
    client = MagicMock()
    client.post_json.side_effect = [{"hits": [_org_hit(_PUBLIC_ID)]}]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Some Showdown",
        registry=[_manual_record()],
    )

    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
    assert result.public_id is None
    row = _link_row(db)
    assert row["public_id"] is None
    assert row["resolution_method"] is None


def test_search_organization_beside_one_team_resolves_the_team(
    db: sqlite3.Connection,
) -> None:
    """Drop organizations, THEN count -- not refuse-whenever-an-org-appears.

    An organization hit is usually a NAME COLLISION rather than the umbrella of
    the team beside it, so refusing here would punt a resolvable team to the
    operator queue for nothing.
    """
    client = MagicMock()
    client.post_json.side_effect = [
        {"hits": [_org_hit("org-slug"), _search_hit(_PUBLIC_ID)]}
    ]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Real Team Name",
        registry=[_manual_record()],
    )

    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.method == METHOD_SEARCH
    assert result.public_id == _PUBLIC_ID


def test_search_two_teams_plus_organization_is_still_ambiguous(
    db: sqlite3.Connection,
) -> None:
    """The team-side uniqueness bar is UNCHANGED.

    Dropping the organization must not turn an ambiguous multi-team result
    into an auto-resolve -- no new wrong-team mode is introduced.
    """
    client = MagicMock()
    client.post_json.side_effect = [
        {
            "hits": [
                _org_hit("org-slug"),
                _search_hit("slug-a", "id-a"),
                _search_hit("slug-b", "id-b"),
            ]
        }
    ]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Ambiguous Team",
        registry=[_manual_record()],
    )

    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
    row = _link_row(db)
    assert row["public_id"] is None


def test_search_all_organization_hits_falls_through_like_zero_hits(
    db: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An all-organization result set filters to zero teams -> rung (d).

    Also pins the WARNING. This state is newly reachable, and it is how a
    class-wide failure would present (a renamed envelope type, or a third
    entity class, would drop EVERY hit). At DEBUG that is indistinguishable
    from "GameChanger has not indexed this team", so the level is deliberate --
    do not downgrade it.
    """
    client = MagicMock()
    client.post_json.side_effect = [
        {"hits": [_org_hit("org-a", "id-a"), _org_hit("org-b", "id-b")]}
    ]

    with caplog.at_level("WARNING", logger="src.gamechanger.opponent_ladder"):
        result = resolve_opponent(
            conn=db,
            client=client,
            our_team_id=_OUR_TEAM_ID,
            opponent_id=_ROOT,
            opponent_name="League Showdown",
            registry=[_manual_record()],
        )

    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
    assert result.public_id is None
    warnings = [
        r.getMessage() for r in caplog.records if r.levelname == "WARNING"
    ]
    assert any("are non-team" in m for m in warnings), warnings


def test_search_zero_hits_is_unresolved_mappable_not_no_presence(
    db: sqlite3.Connection,
) -> None:
    """A zero-hit search is AMBIGUOUS -> unresolved_mappable, NEVER no_gc_presence."""
    client = MagicMock()
    client.post_json.side_effect = [{"hits": []}]

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Unindexed HS Program",
        registry=[_manual_record()],
    )

    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
    row = _link_row(db)
    # The ladder NEVER writes the no_presence state.
    assert row["resolution_method"] is None
    assert row["resolution_method"] != "no_presence"


def test_search_routes_through_helper_with_real_name(
    db: sqlite3.Connection,
) -> None:
    """Rung (c) queries POST /search with the real NAME, never a slug.

    The search helper calls client.post_json with body={"name": <name>}; we
    assert the real opponent name (not the public_id slug) is the query.
    """
    client = MagicMock()
    client.post_json.side_effect = [{"hits": [_search_hit(_PUBLIC_ID)]}]

    resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Lincoln Northeast Rockets",
        registry=[_manual_record()],
    )

    client.post_json.assert_called_once()
    call = client.post_json.call_args
    assert call.args[0] == "/search"
    assert call.kwargs["body"] == {"name": "Lincoln Northeast Rockets"}
    assert call.kwargs["body"]["name"] != _PUBLIC_ID


# ---------------------------------------------------------------------------
# AC-6: rung (d) persists the pending not-resolved row
# ---------------------------------------------------------------------------


def test_rung_d_persists_pending_row(db: sqlite3.Connection) -> None:
    client = MagicMock()
    client.post_json.side_effect = [{"hits": []}]

    resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Pending Team",
        registry=[_manual_record()],
    )

    row = _link_row(db)
    assert row is not None
    assert row["our_team_id"] == _OUR_TEAM_ID
    assert row["root_team_id"] == _ROOT
    assert row["opponent_name"] == "Pending Team"
    assert row["public_id"] is None
    assert row["resolution_method"] is None
    assert row["resolved_at"] is None


# ---------------------------------------------------------------------------
# AC-7 / AC-8: terminality gate + state reads
# ---------------------------------------------------------------------------


def test_terminality_gate_reuses_cached_positive_without_reattempt(
    db: sqlite3.Connection,
) -> None:
    # Seed a resolved-positive row.
    db.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, public_id, "
        " resolution_method, resolved_at) "
        "VALUES (?, ?, 'Cached', ?, ?, datetime('now'))",
        (_OUR_TEAM_ID, _ROOT, _PUBLIC_ID, METHOD_PROGENITOR),
    )
    db.commit()
    client = MagicMock()

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Cached",
        registry=[_linked_record()],
    )

    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.public_id == _PUBLIC_ID
    assert result.method == METHOD_PROGENITOR
    assert result.from_cache is True
    # No network re-attempt.
    client.get.assert_not_called()
    client.post_json.assert_not_called()


def test_terminality_gate_still_short_circuits_a_search_row(
    db: sqlite3.Connection,
) -> None:
    """A `search` row stays TERMINAL to the ladder -- unchanged by the override.

    `bb report map-opponent` can now correct a wrong `search` resolution
    (`src/cli/report.py::_apply_opponent_mapping`), which makes it tempting to
    assume the ladder re-attempts one too. It does NOT, deliberately: the gate
    keys on `resolution_method IS NOT NULL` and was left alone, because widening
    it is what would resurrect a `no_presence` row (see the test below).
    Correction is operator-driven and on demand; it is not automatic.
    """
    db.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, public_id, "
        " resolution_method, resolved_at) "
        "VALUES (?, ?, 'Cached', ?, ?, datetime('now'))",
        (_OUR_TEAM_ID, _ROOT, _PUBLIC_ID, METHOD_SEARCH),
    )
    db.commit()
    client = MagicMock()

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Cached",
        registry=[_linked_record()],
    )

    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.public_id == _PUBLIC_ID
    assert result.method == METHOD_SEARCH
    assert result.from_cache is True
    # No re-search, no re-bridge.
    client.get.assert_not_called()
    client.post_json.assert_not_called()


def test_terminality_gate_no_presence_not_reattempted_resurrection_regression(
    db: sqlite3.Connection,
) -> None:
    """A no_presence row (public_id NULL, method set) must NOT be re-attempted.

    Regression for the resurrection bug: a public_id-based gate would re-queue
    this row every run because its public_id is NULL. The gate keys on
    resolution_method IS NOT NULL.
    """
    db.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, public_id, "
        " resolution_method, resolved_at) "
        "VALUES (?, ?, 'Gone Team', NULL, 'no_presence', datetime('now'))",
        (_OUR_TEAM_ID, _ROOT),
    )
    db.commit()
    client = MagicMock()

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Gone Team",
        registry=[_linked_record()],  # would resolve via (a) if re-attempted
    )

    # Not re-attempted: no GET, no search.
    client.get.assert_not_called()
    client.post_json.assert_not_called()
    assert result.from_cache is True
    # Surfaced as unresolved_mappable (E-240-07 maps the no_presence link state
    # to the no_gc_presence run outcome); the ladder itself never re-resolves it.
    assert result.outcome is ResolutionOutcome.UNRESOLVED_MAPPABLE
    assert result.method == "no_presence"


def test_pending_row_is_not_terminal_and_is_reattempted(
    db: sqlite3.Connection,
) -> None:
    """A pending row (method NULL) is NOT terminal -- the ladder re-attempts it."""
    # Seed a pending (not-resolved) row.
    db.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
        "VALUES (?, ?, 'Pending')",
        (_OUR_TEAM_ID, _ROOT),
    )
    db.commit()
    client = MagicMock()
    client.get.return_value = {"public_id": _PUBLIC_ID}

    result = resolve_opponent(
        conn=db,
        client=client,
        our_team_id=_OUR_TEAM_ID,
        opponent_id=_ROOT,
        opponent_name="Pending",
        registry=[_linked_record()],
    )

    # Re-attempted via rung (a): the pending row is upgraded to resolved.
    client.get.assert_called_once()
    assert result.outcome is ResolutionOutcome.RESOLVED
    assert result.from_cache is False
    row = _link_row(db)
    assert row["public_id"] == _PUBLIC_ID
    assert row["resolution_method"] == METHOD_PROGENITOR


# ---------------------------------------------------------------------------
# AC-9: 403 surfaced distinctly (not collapsed into auth-expiry)
# ---------------------------------------------------------------------------


def test_rung_a_forbidden_propagates_distinctly(db: sqlite3.Connection) -> None:
    client = MagicMock()
    client.get.side_effect = ForbiddenError("Access denied for /teams/x")

    with pytest.raises(ForbiddenError):
        resolve_opponent(
            conn=db,
            client=client,
            our_team_id=_OUR_TEAM_ID,
            opponent_id=_ROOT,
            opponent_name="Linked Opp",
            registry=[_linked_record()],
        )


def test_rung_a_credential_expired_propagates(db: sqlite3.Connection) -> None:
    client = MagicMock()
    client.get.side_effect = CredentialExpiredError("token expired")

    with pytest.raises(CredentialExpiredError):
        resolve_opponent(
            conn=db,
            client=client,
            our_team_id=_OUR_TEAM_ID,
            opponent_id=_ROOT,
            opponent_name="Linked Opp",
            registry=[_linked_record()],
        )


# ---------------------------------------------------------------------------
# Per-team-opponent pairing: same root, two teams -> two independent rows
# ---------------------------------------------------------------------------


def test_per_pairing_key_is_local_to_team(db: sqlite3.Connection) -> None:
    """The same opponent faced by two teams persists one row per team."""
    db.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (2, 'LSB Varsity', 'member')"
    )
    db.commit()
    client = MagicMock()
    client.get.return_value = {"public_id": _PUBLIC_ID}

    for team_id in (_OUR_TEAM_ID, 2):
        resolve_opponent(
            conn=db,
            client=client,
            our_team_id=team_id,
            opponent_id=_ROOT,
            opponent_name="Shared Opp",
            registry=[_linked_record()],
        )

    rows = db.execute(
        "SELECT our_team_id FROM opponent_links WHERE root_team_id = ? "
        "ORDER BY our_team_id",
        (_ROOT,),
    ).fetchall()
    assert [r[0] for r in rows] == [1, 2]
