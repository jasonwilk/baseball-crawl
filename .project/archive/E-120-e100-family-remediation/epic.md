# E-120: E-100 Family Code Review Remediation

## Status
`COMPLETED`

## Overview
Fix bugs, test gaps, validation holes, and documentation errors identified by two comprehensive code reviews of the E-100 family (E-100, E-114, E-115, E-116, E-118). The most critical issue is a pipeline bug where `bb data resolve-opponents` silently writes zero rows because `load_config()` is called without `db_path`, making every `TeamEntry.internal_id` None. The second review added dashboard display bugs, TOCTOU handling, parameter shadowing, XSS regression testing, and additional doc/test gaps.

## Background & Context
Two post-dev code reviews of E-100 family code surfaced a combined 42 findings. After triage (with SE and Coach consultation), 24 are actual problems requiring fixes (across 12 stories), 3 are already covered by existing stories, 1 is deferred, and 14 are dismissed. The first review found 16 findings (12 FIX, 4 DISMISS). The second 8-agent review found 26 additional findings (C1-C3, M1-M8, m1-m15); after expert-informed triage: 14 FIX (mapped to stories 01-12), 3 already covered by prior stories, 1 deferred (m3 season fallback — Coach says adequate for current scope), and 8 dismissed. Two new stories added: E-120-11 (m4+m5 dashboard nav fixes) and E-120-12 (m8 scouting loader type guard).

Expert consultation completed: SE validated technical feasibility and severity for all findings. Coach confirmed tied games occur in HS baseball ("T" is correct), pitcher HR is marginal but needed for future FIP computation (COALESCE fix sufficient), and "spring-hs" fallback is adequate for current scope.

## Goals
- Fix the `resolve-opponents` pipeline so it actually resolves opponents (critical path bug)
- Harden admin route input validation (membership_type whitelist, already-resolved guard)
- Correct opponent count display to exclude hidden links
- Fix dashboard display bugs (pitching HR, tied games, null scores, fragile back links)
- Handle TOCTOU race in team insert gracefully
- Clean up parameter shadowing of Python builtins
- Fix scouting loader type confusion when public_id is None
- Add XSS regression tests for query parameters
- Close test coverage gaps that allow real bugs to ship undetected
- Fix stale documentation in `docs/admin/architecture.md` and `docs/admin/operations.md`

## Non-Goals
- Refactoring inline stdlib imports in dashboard.py (cosmetic, zero risk)
- Rewriting seed.sql / seed_dev.sql fixture data to match game-level sums (intentional design for clean K/9 values)
- Changing f-string SQL patterns in test helpers (not real injection risk)
- Updating `config/teams.yaml` season value (user-managed config)
- Adding constraints to `spray_charts` table (schema-ready but not yet populated -- premature)
- Fixing `reset.py` executescript/rollback (no-op rollback, but DB is freshly created -- zero practical risk)
- Refactoring long functions (opponent.py ~127 lines) without a bug or behavior change
- Moving inline dashboard auth SQL to db.py layer (convention preference, not a bug -- simple read-only checks)
- Replacing hardcoded `"spring-hs"` season fallback (adequate for current HS scope per Coach; defer until multi-program is real)
- Removing `sys.path.insert` from test files (unnecessary with editable install but harmless)
- Sequential await performance in admin routes (single-user admin UI, no user impact)
- Disabled button string equality check (brittle but functional, cosmetic)

## Success Criteria
- `bb data resolve-opponents` resolves opponents correctly (non-zero rows written for teams with opponents)
- `opponent_resolver.py` raises `ValueError` when `internal_id` is None instead of silently using 0
- Admin team list shows correct opponent count (hidden links excluded)
- `membership_type` is validated against a whitelist before DB write
- GET `/opponents/{link_id}/connect/confirm` returns 400 for already-resolved links
- `save_manual_opponent_link` has exception handling consistent with other db.py write functions
- Game detail pitching box score displays HR column correctly
- Tied games display "T" instead of incorrectly labeling both teams "L"
- Opponent detail scores display "-" instead of literal "None" when null
- Concurrent team insert returns user-friendly error instead of raw 500
- Parameter shadowing of Python builtins (`filter`, `id`) is eliminated
- XSS regression test verifies query parameter escaping
- Dashboard back links use explicit URLs with team context instead of `javascript:history.back()`
- Scouting loader skips teams with no public_id explicitly instead of silent integer fallback
- Test files `test_admin_teams.py`, `test_admin_opponents.py`, and `test_dashboard_auth.py` use `run_migrations()` instead of inline schema
- `test_migration_003.py` renamed to reflect its actual content (001 auth tables)
- `test_e100_schema.py` FK test uses its own pragma setting (not inherited from fixture)
- New CLI tests cover the `resolve-opponents` code path
- Scouting loader multi-scope test includes data for multiple teams
- `docs/admin/architecture.md` documents `opponent_links` table, has correct sub-nav description, correct `url_parser.py` characterization, port 8001 access, and complete teams table columns
- `docs/admin/operations.md` URL parser section documents bare UUIDs
- All existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-120-01 | Fix resolve-opponents pipeline bug | DONE | None | - |
| E-120-02 | Resolve-opponents and scouting loader test coverage | DONE | E-120-01 | - |
| E-120-03 | Admin validation and UX hardening | DONE | None | - |
| E-120-04 | Opponent count query and db.py consistency fixes | DONE | E-120-03 | - |
| E-120-05 | Test infrastructure quality fixes | DONE | None | - |
| E-120-06 | Documentation corrections | DONE | None | - |
| E-120-07 | Dashboard pitching HR query and template display fixes | DONE | None | - |
| E-120-08 | Admin team insert IntegrityError handling | DONE | E-120-03 | - |
| E-120-09 | Parameter shadowing cleanup | DONE | E-120-08 | - |
| E-120-10 | XSS escaping regression test for query parameters | DONE | E-120-03 | - |
| E-120-11 | Dashboard back-link navigation fixes | DONE | None | - |
| E-120-12 | Scouting loader public_id type guard | DONE | E-120-01 | - |

## Dispatch Team
- software-engineer (E-120-01, E-120-02, E-120-03, E-120-04, E-120-05, E-120-07, E-120-08, E-120-09, E-120-10, E-120-11, E-120-12)
- docs-writer (E-120-06)

## Technical Notes

### Triage Summary -- Review 1 (16 findings)

| ID | Finding | Verdict | Story |
|----|---------|---------|-------|
| MF-1 | `load_config()` missing `db_path` in `data.py:460` | FIX | E-120-01 |
| MF-2 | `internal_id or 0` silently masks None in `opponent_resolver.py:197` | FIX | E-120-01 |
| MF-3 | Zero test coverage for resolve-opponents CLI; vacuous multi-scope scouting test | FIX | E-120-02 |
| SF-1 | `membership_type` not validated before DB write in `admin.py` | FIX | E-120-03 |
| SF-2 | `opponent_count` subquery in `_get_all_teams_flat` includes hidden links | FIX | E-120-04 |
| SF-3 | `save_manual_opponent_link` missing exception handling | FIX | E-120-04 |
| SF-4 | `connect_opponent_confirm` GET missing already-resolved guard | FIX | E-120-03 |
| SF-5 | Inline stdlib imports in dashboard.py | DISMISS | — |
| SF-6 | Test files use inline schema instead of `run_migrations()` | FIX | E-120-05 |
| SF-7 | `docs/admin/architecture.md` stale/missing content | FIX | E-120-06 |
| P3-1 | seed.sql pitching sums don't match game-level | DISMISS | — |
| P3-2 | `test_migration_003.py` stale filename | FIX | E-120-05 |
| P3-3 | `test_e100_schema.py` vacuously true FK test | FIX | E-120-05 |
| P3-4 | `config/teams.yaml` season "2025" | DISMISS | — |
| P3-5 | `save_manual_opponent_link` docstring references nonexistent `updated_at` | FIX | E-120-04 |
| P3-6 | f-string SQL in test helper | DISMISS | — |

### Triage Summary -- Review 2 (26 findings)

| ID | Finding | Verdict | Story |
|----|---------|---------|-------|
| C1 | TOCTOU race: IntegrityError unhandled on concurrent team insert | FIX | E-120-08 |
| C2 | Pitching query omits `hr` column; template renders blank | FIX | E-120-07 |
| C3 | `reset.py` executescript() implicit commit makes rollback no-op | DISMISS | DB freshly created; zero practical risk |
| M1 | No server-side validation of `membership_type` | ALREADY COVERED | E-120-03 (AC-1) |
| M2 | Sequential `await` masquerading as concurrent in admin.py | DISMISS | Performance only; single-user admin UI |
| M3 | `_compute_wl` doesn't handle tied games | FIX | E-120-07 |
| M4 | Dashboard auth checks bypass `db.py` with inline raw SQL | DISMISS | Convention preference; simple read-only checks |
| M5 | Opponent detail shows `None-None` for null scores | FIX | E-120-07 |
| M6 | seed_dev.sql `ip_outs=54` doesn't match per-game sum | DISMISS | Same class as P3-1; intentional test data (SE confirmed) |
| M7 | `db.py:831` parameter `filter` shadows Python builtin | FIX | E-120-09 |
| M8 | No XSS escaping tests for `?msg=`/`?error=` query params | FIX | E-120-10 |
| m1 | `spray_charts` table missing NOT NULL / UNIQUE constraints | DISMISS | Schema-ready, not yet populated; premature |
| m2 | Dead `_PlayerPitching.hr` field in game_loader.py | ALREADY COVERED | E-120-07 (field defaults to 0; COALESCE handles DB NULLs; loader populates when API returns HR) |
| m3 | Hardcoded `"spring-hs"` season fallback in dashboard routes | DEFER | Coach: adequate for current HS scope; defer until multi-program |
| m4 | `javascript:history.back()` fragile for direct navigation | FIX | E-120-11 |
| m5 | game_detail.html back links lose team_id context | FIX | E-120-11 |
| m6 | Disabled button checks error message by string equality | DISMISS | Brittle but functional; cosmetic |
| m7 | `admin.py:1150` parameter `id` shadows Python builtin | FIX | E-120-09 |
| m8 | `effective_pub_id` integer fallback when public_id is None (`data.py:388`, not scouting_loader) | FIX | E-120-12 (SE: real bug, misleading warning path) |
| m9 | `_crawl_opponent_rosters` is ~127 lines | DISMISS | No bug; refactoring for length alone |
| m10 | `operations.md` URL parser docs omit bare UUIDs | FIX | E-120-06 |
| m11 | `architecture.md` no mention of port 8001 access | FIX | E-120-06 |
| m12 | `architecture.md` teams table listing omits columns | FIX | E-120-06 |
| m13 | `test_dashboard_auth.py` schema missing `_migrations` seed row | FIX | E-120-05 |
| m14 | Dead `_patch_all` helper in test_bootstrap.py | ALREADY COVERED | E-120-05 (AC-5) |
| m15 | `sys.path.insert` in test files unnecessary with editable install | DISMISS | Harmless; low value cleanup |

### E-116 Fix Pattern
E-116-01 fixed the `load_config()` missing `db_path` bug in `src/gamechanger/pipeline/load.py`. The same bug exists in `src/cli/data.py:460` (the `resolve-opponents` command). The fix pattern is identical: pass the resolved `db_path` to `load_config(db_path)`.

### membership_type Validation Pattern
`_VALID_CLASSIFICATIONS` (admin.py:78) validates classification values. The same pattern should be applied for membership_type with a `_VALID_MEMBERSHIP_TYPES = {"member", "tracked"}` set. Apply in both `confirm_team_submit` and `edit_team_submit` handlers, mirroring how `_VALID_CLASSIFICATIONS` is checked in `_normalize_confirm_inputs` and the edit handler.

### Test Migration Pattern
Several test files (e.g., `test_e100_schema.py`, `test_scouting_loader.py`, `test_crawlers/test_opponent_resolver.py`) already use `run_migrations()` from `migrations` to set up their test databases. `test_admin_teams.py` and `test_admin_opponents.py` instead define an inline `_SCHEMA_SQL` string that is a subset of the real schema — missing CHECK constraints and partial unique indexes. This means tests can pass with data that the real schema would reject.

## Open Questions
None — all findings are scoped and actionable.

### Dispatch Waves
- **Wave 1** (parallel): E-120-01, E-120-03, E-120-05, E-120-06, E-120-07, E-120-11
- **Wave 2** (after wave 1): E-120-02 (after 01), E-120-04 (after 03), E-120-08 (after 03), E-120-10 (after 03, serializes test_admin.py), E-120-12 (after 01, serializes data.py)
- **Wave 3** (after wave 2): E-120-09 (after 08)

### File Conflict Map
| File | Stories | Resolution |
|------|---------|------------|
| `src/cli/data.py` | E-120-01, E-120-12 | Chain: 01 -> 12 |
| `src/api/routes/admin.py` | E-120-03, E-120-04, E-120-08, E-120-09 | Chain: 03 -> 04, 03 -> 08 -> 09 |
| `src/api/routes/dashboard.py` | E-120-07 only | No conflict |
| `src/api/db.py` | E-120-04, E-120-09 | Touch different functions; serialized by wave structure |
| `src/api/templates/dashboard/player_profile.html` | E-120-11 only | No conflict |
| `src/api/templates/dashboard/game_detail.html` | E-120-07, E-120-11 | Different sections (07: hr column/scores; 11: back link). Low conflict. |
| `tests/test_admin.py` | E-120-03, E-120-04, E-120-08, E-120-10 | E-120-04/08 depend on E-120-03; E-120-10 adds independent test (low conflict) |
| `tests/test_admin_teams.py` | E-120-05 only | No conflict |
| `tests/test_admin_opponents.py` | E-120-05 only | No conflict |
| `tests/test_dashboard_auth.py` | E-120-05 only | No conflict |
| `docs/admin/architecture.md` | E-120-06 only | No conflict |
| `docs/admin/operations.md` | E-120-06 only | No conflict |

## History
- 2026-03-17: Created from comprehensive code review of E-100 family. 16 findings triaged: 12 FIX, 4 DISMISS. Grouped into 6 stories across SE and docs-writer. Set to READY.
- 2026-03-17: Refinement pass. Tightened ACs with exact line numbers and file references. Added E-120-04 dependency on E-120-03 (both modify admin.py). Routed E-120-03/04 tests to test_admin.py to avoid conflict with E-120-05 (which modifies test_admin_teams.py and test_admin_opponents.py). Fixed finding count (12 FIX, not 13). Added dispatch wave structure and file conflict map. Confirmed test_cli_data.py already exists.
- 2026-03-17: Second code review triage with expert consultation (SE + Coach). 26 new findings triaged: 3 already covered by stories 01-06, 4 covered by stories 07-10, 5 new FIX items, 1 deferred (m3 season fallback per Coach), 13 dismissed. Replaced E-120-11 (was M4+m3, now m4+m5 dashboard nav fixes per SE recommendation). Created E-120-12 (m8 scouting loader type guard per SE). Key expert inputs: Coach confirmed "T" for tied games, pitcher HR marginal but COALESCE fix sufficient, season fallback adequate; SE confirmed M6 same as P3-1, M2 dismiss, m4+m5 worth grouping, m8 is real bug. Epic now has 12 stories across 3 dispatch waves.
- 2026-03-17: Codex spec review triage (5 findings). ACCEPTED all 5: (1) E-120-12 retargeted from scouting_loader.py to data.py:388 where the bug actually lives, added E-120-01 dependency and data.py to conflict map, moved from wave 1 to wave 2; (2) E-120-06 AC-7 bounded with concrete stop condition (scan schema + routes, note if none found); (3) E-120-07 AC-2 converted to verification-only (season query already has hr at db.py:174); (4) E-120-03 Blocks field updated to list E-120-04/08/10 (was "None", contradicted epic table); (5) E-120-10 Files clarified to test_admin.py (removed ambiguous "or test_admin_teams.py" — dependency is about serializing test_admin.py writes with E-120-03).
- 2026-03-17: COMPLETED. All 12 stories done across 3 dispatch waves. Wave 1 (parallel): 01, 03, 05, 06, 07, 11. Wave 2a (parallel): 02, 04, 12. Wave 2b: 08, 10. Wave 3: 09. Fixes delivered: critical resolve-opponents pipeline bug (01), admin validation hardening (03), opponent count query fix (04), test infrastructure migration to run_migrations() (05), architecture/operations doc corrections (06), dashboard pitching HR + tied games + null scores (07), IntegrityError handling (08), parameter shadowing cleanup (09), XSS regression test (10), dashboard back-link navigation (11), scouting loader type guard (12), and resolve-opponents + scouting loader test coverage (02). Documentation assessment: E-120-06 already delivered doc fixes as a story — no additional docs-writer dispatch needed. Context-layer assessment: (1) New agent capability? No. (2) New conventions/patterns? No — fixes apply existing patterns. (3) New project knowledge for CLAUDE.md? No. (4) Changed file organization? No. (5) Lessons learned for agent definitions? No. (6) New rules/skills needed? No. No context-layer impact.
