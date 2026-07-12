# IDEA-124: Retire the per-game `_COMPLETENESS_RANK` dedup conflict-resolution (vestigial-by-convention)

## Status
`CANDIDATE`

## Summary
`src/db/player_dedup.py`'s `_COMPLETENESS_RANK` (`:473`, `{full:3, supplemented:2, boxscore_only:1}`) and the `dup_rank > can_rank` "duplicate wins on better completeness" branch in `_delete_or_update_game_stats` (`:764-776`) are **vestigial in production**: they arbitrate a per-game merge conflict by `stat_completeness`, but **no `src/` writer ever sets `full`/`supplemented` on `player_game_batting`/`player_game_pitching`** (verified during E-259-02 dispatch — the only per-game `stat_completeness` touch is the RANK's own READ). Since the column is `NOT NULL DEFAULT 'boxscore_only'` (migration 001), every per-game row is `boxscore_only`, so `dup_rank == can_rank` always and the dup-wins branch is **unreachable on real data**. Simplifying `_delete_or_update_game_stats` to "canonical always wins on a same-perspective conflict" (delete the duplicate) is production-behavior-preserving and removes the RANK + the unreachable branch.

## Why It Matters
Dead-code hygiene: the RANK encodes a per-game data-quality intent ("on merge, keep the richer per-game row") that no live path can trigger. Retiring it simplifies the dedup conflict-resolution to one obvious rule.

**Two reasons it was DEFERRED out of E-259-02 (dispatch, 2026-07-12), not a reason to skip it:**
1. Its vestigial-ness is **independent of the E-259 season-aggregate cutover** — it is per-game conflict-resolution, not a season/member guard (E-259-02's story mislabeled it a season guard). Bundling it into "retire the season write paths" was a scope error.
2. Removing it deletes a real test — `tests/test_player_dedup.py:~588` (the "Row with better stat_completeness is kept in game-level conflict" case) deliberately seeds a `full` per-game row and asserts the dup-wins behavior. The `stat_completeness` CHECK constraint still **permits** `full`/`supplemented` per-game rows, so the guard defends a **schema-permitted (if writer-absent) state**. Deleting it removes documented data-quality intent — a scoped decision deserving its own eyes, not a rider.

## Rough Timing
A dedicated per-game dedup-simplification pass. No urgency — it is dead code, not a bug. Promote when a dedup-focused cleanup epic is planned, OR reconsider (keep it) if a future feature ever sets `full`/`supplemented` on per-game rows (e.g. per-game member-data enrichment), which would make the guard live again.

## Dependencies & Blockers
- [ ] None hard. Independent of E-259 (the season cutover does not touch per-game completeness).

## Open Questions
- Should the `stat_completeness` **CHECK** on `player_game_*` be narrowed to `'boxscore_only'` only (making the vestigial-ness a schema guarantee, not a convention) as part of the same pass — or left permissive in case per-game member enrichment is ever added?
- Delete `test_player_dedup.py`'s dup-wins case, or convert it to a guard that asserts no per-game row carries `full`/`supplemented`?

## Notes
Surfaced by DE + verified by PM (schema + zero-writer trace) during E-259-02 dispatch, 2026-07-12 — the Q3 deferral. **Domain: data-engineer** (`src/db/player_dedup.py`). Related: E-259-02 story file's DISPATCH CORRECTION block records the full trace.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
