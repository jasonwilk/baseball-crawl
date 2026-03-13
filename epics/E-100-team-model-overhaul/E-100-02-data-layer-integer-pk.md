# E-100-02: Data Layer INTEGER PK — db.py + auth.py

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, all query functions in `src/api/db.py` and the permission function in `src/api/auth.py` will use INTEGER team references (`teams.id`) instead of TEXT `team_id`. SQL JOINs will reference `teams.id` (e.g., `JOIN teams t ON t.id = x.team_id`). The `get_permitted_teams()` function will return a list of integers. Stub-INSERT helpers in db.py will use the INTEGER PK pattern. This is the foundational data layer change that stories 03-05 depend on.

## Context
With E-100-01's INTEGER PK schema, every `db.py` function that joins on `teams.team_id` or passes TEXT team_id parameters is broken. There are ~30 query functions with 100+ `team_id` references. `auth.py`'s `get_permitted_teams()` returns TEXT strings that callers (dashboard, admin) compare against. All must change to INTEGER before any downstream code can function. This story is the critical path between the schema (01) and all application code (03-06).

## Acceptance Criteria
- [ ] **AC-1**: All `db.py` query functions that JOIN on the teams table use `t.id` instead of `t.team_id` (e.g., `JOIN teams t ON t.id = g.home_team_id`).
- [ ] **AC-2**: All `db.py` function signatures that accept `team_id: str` parameters change to `team_id: int` where the parameter represents a DB team reference.
- [ ] **AC-3**: `get_teams_by_ids()` accepts `list[int]` and queries `WHERE id IN (...)`.
- [ ] **AC-4**: `get_team_batting_stats()`, `get_team_pitching_stats()`, `get_team_games()`, `get_team_opponents()` accept `team_id: int`.
- [ ] **AC-5**: `get_game_detail()` returns INTEGER `home_team_id` and `away_team_id` values.
- [ ] **AC-6**: `get_opponent_scouting_report()` and `get_last_meeting()` accept INTEGER team_id parameters.
- [ ] **AC-7**: Opponent link functions (`get_opponent_links()`, `get_opponent_link_counts()`, `is_duplicate_opponent_public_id()`, `get_opponent_link_count_for_team()`) use INTEGER `our_team_id` parameters.
- [ ] **AC-8**: `_generate_opponent_team_id()` is removed or refactored — with INTEGER PK, stub teams no longer need a generated TEXT slug as their PK.
- [ ] **AC-9**: `is_owned_team_public_id()` is renamed and updated for the new schema (no `is_owned` column; uses `membership_type='member'`).
- [ ] **AC-10**: Stub-INSERT patterns in db.py (opponent discovery) use `membership_type='tracked'` instead of `is_owned=0` and let SQLite auto-assign the INTEGER PK.
- [ ] **AC-11**: `auth.py` `get_permitted_teams()` returns `list[int]` instead of `list[str]`. The admin query uses `membership_type='member'` instead of `is_owned=1`. The user_team_access query returns INTEGER team_id values.
- [ ] **AC-12**: `get_player_detail()` uses INTEGER team references in its queries.
- [ ] **AC-13**: All existing tests in `tests/test_dashboard.py`, `tests/test_admin.py`, `tests/test_admin_teams.py`, `tests/test_admin_opponents.py`, `tests/test_auth.py`, `tests/test_auth_routes.py`, `tests/test_schema_queries.py` are updated and pass.

## Technical Approach
Refer to the epic Technical Notes "db.py + auth.py INTEGER PK Migration" section. The changes are mechanical: update SQL JOIN patterns, change parameter types from `str` to `int`, update stub-INSERT patterns. The key constraint: this story modifies ONLY `src/api/db.py` and `src/api/auth.py` (plus their tests). It does NOT modify routes, templates, or pipeline code.

## Dependencies
- **Blocked by**: E-100-01 (needs INTEGER PK schema)
- **Blocks**: E-100-03, E-100-04, E-100-05, E-100-06

## Files to Create or Modify
- `src/api/db.py`
- `src/api/auth.py`
- `tests/test_dashboard.py` (db.py query tests)
- `tests/test_admin.py`
- `tests/test_admin_teams.py`
- `tests/test_admin_opponents.py`
- `tests/test_auth.py`
- `tests/test_auth_routes.py`
- `tests/test_schema_queries.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-100-03**: All db.py functions accept INTEGER team_id. Pipeline code can call db.py with INTEGER values.
- **Produces for E-100-04**: Admin routes can call db.py with INTEGER team_id. `get_permitted_teams()` returns `list[int]`.
- **Produces for E-100-05**: Dashboard routes can call db.py with INTEGER team_id. `get_permitted_teams()` returns `list[int]`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
