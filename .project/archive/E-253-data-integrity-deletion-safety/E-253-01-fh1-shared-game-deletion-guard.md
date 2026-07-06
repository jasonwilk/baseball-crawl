# E-253-01: F-H1 — Shared-Game Deletion Guard (discharges E-250-02 TN-5)

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`DONE`

## Description
After this story is complete, deleting a report will never destroy per-game or plays data that a still-live report depends on. When teams X and Y played each other and Y holds a live report, deleting X's report (and cleaning up X) must preserve the shared-game plays/stat rows under Y's perspective, so Y's pitcher FPS%/P-BF remain intact. This is the guard the E-250-02 TN-5 amendment declared REQUIRED-but-deferred to CE-3; completing it lifts the live operator "no report deletions" hold.

## Context
This is the epic's HEADLINE finding (F-H1, HIGH). See Technical Notes **TN-1** in the epic for the full destruction-path analysis. Summary: the unbounded anchor pass in `_delete_team_anchor_and_orphan_data` deletes `plays` rows by `batting_team_id`/`team_id` across ALL games and perspectives. That unboundedness is intentional FK-safety (the `team_id`/`batting_team_id` FKs have no `ON DELETE` clause, so `DELETE FROM teams` IntegrityErrors unless anchor rows are gone first). The fix therefore must both spare shared-game rows AND make the teams-row deletion conditional — extending the existing "retain the teams row when a game FK still references it" survivor pattern already present in `cascade_delete_team` / `cleanup_orphan_teams`.

The whole-game plays idempotency (`.claude/rules/data-model.md`) means destroyed shared-game plays are NEVER re-fetched on regeneration — the hole is permanent and silent. That is why this must be prevented at deletion time, not repaired after.

## Acceptance Criteria
- [ ] **AC-1**: Given teams X and Y that played a shared game, with Y holding a live `reports` row, when X's report is deleted and X's cleanup runs, then the `plays` and per-game stat rows for that shared game under Y's perspective (`perspective_team_id = Y`) survive — a query of Y's pitcher FPS%/P-BF over that game returns the same rows as before the deletion.
- [ ] **AC-2**: Given the same shared-game scenario, when X's cleanup runs, then X's `teams` row and the shared-game anchor rows it still references are RETAINED (not deleted), and the operation completes without a SQLite `IntegrityError` — the FK-safety survivor path per TN-1.
- [ ] **AC-3**: Given team X that shares NO game with any live-report team (a true orphan), when X's report is deleted, then X and all its data are fully cleaned up as before — this story does not regress the existing orphan-cleanup behavior.
- [ ] **AC-4**: The guard lives in / extends the canonical deletion helpers (`cascade_delete_team` / `cleanup_orphan_teams` in `src/reports/generator.py`) per TN-1 — no new parallel delete path is introduced; the admin/report delete callers remain thin wrappers.
- [ ] **AC-5**: A test reproduces the F-H1 destruction (asserts the hole would occur WITHOUT the guard) and then asserts the guard prevents it — a failing-then-passing regression test.

## Technical Approach
See epic Technical Notes **TN-1**. The problem: perspective-scoping the anchor DELETEs alone is insufficient because the teams-row delete then IntegrityErrors on the spared rows; the survivor pattern for the teams row must be extended to shared-game-with-live-report cases. The implementing agent decides the exact eligibility-check and DELETE-scoping mechanism. Do NOT introduce a new deletion path — extend the canonical helpers.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-253-07 (also modifies `src/reports/generator.py`; run E-253-01 first to isolate per-story diffs)

## Files to Create or Modify
- `src/reports/generator.py` (`cascade_delete_team` / `cleanup_orphan_teams` / `_delete_team_anchor_and_orphan_data` and the eligibility helper)
- `tests/test_report_generator.py` (or the appropriate deletion-path test module) — F-H1 regression test

## Agent Hint
software-engineer

## Handoff Context
- **Produces for the epic close**: once merged, the operator "no report deletions" hold (user decision 2026-07-04) is lifted. Flag this in the epic completion summary.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/data-model.md` "Cleanup-Detection Mirror Invariant" and "Whole-game idempotency"; CLAUDE.md canonical-deletion-helper convention.
