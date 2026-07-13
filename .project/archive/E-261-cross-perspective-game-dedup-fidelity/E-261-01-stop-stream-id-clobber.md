# E-261-01: Stop the redirect-path `game_stream_id` clobber

## Epic
[E-261: Cross-Perspective Game-Dedup Fidelity](./epic.md)

## Status
`DONE`

## Description
After this story, a cross-perspective dedup redirect no longer overwrites the canonical `games` row's non-null `game_stream_id` with the incoming perspective's value. The silent poisoning that currently happens on EVERY clean redirect stops, and the `UNIQUE constraint failed: games.game_stream_id` load error can no longer be triggered by the clobber write itself. Migration 010's header premise is corrected to match reality.

## Context
Defect A, first half (see epic Background). `_upsert_game` (`src/gamechanger/loaders/game_loader.py:~1131`) sets `game_stream_id = excluded.game_stream_id` unconditionally on `ON CONFLICT(game_id)`. For tracked-opponent games `game_stream_id` is perspective-specific (self-keyed to each row's own `event_id`), so the redirect path writes the wrong perspective's id onto the canonical row — poisoning it always, and violating migration 010's partial UNIQUE index whenever an un-merged twin row still owns that value. This story fixes the write semantics; the twin-merge half of Defect A is E-261-03b.

## Acceptance Criteria
- [ ] **AC-1**: Given a canonical row with a non-null `game_stream_id`, when a cross-perspective redirect upserts that `game_id` with a different incoming `game_stream_id`, then the canonical row's original `game_stream_id` is preserved (keep-existing semantics per Technical Notes TN-1).
- [ ] **AC-2**: Given the TN-2 Defect A seeded state (canonical row X + un-merged twin E, matching scores), when the own-perspective payload for E is loaded, then NO `UNIQUE constraint failed: games.game_stream_id` error occurs and `LoadResult.errors == 0`. (The twin row may still exist after this story — its merge is E-261-03b; this story only removes the erroring write.)
- [ ] **AC-3**: Given a first-time (non-conflict) game insert, when the game is loaded, then `game_stream_id` is written from the incoming summary exactly as today (no behavior change on the insert path).
- [ ] **AC-4**: Given the pre-fix loader, the new regression test from the TN-2 recipe fails; post-fix it passes; all existing tests in `tests/test_loaders/test_game_dedup.py` (including doubleheader cases c/d and the migration-010 no-regression test) still pass.
- [ ] **AC-5**: `migrations/010_game_dedup_backstop.sql`'s header comment no longer claims `game_stream_id` is "NULL (tracked) or stable across perspectives (member)"; it documents the actual tracked-game shape (non-null, perspective-specific, self-keyed), NAMES the retired authenticated game-summaries model as the source of the wrong premise (api-scout confirmed the scouting/public path is the sole populator post-E-239), and states why the index remains correct (comment-only edit; DDL unchanged).

## Technical Approach
Per TN-1: change the conflict clause to the keep-existing form `game_stream_id = COALESCE(games.game_stream_id, excluded.game_stream_id)` — the EXISTING column is the FIRST argument. **Do NOT copy the adjacent `start_time`/`timezone` argument order:** that COALESCE is `COALESCE(excluded.start_time, games.start_time)` = prefer-NEW, the OPPOSITE order. Copying it (`COALESCE(excluded.game_stream_id, games.game_stream_id)`) would still clobber the canonical value when both are non-null and reintroduce the bug. Use the literal existing-first form above. Add the TN-2 Defect A fixture to `tests/test_loaders/test_game_dedup.py` (note the `opponent_name` resolution trap documented there).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-261-03a (same file `game_loader.py`; serial ordering)

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (modify — `_upsert_game` conflict clause)
- `migrations/010_game_dedup_backstop.sql` (modify — header comment only)
- `tests/test_loaders/test_game_dedup.py` (modify — add regression tests)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-261-03a**: the corrected `_upsert_game` write semantics and the TN-2 Defect A fixture, which 03a/03b extend with the tolerant-signal and twin-merge assertions (one surviving row).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Keep-existing applies to ALL `_upsert_game` callers, not only redirects — TN-1 records why that is the intended shape. Do not touch the score columns in this story: cross-perspective score ownership is RESOLVED (keep-existing on the redirect path only; see epic TN-1 / Resolved Decisions) and is owned by E-261-03a, the story that introduces disagreeing-score redirects.
