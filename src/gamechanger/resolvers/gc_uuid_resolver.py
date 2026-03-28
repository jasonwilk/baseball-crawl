"""Opportunistic gc_uuid resolution cascade for tracked teams.

Discovers and stores gc_uuid values using cached data (member-team boxscores,
opponents.json) plus a search API fallback. The cascade stops at the first
successful tier. Tiers 1 and 2 make zero API calls.

Tier 1: Extract opponent UUID from member-team boxscore JSON files.
Tier 2: Match by name in cached opponents.json, use progenitor_team_id.
Tier 3: POST /search with classification-suffix-stripped name.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from src.gamechanger.exceptions import CredentialExpiredError

if TYPE_CHECKING:
    from src.gamechanger.client import GameChangerClient

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

_SEARCH_CONTENT_TYPE = "application/vnd.gc.com.post_search+json; version=0.0.0"

# Classification suffixes to strip iteratively (longest first to avoid partial).
_CLASSIFICATION_SUFFIXES = [
    "Reserve/Freshman",
    "Reserve",
    "Freshman",
    "Varsity",
    "JV",
]


def resolve_gc_uuid(
    team_id: int,
    public_id: str,
    team_name: str,
    season_year: int | None,
    conn: sqlite3.Connection,
    data_root: Path,
    client: GameChangerClient | None = None,
) -> str | None:
    """Attempt to resolve a tracked team's gc_uuid using a three-tier cascade.

    The cascade stops at the first tier that produces a result. If a gc_uuid
    is found, it is stored on the team row (conditional -- never overwrites).

    Args:
        team_id: Internal ``teams.id`` for the target tracked team.
        public_id: Public slug for the target team.
        team_name: Display name of the target team.
        season_year: Season year for search validation (None skips tier 3).
        conn: Open SQLite connection.
        data_root: Path to ``data/raw/`` directory.
        client: Optional authenticated GameChangerClient (needed for tier 3).

    Returns:
        The resolved gc_uuid string, or None if all tiers fail.

    Raises:
        CredentialExpiredError: If tier 3 encounters an auth failure.
    """
    # Tier 1: member-team boxscores
    try:
        uuid = _tier1_boxscore_extraction(team_id, conn, data_root)
        if uuid:
            _store_gc_uuid(conn, team_id, uuid)
            logger.info(
                "gc_uuid resolved via tier 1 (boxscore) for team_id=%d: %s",
                team_id, uuid,
            )
            return uuid
    except Exception:  # noqa: BLE001
        logger.warning(
            "Tier 1 (boxscore) failed for team_id=%d", team_id, exc_info=True,
        )

    # Tier 2: progenitor_team_id from opponents.json
    try:
        uuid = _tier2_progenitor(team_name, conn, data_root)
        if uuid:
            _store_gc_uuid(conn, team_id, uuid)
            logger.info(
                "gc_uuid resolved via tier 2 (progenitor) for team_id=%d: %s",
                team_id, uuid,
            )
            return uuid
    except Exception:  # noqa: BLE001
        logger.warning(
            "Tier 2 (progenitor) failed for team_id=%d", team_id, exc_info=True,
        )

    # Tier 3: POST /search (only with client and season_year)
    if client is None:
        logger.debug(
            "Tier 3 skipped for team_id=%d: no client provided", team_id,
        )
        return None

    if season_year is None:
        logger.debug(
            "Tier 3 skipped for team_id=%d: season_year is None", team_id,
        )
        return None

    try:
        uuid = _tier3_search(team_name, season_year, client)
        if uuid:
            _store_gc_uuid(conn, team_id, uuid)
            logger.info(
                "gc_uuid resolved via tier 3 (search) for team_id=%d: %s",
                team_id, uuid,
            )
            return uuid
    except CredentialExpiredError:
        raise
    except Exception:
        logger.warning(
            "Tier 3 (search) failed for team_id=%d", team_id, exc_info=True,
        )

    return None


def _tier1_boxscore_extraction(
    team_id: int,
    conn: sqlite3.Connection,
    data_root: Path,
) -> str | None:
    """Tier 1: Scan member-team boxscores for the opponent UUID.

    Each boxscore JSON has two top-level keys: the member team's gc_uuid and
    the opponent's gc_uuid. We extract the non-member UUID, then verify that
    the target team participated in that game via the games table.
    """
    # Get all member teams' gc_uuids.
    member_rows = conn.execute(
        "SELECT id, gc_uuid FROM teams WHERE membership_type = 'member' AND gc_uuid IS NOT NULL"
    ).fetchall()

    if not member_rows:
        return None

    for _member_id, member_gc_uuid in member_rows:
        # Scan all season directories for this member's boxscores.
        teams_glob = data_root.glob(f"*/teams/{member_gc_uuid}/boxscores/*.json")
        for boxscore_path in teams_glob:
            try:
                with open(boxscore_path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            if not isinstance(data, dict):
                continue

            # Extract the UUID key that is NOT the member team's own gc_uuid.
            opponent_uuid = None
            for key in data:
                if _UUID_RE.match(key) and key != member_gc_uuid:
                    opponent_uuid = key
                    break

            if not opponent_uuid:
                continue

            # The boxscore filename stem is the event_id, which maps to
            # games.game_id.
            event_id = boxscore_path.stem

            # Cross-reference with games table: verify target team played.
            row = conn.execute(
                "SELECT 1 FROM games WHERE game_id = ? "
                "AND (home_team_id = ? OR away_team_id = ?)",
                (event_id, team_id, team_id),
            ).fetchone()

            if row is not None:
                return opponent_uuid

    return None


def _tier2_progenitor(
    team_name: str,
    conn: sqlite3.Connection,
    data_root: Path,
) -> str | None:
    """Tier 2: Find progenitor_team_id from cached opponents.json files.

    Scans all member teams' opponents.json files for a name match
    (case-insensitive). Returns progenitor_team_id when non-null.
    """
    member_rows = conn.execute(
        "SELECT gc_uuid FROM teams WHERE membership_type = 'member' AND gc_uuid IS NOT NULL"
    ).fetchall()

    if not member_rows:
        return None

    for (member_gc_uuid,) in member_rows:
        opponents_files = data_root.glob(f"*/teams/{member_gc_uuid}/opponents.json")
        for opp_path in opponents_files:
            try:
                with open(opp_path) as f:
                    entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            if not isinstance(entries, list):
                continue

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name", "")
                if name.lower() == team_name.lower():
                    progenitor = entry.get("progenitor_team_id")
                    if progenitor:
                        return progenitor

    return None


def _tier3_search(
    team_name: str,
    season_year: int,
    client: GameChangerClient,
) -> str | None:
    """Tier 3: POST /search with classification-suffix-stripped name.

    Accepts only a single unambiguous match for the correct season year.
    """
    shortened = _strip_classification_suffix(team_name)

    result = client.post_json(
        "/search",
        body={"name": shortened},
        params={"start_at_page": 0, "search_source": "search"},
        content_type=_SEARCH_CONTENT_TYPE,
    )

    hits = result.get("hits", []) if isinstance(result, dict) else []

    matches = []
    for hit in hits:
        r = hit.get("result", {})
        season = r.get("season") or {}
        hit_year = season.get("year")
        if hit_year == season_year:
            matches.append(r)

    if len(matches) != 1:
        if matches:
            logger.debug(
                "Tier 3: %d matches for '%s' (year=%d) -- ambiguous, skipping",
                len(matches), shortened, season_year,
            )
        else:
            logger.debug(
                "Tier 3: no match for '%s' (year=%d)", shortened, season_year,
            )
        return None

    gc_uuid: str = matches[0].get("id", "")
    if not gc_uuid or not _UUID_RE.match(gc_uuid.lower()):
        logger.debug(
            "Tier 3: match id '%s' is not a valid UUID -- skipping", gc_uuid,
        )
        return None

    return gc_uuid


def _strip_classification_suffix(name: str) -> str:
    """Iteratively strip classification suffixes from a team name.

    Handles cases like "Lincoln Northeast Reserve/Freshman Rockets" by
    removing known suffixes. Strips trailing whitespace after each removal.
    """
    result = name.strip()
    changed = True
    while changed:
        changed = False
        for suffix in _CLASSIFICATION_SUFFIXES:
            # Try removing suffix as a whole word (space-bounded).
            pattern = r"\s+" + re.escape(suffix) + r"(?=\s|$)"
            new_result = re.sub(pattern, "", result, flags=re.IGNORECASE)
            if new_result != result:
                result = new_result.strip()
                changed = True
                break
    return result


def _store_gc_uuid(conn: sqlite3.Connection, team_id: int, gc_uuid: str) -> None:
    """Store resolved gc_uuid on team row, never overwriting existing value."""
    conn.execute(
        "UPDATE teams SET gc_uuid = ? WHERE id = ? AND gc_uuid IS NULL",
        (gc_uuid, team_id),
    )
    conn.commit()
