# IDEA-149: E-261 Fail-Closed Twin Double-Counts in Non-Perspective-Scoped Game Reads

## Status
`CANDIDATE`

## Summary
E-261 hardened cross-perspective game-dedup but is deliberately bias-to-refuse: an ambiguous-date twin with score disagreement is left un-merged (fail-closed). Such a residual twin `games` row double-counts in the game-level report reads that are NOT perspective-scoped — `_query_record` (W-L), recent form, and runs-for/against average. Known territory (the operator corrective is `bb data merge-duplicate-games`), but this is a newly-identified query-surface consequence of the fail-closed residual. (Corner case CC-8.)

## Why It Matters
Coach-facing: a residual twin inflates the opponent's win-loss record, recent-form line, and runs averages on the report — the exact game-level numbers a coach reads first. Unlike the query-time season aggregates (which are perspective-scoped and safe), these game-level reads count `games` rows directly, so an un-merged twin is counted twice.

## Rough Timing
Promote on pain (a doubled W-L / runs line observed) or fold into E-267's game grain — E-267 reconciles loaded games against the fresh crawl and shares the `merge_duplicate_game` seam, so surfacing/retiring fail-closed residual twins is design-adjacent.

## Dependencies & Blockers
- [ ] Relates to E-261 (cross-perspective game-dedup fidelity, archived) and E-267 (reconcile-against-crawl). Decide whether this is an E-267 rider or its own small fix.

## Open Questions
- Should the fix make the non-perspective-scoped game-level reads twin-aware (dedup at query time), or push harder on merging the residual twins at load/operator time?
- What corroboration lets a fail-closed twin be safely merged that E-261 currently refuses (bias-to-refuse is intentional — don't weaken it blindly)?

## Notes
- Source: 2026-07-19 accumulate-only re-run audit, corner case CC-8 (single-channel fable sweep). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
- Related: E-261 (archived), E-267 (game grain), [[IDEA-134]] (play-level cross-perspective dup — same family).
- **Standing test requirement (operator directive 2026-07-19):** any future promotion MUST ship a regression test that reproduces the double-count (fails pre-fix — a residual twin inflates W-L/runs) and asserts the corrected count (passes post-fix). Gate every ingestion change against the E-257 reconciliation-scoreboard ratchet.

---
Created: 2026-07-19
Last reviewed: 2026-07-19
Review by: 2026-10-17 (suggest 90 days from created)
