# E-197-02: Update Member-Team Loaders to Use Team-Derived season_id

## Epic
[E-197: Derive season_id from Team Context](epic.md)

## Status
`DONE`

## Description
After this story is complete, all member-team loaders (GameLoader, ScheduleLoader, PlaysLoader, RosterLoader, SeasonStatsLoader) will derive season_id from team metadata via `derive_season_id_for_team()` instead of receiving it from the config or parsing it from the filesystem path. The load orchestrator (`src/pipeline/load.py`) will no longer pass `config.season` as season_id to loaders.

## Context
This story converts the member-team pipeline loaders from the two broken derivation patterns (constructor-injected from config, path-inferred) to the canonical utility from E-197-01. Per Technical Notes TN-1, the filesystem path remains unchanged for file discovery -- only the DB insert season_id changes.

**Constructor-injected loaders** (receive `season_id=config.season`):
- `GameLoader.__init__(db, season_id, owned_team_ref)` -- uses `self._season_id` for all game/stat inserts
- `ScheduleLoader.__init__(db, season_id, owned_team_ref)` -- uses `self._season_id` for game inserts
- `PlaysLoader.__init__(db, season_id, owned_team_ref)` -- constructor accepts it but `load_game()` reads from games table (per TN-5)

**Path-inferring loaders** (parse season_id from filesystem):
- `RosterLoader._infer_ids_from_path()` -- parses `data/raw/{season_id}/teams/{team_id}/roster.json`
- `SeasonStatsLoader._infer_ids_from_path()` -- parses `data/raw/{season_id}/teams/{team_id}/stats.json`

## Acceptance Criteria
- [ ] **AC-1**: `GameLoader` and `ScheduleLoader` derive season_id from `derive_season_id_for_team(db, team_ref.id)` instead of a constructor parameter. The `season_id` constructor parameter is removed or replaced.
- [ ] **AC-2**: `RosterLoader.load_file()` derives season_id from team metadata (after identifying the team_id from the path) instead of parsing season_id from the path. The `_infer_ids_from_path()` method no longer returns a season_id component.
- [ ] **AC-3**: `SeasonStatsLoader.load_file()` derives season_id from team metadata instead of parsing it from the path.
- [ ] **AC-4**: `PlaysLoader` constructor no longer requires a `season_id` parameter (it reads from the games table per TN-5). The unused constructor parameter is removed.
- [ ] **AC-5**: `src/pipeline/load.py` no longer passes `config.season` as `season_id` to any loader constructor. Loaders are responsible for their own season_id derivation.
- [ ] **AC-6**: Each modified loader calls `ensure_season_row()` from `src/gamechanger/loaders` (the consolidated version from E-197-01) instead of its own private `_ensure_season_row()` method.
- [ ] **AC-7**: All imports of `warn_season_year_mismatch` and `extract_year_from_season_id` are removed from the modified files. No calls to these functions remain in `game_loader.py`, `schedule_loader.py`, `roster.py`, `season_stats_loader.py`, or `plays_loader.py`. The callers are replaced by `derive_season_id_for_team()` (which provides the year internally) or removed entirely.
- [ ] **AC-8**: Existing tests for each modified loader are updated to reflect the new derivation pattern. Tests that previously mocked or provided season_id as a constructor argument are updated.
- [ ] **AC-9**: Given a team with `season_year=2025` and program_type `usssa`, running the game loader produces games with `season_id='2025-summer-usssa'` in the database (integration test with in-memory DB).

## Technical Approach
For constructor-injected loaders, replace the `season_id` parameter with a call to `derive_season_id_for_team()` inside the loader (either in the constructor or at load time). The loader already has access to `db` and `team_ref.id`.

For path-inferring loaders, the path still provides the team's `gc_uuid` (needed to look up the team's integer ID), but season_id comes from the DB after the team_id is resolved.

The load orchestrator (`src/pipeline/load.py`) simplifies: it no longer needs to pass `config.season` to loader constructors. `config.season` is still used for constructing file paths to find the raw data on disk.

## Dependencies
- **Blocked by**: E-197-01
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` -- remove season_id constructor param, derive from team
- `src/gamechanger/loaders/schedule_loader.py` -- remove season_id constructor param, derive from team
- `src/gamechanger/loaders/plays_loader.py` -- remove unused season_id constructor param
- `src/gamechanger/loaders/roster.py` -- derive season_id from team metadata instead of path
- `src/gamechanger/loaders/season_stats_loader.py` -- derive season_id from team metadata instead of path
- `src/pipeline/load.py` -- stop passing config.season to loaders
- Existing test files for each modified loader (discover via grep)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- `config.season` continues to be used for constructing file paths in `src/pipeline/load.py` (e.g., `data_root / config.season / "teams" / team.id / "roster.json"`). Only the DB season_id derivation changes.
- The `SprayChartLoader` (member-team spray charts) is handled in E-197-03 alongside the scouting spray loader, since both share the path-inference pattern and are closely related.
- `schedule_loader.py:198` uses `extract_year_from_season_id()` for `first_seen_year` in `team_opponents` inserts. The replacement should use `teams.season_year` directly (available from the team context), not re-extract from the derived season_id string. Similarly, `schedule_loader.py:293` and `game_loader.py:1173` use it for `ensure_team_row()`'s `season_year` param -- same replacement pattern.
- Changing `GameLoader`'s constructor signature affects `ScoutingLoader` (which instantiates `GameLoader` at `scouting_loader.py:116`). Story 03 handles that caller; this story only changes the constructor definition and its callers in `src/pipeline/load.py`.
