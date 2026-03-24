"""Schedule-based opponent seeder for the GameChanger data ingestion pipeline.

Reads a team's cached ``schedule.json`` and ``opponents.json`` files and
upserts identity rows into the ``opponent_links`` table for every unique
opponent found in the schedule.

This is a pure local-file reader -- no API calls are made.  Resolution
(populating ``resolved_team_id``, ``public_id``, and ``resolution_method``)
is deferred to :class:`~src.gamechanger.crawlers.opponent_resolver.OpponentResolver`.

Designed to be called once per member team *before* ``OpponentResolver.resolve()``
so that every opponent seen in the schedule is present in ``opponent_links``
before the API resolution pass begins.

Usage::

    import sqlite3
    from pathlib import Path
    from src.gamechanger.loaders.opponent_seeder import seed_schedule_opponents

    conn = sqlite3.connect("./data/app.db")
    count = seed_schedule_opponents(
        team_id=1,
        schedule_path=Path("data/raw/2026-spring-hs/teams/<gc_uuid>/schedule.json"),
        opponents_path=Path("data/raw/2026-spring-hs/teams/<gc_uuid>/opponents.json"),
        db=conn,
    )
    print(f"Seeded {count} opponents")
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Upsert SQL: always refresh opponent_name; never touch resolution fields.
#
# When a row already exists (e.g., already resolved by OpponentResolver with
# resolution_method='auto', 'follow-bridge', or 'manual'), only opponent_name
# is updated.  resolved_team_id, public_id, resolution_method, and resolved_at
# are left unchanged -- protecting rows that OpponentResolver already upgraded.
#
# When no row exists, a new row is inserted with only our_team_id, root_team_id,
# and opponent_name populated; all resolution fields default to NULL.
_UPSERT_SQL = """
    INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name)
    VALUES (?, ?, ?)
    ON CONFLICT(our_team_id, root_team_id) DO UPDATE SET
        opponent_name = excluded.opponent_name
"""


def seed_schedule_opponents(
    team_id: int,
    schedule_path: Path,
    opponents_path: Path,
    db: sqlite3.Connection,
) -> int:
    """Seed ``opponent_links`` from a team's cached schedule and opponents JSON files.

    Reads ``schedule.json`` for ``pregame_data.opponent_id`` and
    ``pregame_data.opponent_name``, cross-references ``opponents.json`` for
    the canonical opponent name, and upserts one row per unique opponent into
    ``opponent_links``.

    Name precedence:
    - ``opponents.json`` ``name`` field (primary).
    - ``schedule.json`` ``pregame_data.opponent_name`` (fallback when the
      opponent is absent from ``opponents.json``).

    Resolution fields (``resolved_team_id``, ``public_id``, ``resolution_method``,
    ``resolved_at``) are always ``NULL`` on insert and are never overwritten on
    conflict -- protecting rows already resolved by ``OpponentResolver``.

    Args:
        team_id: INTEGER PK of the member team in the ``teams`` table
            (written as ``our_team_id`` in ``opponent_links``).
        schedule_path: Path to the team's cached ``schedule.json`` file.
        opponents_path: Path to the team's cached ``opponents.json`` file.
            Missing or empty ``opponents.json`` is non-fatal -- schedule
            opponent names are used as fallback.
        db: Open SQLite connection.  ``PRAGMA foreign_keys=ON`` is recommended
            by the caller but not required by this function.

    Returns:
        Number of unique opponents upserted into ``opponent_links``.
        Returns ``0`` when ``schedule.json`` is missing or empty.

    Raises:
        json.JSONDecodeError: If ``schedule.json`` or ``opponents.json``
            contains malformed JSON.
        sqlite3.Error: On database write failure.
    """
    # --- Load schedule.json -- missing or empty is non-fatal ---
    if not schedule_path.exists():
        logger.info(
            "schedule.json not found for team %d at %s; skipping seeder.",
            team_id,
            schedule_path,
        )
        return 0

    schedule_text = schedule_path.read_text(encoding="utf-8").strip()
    if not schedule_text:
        logger.info(
            "schedule.json is empty for team %d at %s; skipping seeder.",
            team_id,
            schedule_path,
        )
        return 0

    schedule: list[Any] = json.loads(schedule_text)
    if not schedule:
        logger.info(
            "schedule.json contains no events for team %d; skipping seeder.",
            team_id,
        )
        return 0

    # --- Load opponents.json for name lookup -- missing is non-fatal ---
    opponents_lookup: dict[str, str] = _load_opponents_lookup(team_id, opponents_path)

    # --- Collect unique opponents from schedule events ---
    # Key:   root_team_id (= pregame_data.opponent_id, confirmed identical)
    # Value: resolved display name (opponents.json preferred, schedule fallback)
    unique_opponents: dict[str, str] = {}
    skipped = 0

    for event in schedule:
        pregame: dict[str, Any] | None = event.get("pregame_data")
        if not pregame:
            skipped += 1
            continue

        opponent_id: str | None = pregame.get("opponent_id")
        if not opponent_id:
            skipped += 1
            continue

        if opponent_id not in unique_opponents:
            # opponents.json name is primary; schedule name is fallback.
            name = opponents_lookup.get(opponent_id) or pregame.get("opponent_name") or ""
            unique_opponents[opponent_id] = name

    if skipped:
        logger.debug(
            "Skipped %d schedule event(s) without pregame_data or opponent_id "
            "for team %d.",
            skipped,
            team_id,
        )

    if not unique_opponents:
        logger.info(
            "No opponents with opponent_id found in schedule for team %d.", team_id
        )
        return 0

    # --- Upsert all unique opponents into opponent_links ---
    for root_team_id, opponent_name in unique_opponents.items():
        db.execute(_UPSERT_SQL, (team_id, root_team_id, opponent_name))
        logger.debug(
            "Upserted opponent '%s' (root_team_id=%s) for team %d.",
            opponent_name,
            root_team_id,
            team_id,
        )

    db.commit()

    count = len(unique_opponents)
    logger.info("Seeded %d opponent(s) for team %d from schedule.", count, team_id)
    return count


def _load_opponents_lookup(team_id: int, opponents_path: Path) -> dict[str, str]:
    """Load a ``root_team_id -> name`` mapping from ``opponents.json``.

    Missing or empty ``opponents.json`` returns an empty dict (non-fatal).

    Args:
        team_id: Member team ID (used in log messages only).
        opponents_path: Path to the team's cached ``opponents.json`` file.

    Returns:
        Mapping of ``root_team_id`` to ``name`` for all valid entries.

    Raises:
        json.JSONDecodeError: If the file exists but contains malformed JSON.
    """
    if not opponents_path.exists():
        logger.info(
            "opponents.json not found for team %d at %s; "
            "schedule opponent names will be used as fallback.",
            team_id,
            opponents_path,
        )
        return {}

    opponents_text = opponents_path.read_text(encoding="utf-8").strip()
    if not opponents_text:
        logger.debug(
            "opponents.json is empty for team %d; using schedule names.", team_id
        )
        return {}

    opponents_data: list[Any] = json.loads(opponents_text)
    lookup: dict[str, str] = {}
    for opp in opponents_data:
        root_id: str | None = opp.get("root_team_id")
        name: str | None = opp.get("name")
        if root_id and name:
            lookup[root_id] = name

    logger.debug(
        "Loaded %d opponent name(s) from opponents.json for team %d.",
        len(lookup),
        team_id,
    )
    return lookup
