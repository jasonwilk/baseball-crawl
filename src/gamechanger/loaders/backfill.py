"""Backfill appearance_order for existing player_game_pitching rows.

.. deprecated::
    **One-time migration aid for E-204.** The ``appearance_order`` column is
    now populated at INSERT time by the game loader
    (``src/gamechanger/loaders/game_loader.py``). This script was needed only
    to backfill historical rows that pre-dated E-204. It reads from
    disk-cached boxscore JSON (``data/raw/``), which means it does not work
    in the scouting pipeline's in-memory flow. It also does not include
    perspective-aware filtering. No further maintenance is planned.

Walks cached boxscore JSON files on disk and updates rows where
appearance_order IS NULL. Idempotent and re-runnable.

See E-204-02 for context.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DATA_ROOT = _PROJECT_ROOT / "data" / "raw"


def resolve_boxscore_path(
    season_id: str,
    game_id: str,
    game_stream_id: str | None,
    gc_uuid: str | None,
    public_id: str | None,
    data_root: Path | None = None,
) -> Path | None:
    """Find cached boxscore JSON on disk.

    Tries member team path first, then scouting path. Mirrors the path
    resolution in ``src/reconciliation/engine.py`` ``_extract_pitcher_order()``.

    Args:
        season_id: Season directory name (e.g., ``"2025"``).
        game_id: Canonical event_id.
        game_stream_id: Alternate file key (may be ``None``).
        gc_uuid: Team's GameChanger UUID (may be ``None``).
        public_id: Team's public_id slug (may be ``None``).
        data_root: Override for the data root directory (for testing).

    Returns:
        Path to the boxscore JSON file, or ``None`` if not found.
    """
    root = data_root or _DATA_ROOT

    # Member team path
    if gc_uuid:
        member_base = root / season_id / "teams" / gc_uuid / "games"
        for filename in (game_id, game_stream_id):
            if filename:
                candidate = member_base / f"{filename}.json"
                if candidate.is_file():
                    return candidate

    # Scouting path
    if public_id:
        scouting_base = root / season_id / "scouting" / public_id / "boxscores"
        for filename in (game_stream_id, game_id):
            if filename:
                candidate = scouting_base / f"{filename}.json"
                if candidate.is_file():
                    return candidate

    return None


def parse_pitcher_order_for_team(
    boxscore: dict,
    gc_uuid: str | None,
    public_id: str | None,
) -> list[str] | None:
    """Extract pitcher player_ids in appearance order for a specific team.

    The boxscore JSON is keyed by team identifier (public_id slug or UUID).
    Within each team's data, groups with ``category="pitching"`` contain a
    ``stats`` array ordered by appearance.

    Args:
        boxscore: Full team-keyed boxscore dict.
        gc_uuid: Team's GameChanger UUID for key matching.
        public_id: Team's public_id slug for key matching.

    Returns:
        List of player_id strings in appearance order, or ``None`` if not found.
    """
    # Find the team's data by matching key against gc_uuid or public_id
    team_data = None
    for key in boxscore:
        if gc_uuid and key.lower() == gc_uuid.lower():
            team_data = boxscore[key]
            break
        if public_id and key == public_id:
            team_data = boxscore[key]
            break

    if team_data is None:
        return None

    # Find pitching group
    for group in team_data.get("groups") or []:
        if group.get("category") == "pitching":
            stats = group.get("stats") or []
            player_ids = [
                row["player_id"]
                for row in stats
                if row.get("player_id")
            ]
            return player_ids if player_ids else None

    return None


def backfill_appearance_order(
    conn: sqlite3.Connection,
    data_root: Path | None = None,
) -> dict[str, int]:
    """Backfill appearance_order for all NULL rows.

    Args:
        conn: Open SQLite connection with FK enforcement on.
        data_root: Override for the data root directory (for testing).

    Returns:
        Summary dict with keys: ``games_processed``, ``rows_updated``,
        ``games_skipped``, ``games_with_errors``.
    """
    summary = {
        "games_processed": 0,
        "rows_updated": 0,
        "games_skipped": 0,
        "games_with_errors": 0,
    }

    # Group by game_id: for each game, gather all teams with NULL rows.
    # A boxscore file cached under one team's path contains BOTH teams' data,
    # so we try all participating teams' paths to find the file, then backfill
    # every team from that single file.
    game_teams = conn.execute(
        """
        SELECT DISTINCT
            pgp.game_id,
            pgp.team_id,
            g.season_id,
            g.game_stream_id,
            t.gc_uuid,
            t.public_id,
            t.name
        FROM player_game_pitching pgp
        JOIN games g ON g.game_id = pgp.game_id
        JOIN teams t ON t.id = pgp.team_id
        WHERE pgp.appearance_order IS NULL
        ORDER BY g.season_id, pgp.game_id, pgp.team_id
        """
    ).fetchall()

    if not game_teams:
        logger.info("No rows with NULL appearance_order found.")
        return summary

    # Build per-game team lists
    games: dict[str, list[tuple]] = {}
    for row in game_teams:
        game_id = row[0]
        games.setdefault(game_id, []).append(row)

    logger.info(
        "Found %d games (%d game-team pairs) to backfill.",
        len(games), len(game_teams),
    )

    for game_id, team_rows in games.items():
        # Try to find the boxscore file from any participating team's path
        season_id = team_rows[0][2]
        game_stream_id = team_rows[0][3]
        boxscore_path = None
        raw = None

        for _, _, sid, gsid, gc_uuid, public_id, _ in team_rows:
            boxscore_path = resolve_boxscore_path(
                sid, game_id, gsid, gc_uuid, public_id,
                data_root=data_root,
            )
            if boxscore_path is not None:
                break

        if boxscore_path is None:
            logger.warning(
                "No cached boxscore for game_id=%s from any participating team; skipping.",
                game_id,
            )
            summary["games_skipped"] += 1
            continue

        try:
            raw = json.loads(boxscore_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "Failed to load boxscore JSON at %s for game_id=%s: %s",
                boxscore_path, game_id, exc,
            )
            summary["games_with_errors"] += 1
            continue

        # Backfill all teams from this single boxscore file
        updated_in_game = 0
        teams_with_errors = 0
        for _, team_id, _, _, gc_uuid, public_id, team_name in team_rows:
            pitcher_ids = parse_pitcher_order_for_team(raw, gc_uuid, public_id)
            if pitcher_ids is None:
                logger.warning(
                    "Could not parse pitcher order from %s for team=%s (id=%d); skipping team.",
                    boxscore_path, team_name, team_id,
                )
                teams_with_errors += 1
                continue

            for order, player_id in enumerate(pitcher_ids, start=1):
                cur = conn.execute(
                    """
                    UPDATE player_game_pitching
                    SET appearance_order = ?
                    WHERE game_id = ? AND player_id = ? AND team_id = ?
                      AND appearance_order IS NULL
                    """,
                    (order, game_id, player_id, team_id),
                )
                updated_in_game += cur.rowcount

        if teams_with_errors == len(team_rows):
            summary["games_with_errors"] += 1
        else:
            summary["games_processed"] += 1
        summary["rows_updated"] += updated_in_game

        if updated_in_game > 0:
            logger.debug(
                "Backfilled %d pitchers for game_id=%s",
                updated_in_game, game_id,
            )

    conn.commit()
    return summary
