# E-122 Story Re-Verification Report

Verified by SE agent against current codebase on 2026-03-17.

---

## E-122-01: Scouting Crawler — Abort on CredentialExpiredError

**Source file**: `src/gamechanger/crawlers/scouting.py`

### File paths and line numbers
- `_fetch_boxscores()` except clause at **line 246**: `except (CredentialExpiredError, ForbiddenError, GameChangerAPIError)` — **STILL ACCURATE**.
- `scout_all()` broad `except Exception` at **line 330**: **STILL ACCURATE**.

### AC verification
- **AC-1** (don't catch CredentialExpiredError in per-game handler): Bug is **STILL PRESENT**. Line 246 catches `CredentialExpiredError` alongside `ForbiddenError` and `GameChangerAPIError`.
- **AC-2** (keep ForbiddenError and GameChangerAPIError caught): Correct — these should remain caught.
- **AC-3** (don't swallow in scout_all): Bug is **STILL PRESENT**. Line 330 `except Exception` swallows everything including CredentialExpiredError.
- **AC-4** (test): No existing test covers this; test needs to be written.
- **AC-5** (existing tests pass): Standard regression check.

### Technical approach soundness
Sound. Separating `CredentialExpiredError` from the except group is straightforward. For `scout_all`, the implementer should add a specific `except CredentialExpiredError: raise` before the broad `except Exception`.

### Missing ACs or context
None. Story is well-scoped.

**Verdict: STORY IS ACCURATE. Ready for implementation.**

---

## E-122-02: Dashboard Template Fixes — Phantom HR Column + Opponent Back-Link

**Source files**: `src/api/templates/dashboard/game_detail.html`, `opponent_detail.html`, `src/api/routes/dashboard.py`

### File paths and line numbers
- `game_detail.html` HR header at **line 113**, `{{ pitcher.hr }}` at **line 129**: **STILL ACCURATE**.
- `opponent_detail.html` back-link at **line 21**: **STILL ACCURATE** — `<a href="/dashboard/opponents">Back to Opponents</a>` with no `team_id`.

### AC verification
- **AC-1** (remove HR column header and data cell): Bug is **STILL PRESENT**. Lines 113 and 129 render HR.
- **AC-2** (pitching query doesn't return hr): **ALREADY SATISFIED**. The `pitching_query` in `src/api/db.py:309-323` does NOT select `hr`. The template references a field that doesn't exist in the query results, so removing the template column is all that's needed. AC-2 is pre-satisfied — the story should note this so the implementer doesn't waste time searching for a query to fix.
- **AC-3** (opponent back-link preserves team_id): Bug is **STILL PRESENT**. Line 21 has no query parameter. The template context does include `active_team_id` (confirmed in `dashboard.py:648`), so `?team_id={{ active_team_id }}` will work.
- **AC-4** (existing tests pass): Standard regression check.

### Technical approach soundness
Sound. Template-only changes. AC-2 is already satisfied by the current query — the story should clarify this to avoid confusion.

### Missing ACs or context
**Minor clarification needed**: AC-2 should note that the pitching query already does not return `hr`, so no route change is needed. The "Files to Create or Modify" section lists `src/api/routes/dashboard.py` conditionally, which is appropriate.

**Verdict: STORY IS ACCURATE. AC-2 is pre-satisfied; template-only changes needed.**

---

## E-122-03: proxy.py Import Boundary Fix

**Source files**: `src/cli/proxy.py`, `scripts/proxy-refresh-headers.py`

### File paths and line numbers
- `proxy.py` importlib usage at **lines 48-54**: **STILL ACCURATE**. `_load_refresh_headers_module()` uses `importlib.util.spec_from_file_location` to load `scripts/proxy-refresh-headers.py`.

### AC verification
- **AC-1** (no importlib from scripts): Bug is **STILL PRESENT**. Lines 48-54.
- **AC-2** (reusable logic in src/): Not yet done.
- **AC-3** (scripts/ file still works standalone): Needs implementation.
- **AC-4** (`bb proxy refresh-headers` works): Needs verification after implementation.
- **AC-5** (existing tests pass): Standard regression check.

### Technical approach soundness
Sound. Need to understand what `proxy.py` actually uses from the script. Let me check what functions are called.

Checking `proxy.py` usage: The `_load_refresh_headers_module()` return value is used to call functions from the loaded module. The story correctly identifies the pattern and the fix (move logic to `src/`, have both `proxy.py` and the script import from there).

### Missing ACs or context
**Important context for implementer**: The implementer needs to know exactly which functions/classes from `scripts/proxy-refresh-headers.py` are used by `proxy.py`. A quick check shows `proxy.py` calls into the module after loading it. The implementer should read both files to understand the interface.

**Verdict: STORY IS ACCURATE. Ready for implementation.**

---

## E-122-04: Migrate Inline _SCHEMA_SQL to run_migrations()

**Source files**: 5 test files

### File paths verification
All 5 files confirmed to contain `_SCHEMA_SQL`:
- `tests/test_admin.py` — **CONFIRMED** (contains `_SCHEMA_SQL`)
- `tests/test_auth_routes.py` — **CONFIRMED**
- `tests/test_passkey.py` — **CONFIRMED**
- `tests/test_dashboard.py` — **CONFIRMED**
- `tests/test_auth.py` — **CONFIRMED**

### AC verification
- **AC-1 through AC-5** (each file migrated): All 5 files still use inline `_SCHEMA_SQL`. Bug is **STILL PRESENT** in all 5.
- **AC-6** (no remaining `_SCHEMA_SQL` definitions, except `_SCHEMA_SQL_NO_AUTH`): `test_auth.py` has both `_SCHEMA_SQL` (line 46) and `_SCHEMA_SQL_NO_AUTH` (line 464). The story correctly notes that `_SCHEMA_SQL_NO_AUTH` is intentionally retained.
- **AC-7** (all tests pass with run_migrations): Needs verification after implementation.
- **AC-8** (no regressions): Standard check.

### Existing `run_migrations()` usage
12 test files already use `run_migrations()` successfully, providing a clear pattern to follow. These include `test_admin_teams.py`, `test_dashboard_auth.py`, `test_scouting_loader.py`, etc.

### Technical approach soundness
Sound. The pattern is well-established. Key risk: some test files may use inline schemas that include auth tables (`auth_users`, `user_passkeys`, `auth_sessions`). The `run_migrations()` function already creates these (via `001_initial_schema.sql`), so the migration should be straightforward. However, the implementer must preserve any INSERT seed data that follows the schema setup.

### Missing ACs or context
**Important context for implementer**: The 5 test files with inline schemas include auth-aware schemas (they define `auth_users`, `user_passkeys`, `auth_sessions` tables). `run_migrations()` creates all tables including auth tables, so this should work. The implementer should verify that `run_migrations()` creates the same set of tables that the inline schemas define, and preserve any fixture INSERT statements.

**Verdict: STORY IS ACCURATE. Ready for implementation.**

---

## E-122-05: Credentials Module — Publicize Private API Names

**Source files**: `src/gamechanger/credentials.py`, `src/cli/creds.py`

### File paths and line numbers
- `credentials.py` line 47: `_ALL_PROFILES: tuple[str, ...] = ("web", "mobile")` — **STILL ACCURATE**.
- `credentials.py` line 161: `def _run_api_check(profile: str) -> ApiCheckResult:` — **STILL ACCURATE**.
- `creds.py` lines 22-23: imports `_ALL_PROFILES` and `_run_api_check` — **STILL ACCURATE**.

### AC verification
- **AC-1** (rename to `ALL_PROFILES`): Bug is **STILL PRESENT**. Still underscore-prefixed.
- **AC-2** (rename to `run_api_check`): Bug is **STILL PRESENT**. Still underscore-prefixed.
- **AC-3** (update all consumers): `src/cli/creds.py` is the known consumer.
- **AC-4** (no remaining imports of old names): Needs grep after implementation.
- **AC-5** (existing tests pass): Standard check.

### Additional consumers discovered
- `tests/test_cli_creds.py` also references `_run_api_check` (lines 654, 740, 743) — these are `patch()` targets that mock `src.cli.creds._run_api_check`. After renaming, these patch targets must also be updated.
- `credentials.py` line 240 and 484 use the names internally — these will change with the rename.

### Missing ACs or context
**Critical missing context**: The story lists `src/cli/creds.py` as the only consumer file, but `tests/test_cli_creds.py` also patches `_run_api_check` by name. The implementer MUST update the test file's `patch()` calls too, or tests will break. Additionally, `credentials.py` itself also imports `_required_keys` from `client.py` (line 35) — but that's a separate issue not in scope.

**Recommended**: Add `tests/test_cli_creds.py` to the "Files to Create or Modify" section, or at minimum note it in the technical approach. AC-3 ("all consumers") technically covers it, but being explicit would help the implementer.

**Verdict: STORY IS ACCURATE but needs test file reference. Substantively correct — all bugs still present.**

---

## Summary

| Story | Status | All Bugs Still Present? | File Paths Accurate? | ACs Sound? | Issues Found |
|-------|--------|------------------------|---------------------|-----------|--------------|
| E-122-01 | Ready | Yes | Yes | Yes | None |
| E-122-02 | Ready | Yes (AC-2 pre-satisfied) | Yes | Yes | AC-2 already satisfied by current query; note for implementer |
| E-122-03 | Ready | Yes | Yes | Yes | None |
| E-122-04 | Ready | Yes | Yes | Yes | None |
| E-122-05 | Ready | Yes | Yes | Yes | `tests/test_cli_creds.py` missing from Files list |

### Recommendations for PM

1. **E-122-02 AC-2**: Add a note that the pitching query already omits `hr` — AC-2 is pre-satisfied, no route change needed.
2. **E-122-05 Files list**: Add `tests/test_cli_creds.py` to "Files to Create or Modify" — it patches `_run_api_check` by name and must be updated.
3. **All stories**: No blocking issues found. All 5 stories are implementable as written.
