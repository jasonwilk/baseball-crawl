"""Corrective re-ingest for self-game (``home == away``) corruption (E-245-04).

Background (E-245 TN-6): a scouting boxscore whose opponent never used GC
scorekeeping carries only the scouted team's stat block, so the pre-fix loader
collapsed the opponent onto ``own_team_id`` and wrote a self-game
(``home_team_id == away_team_id``).  The plays parser then derived
``batting_team_id`` from ``half`` against the collapsed home/away, so both halves
landed on one team id -- corrupting team rollups and over-attributing pitchers.

The forward fix lives in ``game_loader.py`` (the opponent now always resolves to
a distinct team -- by name when the stat block is absent, else an
"Unknown Opponent" sentinel).  This module drives the ONE-TIME correction of the
games ingested BEFORE that fix:

1. :func:`find_self_games` / :func:`affected_team_ids` locate the corrupt rows.
2. The CLI (``bb data fix-self-games``) re-fetches each affected team's
   boxscores via the existing scouting crawl->load pipeline (an API re-fetch --
   the opponent name was discarded at ingest and is unrecoverable from the DB),
   re-running the FIXED loader so the ``games`` row is corrected to
   ``home != away`` and the opponent is created by name.
3. :func:`rederive_corrected_game_plays` re-derives the collapsed
   ``batting_team_id`` IN PLACE via E-245-02's ``reload_game_plays`` entry point
   (TN-3b: it re-reads home/away FRESH from the corrected games row).  Plays and
   play_events are NEVER cleared or re-fetched -- clearing would destroy
   ``raw_template`` (TN-3/M1).

Perspective scoping + Cleanup-Detection Mirror Invariant (AC-4): every step here
is non-destructive.  ``reload_game_plays`` is perspective-scoped and only UPDATEs
``plays`` / ``play_events`` rows; the boxscore re-ingest's season-aggregate
recompute (``canonical_recompute``) preserves member ``full``/``supplemented``
rows via its provenance guard.  Nothing in this module DELETEs a row, so the
Cleanup-Detection Mirror Invariant (``.claude/rules/data-model.md``) is not
engaged -- there is no cleanup surface to mirror.
"""

from __future__ import annotations

import logging
import sqlite3

from src.gamechanger.loaders.plays_reload import reload_game_plays

logger = logging.getLogger(__name__)


def find_self_games(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Return ``[(game_id, team_id)]`` for completed self-games (home == away).

    ``team_id`` is the collapsed ``home_team_id`` (== ``away_team_id``) -- the
    scouted team whose boxscore must be re-fetched.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(game_id, team_id)`` tuples, ordered by ``game_id``.
    """
    return [
        (row[0], row[1])
        for row in conn.execute(
            "SELECT game_id, home_team_id FROM games "
            "WHERE home_team_id = away_team_id AND status = 'completed' "
            "ORDER BY game_id"
        ).fetchall()
    ]


def affected_team_ids(conn: sqlite3.Connection) -> list[int]:
    """Return the distinct team ids that own at least one completed self-game.

    These are the teams whose boxscores need an API re-fetch through the FIXED
    loader.

    Args:
        conn: Open SQLite connection.

    Returns:
        Sorted list of ``teams.id`` integers.
    """
    return [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT home_team_id FROM games "
            "WHERE home_team_id = away_team_id AND status = 'completed' "
            "ORDER BY home_team_id"
        ).fetchall()
    ]


def rederive_corrected_game_plays(
    conn: sqlite3.Connection,
    game_ids: list[str],
) -> dict[str, int]:
    """Re-derive ``batting_team_id`` IN PLACE for the given games (TN-3b).

    Call this AFTER the boxscore re-ingest has corrected each game's ``games``
    row to ``home != away``.  For every game, every distinct perspective present
    in ``plays`` is re-derived via :func:`reload_game_plays`, which re-reads
    home/away FRESH from the (now corrected) games row and re-derives
    ``batting_team_id`` per ``half``.  Commits per game so a mid-run failure
    isolates to one game (mirrors ``reload_all_games``).  Idempotent; a game
    with no plays rows is a no-op.

    This NEVER clears ``play_events`` and NEVER re-fetches plays -- it only
    UPDATEs existing rows (TN-6).

    Args:
        conn: Open SQLite connection.  The caller owns the connection; this
            function commits per game.
        game_ids: The game ids to re-derive (the games that WERE self-games).

    Returns:
        Summary dict with keys ``games_rederived``, ``plays_updated``,
        ``games_with_errors``.
    """
    summary = {"games_rederived": 0, "plays_updated": 0, "games_with_errors": 0}
    for game_id in game_ids:
        perspective_rows = conn.execute(
            "SELECT DISTINCT perspective_team_id FROM plays WHERE game_id = ?",
            (game_id,),
        ).fetchall()
        if not perspective_rows:
            continue
        try:
            plays_updated = 0
            for (perspective_team_id,) in perspective_rows:
                result = reload_game_plays(conn, game_id, perspective_team_id)
                plays_updated += result.plays_updated
            conn.commit()
        except Exception as exc:  # noqa: BLE001 -- per-game error isolation
            conn.rollback()
            logger.error("Re-derive error for corrected game %s: %s", game_id, exc)
            summary["games_with_errors"] += 1
            continue
        summary["games_rederived"] += 1
        summary["plays_updated"] += plays_updated
    return summary
