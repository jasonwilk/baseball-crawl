# E-167-01: Shared `ensure_team_row()` Function and Name Index Migration

## Epic
[E-167: Opponent Dedup Prevention and Resolution](epic.md)

## Status
`TODO`

## Description
After this story is complete, a new `src/db/teams.py` module will provide an `ensure_team_row()` function that implements the deterministic dedup cascade (gc_uuid → public_id → name+season_year → INSERT) with a self-tracking guard. A new migration adds a COLLATE NOCASE index on `name + season_year` to support name-based lookups. This is the foundation that all other stories in the epic depend on.

## Context
Eight independent team-INSERT locations across seven modules each use different dedup keys, creating duplicates when the same real-world opponent enters through different paths. This story extracts the dedup logic into a single shared function. Later stories (E-167-02) will migrate all callers to use it.

## Acceptance Criteria
- [ ] **AC-1**: `src/db/teams.py` exports an `ensure_team_row()` function with the signature and cascade behavior defined in TN-1. All identifier parameters (`name`, `gc_uuid`, `public_id`, `season_year`, `source`) are optional keyword-only arguments. Returns an `int` (teams.id).
- [ ] **AC-2**: The cascade lookup order is: gc_uuid → public_id (without `gc_uuid IS NULL` filter) → name+season_year+tracked → INSERT, per TN-1.
- [ ] **AC-3**: Back-fill rules per TN-1 are implemented. For gc_uuid and public_id matches (steps 1-2): gc_uuid and public_id are written only when existing row has NULL (collision-safe with pre-check), name is updated only when existing name equals the gc_uuid string (UUID-as-name stub), season_year is written only when existing row has NULL. For name+season_year matches (step 3): only season_year and name (UUID-as-name stub only) are back-filled. gc_uuid and public_id are NOT back-filled on name-only matches (heuristic match -- false positives are harder to undo than duplicates).
- [ ] **AC-4**: Self-tracking guard per TN-1: before creating a new tracked row, checks if the gc_uuid or public_id matches an existing member team. When both gc_uuid and public_id are NULL (name-only callers), also checks if the name matches an existing member team (case-insensitive). If any check matches, returns the member team's id without creating a tracked duplicate.
- [ ] **AC-5**: Migration 007 creates `idx_teams_name_season_year` index per TN-8.
- [ ] **AC-6**: Tests cover all four cascade steps (gc_uuid match, public_id match, name+season_year match, new INSERT), back-fill behavior (including the conservative step-3 rule: no gc_uuid/public_id back-fill on name matches), collision-safe writes, self-tracking guard (including the name-only path for scrimmage opponents matching member teams), UUID-as-name stub pattern, and multiple-name-match tie-breaking (lowest id wins).

## Technical Approach
Create `src/db/teams.py` with the `ensure_team_row()` function implementing the cascade from TN-1. The function is a pure database operation -- takes a `sqlite3.Connection` plus optional identifiers, returns an integer PK. No API client or config dependencies. The collision-safe gc_uuid/public_id write pattern already exists in `opponent_resolver._write_gc_uuid` / `_write_public_id` -- reuse that approach (SELECT for collision before UPDATE). Migration 007 goes in `migrations/007_teams_name_index.sql`.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-167-02, E-167-04

## Files to Create or Modify
- `src/db/teams.py` (create)
- `migrations/007_teams_name_index.sql` (create)
- `tests/test_ensure_team_row.py` (create)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-167-02**: The `ensure_team_row()` function that all pipeline INSERT paths will call. E-167-02 needs the function signature and cascade behavior.
- **Produces for E-167-04**: The `ensure_team_row()` function used by the resolution confirm endpoint to create/update team rows when the admin selects a GC search result.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `source` parameter is for logging/debugging (which pipeline path created the row), not for dedup logic. It maps to the existing `teams.source` column.
- The function should use `logging` for all dedup decisions (which step matched, what was back-filled, collision warnings).
- The name+season_year step uses `COLLATE NOCASE` for case-insensitive matching and `COALESCE(season_year, -1)` to group NULLs together (same pattern as `find_duplicate_teams()`).
- When multiple rows match in step 3 (name+season_year), return the row with the lowest `id` (oldest, most likely canonical). This is deterministic and consistent with the auto-merge canonical heuristic in TN-5.
- Step 3 back-fill is deliberately conservative: only `season_year` (when NULL) and `name` (UUID-as-name stub) are updated. gc_uuid and public_id are NOT written on name-only matches because the match is heuristic -- attaching an identifier to the wrong row is harder to undo than a duplicate.
