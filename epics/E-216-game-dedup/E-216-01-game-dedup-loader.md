# E-216-01: Add Pre-Load Game Dedup Check to GameLoader

## Epic
[E-216: Cross-Perspective Game Dedup in the Scouting Pipeline](epic.md)

## Status
`TODO`

## Description
After this story is complete, `GameLoader.load_file()` will detect when a game already exists in the database for the same date and team pair (in either home/away order) before inserting a new row. When a match is found, the loader reuses the existing game's `game_id` for all stat upserts instead of creating a duplicate row. This prevents the cross-perspective duplication that occurs when two tracked teams share a matchup. Because the check lives in `GameLoader` (not in any specific caller), it covers all three data loading paths: `bb data scout` (CLI), `run_scouting_sync` (web), and `bb report generate` (standalone reports). See Technical Notes "Data Loading Paths Covered" section.

## Context
The scouting loader calls `GameLoader.load_file()` for each boxscore. The `GameSummaryEntry.event_id` becomes the `game_id` PK in the `games` table. When the public games API returns different IDs for the same game from different team perspectives, two rows are created. This story adds a dedup check before the insert so the second perspective's data merges into the existing row rather than creating a new one.

The dedup check must be order-insensitive on team IDs because the home/away assignment may differ between perspectives. Doubleheader disambiguation uses `start_time` and score tiebreakers per Technical Notes.

## Acceptance Criteria
- [ ] **AC-1**: Given a game row already exists for `(game_date, team_a, team_b)` and a new boxscore arrives with a different `game_id` but the same `game_date` and same team pair (in either home/away order), when `GameLoader.load_file()` processes the new boxscore, then it reuses the existing `game_id` for all stat upserts and does not create a duplicate `games` row.
- [ ] **AC-2**: Given two games on the same date between the same teams (doubleheader) with different `start_time` values, when `GameLoader.load_file()` processes the second game, then it inserts a new row (no false-positive dedup). Per Technical Notes "Natural Key for Game Dedup" section.
- [ ] **AC-3**: Given two games on the same date between the same teams where `start_time` is NULL on one or both, but the total runs scored (`home_score + away_score`) differ between the two games, when `GameLoader.load_file()` processes the second game, then score-total matching prevents false-positive dedup. Per Technical Notes "Natural Key for Game Dedup" section.
- [ ] **AC-4**: When a duplicate is detected, the loader logs an INFO-level message identifying the original `game_id` and the duplicate `game_id` being redirected.
- [ ] **AC-5**: All existing tests in `tests/test_loaders/test_game_loader.py` continue to pass (no regressions).
- [ ] **AC-6**: New tests cover: (a) basic dedup detection, (b) order-insensitive team matching, (c) doubleheader non-collision with start_time, (d) doubleheader non-collision with score tiebreaker, (e) NULL start_time fallback to score.

## Technical Approach
The dedup check queries the `games` table for an existing completed game on the same date involving the same two teams (order-insensitive). The query and tiebreaker logic are described in the epic's Technical Notes sections "Pre-Load Check (E-216-01)" and "Dedup Query Pattern". The implementer should read those sections for the full pattern, then determine where in the `load_file()` -> `_upsert_game_and_stats()` flow to insert the check and how to propagate the canonical `game_id` to downstream stat upserts.

Key constraint: the `GameSummaryEntry` is currently used as a read-only data carrier. The implementer needs to decide whether to mutate it, create a modified copy, or pass the canonical game_id as a separate parameter.

Reference files:
- `/workspaces/baseball-crawl/src/gamechanger/loaders/game_loader.py` -- `load_file()` at line ~469, `_upsert_game_and_stats()` at line ~580, `_upsert_game()` at line ~934
- `/workspaces/baseball-crawl/src/gamechanger/loaders/scouting_loader.py` -- `_build_games_index()` at line ~262 (root cause context)

## Dependencies
- **Blocked by**: None
- **Blocks**: E-216-02

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` -- add dedup check method, modify `load_file()` to call it
- `tests/test_loaders/test_game_loader.py` or `tests/test_loaders/test_game_dedup.py` -- new dedup-specific tests

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-216-02**: The pre-load dedup logic must be in place before post-load validation is added, so that validation sees correct (deduplicated) data.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `_upsert_game()` method already uses `ON CONFLICT(game_id) DO UPDATE`, so reusing an existing game_id for the upsert will cleanly merge metadata.
- Per-player stat tables (`player_game_batting`, `player_game_pitching`) also use `ON CONFLICT ... DO UPDATE`, so stat rows from the second perspective will merge into existing rows for the same player or insert new rows for players only seen from one perspective.
- This check covers all three loading paths (CLI, web, reports) because it fires inside `GameLoader.load_file()`. The post-load validation (E-216-02) also covers all three paths via `ScoutingLoader.load_team()`. See Technical Notes "Data Loading Paths Covered" section.
