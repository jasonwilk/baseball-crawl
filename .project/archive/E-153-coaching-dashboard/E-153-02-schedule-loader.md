# E-153-02: Schedule Loader

## Epic
[E-153: Team-Centric Coaching Dashboard](epic.md)

## Status
`DONE`

## Description
After this story is complete, the sync pipeline loads upcoming (not-yet-completed) games from `schedule.json` into the `games` table with `status='scheduled'`. When a game completes and its boxscore is loaded, the existing game loader's upsert naturally upgrades the row to `status='completed'` with scores. The coaching dashboard can then query both upcoming and past games from one table.

## Context
The `ScheduleCrawler` already writes `schedule.json` during member sync, but the `GameLoader` only inserts completed games (hardcoded `status='completed'`). There is no code path that loads future games into the database. This is the data prerequisite for the schedule landing page (E-153-03). See Technical Notes TN-1 and TN-2 in the epic for the data flow and opponent resolution chain.

## Acceptance Criteria
- [ ] **AC-1**: After a member team sync, the `games` table contains rows for upcoming (not-yet-played) games from `schedule.json` with `status='scheduled'`, `game_date` populated, and `home_team_id`/`away_team_id` referencing valid `teams(id)` rows. Home/away assignment uses `pregame_data.home_away` per Technical Notes TN-2; when `home_away` is null, our team is assigned as `home_team_id` by convention.
- [ ] **AC-2**: Scheduled game rows have `home_score` and `away_score` as NULL (no scores for unplayed games).
- [ ] **AC-3**: The schedule loader is idempotent -- re-running the sync does not create duplicate game rows. Existing scheduled rows are updated (not duplicated) if schedule data changes.
- [ ] **AC-4**: A test verifies that when a scheduled game row already exists and the `GameLoader` subsequently upserts the same `game_id` with `status='completed'` and actual scores, the row is upgraded correctly (status changes, scores populate, no constraint violation).
- [ ] **AC-5**: For opponents with `resolved_team_id` in `opponent_links`, the game row references the resolved `teams(id)`. For name-only opponents (no `resolved_team_id`), a stub `teams` row is created or found and referenced, per Technical Notes TN-2.
- [ ] **AC-6**: The `team_opponents` junction table has a row for each opponent discovered from the schedule, with `first_seen_year` populated (derived as the year portion of the season_id), ensuring the opponent appears in `get_team_opponents()` dashboard queries. This is an upsert (ON CONFLICT DO NOTHING) to avoid duplicating rows already created by E-152/OpponentResolver. Without `first_seen_year`, opponents will not appear in the junction fallback query (which filters by `first_seen_year = CAST(substr(:season_id, 1, 4) AS INTEGER)`).
- [ ] **AC-7**: The schedule loader runs automatically as part of the member sync pipeline (wired into the sync flow alongside existing crawl/load steps).
- [ ] **AC-8**: Canceled games and non-game events (practices, etc.) from `schedule.json` are filtered out and NOT inserted into the `games` table. Only actual scheduled games are loaded. Consult `docs/api/endpoints/get-teams-team_id-schedule.md` for the field names that distinguish games from non-game events and indicate cancellation.
- [ ] **AC-9**: Each inserted game row has a valid `season_id` set to `config.season` -- the same season_id used by all other loaders in the pipeline per Technical Notes TN-1.
- [ ] **AC-10**: Tests verify: (a) scheduled games are inserted with correct status, NULL scores, and valid season_id, (b) idempotency on re-run, (c) the scheduled-to-completed upgrade path, (d) canceled/non-game events are excluded, (e) when home_away is null, our team is assigned as home_team_id and opponent as away_team_id.

## Technical Approach
Read `schedule.json` structure (written by `ScheduleCrawler`), `opponent_links` table, and the existing `GameLoader._upsert_game()` upsert pattern. The schedule loader reads the crawled `schedule.json` file, resolves opponent team IDs per TN-2, and upserts game rows. Wire the schedule loader into `src/pipeline/load.py` by adding it to the `_LOADERS` list -- it should run before the game loader so that scheduled game rows exist when the game loader upserts completed games. Consult `src/pipeline/load.py` for the loader integration pattern and `src/pipeline/trigger.py` for how `run_member_sync` invokes the load pipeline.

## Dependencies
- **Blocked by**: None within this epic. **Cross-epic runtime dependency**: E-152 (Schedule-Based Opponent Discovery) must be deployed before E-153-02 can produce correct results. E-152 populates `opponent_links` from schedule.json -- without it, the opponent resolution chain (TN-2) has no `opponent_links` data to query. This is a runtime dependency, not a code dependency: the schedule loader code compiles and tests independently, but real syncs require E-152's data.
- **Blocks**: E-153-03 (schedule landing page needs scheduled games in DB)

## Files to Create or Modify
- `src/gamechanger/loaders/` (new schedule loader module or extend existing)
- `src/pipeline/load.py` (wire schedule loader into `_LOADERS` list for pipeline execution)
- `tests/` (new tests for schedule loader)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-153-03**: Scheduled game rows in the `games` table with `status='scheduled'`, enabling the schedule view to show upcoming games. E-153-03 can assume `games` contains both completed and scheduled rows after sync.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `games.game_id` for scheduled games needs a stable identifier. `schedule.json` events have an `id` field -- use that as `game_id` to enable natural upsert when the game completes.
- The `game_stream_id` field may or may not be available for scheduled games in `schedule.json` -- check the crawled data.
- Home/away determination uses `pregame_data.home_away` (values: `"home"`, `"away"`, or `null`). The field name is NOT `is_home_team`. Check the endpoint documentation at `docs/api/endpoints/get-teams-team_id-schedule.md` for the exact structure.
- Stub teams created for name-only opponents should use `source='schedule'` to distinguish from API-resolved teams (`source='gamechanger'`).
