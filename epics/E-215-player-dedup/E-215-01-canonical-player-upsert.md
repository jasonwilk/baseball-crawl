# E-215-01: Canonical Player Upsert with Name-Preference Logic

## Epic
[E-215: Fix Player-Level Duplicates from Cross-Perspective Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, a shared `ensure_player_row()` function will exist in `src/db/players.py` that all 7 loader paths use to create or update player rows. The function implements the name-preference rule (per TN-1): name components are only updated when the incoming value is strictly longer than the stored value, preventing initials from overwriting full names. All existing loader-specific player upsert functions are replaced with calls to this shared function.

## Context
The root cause of name degradation is that two loaders (`roster.py:_upsert_player()` and `scouting_loader.py:_upsert_roster_player()`) unconditionally overwrite names on conflict. The game loader is too conservative (only upgrades from "Unknown"). A shared function with consistent "prefer longer" logic fixes all paths at once. This follows the established pattern of `ensure_team_row()` in `src/db/teams.py`.

## Acceptance Criteria
- [ ] **AC-1**: A new function `ensure_player_row(db, player_id, first_name, last_name)` exists in `src/db/players.py` that implements the name-preference rule per TN-1.
- [ ] **AC-2**: Given a player row with first_name="Oliver", when `ensure_player_row()` is called with first_name="O" for the same player_id, then the stored first_name remains "Oliver" (no downgrade).
- [ ] **AC-3**: Given a player row with first_name="O", when `ensure_player_row()` is called with first_name="Oliver" for the same player_id, then the stored first_name is updated to "Oliver" (upgrade).
- [ ] **AC-4**: Given a player row with first_name="Unknown", when `ensure_player_row()` is called with any non-"Unknown" first_name, then the stored first_name is updated (upgrade from stub).
- [ ] **AC-5**: The same upgrade-only logic applies to `last_name` independently.
- [ ] **AC-6**: All 7 loader paths listed in TN-8 call `ensure_player_row()` instead of their own inline player upsert SQL. For compound methods that also write to other tables (e.g., `scouting_loader._upsert_roster_player()` writes to both `players` and `team_rosters`), only the `players` INSERT/UPDATE is replaced; the `team_rosters` INSERT stays in the loader method.
- [ ] **AC-7**: Existing tests for each migrated loader continue to pass after the refactor.
- [ ] **AC-8**: Unit tests cover all 6 name-transition cases: Unknown->short, Unknown->full, short->full, full->short (no-op), same->same (no-op), full->Unknown (no-op).

## Technical Approach
Create `src/db/players.py` with a single `ensure_player_row()` function. The function uses an INSERT ... ON CONFLICT DO UPDATE with CASE expressions that compare LENGTH of incoming vs stored values, per TN-1. Then mechanically replace each of the 7 loader paths (listed in TN-8) to call this function instead of their inline SQL. The stub-only loaders (plays, spray_chart, season_stats, scouting_spray) pass "Unknown"/"Unknown" as before -- the shared function handles this correctly since "Unknown" won't overwrite a real name.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-215-03, E-215-04

## Files to Create or Modify
- `src/db/players.py` (CREATE)
- `src/gamechanger/loaders/roster.py` (MODIFY -- replace `_upsert_player`)
- `src/gamechanger/loaders/scouting_loader.py` (MODIFY -- replace inline upsert in `_upsert_roster_player`)
- `src/gamechanger/loaders/game_loader.py` (MODIFY -- replace `_ensure_player`)
- `src/gamechanger/loaders/plays_loader.py` (MODIFY -- replace `_ensure_player_stub`)
- `src/gamechanger/loaders/spray_chart_loader.py` (MODIFY -- replace `_ensure_stub_player`)
- `src/gamechanger/loaders/season_stats_loader.py` (MODIFY -- replace `_ensure_player_row`)
- `src/gamechanger/loaders/scouting_spray_loader.py` (MODIFY -- replace `_ensure_stub_player`)
- `tests/test_player_upsert.py` (CREATE -- unit tests for `ensure_player_row`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-215-03**: The `ensure_player_row()` function is used by the merge to update the canonical player's name to the best available after merge.
- **Produces for E-215-04**: The `ensure_player_row()` function is called by the prevention layer to ensure name quality on new inserts.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The 4 stub-only loaders (plays, spray_chart, season_stats, scouting_spray) can call `ensure_player_row(db, player_id, "Unknown", "Unknown")` -- the shared function's ON CONFLICT DO NOTHING-equivalent behavior for "Unknown" values preserves existing rows untouched.
