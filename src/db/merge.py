"""Team merge logic.

Provides ``merge_teams()`` and ``preview_merge()`` for combining duplicate
team records into a single canonical record.

The merge is fully atomic: all FK reassignments, conflict deletions, and the
final duplicate deletion execute in a single ``BEGIN IMMEDIATE`` transaction.
If any step raises, the transaction is rolled back and the database is
unchanged.

Canonical wins rule: when both teams have rows for the same UNIQUE-constrained
slot, the canonical team's row is kept and the duplicate's conflicting row is
deleted.  Stats are never summed or merged.

Identifier gap-filling (TN-6): if the canonical team has a NULL ``gc_uuid`` or
``public_id`` and the duplicate has a non-null value, the canonical team
inherits the duplicate's value.  If both are non-null and different, the
canonical team wins and the mismatch is surfaced as a warning in the preview.

Self-referencing rows in ``opponent_links`` and ``team_opponents`` that would
link a team to itself after FK reassignment are auto-deleted during the
conflict-resolution step rather than blocking the merge.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Duplicate detection result dataclass
# ---------------------------------------------------------------------------


@dataclass
class DuplicateTeam:
    """A team record within a duplicate group.

    Attributes:
        id: Primary key from teams.id.
        name: Team name as stored in the database.
        season_year: Season year (may be None).
        gc_uuid: GameChanger UUID, or None if unset.
        public_id: GameChanger public slug, or None if unset.
        game_count: Number of games where this team appears as home or away.
        has_stats: True if the team has any rows in player_season_batting,
            player_season_pitching, or scouting_runs.
    """

    id: int
    name: str
    season_year: int | None
    gc_uuid: str | None
    public_id: str | None
    game_count: int
    has_stats: bool


# ---------------------------------------------------------------------------
# Preview result dataclass
# ---------------------------------------------------------------------------


@dataclass
class MergePreview:
    """Structured summary of what a merge will do.

    Attributes:
        blocking_issues: Non-empty list means the merge cannot proceed.
        conflict_counts: Per-table count of duplicate rows that will be deleted.
        reassignment_counts: Per-table count of rows that will be re-pointed to canonical.
        canonical_gc_uuid: Current gc_uuid of the canonical team.
        canonical_public_id: Current public_id of the canonical team.
        duplicate_gc_uuid: Current gc_uuid of the duplicate team.
        duplicate_public_id: Current public_id of the duplicate team.
        duplicate_is_member: True if the duplicate has membership_type='member'.
        games_between_teams: Count of games where one team is canonical and the
            other is duplicate (signal they may NOT be the same team).
        self_ref_deletions: Count of self-referencing rows that will be
            auto-deleted from opponent_links and team_opponents.
        duplicate_has_our_team_entries: True if the duplicate appears as
            our_team_id in opponent_links (signals it was treated as a member team).
    """

    blocking_issues: list[str] = field(default_factory=list)
    conflict_counts: dict[str, int] = field(default_factory=dict)
    reassignment_counts: dict[str, int] = field(default_factory=dict)
    canonical_gc_uuid: str | None = None
    canonical_public_id: str | None = None
    duplicate_gc_uuid: str | None = None
    duplicate_public_id: str | None = None
    duplicate_is_member: bool = False
    games_between_teams: int = 0
    self_ref_deletions: int = 0
    duplicate_has_our_team_entries: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_team(db: sqlite3.Connection, team_id: int) -> dict | None:
    """Return a row dict for teams.id = team_id, or None if not found."""
    row = db.execute(
        "SELECT id, name, membership_type, gc_uuid, public_id"
        " FROM teams WHERE id = ?",
        (team_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "membership_type": row[2],
        "gc_uuid": row[3],
        "public_id": row[4],
    }


def _run_blocking_checks(
    canonical_id: int,
    duplicate_id: int,
    db: sqlite3.Connection,
) -> tuple[dict, dict]:
    """Run all blocking pre-merge validation checks.

    Returns:
        (canonical_row, duplicate_row) dicts if all checks pass.

    Raises:
        MergeBlockedError: if any blocking check fails.
    """
    canonical = _fetch_team(db, canonical_id)
    if canonical is None:
        raise MergeBlockedError(f"Canonical team id={canonical_id} does not exist")

    duplicate = _fetch_team(db, duplicate_id)
    if duplicate is None:
        raise MergeBlockedError(f"Duplicate team id={duplicate_id} does not exist")

    if canonical_id == duplicate_id:
        raise MergeBlockedError("canonical_id and duplicate_id must be different")

    if duplicate["membership_type"] == "member":
        raise MergeBlockedError(
            f"Duplicate team id={duplicate_id} has membership_type='member';"
            " merging member teams is not allowed. Re-classify the duplicate as"
            " 'tracked' first, or swap the canonical/duplicate roles."
        )

    return canonical, duplicate


def _count_self_refs(
    canonical_id: int,
    duplicate_id: int,
    db: sqlite3.Connection,
) -> int:
    """Count self-referencing rows in opponent_links and team_opponents."""
    # opponent_links: rows that would link canonical to itself after reassignment.
    # Three cases: cross-pair directions A and B, plus same-column (dup, dup).
    ol_count = db.execute(
        """
        SELECT COUNT(*) FROM opponent_links
        WHERE (resolved_team_id = ? AND our_team_id = ?)
           OR (our_team_id = ? AND resolved_team_id = ?)
           OR (our_team_id = ? AND resolved_team_id = ?)
        """,
        (duplicate_id, canonical_id, duplicate_id, canonical_id, duplicate_id, duplicate_id),
    ).fetchone()[0]

    # team_opponents: rows that would link canonical to itself after reassignment.
    # Three cases: cross-pair directions A and B, plus same-column (dup, dup).
    to_count = db.execute(
        """
        SELECT COUNT(*) FROM team_opponents
        WHERE (opponent_team_id = ? AND our_team_id = ?)
           OR (our_team_id = ? AND opponent_team_id = ?)
           OR (our_team_id = ? AND opponent_team_id = ?)
        """,
        (duplicate_id, canonical_id, duplicate_id, canonical_id, duplicate_id, duplicate_id),
    ).fetchone()[0]

    return ol_count + to_count


def _count_conflicts(
    canonical_id: int,
    duplicate_id: int,
    db: sqlite3.Connection,
) -> dict[str, int]:
    """Count per-table conflicting rows that will be deleted (canonical wins)."""
    conflicts: dict[str, int] = {}

    # team_opponents: UNIQUE(our_team_id, opponent_team_id)
    # Conflicts: duplicate's rows where (canonical_id, opponent_team_id) or
    # (our_team_id, canonical_id) already exist for canonical.
    # Also count the self-referencing rows being deleted.
    # We'll just count all rows from duplicate that conflict with canonical.
    to_conflict = db.execute(
        """
        SELECT COUNT(*) FROM team_opponents t_dup
        WHERE (t_dup.our_team_id = ? AND EXISTS (
                SELECT 1 FROM team_opponents t_can
                WHERE t_can.our_team_id = ? AND t_can.opponent_team_id = t_dup.opponent_team_id
              ))
           OR (t_dup.opponent_team_id = ? AND EXISTS (
                SELECT 1 FROM team_opponents t_can
                WHERE t_can.opponent_team_id = ? AND t_can.our_team_id = t_dup.our_team_id
              ))
           OR (t_dup.our_team_id = ? AND t_dup.opponent_team_id = ?)
           OR (t_dup.opponent_team_id = ? AND t_dup.our_team_id = ?)
        """,
        (duplicate_id, canonical_id, duplicate_id, canonical_id,
         duplicate_id, canonical_id, duplicate_id, canonical_id),
    ).fetchone()[0]
    if to_conflict:
        conflicts["team_opponents"] = to_conflict

    # team_rosters: PK(team_id, player_id, season_id)
    tr_conflict = db.execute(
        """
        SELECT COUNT(*) FROM team_rosters t_dup
        WHERE t_dup.team_id = ?
          AND EXISTS (
            SELECT 1 FROM team_rosters t_can
            WHERE t_can.team_id = ? AND t_can.player_id = t_dup.player_id
              AND t_can.season_id = t_dup.season_id
          )
        """,
        (duplicate_id, canonical_id),
    ).fetchone()[0]
    if tr_conflict:
        conflicts["team_rosters"] = tr_conflict

    # player_season_batting: UNIQUE(player_id, team_id, season_id)
    psb_conflict = db.execute(
        """
        SELECT COUNT(*) FROM player_season_batting t_dup
        WHERE t_dup.team_id = ?
          AND EXISTS (
            SELECT 1 FROM player_season_batting t_can
            WHERE t_can.team_id = ? AND t_can.player_id = t_dup.player_id
              AND t_can.season_id = t_dup.season_id
          )
        """,
        (duplicate_id, canonical_id),
    ).fetchone()[0]
    if psb_conflict:
        conflicts["player_season_batting"] = psb_conflict

    # player_season_pitching: UNIQUE(player_id, team_id, season_id)
    psp_conflict = db.execute(
        """
        SELECT COUNT(*) FROM player_season_pitching t_dup
        WHERE t_dup.team_id = ?
          AND EXISTS (
            SELECT 1 FROM player_season_pitching t_can
            WHERE t_can.team_id = ? AND t_can.player_id = t_dup.player_id
              AND t_can.season_id = t_dup.season_id
          )
        """,
        (duplicate_id, canonical_id),
    ).fetchone()[0]
    if psp_conflict:
        conflicts["player_season_pitching"] = psp_conflict

    # opponent_links: UNIQUE(our_team_id, root_team_id)
    # Also auto-deletes self-referencing rows.
    ol_conflict = db.execute(
        """
        SELECT COUNT(*) FROM opponent_links t_dup
        WHERE (t_dup.our_team_id = ? AND EXISTS (
                SELECT 1 FROM opponent_links t_can
                WHERE t_can.our_team_id = ? AND t_can.root_team_id = t_dup.root_team_id
              ))
           OR (t_dup.resolved_team_id = ? AND t_dup.our_team_id = ?)
           OR (t_dup.our_team_id = ? AND t_dup.resolved_team_id = ?)
        """,
        (duplicate_id, canonical_id, duplicate_id, canonical_id,
         duplicate_id, canonical_id),
    ).fetchone()[0]
    if ol_conflict:
        conflicts["opponent_links"] = ol_conflict

    # scouting_runs: UNIQUE(team_id, season_id, run_type)
    sr_conflict = db.execute(
        """
        SELECT COUNT(*) FROM scouting_runs t_dup
        WHERE t_dup.team_id = ?
          AND EXISTS (
            SELECT 1 FROM scouting_runs t_can
            WHERE t_can.team_id = ? AND t_can.season_id = t_dup.season_id
              AND t_can.run_type = t_dup.run_type
          )
        """,
        (duplicate_id, canonical_id),
    ).fetchone()[0]
    if sr_conflict:
        conflicts["scouting_runs"] = sr_conflict

    # user_team_access: UNIQUE(user_id, team_id)
    uta_conflict = db.execute(
        """
        SELECT COUNT(*) FROM user_team_access t_dup
        WHERE t_dup.team_id = ?
          AND EXISTS (
            SELECT 1 FROM user_team_access t_can
            WHERE t_can.team_id = ? AND t_can.user_id = t_dup.user_id
          )
        """,
        (duplicate_id, canonical_id),
    ).fetchone()[0]
    if uta_conflict:
        conflicts["user_team_access"] = uta_conflict

    # coaching_assignments: UNIQUE(user_id, team_id)
    ca_conflict = db.execute(
        """
        SELECT COUNT(*) FROM coaching_assignments t_dup
        WHERE t_dup.team_id = ?
          AND EXISTS (
            SELECT 1 FROM coaching_assignments t_can
            WHERE t_can.team_id = ? AND t_can.user_id = t_dup.user_id
          )
        """,
        (duplicate_id, canonical_id),
    ).fetchone()[0]
    if ca_conflict:
        conflicts["coaching_assignments"] = ca_conflict

    return conflicts


def _count_reassignments(
    canonical_id: int,
    duplicate_id: int,
    db: sqlite3.Connection,
) -> dict[str, int]:
    """Count per-table rows that will be reassigned from duplicate to canonical."""
    reassignments: dict[str, int] = {}

    def _count(table: str, *columns: str) -> int:
        total = 0
        for col in columns:
            n = db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} = ?",  # noqa: S608
                (duplicate_id,),
            ).fetchone()[0]
            total += n
        return total

    for table, cols in [
        ("team_opponents", ("our_team_id", "opponent_team_id")),
        ("team_rosters", ("team_id",)),
        ("games", ("home_team_id", "away_team_id")),
        ("player_game_batting", ("team_id",)),
        ("player_game_pitching", ("team_id",)),
        ("player_season_batting", ("team_id",)),
        ("player_season_pitching", ("team_id",)),
        ("spray_charts", ("team_id",)),
        ("opponent_links", ("our_team_id", "resolved_team_id")),
        ("scouting_runs", ("team_id",)),
        ("user_team_access", ("team_id",)),
        ("coaching_assignments", ("team_id",)),
        ("crawl_jobs", ("team_id",)),
    ]:
        n = _count(table, *cols)
        if n:
            reassignments[table] = n

    return reassignments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class MergeBlockedError(Exception):
    """Raised when a blocking pre-merge check fails."""


def preview_merge(
    canonical_id: int,
    duplicate_id: int,
    db: sqlite3.Connection,
) -> MergePreview:
    """Return a structured summary of what merge_teams would do.

    This function is read-only -- it does not modify any data.

    Args:
        canonical_id: The team id that will be kept.
        duplicate_id: The team id that will be deleted.
        db: An open sqlite3.Connection.

    Returns:
        MergePreview dataclass with blocking issues, conflict counts,
        reassignment counts, identifier comparison, and warning signals.
    """
    preview = MergePreview()

    canonical = _fetch_team(db, canonical_id)
    if canonical is None:
        preview.blocking_issues.append(
            f"Canonical team id={canonical_id} does not exist"
        )

    duplicate = _fetch_team(db, duplicate_id)
    if duplicate is None:
        preview.blocking_issues.append(
            f"Duplicate team id={duplicate_id} does not exist"
        )

    if canonical_id == duplicate_id:
        preview.blocking_issues.append("canonical_id and duplicate_id must be different")

    # If either team is missing, can't compute further details
    if preview.blocking_issues:
        return preview

    assert canonical is not None
    assert duplicate is not None

    # Member-team guard
    if duplicate["membership_type"] == "member":
        preview.blocking_issues.append(
            f"Duplicate team id={duplicate_id} has membership_type='member';"
            " merging member teams is not allowed"
        )

    # Populate identifier fields
    preview.canonical_gc_uuid = canonical["gc_uuid"]
    preview.canonical_public_id = canonical["public_id"]
    preview.duplicate_gc_uuid = duplicate["gc_uuid"]
    preview.duplicate_public_id = duplicate["public_id"]
    preview.duplicate_is_member = duplicate["membership_type"] == "member"

    # Games between the two teams (warning: may signal they're NOT duplicates)
    games_between = db.execute(
        """
        SELECT COUNT(*) FROM games
        WHERE (home_team_id = ? AND away_team_id = ?)
           OR (home_team_id = ? AND away_team_id = ?)
        """,
        (canonical_id, duplicate_id, duplicate_id, canonical_id),
    ).fetchone()[0]
    preview.games_between_teams = games_between

    # Self-referencing rows that will be auto-deleted
    preview.self_ref_deletions = _count_self_refs(canonical_id, duplicate_id, db)

    # Duplicate has our_team_id entries in opponent_links
    dup_our_team_count = db.execute(
        "SELECT COUNT(*) FROM opponent_links WHERE our_team_id = ?",
        (duplicate_id,),
    ).fetchone()[0]
    preview.duplicate_has_our_team_entries = dup_our_team_count > 0

    # Conflict counts and reassignment counts (only valid if no blocking issues)
    if not preview.blocking_issues:
        preview.conflict_counts = _count_conflicts(canonical_id, duplicate_id, db)
        preview.reassignment_counts = _count_reassignments(canonical_id, duplicate_id, db)

    return preview


def merge_teams(
    canonical_id: int,
    duplicate_id: int,
    db: sqlite3.Connection,
) -> None:
    """Atomically merge duplicate_id into canonical_id.

    All FK references to duplicate_id are reassigned to canonical_id.
    Conflicting rows (where canonical already has a matching row for a
    UNIQUE constraint) are deleted (canonical wins).  Self-referencing rows
    in opponent_links and team_opponents are auto-deleted.  The duplicate
    team row is deleted at the end.

    Identifier gap-filling: canonical's NULL gc_uuid / public_id values are
    filled from the duplicate's non-null values.  Mismatched non-null values
    are left unchanged (canonical wins).

    The entire operation executes inside a single ``BEGIN IMMEDIATE``
    transaction.  On any exception the transaction is rolled back and the
    database is unchanged.

    Args:
        canonical_id: The team id to keep.
        duplicate_id: The team id to delete (after reassigning its data).
        db: An open sqlite3.Connection. ``PRAGMA foreign_keys = ON`` is
            set at connection creation time (SQLite ignores PRAGMA changes
            inside an active transaction).

    Raises:
        MergeBlockedError: If any blocking pre-merge check fails.
        sqlite3.Error: If any SQL operation fails (triggers rollback).
    """
    # Run blocking checks before opening the transaction
    canonical, duplicate = _run_blocking_checks(canonical_id, duplicate_id, db)

    dup_gc_uuid = duplicate["gc_uuid"]
    dup_public_id = duplicate["public_id"]

    logger.info(
        "merge_teams: canonical=%d (%s) <- duplicate=%d (%s)",
        canonical_id,
        canonical["name"],
        duplicate_id,
        duplicate["name"],
    )

    in_transaction = False
    try:
        db.execute("BEGIN IMMEDIATE")
        in_transaction = True
        db.execute("PRAGMA foreign_keys = ON")

        # ---------------------------------------------------------------
        # Step 1: Clear duplicate's identifiers (required before gap-fill
        # to avoid partial unique index violations).
        # ---------------------------------------------------------------
        db.execute(
            "UPDATE teams SET gc_uuid = NULL, public_id = NULL WHERE id = ?",
            (duplicate_id,),
        )

        # ---------------------------------------------------------------
        # Step 2: Gap-fill canonical's identifiers from duplicate.
        # COALESCE(canonical_value, dup_value) = canonical wins if set.
        # ---------------------------------------------------------------
        db.execute(
            "UPDATE teams SET gc_uuid = COALESCE(gc_uuid, ?), public_id = COALESCE(public_id, ?) WHERE id = ?",
            (dup_gc_uuid, dup_public_id, canonical_id),
        )

        # ---------------------------------------------------------------
        # Step 3: Delete conflicting rows (canonical wins)
        # ---------------------------------------------------------------

        # team_opponents: UNIQUE(our_team_id, opponent_team_id), CHECK(our != opponent)
        # (a) Self-referencing rows: after reassignment would link canonical to itself.
        # Three cases: cross-pair A, cross-pair B, same-column (dup, dup).
        db.execute(
            """
            DELETE FROM team_opponents
            WHERE (our_team_id = ? AND opponent_team_id = ?)
               OR (our_team_id = ? AND opponent_team_id = ?)
               OR (our_team_id = ? AND opponent_team_id = ?)
            """,
            (duplicate_id, canonical_id, canonical_id, duplicate_id, duplicate_id, duplicate_id),
        )
        # (b) Rows where canonical already has the same (our_team_id, opponent_team_id) pair
        db.execute(
            """
            DELETE FROM team_opponents
            WHERE our_team_id = ?
              AND EXISTS (
                SELECT 1 FROM team_opponents AS t2
                WHERE t2.our_team_id = ? AND t2.opponent_team_id = team_opponents.opponent_team_id
              )
            """,
            (duplicate_id, canonical_id),
        )
        db.execute(
            """
            DELETE FROM team_opponents
            WHERE opponent_team_id = ?
              AND EXISTS (
                SELECT 1 FROM team_opponents AS t2
                WHERE t2.opponent_team_id = ? AND t2.our_team_id = team_opponents.our_team_id
              )
            """,
            (duplicate_id, canonical_id),
        )

        # team_rosters: PK(team_id, player_id, season_id)
        db.execute(
            """
            DELETE FROM team_rosters
            WHERE team_id = ?
              AND EXISTS (
                SELECT 1 FROM team_rosters AS tr2
                WHERE tr2.team_id = ? AND tr2.player_id = team_rosters.player_id
                  AND tr2.season_id = team_rosters.season_id
              )
            """,
            (duplicate_id, canonical_id),
        )

        # player_season_batting: UNIQUE(player_id, team_id, season_id)
        db.execute(
            """
            DELETE FROM player_season_batting
            WHERE team_id = ?
              AND EXISTS (
                SELECT 1 FROM player_season_batting AS psb2
                WHERE psb2.team_id = ? AND psb2.player_id = player_season_batting.player_id
                  AND psb2.season_id = player_season_batting.season_id
              )
            """,
            (duplicate_id, canonical_id),
        )

        # player_season_pitching: UNIQUE(player_id, team_id, season_id)
        db.execute(
            """
            DELETE FROM player_season_pitching
            WHERE team_id = ?
              AND EXISTS (
                SELECT 1 FROM player_season_pitching AS psp2
                WHERE psp2.team_id = ? AND psp2.player_id = player_season_pitching.player_id
                  AND psp2.season_id = player_season_pitching.season_id
              )
            """,
            (duplicate_id, canonical_id),
        )

        # opponent_links: UNIQUE(our_team_id, root_team_id)
        # (a) Self-referencing rows: cross-pair directions A and B, plus same-column (dup, dup).
        db.execute(
            """
            DELETE FROM opponent_links
            WHERE (resolved_team_id = ? AND our_team_id = ?)
               OR (our_team_id = ? AND resolved_team_id = ?)
               OR (our_team_id = ? AND resolved_team_id = ?)
            """,
            (duplicate_id, canonical_id, duplicate_id, canonical_id, duplicate_id, duplicate_id),
        )
        # (b) Rows where canonical already has the same (our_team_id, root_team_id) pair
        db.execute(
            """
            DELETE FROM opponent_links
            WHERE our_team_id = ?
              AND EXISTS (
                SELECT 1 FROM opponent_links AS ol2
                WHERE ol2.our_team_id = ? AND ol2.root_team_id = opponent_links.root_team_id
              )
            """,
            (duplicate_id, canonical_id),
        )

        # scouting_runs: UNIQUE(team_id, season_id, run_type)
        db.execute(
            """
            DELETE FROM scouting_runs
            WHERE team_id = ?
              AND EXISTS (
                SELECT 1 FROM scouting_runs AS sr2
                WHERE sr2.team_id = ? AND sr2.season_id = scouting_runs.season_id
                  AND sr2.run_type = scouting_runs.run_type
              )
            """,
            (duplicate_id, canonical_id),
        )

        # user_team_access: UNIQUE(user_id, team_id)
        db.execute(
            """
            DELETE FROM user_team_access
            WHERE team_id = ?
              AND EXISTS (
                SELECT 1 FROM user_team_access AS uta2
                WHERE uta2.team_id = ? AND uta2.user_id = user_team_access.user_id
              )
            """,
            (duplicate_id, canonical_id),
        )

        # coaching_assignments: UNIQUE(user_id, team_id)
        db.execute(
            """
            DELETE FROM coaching_assignments
            WHERE team_id = ?
              AND EXISTS (
                SELECT 1 FROM coaching_assignments AS ca2
                WHERE ca2.team_id = ? AND ca2.user_id = coaching_assignments.user_id
              )
            """,
            (duplicate_id, canonical_id),
        )

        # ---------------------------------------------------------------
        # Step 4: Reassign all FK references from duplicate to canonical
        # ---------------------------------------------------------------

        # team_opponents: both FK columns
        db.execute(
            "UPDATE team_opponents SET our_team_id = ? WHERE our_team_id = ?",
            (canonical_id, duplicate_id),
        )
        db.execute(
            "UPDATE team_opponents SET opponent_team_id = ? WHERE opponent_team_id = ?",
            (canonical_id, duplicate_id),
        )

        # team_rosters
        db.execute(
            "UPDATE team_rosters SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # games: both FK columns
        db.execute(
            "UPDATE games SET home_team_id = ? WHERE home_team_id = ?",
            (canonical_id, duplicate_id),
        )
        db.execute(
            "UPDATE games SET away_team_id = ? WHERE away_team_id = ?",
            (canonical_id, duplicate_id),
        )

        # player_game_batting
        db.execute(
            "UPDATE player_game_batting SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # player_game_pitching
        db.execute(
            "UPDATE player_game_pitching SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # player_season_batting
        db.execute(
            "UPDATE player_season_batting SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # player_season_pitching
        db.execute(
            "UPDATE player_season_pitching SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # spray_charts
        db.execute(
            "UPDATE spray_charts SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # opponent_links: both FK columns
        db.execute(
            "UPDATE opponent_links SET our_team_id = ? WHERE our_team_id = ?",
            (canonical_id, duplicate_id),
        )
        db.execute(
            "UPDATE opponent_links SET resolved_team_id = ? WHERE resolved_team_id = ?",
            (canonical_id, duplicate_id),
        )

        # scouting_runs
        db.execute(
            "UPDATE scouting_runs SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # user_team_access
        db.execute(
            "UPDATE user_team_access SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # coaching_assignments
        db.execute(
            "UPDATE coaching_assignments SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # crawl_jobs
        db.execute(
            "UPDATE crawl_jobs SET team_id = ? WHERE team_id = ?",
            (canonical_id, duplicate_id),
        )

        # ---------------------------------------------------------------
        # Step 5: Delete the duplicate team
        # ---------------------------------------------------------------
        db.execute("DELETE FROM teams WHERE id = ?", (duplicate_id,))

        db.execute("COMMIT")
        in_transaction = False

    except Exception:  # noqa: BLE001
        if in_transaction:
            db.execute("ROLLBACK")
        logger.exception(
            "merge_teams failed; transaction rolled back. canonical=%d duplicate=%d",
            canonical_id,
            duplicate_id,
        )
        raise

    logger.info(
        "merge_teams complete: duplicate team id=%d deleted, data reassigned to id=%d",
        duplicate_id,
        canonical_id,
    )


def find_duplicate_teams(db: sqlite3.Connection) -> list[list[DuplicateTeam]]:
    """Return groups of tracked teams that are likely duplicates.

    Two-pass detection:

    **Pass 1 -- Exact matches**: Teams with the same name (case-insensitive)
    AND the same ``season_year`` value (including both NULL).

    **Pass 2 -- Cross matches**: Teams with the same name where one has
    ``season_year IS NULL`` and the other has a non-NULL value.  Teams already
    appearing in a pass-1 group are excluded (non-overlap guarantee).

    Only ``membership_type = 'tracked'`` teams are considered.  Member teams are
    excluded.

    Each team in a group includes ``game_count`` (appearances as home or away
    team) and ``has_stats`` (True when any row exists in player_season_batting,
    player_season_pitching, or scouting_runs) to help identify the canonical.

    Args:
        db: An open sqlite3.Connection.

    Returns:
        A list of duplicate groups.  Exact-match groups come first, then
        cross-match groups.  Returns an empty list when no duplicates exist.
    """
    # ------------------------------------------------------------------
    # Pass 1: Exact season_year matches (including both-NULL)
    # ------------------------------------------------------------------
    exact_rows = db.execute(
        """
        WITH dup_groups AS (
            SELECT
                name COLLATE NOCASE        AS norm_name,
                COALESCE(season_year, -1)  AS sy_key
            FROM teams
            WHERE membership_type = 'tracked'
            GROUP BY name COLLATE NOCASE, COALESCE(season_year, -1)
            HAVING COUNT(*) >= 2
        )
        SELECT
            t.id,
            t.name,
            t.season_year,
            t.gc_uuid,
            t.public_id,
            (
                SELECT COUNT(*) FROM games g
                WHERE g.home_team_id = t.id OR g.away_team_id = t.id
            ) AS game_count,
            CASE WHEN (
                EXISTS (SELECT 1 FROM player_season_batting  WHERE team_id = t.id)
                OR EXISTS (SELECT 1 FROM player_season_pitching WHERE team_id = t.id)
                OR EXISTS (SELECT 1 FROM scouting_runs        WHERE team_id = t.id)
            ) THEN 1 ELSE 0 END AS has_stats
        FROM teams t
        JOIN dup_groups dg
            ON  t.name = dg.norm_name COLLATE NOCASE
            AND COALESCE(t.season_year, -1) = dg.sy_key
        WHERE t.membership_type = 'tracked'
        ORDER BY t.name COLLATE NOCASE, COALESCE(t.season_year, -1), t.id
        """
    ).fetchall()

    exact_groups: dict[tuple[str, int], list[DuplicateTeam]] = {}
    exact_team_ids: set[int] = set()
    for row in exact_rows:
        team = _row_to_duplicate_team(row)
        key = (team.name.lower(), team.season_year if team.season_year is not None else -1)
        exact_groups.setdefault(key, []).append(team)
        exact_team_ids.add(team.id)

    # ------------------------------------------------------------------
    # Pass 2: NULL-vs-non-NULL season_year cross-matches
    # ------------------------------------------------------------------
    # Cross-match candidates: only teams with season_year IS NULL that share a
    # name with at least one non-NULL team, PLUS the non-NULL counterpart(s).
    # Rows with two different non-NULL season_years are NOT cross-matched --
    # only NULL-vs-non-NULL pairs qualify.
    cross_rows = db.execute(
        """
        SELECT
            t.id,
            t.name,
            t.season_year,
            t.gc_uuid,
            t.public_id,
            (
                SELECT COUNT(*) FROM games g
                WHERE g.home_team_id = t.id OR g.away_team_id = t.id
            ) AS game_count,
            CASE WHEN (
                EXISTS (SELECT 1 FROM player_season_batting  WHERE team_id = t.id)
                OR EXISTS (SELECT 1 FROM player_season_pitching WHERE team_id = t.id)
                OR EXISTS (SELECT 1 FROM scouting_runs        WHERE team_id = t.id)
            ) THEN 1 ELSE 0 END AS has_stats
        FROM teams t
        WHERE t.membership_type = 'tracked'
          AND (
              -- NULL rows that have a non-NULL counterpart with the same name
              (t.season_year IS NULL AND EXISTS (
                  SELECT 1 FROM teams t2
                  WHERE t2.name = t.name COLLATE NOCASE
                    AND t2.id != t.id
                    AND t2.membership_type = 'tracked'
                    AND t2.season_year IS NOT NULL
              ))
              OR
              -- Non-NULL rows that have a NULL counterpart with the same name
              (t.season_year IS NOT NULL AND EXISTS (
                  SELECT 1 FROM teams t2
                  WHERE t2.name = t.name COLLATE NOCASE
                    AND t2.id != t.id
                    AND t2.membership_type = 'tracked'
                    AND t2.season_year IS NULL
              ))
          )
        ORDER BY t.name COLLATE NOCASE, COALESCE(t.season_year, -1), t.id
        """
    ).fetchall()

    cross_groups: dict[str, list[DuplicateTeam]] = {}
    for row in cross_rows:
        team = _row_to_duplicate_team(row)
        if team.id in exact_team_ids:
            continue  # non-overlap guarantee
        norm = team.name.lower()
        cross_groups.setdefault(norm, []).append(team)

    # Only keep cross-match groups with 2+ members after filtering
    result = list(exact_groups.values())
    result.extend(g for g in cross_groups.values() if len(g) >= 2)
    return result


def _row_to_duplicate_team(row: tuple) -> DuplicateTeam:
    """Convert a raw SQL row to a DuplicateTeam dataclass."""
    team_id, name, season_year, gc_uuid, public_id, game_count, has_stats_int = row
    return DuplicateTeam(
        id=team_id,
        name=name,
        season_year=season_year,
        gc_uuid=gc_uuid,
        public_id=public_id,
        game_count=game_count,
        has_stats=bool(has_stats_int),
    )
