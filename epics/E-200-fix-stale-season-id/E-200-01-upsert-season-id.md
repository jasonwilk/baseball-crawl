# E-200-01: Add season_id to _upsert_game ON CONFLICT Clause

## Epic
[E-200: Fix Stale season_id on Pre-Existing Games](epic.md)

## Status
`TODO`

## Description
After this story is complete, the `_upsert_game` method in `game_loader.py` will include `season_id = excluded.season_id` in its ON CONFLICT DO UPDATE SET clause. This ensures that when a game row is re-upserted with a corrected season_id, the existing row's season_id is updated rather than left stale. A regression test will verify this behavior.

## Context
The root cause of the stale season_id bug: `_upsert_game` updates scores, dates, and team IDs on conflict but omits `season_id`. E-197 changed how season_ids are derived (year-only for teams without program_id), but existing game rows never pick up the new value on re-sync. This one-line fix prevents the bug from recurring.

## Acceptance Criteria
- [ ] **AC-1**: The `_upsert_game` method's ON CONFLICT DO UPDATE SET clause includes `season_id = excluded.season_id`.
- [ ] **AC-2**: A test exists that: (1) inserts a game with season_id `"old-season"`, (2) upserts the same game_id with season_id `"new-season"`, (3) asserts the row's season_id is `"new-season"` after the upsert.
- [ ] **AC-3**: All existing game_loader tests pass (no regressions). Test scope discovery per `/.claude/rules/testing.md` -- run all test files that import from `game_loader`.

## Technical Approach
The fix is a single line addition to the SQL in `_upsert_game` (around line 951 of `src/gamechanger/loaders/game_loader.py`). The test should use an in-memory SQLite database with the games table schema, exercise the upsert path twice with different season_ids, and verify the final value.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `/workspaces/baseball-crawl/src/gamechanger/loaders/game_loader.py` — add `season_id = excluded.season_id` to ON CONFLICT clause
- `/workspaces/baseball-crawl/tests/test_loaders/test_game_loader.py` — add regression test for season_id upsert

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The fix is intentionally minimal -- one line of SQL. The test is the main deliverable ensuring this doesn't regress.
