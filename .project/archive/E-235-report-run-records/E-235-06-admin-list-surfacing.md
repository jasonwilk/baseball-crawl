# E-235-06: Surface run records + trust flags in the admin reports list

## Epic
[E-235: Report Run Records, Trust Signals & Quality Gates](../E-235-report-run-records/epic.md)

## Status
`DONE`

## Description
After this story is complete, the admin reports list shows each report's per-stage detail and counts, the operator-only trust flags (season fallback, name-only identity), and the existing `error_message`, replacing the binary ready/failed view. The operator can tell a degraded report from a complete one at a glance.

## Context
Today the report listing returns only `slug`/`title`/`status`/`generated_at`/`expires_at`/`url`/`is_expired`; `error_message` exists on the row but is never returned (ROADMAP §2). Two list paths read reports — the CLI `list_reports()` in `src/reports/generator.py` (used by `bb report list`) and the admin route's data function + `admin/reports.html` (used by `/admin/reports`) — and BOTH must join the run record (1:1 via `UNIQUE(report_id)`). The operator-only flags surface here, NOT in the coach footer (story 07). The surfacing requirements are in **epic Technical Notes §TN-6**.

## Acceptance Criteria
- [ ] **AC-1**: The admin reports list (`/admin/reports` via its data function + `admin/reports.html`) shows, per report, the per-stage status/counts from `report_generation_runs` and replaces the binary ready/failed display with stage-aware detail. The status badges (which switch on `report.status` in `reports.html`) gain handling for the `no_games` status value introduced by story 03 (§TN-3). Per §TN-6.
- [ ] **AC-2**: The operator-only trust flags (`season_fallback`, `identity_match_method = 'name_only'`) are surfaced in the admin list. **Note (Codex P2)**: `error_message` is ALREADY selected by `_get_all_reports` (admin.py:3222) and rendered for failed rows (`reports.html:71`), so the admin-web delta here is the per-stage detail + operator flags, NOT error_message. The path that lacks `error_message` is the CLI `list_reports()` (AC-3). Per §TN-6.
- [ ] **AC-3**: Both report-listing paths join the run record: the CLI `list_reports()` in `src/reports/generator.py` and the admin route's data function. The CLI `list_reports()` also gains `error_message` in its returned dict (it does not select it today, unlike the admin web path). A report with no run row (legacy/pre-migration) renders without error (NULL-safe LEFT join). Prefer factoring the joined query into one shared helper (per §TN-6 / the "shared query functions" convention) over duplicating the SQL in two files. Per §TN-6.
- [ ] **AC-4**: The coach-facing footer signals are NOT introduced here (this is the operator surface); the specific data-integrity flags stay operator-only per the operator/coach split (§TN-7).
- [ ] **AC-5**: Tests cover the joined list output (a report with a complete run row, a degraded run row, and a report with no run row) and assert `error_message` and the operator flags appear.
- [ ] **AC-6**: E-234 guards stay green. The `list_reports()` edit is read/list-path only and is disjoint from `generate_report()`'s stat computation, so the golden stat-table assertion does not apply to this story — stated explicitly so the restructure-as-refactor criterion resolves rather than being left implicit (CR-F2).

## Technical Approach
Extend the report-listing queries to LEFT JOIN `report_generation_runs ON report_id` (left join so legacy rows without a run survive) and add the run columns to the returned dicts. Update `admin/reports.html` to render the per-stage detail and operator flags (the visual treatment is the implementer's call; keep it operator-dense, not coach-facing). This story is sequenced after story 05 to serialize `src/api/routes/admin.py` edits.

## Dependencies
- **Blocked by**: E-235-03, E-235-05
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` (`list_reports()` join)
- `src/api/routes/admin.py` (the `/admin/reports` data function — e.g. `_get_all_reports`)
- `src/api/templates/admin/reports.html`
- `tests/` (admin reports-list tests + CLI `bb report list` coverage)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Keep operator-only data-integrity flags here and out of the coach footer (story 07) — the split is intentional per coach (§TN-7).
