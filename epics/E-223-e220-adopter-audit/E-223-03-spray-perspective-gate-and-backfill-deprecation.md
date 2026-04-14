# E-223-03: Add Perspective Gate to Spray Loaders + Deprecate Backfill

## Epic
[E-223: E-220 Adopter Audit](./epic.md)

## Status
`TODO`

## Description
After this story is complete, both spray loaders will skip already-loaded game+perspective combinations at the game level (avoiding unnecessary per-row INSERT OR IGNORE attempts), and the backfill script will be marked as a deprecated one-time migration aid.

## Context
**F-4 (spray loaders)**: `src/gamechanger/loaders/spray_chart_loader.py` and `src/gamechanger/loaders/scouting_spray_loader.py` both lack a whole-game perspective gate. They rely on per-row `INSERT OR IGNORE` on the UNIQUE constraint to handle already-loaded data. Data correctness is preserved, but this causes unnecessary per-row INSERT OR IGNORE work (SQL round-trips for every spray event) for perspectives that have already been fully loaded. The plays loader demonstrates the correct pattern: check for existing rows before processing a game (per Technical Notes TN-3).

**F-3 (backfill)**: `src/gamechanger/loaders/backfill.py` was a one-time migration aid for E-204 (adding `appearance_order` to historical rows). Going forward, `appearance_order` is populated at INSERT time by the game loader. SE confirmed the script has no ongoing operational value. Adding a deprecation comment is sufficient.

## Acceptance Criteria
- [ ] **AC-1**: `SprayChartLoader` checks whether spray data has already been loaded for the current `(game_id, perspective_team_id)` combination before processing a game's spray events. If already loaded, the game is skipped with a debug log message.
- [ ] **AC-2**: `ScoutingSprayChartLoader` performs the same whole-game perspective gate as AC-1.
- [ ] **AC-3**: Both loaders' `LoadResult.skipped` count increments by 1 per game skipped by the perspective gate (game-level granularity, matching the plays loader convention).
- [ ] **AC-4**: Tests verify that a game with an already-loaded perspective is skipped (no duplicate INSERT attempts), while a game with a new perspective is loaded normally.
- [ ] **AC-5**: `src/gamechanger/loaders/backfill.py` contains a module-level docstring or comment marking it as a deprecated one-time migration aid for E-204, noting that `appearance_order` is now populated at INSERT time by the game loader and that this script does not include perspective-aware filtering.

## Technical Approach
For the spray loaders, the perspective gate follows the same pattern as the plays loader (TN-3): query `spray_charts` for any existing row matching the game and perspective before processing. For the backfill deprecation, add a clear note at the module level.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/spray_chart_loader.py` (modify -- add perspective gate)
- `src/gamechanger/loaders/scouting_spray_loader.py` (modify -- add perspective gate)
- `src/gamechanger/loaders/backfill.py` (modify -- add deprecation comment)
- `tests/test_loaders/test_spray_chart_loader.py` (modify -- add perspective gate test)
- `tests/test_scouting_spray_loader.py` (modify -- add perspective gate test)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The perspective gate is a performance optimization, not a correctness fix. The `INSERT OR IGNORE` pattern ensures data correctness regardless. But skipping entire games avoids wasted per-row SQL work for already-loaded perspectives. Note: the gate checks `spray_charts` for existing rows (same pattern as plays_loader TN-3). Games where spray data was null (scorekeeper didn't record) will have no rows and re-process on each run — this is acceptable as the processing overhead for null-data games is minimal.
- The backfill script reads from disk-cached boxscore JSON (`data/raw/`), which means it doesn't work in the scouting pipeline's in-memory flow -- another reason it's effectively deprecated.
