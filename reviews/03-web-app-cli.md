# Code Review: Web Application & CLI

## Critical Issues

### 1. No CSRF Protection on Any POST Form
**Files:** `src/api/routes/admin.py`, `src/api/routes/auth.py`, all admin/auth templates

The application has no CSRF protection on any of its POST endpoints. Every state-mutating form -- user creation, user deletion, team creation, opponent linking, login -- is vulnerable to cross-site request forgery. An attacker could craft a page that auto-submits a form to `/admin/users/1/delete` and delete a user if an admin visits the malicious page while logged in.

FastAPI does not include CSRF middleware by default. The `SameSite=lax` cookie attribute (set in `src/api/routes/auth.py:141`) provides partial mitigation for top-level navigations but does **not** protect against POST-based attacks from cross-origin forms (which are same-site GET redirects followed by POST). The standard fix is a hidden CSRF token in every form validated server-side.

Severity: **High** -- this is the most significant security gap in the web application.

### 2. `|safe` Filter on WebAuthn Options JSON -- Potential XSS
**File:** `src/api/templates/auth/passkey_register.html:32`

```html
{{ options_json | safe }}
```

The `options_json` value comes from `options_to_json(registration_options)` in `src/api/routes/auth.py:579`. While `py_webauthn`'s `options_to_json` should produce clean JSON, the `|safe` filter disables Jinja2's autoescaping entirely. If the `user_display_name` (set to the user's email at line 561) or any other field ever contained `</script>` or similar HTML, it would break out of the `<script>` tag. The server-generated JSON should be escaped properly rather than marked as safe, or at minimum the email should be sanitized before being passed to the WebAuthn library.

A safer pattern: use `{{ options_json }}` (auto-escaped, but breaks JSON parsing) or encode as base64 and decode in JS, or use `json_script` equivalent.

### 3. Broken Backlink in Player Profile Template -- 404
**File:** `src/api/templates/dashboard/player_profile.html:22,26`

```html
<a href="/dashboard/stats?team_id={{ backlink_team_id }}" ...>Back to Team Stats</a>
<a href="/dashboard/stats" ...>Back to Team Stats</a>
```

The route `/dashboard/stats` does not exist. The batting stats dashboard route is `/dashboard` (defined in `src/api/routes/dashboard.py:48`). These links will produce a 404 for every user who clicks "Back to Team Stats" from a player profile page. This is a user-facing bug affecting core navigation.

### 4. OBP Formula Missing HBP
**Files:** `src/api/templates/dashboard/team_stats.html:57`, `src/api/templates/dashboard/opponent_detail.html:129`, `src/api/templates/dashboard/player_profile.html:51,106`

The OBP calculation across all templates is:

```jinja
{{ (player.h + player.bb) | format_avg(player.ab + player.bb) }}
```

The correct OBP formula is `(H + BB + HBP) / (AB + BB + HBP + SF)`. The `player_season_batting` table has `hbp` and `shf` columns, and the db queries for team batting stats do not fetch them (`src/api/db.py:78-92` only selects `h, ab, bb, so, sb` etc., not `hbp` or `shf`). This means OBP is systematically understated for players who get hit by pitches -- a meaningful coaching metric error.

Similarly, SLG in templates uses `(h + doubles + 2*triples + 3*hr) / ab` which is `(1B + 2*2B + 3*3B + 4*HR) / AB` -- but since `h` already includes extra-base hits, the numerator should be `(h + doubles + 2*triples + 3*hr)` which equals `(singles + 2*doubles + 3*triples + 4*hr)` only if `h = singles + doubles + triples + hr`. Looking at the data model, `h` is total hits and the template adds `doubles` on top, so the SLG numerator is actually: `h + doubles + 2*triples + 3*hr = (singles + doubles + triples + hr) + doubles + 2*triples + 3*hr = singles + 2*doubles + 3*triples + 4*hr`. This is correct -- the total bases formula. My mistake on SLG, but the OBP issue remains.

### 5. Magic Link Token Stored as Plaintext
**File:** `src/api/routes/auth.py:341-346`

```python
conn.execute(
    "INSERT INTO magic_link_tokens (token, user_id, expires_at) VALUES (?, ?, ...)",
    (raw_token, user_id),
)
```

The magic link token is stored in cleartext in the database. If an attacker gains read access to the SQLite file (backup leak, directory traversal, shared hosting), they can steal any unexpired magic link token and log in as any user. The session tokens are properly hashed via `hash_token()` before storage (`src/api/auth.py:96`), but magic link tokens do not receive the same treatment. The `verify_token` function at line 388 does a plaintext lookup: `WHERE token = ?`.

For a high-school coaching app this is medium severity, but it's inconsistent with the session token handling which correctly uses SHA-256 hashing.


## Important Issues

### 6. Passkey Challenge Store Is Not Process-Safe
**File:** `src/api/routes/auth.py:77-88`

```python
_PASSKEY_LOGIN_CHALLENGES: dict[str, float] = {}
_PASSKEY_REG_CHALLENGES: dict[str, tuple[str, float]] = {}
```

The WARNING comments acknowledge this but the code still ships with in-memory challenge stores. With `uvicorn --workers N > 1` (the standard production configuration for performance), passkey login/registration will silently fail -- a challenge generated by worker A will not be found by worker B. The comments say "Move to SQLite if scaling" but the current Docker CMD (`src/api/main.py` referenced from Dockerfile:41) uses a single worker, so this is a latent issue rather than an active bug. However, there is no CI check or runtime guard preventing multi-worker deployment.

### 7. `format_avg` Treats `numerator=None` as 0 Silently
**File:** `src/api/helpers.py:69`

```python
avg = (numerator or 0) / denominator
```

When `numerator` is `None` and `denominator` is non-zero, this returns `.000` instead of `-`. This silently converts missing data into a definitive "zero batting average" in the dashboard. The COALESCE in the SQL queries should prevent None from reaching here, but if a query path changes or new data sources are added, this will produce misleading stats rather than a clear "no data" indicator.

### 8. Unbounded In-Memory Challenge Stores
**File:** `src/api/routes/auth.py:77-88`

The `_PASSKEY_LOGIN_CHALLENGES` dict is never bounded. While `_purge_expired_challenges()` removes expired entries, it only runs when explicitly called. An attacker could issue thousands of `GET /auth/passkey/login/options` requests to grow the dict unboundedly, consuming server memory. Each entry is small (base64 string + float), but there's no rate limiting or maximum size cap.

### 9. Admin DB Helpers Don't Wrap in Try/Except
**File:** `src/api/routes/admin.py:148-168, 177-184, 196-202, etc.`

The admin DB helper functions (`_get_all_users`, `_get_available_teams`, `_get_user_by_id`, `_get_user_team_ids`, `_get_team_by_integer_id`, `_get_all_teams_flat`, etc.) do NOT wrap their database calls in try/except like the `src/api/db.py` functions do. If the database is locked or has a transient error, these will propagate as unhandled 500 errors. The dashboard DB functions in `src/api/db.py` consistently catch `sqlite3.Error` and return empty results, but the admin helpers let exceptions bubble up.

### 10. No Rate Limiting on Login Endpoint
**File:** `src/api/routes/auth.py:280-356`

The magic link rate limit (lines 319-332) only prevents re-issuance for a known user within 60 seconds. There is no IP-based or global rate limit on `POST /auth/login`. An attacker could enumerate emails at high speed (the response is identical for known/unknown emails, but timing side-channels may exist due to the database lookup for known users triggering additional queries for token insertion). More importantly, an attacker could use this endpoint to spam arbitrary email addresses if Mailgun is configured.

### 11. Dashboard Routes Have Heavy Code Duplication
**File:** `src/api/routes/dashboard.py` -- lines 48-129 vs 183-267 vs 294-373 vs 472-549

Every dashboard route handler repeats the same pattern:
1. Get `permitted_teams` from request state
2. Check for no assignments
3. Parse and validate `team_id` query param
4. Parse `season_id` with default
5. Fetch data
6. Find team name
7. Render template

This ~30-line block is copied 4+ times with minor variable name variations (`active_team_id_p`, `active_team_id_g`, `active_team_id_o`, `active_team_id_od`). A shared helper function could eliminate this duplication.

### 12. No Test for Health Endpoint
**File:** No `tests/test_health.py` exists

The health endpoint (`/health`) is tested indirectly as a middleware exclusion path in `test_auth.py:326-330`, but there's no dedicated test that verifies:
- Returns `{"status": "ok", "db": "connected"}` with 200 when DB is healthy
- Returns `{"status": "error", "db": "error"}` with 503 when DB is unreachable

### 13. `_resolve_db_path` Duplicated Between CLI and API
**Files:** `src/api/db.py:26-35`, `src/cli/data.py:430-436`

Both modules implement their own version of "read DATABASE_PATH env var, fall back to default". The CLI version has additional logic for relative paths. This is a DRY violation that could lead to divergent behavior.


## Minor Issues

### 14. Missing `from __future__ import annotations` in Several `__init__.py` Files
**Files:** `src/api/__init__.py`, `src/api/routes/__init__.py`, `src/cli/__main__.py`

Per `python-style.md`: "Use `from __future__ import annotations` at the top of each module." These three files are comment-only or minimal, but the convention applies to all modules. Since these files contain only comments or minimal code, this is cosmetic.

### 15. Inconsistent Variable Naming in Dashboard Route Handlers
**File:** `src/api/routes/dashboard.py`

Variables are suffixed with letters to avoid name collisions across handlers: `active_team_id_p` (pitching), `active_team_id_g` (games), `active_team_id_o` (opponents), `active_team_id_od` (opponent detail), `active_team_id_gd` (game detail). This makes the code harder to read. Each handler is an independent function, so the same variable name (`active_team_id`) could be reused safely.

### 16. Local Imports Inside Functions
**File:** `src/api/routes/dashboard.py:669,823` and `src/api/routes/auth.py:729,817`

Functions like `_check_opponent_authorization` and `_check_player_authorization` import `sqlite3` and `closing` inside the function body, despite these already being imported at module level in the parent module (`src/api/db.py`). In `auth.py`, `import json` appears at line 729 inside a function despite being a stdlib module. These should use the module-level imports.

### 17. `_DEFAULT_DB_PATH` Uses `parents[2]` -- Fragile Path Calculation
**File:** `src/api/db.py:23`

```python
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "app.db"
```

This is documented convention per `python-style.md`, but `src/api/db.py` is at depth 3 (`src/api/db.py`), so `parents[2]` goes to the repo root (parents: `api/`, `src/`, repo-root). This is correct. No action needed -- noting for completeness.

### 18. `_human_size` in `src/cli/status.py` Could Overflow
**File:** `src/cli/status.py:29-36`

The function converts bytes through B -> KB -> MB -> GB -> TB, but the loop uses `("B", "KB", "MB", "GB")` and only falls through to TB after the loop. For files > 1TB (unlikely for SQLite), it works correctly. This is fine for the use case.

### 19. Jinja2 Templates Load Tailwind from CDN
**Files:** `src/api/templates/base.html:7`, `src/api/templates/base_auth.html:7`

```html
<script src="https://cdn.tailwindcss.com"></script>
```

The Tailwind CSS CDN script is for development only per Tailwind's docs and adds ~300KB of JS on every page load. For production, this should be replaced with a build step that generates a minimal CSS file. This is acceptable for the current stage but should be addressed before production deployment.


## Observations

### Things Done Well

1. **Session security is solid**: SHA-256 hashed session tokens, httponly cookies, SameSite=lax, secure flag in production, 7-day TTL. The session architecture follows security best practices.

2. **DEV_USER_EMAIL production guard**: The `SessionMiddleware.__init__` raises `RuntimeError` if `DEV_USER_EMAIL` is set with `APP_ENV=production`. This is a good defense against accidentally shipping dev bypasses.

3. **Fail-closed on missing auth tables**: The middleware returns 503 when auth tables are missing rather than silently allowing unauthenticated access. This is tested thoroughly in `test_auth.py`.

4. **User enumeration prevention**: `POST /auth/login` returns the same "check your email" response for both known and unknown addresses.

5. **Admin self-delete prevention**: `src/api/routes/admin.py:744` prevents admins from deleting their own account.

6. **Authorization checks on all dashboard routes**: Every dashboard route validates `permitted_teams`, and opponent/player/game detail pages have additional authorization checks ensuring users can only view data for teams they have access to.

7. **Thorough auth test coverage**: `test_auth.py` covers valid sessions, invalid sessions, expired sessions, dev bypass, production guards, and missing auth tables. `test_auth_routes.py` covers the magic link lifecycle.

8. **SQL injection prevention**: All SQL queries use parameterized queries (`?` placeholders). The few `f-string` SQL constructions (e.g., `db.py:136`, `dashboard.py:675`) use `",".join("?" ...)` to build placeholder lists, which is safe.

9. **Clean CLI structure**: The `bb` CLI uses Typer with well-organized sub-command groups, proper help text, and consistent exit code handling.

10. **Passkey implementation completeness**: The full WebAuthn flow (registration + authentication) is implemented with proper challenge-response, sign count tracking, and user-friendly error handling.

### Architectural Patterns

- **Synchronous SQLite with `run_in_threadpool`**: Dashboard and admin routes use `run_in_threadpool` to avoid blocking the async event loop. This is the correct pattern for synchronous SQLite with async FastAPI.

- **Connection-per-request**: Each DB call opens a new connection via `get_connection()` with WAL mode and foreign keys. This is simple and correct for SQLite's concurrency model.

- **Template-per-route**: Each route has a dedicated template with `base.html` inheritance. The `_team_selector.html` macro is properly shared across dashboard pages.


## Summary

The web application is functional and well-structured for its purpose as a high-school coaching tool. The codebase shows consistent patterns, good test coverage for auth flows, and proper use of parameterized SQL.

**Critical concerns** center on the absence of CSRF protection (the most impactful security gap), a broken navigation link in player profiles, the OBP formula missing HBP, and plaintext magic link token storage.

**Important concerns** include the process-unsafe passkey challenge stores (latent issue until multi-worker deployment), admin DB helpers lacking error handling, significant code duplication in dashboard routes, and missing health endpoint tests.

The CLI layer is clean and well-organized, with proper exit codes and help text. The main gap there is the duplicated DB path resolution logic.

Overall, the application is in good shape for development/staging use. Before production deployment, CSRF protection and the broken backlink should be addressed as priorities.
