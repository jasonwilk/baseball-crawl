# E-254-03: Auth-route hardening (passkey rowcount, login timing, options cap)

## Epic
[E-254: Security & PII Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, three remaining low-severity auth gaps in `src/api/routes/auth.py` are closed: passkey registration enforces single-use of its challenge via the consume rowcount, the login route no longer reveals whether an email is registered through response timing, and the unauthenticated passkey-options endpoint can no longer be used to flood the challenge table with unbounded rows.

## Context
Three low-severity findings, all in `src/api/routes/auth.py`:
- **Passkey registration rowcount** (`post_passkey_register`, ~591-599): the registration path calls `consume_challenge` but discards its rowcount, unlike the login path (849-860) which gates on `consumed != 1`. This violates the DELETE-is-the-arbiter single-use invariant (`.claude/rules/data-model.md`).
- **Login timing enumeration** (`post_login`, 267-321): a known email triggers token generation + two DB writes + an awaited Mailgun send; an unknown email does nothing, so response time reveals registration — defeating the route's stated enumeration protection.
- **Passkey-options flood** (`get_passkey_login_options`, 685-710): unauthenticated; inserts one `webauthn_challenges` (kind=login) row per call, and `store_challenge` sweeps only expired rows — so within the TTL an attacker creates unbounded rows.

See Technical Notes TN-7 (options cap), TN-8 (timing), and TN-6 (test discipline). This story is sequenced after E-254-02 because both modify `src/api/routes/auth.py`.

## Acceptance Criteria
- [ ] **AC-1**: Given a passkey registration challenge that has already been consumed, when POST `/auth/passkey/register` is submitted again for the same challenge, then it is rejected with 400 and no second credential is stored — the registration path gates on the `consume_challenge` rowcount (`consumed != 1`), matching the login path.
- [ ] **AC-2**: Given a normal first-time registration with a live challenge, when POST `/auth/passkey/register` succeeds, then the credential is stored exactly once (the rowcount gate does not break the happy path).
- [ ] **AC-3**: Given POST `/auth/login` for a KNOWN, NON-rate-limited email (fresh / no unexpired recent token — so `post_login` takes the issuance path, not the rate-limit-suppression branch) and for an UNKNOWN email, when each is submitted through the full middleware stack (TN-6), then both return the byte-identical confirmation page (200) and the Mailgun send is scheduled as a `BackgroundTask` (not awaited inline). Crucially — to close the residual DB-write asymmetry (the known branch does a rate-limit SELECT + DELETE + INSERT + commit the unknown branch would otherwise skip) — a SPECIFIC equalizing operation (e.g. `hash_token` or a dummy user-scoped SELECT) is invoked an EQUAL number of times on both branches, asserted via mock call-count parity, so a do-nothing-unknown implementation FAILS. NO wall-clock assertions (TN-6, TN-8).
- [ ] **AC-4**: Given fewer than the cap (TN-7) of live `KIND_LOGIN` challenge rows, when GET `/auth/passkey/login/options` is called, then exactly one new challenge row is stored and options are returned as before.
- [ ] **AC-5**: Given the number of live `KIND_LOGIN` challenge rows is at/over the cap (TN-7), when GET `/auth/passkey/login/options` is called again, then the endpoint returns 429 and does NOT insert a new challenge row (the live login count does not grow past the cap). The cap is scoped to `kind='login'` only; registration challenges are unaffected. The cap is a module-level constant the test monkeypatches to a small N (TN-7) — the test does NOT seed 100 live rows.
- [ ] **AC-6**: Given expired `KIND_LOGIN` challenge rows exist, when a new options call arrives, then expired rows are still swept (existing sweep-on-write behavior preserved) so legitimate use is not blocked by stale rows counting toward the cap.
- [ ] **AC-7**: No regressions — discovered importing test files for `routes/auth.py` and `passkey_challenges.py` pass (TN-6).

## Technical Approach
Gate `post_passkey_register` on the `consume_challenge` return value (the login path is the reference). For login timing, move the Mailgun send to a `BackgroundTask` so both branches return before network I/O and add symmetric cheap work on the unknown branch (TN-8). For the options flood, enforce the live-`KIND_LOGIN`-row cap from TN-7 (a count-live-challenges helper may belong in `src/api/passkey_challenges.py`). See TN-6, TN-7, TN-8.

## Dependencies
- **Blocked by**: E-254-02 (same file, serial ordering)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/auth.py` (`post_passkey_register` rowcount gate; `post_login` timing; `get_passkey_login_options` cap)
- `src/api/passkey_challenges.py` (optional live-challenge count helper for the cap)
- `tests/test_passkey.py` (passkey-register rowcount AC-1/2 + options-cap AC-4/5/6 — the established dedicated passkey home; 03-exclusive)
- `tests/test_auth_routes.py` (login-timing AC-3 — shared with 01/02 on the serial chain, per TN-6)
- Broader discovered importing suites: run-only per TN-6

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The cap value (100) and TTL (unchanged, 5 min) are in TN-7. Timing ACs must never assert wall-clock durations (TN-6).

**Accepted residual (login-timing, LOW)**: the AC-3 call-parity equalizes the FRESH-known vs UNKNOWN paths (the single-probe enumeration vector the finding targets). A THIRD path — the rate-limit-suppression branch — does LESS work than both, so REPEATED probes of a REGISTERED email show a timing DROP on the 2nd probe while an UNREGISTERED email stays flat (a repeated-probe differential). Chasing constant-time across all three paths is over-scoping for a LOW finding on a single-operator app; this residual is ACCEPTED-AND-NOTED (same disposition class as IDEA-093). Optional zero-residual hardening (not required): run the same dummy equalizing work in the rate-limited branch too. Captured as IDEA-095.
