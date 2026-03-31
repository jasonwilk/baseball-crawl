# E-178-02: Auto-Refresh While Jobs Running + Failed Badge Error Display

## Epic
[E-178: Teams Page UX Overhaul](epic.md)

## Status
`DONE`

## Description
After this story is complete, the teams list page auto-refreshes while any team has a running job, and failed sync badges show the error message as a tooltip with a retry action. The coach gets passive progress feedback without manually refreshing and can understand and recover from failures directly from the teams list.

## Context
When a sync is running, the coach must manually refresh the teams page to see when it completes. When a sync fails, the badge just says "failed" with no context -- the coach has no idea what went wrong or how to retry. UXD designed two solutions: (1) a `<meta http-equiv="refresh">` auto-refresh when jobs are running, with a yellow banner; (2) surface `crawl_jobs.error_message` as a tooltip on the failed badge with a "Retry" link. Coach feedback on auto-refresh: "Don't assume the coach is staring at the page. The row badges when they come back are what matters."

## Acceptance Criteria

**Auto-refresh:**
- [ ] **AC-1**: When any team in the list has `latest_job_status == 'running'`, the teams page includes `<meta http-equiv="refresh" content="8">` in the `<head>`.
- [ ] **AC-2**: When any team has a running job, a yellow banner is displayed at the top of the teams list (e.g., "Stats are updating. This page refreshes automatically.").
- [ ] **AC-3**: When no team has a running job, neither the meta refresh tag nor the yellow banner is present.
- [ ] **AC-4**: The auto-refresh interval is 8 seconds.

**Failed badge error display:**
- [ ] **AC-5**: When `latest_job_status == 'failed'`, the badge displays the `error_message` from `crawl_jobs` as a `title=""` tooltip. If `error_message` is NULL, the tooltip reads "Unknown error".
- [ ] **AC-6**: When `latest_job_status == 'failed'`, a "Retry" link appears next to the badge that triggers the same sync endpoint as the "Update Stats" button.
- [ ] **AC-7**: The "Retry" link uses the existing sync form/endpoint (POST `/admin/teams/{id}/sync`).

**Tests:**
- [ ] **AC-8**: Tests verify the meta refresh tag is present when a job is running and absent when no job is running.
- [ ] **AC-9**: Tests verify the failed badge tooltip shows the error message.
- [ ] **AC-10**: No regressions in existing tests.

## Technical Approach
The auto-refresh requires a template-level check: pass a flag from the route handler to the template indicating whether any team has a running job. The template conditionally renders the meta tag and banner. The failed badge error display requires adding `error_message` to the existing `_list_teams_for_admin` query (the LEFT JOIN on `crawl_jobs` already exists -- one column added). The template renders the error as a `title=""` attribute and adds a retry form. **Reference implementation**: `src/api/templates/admin/reports.html` already implements both auto-refresh and error tooltips -- use it as a pattern reference.

## Dependencies
- **Blocked by**: E-178-01 (teams.html terminology must be clean first)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` -- add `error_message` to `_list_teams_for_admin` query; pass `any_running` flag to template context
- `src/api/templates/admin/teams.html` -- add conditional meta refresh tag, yellow banner, failed badge tooltip, and retry link
- `tests/test_admin_teams.py` -- add tests for auto-refresh behavior and failed badge tooltip

## Agent Hint
software-engineer

## Definition of Done
- [ ] Auto-refresh fires when jobs are running, stops when complete
- [ ] Failed badges show error tooltip and retry action
- [ ] All acceptance criteria pass; no regressions
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- Coach's feedback is important context: auto-refresh is a convenience, not the primary feedback. The row-level badges (done/failed/running) are what the coach relies on. Do not make the auto-refresh banner alarming or distracting.
- The 8-second refresh interval balances responsiveness with server load. A typical sync takes 15-60 seconds.
- The `error_message` column exists in `crawl_jobs` (migration 001). The query already joins this table -- only one column needs to be added to the SELECT.
