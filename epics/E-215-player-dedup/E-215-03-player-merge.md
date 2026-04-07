# E-215-03: Player Merge Function and CLI Execution

## Epic
[E-215: Fix Player-Level Duplicates from Cross-Perspective Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, a `merge_player_pair(db, canonical_id, duplicate_id)` function will atomically reassign all FK references from a duplicate player_id to the canonical player_id across all 8 affected tables, handling UNIQUE constraint conflicts with the delete-or-update pattern, then deleting the duplicate player row. The `bb data dedup-players --execute` CLI flag triggers the merge for all detected pairs. Season aggregates are recomputed after the merge.

## Context
This is the core data repair story. With detection (E-215-02) identifying the pairs and the canonical upsert (E-215-01) ensuring name quality, this story performs the actual merge. The pattern follows `src/db/merge.py:merge_teams()` -- atomic transaction, delete conflicts first, then reassign FKs, then delete the duplicate. The critical insight from Coach consultation: these are the same at-bats from two boxscore perspectives, so stats are NOT additive -- canonical wins for same-game conflicts.

## Acceptance Criteria
- [ ] **AC-1**: A function `merge_player_pair(db, canonical_id, duplicate_id, manage_transaction=True)` exists in `src/db/player_dedup.py` that executes the merge following the order in TN-6. When `manage_transaction=True` (default, for CLI use), it wraps the merge in a `BEGIN IMMEDIATE` transaction. When `manage_transaction=False` (for scouting loader post-load use per E-215-04), it uses `SAVEPOINT`/`RELEASE`/`ROLLBACK TO` for per-pair isolation within the caller's implicit transaction (per TN-4).
- [ ] **AC-2**: For game-level stat tables (`player_game_batting`, `player_game_pitching`) with same-game conflicts per TN-4, the row with the better `stat_completeness` value is kept (full > supplemented > boxscore_only); if tied, the canonical row is kept. For season-level stat tables, both rows are deleted and recomputed per TN-5. For `team_rosters` and `reconciliation_discrepancies`, the canonical row is kept.
- [ ] **AC-3**: For tables without player UNIQUE constraints (plays, spray_charts), all duplicate references are updated to canonical via simple UPDATE.
- [ ] **AC-4**: After merge, zero rows in any table reference the duplicate player_id.
- [ ] **AC-5**: After merge, the duplicate player_id row is deleted from the `players` table.
- [ ] **AC-6**: The canonical player row has the best available name (full name, not initial) after merge -- using `ensure_player_row()` from E-215-01 to ensure the longer name is preserved.
- [ ] **AC-7**: If the merge transaction fails for any pair, it rolls back cleanly for that pair (no partial state), logs the error, and continues to the next pair.
- [ ] **AC-8**: `bb data dedup-players --execute` runs detection, then merges all detected pairs, printing a summary of pairs merged and any errors.
- [ ] **AC-9**: After all pairs are merged, season aggregates (`player_season_batting`, `player_season_pitching`) for all affected (player_id, team_id, season_id) tuples -- across all seasons where either the canonical or duplicate appeared -- are recomputed from game-level data per TN-5.
- [ ] **AC-10**: Integration test sets up two player_ids with rows in all 8 affected tables (including same-game conflict rows), runs the merge, and asserts: (a) all rows reference canonical, (b) no rows reference duplicate, (c) every duplicate row is accounted for -- either reassigned to canonical or intentionally deleted as a UNIQUE conflict (no rows silently dropped), (d) duplicate player row is deleted, (e) the canonical player's post-merge stat values (PA for batting, IP for pitching) match the expected values from the kept row (not summed across both).
- [ ] **AC-11**: `bb data dedup-players --dry-run` (default) reports what the merge WOULD do without modifying any data (pair count + per-table row counts that would be affected).

## Technical Approach
Add `merge_player_pair()` and a `merge_all_duplicate_players()` orchestrator to `src/db/player_dedup.py`. The per-pair function follows the transaction pattern in TN-6: open BEGIN IMMEDIATE, process tables in FK-safe order (children before parent), commit. For UNIQUE-constrained tables, check for conflict existence before UPDATE; if conflict exists, DELETE the duplicate's row. For non-UNIQUE tables, simple UPDATE. After all pairs are merged, delete season aggregate rows for affected (player_id, team_id, season_id) combos and trigger recomputation. Wire `--execute` into the existing `bb data dedup-players` CLI command from E-215-02.

## Dependencies
- **Blocked by**: E-215-01 (needs `ensure_player_row()` for name quality), E-215-02 (needs `find_duplicate_players()` for pair list)
- **Blocks**: E-215-04

## Files to Create or Modify
- `src/db/player_dedup.py` (MODIFY -- add merge function)
- `src/cli/data.py` (MODIFY -- add `--execute` flag to `dedup-players` command)
- `tests/test_player_dedup.py` (MODIFY -- add integration test for merge)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-215-04**: The `merge_player_pair()` function is reused by the post-load prevention layer to merge any duplicates detected immediately after scouting load.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `spray_charts` table has both `player_id` (batter) and `pitcher_id` columns that reference `players(player_id)`. Both must be updated during merge.
- The `plays` table has both `batter_id` and `pitcher_id` columns. Both must be updated.
- Season recomputation must be self-contained in `src/db/player_dedup.py` -- do NOT import from scouting_loader (circular dependency risk per TN-5). Aggregate directly from `player_game_batting`/`player_game_pitching`.
- The `reconciliation_discrepancies` table has a sentinel `player_id = '__game__'` for game-level discrepancies. The merge must filter `player_id != '__game__'` to avoid corrupting sentinel rows (per TN-4).
- The dry-run report should show per-table counts similar to `preview_merge()` in `src/db/merge.py`.
