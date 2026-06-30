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
    exact ``result.public_id == public_id`` match, and yields the matching
    hit's ``result.id`` paired with the page index it was found on.

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
            yield page, result.get("id")

        # Page-0 empty for a dirty name: the search helper already exhausted
        # its raw + normalized attempts, so further pages just repeat them.
        if page == 0 and not hits and name_is_dirty:
            break
        # Partial page means no more results.
        if len(hits) < _SEARCH_PAGE_SIZE:
            break
