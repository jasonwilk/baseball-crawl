# E-235-05: Cleanup-mirror — wire `report_generation_runs` into report/team delete paths

## Epic
[E-235: Report Run Records, Trust Signals & Quality Gates](../E-235-report-run-records/epic.md)

## Status
`TODO`

## Description
After this story is complete, every code path that deletes a `reports` row (or a `teams` row whose reports are removed) also removes the associated `report_generation_runs` rows, so the new run table never orphans rows or blocks a delete. The cleanup-detection mirror invariant is satisfied for the new table.

## Context
`report_generation_runs` FK-references `reports`. Per the "Cleanup-Detection Mirror Invariant" in `.claude/rules/data-model.md`, adding a table that references `reports` obligates this epic to update every delete/detection path in the same change — DE was explicit this is a required story, not an afterthought. `ON DELETE CASCADE` only fires when the deleting connection has `PRAGMA foreign_keys = ON`, so the cleanup must either verify that pragma or delete the run rows explicitly. The known delete site, the mechanism choice, and the audit obligation are in **epic Technical Notes §TN-5**.

## Acceptance Criteria
- [ ] **AC-1**: Deleting a report (`src/api/routes/admin.py::_delete_report`, which runs `DELETE FROM reports WHERE id = ?`) removes its `report_generation_runs` row(s) — either via `ON DELETE CASCADE` (pragma confirmed on the connection that deletes the reports row) or an explicit `DELETE FROM report_generation_runs WHERE report_id = ?`. The two-connection structure of `_delete_report` is respected per §TN-5: with the explicit mechanism the run-row delete lands in **conn1, before `DELETE FROM reports`**, not in the conn2 cascade block; with CASCADE, `foreign_keys=ON` is confirmed on conn1 (`get_connection()` sets it — §TN-5/SE-F6). Proven by a test that runs against `get_connection()` (or replicates the pragma — a bare `sqlite3.connect()` has FKs OFF and gives a false result): create a run row, delete the report, assert the run row is gone. Per §TN-5.
- [ ] **AC-2**: Every path that deletes a `reports` row or a `teams` row with associated reports is audited (`_delete_report`, the admin team-delete cascade via `cascade_delete_team`, and the delete-confirmation/detection queries such as `_get_delete_confirmation_data`); each is updated where it must handle `report_generation_runs`, in lock-step. Per §TN-5.
- [ ] **AC-3**: The audit explicitly determines whether `report_generation_runs` belongs in the `cross_persp_rows` per-perspective detection UNION and records the conclusion in a NAMED location — a code comment at the `cross_persp_rows` site in `src/api/routes/admin.py` (and/or this story's Notes) — so a reviewer can confirm it (it is report-scoped telemetry, not a per-player stat table — confirm rather than assume). Per §TN-5.
- [ ] **AC-4**: No delete path raises an integrity error due to the new FK; a test exercises report deletion and team-delete cascade with a populated run row present.
- [ ] **AC-5**: E-234 guards stay green; no change to generation behavior (delete-path only).

## Technical Approach
Pick the cascade-vs-explicit-delete mechanism per §TN-5 and apply it at the report-deletion site. Grep for every `DELETE FROM reports`, every caller of `cascade_delete_team`, and the delete-confirmation/detection queries that mirror the report/team delete surface; update each that must account for the new table. Add a test that creates a `report_generation_runs` row and verifies it is removed when its report is deleted, and that team-delete cascade with a present run row does not error. Coordinate with story 04's settled `generator.py` deletion surface (this story is sequenced after it).

## Dependencies
- **Blocked by**: E-235-01, E-235-04
- **Blocks**: E-235-06 (serializes `src/api/routes/admin.py` edits)

## Files to Create or Modify
- `src/api/routes/admin.py` (`_delete_report`; audit `_get_delete_confirmation_data` / `cross_persp_rows`)
- `src/reports/generator.py` (if the team-delete cascade path needs to handle the run table)
- `tests/` (report-deletion + team-cascade tests covering the new table; e.g. `tests/test_admin_*` or `tests/test_report_generator.py`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (E-234 guards green)

## Notes
This is the mirror-invariant class that has bitten the project before (data-model.md). Treat the audit (AC-2/AC-3) as load-bearing, not a formality — confirm each path explicitly.
