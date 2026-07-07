# E-254-04: Report-serving revocation-respecting cache-control

## Epic
[E-254: Security & PII Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, generated report HTML is served with a cache policy that respects report revocation and expiry — a shared/CDN cache can no longer hold a report for up to an hour after it has been expired or cleaned up.

## Context
`src/api/routes/reports.py::serve_report` (line 85) serves report HTML with `Cache-Control: public, max-age=3600`. Reports are ephemeral (14-day expiry; `cleanup_expired_reports()` unlinks the HTML and nulls `report_path`) and served on a no-auth public route by slug. A one-hour public cache undermines revocation: a report expired or deleted server-side can still be served from an intermediary cache for up to an hour (low severity, `reports.py:85`). Report HTML is a self-contained frozen snapshot; there is no shared-cache benefit that justifies the revocation risk here.

## Acceptance Criteria
- [ ] **AC-1**: Given a serveable, non-expired report, when GET `/reports/{slug}` returns the HTML, then the response `Cache-Control` header is `private, no-store` (no `public`, no `max-age=3600`).
- [ ] **AC-2**: Given each non-serveable condition, when GET `/reports/{slug}` is requested, then the 404 behavior is unchanged for ALL existing 404 branches — currently seven in `serve_report` (DB error, unknown slug, non-serveable status, expired timestamp, invalid/unparseable timestamp, missing `report_path`, missing file on disk). Only the successful-HTML response's `Cache-Control` changes.
- [ ] **AC-3**: No regressions — discovered importing test files for `routes/reports.py` pass (TN-6).

## Technical Approach
Change the `Cache-Control` header on the successful HTML response in `serve_report` to a revocation-respecting value (`private, no-store` per the epic decision). Leave the 404 paths untouched. See TN-6 for test discipline.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/reports.py` (`serve_report` success-response headers)
- `tests/test_report_routes.py` (Cache-Control assertion + unchanged-404 regression — already tests `serve_report`; 04-exclusive)
- Broader discovered importing suites: run-only per TN-6

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
File-independent of the auth stories; can run in any order relative to them.
