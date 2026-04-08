# E-219-01: GameLoader Own-Side-Only

## Epic
[E-219: Own-Side-Only Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, `GameLoader._upsert_game_and_stats()` will only insert player stats (batting, pitching, roster, player rows) for the team whose perspective the boxscore was fetched from. The opponent's player data (`opp_data`) will be discarded. Game-level data (game row, team rows, scores, dates) will continue to load from either perspective.

## Context
This is the core fix for the cross-perspective player duplication bug. `_upsert_game_and_stats()` currently calls `_load_team_stats()` for both `own_data` and `opp_data` (lines 637-648 of `game_loader.py`). The `opp_data` path inserts opponent players with perspective-specific UUIDs that differ from those opponent's own boxscore. This is the root cause of phantom duplicate players across all three prior fix attempts (E-211, E-215, E-216). See TN-1 and TN-2 in the epic for full context.

## Acceptance Criteria
- [ ] **AC-1**: Given a boxscore with both own and opponent team data, when `_upsert_game_and_stats()` is called, then player stats (`player_game_batting`, `player_game_pitching`, `team_rosters`, `players`) are inserted ONLY for the own-team side. No rows are inserted for the opponent team's players. (The opponent team row in `teams` is preserved -- only player-level data is filtered.)
- [ ] **AC-2**: Given a boxscore load, when the game row is upserted, then game-level data (game row with scores, dates, `home_team_id`, `away_team_id`) is still populated from either perspective. The opponent team row in `teams` is still created/updated.
- [ ] **AC-3**: Given existing tests in `tests/test_loaders/test_game_loader.py` and `tests/test_uuid_contamination.py`, when tests are updated to reflect own-side-only behavior, then all tests pass. Tests that previously asserted opponent player rows are inserted must be updated to assert they are NOT inserted.
- [ ] **AC-4**: A new test verifies that when a boxscore contains both own and opponent data, opponent player stats are discarded (zero rows in `player_game_batting`/`player_game_pitching`/`team_rosters` for the opponent team's player UUIDs).
- [ ] **AC-5**: The `opp_data` variable is still extracted from the boxscore JSON (needed for `_resolve_team_ids` and opponent team name resolution). Only the `_load_team_stats(opp_data, ...)` call is removed.

## Technical Approach
The fix is in `src/gamechanger/loaders/game_loader.py`, method `_upsert_game_and_stats()`. The `opp_data` extraction and team ID resolution must remain (game row needs both team IDs). Only the player stat insertion for the opponent side needs removal. See TN-2 in the epic for the risk assessment and TN-1 for the UUID behavior.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-219-02, E-219-03, E-219-04, E-219-05

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py`
- `tests/test_loaders/test_game_loader.py`
- `tests/test_uuid_contamination.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-219-02**: The `opp_data` player loading path is removed from `GameLoader`. Downstream stories can assume only own-side player data exists in stat tables after a boxscore load. The spray loader fix (E-219-02) applies the same principle to a different loader.
- **Produces for E-219-03**: Existing cross-perspective duplicates in the database are now orphaned (no new ones created). The cleanup story targets these orphans.
- **Produces for E-219-04**: The code change establishes the own-side-only pattern. The context-layer story codifies it as a rule.
- **Produces for E-219-05**: With the root cause fixed, dedup infrastructure built to compensate can be assessed for removal.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- This story is the foundation. All other stories in the epic depend on this core fix being in place.
- The `opp_data` variable and opponent team resolution logic must NOT be removed -- they serve the game row upsert. Only the `_load_team_stats(opp_data, opp_team_id, ...)` call is removed.
