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
  REAL name (never a slug). Two filters run before the count: organization hits
  are dropped (search returns BOTH entity classes), then hits whose
  ``result.season.year`` does not equal the MEMBER team's ``teams.season_year``
  are dropped. Auto-resolves ONLY on an unambiguous single surviving TEAM match;
  method ``search``. A zero-hit is ambiguous -> falls to rung (d), not a hard
  failure. See :func:`_resolve_via_search` for what each filter costs -- both
  narrow AND widen the accept surface, and the result is terminal TO THIS
  LADDER. The season filter is FAIL-CLOSED: an absent or non-integer hit year
  drops the hit, and a member team with NULL ``season_year`` auto-accepts
  nothing at this rung. A ``search`` row is the ONE method an operator can
  override via ``bb report map-opponent`` (2026-08-05); the ladder itself still
  never re-attempts it.
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

⚠ Do NOT confuse this gate with ``bb report map-opponent``'s eligibility
predicate. They are different questions over the same column and they diverged
deliberately on 2026-08-05: this gate is about what the LADDER re-attempts
(nothing with a method -- unchanged), while map-opponent is about what an
OPERATOR may correct (a pending row, plus a ``search`` row). Widening THIS gate
to match would re-attempt every resolution every run; widening map-opponent's
to ``IS NOT NULL`` would resurrect a ``no_presence`` row. Neither predicate is
the other's copy -- do not "align" them.

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

from src.gamechanger.search import is_team_hit, search_teams_by_name

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

# ⚠ ADDING A NEW AUTOMATIC METHOD? One thing outside this file keys on this set:
# `_MAPPABLE_ROW_PREDICATE` in ``src/cli/report.py`` decides which methods
# ``bb report map-opponent`` may OVERRIDE, and it currently names METHOD_SEARCH
# alone. A new auto-accept method is NOT overridable until you add it there.
# Both sides of that, because only one of them is obvious: the drift fails
# CLOSED (the operator gets "No mappable opponent" and has to fix the DB by
# hand) rather than open, which is why this is a pointer and not a shared
# frozenset -- a set of one, plus the dynamic IN-clause it would require, buys
# machinery against a hypothetical second member. But fail-closed is not
# harmless: it strands a wrong auto-resolve with no CLI recovery, which is the
# exact gap `.project/specs/2026-08-05-rung-c-search-resolve-recoverable.md`
# closed. If a second automatic method lands, hoist the policy here instead of
# widening the literal there.

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


def _hit_season_year(hit: dict) -> int | None:
    """Return a search hit's ``result.season.year`` as an int, or None.

    ⚠ On ``POST /search`` ``season`` is an OBJECT ``{name, year}``
    (``docs/api/endpoints/post-search.md``). That is NOT the public team
    profile's shape, where ``season`` is a bare string and ``year`` is a flat
    sibling integer -- do NOT carry a parser between the two.
    ``.claude/rules/testing.md`` records ``team_season.season.year`` as a
    FABRICATED path that a mirrored mock will happily validate.

    Returns None (which the caller treats as "drop the hit") for every shape
    that is not an honest integer year: no ``result``, no ``season`` object, an
    absent year, or a non-integer one. ``bool`` is excluded explicitly because
    it is an ``int`` subclass in Python and ``True == 1`` would otherwise
    compare as a year.
    """
    result = hit.get("result")
    if not isinstance(result, dict):
        return None
    season = result.get("season")
    if not isinstance(season, dict):
        return None
    year = season.get("year")
    if isinstance(year, bool) or not isinstance(year, int):
        return None
    return year


def _resolve_via_search(
    client: GameChangerClient,
    opponent_name: str,
    member_season_year: int | None,
) -> str | None:
    """Resolve a public_id via POST /search on an UNAMBIGUOUS single TEAM match.

    Routes through :func:`search_teams_by_name` (never ``client.post_json``).
    TWO filters run before the count: organization hits are DROPPED first
    (:func:`is_team_hit`), then hits whose ``result.season.year`` does not equal
    ``member_season_year`` are dropped (:func:`_hit_season_year`). The
    ``result.public_id`` is returned ONLY when exactly one hit survives BOTH.
    Zero survivors (ambiguous: punctuation quirk, genuinely unindexed, an
    all-organization result set, or an all-wrong-season one) or 2+ survivors
    (ambiguous) return ``None`` so the caller falls to rung (d) -- NEVER a hard
    failure.

    ⚠ **State both sides: EACH filter both NARROWS and WIDENS the auto-accept
    surface.** The bar's PREDICATE is unchanged ("exactly one"), but its
    POPULATION is not. Dropping organizations means one team beside N
    organizations now auto-resolves where the raw count previously sent it to
    the operator queue. The season filter behaves the same way: two team hits of
    which only ONE carries the member's year now auto-accept on that one. Both
    also narrow -- a single hit that fails a filter is refused where it once
    resolved. Neither is a no-op in either direction, and this is STICKY *to
    this ladder*: :func:`resolve_opponent` treats any ``opponent_links`` row
    with a non-NULL ``resolution_method`` as terminal, so a wrong auto-resolve
    is **never re-attempted automatically**.

    **The season filter is FAIL-CLOSED, on ``year`` ALONE** (operator ruling,
    2026-08-08). A team from one YEAR must never auto-match a team from another
    year; cross-season *within* one year (spring 2026 vs summer 2026) is
    legitimate and must still auto-accept, which is why ``season.name`` is
    **never** compared. A hit with no usable year is dropped rather than waved
    through, and a ``member_season_year`` of ``None`` (the member team's
    ``teams.season_year`` is NULL) refuses EVERY auto-accept at this rung --
    logged at WARNING, because that silently disables rung (c) for that team.

    Criterion 1, the name match, remains REJECTED (not merely unimplemented):
    canonical names diverge in word order and punctuation from the free-text
    schedule name we search with, so an exact match would reject correct hits.

    ⚠ **What DID change (2026-08-05), because the sentence above used to say
    "and never re-surfaces to the operator" and that is no longer true:** a
    ``search`` row is now CORRECTABLE ON DEMAND via ``bb report map-opponent``,
    which accepts ``resolution_method = 'search'`` alongside a pending row (see
    ``src/cli/report.py::_apply_opponent_mapping``). That is an operator-driven
    repair, NOT a re-attempt: nothing here re-runs, and the operator must
    notice the wrong mapping first -- the ``--dry-run`` RESOLVED line prints the
    method to make that possible. The stickiness that matters therefore stands:
    an unnoticed wrong auto-resolve still feeds reports indefinitely. The season
    filter narrows how OFTEN that happens; it does not make it recoverable.

    Args:
        client: Authenticated :class:`GameChangerClient`.
        opponent_name: The REAL opponent name to query (never a slug).
        member_season_year: The member team's ``teams.season_year``, or ``None``
            when the row carries no year. REQUIRED (never defaulted): this is
            EVIDENCE, and per ``.claude/rules/python-style.md`` an evidence
            parameter with a default silently disables the guard it feeds.
    """
    hits = search_teams_by_name(client, opponent_name)
    # Drop organizations, THEN count. Search is heterogeneous and an
    # organization carries a public_id, so the uniqueness bar below cannot tell
    # the classes apart on its own -- it fires exactly when a name matches one
    # thing, which is precisely when an organization name matches uniquely
    # (measured: 2 of 15 organization names returned a single hit; both were
    # the organization). The bar's PREDICATE is unchanged and still
    # load-bearing -- it is what prevents a multi-hit wrong-team auto-resolve.
    # Its POPULATION is not: see the docstring's "widens the auto-accept
    # surface" note before assuming this filter is safety-neutral. It is not.
    #
    # Why drop-then-count rather than refusing whenever an organization
    # appears: an organization hit is usually a NAME COLLISION, not the
    # umbrella of the team beside it -- only 4 of 70 co-occurring organization
    # hits had a same-page team in their member list. Refusing would punt the
    # Showdown/League-shaped queries (43 organizations, ~0 of them umbrellas)
    # to the operator queue for nothing. ⚠ 4-of-70 is a LOWER bound on umbrella
    # relationships, not a rate: the test only sees membership when the member
    # team happens to rank on the same 25-hit page. It refutes "an organization
    # hit is that team's umbrella"; it does NOT license the reverse claim that
    # a given organization is unrelated to a given team. Both readings favor
    # dropping. Resolving THROUGH the organization was considered and declined:
    # that is a new ladder rung, not an entity-class filter, and 4-of-70 says
    # it would fire almost never. An all-organization result set filters to
    # zero teams and falls to rung (d), exactly as a zero-hit does.
    team_hits = [hit for hit in hits if is_team_hit(hit)]
    if hits and not team_hits:
        # Newly reachable state, and the one worth hearing about: search
        # returned results but NONE were teams. WARNING rather than DEBUG
        # because this is also how a class-wide failure would present -- if the
        # envelope type were renamed, or a third entity class appeared, the
        # fail-closed predicate would drop EVERY hit and route EVERY opponent
        # to the operator queue. At DEBUG that is indistinguishable from the
        # ordinary "GameChanger has not indexed this team" case.
        logger.warning(
            "Rung (c): all %d search hit(s) for %r are non-team (organizations "
            "or an unrecognized entity class) -- no team to resolve, falling "
            "through to the operator queue",
            len(hits),
            opponent_name,
        )
        return None
    # Season-year filter, AFTER the organization drop and BEFORE the uniqueness
    # bar. The ordering is load-bearing for the log lines: running this first
    # would make the "all hits are non-team" WARNING above unreachable, and that
    # warning is how a class-wide entity-type failure would announce itself.
    #
    # FAIL-CLOSED on a NULL member year. Refusing every auto-accept is the
    # ruled behavior (2026-08-08), not a degradation: matching a hit against a
    # year we do not have would be the very cross-year auto-match this filter
    # exists to prevent. WARNING rather than DEBUG because it silently disables
    # a whole rung for this team -- morning-run fills the own-team year on
    # ensure_team_row precisely so this stays rare, and a fired warning means
    # that fill did not happen.
    if member_season_year is None:
        # Worded so it claims only what is true. An unindexed opponent (the
        # MODAL case) reaches here with zero hits, and saying "refused an
        # auto-accept" there would assert a refusal that never happened --
        # the state is "rung (c) cannot run", not "rung (c) said no".
        logger.warning(
            "Rung (c): member team has no stored season_year, so rung (c) is "
            "disabled for it (fail-closed) -- %r goes to the operator queue "
            "without a season comparison being possible",
            opponent_name,
        )
        return None
    season_hits = [
        hit for hit in team_hits if _hit_season_year(hit) == member_season_year
    ]
    # Compare on `year` ALONE, never `season.name`: cross-season within one year
    # (spring 2026 vs summer 2026) is a legitimate auto-match, and only the YEAR
    # boundary is the one a team must never cross (ruled 2026-08-08).
    if team_hits and not season_hits:
        # The season-filter analogue of the "all hits are non-team" WARNING
        # above, and it earns the same level for the same reason: this is how a
        # CLASS-WIDE failure would present. A stale or wrong teams.season_year
        # silently drops EVERY hit for EVERY opponent and routes the whole team
        # to the operator queue -- at DEBUG that is indistinguishable from
        # ordinary "GameChanger has not indexed this team" noise, which is
        # precisely the confusion that would let a dead rung run unnoticed for
        # a season.
        #
        # ⚠ There are TWO class-wide failures here, not one, and the message
        # must not name only the likelier. `_hit_season_year` fails closed to
        # None for a missing/renamed `season` key or a non-int year, which is
        # indistinguishable from a real mismatch at the comparison. If GC ever
        # changes that shape, every hit drops -- and blaming the operator's own
        # DB row would send them to the one place the fault is NOT. Counting
        # the unparseable ones separately is what keeps the diagnosis honest.
        unparseable = sum(1 for hit in team_hits if _hit_season_year(hit) is None)
        if unparseable == len(team_hits):
            logger.warning(
                "Rung (c): all %d team hit(s) for %r carry NO usable "
                "result.season.year -- dropped fail-closed. This is an API "
                "SHAPE problem, not a year mismatch: suspect a renamed or "
                "dropped `season` key upstream, NOT the member team's "
                "season_year (%d)",
                len(team_hits),
                opponent_name,
                member_season_year,
            )
        else:
            logger.warning(
                "Rung (c): all %d team hit(s) for %r were dropped on season "
                "year (member season_year=%d; %d had a different year, %d had "
                "no usable year) -- nothing to resolve, falling through to the "
                "operator queue. If this repeats across opponents, suspect the "
                "member team's stored season_year",
                len(team_hits),
                opponent_name,
                member_season_year,
                len(team_hits) - unparseable,
                unparseable,
            )
    elif len(season_hits) != len(team_hits):
        logger.debug(
            "Rung (c): %d team hit(s) for %r, %d dropped on season year "
            "(member season_year=%d)",
            len(team_hits),
            opponent_name,
            len(team_hits) - len(season_hits),
            member_season_year,
        )
    if len(season_hits) != 1:
        logger.debug(
            "Rung (c): %d search hit(s) for %r, %d team hit(s) after dropping "
            "%d non-team hit(s), %d after the season-year filter -- ambiguous, "
            "falling through",
            len(hits),
            opponent_name,
            len(team_hits),
            len(hits) - len(team_hits),
            len(season_hits),
        )
        return None

    result = season_hits[0].get("result")
    if not isinstance(result, dict):
        return None
    public_id = result.get("public_id")
    if isinstance(public_id, str) and public_id:
        return public_id
    return None


# ---------------------------------------------------------------------------
# The ladder
# ---------------------------------------------------------------------------


def _read_member_season_year(
    conn: sqlite3.Connection, our_team_id: int
) -> int | None:
    """Return the member team's ``teams.season_year``, or None when unusable.

    The ladder reads this ITSELF rather than taking it as a threaded parameter
    (ruled 2026-08-08). ``.claude/rules/python-style.md`` requires EVIDENCE
    parameters to be REQUIRED precisely because an omitted one silently
    disables a guard; a value the function reads for itself cannot be omitted
    at all, so no future caller can forget it and no public signature changes.

    A missing row, a NULL year, or a non-integer stored value all return None,
    which rung (c) treats as "refuse every auto-accept" -- fail-closed.
    """
    row = conn.execute(
        "SELECT season_year FROM teams WHERE id = ?", (our_team_id,)
    ).fetchone()
    if row is None:
        return None
    season_year = row[0]
    if isinstance(season_year, bool) or not isinstance(season_year, int):
        return None
    return season_year


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
            slot (the local half of the per-pairing key). ALSO the source of
            the ``season_year`` rung (c) filters search hits against -- a row
            with a NULL year disables that rung's auto-accept entirely.
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

    # --- Rung (c): POST /search by name (unambiguous single TEAM match whose
    # season year equals the member team's) ---------------------------------
    if opponent_name:
        # Read the member year HERE, not at function entry: rungs (a) and (b)
        # resolve without it, and this keeps the query off their path.
        public_id = _resolve_via_search(
            client, opponent_name, _read_member_season_year(conn, our_team_id)
        )
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
