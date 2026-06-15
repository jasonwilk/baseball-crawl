# E-236-07: Admin run-record view — surface partial/failed + derived operator-degraded

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, the operator's `/admin/reports` view (and the shared listing query) will surface the new honest per-stage statuses (`partial`/`failed`), the new count columns, and a derived "degraded" badge — making the run-record telemetry that stories 02-04 write actually legible to the operator. This is the operator surface for the epic; it is OPERATOR-ONLY (no coach-facing change).

## Context
E-235-06 added admin run-record surfacing via the shared `list_reports_with_runs` query (`src/api/db.py:59`) and operator-only trust-flag badges. This story extends that surface with the E-236 additions: the new count columns (TN-2), the new `"partial"` per-stage status value (TN-1), and the derived operator-degraded flag (TN-3). Per coach C3, partial-stage degradation is operator-only — it appears here, never on the coach footer (epic Technical Notes TN-3).

## Acceptance Criteria
- [ ] **AC-1**: `list_reports_with_runs` (`src/api/db.py:59`) selects the four new count columns (`boxscores_fetched`, `load_errors`, `plays_errors`, `spray_games_with_data`), staying NULL-safe for pre-migration rows (LEFT JOIN convention preserved).
- [ ] **AC-2**: The admin reports view (`/admin/reports`) renders per-stage statuses including the new `"partial"` value with a CHECKABLE distinct treatment — a `partial`-specific label and/or CSS class, distinct from `completed` and `failed`, assertable in a template/route test (CR SHOULD-6).
- [ ] **AC-3**: The view shows a derived operator-"degraded" indicator computed at read time as `overall_status == 'completed'` AND any per-stage status in (`'partial'`, `'failed'`), per Technical Notes TN-3. No schema column is added for it.
- [ ] **AC-4**: The new count columns are surfaced to the operator (e.g. as part of the per-stage detail) so a partial status is legible (how many of how many).
- [ ] **AC-5**: This change is operator-only — no coach-facing template (`scouting_report.html`) or coach copy is modified (Technical Notes TN-3).
- [ ] **AC-6**: The `bb report list` CLI surface (which shares `list_reports_with_runs`) is not broken by the query change (NULL-safe; existing columns unaffected).

## Technical Approach
Extend the SELECT in `list_reports_with_runs` with the four new columns. Update the admin reports template to render the `partial` status and the derived degraded badge; compute the derived flag in the route/view layer or template (read-time, no schema). Confirm the `bb report list` path still works (it consumes the same helper). Per the cleanup-detection-mirror discipline is not relevant here (no DELETE surface), but verify both consumers of the shared query stay green.

## Dependencies
- **Blocked by**: E-236-01, E-236-02, E-236-03, E-236-04, E-236-09
- **Blocks**: E-236-08

## Files to Create or Modify
- `src/api/db.py` (modify — `list_reports_with_runs` SELECT)
- `src/api/routes/admin.py` (modify — surface new columns + derived degraded if computed in the route)
- `src/api/templates/admin/reports.html` (modify — render partial status + degraded badge + counts)
- Admin reports tests (modify/add — locate via `grep -rl` per testing.md; e.g. `test_admin_reports`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
DE D1 (derived degraded). Depends on 02-04 so the surfaced data is real and the integration test in 08 has a populated view to assert against.
