"""Player duplicate detection and merge.

Identifies same-team duplicate player pairs where one player's first_name is
a prefix of the other's (e.g., "O" vs "Oliver"), suggesting they are the same
person entered under a shortened name.

The canonical player (the one to keep) has the longer first_name. Ties are
broken by total stat row count, then alphabetical player_id.

The merge function atomically reassigns all FK references from a duplicate
player_id to the canonical player_id, handling UNIQUE constraint conflicts
with delete-or-update, then deletes the duplicate player row.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DuplicatePlayerPair:
    """A detected duplicate player pair with canonical assignment.

    Attributes:
        canonical_player_id: The player_id to keep (longer first_name).
        duplicate_player_id: The player_id to merge away.
        canonical_first_name: First name of the canonical player.
        canonical_last_name: Last name of the canonical player.
        duplicate_first_name: First name of the duplicate player.
        duplicate_last_name: Last name of the duplicate player.
        team_id: The team where both players appear on the roster.
        team_name: Display name of the team.
        reason: Human-readable explanation of why they matched.
        has_overlapping_games: True if both player_ids appear in game
            stats for at least one common game_id.
    """

    canonical_player_id: str
    duplicate_player_id: str
    canonical_first_name: str
    canonical_last_name: str
    duplicate_first_name: str
    duplicate_last_name: str
    team_id: int
    team_name: str
    reason: str
    has_overlapping_games: bool


def find_duplicate_players(
    db: sqlite3.Connection,
    team_id: int | None = None,
    season_id: str | None = None,
) -> list[DuplicatePlayerPair]:
    """Find same-team duplicate player pairs using prefix-matching detection.

    Detection signal (TN-2):
    - Both player_ids appear in team_rosters for the same (team_id, season_id)
    - last_name matches (case-insensitive)
    - One first_name is a prefix of the other (case-insensitive)
    - The shorter first_name has LENGTH > 0 (guards against empty strings)

    Canonical selection (TN-3):
    - Longer first_name wins
    - Ties: more total stat rows wins
    - Still tied: alphabetically lower player_id wins

    Results are deduplicated to unique (canonical, duplicate) pairs -- if a
    pair appears across multiple seasons on the same team, it is returned once.

    Args:
        db: An open sqlite3.Connection.
        team_id: Optional -- scope results to this team only.
        season_id: Optional -- scope results to this season only.

    Returns:
        List of DuplicatePlayerPair, one per unique (canonical, duplicate) pair.
    """
    # Build WHERE clause for optional filters
    filters = []
    params: list[object] = []
    if team_id is not None:
        filters.append("tr1.team_id = ?")
        params.append(team_id)
    if season_id is not None:
        filters.append("tr1.season_id = ?")
        params.append(season_id)

    where_clause = ""
    if filters:
        where_clause = "AND " + " AND ".join(filters)

    # The query finds pairs where both players are on the same team roster
    # in the same season, have matching last names (case-insensitive), and
    # one first_name is a case-insensitive prefix of the other.
    #
    # We enforce p1.player_id < p2.player_id to avoid duplicate pairs (A,B)
    # and (B,A). The canonical selection happens in Python after fetching,
    # since it requires stat-count tiebreaking.
    query = f"""
        SELECT DISTINCT
            p1.player_id,
            p1.first_name,
            p1.last_name,
            p2.player_id,
            p2.first_name,
            p2.last_name,
            tr1.team_id,
            t.name AS team_name
        FROM team_rosters tr1
        JOIN team_rosters tr2
            ON  tr1.team_id = tr2.team_id
            AND tr1.season_id = tr2.season_id
            AND tr1.player_id < tr2.player_id
        JOIN players p1 ON p1.player_id = tr1.player_id
        JOIN players p2 ON p2.player_id = tr2.player_id
        JOIN teams t ON t.id = tr1.team_id
        WHERE p1.last_name = p2.last_name COLLATE NOCASE
          AND LENGTH(p1.first_name) > 0
          AND LENGTH(p2.first_name) > 0
          AND (
              -- p1.first_name is a prefix of p2.first_name
              (LENGTH(p1.first_name) <= LENGTH(p2.first_name)
               AND p2.first_name LIKE (p1.first_name || '%') COLLATE NOCASE)
              OR
              -- p2.first_name is a prefix of p1.first_name
              (LENGTH(p2.first_name) <= LENGTH(p1.first_name)
               AND p1.first_name LIKE (p2.first_name || '%') COLLATE NOCASE)
          )
          {where_clause}
        ORDER BY t.name, p1.last_name COLLATE NOCASE
    """

    rows = db.execute(query, params).fetchall()

    if not rows:
        return []

    # Collect all player_ids to batch-fetch stat counts for tiebreaking
    all_player_ids: set[str] = set()
    for row in rows:
        all_player_ids.add(row[0])
        all_player_ids.add(row[3])

    stat_counts = _count_stat_rows(db, all_player_ids)

    # Check for overlapping game appearances in bulk.  E-220 round 6: the
    # overlap check is now scoped by team_id so same-game cross-team matches
    # do not false-positive, and by the team's own perspective so foreign
    # cross-perspective rows are ignored.
    pairs_to_check = [(row[0], row[3], row[6]) for row in rows]  # pid1, pid2, team_id
    overlap_map = _check_game_overlaps(db, pairs_to_check)

    # Build results with canonical selection, deduplicating across seasons
    seen_pairs: set[tuple[str, str]] = set()
    results: list[DuplicatePlayerPair] = []

    for row in rows:
        pid1, fname1, lname1, pid2, fname2, lname2, tid, tname = row

        canonical_pid, dup_pid, canonical_fname, dup_fname = _select_canonical_player(
            pid1, fname1, pid2, fname2, stat_counts
        )

        # Deduplicate: same (canonical, duplicate) pair on same team
        pair_key = (canonical_pid, dup_pid, tid)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        # Build reason string
        shorter = dup_fname
        longer = canonical_fname
        reason = f"prefix match: {shorter!r} is prefix of {longer!r} (last_name={lname1!r})"

        has_overlap = overlap_map.get((min(pid1, pid2), max(pid1, pid2), tid), False)

        results.append(
            DuplicatePlayerPair(
                canonical_player_id=canonical_pid,
                duplicate_player_id=dup_pid,
                canonical_first_name=canonical_fname,
                canonical_last_name=lname1,
                duplicate_first_name=dup_fname,
                duplicate_last_name=lname2,
                team_id=tid,
                team_name=tname,
                reason=reason,
                has_overlapping_games=has_overlap,
            )
        )

    return results


def _select_canonical_player(
    pid1: str,
    fname1: str,
    pid2: str,
    fname2: str,
    stat_counts: dict[str, int],
) -> tuple[str, str, str, str]:
    """Select canonical vs duplicate player per TN-3.

    Returns (canonical_pid, duplicate_pid, canonical_fname, duplicate_fname).
    """
    len1 = len(fname1)
    len2 = len(fname2)

    if len1 > len2:
        return pid1, pid2, fname1, fname2
    elif len2 > len1:
        return pid2, pid1, fname2, fname1
    else:
        # Tie: compare stat counts
        sc1 = stat_counts.get(pid1, 0)
        sc2 = stat_counts.get(pid2, 0)
        if sc1 > sc2:
            return pid1, pid2, fname1, fname2
        elif sc2 > sc1:
            return pid2, pid1, fname2, fname1
        else:
            # Still tied: alphabetical player_id
            if pid1 <= pid2:
                return pid1, pid2, fname1, fname2
            else:
                return pid2, pid1, fname2, fname1


def _count_stat_rows(
    db: sqlite3.Connection,
    player_ids: set[str],
) -> dict[str, int]:
    """Count total stat rows across batting and pitching tables for each player."""
    if not player_ids:
        return {}

    placeholders = ",".join("?" for _ in player_ids)
    pid_list = list(player_ids)

    counts: dict[str, int] = {pid: 0 for pid in player_ids}

    for table in (
        "player_game_batting",
        "player_game_pitching",
        "player_season_batting",
        "player_season_pitching",
    ):
        rows = db.execute(
            f"SELECT player_id, COUNT(*) FROM {table} "  # noqa: S608
            f"WHERE player_id IN ({placeholders}) GROUP BY player_id",
            pid_list,
        ).fetchall()
        for pid, cnt in rows:
            counts[pid] = counts.get(pid, 0) + cnt

    return counts


def _check_game_overlaps(
    db: sqlite3.Connection,
    pairs: list[tuple[str, str, int]],
) -> dict[tuple[str, str, int], bool]:
    """Check which player pairs have overlapping game appearances.

    E-220 round 6: Scoped by team_id and the team's own perspective.
    Two players "overlap" only when both appear in the same game FROM THE
    TEAM'S OWN PERSPECTIVE (``team_id = perspective_team_id``) on the same
    team.  Cross-team coincidental game_id matches and cross-perspective
    foreign rows do NOT count as overlap.

    Args:
        db: Open SQLite connection.
        pairs: List of ``(pid1, pid2, team_id)`` tuples to check.

    Returns:
        Dict mapping ``(min_pid, max_pid, team_id)`` -> bool.
    """
    if not pairs:
        return {}

    result: dict[tuple[str, str, int], bool] = {}

    for pid1, pid2, team_id in pairs:
        key = (min(pid1, pid2), max(pid1, pid2), team_id)
        if key in result:
            continue

        # Both players must appear in the same game on the SAME team and
        # from the team's OWN perspective (team_id = perspective_team_id).
        # Cross-perspective foreign rows are excluded.
        overlap = db.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM (
                    SELECT game_id FROM player_game_batting
                        WHERE player_id = ? AND team_id = ?
                          AND perspective_team_id = team_id
                    UNION
                    SELECT game_id FROM player_game_pitching
                        WHERE player_id = ? AND team_id = ?
                          AND perspective_team_id = team_id
                ) g1
                JOIN (
                    SELECT game_id FROM player_game_batting
                        WHERE player_id = ? AND team_id = ?
                          AND perspective_team_id = team_id
                    UNION
                    SELECT game_id FROM player_game_pitching
                        WHERE player_id = ? AND team_id = ?
                          AND perspective_team_id = team_id
                ) g2 ON g1.game_id = g2.game_id
            )
            """,
            (pid1, team_id, pid1, team_id, pid2, team_id, pid2, team_id),
        ).fetchone()[0]

        result[key] = bool(overlap)

    return result


# ---------------------------------------------------------------------------
# stat_completeness ranking for conflict resolution
# ---------------------------------------------------------------------------

_COMPLETENESS_RANK = {"full": 3, "supplemented": 2, "boxscore_only": 1}


# ---------------------------------------------------------------------------
# Preview / dry-run support
# ---------------------------------------------------------------------------


@dataclass
class PlayerMergePreview:
    """What a player merge would do, without modifying data.

    Attributes:
        canonical_player_id: The player_id to keep.
        duplicate_player_id: The player_id to remove.
        table_counts: Per-table count of rows that would be affected
            (reassigned or deleted).
    """

    canonical_player_id: str
    duplicate_player_id: str
    table_counts: dict[str, int] = field(default_factory=dict)


def preview_player_merge(
    db: sqlite3.Connection,
    canonical_id: str,
    duplicate_id: str,
) -> PlayerMergePreview:
    """Return a read-only preview of what merge_player_pair would do."""
    preview = PlayerMergePreview(
        canonical_player_id=canonical_id,
        duplicate_player_id=duplicate_id,
    )

    for table, columns in [
        ("plays", ["batter_id", "pitcher_id"]),
        ("spray_charts", ["player_id", "pitcher_id"]),
        ("reconciliation_discrepancies", ["player_id"]),
        ("player_game_batting", ["player_id"]),
        ("player_game_pitching", ["player_id"]),
        ("player_season_batting", ["player_id"]),
        ("player_season_pitching", ["player_id"]),
        ("team_rosters", ["player_id"]),
    ]:
        total = 0
        for col in columns:
            extra_filter = ""
            if table == "reconciliation_discrepancies" and col == "player_id":
                extra_filter = " AND player_id != '__game__'"
            n = db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} = ?{extra_filter}",  # noqa: S608
                (duplicate_id,),
            ).fetchone()[0]
            total += n
        if total:
            preview.table_counts[table] = total

    return preview


# ---------------------------------------------------------------------------
# Merge execution
# ---------------------------------------------------------------------------


class PlayerMergeError(Exception):
    """Raised when a player merge fails."""


def merge_player_pair(
    db: sqlite3.Connection,
    canonical_id: str,
    duplicate_id: str,
    *,
    manage_transaction: bool = True,
) -> set[tuple[str, int, str]]:
    """Atomically merge duplicate_id into canonical_id.

    Follows TN-6 execution order. All FK references are reassigned or
    conflict-deleted, then the duplicate player row is removed.

    Args:
        db: An open sqlite3.Connection with PRAGMA foreign_keys = ON.
        canonical_id: The player_id to keep.
        duplicate_id: The player_id to merge away.
        manage_transaction: If True (CLI use), wraps in BEGIN IMMEDIATE.
            If False (caller manages transaction), uses SAVEPOINT.

    Returns:
        Set of (player_id, team_id, season_id) tuples that need season
        aggregate recomputation.

    Raises:
        PlayerMergeError: If validation fails.
        sqlite3.Error: If any SQL operation fails (triggers rollback).
    """
    # Validation
    if canonical_id == duplicate_id:
        raise PlayerMergeError("canonical_id and duplicate_id must be different")

    canonical_row = db.execute(
        "SELECT player_id, first_name, last_name FROM players WHERE player_id = ?",
        (canonical_id,),
    ).fetchone()
    if canonical_row is None:
        raise PlayerMergeError(f"Canonical player {canonical_id!r} not found")

    duplicate_row = db.execute(
        "SELECT player_id, first_name, last_name FROM players WHERE player_id = ?",
        (duplicate_id,),
    ).fetchone()
    if duplicate_row is None:
        raise PlayerMergeError(f"Duplicate player {duplicate_id!r} not found")

    # Collect affected season tuples BEFORE merge for recomputation
    affected_seasons: set[tuple[str, int, str]] = set()

    # From game-level stats, find all (player_id, team_id, season) combos
    # that will need recomputation. We need to join to games to get season_id.
    for table in ("player_game_batting", "player_game_pitching"):
        rows = db.execute(
            f"SELECT DISTINCT g.season_id, t.team_id "  # noqa: S608
            f"FROM {table} t JOIN games g ON g.game_id = t.game_id "
            f"WHERE t.player_id IN (?, ?)",
            (canonical_id, duplicate_id),
        ).fetchall()
        for season_id, team_id in rows:
            affected_seasons.add((canonical_id, team_id, season_id))

    # Also from season tables directly
    for table in ("player_season_batting", "player_season_pitching"):
        rows = db.execute(
            f"SELECT DISTINCT team_id, season_id FROM {table} "  # noqa: S608
            f"WHERE player_id IN (?, ?)",
            (canonical_id, duplicate_id),
        ).fetchall()
        for team_id, season_id in rows:
            affected_seasons.add((canonical_id, team_id, season_id))

    savepoint_name = "merge_" + canonical_id[:8].replace("-", "_") + "_" + duplicate_id[:8].replace("-", "_")

    if manage_transaction:
        db.execute("BEGIN IMMEDIATE")
    else:
        db.execute(f"SAVEPOINT {savepoint_name}")

    try:
        # AC-6: Ensure canonical has best available name
        from src.db.players import ensure_player_row

        ensure_player_row(db, canonical_id, duplicate_row[1], duplicate_row[2])

        # ---------------------------------------------------------------
        # TN-6 Step 1: plays -- simple UPDATE (no player UNIQUE)
        # ---------------------------------------------------------------
        db.execute(
            "UPDATE plays SET batter_id = ? WHERE batter_id = ?",
            (canonical_id, duplicate_id),
        )
        db.execute(
            "UPDATE plays SET pitcher_id = ? WHERE pitcher_id = ?",
            (canonical_id, duplicate_id),
        )

        # ---------------------------------------------------------------
        # TN-6 Step 2: spray_charts -- simple UPDATE (no player UNIQUE)
        # ---------------------------------------------------------------
        db.execute(
            "UPDATE spray_charts SET player_id = ? WHERE player_id = ?",
            (canonical_id, duplicate_id),
        )
        db.execute(
            "UPDATE spray_charts SET pitcher_id = ? WHERE pitcher_id = ?",
            (canonical_id, duplicate_id),
        )

        # ---------------------------------------------------------------
        # TN-6 Step 3: reconciliation_discrepancies -- delete-or-update
        # Sentinel guard: filter player_id != '__game__'
        # ---------------------------------------------------------------
        _delete_or_update_recon(db, canonical_id, duplicate_id)

        # ---------------------------------------------------------------
        # TN-6 Step 4: player_game_batting -- delete-or-update
        # ---------------------------------------------------------------
        _delete_or_update_game_stats(
            db, "player_game_batting", canonical_id, duplicate_id
        )

        # ---------------------------------------------------------------
        # TN-6 Step 5: player_game_pitching -- delete-or-update
        # ---------------------------------------------------------------
        _delete_or_update_game_stats(
            db, "player_game_pitching", canonical_id, duplicate_id
        )

        # ---------------------------------------------------------------
        # TN-6 Step 6: player_season_batting -- delete boxscore_only (rederived
        # by the recompute) but PRESERVE + re-point member full/supplemented
        # rows (E-237-03 AC-8: member rows are API-authoritative, not
        # rederivable from game rows -- they must survive the merge).
        # ---------------------------------------------------------------
        _delete_or_repoint_season_rows(
            db, "player_season_batting", canonical_id, duplicate_id
        )

        # ---------------------------------------------------------------
        # TN-6 Step 7: player_season_pitching -- same provenance-aware handling.
        # ---------------------------------------------------------------
        _delete_or_repoint_season_rows(
            db, "player_season_pitching", canonical_id, duplicate_id
        )

        # ---------------------------------------------------------------
        # TN-6 Step 8: team_rosters -- delete-or-update
        # ---------------------------------------------------------------
        _delete_or_update_rosters(db, canonical_id, duplicate_id)

        # ---------------------------------------------------------------
        # TN-6 Step 9: DELETE the duplicate player row
        # ---------------------------------------------------------------
        db.execute("DELETE FROM players WHERE player_id = ?", (duplicate_id,))

        if manage_transaction:
            db.execute("COMMIT")
        else:
            db.execute(f"RELEASE {savepoint_name}")

    except Exception:
        if manage_transaction:
            db.execute("ROLLBACK")
        else:
            db.execute(f"ROLLBACK TO {savepoint_name}")
            db.execute(f"RELEASE {savepoint_name}")
        logger.exception(
            "merge_player_pair failed: canonical=%s duplicate=%s",
            canonical_id,
            duplicate_id,
        )
        raise

    logger.info(
        "merge_player_pair complete: duplicate %s merged into canonical %s",
        duplicate_id,
        canonical_id,
    )

    return affected_seasons


def _delete_or_update_game_stats(
    db: sqlite3.Connection,
    table: str,
    canonical_id: str,
    duplicate_id: str,
) -> None:
    """Handle UNIQUE(game_id, player_id, perspective_team_id) conflict.

    E-220 round 6 P1-2: the UNIQUE constraint is 3-column now, so the
    conflict detection JOIN must include ``perspective_team_id``.  Same
    game_id with DIFFERENT perspective_team_id values are legitimately
    distinct rows (one per perspective the game was loaded from) and must
    NOT be collapsed.

    For same-perspective conflicts: keep the row with better
    stat_completeness.  If tied, keep the canonical row.  Delete the loser.
    For non-conflicting rows: UPDATE player_id to canonical.
    """
    # Find conflicting rows within the same perspective.
    conflicts = db.execute(
        f"SELECT d.id, d.game_id, d.stat_completeness, c.id, c.stat_completeness "  # noqa: S608
        f"FROM {table} d "
        f"JOIN {table} c "
        f"    ON c.game_id = d.game_id "
        f"   AND c.perspective_team_id = d.perspective_team_id "
        f"   AND c.player_id = ? "
        f"WHERE d.player_id = ?",
        (canonical_id, duplicate_id),
    ).fetchall()

    for dup_rowid, _game_id, dup_comp, can_rowid, can_comp in conflicts:
        dup_rank = _COMPLETENESS_RANK.get(dup_comp, 0)
        can_rank = _COMPLETENESS_RANK.get(can_comp, 0)

        if dup_rank > can_rank:
            # Duplicate has better completeness -- delete canonical, update duplicate
            db.execute(f"DELETE FROM {table} WHERE id = ?", (can_rowid,))  # noqa: S608
            db.execute(
                f"UPDATE {table} SET player_id = ? WHERE id = ?",  # noqa: S608
                (canonical_id, dup_rowid),
            )
        else:
            # Canonical wins (better or tied) -- delete duplicate
            db.execute(f"DELETE FROM {table} WHERE id = ?", (dup_rowid,))  # noqa: S608

    # Update remaining non-conflicting rows
    db.execute(
        f"UPDATE {table} SET player_id = ? WHERE player_id = ?",  # noqa: S608
        (canonical_id, duplicate_id),
    )


def _delete_or_update_recon(
    db: sqlite3.Connection,
    canonical_id: str,
    duplicate_id: str,
) -> None:
    """Handle reconciliation_discrepancies: delete-or-update with sentinel guard.

    UNIQUE(run_id, game_id, perspective_team_id, team_id, player_id, signal_name).
    The perspective_team_id predicate is required so the self-JOIN only
    identifies true conflicts within the same (perspective, participant)
    tuple -- rows belonging to different perspectives are independent.
    Sentinel guard: only touch rows where player_id != '__game__'.
    """
    # Find conflicts
    conflicts = db.execute(
        """
        SELECT d.id FROM reconciliation_discrepancies d
        JOIN reconciliation_discrepancies c
            ON  c.run_id = d.run_id
            AND c.game_id = d.game_id
            AND c.perspective_team_id = d.perspective_team_id
            AND c.team_id = d.team_id
            AND c.signal_name = d.signal_name
            AND c.player_id = ?
        WHERE d.player_id = ?
          AND d.player_id != '__game__'
        """,
        (canonical_id, duplicate_id),
    ).fetchall()

    for (dup_rowid,) in conflicts:
        db.execute("DELETE FROM reconciliation_discrepancies WHERE id = ?", (dup_rowid,))

    # Update remaining
    db.execute(
        """
        UPDATE reconciliation_discrepancies
        SET player_id = ?
        WHERE player_id = ? AND player_id != '__game__'
        """,
        (canonical_id, duplicate_id),
    )


def _delete_or_update_rosters(
    db: sqlite3.Connection,
    canonical_id: str,
    duplicate_id: str,
) -> None:
    """Handle team_rosters: PK(team_id, player_id, season_id).

    If canonical already has a roster entry for the same (team_id, season_id),
    delete the duplicate's row. Otherwise, update player_id to canonical.
    """
    conflicts = db.execute(
        """
        SELECT d.team_id, d.season_id FROM team_rosters d
        JOIN team_rosters c
            ON  c.team_id = d.team_id
            AND c.season_id = d.season_id
            AND c.player_id = ?
        WHERE d.player_id = ?
        """,
        (canonical_id, duplicate_id),
    ).fetchall()

    for team_id, season_id in conflicts:
        db.execute(
            "DELETE FROM team_rosters WHERE team_id = ? AND player_id = ? AND season_id = ?",
            (team_id, duplicate_id, season_id),
        )

    # Update remaining
    db.execute(
        "UPDATE team_rosters SET player_id = ? WHERE player_id = ?",
        (canonical_id, duplicate_id),
    )


def _delete_or_repoint_season_rows(
    db: sqlite3.Connection,
    table: str,
    canonical_id: str,
    duplicate_id: str,
) -> None:
    """Merge season-aggregate rows from a duplicate into the canonical player.

    Provenance-aware (E-237-03 AC-8 -- closes the merge-path re-opening of the
    member data-loss bug that the canonical recompute's NOT EXISTS guard closes
    for non-merged players):

    * ``boxscore_only`` rows are derivable from the per-game rows by the
      canonical recompute that runs after the merge, so they are DELETED for
      BOTH players here and rebuilt under the canonical id later.
    * ``full`` / ``supplemented`` rows are member-authoritative -- they come
      straight from the season-stats API and are NOT rederivable from game
      rows.  They must MOVE to the canonical id, never be deleted or downgraded
      to a boxscore sum.

    Collision (PK ``UNIQUE(player_id, team_id, season_id)``): if the canonical
    player ALSO owns a member row for the SAME ``(team_id, season_id)`` as a
    duplicate member row, re-pointing the duplicate's would violate the unique
    constraint.  Resolution is deterministic -- the canonical's row WINS (the
    duplicate's member row is dropped) -- matching the canonical-preference
    convention used elsewhere in the merge (``_delete_or_update_*``).  Both
    rows are member-authoritative for the same scope, so keeping one is correct
    and keeping the canonical's is the consistent choice.
    """
    # boxscore_only rows: drop for both players; the post-merge canonical
    # recompute rebuilds them under the canonical id from the per-game rows.
    db.execute(
        f"DELETE FROM {table} "  # noqa: S608
        f"WHERE player_id IN (?, ?) AND stat_completeness = 'boxscore_only'",
        (canonical_id, duplicate_id),
    )

    # Collision resolution: drop the duplicate's member rows whose
    # (team_id, season_id) the canonical already owns a (member) row for.
    conflicts = db.execute(
        f"SELECT d.team_id, d.season_id FROM {table} d "  # noqa: S608
        f"JOIN {table} c "
        f"  ON  c.team_id = d.team_id "
        f"  AND c.season_id = d.season_id "
        f"  AND c.player_id = ? "
        f"WHERE d.player_id = ?",
        (canonical_id, duplicate_id),
    ).fetchall()
    for team_id, season_id in conflicts:
        db.execute(
            f"DELETE FROM {table} "  # noqa: S608
            f"WHERE player_id = ? AND team_id = ? AND season_id = ?",
            (duplicate_id, team_id, season_id),
        )

    # Re-point the remaining (non-colliding) duplicate member rows to canonical.
    db.execute(
        f"UPDATE {table} SET player_id = ? WHERE player_id = ?",  # noqa: S608
        (canonical_id, duplicate_id),
    )


# ---------------------------------------------------------------------------
# Season aggregate recomputation (TN-5)
# ---------------------------------------------------------------------------


def dedup_team_players(
    db: sqlite3.Connection,
    team_id: int,
    season_id: str,
    *,
    manage_transaction: bool = True,
    recompute_aggregates: bool = True,
) -> int:
    """Detect and merge same-team duplicate players for one (team, season).

    Calls ``find_duplicate_players()`` scoped to the given team and season,
    then ``merge_player_pair()`` for each detected pair.  Recomputes season
    aggregates for any affected (player, team, season) tuples.

    Errors on individual pairs are logged and skipped -- partial dedup is
    acceptable (AC-7).

    Args:
        db: An open sqlite3.Connection with PRAGMA foreign_keys = ON.
        team_id: INTEGER PK of the team to dedup.
        season_id: Season slug to scope the detection query.
        manage_transaction: Passed through to ``merge_player_pair()``.
            Use ``False`` when the caller already has an open transaction
            (Hook 1 inside ScoutingLoader), ``True`` when the caller owns
            the connection (Hook 2 in orchestrators).
        recompute_aggregates: When ``True`` (default -- the standalone
            ``bb data dedup-players`` CLI caller), recompute season aggregates for the
            affected scopes after merging.  The two embedded load-path dedup
            calls (ScoutingLoader Hook 1) pass ``False`` because the canonical
            recompute runs once at end-of-load -- suppressing the redundant
            in-dedup recompute (E-237-03, TN-11).  This is deliberately a
            separate flag from ``manage_transaction``: transaction-ownership is
            not the same concern as recompute-ownership.

    Returns:
        Number of pairs successfully merged.
    """
    pairs = find_duplicate_players(db, team_id=team_id, season_id=season_id)

    if not pairs:
        logger.info(
            "dedup_team_players: 0 duplicates found for team_id=%d season=%s",
            team_id,
            season_id,
        )
        return 0

    merged = 0
    all_affected: set[tuple[str, int, str]] = set()

    for pair in pairs:
        try:
            affected = merge_player_pair(
                db,
                pair.canonical_player_id,
                pair.duplicate_player_id,
                manage_transaction=manage_transaction,
            )
            all_affected.update(affected)
            merged += 1
            logger.info(
                "dedup_team_players: merged %s into %s (team_id=%d season=%s)",
                pair.duplicate_player_id,
                pair.canonical_player_id,
                team_id,
                season_id,
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "dedup_team_players: failed to merge %s into %s (team_id=%d); "
                "continuing with remaining pairs",
                pair.duplicate_player_id,
                pair.canonical_player_id,
                team_id,
                exc_info=True,
            )

    # Recompute season aggregates for all affected tuples (unless suppressed
    # because a canonical end-of-load recompute will run -- TN-11).
    if all_affected and recompute_aggregates:
        recompute_affected_seasons(db, all_affected)

    logger.info(
        "dedup_team_players: %d pair(s) merged for team_id=%d season=%s",
        merged,
        team_id,
        season_id,
    )
    return merged


def recompute_affected_seasons(
    db: sqlite3.Connection,
    affected: set[tuple[str, int, str]],
) -> None:
    """Recompute season aggregates for the scopes touched by a set of merges.

    E-237-03 (TN-11): the per-player ``recompute_season_batting`` /
    ``recompute_season_pitching`` writers have been consolidated away into the
    single canonical recompute in ``src.db.season_aggregates``.  This function
    keeps its signature for the standalone ``bb data dedup-players``
    CLI caller but now reduces the
    affected ``(player_id, team_id, season_id)`` tuples to their distinct
    ``(team_id, season_id)`` scopes and runs the scope-level canonical
    recompute once per scope.  Slightly broader than the prior per-player
    recompute (it rebuilds every boxscore_only player in the scope), but
    idempotent and beneficial -- the merged and non-merged players in a scope
    now get the identical deterministic superset column set.
    """
    from src.db.season_aggregates import canonical_recompute

    scopes = {(team_id, season_id) for _player_id, team_id, season_id in affected}
    for team_id, season_id in scopes:
        canonical_recompute(db, team_id, season_id)
