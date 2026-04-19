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
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.gamechanger.client import GameChangerClient

logger = logging.getLogger(__name__)

_SEARCH_CONTENT_TYPE = "application/vnd.gc.com.post_search+json; version=0.0.0"

_NON_WORD_NON_SPACE = re.compile(r"[^\w ]+", flags=re.UNICODE)
_WHITESPACE_RUN = re.compile(r"\s+")


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
