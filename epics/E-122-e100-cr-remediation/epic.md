# E-122: E-100 Family Code Review Remediation (Wave 2)

## Status
`READY`

## Overview
Fix 7 confirmed bugs and warnings from the E-100 family code review that are not covered by other active epics. These span scouting auth handling, dashboard template errors, import boundary violations, and test infrastructure drift. Left unfixed, they cause silent auth failure during scouting crawls, phantom UI columns, architecture violations, and schema drift risk in tests.

## Background & Context
Eight code reviewers audited the E-100 family epics (E-100, E-114, E-115, E-116, E-118, E-120). SE verified all findings against actual source code. Results are in `.project/research/cr-e100-family/verified-findings.md`.

Of the original 10 actionable items, 3 are already covered by **E-117-01** (game_loader pitching data loss: `R`, `WP`, `HBP`, `BF`, `#P`, `TS` skip-list fixes + `_PlayerPitching.hr` dead code removal). This epic covers the remaining 7 items.

E-121 (style guide remediation) is context-layer only and has no overlap with these code-level fixes.

Expert consultation: No expert consultation required -- all findings are verified bugs with clear, scoped fixes. The verified-findings file provides full diagnostic context.

## Goals
- Scouting crawler aborts on auth expiry instead of silently continuing
- Dashboard templates show only columns backed by actual data
- `src/` import boundary is respected (no importlib from `scripts/`)
- All test files use `run_migrations()` instead of inline schema SQL
- Private API names in credentials module are made public
- Opponent detail back-link preserves team context

## Non-Goals
- Pitching data loss in game_loader (covered by E-117-01)
- `_PlayerPitching.hr` dead code removal (covered by E-117-01 AC-13)
- Scouting loader performance optimization beyond the double-I/O fix
- Any schema changes -- all fixes are in Python code and templates

## Success Criteria
- `CredentialExpiredError` during scouting boxscore fetch aborts the crawl immediately
- `game_detail.html` pitching table has no HR column
- `opponent_detail.html` back-link includes `team_id` query parameter
- `src/cli/proxy.py` imports from `src/` only (no importlib to `scripts/`)
- All 5 test files with inline `_SCHEMA_SQL` use `run_migrations()` instead
- `_ALL_PROFILES` and `_run_api_check` are public names in the credentials module
- All existing tests pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-122-01 | Scouting crawler: abort on CredentialExpiredError | TODO | None | - |
| E-122-02 | Dashboard template fixes: phantom HR column + opponent back-link | TODO | None | - |
| E-122-03 | proxy.py import boundary fix | TODO | None | - |
| E-122-04 | Migrate inline _SCHEMA_SQL to run_migrations() | TODO | None | - |
| E-122-05 | Credentials module: publicize private API names | TODO | None | - |

## Dispatch Team
- software-engineer (E-122-01 through E-122-05)

## Technical Notes

### TN-1: Overlap with E-117
E-117-01 (game loader full boxscore coverage) already handles:
- CR-5-7: pitching `R` in skip list → maps to `r` column
- CR-5-8: pitching extras `WP`, `HBP`, `BF`, `#P`, `TS` in skip list → maps to schema columns
- `_PlayerPitching.hr` dead code removal (AC-13)

These items are explicitly excluded from E-122 to avoid conflicting changes to `game_loader.py`.

### TN-2: Scouting Auth Abort Pattern
The scouting crawler's `_fetch_boxscores()` catches `(CredentialExpiredError, ForbiddenError, GameChangerAPIError)` as a group and continues. The fix must separate `CredentialExpiredError` from the group -- re-raise it so it propagates up. `ForbiddenError` should remain caught (expected for non-owned team boxscores). The outer `scout_all()` `except Exception` at line 328-331 also swallows -- it should either re-raise `CredentialExpiredError` or the fix should ensure it never reaches that handler.

### TN-3: Import Boundary Fix Strategy
`src/cli/proxy.py` uses `importlib.util.spec_from_file_location` to load `scripts/proxy-refresh-headers.py` (hyphenated filename forces importlib). The fix is to move the reusable logic from that script into a proper `src/` module and import normally. The script in `scripts/` becomes a thin wrapper that imports from `src/`. This preserves the script's standalone usability while fixing the boundary violation.

### TN-4: Test Migration Scope
5 test files contain inline `_SCHEMA_SQL`:
- `tests/test_admin.py`
- `tests/test_auth_routes.py`
- `tests/test_passkey.py`
- `tests/test_dashboard.py`
- `tests/test_auth.py`

14 other test files already use `run_migrations()`. The fix replaces inline SQL with `run_migrations()` calls, using the same pattern as the majority of the test suite. After migration, `_SCHEMA_SQL` constants should be removed entirely from these files.

### TN-5: Verified Findings Reference
Full diagnostic details for each finding are in `/.project/research/cr-e100-family/verified-findings.md`. Story implementers should read the relevant finding section for line numbers, code context, and root cause analysis.

## Open Questions
- None. All findings verified with line-level precision.

## History
- 2026-03-17: Created from verified E-100 family code review findings. 3 of 10 actionable items excluded (covered by E-117-01). 7 remaining items organized into 5 stories. No expert consultation required. Set READY.
