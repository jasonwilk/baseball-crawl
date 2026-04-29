# IDEA-081: PlaysLoader._load_game() Writes to game_perspectives

## Status
`CANDIDATE`

## Summary
After a successful per-game load, `PlaysLoader._load_game()` should `INSERT OR IGNORE` the corresponding `(game_id, perspective_team_id)` row into `game_perspectives`. Closes the gap for the standalone `bb data load --loader plays` path, which today bypasses the shared scouting load and so produces `plays` rows tagged with a perspective that may not be recorded in `game_perspectives`.

## Why It Matters
The `game_perspectives` table is the registry of which (game, team) pairs have been observed from which API perspective. Today the only writer is `src/gamechanger/loaders/game_loader.py:640-647`, which writes the row after boxscore load. `PlaysLoader._load_game()` does NOT itself INSERT into `game_perspectives` -- which is fine for E-229's three caller paths (CLI scout, web scout, report generator) because the upstream boxscore load runs BEFORE plays in all three. But the standalone `bb data load --loader plays` path bypasses boxscore load, which leaves `game_perspectives` un-populated for any game first seen via that path and breaks perspective-provenance MUST #5 there.

## Rough Timing
Promote when: (a) operators start using `bb data load --loader plays` for backfills or one-off loads, OR (b) a downstream consumer of `game_perspectives` notices gaps for plays-only loads.

## Dependencies & Blockers
- [x] E-229 must be complete (the shared helper's docstring already documents the upstream-population assumption -- once this idea ships, the helper's invariant relaxes)
- [ ] Confirm the `INSERT OR IGNORE` is idempotency-safe across all `PlaysLoader` callers

## Open Questions
- Should the loader-internal write happen on every per-game commit, or batched? (Per-game keeps consistency with the loader's existing per-game commit pattern.)
- After this ships, the shared `run_plays_stage` helper docstring invariant #3 ("`game_perspectives` rows are already populated") becomes redundant -- update the helper docstring at that time.

## Notes
Surfaced during E-229 planning iter-1, DE Q3 follow-up. Initial scope had the shared helper itself perform the `INSERT OR IGNORE`, but DE Q3 correctly observed that loader-internal behavior belongs in the loader, not in an orchestration helper. Helper out of `game_perspectives`; loader-internal write captured here.

This is a small, well-scoped change but should be co-tested against `bb data load --loader plays` to confirm the standalone path is also closed.

---
Created: 2026-04-29
Last reviewed: 2026-04-29
Review by: 2026-07-28
