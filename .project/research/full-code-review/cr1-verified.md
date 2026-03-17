# CR1 (Web App & Auth) — Verified Findings

**Verifier**: software-engineer
**Date**: 2026-03-17

---

## Critical Issues

### C1 — No CSRF protection on any POST route
**Verdict**: CONFIRMED
**Evidence**: Grep for `csrf`/`CSRF` across `src/api/` returns no matches. All POST routes in `src/api/routes/admin.py` and `src/api/routes/auth.py` use `<form method="post">` with no token. The `SameSite=Lax` cookie attribute provides partial mitigation for cross-origin POST (blocks it in modern browsers), which the reviewer correctly noted.
**Notes**: Severity is appropriately rated. SameSite=Lax is a strong practical mitigation — cross-site POST is blocked in all modern browsers. The remaining attack surface is narrow (top-level navigation edge cases, very old browsers). This is a defense-in-depth concern, not an actively exploitable vulnerability in the current deployment context (single admin user behind Cloudflare Zero Trust). Not covered by E-122.

### C2 — Cascade delete omits `coaching_assignments` table — FK violation
**Verdict**: CONFIRMED
**Evidence**: `src/api/routes/admin.py:279-294` — `_delete_user()` deletes from `user_team_access`, `sessions`, `magic_link_tokens`, `passkey_credentials`, then `users`. The `coaching_assignments` table has `user_id INTEGER NOT NULL REFERENCES users(id)` (migrations/001_initial_schema.sql:469). No `DELETE FROM coaching_assignments` appears in `_delete_user()`. With `PRAGMA foreign_keys=ON`, deleting a user with coaching assignments will raise `IntegrityError`.
**Notes**: Not covered by E-122. This is a genuine bug — the cascade is incomplete.

### C3 — XSS in JavaScript context — admin user delete confirmation
**Verdict**: CONFIRMED (low practical risk)
**Evidence**: `src/api/templates/admin/users.html:57` — `onsubmit="return confirm('Delete {{ user.email }}? ...');"`. The `{{ user.email }}` is Jinja2 auto-escaped for HTML, but within an inline JS string in an HTML attribute, the HTML-decoded value could break out of the JS string. The reviewer correctly assessed practical risk as low (emails are admin-controlled).
**Notes**: Not covered by E-122. The fix (`|tojson` filter or `data-*` attribute) is trivial. Low priority given admin-only context.

---

## High Priority

### H1 — In-memory passkey challenge stores don't survive restarts / break with multiple workers
**Verdict**: CONFIRMED
**Evidence**: `src/api/routes/auth.py:81-88` — `_PASSKEY_LOGIN_CHALLENGES` and `_PASSKEY_REG_CHALLENGES` are module-level dicts. The WARNING comments at lines 78-80 and 87 acknowledge the single-worker constraint but there's no enforcement. No size cap exists on the dicts.
**Notes**: Not covered by E-122. The code comments explicitly acknowledge this limitation. Low urgency — deployment is single-worker behind Cloudflare Zero Trust with a small number of admin users.

### H2 — No session garbage collection
**Verdict**: CONFIRMED
**Evidence**: `src/api/auth.py` — `_resolve_session_from_cookie` filters by `expires_at > datetime('now')` but never deletes expired rows. `src/api/routes/auth.py:417-421` cleans up individual expired magic link tokens when presented, but bulk cleanup never occurs. No scheduled cleanup task or `bb db cleanup` command exists.
**Notes**: Not covered by E-122. Very low urgency for current scale (single admin user, ~30 games/season). Table growth will be negligible for years.

### H3 — `_is_excluded_path` uses prefix matching with `/health` — overly broad
**Verdict**: NEEDS CONTEXT
**Evidence**: `src/api/auth.py:44` — `_EXCLUDED_PREFIXES = ("/auth/", "/health", "/static/")`. The reviewer is correct that `/health` as a prefix would match `/health-dashboard`. However, `_is_excluded_path()` (lines 61-77) normalizes the path by appending `/` if not present, so `/health` matches as `"/health"` starts with `"/health"` — this is correct for the existing route. The concern is about hypothetical future routes that happen to start with `/health`.
**Notes**: Not covered by E-122. The risk is speculative — no such routes exist. The fix is trivial (move `/health` to `_EXCLUDED_EXACT`). Low priority.

### H4 — `email.py` uses raw `httpx.AsyncClient()` without configured headers
**Verdict**: CONFIRMED (acceptable)
**Evidence**: `src/api/email.py:59` — `async with httpx.AsyncClient() as client:` — bare client with no custom headers. The reviewer correctly noted that HTTP discipline rules are scoped to `src/gamechanger/**` and this is a first-party Mailgun API call.
**Notes**: Not covered by E-122. This is acceptable and low priority. The Mailgun API doesn't require browser-like headers.

### H5 — Duplicate schema SQL across test files
**Verdict**: CONFIRMED
**Evidence**: `_SCHEMA_SQL` constant found in 5 test files: `tests/test_auth.py`, `tests/test_auth_routes.py`, `tests/test_passkey.py`, `tests/test_admin.py`, `tests/test_dashboard.py`. Other test files (e.g., `test_dashboard_auth.py`, `test_coaching_assignments.py`) already use `run_migrations()`.
**Notes**: **Covered by E-122-04** — "Migrate inline _SCHEMA_SQL to run_migrations()" explicitly targets these 5 files.

### H6 — `get_team_batting_stats` silently returns empty list on DB error
**Verdict**: CONFIRMED
**Evidence**: `src/api/db.py:111-113` — `except sqlite3.Error: logger.exception(...); return []`. This pattern is repeated across all query functions in `db.py`. The dashboard cannot distinguish "no data" from "database error".
**Notes**: Not covered by E-122. This is a design decision (fail-safe vs fail-loud). The health check endpoint provides a separate database liveness signal. For a single-admin coaching dashboard, silent degradation with logging is arguably the right choice. Medium priority at most.

---

## Medium Priority

### M1 — `_compute_pitching_rates` duplicated three times
**Verdict**: CONFIRMED
**Evidence**: Three nearly identical functions:
- `_compute_pitching_rates` at `src/api/routes/dashboard.py:152-180` (team pitching)
- `_compute_opponent_pitching_rates` at `src/api/routes/dashboard.py:396-425` (opponent scouting — adds `avg_pitches`, omits `bb9`)
- `_compute_player_pitching_rates` at `src/api/routes/dashboard.py:782-807` (player profile — omits `bb9`)
All use the same ERA/K9/WHIP formulas. The differences are minor: `_compute_pitching_rates` also computes `bb9`, `_compute_opponent_pitching_rates` adds `avg_pitches`.
**Notes**: Not covered by E-122. Code smell, not a bug. Low priority.

### M2 — Team ID authorization check repeated in every dashboard route
**Verdict**: CONFIRMED
**Evidence**: Identical pattern at lines 88-98, 222-232, 331-341, 508-518 of `src/api/routes/dashboard.py`. Each copy uses slightly different variable suffixes (`active_team_id`, `active_team_id_p`, `active_team_id_g`, `active_team_id_o`) to avoid naming collision.
**Notes**: Not covered by E-122. Code smell, not a bug. Low priority.

### M3 — `_check_opponent_authorization` and `_check_player_authorization` use inline imports
**Verdict**: CONFIRMED
**Evidence**: `src/api/routes/dashboard.py:669-670` (`_check_opponent_authorization`) and `823-824` (`_check_player_authorization`) both have `import sqlite3 as _sqlite3` and `from contextlib import closing as _closing` inline. Both `sqlite3` and `closing` are used at module scope elsewhere in this file.
**Notes**: Not covered by E-122. Trivial cleanup. These functions don't even use their inline imports — they actually use the module-level `sqlite3` and `closing`. Wait, let me re-check — they alias to `_sqlite3` and `_closing`, then use those aliases. Either way, the module-level imports would suffice.

### M4 — No test for `_delete_user` with coaching_assignments present
**Verdict**: CONFIRMED
**Evidence**: Grep for `coaching_assignments` in `tests/test_admin.py` returns no matches. The `TestCascadeDelete` class tests deletion of sessions, magic link tokens, and passkey credentials, but not coaching assignments.
**Notes**: This is the test gap that would catch C2. Not covered by E-122 (E-122 doesn't address the cascade delete bug).

### M5 — `format_avg` treats negative denominators the same as zero
**Verdict**: CONFIRMED (negligible)
**Evidence**: `src/api/helpers.py:67` — `if not denominator:` is truthy for `0`, `None`, and negative numbers. Negative denominators are essentially impossible in baseball stats (negative at-bats don't exist).
**Notes**: Not covered by E-122. Negligible risk. Not worth fixing.

### M6 — Stale expired magic link tokens not cleaned up on verification failure
**Verdict**: CONFIRMED
**Evidence**: `src/api/routes/auth.py:415-423` — only the specific presented expired token is cleaned up. This is a subset of H2 (no session/token garbage collection).
**Notes**: Duplicate of H2. Not covered by E-122. Very low priority.

### M7 — `get_player_profile` recent games deduplication loses pitching data for two-way players
**Verdict**: CONFIRMED
**Evidence**: `src/api/db.py:747-752` — `if gid not in games_by_id or row["appearance_type"] == "batting": games_by_id[gid] = row`. For a two-way player who both bats and pitches in the same game, only the batting row is kept in recent games. Pitching data (ip_outs, er, so_pitched) from that game is lost.
**Notes**: Not covered by E-122. Real bug but affects only two-way players' recent games display. The season-level pitching stats are not affected (separate query). Medium priority.

---

## Low Priority

### L1 — `_SESSION_COOKIE_NAME` and `_SESSION_MAX_AGE` defined in two places
**Verdict**: CONFIRMED
**Evidence**: `src/api/auth.py:39-41` defines `_SESSION_COOKIE_NAME = "session"` and `_SESSION_MAX_AGE = 604800`. `src/api/routes/auth.py:68-69` defines identical constants. Neither imports from the other.
**Notes**: Not covered by E-122. Code smell, low priority.

### L2 — `test_api_health.py` uses `sys.path` manipulation
**Verdict**: CONFIRMED (acceptable)
**Evidence**: `tests/test_api_health.py:24-26` — `sys.path.insert(0, str(_PROJECT_ROOT))`. This is common across test files and is acceptable per project conventions (test files are not `src/` modules).
**Notes**: Not covered by E-122. Not a real issue — acceptable per project conventions.

### L3 — `format_date` uses platform-dependent `%-d`
**Verdict**: CONFIRMED (acceptable)
**Evidence**: `src/api/helpers.py:99` — `dt.strftime("%b %-d")`. `%-d` is a GNU extension. The deployment target is Linux (Docker), so this works. Would fail on Windows.
**Notes**: Not covered by E-122. Acceptable for the deployment target.

### L4 — `get_teams_by_ids` parameter type annotation
**Verdict**: CONFIRMED (non-issue)
**Evidence**: `src/api/db.py:116-138` — The function works correctly. The `placeholders` construction is safe (not user-controlled). The reviewer confirmed it works.
**Notes**: Not covered by E-122. Not a real issue.

### L5 — `_APP_URL_DEFAULT` hardcodes port 8001
**Verdict**: CONFIRMED
**Evidence**: `src/api/routes/auth.py:70` — `_APP_URL_DEFAULT = "http://baseball.localhost:8001"`. The Dockerfile exposes port 8000. In production, `APP_URL` is always set via environment variable, so the default is only used in dev.
**Notes**: Not covered by E-122. Minor config inconsistency. Low priority.

### L6 — `500` exception handler may not fire for all 500 errors
**Verdict**: CONFIRMED (acceptable)
**Evidence**: `src/api/main.py:117-122` — `@app.exception_handler(500)` catches unhandled exceptions that FastAPI converts to 500 responses. Middleware-level exceptions (e.g., in the session middleware) may be caught by Starlette before FastAPI's handler. This is a known limitation of FastAPI's exception handling architecture.
**Notes**: Not covered by E-122. This is a FastAPI framework limitation, not a bug in our code. The session middleware already has its own error handling (returns 503 for missing auth tables).

---

## E-122 Overlap Summary

| Finding | Covered by E-122? |
|---------|-------------------|
| H5 (duplicate schema SQL in tests) | Yes — E-122-04 |
| All others | No |

## Actionable Findings Not in E-122

**Bugs (should fix)**:
- C2: Cascade delete missing `coaching_assignments` — FK violation
- M7: Two-way player recent games loses pitching data

**Security hardening (consider)**:
- C1: CSRF protection (mitigated by SameSite=Lax + Cloudflare ZT)
- C3: XSS in JS context (low practical risk, trivial fix)

**Code quality (nice to have)**:
- H3: `/health` prefix matching (speculative risk)
- L1: Duplicated session constants
- M1-M3: Code duplication / inline imports
