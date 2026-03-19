# E-131-02: Game Box Score Jersey Number Column

## Epic
[E-131: Jersey Number as Distinct Dashboard Column](epic.md)

## Status
`TODO`

## Description
After this story is complete, the game detail box score tables (batting and pitching for both teams) will display jersey number as a dedicated `#` column. This requires both a query-layer change (adding a `LEFT JOIN team_rosters` to `get_game_box_score()`) and a template change (adding the column to `game_detail.html`).

## Context
The current `get_game_box_score()` batting and pitching queries do not JOIN `team_rosters`, so jersey number data is not available in the template. The `games` table has a `season_id` column, but the current `game_query` in `get_game_box_score()` does not SELECT it. This story must extend `game_query` to include `g.season_id` so it can be passed to the batting/pitching queries for the three-way JOIN key per Technical Notes TN-3.

Box score rows contain players from both teams in the same game. For member-team games, one team's jersey numbers come from roster-loaded data and the opponent's come from scouting-loaded data (or may be absent if scouting hasn't run). The LEFT JOIN must resolve correctly for both sides. See epic Technical Notes TN-5.

## Acceptance Criteria
- [ ] **AC-1**: `get_game_box_score()` batting query includes `LEFT JOIN team_rosters` per Technical Notes TN-2 and TN-3, returning `jersey_number` in each batting line dict.
- [ ] **AC-2**: `get_game_box_score()` pitching query includes `LEFT JOIN team_rosters` per Technical Notes TN-2 and TN-3, returning `jersey_number` in each pitching line dict.
- [ ] **AC-3**: `game_detail.html` batting table has a `#` column as the first column per Technical Notes TN-1. When `jersey_number` is NULL, the cell renders `—`.
- [ ] **AC-4**: `game_detail.html` pitching table has a `#` column as the first column per Technical Notes TN-1. When `jersey_number` is NULL, the cell renders `—`.
- [ ] **AC-5**: No batting or pitching rows are lost when a player has no `team_rosters` entry (LEFT JOIN correctness per TN-2).
- [ ] **AC-6**: New tests in `tests/test_db.py` verify: (a) `jersey_number` appears in box score batting/pitching results when a roster row exists, (b) `jersey_number` is `None` (not missing key) when no roster row exists.
- [ ] **AC-7**: Tests cover both ingestion paths within the same box score: set up a `membership_type='member'` team with a roster row (jersey number present, as populated by `RosterLoader`) AND a `membership_type='tracked'` opponent team -- one with a scouting-loaded roster row (jersey number present) and one without any roster row (jersey number `None`). Validates that the LEFT JOIN resolves correctly for both data sources in the same query. Per TN-4 item 3 and TN-5.
- [ ] **AC-8**: Template rendering tests in `tests/test_dashboard.py` verify: (a) `#` column header is present in game detail batting and pitching tables, (b) jersey number value renders in the cell, (c) em dash renders when jersey number is NULL.

## Technical Approach
Add `season_id` from the game row as a parameter to the batting and pitching queries in `get_game_box_score()`. Add `LEFT JOIN team_rosters tr ON tr.player_id = pgb.player_id AND tr.team_id = pgb.team_id AND tr.season_id = ?` to each query. Update `game_detail.html` with the new column. Add test cases per TN-4.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py` (modify `get_game_box_score` — extend `game_query` to SELECT `g.season_id`, add LEFT JOIN to batting/pitching queries)
- `src/api/templates/dashboard/game_detail.html`
- `tests/test_db.py` (add jersey number assertions to box score query tests)
- `tests/test_dashboard.py` (add template rendering assertions for `#` column in game detail)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Box score rows include players from both teams. The member team's players have roster data populated via `RosterLoader`; the opponent's players have roster data populated via `ScoutingLoader._load_roster()` (if scouting has run) or may have no roster row at all. The LEFT JOIN ensures all players appear regardless, with `jersey_number = None` when no roster row exists.
