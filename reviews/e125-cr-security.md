# Code Review: E-125 Security Stories (01, 02, 05)

## Critical Issues

### 1. CSRF middleware only validates POST — PUT/DELETE/PATCH bypass (csrf.py:74)

The CSRF middleware checks `request.method == "POST"` but does not validate other state-changing HTTP methods (PUT, DELETE, PATCH). While the current routes only use POST for state changes, this is a defense-in-depth gap. If any future route uses PUT/DELETE/PATCH, it will bypass CSRF validation silently.

**Current impact**: Low (no PUT/DELETE/PATCH routes exist today).
**Recommended fix**: Change line 74 to check `request.method in ("POST", "PUT", "DELETE", "PATCH")` or equivalently check `request.method not in ("GET", "HEAD", "OPTIONS", "TRACE")`.

### 2. CSRF cookie lacks HttpOnly=false explicit documentation but is correctly not HttpOnly

The CSRF cookie is intentionally not HttpOnly (JS needs to read it for fetch-based POSTs). This is correctly implemented — the cookie string at line 137 does not include `HttpOnly`. The JS code in `login.html:133` and `passkey_register.html:101` correctly reads it via `document.cookie.match()`. This is **not a vulnerability** — just noting the design is correct.

**Verdict**: No action needed.

### 3. CSRF token not rotated after successful authentication (csrf.py:127-128)

The CSRF token is generated once (on first visit when no cookie exists) and reused for the entire session lifetime. After successful login, the same CSRF token persists. Best practice for double-submit cookies is to rotate the token after authentication to prevent session fixation attacks on the CSRF token.

**Current impact**: Low — SameSite=Lax on the session cookie and the session middleware provide additional protection layers.
**Recommended fix**: Consider regenerating the CSRF cookie after successful authentication in the `verify_token` and `post_passkey_login_verify` handlers.

## Important Issues

### 4. Magic link token column named `token` but now stores hashes — schema/code mismatch (migrations/001_initial_schema.sql:443)

The schema comment says "passwordless login tokens" and the column is named `token`, but E-125-02 changed the code to store SHA-256 hashes instead of raw tokens. The schema comment at line 20-21 of `auth.py` still says `magic_link_tokens.token is TEXT PRIMARY KEY (raw token stored directly; DELETE on use)`. This is now incorrect — the code at `auth.py:335` stores `hash_token(raw_token)`.

**Files affected**:
- `src/api/routes/auth.py:20-21` — docstring says "raw token stored directly" but code stores hashes
- The column name `token` is misleading (it stores `token_hash`), but renaming would require a migration

**Recommended fix**: Update the docstring at `auth.py:20-21` to accurately reflect that the `token` column now stores SHA-256 hashes. A schema rename is optional but would improve clarity.

### 5. `_insert_magic_token` test helpers use f-string SQL for datetime offset (test_auth_routes.py:133, 176)

The test helper `_insert_magic_token` at line 133 and `_insert_magic_token_with_age` at line 176 use f-string interpolation for the datetime offset:
```python
f"VALUES (?, ?, datetime('now', '{expires_offset}'))"
f"VALUES (?, ?, datetime('now', '{remaining_seconds} seconds'))"
```

These are test-only helpers with hardcoded values (not user input), so this is not a real SQL injection vector. However, it violates the project convention against f-string SQL and sets a bad pattern. The offset values are controlled (`"-1 hour"`, `"+15 minutes"`, or computed integers), so the risk is nil, but using parameterized queries would be more consistent.

**Severity**: Low (test code only, no user-controlled input).
**Recommended fix**: Compute the absolute datetime in Python and pass it as a parameter.

### 6. `_parse_retry_after` defined before `logger` assignment (client.py:51-75)

The `_parse_retry_after` function is defined at line 51, but `logger = logging.getLogger(__name__)` is at line 75. If `_parse_retry_after` were called at module import time, the `logger.warning()` call at line 67 would raise `NameError`. In practice this can't happen because the function is only called from instance methods, but the ordering is fragile.

**Recommended fix**: Move the `logger` assignment above `_parse_retry_after` (before line 51).

### 7. Pagination host validation uses hostname comparison only — no scheme/port check (client.py:371-373)

The pagination SSRF defense compares `urlparse(next_page_url).hostname` vs `urlparse(self._base_url).hostname`. This checks the host but not the scheme or port. An attacker-controlled `x-next-page` header could redirect to `http://api.team-manager.gc.com:8080/evil` (same hostname, different port/scheme) and the auth headers would be sent.

**Current impact**: Low — the GameChanger API is HTTPS-only and an attacker would need to control the API response headers.
**Recommended fix**: Also compare scheme and port, or compare the full origin (`scheme://host:port`).

### 8. No test for CSRF rejection on `application/x-www-form-urlencoded` with missing field but valid cookie (test_csrf.py)

The test `test_post_without_csrf_form_field_returns_403` sends `data={"user": "test"}` (no CSRF field) with a CSRF cookie. This correctly tests the missing-field case. However, there's no test verifying that a multipart/form-data POST (file upload scenario) is also validated. The middleware parses `parse_qs` which only handles URL-encoded forms. A `multipart/form-data` POST would fail to extract the CSRF token and correctly reject with 403 — but this deserves an explicit test.

### 9. Missing negative `Retry-After` value test (test_client.py)

Tests cover `"0"` (clamps to 1), valid integers, HTTP-dates, and empty strings. There is no test for a negative value like `"-5"`. The `max(1, int(value))` at `client.py:65` would correctly clamp it to 1, but an explicit test would document this behavior.

## Minor Issues

### 10. Inline `import json` inside route handlers (auth.py:582, 733, 821)

Three route handlers contain `import json as _json` or `import json` inline:
- `auth.py:582` in `get_passkey_register`
- `auth.py:733` in `get_passkey_login_options`
- `auth.py:821` in `post_passkey_login_verify`

These should be top-level imports per Python convention.

### 11. Inline `import base64 as _base64` in route handler (auth.py:820)

`base64` is already imported at the top of the file (line 7). The inline `import base64 as _base64` at line 820 is redundant.

### 12. CSRF middleware `scope.setdefault("state", {})` may conflict with Starlette's state management (csrf.py:131)

The middleware directly sets `scope["state"]["csrf_token"]` at line 132. Starlette's `Request.state` normally wraps `scope["state"]` in a `State` object. Setting it directly on the dict works because `request.state.csrf_token` resolves through `State.__getattr__` → `scope["state"].__getitem__`. This is functional but relies on Starlette internals.

### 13. Logout form markup repeated across 8+ templates

Every admin/dashboard template includes the same inline logout form:
```html
<form method="post" action="/auth/logout" class="inline">
  <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
  <button type="submit" ...>Logout</button>
</form>
```
This is duplicated across `users.html`, `teams.html`, `edit_team.html`, `confirm_team.html`, `opponents.html`, `opponent_connect.html`, `edit_user.html`, `team_stats.html`, and likely others. A Jinja2 macro or `{% include %}` partial would reduce duplication and ensure all instances stay in sync.

### 14. `test_csrf.py` has `sys.path` manipulation (test_csrf.py:28-29)

Lines 28-29 use `sys.path.insert(0, str(_PROJECT_ROOT))`. Test files in this project typically use this pattern, but the project convention discourages `sys.path` manipulation (though it's only strictly prohibited in `src/` modules per `python-style.md`).

## Observations

### Things done well

1. **CSRF middleware is pure ASGI** — avoids the known `BaseHTTPMiddleware` body-stream consumption bug. The body caching via `cached_receive()` (csrf.py:108-115) is clean and correct.

2. **Timing-safe comparison** — `secrets.compare_digest()` at csrf.py:117 prevents timing attacks on CSRF token comparison.

3. **Magic link token hashing** — `hash_token(raw_token)` is applied consistently at all entry/exit points: INSERT (auth.py:335), SELECT for verification (auth.py:386), DELETE for cleanup (auth.py:421, 431), and the test helpers use `hash_token()` too. The session token hashing pattern is also consistent.

4. **Pagination SSRF defense** — The host validation at client.py:371-380 with clear logging and graceful degradation (stops pagination rather than crashing) is well implemented.

5. **`_parse_retry_after` error handling** — Graceful fallback to a default value with warning log instead of crashing on malformed headers. Test coverage includes edge cases (zero, HTTP-date, empty string).

6. **XSS fix for passkey register** — `{{ options_json | tojson }}` in `passkey_register.html:32` correctly replaces what was presumably `| safe`. The server-side change at auth.py:583-587 passes a dict (not a JSON string), so `| tojson` produces valid, escaped JSON. The `<script type="application/json">` block prevents HTML parsing context issues.

7. **Comprehensive CSRF test coverage** — `test_csrf.py` covers rejection (no cookie, no field, wrong token, JSON without header), acceptance (form field match, header match), exemptions (health), cookie delivery, and logout POST enforcement. The admin and passkey endpoints are tested too.

8. **SQL injection fix** — The `update_run_load_status` method at scouting.py:287-298 now uses parameterized CASE expression (`CASE WHEN ? = 'completed'`) instead of string interpolation. Tests verify both `completed` and `failed` status values.

9. **`|safe` completely absent from all templates** — grep confirms zero uses of `|safe` across all Jinja2 templates. Autoescaping is active everywhere.

10. **Middleware ordering** — `CSRFMiddleware` is added before `SessionMiddleware` at main.py:92-93. In Starlette/FastAPI, middleware is processed in reverse-add order (last added runs first). So `CSRFMiddleware` runs first (outermost), which is correct — CSRF validation happens before session resolution, preventing any session state mutation from a CSRF-invalid request.

## Summary

The security implementation across E-125-01, E-125-02, and E-125-05 is **solid**. The CSRF middleware is well-architected (pure ASGI, timing-safe, correct body caching), magic link token hashing is consistently applied, the SQL injection is genuinely fixed with parameterized queries, and the HTTP client hardening (Retry-After parsing, pagination host validation, XSS fix) addresses real attack vectors with appropriate defense-in-depth.

**Critical issues**: None that are exploitable today. The POST-only CSRF check (#1) is a defense-in-depth gap but has zero current attack surface.

**Most important improvements**: Update the misleading docstring (#4), move the logger above `_parse_retry_after` (#6), and consider CSRF token rotation after authentication (#3) for best-practice alignment.

The test coverage is thorough across all three stories, with security-specific tests for CSRF bypass attempts, token hashing verification, Retry-After parsing edge cases, and SSRF pagination defense.
