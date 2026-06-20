"""Authenticated opponents-registry crawler + own-team resolver (E-240).

Two pieces, both new (the E-239 removal deleted the prior opponent-discovery
machinery, so neither survived):

1. :func:`fetch_opponents` -- crawls a team's opponents registry via the
   authenticated, PAGINATED ``GET /teams/{gc_uuid}/opponents`` endpoint and
   returns per-opponent :class:`OpponentRecord` records keyed by
   ``root_team_id``. The registry is the ONLY live source of
   ``progenitor_team_id`` (``pregame_data`` lacks it and ``opponent_links`` has
   no column for it), which E-240-04's resolution ladder reads for rung (a).

2. :func:`resolve_own_team_gc_uuid` -- the own-team ``public_id -> gc_uuid``
   resolver (the prerequisite to calling both authenticated list-crawlers). It
   composes the EXISTING :func:`resolve_team` (public profile fetch, yields the
   real ``name``) and :func:`search_teams_by_name` (the canonical
   ``POST /search`` helper), then filters the hits by ``public_id`` to read the
   matching hit's ``id`` (the ``gc_uuid``). It passes a REAL ``name`` to search,
   never a URL slug (a slug returns 0 hits).

This crawler is a thin fetch+parse+paginate seam: outcome classification, the
registry join, and orchestration live in E-240-04 / E-240-07.

Usage::

    from src.gamechanger.client import GameChangerClient
    from src.gamechanger.crawlers.opponents import (
        fetch_opponents,
        resolve_own_team_gc_uuid,
    )

    client = GameChangerClient()
    gc_uuid = resolve_own_team_gc_uuid(client, "dD9PtF0YbKad")
    registry = fetch_opponents(client, gc_uuid)
    for record in registry:
        if record.has_progenitor:
            print(record.name, record.progenitor_team_id)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from src.gamechanger.client import GameChangerClient
from src.gamechanger.exceptions import GameChangerAPIError, TeamNotFoundError
from src.gamechanger.search import search_teams_by_name
from src.gamechanger.team_resolver import resolve_team

logger = logging.getLogger(__name__)

# Accept version pin per epic Technical Notes TN-4. The opponents registry is
# paginated (page size ~50): a multi-season team REQUIRES pagination, so this
# crawler follows the x-next-page cursor via client.get_paginated() (AC-5).
OPPONENTS_ACCEPT = "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# POST /search pagination, mirroring the sibling own-team resolver
# (src/reports/generator.py::_resolve_gc_uuid): a common team name's exact
# public_id match can land on a later page, so page until a match or a partial
# page. Same page size (25) and cap (5 pages = 125 results) as the sibling.
_SEARCH_PAGE_SIZE = 25
_SEARCH_MAX_PAGES = 5
_NAME_PUNCTUATION_RE = re.compile(r"[^\w ]")

# Sentinel distinguishing "key absent" from "key present but null". The
# opponents endpoint OMITS progenitor_team_id on manual-entry opponents (it is
# not null), and rung (a)'s eligibility test is key-presence, not truthiness.
_MISSING = object()


@dataclass(frozen=True)
class OpponentRecord:
    """One opponent-registry record, keyed by ``root_team_id``.

    This is the PINNED handoff shape consumed by E-240-04 (resolution ladder,
    rung (a)). The eligibility test for rung (a) MUST be key-presence
    (:attr:`has_progenitor`), NOT a truthiness/null check -- the endpoint OMITS
    ``progenitor_team_id`` on manual-entry opponents.

    Attributes:
        root_team_id: Local registry key. Equals ``pregame_data.opponent_id``
            from the schedule. Use ONLY as the join key -- never as a
            ``gc_uuid``.
        name: Opponent display name.
        progenitor_team_id: The canonical GC team UUID when the key is PRESENT
            (search-linked opponent), else ``None`` (manual-entry opponent --
            key omitted, distinguished by :attr:`has_progenitor`).
        has_progenitor: ``True`` iff the ``progenitor_team_id`` KEY was present
            in the API record (the manual-vs-lookup entry-mode signal). Use this
            for rung (a) eligibility, NOT ``progenitor_team_id is not None``.
        owning_team_id: Always equals the path ``team_id``. Informational only.
        is_hidden: Whether the opponent is hidden in the GC UI (dupes/bad
            entries). The crawler returns these unfiltered -- callers may filter.
    """

    root_team_id: str | None
    name: str | None
    progenitor_team_id: str | None
    has_progenitor: bool
    owning_team_id: str | None
    is_hidden: bool


def _parse_opponent(record: dict[str, Any]) -> OpponentRecord:
    """Parse one opponents-registry array item into an :class:`OpponentRecord`.

    Distinguishes a PRESENT ``progenitor_team_id`` key from an absent one via
    :data:`_MISSING`, so :attr:`OpponentRecord.has_progenitor` reflects
    key-presence rather than truthiness.
    """
    progenitor_raw = record.get("progenitor_team_id", _MISSING)
    has_progenitor = progenitor_raw is not _MISSING
    # Narrow to ``str | None`` for the dataclass field: a present key carries a
    # string UUID (or, defensively, null); the sentinel and any non-str value
    # collapse to None. This explicit narrowing lets the type checker validate
    # the assignment without an ``arg-type`` suppression.
    progenitor: str | None = progenitor_raw if isinstance(progenitor_raw, str) else None

    return OpponentRecord(
        root_team_id=record.get("root_team_id"),
        name=record.get("name"),
        progenitor_team_id=progenitor,
        has_progenitor=has_progenitor,
        owning_team_id=record.get("owning_team_id"),
        is_hidden=bool(record.get("is_hidden")),
    )


def fetch_opponents(
    client: GameChangerClient, gc_uuid: str
) -> list[OpponentRecord]:
    """Fetch a team's complete opponents registry (paginated).

    Calls ``GET /teams/{gc_uuid}/opponents`` with the TN-4 version pin via
    :meth:`GameChangerClient.get_paginated`, which follows the ``x-next-page``
    cursor until exhausted -- so a multi-season team whose registry exceeds the
    ~50-record page size returns ALL records (AC-5). Each record is parsed into
    an :class:`OpponentRecord` keyed by ``root_team_id``, exposing
    ``progenitor_team_id`` when the key is present (key-absent is distinguished
    via :attr:`OpponentRecord.has_progenitor`).

    A 403 propagates as ``ForbiddenError`` (DISTINCT from a true
    ``CredentialExpiredError``) so the caller can distinguish a version-pin /
    legitimate-denial case from auth expiry (AC-6); this crawler does NOT catch
    or re-classify it.

    Args:
        client: Authenticated :class:`GameChangerClient` instance.
        gc_uuid: The team's GameChanger UUID (NOT a ``public_id`` slug and NOT
            an ``opponent_id``/``root_team_id``).

    Returns:
        List of :class:`OpponentRecord`, across all pages.

    Raises:
        ForbiddenError: On a 403 -- propagated unchanged (AC-6).
        CredentialExpiredError: On a 401 that survives a single token refresh.
        RateLimitError: On a 429.
        GameChangerAPIError: On 5xx after retries.
    """
    logger.debug("Fetching opponents registry for gc_uuid=%s", gc_uuid)
    raw = client.get_paginated(
        f"/teams/{gc_uuid}/opponents",
        accept=OPPONENTS_ACCEPT,
    )

    records: list[OpponentRecord] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        records.append(_parse_opponent(item))

    logger.info(
        "Opponents registry fetch complete for gc_uuid=%s: %d record(s)",
        gc_uuid,
        len(records),
    )
    return records


def resolve_own_team_gc_uuid(
    client: GameChangerClient, public_id: str
) -> str | None:
    """Resolve an own-team ``public_id`` slug to its ``gc_uuid``.

    The prerequisite to calling the authenticated list-crawlers. Composes two
    existing helpers (AC-8):

    1. :func:`resolve_team` -- ``GET /public/teams/{public_id}`` for the team's
       real ``name``. The slug is NOT a valid search query (slug -> 0 hits), so
       this step is mandatory to obtain a real name.
    2. :func:`search_teams_by_name` -- the canonical ``POST /search`` helper
       (handles the punctuation/Unicode quirks). The returned hits are filtered
       by exact ``public_id`` match; the matching hit's ``result.id`` is the
       ``gc_uuid``.

    Args:
        client: Authenticated :class:`GameChangerClient` instance.
        public_id: The own team's ``public_id`` slug (e.g. ``"dD9PtF0YbKad"``).

    Returns:
        The team's ``gc_uuid`` string, or ``None`` when the team profile cannot
        be fetched, the search returns no ``public_id`` match, or the matched
        hit carries a non-UUID ``id``.

    Raises:
        CredentialExpiredError: Propagated from ``search_teams_by_name`` on an
            auth failure (not caught here).
    """
    try:
        profile = resolve_team(public_id)
    except (TeamNotFoundError, GameChangerAPIError):
        logger.warning(
            "Own-team resolver: could not fetch public profile for "
            "public_id=%s; cannot resolve gc_uuid",
            public_id,
        )
        return None

    name = profile.name
    logger.debug(
        "Own-team resolver: public_id=%s -> name=%r; searching for gc_uuid",
        public_id,
        name,
    )

    # Page through POST /search (the exact public_id match can land on a later
    # page for a common team name), mirroring the sibling resolver in
    # generator.py::_resolve_gc_uuid: return on a match, short-circuit on a
    # partial page (< page size = no more results), and stop after a page-0
    # empty for a punctuation-"dirty" name (the search helper already exhausted
    # its raw + normalized attempts, so further pages just repeat them).
    name_is_dirty = bool(_NAME_PUNCTUATION_RE.search(name))
    for page in range(_SEARCH_MAX_PAGES):
        hits = search_teams_by_name(client, name, start_at_page=page)
        for hit in hits:
            result = hit.get("result") if isinstance(hit, dict) else None
            if not isinstance(result, dict):
                continue
            if result.get("public_id") != public_id:
                continue
            gc_uuid = result.get("id")
            if isinstance(gc_uuid, str) and _UUID_RE.match(gc_uuid):
                logger.debug(
                    "Own-team resolver: public_id=%s -> gc_uuid=%s (page %d)",
                    public_id,
                    gc_uuid,
                    page,
                )
                return gc_uuid
            logger.warning(
                "Own-team resolver: public_id=%s matched a hit but its id %r "
                "is not a valid UUID",
                public_id,
                gc_uuid,
            )
            return None

        if page == 0 and not hits and name_is_dirty:
            break
        if len(hits) < _SEARCH_PAGE_SIZE:
            break

    logger.warning(
        "Own-team resolver: no search hit matched public_id=%s (name=%r)",
        public_id,
        name,
    )
    return None
