# E-169-01: Extract Player Names from Boxscore Data in GameLoader

## Epic
[E-169: Fix Unknown Player Names in Scouting Data](epic.md)

## Status
`DONE`

## Description
After this story is complete, the GameLoader will extract player names from the boxscore `players` array and use them when creating player rows, instead of inserting "Unknown Unknown" stubs. Existing stub rows will be upgraded to real names when the pipeline is re-run, because the UPSERT is conditional — it only overwrites when the current name is "Unknown". Jersey numbers from the boxscore will also populate `team_rosters.jersey_number` when not already set.

## Context
The boxscore JSON contains a `players` array with `id`, `first_name`, `last_name`, `number` for every player in the game. This data is already loaded into memory in `GameLoader.load_file()` but never used — the loader only processes the `groups` section for stats. The stub-creation function (`_ensure_stub_player` or similar) receives only a `player_id` with no name context. This story threads the name data through to the player upsert.

## Acceptance Criteria
- [ ] **AC-1**: Given a boxscore with a player in the `players` array who does not exist in the `players` table, when the GameLoader processes the boxscore, then a new player row is created with the real `first_name` and `last_name` from the boxscore (not "Unknown").
- [ ] **AC-2**: Given a boxscore with a player whose `players` table row has `first_name='Unknown'` and `last_name='Unknown'`, when the GameLoader processes the boxscore, then the player row is updated with the real name from the boxscore `players` array.
- [ ] **AC-3**: Given a boxscore with a player whose `players` table row already has a real name (non-"Unknown"), when the GameLoader processes the boxscore, then the existing name is NOT overwritten — per the conditional UPSERT pattern in Technical Notes.
- [ ] **AC-4**: Given a player whose stats are being loaded from the boxscore AND whose `players` array entry has a `number` field, when the GameLoader processes the boxscore, then a `team_rosters` row is created or updated for that `(team_id, player_id, season_id)` tuple per the conditional UPSERT pattern in Technical Notes (Jersey Number Backfill section): new rows get `jersey_number` populated; existing rows get `jersey_number` backfilled only when currently NULL. `position` is left NULL on boxscore-sourced rows; existing `position` values are never overwritten. Players in the `players` array who do not appear in any stat group are not touched.
- [ ] **AC-5**: Given the GameLoader processes both the "own" team and "opponent" team data from a boxscore, then player names are extracted from both teams' `players` arrays (not just the own team).
- [ ] **AC-6**: Tests verify all three UPSERT scenarios: new player (real name inserted), existing stub (upgraded to real name), existing real name (not overwritten). Tests also verify jersey number behavior: new roster row created with jersey number; existing roster row with NULL jersey_number gets backfilled; existing roster row with non-NULL jersey_number is NOT overwritten.

## Technical Approach
The boxscore JSON has a `players` array sibling to `groups` in each team's data. The loader already has this data in memory — it just needs to be extracted into a lookup dict and threaded through the stat-loading functions to the player upsert call. The stub-creation function needs to accept optional name parameters and use the conditional UPSERT pattern described in the epic's Technical Notes.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-169-02

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` — extract `players` array, thread names through, conditional UPSERT
- `tests/test_loaders/test_game_loader.py` (or appropriate test file) — tests for name extraction, stub upgrade, no-overwrite, jersey number

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `players` array is at `team_data["players"]` where `team_data` is already the per-team dict in scope
- Season stats loader, spray chart loaders, and scouting spray loader do NOT need changes — they lack name data and rely on pipeline ordering (boxscores loaded first)
- ScoutingLoader delegates to `GameLoader.load_file()` and gets this fix for free
