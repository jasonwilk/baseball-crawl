"""Backfill utility: update UUID-stub team names from on-disk data files.

A "UUID-stub" team row is one where ``teams.name == teams.gc_uuid``.  These
are created by the game loader when it encounters a new opponent whose name is
not yet known.  After E-132-01, normal loading self-heals stubs for opponents
that appear in re-loaded games.  This module fixes stubs for opponents that
are not re-loaded (e.g., prior seasons, inactive opponents).

Data sources scanned:
- ``data/raw/{season}/teams/{team_id}/opponents.json``
  Keyed by ``progenitor_team_id`` (NOT ``root_team_id``).
- ``data/raw/{season}/teams/{team_id}/schedule.json``
  Keyed by ``pregame_data.opponent_id`` (supplement for null progenitor gaps).
- ``data/raw/{season}/scouting/{public_id}/games.json`` +
  ``data/raw/{season}/scouting/{public_id}/boxscores/*.json``
  games.json supplies ``opponent_team.name`` keyed by game_stream_id;
  boxscore files supply the UUID key for each game_stream_id.

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.backfill import backfill_team_names

    conn = sqlite3.connect("data/app.db")
    conn.execute("PRAGMA foreign_keys=ON;")
    updated = backfill_team_names(conn, Path("data/raw"))
    print(f"{updated} team name(s) updated")
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# UUID pattern: 8-4-4-4-12 hex digits with dashes (36 chars total).
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def build_name_lookup_from_raw_data(data_root: Path) -> dict[str, str]:
    """Scan all on-disk data files under ``data_root`` and build a UUID → name map.

    Combines three sources:
    1. ``opponents.json`` files (authenticated path) -- ``progenitor_team_id → name``.
    2. ``schedule.json`` files (authenticated path) -- ``pregame_data.opponent_id →
       pregame_data.opponent_name`` (supplements null-progenitor gaps).
    3. ``games.json`` + boxscores (scouting path) -- maps UUID keys from boxscore
       files to ``opponent_team.name`` from the matching games.json entry.

    Args:
        data_root: Path to the raw data root (e.g. ``data/raw/``).

    Returns:
        Dict mapping canonical GC team UUID to human-readable team name.
        Returns an empty dict if ``data_root`` does not exist.
    """
    lookup: dict[str, str] = {}
    if not data_root.is_dir():
        logger.info("data_root %s does not exist; returning empty lookup.", data_root)
        return lookup

    # --- Authenticated path: opponents.json and schedule.json ---
    # Collect unique team dirs from both files so schedule-only dirs are included.
    team_dirs: set[Path] = set()
    for opponents_path in sorted(data_root.glob("*/teams/*/opponents.json")):
        team_dirs.add(opponents_path.parent)
    for schedule_path in sorted(data_root.glob("*/teams/*/schedule.json")):
        team_dirs.add(schedule_path.parent)
    for team_dir in sorted(team_dirs):
        _merge_authenticated_dir(team_dir, lookup)

    # --- Scouting path: games.json + boxscores ---
    for games_path in sorted(data_root.glob("*/scouting/*/games.json")):
        scouting_dir = games_path.parent
        _merge_scouting_dir(scouting_dir, lookup)

    logger.info(
        "Built name lookup from on-disk data: %d entries across all sources.", len(lookup)
    )
    return lookup


def _merge_authenticated_dir(team_dir: Path, lookup: dict[str, str]) -> None:
    """Add ``progenitor_team_id → name`` entries from opponents.json and schedule.json."""
    # Primary source: opponents.json
    opponents_path = team_dir / "opponents.json"
    if opponents_path.exists():
        try:
            with opponents_path.open(encoding="utf-8") as fh:
                opponents = json.load(fh)
            if isinstance(opponents, list):
                for opp in opponents:
                    pid = opp.get("progenitor_team_id")  # canonical UUID
                    name = opp.get("name")
                    # Skip hidden records and entries with null progenitor_team_id.
                    if pid and name and not opp.get("is_hidden") and pid not in lookup:
                        lookup[pid] = name
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", opponents_path, exc)

    # Supplementary source: schedule.json (fills null-progenitor gaps)
    schedule_path = team_dir / "schedule.json"
    if schedule_path.exists():
        try:
            with schedule_path.open(encoding="utf-8") as fh:
                schedule = json.load(fh)
            if isinstance(schedule, list):
                for event in schedule:
                    pregame = event.get("pregame_data") or {}
                    opp_id = pregame.get("opponent_id")
                    opp_name = pregame.get("opponent_name")
                    if opp_id and opp_name and opp_id not in lookup:
                        lookup[opp_id] = opp_name
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", schedule_path, exc)


def _merge_scouting_dir(scouting_dir: Path, lookup: dict[str, str]) -> None:
    """Add UUID → name entries from a scouting directory.

    Reads ``games.json`` to build a ``game_stream_id → opponent_name`` map,
    then opens each boxscore to discover which UUID key is the opponent for
    each game.

    Uses a two-pass strategy to avoid mislabeling the scouted team's own UUID
    as an opponent:

    1. First pass: count how many boxscores each UUID appears in.  The scouted
       team's own UUID appears in ALL their games; each opponent UUID appears in
       only one.  UUIDs seen in 2+ boxscores are treated as the scouted team's
       own UUID and excluded from the lookup.
    2. Second pass: add only opponent UUIDs (those not excluded) to ``lookup``.

    Limitation: when a scouting directory contains only one game, both the
    scouted team's UUID and the opponent's UUID appear exactly once, so they
    cannot be distinguished.  In that case both UUIDs may be added; this is an
    accepted edge-case limitation.
    """
    games_path = scouting_dir / "games.json"
    try:
        with games_path.open(encoding="utf-8") as fh:
            games = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", games_path, exc)
        return

    if not isinstance(games, list):
        return

    # Build game_stream_id → opponent_name from games.json
    name_by_stream: dict[str, str] = {}
    for game in games:
        game_id = game.get("id")
        opp_team = game.get("opponent_team") or {}
        name = opp_team.get("name")
        if game_id and name:
            name_by_stream[str(game_id)] = name

    if not name_by_stream:
        return

    boxscores_dir = scouting_dir / "boxscores"
    if not boxscores_dir.is_dir():
        return

    # First pass: count UUID occurrences across ALL boxscores to identify the
    # scouted team's own UUID (it appears in every game they played).
    uuid_counts: dict[str, int] = {}
    loaded_boxscores: list[tuple[str, dict]] = []

    for bs_path in sorted(boxscores_dir.glob("*.json")):
        game_stream_id = bs_path.stem
        try:
            with bs_path.open(encoding="utf-8") as fh:
                boxscore = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(boxscore, dict):
            continue
        loaded_boxscores.append((game_stream_id, boxscore))
        for key in boxscore:
            if _UUID_RE.match(key):
                uuid_counts[key] = uuid_counts.get(key, 0) + 1

    # UUIDs appearing in 2+ boxscores belong to the scouted team, not opponents.
    scouted_uuids = {k for k, v in uuid_counts.items() if v > 1}

    # Second pass: add opponent UUIDs (those not identified as scouted team) to lookup.
    for game_stream_id, boxscore in loaded_boxscores:
        name = name_by_stream.get(game_stream_id)
        if name is None:
            continue
        for key in boxscore:
            if _UUID_RE.match(key) and key not in scouted_uuids and key not in lookup:
                lookup[key] = name


def backfill_team_names(db: sqlite3.Connection, data_root: Path) -> int:
    """Update UUID-stub team names in the database from on-disk data files.

    Queries the database for team rows where ``name == gc_uuid`` (UUID-stubs).
    For each match, looks up a real name from on-disk data and issues an UPDATE.
    Rows where ``name`` is already a non-UUID value are not touched.

    Args:
        db: Open ``sqlite3.Connection`` with ``PRAGMA foreign_keys=ON`` set.
        data_root: Path to the raw data root directory (e.g. ``data/raw/``).

    Returns:
        Number of team rows updated.
    """
    lookup = build_name_lookup_from_raw_data(data_root)
    if not lookup:
        logger.info("No opponent name data found on disk; nothing to backfill.")
        return 0

    # Find all UUID-stub rows: name == gc_uuid (exact column match).
    stubs = db.execute(
        "SELECT id, gc_uuid FROM teams WHERE gc_uuid IS NOT NULL AND name = gc_uuid"
    ).fetchall()

    updated = 0
    for team_id, gc_uuid in stubs:
        name = lookup.get(gc_uuid)
        if name:
            db.execute("UPDATE teams SET name = ? WHERE id = ?", (name, team_id))
            logger.debug(
                "Backfilled team name: id=%d gc_uuid=%s -> %r", team_id, gc_uuid, name
            )
            updated += 1

    if updated:
        db.commit()

    logger.info("Backfill complete: %d team name(s) updated.", updated)
    return updated
