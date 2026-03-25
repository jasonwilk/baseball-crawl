# E-155-01: Team Merge Core Logic

## Epic
[E-155: Combine Duplicate Teams](epic.md)

## Status
`TODO`

## Description
After this story is complete, the system will have a `merge_teams(canonical_id, duplicate_id, db)` function that atomically reassigns all FK references from the duplicate team to the canonical team and deletes the duplicate. A companion `preview_merge(canonical_id, duplicate_id, db)` function will return a structured summary of what the merge will do (conflict counts, games to reassign, identifier status, blocking issues) without modifying data.

## Context
This is the data-layer foundation for the combine-teams feature. The merge must handle 16 FK references across 13 tables (per TN-1), resolve UNIQUE constraint conflicts (per TN-4), validate safety constraints (per TN-3), and execute in a single atomic transaction (per TN-2). The UI story (E-155-03) will call these functions.

## Acceptance Criteria
- [ ] **AC-1**: A `merge_teams(canonical_id, duplicate_id, db)` function exists in `src/db/merge.py` that executes the full merge transaction per TN-2 (identifier gap-fill, conflict deletion, FK reassignment, duplicate deletion) and raises on any blocking validation failure per TN-3.
- [ ] **AC-2**: A `preview_merge(canonical_id, duplicate_id, db)` function exists in `src/db/merge.py` that returns a dataclass/dict containing: (a) blocking issues list, (b) per-table conflict counts, (c) per-table reassignment counts, (d) identifier comparison (canonical vs duplicate gc_uuid/public_id), (e) whether duplicate has member status, (f) count of games between canonical and duplicate (per TN-3 warning check #5), (g) count of self-referencing rows that will be auto-deleted from `opponent_links` and `team_opponents` (per TN-3 self-reference auto-deletion), (h) whether the duplicate has `our_team_id` entries in `opponent_links` (per TN-3 warning check #4 -- signals it was treated as a member team).
- [ ] **AC-3**: All three blocking checks from TN-3 are enforced (existence, not-equal, member-team guard). `merge_teams` raises a descriptive exception when any blocking check fails. Tests verify each blocking check independently. Self-referencing rows in `opponent_links` and `team_opponents` are auto-deleted during conflict resolution (per TN-3 self-reference auto-deletion), not blocked. Tests verify both directions for each table: (a) `opponent_links` with `(our_team_id=canonical, resolved_team_id=duplicate)` and `(our_team_id=duplicate, resolved_team_id=canonical)`, (b) `team_opponents` with `(our_team_id=canonical, opponent_team_id=duplicate)` and `(our_team_id=duplicate, opponent_team_id=canonical)`.
- [ ] **AC-4**: All tables in TN-1 marked "Delete duplicate's conflicting rows" have their conflicts resolved before FK UPDATE, per TN-4 (canonical wins). Tests verify that for `player_season_batting` and `team_opponents`, conflicting rows from the duplicate are deleted while canonical rows are preserved.
- [ ] **AC-5**: The merge is fully atomic -- if any step fails, no data is modified. Test verifies rollback by triggering a failure mid-merge and confirming the database is unchanged.
- [ ] **AC-6**: Identifier gap-filling per TN-6: canonical's NULL `gc_uuid`/`public_id` are filled from the duplicate's non-null values. Mismatched non-null values are left unchanged (canonical wins). Tests verify both cases AND verify that the partial unique index does not cause a transaction failure (the duplicate's identifiers must be NULLed before copying to canonical, per TN-2 steps 4-5).
- [ ] **AC-7**: After a successful merge, `SELECT COUNT(*) FROM teams WHERE id = :duplicate_id` returns 0. All rows formerly referencing `duplicate_id` either reference `canonical_id` (reassigned) or have been deleted (conflicts per AC-4, self-references per AC-3). No rows reference `duplicate_id` in any of the 13 referencing tables. Test verifies with a populated test database covering all 13 tables.

## Technical Approach
The merge function lives in a new `src/db/merge.py` module. It receives an open `sqlite3.Connection` and executes the full merge within a single `BEGIN IMMEDIATE` transaction. The preview function uses read-only queries to build the summary without modifying data. All 13 tables from TN-1 must be covered. The conflict resolution pattern: for each UNIQUE-constrained table, DELETE the duplicate's rows that would conflict, then UPDATE the remaining rows. See TN-1 for which tables need conflict resolution vs. direct UPDATE.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-155-02, E-155-03

## Files to Create or Modify
- `src/db/merge.py` (create)
- `tests/test_merge.py` (create)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-155-02**: The `src/db/merge.py` module where `find_duplicate_teams` will be added.
- **Produces for E-155-03**: The `merge_teams` and `preview_merge` functions that the admin route will call.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The merge function must handle both columns in tables with dual FK references (`games.home_team_id` + `games.away_team_id`, `team_opponents.our_team_id` + `team_opponents.opponent_team_id`, `opponent_links.our_team_id` + `opponent_links.resolved_team_id`).
- `PRAGMA foreign_keys = ON` should remain enabled throughout. The UPDATEs are safe because `canonical_id` already exists in `teams`.
