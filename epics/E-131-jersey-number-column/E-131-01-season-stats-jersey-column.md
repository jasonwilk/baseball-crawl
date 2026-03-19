# E-131-01: Season Stats Jersey Number Column

## Epic
[E-131: Jersey Number as Distinct Dashboard Column](epic.md)

## Status
`TODO`

## Description
After this story is complete, the team batting stats and team pitching stats tables will display jersey number as a dedicated `#` column (first column, before Player name) instead of inlining it with the player name. Players without a jersey number will show an em dash. No query changes needed -- both `get_team_batting_stats()` and `get_team_pitching_stats()` already return `jersey_number`.

## Context
The season stats templates already receive `jersey_number` from the query layer and render it inline as `#23 Smith`. This story extracts it into its own column per the UXD spec in Technical Notes TN-1. Pure template work.

The query layer (`get_team_batting_stats`, `get_team_pitching_stats`) already JOINs `team_rosters` and returns `jersey_number`. This works identically for member teams (roster-loaded data) and opponent/tracked teams (scouting-loaded data) since both paths write to the same `team_rosters.jersey_number` column. See epic Technical Notes TN-5.

## Acceptance Criteria
- [ ] **AC-1**: `team_stats.html` has a `#` column as the first column (before Player) per Technical Notes TN-1. The inline `{% if player.jersey_number %}#{{ player.jersey_number }} {% endif %}` is removed from the Player name cell.
- [ ] **AC-2**: `team_pitching.html` has a `#` column as the first column (before Player) per Technical Notes TN-1. The inline `{% if pitcher.jersey_number %}#{{ pitcher.jersey_number }} {% endif %}` is removed from the Player name cell.
- [ ] **AC-3**: When `jersey_number` is NULL, both tables render `—` (em dash) in the `#` cell.
- [ ] **AC-4**: Empty-state colspan is incremented: `team_stats.html` from 14 to 15, `team_pitching.html` from 12 to 13.
- [ ] **AC-5**: New or updated tests in `tests/test_dashboard.py` verify jersey number renders as a distinct column for both a `membership_type='member'` team (roster-loaded data) and a `membership_type='tracked'` team (scouting-loaded data). Both paths write to the same `team_rosters.jersey_number` column, so the template must handle both identically. Per TN-4 and TN-5.
- [ ] **AC-6**: Tests verify that when `jersey_number` is NULL, the rendered HTML contains `—` (em dash) in the `#` cell, not a blank cell.
- [ ] **AC-7**: Existing dashboard tests in `tests/test_dashboard.py` pass without regression.

## Technical Approach
Template-only changes to two files. Extract inline jersey number from the Player name cell into a new first-column `<th>`/`<td>`. Update colspan on empty-state rows.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/dashboard/team_stats.html`
- `src/api/templates/dashboard/team_pitching.html`
- `tests/test_dashboard.py` (add dual-path jersey number rendering tests)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
No query-layer changes needed -- `jersey_number` is already in the template context for both views. The season stats views can display data for any team (member or tracked), so tests must verify jersey number rendering works for both `membership_type` values.
