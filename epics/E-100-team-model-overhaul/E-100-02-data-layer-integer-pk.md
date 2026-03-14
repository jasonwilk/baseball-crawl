# E-100-02: Data Layer — db.py + auth.py INTEGER PK

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, all query functions in `src/api/db.py` and the permission function in `src/api/auth.py` will use INTEGER team references (`teams.id`) instead of TEXT `team_id`. SQL JOINs will reference `teams.id`. `get_permitted_teams()` will return `list[int]`. Stub-INSERT helpers will use the INTEGER PK pattern with `membership_type`. All tests for db.py and auth.py will pass cleanly against the new schema — no xfail markers.

## Context
With E-100-01's INTEGER PK schema, every db.py function that joins on `teams.team_id` or passes TEXT team_id parameters is broken. There are ~30 query functions. `auth.py`'s `get_permitted_teams()` returns TEXT strings. All must change to INTEGER. This is the critical path between the schema (01) and all application code (03-05).

Fresh-start simplification: no xfail dance, no fixture-splitting across stories. This story updates db.py + auth.py + ALL their direct tests. Every test must pass. Route-handler tests (admin, dashboard) are updated by their respective stories (04, 05) — but this story does NOT need to touch those test files at all since they will be rewritten against the new schema in their own stories.

## Acceptance Criteria
- [ ] **AC-1**: All `db.py` query functions that JOIN on the teams table use `t.id` instead of `t.team_id`.
- [ ] **AC-2**: All `db.py` function signatures that accept `team_id: str` change to `team_id: int` where the parameter represents a DB team reference.
- [ ] **AC-3**: `get_teams_by_ids()` accepts `list[int]` and queries `WHERE id IN (...)`.
- [ ] **AC-4**: `get_team_batting_stats()`, `get_team_pitching_stats()`, `get_team_games()`, `get_team_opponents()` accept `team_id: int`.
- [ ] **AC-5**: `get_game_detail()` returns INTEGER `home_team_id` and `away_team_id` values.
- [ ] **AC-6**: `get_opponent_scouting_report()` and `get_last_meeting()` accept INTEGER team_id parameters.
- [ ] **AC-7**: Opponent link functions use INTEGER `our_team_id` parameters.
- [ ] **AC-8**: `_generate_opponent_team_id()` is deleted — with INTEGER PK, stub teams no longer need a generated TEXT slug as their PK.
- [ ] **AC-9**: `is_owned_team_public_id()` is renamed and updated — uses `membership_type='member'` instead of `is_owned`.
- [ ] **AC-10**: Stub-INSERT patterns use `membership_type='tracked'` instead of `is_owned=0` and let SQLite auto-assign the INTEGER PK.
- [ ] **AC-11**: `auth.py` `get_permitted_teams()` returns `list[int]`. Uses `membership_type='member'` instead of `is_owned=1`.
- [ ] **AC-12**: `get_player_detail()` uses INTEGER team references.
- [ ] **AC-13**: All tests in `tests/test_auth.py`, `tests/test_auth_routes.py`, `tests/test_coaching_assignments.py`, `tests/test_passkey.py` are updated and pass cleanly. No xfail markers.

## Technical Approach
Refer to the epic Technical Notes "db.py + auth.py INTEGER PK Migration" section. The changes are mechanical: update SQL JOIN patterns, change parameter types from `str` to `int`, update stub-INSERT patterns, delete `_generate_opponent_team_id()`. This story modifies ONLY `src/api/db.py`, `src/api/auth.py`, and their direct test files. It does NOT modify routes, templates, pipeline code, or route-level test files.

## Dependencies
- **Blocked by**: E-100-01 (needs INTEGER PK schema)
- **Blocks**: E-100-03, E-100-04, E-100-05

## Files to Create or Modify
- `src/api/db.py`
- `src/api/auth.py`
- `tests/test_auth.py`
- `tests/test_auth_routes.py`
- `tests/test_coaching_assignments.py`
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
