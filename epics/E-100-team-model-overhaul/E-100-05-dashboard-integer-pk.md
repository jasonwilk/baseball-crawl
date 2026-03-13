# E-100-05: Dashboard Routes + Templates INTEGER PK

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, all dashboard routes and templates will use INTEGER team references instead of TEXT `team_id`. The `?team_id=` query parameter will accept integer values. The `permitted_teams` comparison logic will work with `list[int]` (from auth.py E-100-02). Template links and selectors will use INTEGER team IDs. No new dashboard features are added — this is purely INTEGER PK compatibility.

## Context
Dashboard routes currently receive TEXT team_id strings from `get_permitted_teams()`, pass them to db.py query functions, and render them in templates. With E-100-01's INTEGER PK schema and E-100-02's data layer migration, all these flows must use integers. There are 7 dashboard route handlers and 7 dashboard templates that reference `team_id`.

## Acceptance Criteria
- [ ] **AC-1**: All dashboard route handlers (`team_stats`, `team_pitching`, `game_list`, `game_detail`, `opponent_list`, `opponent_detail`, `player_detail`) use INTEGER team_id values when calling db.py functions and comparing against `permitted_teams`.
- [ ] **AC-2**: The `?team_id=` query parameter is parsed as `int` (e.g., `int(request.query_params.get("team_id"))`). Invalid values return 400 or fall back to the default team.
- [ ] **AC-3**: `permitted_teams` (from `get_permitted_teams()`) is a `list[int]`. All `in` comparisons use integer values.
- [ ] **AC-4**: `_compute_wl()` and `_check_opponent_authorization()` helper functions work with INTEGER team_id parameters.
- [ ] **AC-5**: All dashboard templates render INTEGER team IDs in links, form values, and selectors (e.g., `?team_id={{ team.id }}`).
- [ ] **AC-6**: The `_team_selector.html` partial renders INTEGER team IDs in the dropdown options.
- [ ] **AC-7**: `is_owned` references in dashboard code (if any) are replaced with `membership_type`.
- [ ] **AC-8**: Tests verify: (a) dashboard routes accept INTEGER team_id query params, (b) permitted_teams filtering works with integers, (c) game detail renders correct INTEGER team references.

## Technical Approach
The changes are mechanical: update parameter types, parse query params as int, update template variables. The data layer (db.py) was updated in E-100-02 to accept INTEGER parameters — dashboard routes now pass integers to those functions. This story does NOT modify `src/api/routes/admin.py` or admin templates (E-100-04 handles those).

## Dependencies
- **Blocked by**: E-100-02 (needs INTEGER-aware db.py/auth.py)
- **Blocks**: None (E-100-06 does not depend on this)

## Files to Create or Modify
- `src/api/routes/dashboard.py`
- `src/api/templates/dashboard/team_stats.html`
- `src/api/templates/dashboard/team_pitching.html`
- `src/api/templates/dashboard/game_list.html`
- `src/api/templates/dashboard/game_detail.html`
- `src/api/templates/dashboard/opponent_list.html`
- `src/api/templates/dashboard/opponent_detail.html`
- `src/api/templates/dashboard/_team_selector.html`
- `tests/test_dashboard.py`
- `tests/test_dashboard_auth.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The dashboard does NOT gain program-awareness in this story. Program-first navigation is a separate future epic (Non-Goals).
- Template changes may be minimal if templates already render `team_id` values generically — integers render the same as strings in HTML. But links like `?team_id={{ team.team_id }}` must change to `?team_id={{ team.id }}`.
