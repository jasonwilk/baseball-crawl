"""Shared player-row lookup and creation with name-preference logic.

Provides ``ensure_player_row()`` -- a single function that all loader paths
use to find or create a player row.  The name-preference rule prevents
shorter names (initials) from overwriting longer names (full names), and
treats ``"Unknown"`` as length 0.

This follows the established pattern of ``ensure_team_row()`` in
``src/db/teams.py``.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def ensure_player_row(
    db: sqlite3.Connection,
    player_id: str,
    first_name: str,
    last_name: str,
) -> None:
    """Find or create a player row using the name-preference rule.

    The name-preference rule (TN-1): a name component is only updated when
    the incoming value is strictly longer than the stored value. ``"Unknown"``
    is treated as length 0 so any real name (even a single initial) upgrades
    from a stub, but ``"Unknown"`` never overwrites a real name.

    Each name component (first_name, last_name) is evaluated independently.

    Args:
        db: An open sqlite3.Connection.
        player_id: GameChanger player UUID (``players.player_id`` PK).
        first_name: Incoming first name (may be ``"Unknown"``).
        last_name: Incoming last name (may be ``"Unknown"``).
    """
    db.execute(
        """
        INSERT INTO players (player_id, first_name, last_name)
        VALUES (?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            first_name = CASE
                WHEN LENGTH(excluded.first_name) > LENGTH(players.first_name)
                     AND excluded.first_name != 'Unknown'
                THEN excluded.first_name
                WHEN players.first_name = 'Unknown'
                     AND excluded.first_name != 'Unknown'
                THEN excluded.first_name
                ELSE players.first_name
            END,
            last_name = CASE
                WHEN LENGTH(excluded.last_name) > LENGTH(players.last_name)
                     AND excluded.last_name != 'Unknown'
                THEN excluded.last_name
                WHEN players.last_name = 'Unknown'
                     AND excluded.last_name != 'Unknown'
                THEN excluded.last_name
                ELSE players.last_name
            END
        """,
        (player_id, first_name, last_name),
    )
    logger.debug(
        "ensure_player_row: player_id=%s first_name=%r last_name=%r",
        player_id,
        first_name,
        last_name,
    )
