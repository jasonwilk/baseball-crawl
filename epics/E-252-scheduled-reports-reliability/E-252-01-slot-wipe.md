# E-252-01: Fix F-H2 slot-wipe: idempotency skip must not null report linkage

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, a same-day re-run of `bb report morning-run` that hits the idempotency skip branch for an already-generated slot no longer wipes that slot's `report_id`/`report_slug` from the `scheduled_report_runs` audit row. A subsequent run therefore recognizes the prior success and does not do a wasteful duplicate crawl + generate.

## Context
This is the epic's HIGH finding (F-H2). The documented daily workflow is: the morning run generates a report for a resolved opponent (run 1); the operator resolves a still-unresolved opponent with `bb report map-opponent`; the operator re-runs morning-run the same day (run 2). On run 2, the already-generated slot takes the idempotency skip branch in `_process_opponent` (`_prior_success` is true → `slot.delivery_status = "skipped"`, returned early). On that skip path the slot carries `report_slug = None`, so `_upsert_slot` looks up `report_id = None` and the `ON CONFLICT DO UPDATE` overwrites the audit row's `report_id`/`report_slug` with NULL. On the NEXT run (run 3), `_prior_success` now sees `report_id IS NULL`, returns false, and regenerates — a wasteful full duplicate crawl+generate. The bug was empirically reproduced in the audit.

The audit's fix direction: carry the prior slug/id onto the skip slot, OR `COALESCE` the existing values in the upsert so a NULL from a skip slot never overwrites a real linkage. See TN-3 for the audit-row invariants that must be preserved.

## Acceptance Criteria
- [ ] **AC-1**: Given a `scheduled_report_runs` row for `(own_team_id, opponent_root_team_id, game_date)` with a non-NULL `report_id` and `report_slug` from a prior successful generation, when a same-day re-run processes that slot and takes the idempotency skip branch, then the row's `report_id` and `report_slug` are unchanged (still non-NULL and pointing at the same report) after the upsert.
- [ ] **AC-2**: Given the run-1 → skip → run-3 sequence described in Context, when run 3 processes the slot, then `_prior_success` still returns true and no regeneration is attempted for that slot (the injectable generator is not called for it).
- [ ] **AC-3**: The idempotency skip continues to record `delivery_status='skipped'` on the slot, and the other audit-row columns (`resolution_outcome`, `resolved_public_id`, `opponent_name`, `updated_at`) are updated as before — only the report-linkage-wipe is corrected, per the audit-row invariants in TN-3.
- [ ] **AC-4**: A regression test reproduces the multi-run skip sequence (run 1 generates, run 2 skips, run 3 checks) against a real-schema `scheduled_report_runs` table and asserts AC-1 and AC-2. Per Technical Notes TN-8, the generator is injected/faked (no real HTTP).

## Technical Approach
Correct the interaction between the idempotency skip path in `_process_opponent` and `_upsert_slot` so a skip slot preserves the audit row's existing report linkage. The audit offers two viable shapes (carry the prior slug/id onto the skip slot, or COALESCE the existing values in the `ON CONFLICT DO UPDATE`); choose whichever is cleaner and keeps the upsert's other-column semantics intact. Preserve the non-NULL-key and FK-nulling invariants in TN-3. Verify against the `scheduled_report_runs` schema in `migrations/` and the contract in `.claude/rules/data-model.md` (Scheduled-Report Audit + Opponent Resolution).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-252-02 (same file `src/reports/morning_run.py`; the chain is 01→02→05→07). E-252-07 inherits this F-H2 fix transitively and must preserve it (its reserve-before-generate must not null the report linkage).

## Files to Create or Modify
- `src/reports/morning_run.py` (skip path in `_process_opponent` and/or `_upsert_slot`)
- `tests/test_morning_run.py` (or the existing morning-run test module) — regression test for the multi-run skip sequence

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-252-07**: The corrected slot-upsert / skip-path shape. E-252-07 further changes the slot lifecycle (reserve-before-generate, audit-write-in-isolation) and must build on this fix, not revert it.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (F-H2, HIGH): "Morning-run idempotency skip wipes `report_id`/`report_slug` from the audit row, causing duplicate regeneration on the next run" — `src/reports/morning_run.py:300`. Anchor reconciliation: the NULL overwrite itself happens in the `_upsert_slot` `ON CONFLICT DO UPDATE` (the audit's `:300`, within `_upsert_slot` ~L281-318), but the offending NULL-bearing skip slot is BUILT in the skip branch of `_process_opponent` (~L387, where `delivery_status='skipped'` is set with `report_slug` left None). Both functions are in play; the fix touches the skip-slot build and/or the upsert.
