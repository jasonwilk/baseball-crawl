# E-253-09: Reconcile Atomicity + Perspective Partition

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`TODO`

## Description
After this story is complete, reconciliation `--execute` will record its discrepancy rows atomically with the plays corrections (a crash can no longer leave corrections applied but unrecorded), and `get_summary_from_db` will partition by `perspective_team_id` so distinct cross-perspective signals are no longer collapsed. Both are designed scoreboard-compatible.

## Context
Two LOW findings in `src/reconciliation/engine.py`, both scoreboard-relevant ("align, don't build" per epic TN-7):
- **Commit ordering** (`:1124`): `--execute` commits the per-team `plays.pitcher_id` corrections (`conn.commit()`) before the discrepancy rows are written; a crash in that window leaves the corrections applied but unrecorded — the `reconciliation_discrepancies` audit trail loses them.
- **Perspective partition** (`:1161`): `get_summary_from_db`'s dedup `PARTITION BY game_id, team_id, player_id, signal_name` omits `perspective_team_id`, collapsing distinct cross-perspective signals. The function's own docstring documents this as a known limitation; the audit flags it because the future E-245 scoreboard's player-level grain depends on the partition being perspective-aware.

## Acceptance Criteria
- [ ] **AC-1**: Given a reconciliation `--execute` that applies corrections, when it commits, then the plays corrections AND their `reconciliation_discrepancies` records commit atomically (in one transaction / same commit boundary), so no crash window can leave corrections applied but unrecorded. Proven by a test.
- [ ] **AC-2**: Given reconciliation discrepancy rows for the same real-world signal recorded under two different perspectives, when `get_summary_from_db` aggregates, then the two perspectives are NOT collapsed — the dedup partition includes `perspective_team_id`. Proven by a test with two-perspective fixtures.
- [ ] **AC-3**: The `get_summary_from_db` docstring is updated to reflect the perspective-aware partition (the old "cross-perspective limitation" note no longer describes the behavior).
- [ ] **AC-4**: Both fixes are designed scoreboard-compatible per TN-7 (the atomic discrepancy record and the perspective-aware summary are the grains the future E-245 scoreboard consumes) — this story does NOT build the scoreboard.

## Technical Approach
See epic Technical Notes **TN-7**. The two fixes are independent and both in `engine.py`. The implementing agent owns the transaction-boundary restructuring and the partition-key change. Preserve the existing "most recent row wins" dedup semantics; only add `perspective_team_id` to the partition.

**Implementer heads-up (SE)**: the atomicity fix spans a helper (the correction commit at `engine.py:1124`) and its caller (the discrepancy-row write, ~`engine.py:274`) — keep the transaction boundary **per-game** (do not widen it across games), and heed the shared-connection partial-commit footgun in `.claude/rules/architecture-subsystems.md` ("Shared-connection partial-commit footgun"): a multi-item loop on one connection must `rollback()` a failed item before the next, or its uncommitted writes get committed by the next success.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reconciliation/engine.py` (commit ordering ~line 1124; `get_summary_from_db` partition ~line 1161)
- `tests/` — atomicity test (corrections + discrepancy rows commit together) + two-perspective summary test

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/perspective-provenance.md` (perspective-specific `player_id`), `.claude/rules/architecture-subsystems.md` (Reconciliation Package).
