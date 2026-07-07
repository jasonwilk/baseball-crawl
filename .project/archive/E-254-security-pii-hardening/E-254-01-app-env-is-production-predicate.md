# E-254-01: Canonical `is_production()` APP_ENV fail-safe predicate

## Epic
[E-254: Security & PII Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, every security-sensitive `APP_ENV` gate in the app reads ONE canonical `is_production()` predicate instead of its own inline, case-sensitive `os.environ.get("APP_ENV", ...)` check. Casing and whitespace variants of `production` correctly select the production posture, and a non-empty but unrecognized value (a typo like `prod`) is caught loudly at startup (CRITICAL log + refuse-to-start) instead of silently selecting the insecure posture at runtime.

## Context
Three files independently read `APP_ENV` to decide security postures, and they do it inconsistently: `src/api/routes/auth.py::_is_dev_mode` (session cookie `Secure` flag), `src/api/auth.py::SessionMiddleware.__init__` (the DEV_USER_EMAIL dev-bypass production guard, which lowercases), and `src/api/csrf.py` (CSRF cookie `Secure` flag, which does NOT lowercase). A mistyped or differently-cased `APP_ENV` (`Production`, `prod`, `" production "`) can leave cookies non-`Secure` in production — the exact fail-open the audit flagged (LOW, `auth.py:93`). This story establishes the single predicate and routes its own three cookie-`Secure`/dev-bypass consumers through it; E-254-02 adds the fourth consumer (its email-fallback guard). E-254-03 does NOT consume the predicate (it touches no APP_ENV gate) — it only follows 01→02→03 in the serial chain because it shares `src/api/routes/auth.py`. See Technical Notes TN-1, TN-2.

## Acceptance Criteria
- [ ] **AC-1**: A canonical `is_production()` predicate exists in `src/api/helpers.py` and strict-normalizes per TN-2 — given `APP_ENV` set to `production`, `Production`, `PRODUCTION`, or `" production "`, when `is_production()` is called, then it returns True for all four; given `APP_ENV` unset/empty, it returns False.
- [ ] **AC-2**: Given a non-empty `APP_ENV` that normalizes to a value OUTSIDE the recognized set `{production, development, dev, test, staging}` (a typo like `prod`/`prd`), when the app starts, then it emits a CRITICAL-level log and refuses to start (raises) — per TN-2, catching the typo loudly at boot rather than silently downgrading the cookie `Secure` flag at runtime. Given `APP_ENV` unset OR set-but-empty (`""`), startup proceeds normally (treated as unset → dev posture, NOT unrecognized).
- [ ] **AC-3**: Given the session cookie is set on a login/verify path with `APP_ENV=production` (any casing/whitespace variant from AC-1), when the response is produced through the full middleware stack (TN-6), then the `session` cookie carries `Secure`; given `APP_ENV` unset, the `session` cookie does not carry `Secure`.
- [ ] **AC-4**: Given `APP_ENV=production` (any variant from AC-1), when a response passes through `CSRFMiddleware`, then the `csrf_token` cookie carries `Secure`; given `APP_ENV` unset, it does not.
- [ ] **AC-5**: `src/api/routes/auth.py::_is_dev_mode`, `src/api/auth.py::SessionMiddleware.__init__`, and `src/api/csrf.py` all read the single `is_production()` predicate; no security-gate inline `os.environ.get("APP_ENV", ...)` read remains in those three sites.
- [ ] **AC-6**: The DEV_USER_EMAIL dev-bypass production guard (`SessionMiddleware.__init__`) refuses to start (raises) when `APP_ENV` is a casing/whitespace variant of `production` per AC-1, closing the gap where a non-lowercased variant previously bypassed the guard.
- [ ] **AC-7**: No regressions — discovered importing test files for `helpers.py`, `auth.py`, and `csrf.py` pass (TN-6).

## Technical Approach
Establish the predicate in `src/api/helpers.py` (alongside `get_app_url()`), then route the three existing security-gate reads through it. The strict-normalize semantics and the recognized-token set are FIXED per TN-2 (`{production, development, dev, test, staging}`) — not discretionary, because the refuse-to-start guard depends on the set (AC-2). Only the raise/log mechanism of the startup guard is the implementer's call. Do not change the local-dev default (unset → non-production → non-`Secure` cookies over HTTP is required for local dev). This is a security-gate consolidation — verify each replaced read preserves its site's intended posture.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-254-02

## Files to Create or Modify
- `src/api/helpers.py` (add `is_production()`)
- `src/api/routes/auth.py` (`_is_dev_mode` reads the predicate)
- `src/api/auth.py` (`SessionMiddleware.__init__` reads the predicate)
- `src/api/csrf.py` (cookie `Secure` reads the predicate)
- `tests/test_helpers.py` (`is_production()` / `get_app_env()` unit tests — same module as `get_app_url`; 01-exclusive)
- `tests/test_auth.py` (SessionMiddleware dev-bypass AC-6 + refuse-to-start AC-2; 01-exclusive)
- `tests/test_auth_routes.py` (session-cookie `Secure` behavioral AC-3 — shared with 02/03 on the serial chain, per TN-6)
- `tests/test_csrf.py` (CSRF cookie-`Secure` AC-4; 01-exclusive)
- Broader discovered importing suites: run-only per TN-6

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-254-02**: the `is_production()` predicate that E-254-02's email stdout-fallback guard consumes (TN-4).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Placement in `src/api/helpers.py` is architecture-adjacent but not a context-layer file, so this remains a software-engineer story.

**Deploy landing check** (SE Finding 4b): the refuse-to-start guard raises at app construction, so an out-of-set `APP_ENV` in ANY runtime environment (devcontainer, CI, production) would break startup / the whole test suite. Before landing, confirm every deploy env exports a recognized `APP_ENV` or leaves it unset. Verified at planning time: `.env`/`.env.example` use `APP_ENV=development` and production uses `APP_ENV=production` (both in-set); no compose/devcontainer/CI file exports a stray value — so the guard is safe for the current repo.
