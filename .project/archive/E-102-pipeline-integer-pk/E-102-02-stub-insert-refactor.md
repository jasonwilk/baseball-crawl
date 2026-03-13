# E-102-02: Stub-Insert Refactor Across Crawlers and Loaders

## Epic
[E-102: Pipeline INTEGER PK Migration](epic.md)

## Status
`TODO`

## Description
After this story is complete, all crawler and loader files that INSERT stub team rows for unknown opponents will use the INTEGER PK pattern: look up by `gc_uuid`/`public_id` (UNIQUE columns), INSERT if not found, capture `lastrowid`, and use the INTEGER `id` for all subsequent FK references. All pipeline SQL that references teams will use `teams.id` (INTEGER) instead of `team_id` (TEXT).

## Context
Six files in the pipeline INSERT stub team rows when encountering unknown opponents during crawl/load operations. With the E-100 INTEGER PK schema, these can no longer INSERT with a TEXT `team_id` as the PK — they must let SQLite auto-assign the INTEGER `id` and use it for FK references. The `TeamRef` resolution layer from E-102-01 provides the lookup helpers needed to resolve GC identifiers to INTEGER IDs.

## Acceptance Criteria
- [ ] **AC-1**: `src/gamechanger/loaders/game_loader.py` — all team-related SQL uses INTEGER `teams.id` for FK references. Stub team INSERTs use `gc_uuid`/`public_id` lookup + `lastrowid` pattern.
- [ ] **AC-2**: `src/gamechanger/loaders/roster.py` — team FK references use INTEGER `teams.id`.
- [ ] **AC-3**: `src/gamechanger/loaders/season_stats_loader.py` — team FK references use INTEGER `teams.id`.
- [ ] **AC-4**: `src/gamechanger/loaders/scouting_loader.py` — team FK references use INTEGER `teams.id`.
- [ ] **AC-5**: `src/gamechanger/crawlers/scouting.py` — team references use INTEGER `teams.id` where DB operations occur.
- [ ] **AC-6**: `src/gamechanger/crawlers/opponent_resolver.py` — team FK references use INTEGER `teams.id`.
- [ ] **AC-7**: No remaining `team_id TEXT` FK references in any pipeline SQL across the modified files.
- [ ] **AC-8**: All existing tests pass. Tests that verify stub-INSERT behavior are updated for INTEGER PK patterns.

## Technical Approach
Refer to the epic Technical Notes "Stub-Insert Refactor" section. The key pattern for each file: (1) check if team exists by external identifier using UNIQUE index, (2) if not, INSERT with auto-assigned INTEGER PK, (3) capture the ID (via `lastrowid` or `SELECT` after INSERT), (4) use that INTEGER ID for all FK references in subsequent operations.

## Dependencies
- **Blocked by**: E-102-01 (needs TeamRef resolution layer)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py`
- `src/gamechanger/loaders/roster.py`
- `src/gamechanger/loaders/season_stats_loader.py`
- `src/gamechanger/loaders/scouting_loader.py`
- `src/gamechanger/crawlers/scouting.py`
- `src/gamechanger/crawlers/opponent_resolver.py`
- Test files for the above (updates)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
