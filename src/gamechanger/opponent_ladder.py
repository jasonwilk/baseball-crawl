"""Opponent resolution ladder for the morning-run scheduler (E-240-04).

Given an upcoming game's ``opponent_id`` + ``opponent_name`` (from E-240-01's
schedule crawler) and the team's opponents-registry records (from E-240-01's
opponents crawler), resolves the opponent to a GameChanger ``public_id`` via an
ordered ladder and persists the result in the revived ``opponent_links`` table
(migration 001, revived per E-240-03 / TN-6) so each opponent resolves ONCE per
team-opponent pairing.

The ladder (TN-3), in order:

* **Rung (a) -- registry progenitor reverse bridge.** Join ``opponent_id`` (the
  ``root_team_id`` namespace) to the registry records; if a matching record has
  the ``progenitor_team_id`` KEY PRESENT (key-absence test, NOT truthiness),
  call ``GET /teams/{progenitor_team_id}`` (NOT ``.../public-team-profile-id``)
  to read ``public_id``. Method ``progenitor``.
* **Rung (b) -- placeholder deferral.** Names matching the TN-3 placeholder
  pattern (``TBD|TBA|Winner|Loser|Seed|Game N|Pool|Bracket|Tournament|
  Invitational|Classic|Showcase``) are deferred; NO ``opponent_links`` row is
  persisted. Event/tournament names that ESCAPE the pattern are NOT chased --
  they fall through to rung (c)/(d) by design.
* **Rung (c) -- POST /search by name.** Routes through
  :func:`search_teams_by_name` (never ``client.post_json`` directly), querying a
  REAL name (never a slug). Auto-resolves ONLY on an unambiguous single match;
  method ``search``. A zero-hit is ambiguous -> falls to rung (d), not a hard
  failure.
* **Rung (d) -- operator queue.** Persists a not-resolved pending
  ``opponent_links`` row (``public_id`` NULL, ``resolution_method`` NULL) that
  ``bb report map-opponent`` (E-240-05) later UPDATEs. Outcome
  ``unresolved_mappable``.

The ladder NEVER produces ``no_gc_presence`` -- that is operator-declared only
via ``map-opponent --no-presence`` (C1).

Terminality gate (AC-7): before running the ladder, an existing
``opponent_links`` row whose ``resolution_method IS NOT NULL`` (covers BOTH
resolved-positive AND the operator-declared ``no_presence`` row) short-circuits
and is reused -- NEVER gated on ``public_id IS NOT NULL`` (a ``no_presence`` row
has ``public_id`` NULL, so a public_id gate would re-attempt it every run -- the
resurrection bug).

This module is a PURE resolution seam: it does not generate reports, write
``scheduled_report_runs`` rows, or surface operator alerts -- that is E-240-07.

The banned follow->bridge->unfollow path (`.claude/rules/gc-uuid-bridge.md`) is
NOT used anywhere here; rung (a) is the read-only reverse bridge only.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from src.gamechanger.search import search_teams_by_name

if TYPE_CHECKING:
    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.crawlers.opponents import OpponentRecord

logger = logging.getLogger(__name__)

# Reverse-bridge accept pin per TN-4. NOTE: this is ``team+json`` -- DISTINCT
# from ``/me/teams``' ``team:list+json``; a wrong pin yields a FALSE 403 that
# would wrongly mark an otherwise-resolvable opponent "no report possible".
TEAM_DETAIL_ACCEPT = "application/vnd.gc.com.team+json; version=0.10.0"

# Resolution methods written to opponent_links.resolution_method. The auto-ladder
# writes METHOD_PROGENITOR / METHOD_SEARCH; the operator (map-opponent, E-240-05)
# writes METHOD_OPERATOR or METHOD_NO_PRESENCE. METHOD_NO_PRESENCE is the
# load-bearing resurrection-bug discriminator -- it is coupled writer (map-opponent)
# to reader (the morning-run TN-11 vocabulary mapping), so it lives HERE as one
# shared constant rather than as bare literals on both sides.
METHOD_PROGENITOR = "progenitor"
METHOD_SEARCH = "search"
METHOD_OPERATOR = "operator"
METHOD_NO_PRESENCE = "no_presence"

# Placeholder name pattern (TN-3 rung b). Whole-word, case-insensitive. Event
# names that ESCAPE this set are NOT chased -- they fall through by design.
_PLACEHOLDER_PATTERN = re.compile(
    r"\b("
    r"TBD|TBA|Winner|Loser|Seed|Game\s+\d+|Pool|Bracket|"
    r"Tournament|Invitational|Classic|Showcase"
    r")\b",
    flags=re.IGNORECASE,
)


class ResolutionOutcome(str, Enum):
    """The per-opponent resolution result the ladder returns.

    E-240-07 maps these to the persisted ``scheduled_report_runs`` vocabulary
    per TN-11. The ladder NEVER returns ``no_gc_presence`` (operator-declared
    only; C1).
    """

    RESOLVED = "resolved"  # public_id found (rung a or c, or a cached positive)
    DEFERRED_PLACEHOLDER = "deferred_placeholder"  # rung b -- no row persisted
    UNRESOLVED_MAPPABLE = "unresolved_mappable"  # rung d -- pending row persisted


@dataclass(frozen=True)
class LadderResult:
    """Structured outcome of one opponent resolution.

    Attributes:
        outcome: The :class:`ResolutionOutcome`.
        public_id: The resolved opponent ``public_id`` (set only when
            ``outcome`` is ``RESOLVED``), else ``None``.
        method: The ``opponent_links.resolution_method`` recorded for a
            resolved-positive outcome (``"progenitor"`` / ``"search"`` /
            ``"operator"`` when reusing a cached operator mapping), else
            ``None``.
        from_cache: ``True`` when the result was reused from an existing
            terminal ``opponent_links`` row (AC-7), without re-attempting the
            network ladder.
    """

    outcome: ResolutionOutcome
    public_id: str | None = None
    method: str | None = None
    from_cache: bool = False


def is_placeholder(opponent_name: str | None) -> bool:
    """Return True when the name matches the TN-3 placeholder pattern (rung b)."""
    if not opponent_name:
        return False
    return _PLACEHOLDER_PATTERN.search(opponent_name) is not None


# ---------------------------------------------------------------------------
# opponent_links persistence (three states read from public_id + method only)
# ---------------------------------------------------------------------------


def _read_existing_link(
    conn: sqlite3.Connection, our_team_id: int, root_team_id: str
) -> sqlite3.Row | None:
    """Return the existing opponent_links row for this pairing, or None."""
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT public_id, resolution_method FROM opponent_links "
        "WHERE our_team_id = ? AND root_team_id = ?",
        (our_team_id, root_team_id),
    ).fetchone()


def _upsert_resolved_positive(
    conn: sqlite3.Connection,
    our_team_id: int,
    root_team_id: str,
    opponent_name: str,
    public_id: str,
    method: str,
) -> None:
    """Persist a resolved-positive opponent_links row (public_id + method set).

    Uses ``ON CONFLICT(our_team_id, root_team_id) DO UPDATE`` so a re-resolution
    overwrites the pending/old row. Sets ``resolved_at`` (TN-6 requires it on a
    positive resolution).
    """
    conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name, public_id, "
        " resolution_method, resolved_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(our_team_id, root_team_id) DO UPDATE SET "
        "opponent_name = excluded.opponent_name, "
        "public_id = excluded.public_id, "
        "resolution_method = excluded.resolution_method, "
        "resolved_at = excluded.resolved_at",
        (our_team_id, root_team_id, opponent_name, public_id, method),
    )
    conn.commit()


def _upsert_pending(
    conn: sqlite3.Connection,
    our_team_id: int,
    root_team_id: str,
    opponent_name: str,
) -> None:
    """Persist a not-resolved pending opponent_links row (rung d).

    ``public_id`` NULL and ``resolution_method`` NULL -- the pending row
    ``bb report map-opponent`` (E-240-05) later UPDATEs. Uses
    ``ON CONFLICT ... DO UPDATE`` but ONLY refreshes ``opponent_name`` -- it must
    NOT clobber a public_id/method already set on the row (the terminality gate
    means we only reach this path for a non-terminal row, but the UPSERT stays
    conservative regardless).
    """
    conn.execute(
        "INSERT INTO opponent_links "
        "(our_team_id, root_team_id, opponent_name) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(our_team_id, root_team_id) DO UPDATE SET "
        "opponent_name = excluded.opponent_name",
        (our_team_id, root_team_id, opponent_name),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Rung (a): registry progenitor reverse bridge
# ---------------------------------------------------------------------------


def _find_registry_record(
    registry: list[OpponentRecord], root_team_id: str
) -> OpponentRecord | None:
    """Find the registry record whose root_team_id matches the opponent_id."""
    for record in registry:
        if record.root_team_id == root_team_id:
            return record
    return None


def _resolve_via_progenitor(
    client: GameChangerClient, progenitor_team_id: str
) -> str | None:
    """Call GET /teams/{progenitor_team_id} and return its public_id, or None.

    Uses the TN-4 reverse-bridge pin (``team+json; version=0.10.0``). A 403 is
    NOT caught here -- it propagates as ``ForbiddenError`` (distinct from
    auth-expiry) so the caller can distinguish a version-pin / denial case from
    a true 401 (AC-9). Other unexpected shapes fall through to the next rung by
    returning ``None``.
    """
    data = client.get(
        f"/teams/{progenitor_team_id}",
        accept=TEAM_DETAIL_ACCEPT,
    )
    if isinstance(data, dict):
        public_id = data.get("public_id")
        if isinstance(public_id, str) and public_id:
            return public_id
    logger.warning(
        "Rung (a): GET /teams/%s returned no usable public_id; falling through",
        progenitor_team_id,
    )
    return None


# ---------------------------------------------------------------------------
# Rung (c): POST /search by name
# ---------------------------------------------------------------------------


def _resolve_via_search(
    client: GameChangerClient, opponent_name: str
) -> str | None:
    """Resolve a public_id via POST /search on an UNAMBIGUOUS single match.

    Routes through :func:`search_teams_by_name` (never ``client.post_json``).
    Returns the single hit's ``result.public_id`` ONLY when exactly one hit is
    returned; zero hits (ambiguous: punctuation quirk vs. genuinely unindexed)
    or 2+ hits (ambiguous) return ``None`` so the caller falls to rung (d) --
    NEVER a hard failure, and NEVER a wrong-team auto-ingest.
    """
    hits = search_teams_by_name(client, opponent_name)
    if len(hits) != 1:
        logger.debug(
            "Rung (c): %d search hit(s) for %r -- ambiguous, falling through",
            len(hits),
            opponent_name,
        )
        return None

    result = hits[0].get("result") if isinstance(hits[0], dict) else None
    if not isinstance(result, dict):
        return None
    public_id = result.get("public_id")
    if isinstance(public_id, str) and public_id:
        return public_id
    return None


# ---------------------------------------------------------------------------
# The ladder
# ---------------------------------------------------------------------------


def resolve_opponent(
    *,
    conn: sqlite3.Connection,
    client: GameChangerClient,
    our_team_id: int,
    opponent_id: str,
    opponent_name: str | None,
    registry: list[OpponentRecord],
) -> LadderResult:
    """Resolve an upcoming opponent to a ``public_id`` via the rung a-d ladder.

    Persists the result in ``opponent_links`` (resolved-positive or rung-(d)
    pending; NEVER ``no_presence``) keyed on ``(our_team_id, root_team_id)``,
    resolving once per team-opponent pairing.

    Args:
        conn: Open SQLite connection (the ``opponent_links`` store).
        client: Authenticated :class:`GameChangerClient`.
        our_team_id: ``teams.id`` of the LSB team whose schedule produced this
            slot (the local half of the per-pairing key).
        opponent_id: The upcoming game's ``pregame_data.opponent_id`` -- the
            ``root_team_id`` registry namespace. NEVER fed to
            ``GET /teams/{id}``.
        opponent_name: The opponent's free-text name (placeholder check +
            rung-(c) search query + the persisted pending row's
            ``opponent_name``).
        registry: The team's opponents-registry records from E-240-01.

    Returns:
        A :class:`LadderResult`.

    Raises:
        ForbiddenError: From rung (a)'s ``GET /teams/{progenitor_team_id}`` on a
            403 (version-pin / denial), propagated unchanged so the caller can
            distinguish it from a true 401 (AC-9).
        CredentialExpiredError: On a 401 that survives a refresh (rung a) or
            propagated from the search helper (rung c).
    """
    root_team_id = opponent_id

    # --- Terminality gate (AC-7): reuse a cached terminal mapping ------------
    existing = _read_existing_link(conn, our_team_id, root_team_id)
    if existing is not None and existing["resolution_method"] is not None:
        # resolution_method IS NOT NULL covers BOTH resolved-positive AND the
        # operator-declared no_presence row -- do NOT gate on public_id (the
        # no_presence resurrection bug).
        cached_public_id = existing["public_id"]
        method = existing["resolution_method"]
        if cached_public_id:
            logger.debug(
                "Terminality gate: reusing cached %s mapping for "
                "(team=%s, root=%s) -> %s",
                method,
                our_team_id,
                root_team_id,
                cached_public_id,
            )
            return LadderResult(
                outcome=ResolutionOutcome.RESOLVED,
                public_id=cached_public_id,
                method=method,
                from_cache=True,
            )
        # public_id NULL + method set == operator-declared no_presence. The
        # ladder never re-attempts it; it surfaces as unresolved-mappable to the
        # orchestration's vocabulary mapping (E-240-07 maps the no_presence
        # opponent_links state to the no_gc_presence run outcome). Do NOT
        # re-attempt resolution.
        logger.debug(
            "Terminality gate: (team=%s, root=%s) is operator-declared "
            "no_presence (method=%s); not re-attempting",
            our_team_id,
            root_team_id,
            method,
        )
        return LadderResult(
            outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE,
            public_id=None,
            method=method,
            from_cache=True,
        )

    # --- Rung (a): registry progenitor reverse bridge -----------------------
    record = _find_registry_record(registry, root_team_id)
    if record is not None and record.has_progenitor and record.progenitor_team_id:
        public_id = _resolve_via_progenitor(client, record.progenitor_team_id)
        if public_id:
            _upsert_resolved_positive(
                conn,
                our_team_id,
                root_team_id,
                opponent_name or "",
                public_id,
                METHOD_PROGENITOR,
            )
            logger.info(
                "Rung (a): resolved (team=%s, root=%s) -> public_id=%s "
                "via progenitor",
                our_team_id,
                root_team_id,
                public_id,
            )
            return LadderResult(
                outcome=ResolutionOutcome.RESOLVED,
                public_id=public_id,
                method=METHOD_PROGENITOR,
            )
    elif record is None:
        # Defensive fall-through: opponent_id wholly absent from the registry
        # (rare per the F4 probe). Do not over-invest -- fall to the next rung.
        logger.debug(
            "Rung (a): opponent_id=%s absent from registry; falling through",
            root_team_id,
        )

    # --- Rung (b): placeholder deferral (persist NO row) --------------------
    if is_placeholder(opponent_name):
        logger.debug(
            "Rung (b): %r is a placeholder; deferring (no opponent_links row)",
            opponent_name,
        )
        return LadderResult(outcome=ResolutionOutcome.DEFERRED_PLACEHOLDER)

    # --- Rung (c): POST /search by name (unambiguous single match only) -----
    if opponent_name:
        public_id = _resolve_via_search(client, opponent_name)
        if public_id:
            _upsert_resolved_positive(
                conn,
                our_team_id,
                root_team_id,
                opponent_name,
                public_id,
                METHOD_SEARCH,
            )
            logger.info(
                "Rung (c): resolved (team=%s, root=%s) -> public_id=%s "
                "via search",
                our_team_id,
                root_team_id,
                public_id,
            )
            return LadderResult(
                outcome=ResolutionOutcome.RESOLVED,
                public_id=public_id,
                method=METHOD_SEARCH,
            )

    # --- Rung (d): operator queue (persist not-resolved pending row) --------
    _upsert_pending(conn, our_team_id, root_team_id, opponent_name or "")
    logger.info(
        "Rung (d): (team=%s, root=%s, name=%r) unresolved-but-mappable; "
        "persisted pending opponent_links row",
        our_team_id,
        root_team_id,
        opponent_name,
    )
    return LadderResult(outcome=ResolutionOutcome.UNRESOLVED_MAPPABLE)
