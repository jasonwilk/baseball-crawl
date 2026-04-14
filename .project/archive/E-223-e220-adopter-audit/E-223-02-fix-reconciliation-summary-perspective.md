# E-223-02: Fix Reconciliation Summary Perspective Double-Counting

## Epic
[E-223: E-220 Adopter Audit](./epic.md)

## Status
`DONE`

## Description
After this story is complete, `get_summary_from_db()` will not double-count discrepancy records when the same game has been reconciled from multiple perspectives. The current query aggregates all `reconciliation_discrepancies` rows without any perspective deduplication, inflating counts for cross-perspective games.

## Context
`src/reconciliation/engine.py::get_summary_from_db()` (lines 1162-1172) runs `GROUP BY signal_name, category, status` across the entire `reconciliation_discrepancies` table. When the same game is loaded from two team perspectives, each perspective can produce its own discrepancy records for the same underlying signal. The summary counts each perspective's record separately, inflating totals. This is a CLI-only path (`bb data reconcile --summary`).

## Acceptance Criteria
- [ ] **AC-1**: `get_summary_from_db()` deduplicates discrepancy records on the composite key `(game_id, team_id, player_id, signal_name)` so that each real-world discrepancy signal is counted once -- regardless of how many perspectives or reconciliation runs produced a record for it. When multiple rows exist for the same composite key with different statuses (e.g., `CORRECTABLE` in run 1, `CORRECTED` in run 2), the most recent row's status is used (ordered by `created_at DESC, rowid DESC` for deterministic tie-breaking).
- [ ] **AC-2**: Tests verify deduplication across both axes: (a) when the same game has discrepancy records from two different perspectives, the summary counts each unique signal once, not twice; (b) when the same signal has records from two different reconciliation runs with different statuses, only the most recent run's status is counted.

## Technical Approach
The `reconciliation_discrepancies` table has a UNIQUE constraint on `(run_id, game_id, perspective_team_id, team_id, player_id, signal_name)`. Double-counting is a two-level problem: (1) cross-perspective -- the same signal appears with different `perspective_team_id` values for the same game, and (2) cross-run -- each `bb data reconcile` invocation creates a new `run_id`, producing additional rows for the same signal. The dedup key `(game_id, team_id, player_id, signal_name)` collapses both dimensions -- but a naive `COUNT(DISTINCT key)` within `GROUP BY status` still counts a signal in multiple status buckets if its status changed across runs. The fix must first pick ONE row per composite key (the most recent, by `created_at` DESC) before grouping by status. A window function or subquery selecting the latest row per key is the natural approach. Existing test infrastructure in `tests/test_reconciliation.py` may need new fixtures with cross-perspective and cross-run discrepancy data.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reconciliation/engine.py` (modify -- `get_summary_from_db()`)
- `tests/test_reconciliation.py` (modify -- add cross-perspective and cross-run summary tests)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `reconciliation_discrepancies` table schema is in migration 001 (`001_initial_schema.sql`). Key columns for dedup: `game_id`, `team_id`, `player_id`, `signal_name`. The `perspective_team_id` and `run_id` columns are the two axes of duplication that the dedup key collapses.
