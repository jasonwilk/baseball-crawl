# CR-7: Admin & Dashboard Tests Review

**Reviewer**: code-reviewer
**Scope**: tests/test_admin.py, tests/test_admin_teams.py, tests/test_admin_opponents.py, tests/test_dashboard.py, tests/test_dashboard_auth.py
**Date**: 2026-03-17

---

## Critical Issues

### 1. Schema drift risk: test_admin.py uses inline _SCHEMA_SQL instead of run_migrations()

**File**: tests/test_admin.py:45-123

`test_admin.py` defines a 78-line inline `_SCHEMA_SQL` schema instead of calling `run_migrations()` (from `migrations.apply_migrations`). This means:
- The test schema can silently drift from the real migration (`001_initial_schema.sql`)
- Missing tables/columns added in later migrations will not be caught
- E-120-05 reportedly fixed this pattern, but `test_admin.py` still uses the old approach

Both `test_admin_teams.py` and `test_admin_opponents.py` correctly use `run_migrations(db_path=db_path)`. `test_dashboard_auth.py` also uses `run_migrations()`. Only `test_admin.py` and `test_dashboard.py` still use the inline pattern.

### 2. Schema drift risk: test_dashboard.py uses inline _SCHEMA_SQL (~170 lines) instead of run_migrations()

**File**: tests/test_dashboard.py:41-214

Same issue as above but larger -- 174 lines of inline schema. This is the biggest drift risk because the dashboard tests exercise queries against many tables (games, players, season batting/pitching, team_rosters, opponent stats). If the real migration adds columns, constraints, or indexes, these tests will not detect breakage.

The inline schema also omits tables that exist in the real migration (e.g., `programs`, `opponent_links`, `team_opponents`, `scouting_runs`, `spray_charts`). While the dashboard tests may not need those tables, using `run_migrations()` ensures the test DB matches production structure, including FK constraints and indexes.

### 3. Foreign key enforcement inconsistent in inline-schema tests

**File**: tests/test_admin.py (entire file), tests/test_dashboard.py:542-612

Tests using `run_migrations()` consistently call `PRAGMA foreign_keys=ON` (e.g., `test_admin_opponents.py:59`, `test_dashboard_auth.py:55`). Tests using inline `_SCHEMA_SQL` do NOT enable foreign keys:
- `test_admin.py:_make_db()` (line 140-155): no `PRAGMA foreign_keys=ON`
- `test_dashboard.py:_make_seeded_db()` and all DB factory functions: no `PRAGMA foreign_keys=ON`

This means FK violations in application code would not be caught by these tests. With `run_migrations()`, the migration runner may handle this, but the inline-schema tests bypass it entirely.

---

## Warnings

### 1. SQL injection surface in test helper _count_rows

**File**: tests/test_admin.py:221-239, tests/test_admin_teams.py:143-150

The `_count_rows()` helper constructs SQL via f-string: `f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"`. While only called with hardcoded strings in test code (no user input), this pattern is fragile -- a future refactor could inadvertently introduce injection. Consider using parameterized table names or at minimum adding a comment noting the security assumption.

### 2. Hardcoded team ID assumption in test_flat_list_uses_integer_id_in_edit_link

**File**: tests/test_admin_teams.py:255-256

The test asserts `"/admin/teams/1/edit" in response.text`, assuming the first AUTOINCREMENT team will get id=1. This is true for a fresh DB but fragile -- if the test setup ever changes to insert other teams first, or if `run_migrations()` seeds data, the assertion will break. Safer approach: query the actual team id (as done in other tests in the same file, e.g., line 1009-1011).

Same issue at line 267: `"/admin/opponents?team_id=1"`.

### 3. _SCHEMA_SQL in test_dashboard.py missing `programs` table

**File**: tests/test_dashboard.py:41-214

The inline schema lacks the `programs` table. If any dashboard route or template ever queries or joins on programs (which the admin routes already do), these tests will fail with a confusing "no such table" error rather than a clear schema mismatch.

---

## Minor Issues

### 1. Inconsistent `hashed_password` column presence

**File**: tests/test_admin.py:78 vs tests/test_dashboard.py:53

`test_admin.py` inline schema includes `hashed_password TEXT` on the `users` table (line 78). `test_dashboard.py` inline schema omits it (line 53, just `id`, `email`, `created_at`). `test_admin.py:_insert_user()` inserts with `hashed_password=''` (line 170). This inconsistency means the two test files model `users` differently. Using `run_migrations()` in both would eliminate the discrepancy.

### 2. `env.pop()` side-effect in test_dev_mode_any_session_can_access_users_page

**File**: tests/test_admin.py:283-291

This test manually pops `ADMIN_EMAIL` from `os.environ` outside `patch.dict`, then restores it in a try/finally. The `patch.dict` context manager should handle this if `clear=True` is used or if `ADMIN_EMAIL` is simply not included in the dict. The manual manipulation is fragile and could leak state if an exception occurs between pop and restore.

---

## Observations

### Positive findings

1. **Test isolation**: All tests use `tmp_path` for database creation -- no shared state between tests. Each test gets its own DB file.

2. **XSS regression test present** (E-120-10): `TestXSSEscaping` in `test_admin.py:980-999` verifies `<script>` tags are HTML-escaped in `?msg=` query parameter output. Good coverage of the exact payload.

3. **Back-link auth regression test present** (E-120): `test_player_profile_backlink_uses_permitted_team_not_scouting_team` in `test_dashboard.py:1584-1655` is a thorough regression test that creates the exact scenario (scouting team's newer season sorts first) and verifies the backlink points to the permitted team.

4. **Tie display regression test present** (E-120): `test_opponent_detail_last_meeting_shows_tie_not_loss` in `test_dashboard.py:1386-1425` creates a tied game and asserts `T` badge appears (not `L`).

5. **`_compute_wl` unit tests** in `test_dashboard.py:1711-1735` cover all edge cases: home win/loss, away win/loss, null scores, and tied games.

6. **Assertion quality is good**: Tests assert specific behavior (computed stat values, exact HTML content, redirect locations with query params), not just status codes.

7. **Comprehensive opponent admin coverage**: `test_admin_opponents.py` covers all 10 ACs plus E-091 scoped duplicate checks and E-091-01 guard against overwriting resolved links.

8. **Dashboard auth tests** (`test_dashboard_auth.py`) properly test team access control, selector visibility, and integer team_id validation using `run_migrations()` -- well-structured.

9. **`# synthetic-test-data` marker** present at top of all five files.

10. **`from __future__ import annotations`** present in all five files.

### Schema setup summary

| File | Schema method | FK enforcement | Risk |
|------|--------------|----------------|------|
| test_admin.py | inline _SCHEMA_SQL | No | HIGH - drift |
| test_admin_teams.py | run_migrations() | Yes (PRAGMA) | Low |
| test_admin_opponents.py | run_migrations() | Yes (PRAGMA) | Low |
| test_dashboard.py | inline _SCHEMA_SQL | No | HIGH - drift |
| test_dashboard_auth.py | run_migrations() | Yes (PRAGMA) | Low |
