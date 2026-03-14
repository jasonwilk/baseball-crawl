# E-100-02: Data Layer — db.py + auth.py INTEGER PK

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, all query functions in `src/api/db.py` and the permission function in `src/api/auth.py` will use INTEGER team references (`teams.id`) instead of TEXT `team_id`. SQL JOINs will reference `teams.id`. `get_permitted_teams()` will return `list[int]`. Stub-INSERT helpers will use the INTEGER PK pattern with `membership_type`. All tests for db.py and auth.py will pass cleanly against the new schema — no xfail markers.

## Context
With E-100-01's INTEGER PK schema, every db.py function that joins on `teams.team_id` or passes TEXT team_id parameters is broken. There are ~30 query functions. `auth.py`'s `get_permitted_teams()` returns TEXT strings. All must change to INTEGER. This is the critical path between the schema (01) and all application code (03-05).

Fresh-start simplification: no xfail dance, no fixture-splitting across stories. This story updates db.py + auth.py + ALL their direct tests. Every test must pass. Route-handler tests for admin and dashboard (`test_admin.py`, `test_admin_teams.py`, `test_admin_opponents.py`) are updated by their respective stories (04, 05). However, `test_auth_routes.py` IS updated in this story — auth route tests break immediately when `get_permitted_teams()` changes its return type to `list[int]`, and auth.py is this story's core deliverable. This story does NOT modify templates, pipeline code, or admin/dashboard route handlers.

## Acceptance Criteria
- [ ] **AC-1**: All `db.py` query functions that JOIN on the teams table use `t.id` instead of `t.team_id`.
- [ ] **AC-2**: All `db.py` function signatures that accept `team_id: str` change to `team_id: int` where the parameter represents a DB team reference.
- [ ] **AC-3**: `get_teams_by_ids()` accepts `list[int]` and queries `WHERE id IN (...)`.
- [ ] **AC-4**: `get_team_batting_stats()`, `get_team_pitching_stats()`, `get_team_games()`, `get_team_opponents()` accept `team_id: int`.
- [ ] **AC-5**: `get_game_box_score()` returns INTEGER `home_team_id` and `away_team_id` values.
- [ ] **AC-6**: `get_opponent_scouting_report()` and `get_last_meeting()` accept INTEGER team_id parameters.
- [ ] **AC-7**: Opponent link functions use INTEGER `our_team_id` parameters.
- [ ] **AC-8**: `_generate_opponent_team_id()` is deleted — with INTEGER PK, stub teams no longer need a generated TEXT slug as their PK.
- [ ] **AC-9**: `is_owned_team_public_id()` is renamed and updated — uses `membership_type='member'` instead of `is_owned`.
- [ ] **AC-10**: Stub-INSERT patterns use `membership_type='tracked'` instead of `is_owned=0` and let SQLite auto-assign the INTEGER PK.
- [ ] **AC-10a**: `bulk_create_opponents()` rewritten: inserts with `membership_type='tracked'`, `is_active=0`, using INTEGER AUTOINCREMENT PK. No `team_id` TEXT slug, no `level`, no `is_owned`. Does not call `_generate_opponent_team_id()` (deleted by AC-8).
- [ ] **AC-11**: `auth.py` `get_permitted_teams()` returns `list[int]`. Uses `membership_type='member'` instead of `is_owned=1`.
- [ ] **AC-12**: `get_player_profile()` uses INTEGER team references.
- [ ] **AC-13**: All tests in `tests/test_auth.py`, `tests/test_auth_routes.py`, `tests/test_passkey.py` are updated and pass cleanly. No xfail markers. (`test_coaching_assignments.py` was rewritten in E-100-01 and should continue to pass.)
- [ ] **AC-13a**: A new `tests/test_db.py` covers the core db.py migration: INTEGER `team_id` parameters (ACs 1–7), stub-INSERT patterns capturing auto-assigned INTEGER PK (ACs 10–10a), and `get_permitted_teams()` returning `list[int]` (AC-11). Each AC-group has at least one test exercising the new integer contract.

## Technical Approach
Refer to the epic Technical Notes "db.py + auth.py INTEGER PK Migration" section. The changes are mechanical: update SQL JOIN patterns, change parameter types from `str` to `int`, update stub-INSERT patterns, delete `_generate_opponent_team_id()`. This story modifies ONLY `src/api/db.py`, `src/api/auth.py`, and their direct test files. It does NOT modify routes, templates, pipeline code, or route-level test files.

## Dependencies
- **Blocked by**: E-100-01 (needs INTEGER PK schema)
- **Blocks**: E-100-03, E-100-04, E-100-05

## Files to Create or Modify
- `src/api/db.py`
- `src/api/auth.py`
- `tests/test_db.py` (CREATE)
- `tests/test_auth.py`
- `tests/test_auth_routes.py`
- `tests/test_passkey.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-100-03**: All db.py functions accept INTEGER team_id. Pipeline code can call db.py with INTEGER values.
- **Produces for E-100-04**: Admin routes can call db.py with INTEGER team_id. `get_permitted_teams()` returns `list[int]`.
- **Produces for E-100-05**: Dashboard routes can call db.py with INTEGER team_id. `get_permitted_teams()` returns `list[int]`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing — no xfail markers
- [ ] Code follows project style (see CLAUDE.md)
