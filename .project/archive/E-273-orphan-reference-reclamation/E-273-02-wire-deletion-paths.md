# E-273-02: Wire reclamation into deletion paths with reap-then-gate concurrency guard

## Epic
[E-273: Reclaim Orphaned Reference Data After Report Deletion](epic.md)

## Status
`DONE`

## Description
After this story is complete, `reclaim_orphan_reference_data` runs automatically at the end of every deletion path — `_delete_report` (unconditionally, after the cascade) and `cleanup_expired_reports` — so the ownership invariant self-heals after any delete, and it never deletes an in-flight generation's data. This is what makes the fix a structural invariant rather than a one-time cleanup.

## Context
The pass attaches to the delete paths (`_delete_report`) plus the opportunistic-cleanup trigger `cleanup_expired_reports` — NOT `_cleanup_orphans` (TN-4, SE correction superseding handoff §7.4). Note (CR S1): `cleanup_expired_reports` is not delete-only — it ALSO runs at the START of every `generate_report` (generator.py:1503); that invocation is safe by construction (the run's scouted team isn't committed yet; concurrent generations covered by the reap-then-gate). `_delete_report` is a 2N structure: conn1 deletes the report row+file and commits (reports_admin.py:583-616), then conn2 runs `cascade_delete_team` and commits internally, opened only `if eligible`. The reclamation must run at the very end on a fresh connection REGARDLESS of `eligible` — a different report's deletion may have freed teams even when this one's team is not eligible (RC#2). It must NOT be wired into `_cleanup_orphans` (generator.py:2236), which already does precise TN-4 created-set cleanup and whose own `reports` row is `generating` there. The concurrency guard (reap-then-gate on `status='generating'`) lives inside the pass (E-273-01 AC-7); this story verifies the guard holds at the real wiring sites.

## Acceptance Criteria
- [ ] **AC-1**: Given a report whose deletion (via `_delete_report`) frees an orphan team, when the delete completes, then `reclaim_orphan_reference_data` has run and the freed team is reclaimed — asserted by the invariant-count helper returning zero, per TN-4/TN-8.
- [ ] **AC-2**: Given a `_delete_report` call where the report's own team is NOT eligible for cascade (conn2 never opens) but a prior deletion left an orphan, when this delete completes, then the reclamation still runs (unconditional, at the very end, on a fresh connection after conn1/conn2) and the orphan is reclaimed, per TN-4.
- [ ] **AC-3**: Given `cleanup_expired_reports` runs, when it completes, then the reclamation has run after the stale-generating reap, per TN-4. Note (CR S1): `cleanup_expired_reports` fires BOTH on the no-operator-action expiry trigger AND at the START of every `generate_report` (`generator.py:1503`); the generation-start invocation is safe because the current run's scouted team is not committed yet (`_ensure_team_row` is a later `run()` step) and concurrent generations are covered by the reap-then-gate. A test confirms the generation-start invocation does not delete the run's own (not-yet-created) team.
- [ ] **AC-4**: Given a live `generating` report exists during a deletion, when the deletion path invokes the pass, then the sweep is DEFERRED (no reference rows deleted) — after the reaper runs, a stale `generating` row does NOT block it, but a genuinely-live one does — per TN-5. The named failure mode is a liveness delay, never deletion of a live generation's data.
- [ ] **AC-5**: The pass is NOT wired into `_cleanup_orphans` (generator.py:2236): a test spies on `reclaim_orphan_reference_data` and asserts that a report generation's `_cleanup_orphans` invocation makes ZERO calls to it, while the created-set cleanup still removes the run's own orphan stubs as before. (Single observable check — a spy-call-count assertion, not code inspection.) Per TN-4.
- [ ] **AC-6**: `opponent_links` operator-decision rows and `user_team_access` grants survive every deletion-path invocation of the pass (regression coverage that the wiring did not reintroduce the §6.1 destruction), per TN-7.

## Technical Approach
Wire `reclaim_orphan_reference_data(conn)` (from E-273-01) at the end of `_delete_report` (`src/api/routes/reports_admin.py`) on a fresh connection after the existing conn1/conn2 sequence, unconditionally, and into `cleanup_expired_reports` (`src/reports/lifecycle.py`) after its existing stale-generating reap. Do NOT wire it into `_cleanup_orphans`. The reap-then-gate guard already lives inside the pass (E-273-01), so these sites just call it; add tests that exercise the guard at the wiring sites. **Double-reap (SE MINOR-2):** `cleanup_expired_reports` already reaps at `lifecycle.py:231` and the pass reaps internally — this is harmless (idempotent); leave BOTH, do NOT remove the pass's internal reap (it makes the guard self-contained) and do NOT treat the call-site reap as dead code. Follow TN-4 (wiring), TN-5 (guard behavior), TN-7 (opponent_links/user_team_access survival). Run test-scope discovery for both modified modules per `.claude/rules/testing.md`.

## Dependencies
- **Blocked by**: E-273-01 (defines the pass)
- **Blocks**: E-273-04 (the batch test exercises the wired `_delete_report` path)

## Files to Create or Modify
- `src/api/routes/reports_admin.py` (wire into `_delete_report`)
- `src/reports/lifecycle.py` (wire into `cleanup_expired_reports`)
- `tests/test_admin_reports.py` (delete-path wiring + guard tests)
- `tests/test_orphan_reclamation.py` (cleanup_expired_reports wiring test — colocated with story 01's pass tests, per TN-15)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-273-04**: the wired `_delete_report` path the batch test deletes through.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (run test-scope discovery for `reports_admin.py` and `lifecycle.py`)

## Notes
Both E-273-01 and this story edit `src/reports/lifecycle.py`, hence the dependency ordering (02 after 01).
