# E-197-01: Canonical season_id Derivation Utility

## Epic
[E-197: Derive season_id from Team Context](epic.md)

## Status
`TODO`

## Description
After this story is complete, a shared `derive_season_id_for_team()` function will exist that takes a DB connection and team_id and returns the correct season_id string derived from team metadata. A shared `ensure_season_row()` function will replace the duplicated implementations across 4+ loaders. The legacy functions (`warn_season_year_mismatch()` and `extract_year_from_season_id()`) are kept in this story to avoid breaking imports; they are removed in Stories 02/03.

## Context
This is the foundation story for the epic. All other stories depend on this utility function. Currently, season_id is derived from filesystem paths or a global config value, leading to wrong tags for teams whose real season differs from the crawl directory. The derivation logic needs a single canonical source that uses team metadata (`teams.season_year` + `programs.program_type`).

The `_ensure_season_row()` function is duplicated in at least `GameLoader`, `ScheduleLoader`, `RosterLoader`, `ScoutingLoader`, and `ScoutingCrawler`. All implementations do the same thing: parse the season_id slug to extract year, then INSERT OR IGNORE into `seasons`.

## Acceptance Criteria
- [ ] **AC-1**: `derive_season_id_for_team(db, team_id)` returns the correct season_id per the algorithm in Technical Notes TN-2. Specifically:
  - Given a team with `season_year=2025` and program_type `usssa`, returns `"2025-summer-usssa"`
  - Given a team with `season_year=2026` and program_type `hs`, returns `"2026-spring-hs"`
  - Given a team with `season_year=2025` and program_type `legion`, returns `"2025-summer-legion"`
  - Given a team with `season_year=2026` and no `program_id`, returns `"2026"`
  - Given a team with NULL `season_year` and program_type `hs`, returns `"{current_year}-spring-hs"`
  - Given a team with NULL `season_year` and no `program_id`, returns `"{current_year}"`
- [ ] **AC-2**: A shared `ensure_season_row(db, season_id)` function exists in `src/gamechanger/loaders/__init__.py` that handles both `{year}-{suffix}` and year-only formats. For `{year}-{suffix}` (e.g., `2025-summer-usssa`), it sets `season_type` to the suffix. For year-only (e.g., `2026`), it sets `season_type` to `"default"`. The `seasons.season_type NOT NULL` constraint is satisfied in both cases. The function uses INSERT OR IGNORE (idempotent).
- [ ] **AC-3**: `warn_season_year_mismatch()` is NOT removed in this story. It has 4 callers (`game_loader.py`, `roster.py`, `season_stats_loader.py`, `scouting_loader.py`) whose imports would break. These callers are removed in Stories 02/03, which will remove the function definition after its last caller is eliminated.
- [ ] **AC-4**: `extract_year_from_season_id()` is NOT removed in this story. It has 5 live callers outside the warning function (`schedule_loader.py` x3, `game_loader.py` x1, `scouting_loader.py` x1) that use it for team creation and opponent linking. These callers are modified in Stories 02/03, which will remove the function and its callers together.
- [ ] **AC-5**: Error contract: If the team_id does not exist in the `teams` table, `derive_season_id_for_team()` raises `ValueError`. If `program_id` is NULL or the programs row is missing, the function falls back to year-only format (not an error). If `season_year` is NULL, the function falls back to current calendar year (not an error).
- [ ] **AC-6**: Unit tests cover all derivation cases from AC-1, the error case from AC-5, and edge cases (NULL program_id, NULL season_year, both NULL).
- [ ] **AC-7**: Unit tests cover `ensure_season_row()` for both formats.

## Technical Approach
The new functions go in `src/gamechanger/loaders/__init__.py` alongside the existing `LoadResult` dataclass. The derivation function queries `teams` joined to `programs` to get `season_year` and `program_type`, then applies the mapping from Technical Notes TN-2. The `ensure_season_row()` consolidation replaces the private `_ensure_season_row()` methods scattered across loaders.

Neither `warn_season_year_mismatch()` nor `extract_year_from_season_id()` is removed in this story. Both have live callers in loaders whose import lines would break tests. Removal is deferred to Stories 02/03 as they eliminate each caller.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-197-02, E-197-03

## Files to Create or Modify
- `src/gamechanger/loaders/__init__.py` -- add `derive_season_id_for_team()`, `ensure_season_row()` (keep both `warn_season_year_mismatch()` and `extract_year_from_season_id()` -- removed in Stories 02/03)
- `tests/test_season_id_derivation.py` -- new test file

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-197-02**: `derive_season_id_for_team()` and `ensure_season_row()` functions importable from `src.gamechanger.loaders`. E-197-02 will import and use these in member-team loaders.
- **Produces for E-197-03**: Same functions. E-197-03 will import and use these in scouting pipeline loaders.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The program_type → season_suffix mapping is: `{"hs": "spring-hs", "usssa": "summer-usssa", "legion": "summer-legion"}`. This is consistent with the existing `2026-spring-hs` convention and extends it to other program types.
