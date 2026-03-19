# E-132-02: Backfill Existing UUID-Stub Team Names from On-Disk Data

## Epic
[E-132: Fix Opponent Names Showing as UUIDs on Player Detail Page](epic.md)

## Status
`DONE`

## Description
After this story is complete, existing team rows where `name == gc_uuid` will be updated with the correct opponent name by scanning on-disk data files. A `bb` CLI command will be available to run this backfill on demand.

## Context
After E-132-01, normal loading (via `bb data load` or `bb data scout`) self-heals UUID-stub names for opponents that appear in re-loaded games. However, opponents that are NOT re-loaded (e.g., from prior seasons or teams no longer active) retain UUID-as-name. This story provides a standalone backfill command that scans ALL on-disk data files (`opponents.json`, `schedule.json`, `games.json`) to fix any remaining UUID-stub rows. See epic Technical Notes for the backfill strategy.

## Acceptance Criteria
- [ ] **AC-1**: After running the backfill command, all team rows where `name == gc_uuid` (exact column match) AND a corresponding opponent name exists in on-disk data have their `name` updated to the human-readable opponent name.
- [ ] **AC-2**: Team rows where `name` was already set to a non-UUID value (by opponent_resolver or manual edit) are NOT modified.
- [ ] **AC-3**: Team rows where no matching name data exists on disk retain their current name (no error, no change).
- [ ] **AC-4**: The backfill is idempotent -- running it twice produces the same result.
- [ ] **AC-5**: The command is accessible via `bb data backfill-team-names`.
- [ ] **AC-6**: The command reports how many team names were updated.

## Technical Approach
Scan `data/raw/` for `opponents.json` and `schedule.json` files (authenticated path) and `games.json` files (scouting path). For each file, extract the opponent UUID → name mapping. Query the database for team rows where `name == gc_uuid` (exact column match, same guard as opponent_resolver). For each match, if a name is found in the on-disk data, UPDATE the row.

The name-extraction logic from E-132-01 can be reused here.

## Dependencies
- **Blocked by**: E-132-01 (reuses name-extraction logic)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (or a new utility module if the implementing agent prefers)
- `src/cli/` (new or modified CLI command)
- `tests/` (test for the backfill logic)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The guard for identifying stale rows is `name == gc_uuid` (exact column match), NOT a regex UUID pattern. This is consistent with the opponent_resolver guard (lines 373-382 of `opponent_resolver.py`).
- When parsing `opponents.json`, the lookup MUST be keyed by `progenitor_team_id` (the canonical GC UUID), NOT `root_team_id` (the local registry key). See epic Technical Notes for the full UUID semantics caveat. `progenitor_team_id` is null on ~14% of records -- those entries are skipped.
- `schedule.json` uses `pregame_data.opponent_id` (same value as `progenitor_team_id`) and can supplement gaps.
