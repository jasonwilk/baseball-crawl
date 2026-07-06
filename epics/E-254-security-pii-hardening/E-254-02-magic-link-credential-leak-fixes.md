# E-254-02: Magic-link credential-leak fixes (GET-verify split + email log guard)

## Epic
[E-254: Security & PII Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, magic-link credentials no longer leak through two paths: (1) magic-link verification is a side-effect-free GET that renders an interstitial, with the single-use token consume and session creation moved to a CSRF-protected POST — so mail-provider link scanners can no longer burn the token or receive a live session; and (2) the email stdout fallback no longer logs the live magic-link URL in production.

## Context
Two findings share the magic-link credential-leak theme:
- **Magic-link GET-verify** (medium, `src/api/routes/auth.py::verify_token`, 324-423): a bare GET `/auth/verify` consumes the token and issues a 7-day session. Email security scanners follow links, burning the token (operator lockout) and potentially receiving a live session; the raw token lands in access logs.
- **Email stdout fallback** (medium, `src/api/email.py::send_email`, ~52-55): when `MAILGUN_API_KEY` is unset, the full message body — including the live 15-minute magic-link URL — is logged at INFO and the call returns a fake success (True).

The app already has a working double-submit CSRF middleware (`src/api/csrf.py`) that protects all POSTs, so the GET/POST split needs no new CSRF infrastructure. The email guard consumes the `is_production()` predicate from E-254-01. See Technical Notes TN-3, TN-4; the log-residual is explicitly out of scope (IDEA-093).

## Acceptance Criteria
- [ ] **AC-1**: Given a valid, unexpired magic-link token, when GET `/auth/verify?token=…` is requested, then the token row still exists afterward (not consumed), no session cookie is set, and an interstitial page is rendered containing a form that carries the token and the CSRF token (per TN-3).
- [ ] **AC-2**: Given a missing/invalid/expired token, when GET `/auth/verify` is requested, then the existing verify-error page is rendered (no interstitial, no session) — matching the prior error behavior. The GET path performs NO database writes for ANY token state, including NO deletion of an expired-token row (the side-effect-free GET rule, per TN-3) — expired-row cleanup is not a GET responsibility.
- [ ] **AC-3**: Given the interstitial form's token and a valid CSRF token, when POST `/auth/verify` is submitted through the full middleware stack (TN-6), then the token is atomically consumed (single-use, DELETE-gated), a session is created and the cookie set, and the response redirects to `/admin/reports` (has passkeys) or `/auth/passkey/prompt` (no passkeys) — preserving the prior redirect logic.
- [ ] **AC-4**: Given a token already consumed by a prior POST, when POST `/auth/verify` is submitted again with the same token, then it is rejected (already-consumed path, no new session) — the existing rowcount==0 race rejection is preserved.
- [ ] **AC-5**: Given POST `/auth/verify` is submitted WITHOUT a valid CSRF token, when it passes through `CSRFMiddleware`, then it is rejected with 403 before any consume/session occurs.
- [ ] **AC-6**: Given `MAILGUN_API_KEY` is unset and `is_production()` is False, when `send_email` is called, then the message (including the URL) is logged and the call returns True (local-dev behavior preserved, per TN-4).
- [ ] **AC-7**: Given `MAILGUN_API_KEY` is unset and `is_production()` is True, when `send_email` is called, then the message body (and thus any magic-link URL) is NOT logged, an ERROR indicating misconfiguration (no secret material) is emitted, and the call returns False (per TN-4).
- [ ] **AC-8**: No regressions — discovered importing test files for `routes/auth.py` and `email.py` pass (TN-6).

## Technical Approach
Split `verify_token` into a side-effect-free GET (validate existence/expiry, render interstitial or error) and a new POST handler that performs the existing atomic consume + session creation + redirect. Add a new interstitial template under `src/api/templates/auth/`; embed the token and `request.state.csrf_token` as hidden form fields per TN-3. Guard the `send_email` stdout fallback with `is_production()` per TN-4. Do not attempt to remove the token from the GET URL (IDEA-093). See TN-3, TN-4.

## Dependencies
- **Blocked by**: E-254-01 (consumes `is_production()`)
- **Blocks**: E-254-03

## Files to Create or Modify
- `src/api/routes/auth.py` (`verify_token` GET split + new POST `/auth/verify`)
- `src/api/templates/auth/` (new interstitial template)
- `src/api/email.py` (`send_email` production fallback guard)
- `tests/test_auth_routes.py` (verify GET/POST behavioral tests through the middleware stack — shared with 01/03 on the serial chain, per TN-6)
- `tests/test_email.py` (email production-guard AC-6/AC-7; 02-exclusive)
- Broader discovered importing suites: run-only per TN-6

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The GET/POST verify split closes the scanner-prefetch threat (the finding). The residual raw-token-in-access-logs exposure is tracked as IDEA-093 and is out of scope here (TN-3).
