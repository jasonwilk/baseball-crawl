# E-246-04: Hoist aggregate-parity SUM projections into shared builders

## Epic
[E-246: Dead-Code Removal & Low-Risk Consolidation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the season-aggregate SUM-projection bodies will live in one shared source that both `canonical_recompute` and the `verify-aggregates` parity check import, so the parity check can never silently sum a stale subset of columns when a new aggregate column is added.

## Context
The sweep's H1 finding: `_BATTING_RECOMPUTE_SQL` / `_PITCHING_RECOMPUTE_SQL` in `src/reports/aggregate_parity.py:103-188` are byte-for-byte copies of the SUM projections in `src/db/season_aggregates.py:105-124` and `:185-205`, kept in sync only by a comment. If someone adds a column to `canonical_recompute` but forgets the parity copy, `bb report verify-aggregates` silently sums a stale subset and reports false parity — defeating the integrity gate, which is exactly the hazard the data-model rule warns about. The canonical-recompute function is the protected entry point for rebuilding `boxscore_only` aggregates, so this consolidation hardens a documented integrity seam.

## Acceptance Criteria
- [ ] **AC-1**: Given the SUM projections are duplicated, when the story completes, then the projection bodies live in shared constants/builders in `src/db/season_aggregates.py`, and both `canonical_recompute` and `aggregate_parity.py` consume them (the parity module composes its own WHERE/scope around the shared projection rather than re-declaring the SUM list).
- [ ] **AC-2**: Given the shared projection (HARD GATE — stats integrity, per epic Technical Notes), when a golden-fixture/characterization test runs the SUM projection against representative season data, then the produced aggregate rows are byte-identical before and after this story. This must be a `pytest` test that pins the pre-change output and passes against the post-change code — not visual inspection. If equivalence cannot be proven, the story is cut, not shipped.
<!-- Note: the live-DB `bb report verify-aggregates` parity check is NOT an implementer AC for this story — it is a blocking epic-level pre-closure gate owned by the operator/closure sequence (see epic Technical Notes "Closure Gate (blocking)"). The implementer cannot run it (no `data/` or `bb` CLI in the worktree); their gate is AC-2's pytest proof. -->
- [ ] **AC-3**: Given a hypothetical new aggregate column added to the shared projection, when both consumers import it, then the parity check automatically includes the new column (no second edit site) — demonstrated by the single-source structure, not by adding a real column.
- [ ] **AC-4**: Given the consolidation, when `tests/test_aggregate_parity.py` (including the AC-2 golden-fixture/characterization test) runs, then it passes. (The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC — it is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/reports/aggregate_parity.py:103-188`, `src/db/season_aggregates.py:105-124`, `:185-205`. The constraint is that the SUM projection must be expressed exactly once and both the recompute and parity paths must reference it; the parity path differs only in its surrounding WHERE/scope, which it keeps. Reuse must not alter the `canonical_recompute` column set or its `boxscore_only`-only provenance ownership (see CLAUDE.md and `.claude/rules/data-model.md`). Output must be provably identical — lean on existing aggregate/parity tests, and add a focused test if none covers the projection equivalence.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/db/season_aggregates.py`
- `src/reports/aggregate_parity.py`
- `tests/test_aggregate_parity.py` (extend — add the golden-fixture/characterization test proving byte-identical projection output per AC-2; file exists today)

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Byte-identical aggregate output proven by a golden-fixture/characterization `pytest` test (AC-2)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
This is a byte-identical consolidation of a documented integrity seam — the value is preventing future silent drift, so the single-source structure is the deliverable.

**Phase 4b Codex finding (2026-06-30): AC-3 end-to-end closure.** Post-merge review found that `aggregate_parity.py` kept a SECOND manual column list (`_BATTING_COLUMNS`/`_PITCHING_COLUMNS`, the `diff_columns` mapping) separate from the `*_RECOMPUTE_KEYS` this story hoisted — `_check_table` only diffs columns in `diff_columns`, so AC-3's "no second edit site" held for the SUM projection but not end-to-end (a future column would be recomputed yet silently uncompared). No current integrity gap (`diff_columns` set == `RECOMPUTE_KEYS` today). Remediated in-dispatch by DE: `_BATTING_COLUMNS`/`_PITCHING_COLUMNS` derived from `*_RECOMPUTE_KEYS` (byte-preserving the current tuples; `cells_compared` stays 74) + guard tests pinning the single-source invariant. CR's byte-preservation verification confirmed APPROVED (byte-preserving; `cells_compared` still 74), so **AC-3 is now fully (end-to-end, literally) satisfied — no second edit site remains.** See epic History Phase 4b scorecard.
