# E-254-05: Admin authorization sweep test

## Epic
[E-254: Security & PII Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, a sweep test enumerates every route on the admin router and proves that an authenticated non-admin is denied — so a future admin route that ships without the admin gate fails the test rather than silently shipping open.

## Context
Admin denial in `src/api/routes/reports_admin.py` is opt-in per route: each handler individually calls `_require_admin` and returns its `Response` on denial. All 8 current routes do call it (verified during consultation). Existing non-admin-403 coverage is PER-ROUTE / PARTIAL (e.g. `tests/test_admin.py`, `tests/test_admin_routes.py`), but there is no ROUTER-WIDE introspection sweep asserting EVERY current AND future route is guarded — so a new route added later could omit the gate and go unnoticed (low severity, `reports_admin.py:664`). This story adds that enforcing sweep. See Technical Notes TN-9 and TN-6.

## Acceptance Criteria
- [ ] **AC-1**: A sweep test enumerates the routes on `reports_admin.router` (introspection over `reports_admin.router.routes`, per TN-9) rather than a hand-maintained route list, so a newly-added route is automatically covered.
- [ ] **AC-2**: Given an unauthenticated request, when each enumerated route is exercised through the full middleware stack with path params substituted by concrete dummy ids and minimal valid POST bodies so the route actually matches (per TN-9), then the response is a 302 redirect to login.
- [ ] **AC-3**: Given an authenticated NON-admin session, when each enumerated route is exercised (path params substituted per AC-2; POST routes with a VALID CSRF token so the 403 proves the admin gate, not the CSRF gate — per TN-9), then the response is 403.
- [ ] **AC-4**: Given an authenticated ADMIN session (positive control), when each enumerated route is exercised with FIXTURE-BACKED EXISTING ids (a seeded user + report so `{user_id}`/`{report_id}` resolve — NOT arbitrary dummy ids, which return 404 after the gate passes and would satisfy "not 403" vacuously) and valid POST bodies, then the response is the route's EXPECTED success status — 303 for the mutation-redirect routes (create/update/delete user, generate/delete report — live handlers redirect with 303) and 200 for any GET admin route — NOT merely "not 403". This catches a "403 for everyone" regression AND is not vacuously satisfied by a 404.
- [ ] **AC-4a**: For POST `/reports/generate` specifically, the admin positive-control MUST mock the report-generation entrypoint (the handler's background `generate_report` call) so the 303 is asserted WITHOUT triggering a live GameChanger crawl — under `TestClient`, BackgroundTasks run after the response, so an un-mocked positive control would kick off a real network crawl (flaky / undesired). Per TN-9.
- [ ] **AC-5**: The sweep is a standing regression guard, not a one-time fix: because it enumerates `router.routes` (AC-1) and asserts non-admin→403 on every route (AC-3), a future admin route added WITHOUT `_require_admin` FAILS the sweep. (All 8 current routes already call `_require_admin`; if the sweep nonetheless finds one unguarded, that route is fixed in this story so the sweep passes green.)
- [ ] **AC-6**: No regressions — discovered importing test files for `reports_admin.py` pass (TN-6).

## Technical Approach
Write an introspection-driven parametrized test over `reports_admin.router.routes` exercising each route at the three authorization levels (unauth / non-admin / admin) through the real `SessionMiddleware` + `CSRFMiddleware` stack via the existing `TestClient` fixtures. POST routes need a valid CSRF token so a 403 attributes to the admin gate. Include the admin positive-control. Per TN-9 this is expected to be test-only; if a route is found unguarded, add the gate in this story. See TN-6, TN-9.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_admin_authz_sweep.py` (NEW — the dedicated router-wide sweep + its own fixtures: admin + non-admin sessions + a seeded target user + a seeded report for the 303/200 positive controls; 05-exclusive. Fallback if preferred: extend `tests/test_admin_reports.py`, which already seeds a report + admin.)
- `src/api/routes/reports_admin.py` (ONLY if AC-5 finds an unguarded route)
- Broader discovered importing suites: run-only per TN-6

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The router-level `Depends`-on-router defense-in-depth refactor is deliberately OUT of scope — captured as IDEA-094. This story's deliverable is the enforcing sweep test.
