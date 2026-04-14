# E-223-01: Fix Admin Delete Confirmation Counts to Mirror Cascade

## Epic
[E-223: E-220 Adopter Audit](./epic.md)

## Status
`DONE`

## Description
After this story is complete, the admin delete confirmation page will display row counts that accurately reflect what `cascade_delete_team()` will actually delete. The current counts use a pre-E-220 game-subquery pattern that overcounts (includes other perspectives' rows) and undercounts (misses scouting rows from the team's perspective in games it didn't play in). The fix replaces the game-subquery pattern with perspective-aware counts mirroring the cascade's two-pass logic.

## Context
`src/api/routes/admin.py::_get_delete_confirmation_data()` (lines 718-798) displays "how many rows will be affected" before the operator confirms a team deletion. Seven COUNT queries use `game_id IN (SELECT game_id FROM games WHERE home_team_id = ? OR away_team_id = ?)` -- the pre-provenance pattern. The actual cascade (`_delete_team_anchor_and_orphan_data`) deletes via two passes: Pass 1 `WHERE perspective_team_id = T`, Pass 2 `WHERE team_id = T` (or `batting_team_id = T` for plays). The cleanup-detection mirror invariant (`.claude/rules/data-model.md`) requires confirmation counts to mirror the cascade surface.

## Acceptance Criteria
- [ ] **AC-1**: The seven stat-table COUNT queries in `_get_delete_confirmation_data()` are replaced with perspective-aware counts per Technical Notes TN-1 and TN-2. The `_game_ids` subquery pattern is retired for these tables.
- [ ] **AC-2**: For tables with both FK dimensions (`player_game_batting`, `player_game_pitching`, `spray_charts`, `plays`, `reconciliation_discrepancies`), counts reflect `WHERE perspective_team_id = T OR [anchor_fk] = T` without double-counting rows where both conditions are true.
- [ ] **AC-3**: `play_events` count cascades through `plays` using the same two-FK union (via `plays.perspective_team_id` and `plays.batting_team_id`).
- [ ] **AC-4**: `game_perspectives` count uses `WHERE perspective_team_id = ?` only (no anchor FK).
- [ ] **AC-5**: The `games_count` and `affected_opponent_teams` queries (lines 733-749) are unchanged -- these are team-participation queries, not stat-table counts.
- [ ] **AC-6**: Tests verify that cross-perspective rows are correctly excluded from counts (not overcounted) and that scouting rows from the team's perspective in non-participant games are included (not undercounted).

## Technical Approach
The seven stat-table queries at lines 723-788 all use the `_game_ids` subquery. Replace each with a query that mirrors the corresponding table's cascade FK columns per TN-2. The `games_count` and team-scoped counts (`psb_count`, `psp_count`, `tr_count`, `sr_count`) are already correct and should not change. Existing test infrastructure in `tests/test_admin_delete_cascade.py` may need new test cases or fixtures that include cross-perspective data to validate the corrected counts.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` (modify -- `_get_delete_confirmation_data()`)
- `tests/test_admin_delete_cascade.py` (modify -- add cross-perspective count tests)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `_game_ids` variable (line 718) can be removed entirely once all stat-table queries are rewritten. The `games_count` query at line 733 uses its own inline condition and does not depend on `_game_ids`.
- The spray_charts count currently has a combined condition (line 762-763) mixing game-subquery with `OR team_id = ?`. This should be simplified to the standard two-FK union pattern.
