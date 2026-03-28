# E-172-04: Admin Reports Page

## Epic
[E-172: Standalone Scouting Report Generator](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin UI has a "Reports" page where the operator can paste a GameChanger URL, click Generate, and see the report appear in a list with its shareable link. The page shows all generated reports with status badges, copy-link buttons, and delete actions.

## Context
The CLI (E-172-02) provides the first generation path. This story adds the web UI path — same underlying pipeline, friendlier interface. The admin page triggers generation as a background task (since crawling takes minutes) and shows real-time status. This is the primary interface the operator will use day-to-day.

## Acceptance Criteria
- [ ] **AC-1**: `GET /admin/reports` renders a page with a URL input field, a "Generate Report" button, and a table of existing reports. The page is behind admin auth (same auth as other admin pages).
- [ ] **AC-2**: The reports table shows columns: team name/title, status badge, generated date, expires date, and a shareable link. Reports are sorted by `generated_at` descending (newest first).
- [ ] **AC-3**: Status badges use color coding: "Generating..." (`bg-yellow-100 text-yellow-800`), "Ready" (`bg-green-100 text-green-800`), "Failed" (`bg-red-100 text-red-800`), "Expired" (`bg-gray-100 text-gray-600`). Expired is determined by `expires_at < now`, regardless of the `status` column value.
- [ ] **AC-4**: Each ready (non-expired) report row displays the shareable public URL as a readonly `<input type="text">` field that the operator can select-all and copy. No JavaScript clipboard API needed — native browser select-on-focus behavior is sufficient. Per UXD consultation (TN-7).
- [ ] **AC-5**: Each report row has a "Delete" button/link. Deleting a report removes the `reports` row and the HTML file from disk. Confirmation before delete (either a confirm dialog or a confirm page).
- [ ] **AC-6**: `POST /admin/reports/generate` accepts a `gc_url` form field, validates it via `parse_team_url()` (returns an error flash if invalid), creates a background task to run the generation pipeline, and redirects to the reports list with a flash message ("Report generation started for [team]. This may take a few minutes.").
- [ ] **AC-7**: Failed reports show the error message (from `reports.error_message`) as a tooltip or expandable detail, so the operator can diagnose failures.
- [ ] **AC-8**: The "Reports" link appears in the admin navigation/sub-nav, consistent with existing admin pages.
- [ ] **AC-9**: Tests verify: (a) the reports page renders with the URL input and table, (b) POST with a valid URL creates a background task and redirects, (c) POST with an invalid URL shows an error flash, (d) delete removes the report row.

## Technical Approach
The admin reports page follows the existing admin page patterns (auth-required routes, Jinja2 template, flash messages). The generation trigger uses FastAPI's `BackgroundTasks` — same pattern as the admin team sync route. The reports list queries the `reports` table and renders a Jinja2 template. The delete handler removes the DB row and the file from disk. The "Copy Link" button uses a small inline JavaScript snippet (no framework needed).

## Dependencies
- **Blocked by**: E-172-02 (needs the generation pipeline function to call from the background task)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` — add report routes (GET list, POST generate, POST delete)
- `src/api/templates/admin/reports.html` — new template for the reports page
- `tests/test_admin_reports.py` — admin reports page tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The background task for generation should follow the same error-handling pattern as existing background tasks in `src/pipeline/trigger.py` — catch exceptions and update the report row status rather than letting them propagate.
- No auto-refresh on the page. The operator refreshes manually to check generation status (same pattern as the team sync page per UXD consultation). The "trigger, check back" pattern is already habituated.
- The reports list page should be reachable from the admin sidebar/nav. Check existing admin templates for the nav structure and add a "Reports" link.
