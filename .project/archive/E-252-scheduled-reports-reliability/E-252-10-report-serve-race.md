# E-252-10: Fix report-serve 500-vs-404 race on concurrent file unlink

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`DONE`

## Description
After this story is complete, the public report-serving route returns a clean 404 (never a 500) when the report's HTML file is unlinked between the `is_file()` guard and the `read_text()` call — closing a TOCTOU race with the concurrent cleanup/reaper passes.

## Context
`serve_report` in `src/api/routes/reports.py` (the unauthenticated `GET /reports/{slug}` route) resolves the report file, guards with `file_path.is_file()` (line 78) → returns 404 if missing, then reads it with `file_path.read_text(encoding="utf-8")` (line 82). Between those two calls another process can unlink the file — `cleanup_expired_reports()` runs opportunistically at the start of every `bb report generate` and via `bb report cleanup`, and this epic's E-252-08 adds a stuck-`generating` reaper on the same lifecycle. When the file vanishes in that window, `read_text()` raises `FileNotFoundError` (an `OSError`), which is uncaught → the route returns HTTP 500 instead of the uniform 404 the route already returns for a missing file at line 78-80.

The route's established contract (its docstring) is that a 404 is returned identically regardless of reason (unknown slug, expired, missing file, non-serveable status) to avoid leaking report existence/expiration. The read race must fold into that same 404 behavior — it is the concurrent-unlink twin of the already-handled `is_file()`-false case.

This finding (audit LOW, `reports.py:82`) was NOT in the CE-2 stub's Absorbed set — it is a report-serving concern, not morning-run orchestration. It is pulled into E-252 by explicit user decision (2026-07-05) because it is a small, cohesive reliability fix in the same serving path this epic hardens. See the epic's provenance note in the scope-accounting section.

## Acceptance Criteria
- [ ] **AC-1**: Given a serveable, non-expired report whose `report_path` file passes the `is_file()` guard, when the file is unlinked (or otherwise made unreadable) before `read_text()` executes, then the route returns HTTP 404 — NOT 500 — matching the existing file-not-found behavior.
- [ ] **AC-2**: The 404 returned on the read race is identical to the route's other 404 responses (no distinguishing body/headers), preserving the no-information-leakage contract in the route docstring.
- [ ] **AC-3**: The read failure is logged (at the same warning level and shape as the existing `is_file()`-miss log at line 79) so an operator can distinguish a genuine concurrent-unlink from a normal miss, without the failure surfacing to the requester as a 500.
- [ ] **AC-4**: The happy path is unchanged: a serveable, non-expired report whose file is present and readable is still served as `HTMLResponse` with its existing content and `Cache-Control` header.
- [ ] **AC-5**: A test simulates the race (e.g. the file is removed, or `read_text` is patched to raise `FileNotFoundError`, after the `is_file()` guard passes) and asserts a 404 (not a 500 / not an unhandled exception). Per Technical Notes TN-8, no real HTTP — exercise the route via the app test client or the route function directly.

## Technical Approach
Wrap the `read_text()` call in `serve_report` so a file-read failure (`OSError` / `FileNotFoundError`) returns the same 404 the route already returns when `is_file()` is false, with a matching operator log line. Keep the response uniform (no leak). Do not change the happy path, the status/expiry gates, or the `Cache-Control` header. Verify the exact current shape against `src/api/routes/reports.py` (lines 72-86) — the fix is a localized guard around the read, consistent with the route's existing 404-uniformity contract.

## Dependencies
- **Blocked by**: None (independent file region — `src/api/routes/reports.py`; no interaction with the morning-run or connection-factory stories)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/reports.py` (`serve_report` — guard the `read_text()` call)
- `tests/test_reports_route.py` (or the existing serve-route test module) — the AC-5 race test

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (LOW): "Report serve can 500 instead of 404 when cleanup unlinks between `is_file()` and `read_text()`" — `src/api/routes/reports.py:82`. Added to E-252 by user decision 2026-07-05 (outside the stub's Absorbed set — deliberate addition, not scope creep). The concurrent unlinker is `cleanup_expired_reports()` and this epic's E-252-08 reaper, both on the report lifecycle.
