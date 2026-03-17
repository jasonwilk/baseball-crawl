# E-100-05: Dashboard — INTEGER PK Migration

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`DONE`

## Description
After this story is complete, all dashboard routes and templates will use INTEGER team references instead of TEXT `team_id`. The `?team_id=` query parameter will accept integer values. `permitted_teams` comparisons will work with `list[int]`. No new dashboard features — purely INTEGER PK compatibility.

## Context
Dashboard routes currently receive TEXT team_id strings from `get_permitted_teams()`, pass them to db.py, and render them in templates. With E-100-01's INTEGER PK schema and E-100-02's data layer migration, all flows must use integers. There are 7 route handlers and 7+ templates referencing team_id.

## Acceptance Criteria
- [x] **AC-1**: All dashboard route handlers use INTEGER team_id values when calling db.py functions and comparing against `permitted_teams`.
- [x] **AC-2**: The `?team_id=` query parameter is parsed as `int`. Non-numeric values return HTTP 400. Non-existent or unpermitted team IDs return HTTP 403 (do not distinguish "doesn't exist" from "not permitted" — consistent with current dashboard behavior).
- [x] **AC-3**: `permitted_teams` (from `get_permitted_teams()`) is `list[int]`. All `in` comparisons use integer values.
- [x] **AC-4**: Helper functions (`_compute_wl()`, `_check_opponent_authorization()`, etc.) work with INTEGER team_id.
- [x] **AC-5**: All dashboard templates render INTEGER team IDs in links, form values, and selectors (e.g., `?team_id={{ team.id }}`).
- [x] **AC-6**: `_team_selector.html` partial renders INTEGER team IDs in dropdown options.
- [x] **AC-7**: Any `is_owned` references in dashboard code replaced with `membership_type`.
- [x] **AC-8**: Tests verify: (a) dashboard routes accept INTEGER team_id query params, (b) permitted_teams filtering works with integers, (c) game detail renders correct INTEGER team references, (d) non-numeric team_id query param returns HTTP 400, (e) unpermitted or non-existent INTEGER team_id returns HTTP 403.
- [x] **AC-9**: All dashboard test suites pass: `tests/test_dashboard.py`, `tests/test_dashboard_auth.py`.

## Technical Approach
The changes are mechanical: update parameter types, parse query params as int, update template variables. The data layer (db.py) was updated in E-100-02. This story does NOT modify `src/api/routes/admin.py` or admin templates (E-100-04 handles those).

## Dependencies
- **Blocked by**: E-100-02 (needs INTEGER-aware db.py/auth.py)
- **Blocks**: E-100-06

## Files to Create or Modify
- `src/api/routes/dashboard.py`
- `src/api/templates/dashboard/team_stats.html`
- `src/api/templates/dashboard/team_pitching.html`
- `src/api/templates/dashboard/game_list.html`
- `src/api/templates/dashboard/game_detail.html`
- `src/api/templates/dashboard/opponent_list.html`
- `src/api/templates/dashboard/opponent_detail.html`
- `src/api/templates/dashboard/player_profile.html`
- `src/api/templates/dashboard/_team_selector.html`
- `tests/test_dashboard.py`
- `tests/test_dashboard_auth.py`

## Agent Hint
software-engineer

## Definition of Done
- [x] All acceptance criteria pass
- [x] Tests written and passing
- [x] Code follows project style (see CLAUDE.md)

## Notes
- Dashboard does NOT gain program-awareness. No program-based navigation or filtering.
- Template changes may be minimal if templates render values generically — but links like `?team_id={{ team.team_id }}` must change to `?team_id={{ team.id }}`.
- **Scope reduction (2026-03-15)**: E-100-02 SE modified `src/api/routes/dashboard.py` as part of scope creep (accepted). Route handlers already use INTEGER team_id values, `int()` parsing, and `list[int]` for `permitted_teams`. Remaining work: templates, tests, and fixing the `_compute_wl(game: dict, team_id: str)` type hint bug at line 270 (`str` should be `int`).
