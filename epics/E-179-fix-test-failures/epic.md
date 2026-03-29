# E-179: Fix Pre-Existing Test Failures from E-173 UI Changes

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Fix 69 pre-existing test failures across 11 test files caused by E-173 (opponent scouting workflow overhaul) UI/route/schema changes that left tests behind, plus a few pre-existing test infrastructure bugs exposed during the same sweep. Tests broke because E-173 renamed UI labels to a pipeline_status-based badge system, consolidated routes, changed filter pills, added background tasks without test mocks, and restructured data models -- but the tests were never updated. Two additional failures (PII hook integration, scouting spray loader) are pre-existing test infrastructure bugs unrelated to E-173. These failures were invisible because RTK was filtering pytest output.

## Background & Context
E-173 was a large workflow epic that renamed badge text ("Full stats" to "Stats loaded", "Scoresheet only" to "Needs linking"), consolidated connect routes into a unified `/resolve` flow, changed filter pills, added auto-scout background tasks after resolution, and restructured report data models. The corresponding tests were not updated during E-173 dispatch. The failures went undetected because the RTK (Rust Token Killer) CLI proxy was filtering out pytest failure output -- a separate fix for that (`.claude/rules/pytest-verbose.md`) has been committed independently.

No expert consultation required -- this is primarily mechanical test alignment work with confirmed fix patterns. Two failures (PII hook integration, scouting spray loader) are pre-existing test infrastructure bugs unrelated to E-173 but are included here because they were discovered in the same sweep and are test-only fixes.

## Goals
- All 69 failing tests pass with zero regressions
- Tests accurately reflect the current UI labels, routes, filters, and data models shipped by E-173

## Non-Goals
- Changing any production code (`src/`, `migrations/`, `scripts/`) -- see TN-3
- Adding new test coverage beyond what already exists
- Refactoring test structure or test utilities

## Success Criteria
- `pytest` runs green (0 failures, 0 errors) across the full test suite
- No production files modified -- only `tests/` files touched

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-179-01 | Fix test_admin_opponents.py label, route, filter, and badge failures | TODO | None | - |
| E-179-02 | Fix test_admin_delete_cascade.py label failure | TODO | None | - |
| E-179-03 | Fix test_dashboard_opponent_detail.py label and mock failures | TODO | None | - |
| E-179-04 | Fix test_dashboard_routes.py empty state and sort test failures | TODO | None | - |
| E-179-05 | Fix test_report_renderer.py data model failures | TODO | None | - |
| E-179-06 | Fix test_pii_hook_integration.py, test_scouting_spray_loader.py, test_admin_teams.py, and test_admin_routes.py failures | TODO | None | - |
| E-179-07 | Full test suite green verification | TODO | E-179-01 thru 06, 08, 09 | - |
| E-179-08 | Fix test_opponent_resolver.py assertion failures | TODO | None | - |
| E-179-09 | Fix test_dashboard.py empty state and stale reference failures | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Root Cause Categories

Seven root causes drive all 69 failures. Each test fix falls into one or more of these categories:

1. **Pipeline-Status Badge System**: E-173 replaced simple badge labels with a `pipeline_status`-based badge system. The old labels no longer exist in templates. Tests asserting old strings will fail. Complete mapping:
   - Old "Full stats" / "Full stats (auto)" / "Full stats (manual)" -> **"Stats loaded"** (green badge). The "(auto)"/"(manual)" distinction no longer appears in badge text; those strings only appear in the `resolution_method` column data.
   - Old "Scoresheet only" -> **"Needs linking"** (orange badge)
   - Old "Tracked" -> **"Opponent"** (on delete confirmation page)
   - Old "Resolved" badge -> **no longer exists as a badge**. Resolved opponents show status-based badges: "Stats loaded" (green), "Linked" (blue, resolved but no stats yet), "Syncing..." (yellow), "Sync failed" (red)
   - Old "Unresolved" badge -> **"Needs linking"** (orange badge)
   - New badge state **"Hidden"** (gray) -- for dismissed opponents
   - Summary stat line: old "N resolved" -> **"N with stats"**; old "N need mapping" -> **"N need linking"**
   - **"Run Discovery" link** -- removed from opponents template entirely

2. **Route Consolidation**: E-173 unified the two-stage connect flow into a single `/admin/opponents/{id}/resolve` endpoint. GET `/connect` and GET `/connect/confirm` now return 303 redirects to `/resolve`. **However, POST `/connect` still exists and works** -- it is NOT redirected, but its behavior changed: it now calls `finalize_opponent_resolution()` which sets `resolved_team_id` (previously NULL after connect) and triggers `run_scouting_sync` in the background. Tests need: (a) URL changes to `/resolve` for GET tests, (b) updated assertions for `resolved_team_id` now being populated after POST, (c) awareness that TestClient follows redirects by default so GET `/connect` tests will land on `/resolve` content, (d) mocks for `trigger.run_scouting_sync` per TN-4.

3. **Filter Pills Changed**: The `?filter=scoresheet` query parameter was removed; its function consolidated into `?filter=unresolved`. Summary stat line text changed per the mapping in category 1 above. Fix: update filter parameters and assertion strings.

4. **Missing Mocks / Real HTTP Leaks**: E-173 added auto-scout background tasks (`trigger.run_scouting_sync`) that fire after opponent resolution. Tests triggering resolution routes without mocking this function make real HTTP calls, causing timeouts. Fix: add appropriate mocks per TN-4.

5. **Schema/Model Changes**: New `pipeline_status` field on opponent data, report data model restructuring, template changes. Test fixtures provide stale mock data missing required fields. Fix: update fixture data to include new required fields.

6. **Test Infrastructure Bugs (not E-173)**: Two failures are pre-existing test bugs unrelated to E-173:
   - **PII hook integration**: `_init_repo()` creates a temp git repo without `src/__init__.py`, so `python3 -m src.safety.pii_scanner` fails as a module import. Fix: update `_init_repo()` to create `src/__init__.py` in the temp repo.
   - **Scouting spray loader**: `test_resolvable_unknown_player_gets_stub_row` fails with `sqlite3.IntegrityError: FOREIGN KEY constraint failed` because the test inserts into `team_rosters` without a matching `players` row while FK enforcement is ON. Fix: restructure the test to work within FK constraints.

7. **Behavioral Drift (not E-173 labels)**: Some test failures are from behavioral changes (new error paths, CHECK constraints, nav label renames) that don't fit the label/route/filter categories:
   - `test_opponent_resolver.py`: Error count assertions off by 1 due to new error path from `finalize_opponent_resolution` integration
   - `test_admin_teams.py`: CHECK constraint `our_team_id != opponent_team_id` on `team_opponents` -- test fixture violates this
   - `test_admin_routes.py`: Nav label rename (">Games<" in bottom nav)
   - `test_dashboard.py`: Stale `/connect` URL reference in template check + empty state UI assertion changes

### TN-2: Current Template and Route Reference

The implementing agent should read these production files to determine current expected values:
- `/workspaces/baseball-crawl/src/api/templates/admin/opponents.html` -- badge text, filter pills, summary stat line
- `/workspaces/baseball-crawl/src/api/templates/admin/opponent_resolve.html` -- the unified resolve form/confirm page
- `/workspaces/baseball-crawl/src/api/templates/admin/confirm_delete.html` -- membership badge text
- `/workspaces/baseball-crawl/src/api/templates/dashboard/opponent_detail.html` -- status card text
- `/workspaces/baseball-crawl/src/api/routes/admin.py` -- current route definitions and handler signatures
- `/workspaces/baseball-crawl/src/api/routes/dashboard.py` -- current route definitions
- `/workspaces/baseball-crawl/src/reports/renderer.py` -- current report data model
- `/workspaces/baseball-crawl/src/pipeline/trigger.py` -- `run_scouting_sync` function that needs mocking

### TN-3: Test-Only Constraint

This epic modifies ONLY files under `tests/`. No production code changes are permitted. The E-173 changes are correct and intentional -- tests must be updated to match the current production behavior.

### TN-4: Mock Path for Background Task

The auto-scout background task (`trigger.run_scouting_sync`) is called at three locations in `src/api/routes/admin.py`: `sync_team_data`, `connect_opponent` (POST `/connect`), and `resolve_opponent_confirm` (POST `/resolve`). The admin routes import trigger as a module (`from src.pipeline import trigger`), then call `trigger.run_scouting_sync(...)`. The canonical monkeypatch target is `src.pipeline.trigger.run_scouting_sync`.

### TN-5: Dashboard Template Text Reference

SE-confirmed current template text for opponent detail pages:
- Old "hasn't been linked" -> **"Scouting stats aren't available"**
- Old "linked but stats haven't been loaded" -> **"Stats are on their way. Check back soon."**
- **"Spray chart coming soon"** -- removed entirely
- **"Batter Tendencies"** -- still exists (unchanged)

## Open Questions
- None. Fix patterns are known and root causes confirmed.

## History
- 2026-03-28: Created
- 2026-03-29: Set to READY after 3-round internal review + 2-round Codex spec review

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 7 | 6 | 1 |
| Internal iteration 1 -- SE holistic review | 7 | 7 | 0 |
| Internal iteration 1 -- PM self-review | 4 | 4 | 0 |
| Internal iteration 2 -- CR | 2 | 2 | 0 |
| Internal iteration 2 -- SE | 3 | 3 | 0 |
| Internal iteration 2 -- PM | 0 | 0 | 0 |
| Codex iteration 1 | 5 | 5 | 0 |
| Codex iteration 2 | 4 | 4 | 0 |
| **Total** | **32** | **31** | **1** |

Note: Many iteration 1 findings overlapped across reviewers (CR-1/SE-7/PM-4 missing files, CR-4/PM-1 vague root cause, CR-3/PM-3 catch-all scope). Unique accepted actions after dedup: ~20. The 1 dismissal was CR-5 (`-x` flag in ACs, marked MINOR by CR itself — later superseded by Codex P1-3 which added `-v` to all ACs).
