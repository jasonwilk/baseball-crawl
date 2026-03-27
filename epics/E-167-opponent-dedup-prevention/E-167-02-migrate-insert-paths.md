# E-167-02: Migrate Pipeline INSERT Paths to Shared Function

## Epic
[E-167: Opponent Dedup Prevention and Resolution](epic.md)

## Status
`TODO`

## Description
After this story is complete, all pipeline team-INSERT paths will use `ensure_team_row()` from `src/db/teams.py` instead of their own inline dedup logic. The opponent seeder and resolver will also filter out `is_hidden=true` opponents. This eliminates the root cause of duplicate team creation.

## Context
SE identified 8 independent team-INSERT locations across 7 modules (see TN-3). Each currently implements its own lookup logic with different keys. This story replaces them all with calls to the shared function from E-167-01. Each individual change is mechanical (replace private method body with shared function call), but the aggregate blast radius spans many modules. The opponent_resolver has the most complex migration because `_ensure_opponent_team_row` contains resolver-specific logic beyond team creation.

## Acceptance Criteria
- [ ] **AC-1**: `schedule_loader._find_or_create_stub_team()` calls `ensure_team_row(db, name=..., season_year=..., source='schedule')` per TN-3. The `season_year` is derived from the loader's `self._season_id`. The method signature and return type are unchanged (still returns `int`).
- [ ] **AC-2**: `opponent_resolver._ensure_opponent_team_row()` uses `ensure_team_row()` for the team lookup/creation step per TN-3. Resolver-specific logic (the `_write_gc_uuid` / `_write_public_id` collision-safe helpers) that is already handled by the shared function's back-fill rules is removed. Any resolver-specific logic that is NOT handled by the shared function (if any) remains in the resolver as a thin wrapper.
- [ ] **AC-3**: `game_loader._ensure_team_row()`, `scouting.py._ensure_team_row()` and the standalone INSERT at `scouting.py` line 537, `roster._ensure_team_row()`, `season_stats_loader._ensure_team_row()`, and `scouting_loader` INSERT paths all call `ensure_team_row()` per TN-3.
- [ ] **AC-4**: The opponent seeder (`seed_schedule_opponents`) filters out entries where `is_hidden=true` from the opponents.json data before upserting into opponent_links, per TN-4.
- [ ] **AC-5**: The opponent resolver (`OpponentResolver._resolve_team`) skips opponents where `is_hidden=true` in the API response, per TN-4.
- [ ] **AC-6**: All existing tests pass. New tests verify the is_hidden filtering behavior in both seeder and resolver.
- [ ] **AC-7**: An integration test with an in-memory SQLite database and fixture data demonstrates that running the pipeline INSERT paths (schedule_loader stub creation, resolver team creation, game_loader/scouting team creation) for the same opponent through different paths does not create duplicate rows. The test should cover: (a) stub created first, then resolver finds by name; (b) resolver created first, then stub finds by name; (c) two resolvers with different gc_uuids for the same public_id.

## Technical Approach
For each path in TN-3, replace the inline INSERT/SELECT logic with a call to `ensure_team_row()`, passing the identifiers available to that caller. The opponent_resolver migration is the most involved: its 3-step lookup (gc_uuid → public_id WHERE gc_uuid IS NULL → INSERT) is replaced by a single `ensure_team_row()` call that implements the full cascade. The resolver's collision-safe `_write_gc_uuid` and `_write_public_id` helpers can likely be removed since the shared function handles back-fill. Verify by reading `_ensure_opponent_team_row` in full -- any logic beyond "find or create a team row" should remain.

For `is_hidden` filtering: in the seeder, filter the parsed `opponents.json` list before the upsert loop. In the resolver, add a `continue` check at the top of the per-opponent loop when the opponent dict has `is_hidden=true`.

## Dependencies
- **Blocked by**: E-167-01
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/schedule_loader.py` (modify)
- `src/gamechanger/crawlers/opponent_resolver.py` (modify)
- `src/gamechanger/loaders/game_loader.py` (modify)
- `src/gamechanger/crawlers/scouting.py` (modify)
- `src/gamechanger/loaders/roster.py` (modify)
- `src/gamechanger/loaders/season_stats_loader.py` (modify)
- `src/gamechanger/loaders/scouting_loader.py` (modify)
- `src/gamechanger/loaders/opponent_seeder.py` (modify)
- `tests/test_loaders/test_schedule_loader.py` (modify -- shared function usage)
- `tests/test_crawlers/test_opponent_resolver.py` (modify -- shared function usage, is_hidden filtering)
- `tests/test_opponent_seeder.py` (modify -- is_hidden filtering)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The admin add-team paths (`src/api/routes/admin.py`, `src/api/db.py`) are excluded from this migration (see Non-Goals in epic). They are user-initiated with URL input and have different dedup expectations.
- When removing the resolver's `_write_gc_uuid` / `_write_public_id` helpers, verify no other code calls them before deleting.
- The `source` parameter value for each caller is documented in TN-3. Use those values for consistency.
- The resolver's `_ensure_opponent_team_row` currently returns `tuple[int, str|None]` (team_id, public_id). After migration to the shared function (which returns `int`), the resolver wrapper must preserve its return signature by reading back the public_id from the DB row. Do not change the resolver's public API.
- Test scope discovery: after modifying these modules, grep for all test files that import from them and include the full discovered set. The Files section lists known test files but SE should verify against actual imports -- some test files may have been renamed or added since this story was written.
