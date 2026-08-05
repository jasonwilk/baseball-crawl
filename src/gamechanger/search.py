"""Shared helper for POST /search calls with punctuation-normalization fallback.

GameChanger's POST /search backend returns zero hits for team names containing
certain punctuation characters (confirmed: ``/``, straight apostrophe ``'``
U+0027, ``%``, ``#``), plus a Unicode trap where indexed canonical names use
a curly apostrophe (U+2019) and queries with a straight apostrophe fail to
match. This module exposes :func:`search_teams_by_name`, which transparently
retries a zero-hit query with a normalized name when the input contains any
non-word non-space character.

The fallback is a lossy recovery, not a round-trippable transformation: the
normalized name maps multiple distinct inputs to the same query string.

It also exposes :func:`resolve_gc_uuid_by_public_id`, the shared
``public_id``-match pagination loop used by both the report generator and the
own-team opponent resolver (see those callers for the per-match validation
policy each layers on top of this loop).

Finally it exposes :func:`is_team_hit`, the entity-class predicate. ``POST
/search`` returns a HETEROGENEOUS result set -- teams and organizations -- and
an organization carries a ``public_id`` just as a team does, so filtering hits
on ``public_id`` alone can select one. Consumers that need a team MUST apply
the predicate per hit; it is deliberately not applied inside
:func:`search_teams_by_name`, whose raw ``hits`` length is the pagination
signal.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import Any

from src.gamechanger.client import GameChangerClient

logger = logging.getLogger(__name__)

_SEARCH_CONTENT_TYPE = "application/vnd.gc.com.post_search+json; version=0.0.0"

_NON_WORD_NON_SPACE = re.compile(r"[^\w ]+", flags=re.UNICODE)
_WHITESPACE_RUN = re.compile(r"\s+")

# Pagination bounds for the public_id-match resolution loop. A common team
# name's exact public_id match can land on a later page; 5 pages * 25 hits =
# 125 candidates. Owned here as the single source after E-247-03 collapsed the
# per-caller copies in generator.py and opponents.py.
_SEARCH_PAGE_SIZE = 25
_SEARCH_MAX_PAGES = 5

# Detection of a punctuation-"dirty" name: a page-0 empty result for such a
# name means search_teams_by_name already exhausted its raw + normalized
# attempts, so paginating further would just repeat the same lookups.
_NAME_PUNCTUATION_RE = re.compile(r"[^\w ]")

# Envelope entity class marking a search hit as a team. GC's search index is
# heterogeneous: organizations are 15.5% of all hits and 19.5% of baseball hits
# (n=599 measured 2026-08-04), and they carry a public_id exactly as teams do.
_HIT_TYPE_TEAM = "team"


def is_team_hit(hit: Any) -> bool:
    """Return True when a ``POST /search`` hit is a TEAM, not an organization.

    Reads the hit's **envelope** ``type``, which is ``"team"`` or
    ``"organization"``.

    ⚠ Read the ENVELOPE, never ``result.type``. ``result.type`` is the
    ORGANIZATION SUBTYPE (``travel`` / ``tournament`` / ``league``) and is
    ABSENT on teams, so a ``result.type == "team"`` test matches nothing and
    inverts this check -- it would reject every real team.

    Why the check belongs at resolution time rather than downstream: a
    wrong-class id often does NOT fail fast. The team RESOURCE does refuse --
    ``GET /teams/{org_id}`` 404s (58/58 measured) -- but SUB-RESOURCES under
    the same prefix do not validate entity class:
    ``GET /teams/{org_id}/opponents`` serves a registry byte-identical to the
    organization path (2/2). So an organization id can travel a long way
    returning populated, plausible data, and when something finally does
    refuse it, it reads as dead data rather than as a class error. The
    envelope ``type`` is the one cheap discriminator, and it is already
    present in a response we have.

    Fail-closed: an absent or unrecognized ``type`` is NOT a team.
    """
    return isinstance(hit, dict) and hit.get("type") == _HIT_TYPE_TEAM


def _normalize_team_name(name: str) -> str:
    spaced = _NON_WORD_NON_SPACE.sub(" ", name)
    collapsed = _WHITESPACE_RUN.sub(" ", spaced)
    return collapsed.strip()


def search_teams_by_name(
    client: GameChangerClient,
    team_name: str,
    *,
    start_at_page: int = 0,
) -> list[dict[str, Any]]:
    """Return the ``hits`` list from POST /search for a team name query.

    If the first attempt with the raw name returns zero hits AND the name
    contains at least one ``[^\\w ]`` character (i.e., any character that is
    neither a Unicode word character nor a literal space), retries once with
    the name normalized: ``[^\\w ]+`` replaced by a single space, runs of
    whitespace collapsed to one space, leading and trailing whitespace
    stripped.

    The same ``start_at_page`` value is threaded to both the first attempt and
    the fallback attempt; the fallback never silently resets to page 0.

    Args:
        client: Authenticated :class:`GameChangerClient` instance.
        team_name: Raw team name to search for.
        start_at_page: 0-indexed page offset passed to GC's ``start_at_page``
            query param (default ``0``).

    Returns:
        The ``hits`` list from whichever attempt produced results, or an empty
        list when both attempts return zero hits or when the name is
        gate-clean and the first attempt is empty.

    Raises:
        CredentialExpiredError: Propagated unchanged from ``client.post_json``;
            this helper does not catch, log, or swallow auth errors.
    """
    result = client.post_json(
        "/search",
        body={"name": team_name},
        params={"start_at_page": start_at_page, "search_source": "search"},
        content_type=_SEARCH_CONTENT_TYPE,
    )
    hits = result.get("hits", []) if isinstance(result, dict) else []

    if hits or not _NON_WORD_NON_SPACE.search(team_name):
        return hits

    normalized = _normalize_team_name(team_name)
    logger.debug(
        "POST /search empty for %r; retrying with normalized name %r",
        team_name,
        normalized,
    )

    fallback_result = client.post_json(
        "/search",
        body={"name": normalized},
        params={"start_at_page": start_at_page, "search_source": "search"},
        content_type=_SEARCH_CONTENT_TYPE,
    )
    return (
        fallback_result.get("hits", [])
        if isinstance(fallback_result, dict)
        else []
    )


def resolve_gc_uuid_by_public_id(
    client: GameChangerClient,
    name: str,
    public_id: str,
) -> Iterator[tuple[int, Any]]:
    """Page through search hits, yielding each candidate ``gc_uuid`` for an
    exact ``public_id`` match.

    This is the shared resolution loop. For each page (up to
    ``_SEARCH_MAX_PAGES``), it routes the query through
    :func:`search_teams_by_name` (so the punctuation/Unicode-apostrophe quirk
    handling stays centralized here, NOT inlined), filters the hits for an
    exact ``result.public_id == public_id`` match **that is also a team hit**
    (:func:`is_team_hit`), and yields the matching hit's ``result.id`` paired
    with the page index it was found on.

    The two filters are ordered ``public_id`` first, entity class second, and
    a non-team match is SKIPPED rather than refused -- see the inline comment
    at the check. Filtering is done here, per hit, and deliberately NOT inside
    :func:`search_teams_by_name`: that function's ``hits`` length is read below
    as the has-more-pages signal, so filtering at the source would make a full
    page of 25 look partial and strand a team whose match sits on a later page.

    Yielding lazily (a generator) lets each caller layer its own per-match
    policy and stop early:

    * the report generator returns the first *truthy* id (no UUID
      re-validation) and keeps paging past a falsy id;
    * the own-team opponent resolver validates the *first* match's id with
      :func:`~src.gamechanger.url_parser.is_gc_uuid` and returns ``None`` on a
      match-but-invalid id (it never consumes a second match).

    The page-level short-circuits are preserved exactly: a page-0 empty result
    for a punctuation-"dirty" ``name`` stops paging, and any partial page
    (fewer than ``_SEARCH_PAGE_SIZE`` hits) means there are no further pages.

    Args:
        client: Authenticated :class:`GameChangerClient` instance.
        name: The team's real name to search for (NOT the slug).
        public_id: The exact ``public_id`` slug to match.

    Yields:
        ``(page, candidate_id)`` tuples, where ``candidate_id`` is the matched
        hit's ``result.id`` (which may be ``None`` or a non-UUID string -- the
        caller applies its own validation).

    Raises:
        CredentialExpiredError: Propagated unchanged from
            ``search_teams_by_name``; this loop does not catch it.
    """
    name_is_dirty = bool(_NAME_PUNCTUATION_RE.search(name))
    for page in range(_SEARCH_MAX_PAGES):
        hits = search_teams_by_name(client, name, start_at_page=page)
        for hit in hits:
            result = hit.get("result") if isinstance(hit, dict) else None
            if not isinstance(result, dict):
                continue
            if result.get("public_id") != public_id:
                continue
            # Entity class is checked AFTER public_id, deliberately. The ~1-in-6
            # background organization noise already fails the public_id test and
            # skips silently, so only an organization carrying the EXACT sought
            # public_id reaches here -- rare, and worth a WARNING, because it
            # means the slug we were handed names an organization whose id is
            # not a team id. Skip it and keep paging: an organization sharing a
            # public_id with the sought team is no reason to abandon the search.
            if not is_team_hit(hit):
                logger.warning(
                    "POST /search hit matched public_id=%s but its envelope "
                    "type is %r, not %r; skipping (an organization id is not a "
                    "team id) and continuing to page.",
                    public_id,
                    hit.get("type") if isinstance(hit, dict) else None,
                    _HIT_TYPE_TEAM,
                )
                continue
            yield page, result.get("id")

        # Page-0 empty for a dirty name: the search helper already exhausted
        # its raw + normalized attempts, so further pages just repeat them.
        if page == 0 and not hits and name_is_dirty:
            break
        # Partial page means no more results.
        if len(hits) < _SEARCH_PAGE_SIZE:
            break
