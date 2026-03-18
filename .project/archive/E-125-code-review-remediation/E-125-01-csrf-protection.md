# E-125-01: CSRF Protection for All POST Endpoints

## Epic
[E-125: Full-Project Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, every state-mutating endpoint in the FastAPI application will validate a CSRF token. All HTML forms will include a hidden CSRF token field, JS-initiated POSTs will include the CSRF token via header or compatible transport, the mutating GET `/auth/logout` will be converted to POST, and a server-side middleware will reject POST requests with missing or invalid tokens. This closes the most significant security gap identified in the web application review.

## Context
Review 03 finding #1 (Critical): The application has zero CSRF protection. Every POST form -- user creation, user deletion, team creation, opponent linking, login -- is vulnerable to cross-site request forgery. `SameSite=lax` on cookies provides partial mitigation but does NOT protect against POST-based attacks from cross-origin forms. The user explicitly directed: "Do not take Cloudflare as the mitigation for missing CSRF."

## Acceptance Criteria
- [ ] **AC-1**: Every HTML `<form method="POST">` in the application includes a hidden CSRF token field
- [ ] **AC-2**: A server-side middleware or dependency validates the CSRF token on every POST request and returns 403 for missing or invalid tokens
- [ ] **AC-3**: GET requests to form pages generate and deliver the CSRF token (via template context, cookie, or both)
- [ ] **AC-4**: The health endpoint (`/health`) is excluded from CSRF validation (no form, no cookie)
- [ ] **AC-5**: Tests verify that POST requests without a valid CSRF token receive 403
- [ ] **AC-6**: Tests verify that POST requests with a valid CSRF token succeed (existing form flows still work)
- [ ] **AC-7**: `GET /auth/logout` is converted to `POST /auth/logout` with CSRF validation; all templates/links that trigger logout submit a form instead of following a link
- [ ] **AC-8**: JS-initiated POST requests (`/auth/passkey/register` from `passkey_register.html`, `/auth/passkey/login/verify` from `login.html`) include the CSRF token via request header or other transport mechanism compatible with the chosen CSRF solution
- [ ] **AC-9**: All existing tests pass (update test fixtures as needed to include CSRF tokens)

## Technical Approach
Per Technical Notes TN-1: FastAPI has no built-in CSRF. The implementing agent should evaluate lightweight options (library or custom middleware) and choose the simplest approach. All POST routes in `src/api/routes/admin.py` and `src/api/routes/auth.py` need coverage. Templates in `src/api/templates/` that contain `<form>` tags need the hidden field. The auth middleware exclusion list (health, static, login page) may need adjustment.

**Mutating GETs**: `/auth/logout` (line 459 in `auth.py`) is a `GET` that deletes the session -- convert to `POST` with CSRF. Update all templates that link to logout (likely `base.html` or similar nav template) to use a form submission. `/auth/verify` is excluded from CSRF: the magic link token in the query string IS the authorization (single-use, time-limited) -- an attacker would need the token itself, making CSRF inapplicable.

**JS CSRF transport**: `passkey_register.html` (line 101) and the passkey login flow both use `fetch()` for POST requests with JSON bodies. The CSRF solution must support token transport for JS-initiated requests (e.g., double-submit cookie pattern where JS reads a non-httponly CSRF cookie and sends it as a header, or a meta tag pattern).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-125-02, E-125-05 (CSRF changes affect shared `tests/test_auth_routes.py` fixtures -- see TN-8)

## Files to Create or Modify
- `src/api/main.py` (middleware registration)
- `src/api/routes/admin.py` (template context for CSRF token)
- `src/api/routes/auth.py` (template context for CSRF token; convert logout GET→POST)
- `src/api/templates/admin/*.html` (hidden CSRF field in forms)
- `src/api/templates/auth/*.html` (hidden CSRF field in forms; JS CSRF transport in passkey templates)
- `src/api/templates/base.html` or nav template (logout link → form)
- `tests/test_auth_routes.py` (CSRF token in test requests)
- `tests/test_admin.py` or new test file (CSRF rejection tests)
- `requirements/app.in` and `requirements/app.txt` (if a CSRF library is added)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Review 03 observation: session security is otherwise solid (SHA-256 hashed tokens, httponly, SameSite=lax, secure in prod). CSRF is the one gap.
- The `SameSite=lax` cookie is already set (`src/api/routes/auth.py:141`), which helps but is not sufficient alone.
- **`/auth/verify` exclusion rationale**: This is a magic link callback -- the token in the URL is the authorization. CSRF requires an attacker to trick a user into making an unwitting request, but here the attacker would need the one-time token. Standard practice for email magic links.
- **Sequencing note (TN-8)**: This story should merge first among E-125-01/02/05, as CSRF changes affect all auth test fixtures. See epic TN-8.
