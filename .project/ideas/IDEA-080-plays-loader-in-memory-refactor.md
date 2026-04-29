# IDEA-080: PlaysLoader In-Memory Refactor + LoadResult.skipped Semantic Split

## Status
`CANDIDATE`

## Summary
Refactor `PlaysLoader` to accept `dict[game_id, raw_json]` directly instead of reading from a tempdir. Eliminates the tempdir hack that the shared `run_plays_stage` helper inherits from the original report-generator inline pattern. Bundle in cleaning up the `LoadResult.skipped` semantic conflation between idempotency-hit and FK-guard-skip outcomes (currently a single counter that conflates two distinct meanings).

## Why It Matters
The shared helper at `src/gamechanger/pipelines/plays_stage.py` currently writes per-game JSON to `tempfile.TemporaryDirectory()` and then reads it back via `PlaysLoader.load_all(tmp_dir)`. The disk round-trip is pure overhead on a hot path (every scout invocation across CLI, web, and reports). An in-memory `loader.load_dict({gid: raw_json, ...})` API would simplify the helper, eliminate the temp-dir machinery, and make per-game outcomes addressable -- which is the natural place to also split `LoadResult.skipped` into two distinct counters (idempotency-hit vs FK-guard-skip). Today operators see a single "skipped=N" number that hides whether the work was already done or whether the upstream `games` row was missing.

## Rough Timing
After E-229 has shipped and operators have used the new shared helper for a few weeks. Promote when: (a) tempdir-write performance shows up in profiling on bulk-mode scout runs, OR (b) a future pipeline change requires per-game `LoadResult` semantics that the aggregate result cannot express.

## Dependencies & Blockers
- [x] E-229 must be complete (helper exists; this idea refactors its internals)
- [ ] Confirm `PlaysLoader` has no other callers outside the helper + the standalone `bb data load --loader plays` path -- if any, plan for both call shapes simultaneously

## Open Questions
- Should the in-memory API replace `load_all(path)` or coexist with it (the standalone `bb data load --loader plays` operator command still wants a path-based API)?
- What is the right per-game return shape: `dict[game_id, LoadResult]` or a richer `PerGameLoadOutcome` dataclass with status enum?
- Does this refactor extend to other loaders (game_loader, scouting_loader) or stay scoped to `PlaysLoader`?

## Notes
Surfaced during E-229 planning + iter-1 review (Tech Notes "Test fixtures" + DE follow-up). Originally captured as one of the four follow-up ideas in E-229-05's closing AC; routed to PM-owned closure tasks per Codex-F1; filed at E-229 closure.

The `LoadResult.skipped` semantic conflation was added to this idea per DE follow-up Q2 (post-iter-1 incorporation): the aggregate counter today does not distinguish "the loader's pre-insert idempotency check fired" from "the FK guard rejected the load because `games` was missing." Both increment the same field, but they have different operator implications.

---
Created: 2026-04-29
Last reviewed: 2026-04-29
Review by: 2026-07-28
