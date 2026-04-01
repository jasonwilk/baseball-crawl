# E-197-03: Update Scouting Pipeline Loaders to Use Team-Derived season_id

## Epic
[E-197: Derive season_id from Team Context](epic.md)

## Status
`TODO`

## Description
After this story is complete, the scouting pipeline loaders and the member-team spray chart loader will derive season_id from team metadata via `derive_season_id_for_team()` instead of parsing it from filesystem paths or using a hardcoded suffix. The `ScoutingCrawler._derive_season_id()` hardcoded `"spring-hs"` suffix will no longer affect DB season_id values.

## Context
This story handles the scouting-side loaders and the spray chart loaders (both member and scouting). These loaders all use the path-inference pattern to extract season_id from the filesystem.

**Scouting pipeline flow**: `ScoutingCrawler.scout_team()` derives season_id (with hardcoded `"spring-hs"` suffix) and writes it to `scouting_runs.season_id`. The trigger (`src/pipeline/trigger.py`) reads `scouting_runs.season_id` to find the crawled files on disk, then passes it to `ScoutingLoader.load_team()`. Per TN-1, the filesystem path and `scouting_runs.season_id` are for file discovery only -- the DB season_id for loaded data should come from team metadata.

**Spray chart loaders**: Both `SprayChartLoader` (member teams) and `ScoutingSprayChartLoader` (opponents) parse season_id from the spray directory path.

**Important**: The `ScoutingCrawler` itself does NOT change -- it continues writing files to `data/raw/{derived_season_id}/scouting/{public_id}/`. Only the loaders' DB insert behavior changes.

## Acceptance Criteria
- [ ] **AC-1**: `ScoutingLoader.load_team()` derives season_id for DB inserts from `derive_season_id_for_team(db, team_id)` instead of its `season_id` parameter. The parameter may be retained for file path construction but is NOT used for DB writes.
- [ ] **AC-2**: `SprayChartLoader.load_dir()` derives season_id from team metadata instead of parsing it from the spray directory path.
- [ ] **AC-3**: `ScoutingSprayChartLoader.load_dir()` derives season_id from team metadata instead of parsing it from the path.
- [ ] **AC-4**: `src/pipeline/trigger.py` -- the season_id read from `scouting_runs` is used only for file path construction (finding the scouting directory), not passed through to loaders for DB inserts.
- [ ] **AC-5**: `src/cli/data.py` -- scouting-related commands use the correct season_id flow (file paths from config/scouting_runs, DB season_id from team metadata).
- [ ] **AC-6**: `ScoutingLoader` uses the consolidated `ensure_season_row()` from `src/gamechanger/loaders` instead of its own private `_ensure_season_row()` method. (The spray chart loaders do not have their own `_ensure_season_row()` -- this AC applies to `ScoutingLoader` only.)
- [ ] **AC-7**: `src/reports/generator.py` -- the `_query_season_id()` function (which reads `scouting_runs.season_id`) is used only for file path construction. All stat queries (`_query_batting`, `_query_pitching`, `_query_roster`, `_query_record`, `_query_recent_games`, `_query_freshness`, `_query_spray_charts`, `_query_runs_avg`) use `derive_season_id_for_team()` for the season_id parameter. The hardcoded `"spring-hs"` fallback at line 624 is replaced by `derive_season_id_for_team()`.
- [ ] **AC-8**: All imports of `warn_season_year_mismatch` and `extract_year_from_season_id` are removed from the modified source files. The `scouting_loader.py` caller of `extract_year_from_season_id()` is replaced by `derive_season_id_for_team()`. After this story, both `extract_year_from_season_id()` and `warn_season_year_mismatch()` have no remaining callers and are removed from `src/gamechanger/loaders/__init__.py`. The `warn_season_year_mismatch` tests in `tests/test_trigger.py` (3 test methods, lines ~470-528) are also removed.
- [ ] **AC-9**: Existing tests for each modified loader are updated. New tests verify that scouting data for a USSSA team gets the correct season_id in the DB regardless of the crawl directory name.

## Technical Approach
The key insight is separating "where to find files" from "what season_id to write to DB." The `scouting_runs.season_id` and filesystem paths continue to work as they do today for file discovery. But when the loader inserts rows into `games`, `player_season_batting`, `player_season_pitching`, `team_rosters`, `spray_charts`, etc., it calls `derive_season_id_for_team()` to get the correct DB season_id.

For `ScoutingLoader.load_team()`, the `season_id` parameter is still needed to locate the scouting directory on disk. The loader derives the DB season_id separately from team metadata.

For the spray chart loaders, the directory path still provides the `gc_uuid` (for team identification), but season_id for DB writes comes from the utility function.

## Dependencies
- **Blocked by**: E-197-01, E-197-02 (ScoutingLoader instantiates GameLoader -- constructor signature changes in Story 02)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py` -- derive DB season_id from team metadata
- `src/gamechanger/loaders/spray_chart_loader.py` -- derive DB season_id from team metadata
- `src/gamechanger/loaders/scouting_spray_loader.py` -- derive DB season_id from team metadata
- `src/pipeline/trigger.py` -- adjust season_id flow (file path vs DB)
- `src/cli/data.py` -- adjust scouting command season_id flow
- `src/reports/generator.py` -- separate crawl-path season_id (file discovery) from DB season_id (stat queries)
- `src/gamechanger/loaders/__init__.py` -- remove `extract_year_from_season_id()` and `warn_season_year_mismatch()` (last callers eliminated by this story)
- `tests/test_trigger.py` -- remove 3 `warn_season_year_mismatch` test methods (~lines 470-528)
- Existing test files for each modified loader (discover via grep)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `ScoutingCrawler._derive_season_id()` function with its hardcoded `"spring-hs"` suffix is NOT modified by this story. It continues to determine the filesystem path where crawled files are stored. The fix is in the loaders, not the crawlers.
- The `scouting_runs.season_id` column continues to reflect the crawl directory path (for file discovery). It does NOT necessarily match the DB season_id of the loaded data. This is intentional per TN-1. The implementer should add a brief code comment near `scouting_runs.season_id` usage in the scouting loader explaining this semantic distinction (e.g., "season_id here is a file-discovery hint, not the logical season -- see TN-1 in E-197 epic").
