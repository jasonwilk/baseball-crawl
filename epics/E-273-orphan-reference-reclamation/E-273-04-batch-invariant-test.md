# E-273-04: Batch invariant integration test (order-dependent, cross-perspective)

## Epic
[E-273: Reclaim Orphaned Reference Data After Report Deletion](epic.md)

## Status
`TODO`

## Description
After this story is complete, the test suite contains the batch deletion test that would have caught this class of orphan — the highest-value AC in the epic. It generates ≥3 reports sharing an opponent stub where at least one team is retained by a cross-perspective `games` FK, deletes all reports through the real wired `_delete_report` path, and asserts the single-source invariant-count helper returns zero — proving the fix works on the order-dependent, cross-perspective conditions that no single-report delete reproduces.

## Context
Order-dependence is the bug (RC#1), opponent stubs are the largest share (RC#2), and players are their own leak (RC#3) — none of the three reproduce on a single-report delete (handoff §9/§13). Every existing fixture is single-report or single-cascade; nothing sets up two reports where deleting A retains a team that deleting B then frees, and nothing asserts global post-delete state or covers the players leak. This story fills that gap. It asserts the invariant returns ZERO, not "the delete succeeded" (handoff §13 explicitly warns against the easy weaker test). It consumes the single-source invariant helper (TN-8), never re-inlining the query. It exercises the WIRED path (E-273-02), hence the dependency.

## Acceptance Criteria
- [ ] **AC-1**: Given ≥3 generated reports that SHARE at least one opponent stub, where at least one team is retained by a cross-perspective `games` FK (so a single delete would leave it as an RC#1 orphan), when the reports are deleted through the real `_delete_report` path, then: **(a) MID-SEQUENCE (CR M1 — the anti-vacuity gate): after the FIRST delete, assert the RC#1 retention was actually REALIZED — the shared team row still EXISTS and now has ZERO of its own `reports` rows (a retained orphan-in-waiting).** This proves the fixture genuinely created the order-dependent orphan and did not collapse under GameLoader dedup; without it the whole test can pass vacuously (no orphan ever created → invariant trivially zero → §13's "the easy test gets written" trap). **(b) THEN delete the remaining reports and assert the single-source invariant-count helper returns zero for all three orphan classes (teams, players, roster rows), per TN-8.** The final assertion is the invariant = zero, NOT "delete succeeded."
- [ ] **AC-2**: The test covers the players leak specifically — after the batch delete, players transitively orphaned by the deleted teams' rosters (including any reachable only via `plays`) are gone, and the transitively-dead-players count is zero, per TN-3.
- [ ] **AC-3**: The batch fixture MANDATORILY seeds the intentional survivors — a team referenced by `opponent_links.resolved_team_id` AND a team carrying a `user_team_access` grant — and the test asserts BOTH are NOT reclaimed and the invariant assertion does NOT flag them as leaks. Seeding these survivors is REQUIRED, not conditional (a "if present in the fixture" survivor assertion lets the story pass vacuously — the same anti-vacuity trap CR flagged in AC-1/M1, extended here). Per TN-7.
- [ ] **AC-4**: The test satisfies quiescence (all reports are `completed`/final before the deletes, no live `generating` report), so it asserts the clean zero — consistent with the TN-5 qualifier that a delete during a live generation legitimately defers the sweep.
- [ ] **AC-5**: The test consumes the E-273-01 single-source invariant-count helper; it does NOT re-inline its own copy of the orphan queries, per TN-8.

## Technical Approach
Add a batch-delete integration test (a new class/functions in `tests/test_admin_reports.py` — it deletes through `_delete_report`, whose route lives there; per TN-15 this keeps the story off `tests/test_report_generator.py`) shaped per handoff §13's "the test that would have caught this." **Fixture construction (SE MINOR-3): direct DB seeding is the lower-friction path** — the orphan conditions are a DB-STATE property, not a pipeline property, so seed `reports` + `games` + `game_perspectives` + `team_rosters` + stat rows directly rather than driving the real `generate_report()` pipeline (reach for the real pipeline only if needed). The hard part is reproducing "a team retained by a cross-perspective `games` FK across the delete sequence" (RC#1): seed a shared `games` row with two `game_perspectives` rows so the first `_delete_report` retains the team (cross-perspective FK still references it) and a later delete frees it. Delete the reports via the real `_delete_report`; run the MID-SEQUENCE retention assertion (AC-1a) after the first delete, then assert the imported invariant-count helper returns zero for all three classes. Include the players-leak assertion (AC-2) and the intentional-survivor assertion (AC-3). Do not re-inline the orphan queries. Use the disk-backed `db` fixture conventions per `.claude/rules/testing.md` (mind the self-`backup()` deadlock gotcha).

## Dependencies
- **Blocked by**: E-273-02 (the test deletes through the wired `_delete_report` path) — which transitively requires E-273-01 (the helper)
- **Blocks**: None

## Files to Create or Modify
- `tests/test_admin_reports.py` (the batch invariant test — deletes through `_delete_report`; per TN-15, story 04 stays off `test_report_generator.py`)

## Agent Hint
software-engineer

## Handoff Context
<!-- Terminal test story; produces no artifact for a downstream story. -->

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This is the epic's flagship AC. State the order-dependence explicitly in the test docstring so the easy single-delete test is never substituted for it. Per the TN-15 partition this story writes to `tests/test_admin_reports.py` (shared only with story 02, along the declared 02→04 edge) and does NOT touch `tests/test_report_generator.py`, so it has no cross-epic collision with E-270-03 (that overlap is story 03's, per TN-11).
