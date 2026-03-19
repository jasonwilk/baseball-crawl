# E-132-01: Use Opponent Names from On-Disk Data in Both Loader Paths

## Epic
[E-132: Fix Opponent Names Showing as UUIDs on Player Detail Page](epic.md)

## Status
`TODO`

## Description
After this story is complete, both the authenticated game loader and the scouting loader will create opponent team rows with human-readable names instead of UUIDs. The `GameLoader._ensure_team_row()` method will accept an optional opponent name parameter, and both loader paths will extract opponent names from their respective on-disk data files and pass them through.

## Context
The player detail page shows UUIDs as opponent names because `_ensure_team_row()` uses `gc_uuid` as the team `name`. Opponent name data is already on disk (`opponents.json` for authenticated path, `games.json` for scouting path) -- it just isn't read during game loading. See epic Technical Notes for the full data flow analysis, including the UUID semantics caveat for `opponents.json`.

## Acceptance Criteria
- [ ] **AC-1**: Given a team directory with `opponents.json` (and/or `schedule.json`) and `game_summaries.json`, when `GameLoader.load_all()` runs, then any new opponent team rows are created with `name` set to the opponent name from the on-disk data rather than the UUID.
- [ ] **AC-2**: Given a scouting directory with `games.json` and boxscores, when `ScoutingLoader.load_team()` runs, then any new opponent team rows are created with `name` set to the opponent name from `games.json` (via `opponent_team.name`) rather than the UUID.
- [ ] **AC-3**: When name source files (`opponents.json`, `schedule.json`, `games.json`) are missing or contain no matching opponent entry, the loader falls back to the existing behavior (UUID as name) without error.
- [ ] **AC-4**: When a team row already exists with a non-UUID name (set by opponent_resolver or manual edit), the existing name is NOT overwritten. However, when the existing row has `name == gc_uuid` (UUID-stub from a prior load), the name IS updated to the opponent name from on-disk data.
- [ ] **AC-5**: The scouting loader's `_record_uuid_from_boxscore_path()` inline INSERT (line 488 of `scouting_loader.py`) also uses opponent names when available, preventing UUID-stub creation by this safety-net code path.
- [ ] **AC-6**: Tests verify both loader paths produce named team rows and the fallback behavior.

## Technical Approach
**Authenticated path**: The team directory already contains `opponents.json` alongside `game_summaries.json`. Parse it to build a `progenitor_team_id → name` lookup (NOT `root_team_id` -- see epic Technical Notes for UUID semantics). Pass this lookup into the game loading flow so `_ensure_team_row()` can use the name. `schedule.json` (also in the same directory) can supplement for opponents with null `progenitor_team_id`.

**Scouting path**: `_build_games_index()` already parses `games.json` which has `opponent_team.name` per game. The challenge is that the opponent UUID is only known during boxscore parsing (from boxscore keys), not from the games index. The implementing agent should determine the best way to connect the name (from games index) to the UUID (from boxscore parsing).

Key reference files:
- `docs/api/endpoints/get-teams-team_id-opponents.md` -- opponents response schema (`progenitor_team_id`, `name`, UUID semantics caveat)
- `docs/api/endpoints/get-teams-team_id-schedule.md` -- schedule response schema (`pregame_data.opponent_name`, `pregame_data.opponent_id`)
- `docs/api/endpoints/get-public-teams-public_id-games.md` -- public games response schema (`opponent_team.name`)

## Dependencies
- **Blocked by**: None
- **Blocks**: E-132-02 (backfill depends on the name-extraction logic from this story)

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` -- `_ensure_team_row()` and `load_all()` / name lookup
- `src/gamechanger/loaders/scouting_loader.py` -- `_build_games_index()` name extraction, `_load_boxscores()` name passing, and `_record_uuid_from_boxscore_path()` inline INSERT (line 488)
- `tests/` (new or modified test files for both loader paths)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-132-02**: The schedule-parsing and name-lookup logic introduced here can be reused by the backfill script/command.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `opponent_resolver` (lines 373-382 of `opponent_resolver.py`) already updates UUID-stub names for resolved opponents. This story uses the same `name == gc_uuid` guard for consistency -- updating UUID-stub names but preserving non-UUID names.
- `_ensure_team_row()` uses `INSERT OR IGNORE` with a UNIQUE constraint on `gc_uuid`, so the same opponent appearing in multiple games correctly maps to one team row.
- The self-healing behavior (updating UUID-stub names on existing rows) means `bb data load` fixes most UUID-stub names without needing the separate backfill command. E-132-02 covers rows that aren't re-loaded.
