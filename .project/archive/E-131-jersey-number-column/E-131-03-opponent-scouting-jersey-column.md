# E-131-03: Opponent Scouting Jersey Number Column

## Epic
[E-131: Jersey Number as Distinct Dashboard Column](epic.md)

## Status
`DONE`

## Description
After this story is complete, the opponent scouting report batting and pitching tables will display jersey number as a dedicated `#` column. This requires both a query-layer change (adding a `LEFT JOIN team_rosters` to `get_opponent_scouting_report()`) and a template change (adding the column to `opponent_detail.html`).

## Context
The current `get_opponent_scouting_report()` batting and pitching queries do not JOIN `team_rosters`, so jersey number data is not available in the template. Both `team_id` and `season_id` are already function parameters, making the JOIN straightforward.

Opponent scouting data is exclusively for tracked teams whose roster data comes from `ScoutingLoader._load_roster()` (the scouting pipeline). Jersey numbers in `team_rosters` for these teams are populated from public roster API responses (`player.get("number")`). The scouting pipeline may or may not have loaded roster data for every opponent -- the LEFT JOIN handles both cases. See epic Technical Notes TN-5.

## Acceptance Criteria
- [ ] **AC-1**: `get_opponent_scouting_report()` batting query includes `LEFT JOIN team_rosters` per Technical Notes TN-2, returning `jersey_number` in each batting row dict.
- [ ] **AC-2**: `get_opponent_scouting_report()` pitching query includes `LEFT JOIN team_rosters` per Technical Notes TN-2, returning `jersey_number` in each pitching row dict.
- [ ] **AC-3**: `opponent_detail.html` batting table has a `#` column as the first column per Technical Notes TN-1. When `jersey_number` is NULL, the cell renders `—`.
- [ ] **AC-4**: `opponent_detail.html` pitching table has a `#` column as the first column per Technical Notes TN-1. When `jersey_number` is NULL, the cell renders `—`.
- [ ] **AC-5**: No batting or pitching rows are lost when a player has no `team_rosters` entry (LEFT JOIN correctness per TN-2).
- [ ] **AC-6**: New tests in `tests/test_db.py` verify: (a) `jersey_number` appears in scouting report batting/pitching results when a roster row exists, (b) `jersey_number` is `None` (not missing key) when no roster row exists.
- [ ] **AC-7**: Tests verify jersey number resolution for both data paths: (a) a `membership_type='tracked'` opponent team with roster data populated via the scouting pipeline path, and (b) a `membership_type='member'` team queried through the same function (the query is team_id-based and does not filter on membership_type). Both must return `jersey_number` correctly from the same `team_rosters` JOIN. Per TN-4 item 3 and TN-5.
- [ ] **AC-8**: Template rendering tests in `tests/test_dashboard.py` verify: (a) `#` column header is present in opponent detail batting and pitching tables, (b) jersey number value renders in the cell, (c) em dash renders when jersey number is NULL.

## Technical Approach
Add `LEFT JOIN team_rosters tr ON tr.player_id = psb.player_id AND tr.team_id = psb.team_id AND tr.season_id = psb.season_id` to the batting query (and equivalent for pitching). Update `opponent_detail.html` with the new column. Add test cases per TN-4.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py` (modify `get_opponent_scouting_report`)
- `src/api/templates/dashboard/opponent_detail.html`
- `tests/test_db.py` (add jersey number assertions to scouting report query tests)
- `tests/test_dashboard.py` (add template rendering assertions for `#` column in opponent detail)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Opponent jersey number data depends on `ScoutingLoader._load_roster()` having run for that opponent. This is the scouting ingestion path -- roster data comes from public API responses, not the authenticated roster crawler. For opponents without roster data, all players will show `—` in the `#` column -- this is expected and correct behavior.
