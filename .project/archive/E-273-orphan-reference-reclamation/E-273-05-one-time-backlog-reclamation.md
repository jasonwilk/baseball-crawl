# E-273-05: One-time backlog reclamation one-shot + operator sequence

## Epic
[E-273: Reclaim Orphaned Reference Data After Report Deletion](epic.md)

## Status
`DONE`

## Description
After this story is complete, the operator can reclaim the existing 681 orphan teams / 14,326 orphan players in one controlled, quiescent-DB run via a throwaway `scripts/` one-shot that IMPORTS and calls `reclaim_orphan_reference_data` — no migration, no permanent CLI surface, zero duplicated predicates. The one-shot documents and prints the operator sequence (baseline re-snapshot → run → assert), and its post-run assertion uses the single-source invariant-count helper.

## Context
The 681/14,326 backlog exists NOW on the dev DB. The ongoing pass wired into `cleanup_expired_reports` (E-273-02) would eventually reclaim it, but that runs during a live `bb report generate` where the reap-then-gate could defer it (TN-5). A controlled `scripts/` one-shot run against a quiescent DB is safer and decoupled from the §8 generation race (team-lead decision (a)). It is a throwaway one-shot, NOT a permanent `bb data` command — matching the operator's prior pushback on one-off CLI repair commands and the DRY decision that a SQL migration/script would duplicate the reachability predicates (TN-9). The reconciliation baseline is already stale (561 vs 64), so the operator sequence must re-snapshot BEFORE the sweep and expect an exact no-diff after (TN-10).

## Acceptance Criteria
- [ ] **AC-1**: A `scripts/` one-shot IMPORTS `reclaim_orphan_reference_data` from `src/reports/lifecycle.py` and invokes it against the resolved DB — it does NOT re-implement the reclamation or re-inline any orphan query (DRY, per TN-9; import boundary `scripts/`→`src/` per `.claude/rules/architecture-subsystems.md`).
- [ ] **AC-2**: The one-shot prints the pre-run and post-run orphan counts using the E-273-01 single-source invariant-count helper, and reports the `ReclaimResult` counts, per TN-8.
- [ ] **AC-3**: The one-shot distinguishes THREE outcomes on `ReclaimResult` + the post-run count (CR S3 / SE MINOR-1 / DE F4 — do NOT conflate them): (a) `deferred=True` (a live generation was in flight, the guard refused, nothing ran) → exit non-zero with a DISTINCT message "deferred — a generation is in flight; re-run against a quiescent DB," NOT the same signal as a leak; (b) ran and post-run invariant count is zero → exit 0 (success); (c) ran and post-run count is non-zero → exit non-zero "reclamation left a residual — investigate" (a genuine overreach/leak). The operator must be able to tell "re-run when quiescent" from "reclamation is broken" from the exit code + message, per TN-5.
- [ ] **AC-4**: The one-shot documents the operator sequence (in its docstring / `--help` / printed guidance) per TN-10: re-snapshot the reconciliation baseline FIRST (`bb report reconcile-scoreboard --update-baseline`), then run the one-shot, then expect an EXACT no-diff (`bb report reconcile-scoreboard`) plus clean `PRAGMA foreign_key_check` / `PRAGMA integrity_check`. It states that the baseline re-snapshot is operator-owned (no agent runs `--update-baseline`).
- [ ] **AC-5**: The one-shot is idempotent — a second run against an already-clean DB deletes nothing and reports zero orphans (the terminate-after-zero-delta property, TN-1).
- [ ] **AC-6**: TWO tests exist (matching the Technical Approach + Files list): (a) a SUBPROCESS smoke test invoking the one-shot as a script (per `.claude/rules/testing.md` console/script-entry-point convention), and (b) an IN-PROCESS test that runs the one-shot against a temp DB seeded with orphans and asserts the backlog is reclaimed, the post-run invariant is zero, AND the three-way exit-code semantics of AC-3 (deferred / clean-zero / residual-leak) hold. Both are required, not "a test."

## Technical Approach
Create a throwaway one-shot under `scripts/` (thin wrapper: resolve the DB path via `resolve_db_path`, open a connection, call `reclaim_orphan_reference_data`, print pre/post counts via the invariant helper, and set the exit code per AC-3's three-way `deferred` / clean-zero / residual-leak distinction — never conflate a deferred guard-refusal with a genuine leak). Keep it a script — reusable logic already lives in `src/` (E-273-01). Document the TN-10 operator sequence in the script. Do NOT add a `bb data` subcommand. The docs/admin operator-runbook write-up is a closure obligation routed to docs-writer (TN-14), NOT part of this story. Follow the `scripts/` conventions (repo-root resolution, no `sys.path` hacks beyond a standalone-script bootstrap) per `.claude/rules/python-style.md`.

## Dependencies
- **Blocked by**: E-273-01 (imports the pass + helper)
- **Blocks**: None

## Files to Create or Modify
- `scripts/reclaim_orphan_reference_data.py` (new throwaway one-shot)
- `tests/test_reclaim_orphan_script.py` (NEW — the subprocess smoke test + the in-process backlog-reclamation + three-way exit-code test)

## Agent Hint
software-engineer

## Handoff Context
<!-- Terminal story; produces no artifact for a downstream story. The docs/admin runbook is a
     closure obligation to docs-writer (TN-14), not a downstream story here. -->

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The one-shot is deliberately decoupled from any concurrent generation (run it against a quiescent DB) so the reap-then-gate never has to defer it (TN-5/TN-10). The docs/admin operator runbook is handled at closure by docs-writer, not here.
