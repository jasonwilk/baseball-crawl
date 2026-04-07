# E-216-02: Add Post-Load Data Validation to Scouting Loader

## Epic
[E-216: Cross-Perspective Game Dedup in the Scouting Pipeline](epic.md)

## Status
`TODO`

## Description
After this story is complete, the scouting loader will validate loaded data against expected counts from the crawled source files before computing season aggregates. If the DB game count or roster count doesn't match what was crawled, the loader logs a WARNING with expected vs. actual counts. This catches duplicates, missing data, and other integrity issues immediately at load time — not after coaches see wrong stats.

## Context
This project has repeatedly shipped bad data and discovered it after the fact. The scouting loader already knows what the data should look like: `games.json` lists the completed games, `roster.json` lists the players. After loading, the loader should verify the DB matches these expectations. This is a simple, general-purpose integrity check that catches game dupes, player dupes, missing games, and any other load anomaly.

The pre-load check (E-216-01) prevents game duplicates at insert time. This validation confirms it worked — and catches any other category of data corruption that the pre-load check doesn't cover.

## Acceptance Criteria
- [ ] **AC-1**: After `_load_boxscores()` completes, the scouting loader checks for duplicate game rows involving this team by querying for any `(game_date, unordered team pair)` groups with `COUNT(*) > 1` among completed games where this team is home or away. If any duplicates are found, a WARNING is logged: `"Post-load validation: {count} duplicate game(s) detected for team_id={team_id}"` with the game dates and team pairs involved.
- [ ] **AC-2**: After `_load_roster_section()` completes (before boxscores), the scouting loader queries the DB for the count of players in `team_rosters` for this `(team_id, season_id)`, and compares it to the count of players in the loaded `roster.json`. If the DB count exceeds the expected count, a WARNING is logged: `"Post-load validation: expected {expected} roster entries for team_id={team_id}, found {actual} in DB"`. (DB count may be lower than expected after player dedup merges — that's correct behavior, not warned.)
- [ ] **AC-3**: Validation is non-fatal — warnings are logged but the pipeline continues (season aggregates are still computed, scouting run completes).
- [ ] **AC-4**: Roster validation runs immediately after `_load_roster_section()` (before boxscores are loaded, since `GameLoader` can add players from boxscores not in `roster.json`). Game duplicate check runs after `_load_boxscores()`. Both run before `_compute_season_aggregates()`.
- [ ] **AC-5**: The game duplicate check uses order-insensitive team matching (`MIN(home_team_id, away_team_id), MAX(home_team_id, away_team_id)`) and filters to `status = 'completed'`.
- [ ] **AC-6**: Tests cover: (a) no duplicates produces no warning, (b) duplicate game detected produces WARNING, (c) roster count exceeding expected produces WARNING, (d) roster count lower than expected (post-dedup) produces no warning, (e) validation doesn't block the pipeline on warnings.

## Technical Approach
Add two private validation methods to `ScoutingLoader`:

`_check_duplicate_games(team_id)`:
```sql
SELECT game_date, MIN(home_team_id, away_team_id) AS t1, MAX(home_team_id, away_team_id) AS t2, COUNT(*) AS cnt
FROM games
WHERE (home_team_id = ? OR away_team_id = ?)
  AND status = 'completed'
GROUP BY game_date, t1, t2
HAVING cnt > 1
```
If any rows returned, log WARNING with the game dates and team pairs. This directly detects duplicate games without false positives from cross-team loading (where other teams' scouting runs legitimately added games involving this team).

`_validate_roster_count(team_id, season_id, expected_count)`:
```sql
SELECT COUNT(*) FROM team_rosters
WHERE team_id = ? AND season_id = ?
```
Warn only if DB count EXCEEDS expected (player dedup may legitimately reduce count below expected).

Call `_check_duplicate_games()` after `_load_boxscores()`. Call `_validate_roster_count()` after `_load_roster_section()` with the roster player count from `roster.json`.

Reference files:
- `/workspaces/baseball-crawl/src/gamechanger/loaders/scouting_loader.py` -- `load_team()` at line ~75, `_build_games_index()` at line ~262, `_load_roster_section()` at line ~166

## Dependencies
- **Blocked by**: E-216-01 (pre-load check should be in place first so validation sees correct data)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py` -- add `_check_duplicate_games()` and `_validate_roster_count()` methods, call them in `load_team()`
- `tests/test_scouting_loader.py` or `tests/test_post_load_validation.py` -- validation tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- This is ~20-30 lines of implementation code. Keep it simple.
- The game count validation checks games where this team is home OR away — not just games "owned by" this team. This correctly catches cross-perspective duplicates.
- Future enhancement: per-game batting row count validation (expected N batters per game from boxscore data vs. actual DB rows). Out of scope for this story but a natural extension.
- The existing `dedup_team_players()` hook (E-215) runs after boxscore loading and before the game duplicate check (`_check_duplicate_games()`). That's correct — the game duplicate check should see the post-dedup state. Note: roster validation runs earlier (after `_load_roster_section()`, before boxscores) per AC-4, so it is unaffected by `dedup_team_players()`.
