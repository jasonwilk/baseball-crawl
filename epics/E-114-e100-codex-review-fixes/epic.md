# E-114: E-100 Codex Review Fixes

## Status
`READY`

## Overview
Fixes bugs discovered during the E-100 post-implementation Codex review and subsequent Codex test review. P1-1 is a data corruption bug where the game loader creates phantom team rows when `gc_uuid` is None (common scouting scenario). P1-3 is a duplicate-row integrity bug in the admin add-team flow when bridge reverification fails. P1-2 is an optional UX guard preventing operators from creating member teams that can't be crawled. B-P2b fixes stale template references to removed user fields (7 templates across dashboard and admin). A-P4 fixes test schema drift where inline test schemas omit production unique indexes (8 test files).

## Background & Context
Codex review of E-100 implementation found the original three bugs (P1-1, P1-3, P1-2). A subsequent Codex test review found two additional issues (B-P2b, A-P4) and three test coverage gaps (A-P2a, C-P2a, C-P2b). All confirmed by both code-reviewer and software-engineer. All issues exist in code written or rewritten during E-100.

**P1-1 severity**: High. Triggered by common scenario (scouting opponent added via admin when bridge returned 403). Silent data corruption -- boxscore stats written against a phantom team row with `gc_uuid=""` and `name=""`.

**P1-3 severity**: Medium. Low probability (requires credential expiry between Phase 1 and Phase 2 of add-team flow), but hard to recover from -- two rows for the same team with stats accumulating separately.

**P1-2 severity**: Low. Not a correctness bug -- operator-error path with visible failure (crawlers fail loudly on member teams without gc_uuid). UX improvement to prevent the error path entirely.

**B-P2b severity**: Medium. Six dashboard templates and one admin template silently render blank user names and invisible admin nav links due to stale field references.

**A-P4 severity**: Medium. Eight test schemas diverge from production DDL -- uniqueness violations pass in tests but fail in production.

No expert consultation required -- bugs are well-characterized with confirmed fixes.

## Goals
- Game loader uses `self._team_ref.id` directly for the own team, never passing empty string to `_ensure_team_row`
- Admin add-team duplicate detection catches gc_uuid-only rows even when reverify fails
- (Optional) Member radio is disabled or warned when gc_uuid is unavailable
- Dashboard and admin templates use correct user dict fields (no stale `display_name`/`is_admin` references)
- Test schemas match production DDL (partial unique indexes included)

## Non-Goals
- **Redesigning the loader's team resolution pattern.** Minimal fix to the specific bug path.
- **Reworking the admin add-team flow.** Only the duplicate detection and UX guard change.
- **Comprehensive loader test overhaul.** Only adding test coverage for the specific `gc_uuid=None` path.
- **Refactoring test schemas to import from migrations.** Optional improvement noted in E-114-05 but not required.
- **Fixing low-risk test quality items** (A-P2b, B-P1a, B-P1b, B-P2a). Deferred per triage.

## Success Criteria
- `GameLoader._resolve_team_ids()` returns `self._team_ref.id` for the own team without calling `_ensure_team_row` when the own team's INTEGER PK is already known
- The secondary `gc_uuid or ""` usage in `_detect_team_keys` (line 530) is also fixed
- `_check_duplicate_new` detects existing rows when `gc_uuid` is None on reverify but the row has a gc_uuid from prior resolution
- Test coverage for `TeamRef(gc_uuid=None)` scouting path in game loader
- Test coverage for gc_uuid-only duplicate + reverify failure interaction in admin
- All dashboard templates use `user.email` (not `user.display_name`) and have no `user.is_admin` conditionals; `admin/opponent_connect.html` uses `admin_user.email` (not `admin_user.display_name`)
- Test inline schemas include the same unique indexes as production DDL

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-114-01 | Fix game loader phantom team row on gc_uuid=None | TODO | None | - |
| E-114-02 | Fix admin duplicate detection on reverify failure | TODO | None | - |
| E-114-03 | UX guard: disable member radio without gc_uuid | TODO | E-114-02 | - |
| E-114-04 | Fix dashboard and admin template stale references | TODO | None | - |
| E-114-05 | Fix test schema drift — missing unique indexes | TODO | E-114-02, E-114-04 | - |

## Dispatch Team
- software-engineer (E-114-01, E-114-02, E-114-03, E-114-04, E-114-05)

## Technical Notes

### P1-1: Game Loader Phantom Team Row
**Root cause**: `game_loader.py` line 415 calls `self._ensure_team_row(self._team_ref.gc_uuid or "")`. When `gc_uuid` is None (tracked opponent where bridge returned 403), this passes empty string `""` to `_ensure_team_row`, which creates a team row with `gc_uuid=""` and `name=""`. All boxscore stats for the own team are then written against this phantom row.

**Secondary occurrence**: Line 530 has `owned_gc_uuid = self._team_ref.gc_uuid or ""` used for boxscore key identification. Same issue -- when gc_uuid is None, the key matching fails silently.

**Fix**: The own team's INTEGER PK (`self._team_ref.id`) is already known -- it was looked up when the `TeamRef` was constructed. Use it directly instead of re-resolving through `_ensure_team_row`. For line 530, use `self._team_ref.gc_uuid` directly (allow None, adjust the comparison logic).

### P1-3: Admin Duplicate Detection Gap
**Root cause**: The GET confirm handler already calls `_check_duplicate_new` with Phase 1 gc_uuid (catching duplicates at render time). The bug is **POST-side only**: `_check_duplicate_new(public_id, gc_uuid)` checks `public_id` always but only checks `gc_uuid` when it's non-None. When TOCTOU reverify 403s on POST, `gc_uuid_value` becomes None, so the function only checks `public_id`. If an existing row was created by opponent_resolver with a gc_uuid but a different or no public_id, the POST duplicate check misses it.

**Fix**: When `gc_uuid` is None on reverify, also check whether any row exists with the same `public_id` but a different or missing gc_uuid. The current `public_id` check already covers exact public_id match, but the scenario involves a row with gc_uuid but no public_id. Consider a broader query: check if any row's gc_uuid matches what Phase 1 originally discovered (pass the original Phase 1 gc_uuid to the duplicate check even when reverify fails).

### P1-2: Member Radio UX Guard
**Root cause**: `confirm_team.html` line 71 offers `<input type="radio" name="membership_type" value="member">` unconditionally regardless of `gc_uuid_status`.

**Fix options** (implementer chooses):
1. Disable the member radio when `gc_uuid_status != 'found'` (add `disabled` attribute)
2. Add a prominent warning below the member radio when gc_uuid is unavailable
3. Both: disable + warning

### B-P2b: Dashboard Template Stale References
**Root cause**: E-100 removed `display_name` and `is_admin` from the user dict but only updated `dashboard/team_stats.html`. Seven other templates still reference these fields. Jinja2 silently renders undefined variables as empty strings, so the pages render without errors but admin nav links never appear and user names are blank.

**Affected dashboard templates** (use `user` context variable): `dashboard/team_pitching.html`, `dashboard/game_list.html`, `dashboard/opponent_list.html`, `dashboard/opponent_detail.html`, `dashboard/player_profile.html`, `dashboard/game_detail.html`.

**Affected admin template** (uses `admin_user` context variable): `admin/opponent_connect.html` -- same stale `display_name` field but on the `admin_user` variable (which is the same user dict passed from the admin guard).

**Fix**: Update all seven templates. Dashboard templates: use `user.email` (matching `team_stats.html`) and remove `is_admin` conditionals. Admin template: use `admin_user.email`.

### A-P4: Test Schema Drift
**Root cause**: Eight test files define inline `_SCHEMA_SQL` that reproduces production DDL but omits the `CREATE UNIQUE INDEX` statements for `gc_uuid` and `public_id`. Uniqueness violations pass in tests but fail in production.

**Affected test files**: `test_admin.py`, `test_admin_opponents.py`, `test_admin_teams.py`, `test_auth.py`, `test_auth_routes.py`, `test_passkey.py`, `test_dashboard.py`, `test_dashboard_auth.py`.

**Fix**: Add the missing `CREATE UNIQUE INDEX` statements to match `migrations/001_initial_schema.sql`.

### Parallel Execution
- E-114-01: `src/gamechanger/loaders/game_loader.py`, `tests/test_loaders/test_game_loader.py`
- E-114-02: `src/api/routes/admin.py`, `src/api/templates/admin/confirm_team.html` (possible), `tests/test_admin_teams.py`, `tests/test_admin_opponents.py`
- E-114-03: `src/api/templates/admin/confirm_team.html`, `tests/test_admin_teams.py`
- E-114-04: `src/api/templates/dashboard/team_pitching.html`, `src/api/templates/dashboard/game_list.html`, `src/api/templates/dashboard/opponent_list.html`, `src/api/templates/dashboard/opponent_detail.html`, `src/api/templates/dashboard/player_profile.html`, `src/api/templates/dashboard/game_detail.html`, `src/api/templates/admin/opponent_connect.html`, `tests/test_dashboard.py`
- E-114-05: `tests/test_admin.py`, `tests/test_admin_opponents.py`, `tests/test_admin_teams.py`, `tests/test_auth.py`, `tests/test_auth_routes.py`, `tests/test_passkey.py`, `tests/test_dashboard.py`, `tests/test_dashboard_auth.py`, `tests/test_db.py`

E-114-01 is fully independent (no file overlap with any other story).

E-114-04 is independent of E-114-01, E-114-02, and E-114-03 (no file overlap).

**Conflict**: E-114-02 and E-114-03 both touch `tests/test_admin_teams.py` and may both touch `confirm_team.html`. Serialize E-114-03 after E-114-02.

**Conflict**: E-114-05 touches `tests/test_admin_teams.py` and `tests/test_admin_opponents.py` (inline schema), which E-114-02 also modifies (new test cases). Serialize E-114-05 after E-114-02.

**Conflict**: E-114-04 and E-114-05 both touch `tests/test_dashboard.py` (E-114-04 adds template assertions, E-114-05 fixes inline schema). Serialize E-114-05 after E-114-04.

## Open Questions
- None. Bugs are well-characterized with confirmed root causes.

## History
- 2026-03-16: Created from E-100 Codex review findings. Confirmed by CR and SE.
- 2026-03-16: PM refinement review. Fixed: (1) Stories table now shows E-114-03 dependency on E-114-02, (2) Parallel Execution section corrected to reflect confirm_team.html overlap between E-114-02 and E-114-03, (3) E-114-02 Technical Approach revised to describe the constraint rather than prescribing a hidden-field solution. All three bugs verified in source code. Set to READY.
- 2026-03-16: Codex spec review triage. Fixed 4 findings: (F1-P1) corrected test file paths across all stories and epic -- `tests/test_game_loader.py` → `tests/test_loaders/test_game_loader.py`, `tests/test_admin_routes.py` → `tests/test_admin_teams.py`; (F2-P2) renamed `_identify_own_team` → `_detect_team_keys` in epic Technical Notes and Success Criteria to match actual code; (F3-P2) added AC-3b to E-114-01 requiring a two-UUID-key boxscore test to exercise the secondary line-530 bug path; (F4-P2) clarified P1-3 description in epic and E-114-02 Context that the duplicate detection gap is POST-side only (GET already catches duplicates with Phase 1 gc_uuid).
- 2026-03-16: Codex test review triage. Added 2 new stories and expanded ACs. New: E-114-04 (dashboard template stale references -- 6 templates still using removed `user.display_name`/`user.is_admin` fields), E-114-05 (test schema drift -- 6 test files missing production unique indexes on `gc_uuid`/`public_id`). Expanded: E-114-02 AC-4 added for discover-opponents route test coverage (A-P2a); E-114-05 AC-3/AC-4 added for pitching assertion on scouting report test (C-P2a) and is_active/source assertions on bulk_create_opponents test (C-P2b). Dismissed: A-P1 (intentional dev-mode design), A-P2b/B-P1a/B-P1b/B-P2a (low-risk, deferred). Updated Parallel Execution with new file conflicts: E-114-05 blocked by E-114-02 (shared test files). Epic now has 5 stories total.
- 2026-03-16: Full refinement review. Fixed 6 issues: (1) E-114-01 "Context files to read" corrected `_identify_own_team` -> `_detect_team_keys` (stale reference from pre-triage); (2) E-114-02 Files to Create removed prescriptive "hidden field" parenthetical; (3) E-114-04 template paths corrected -- all 6 were missing `dashboard/` subdirectory (e.g., `src/api/templates/team_pitching.html` -> `src/api/templates/dashboard/team_pitching.html`); (4) E-114-04 scope expanded to 7 templates -- `admin/opponent_connect.html` uses `admin_user.display_name` (same stale field, different variable name); (5) E-114-05 scope expanded from 6 to 8 test files -- `test_dashboard.py` and `test_dashboard_auth.py` also have inline schemas missing unique indexes; (6) E-114-05 now blocked by both E-114-02 and E-114-04 (`test_dashboard.py` overlap). E-114-04 test file resolved to `tests/test_dashboard.py` (not `test_admin.py`). All bugs re-verified in source code.
