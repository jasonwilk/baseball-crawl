# E-073-03: Auth Flow Programmatic Validation

## Epic
[E-073: API Documentation Validation Sweep](epic.md)

## Status
`TODO`

## Description
After this story is complete, all five POST /auth body types will have been tested programmatically with the cracked gc-signature algorithm, and the actual request/response schemas will be confirmed against what is documented in `docs/api/endpoints/post-auth.md` and `docs/api/auth.md`. Any schema discrepancies will be documented in a validation report.

## Context
The gc-signature HMAC-SHA256 algorithm was fully reverse-engineered on 2026-03-07. Programmatic token refresh (`{type: "refresh"}`) is confirmed working from Python. The remaining four body types (logout, client-auth, user-auth, password) have documented schemas based on browser proxy captures but have NOT been independently tested via direct programmatic curl. This story closes that gap.

The five body types are:
1. `{type: "refresh"}` -- token refresh (confirmed working)
2. `{type: "client-auth", client_id: "..."}` -- anonymous session establishment
3. `{type: "user-auth", email: "..."}` -- user identification within client session
4. `{type: "password", password: "..."}` -- password authentication (requires steps 2+3 first)
5. `{type: "logout"}` -- session invalidation

Steps 2-4 form a chained login flow with gc-signature chaining between steps. Step 5 invalidates a session.

## Acceptance Criteria
- [ ] **AC-1**: Given valid web profile credentials (refresh token, client ID, client key, device ID, email, password), when the validation script runs, then it successfully executes a token refresh (`{type: "refresh"}`) and confirms the response matches the documented schema in `docs/api/endpoints/post-auth.md` (type, access.data, access.expires, refresh.data, refresh.expires).
- [ ] **AC-2**: Given valid client credentials (client ID, client key), when the script executes the full login chain (client-auth -> user-auth -> password), then it confirms: (a) each step returns 200, (b) gc-signature chaining works between steps, (c) the final response contains access and refresh tokens.
- [ ] **AC-3**: Given a valid refresh token, when the script executes logout (`{type: "logout"}`), then it confirms the response status and schema. The script must re-establish credentials afterward (via refresh) so the operator's session is not left invalidated.
- [ ] **AC-4**: Given each POST /auth response, when compared against the documented schema, the report notes: (a) which response fields match docs, (b) any undocumented fields present in the response, (c) any documented fields missing from the response.
- [ ] **AC-5**: The validation script logs ONLY non-sensitive data: response status codes, response field names (NOT values), schema match results. Token values, passwords, email addresses, and client keys are NEVER logged, printed, or written to any output file.
- [ ] **AC-6**: Given the validation run completes, when a validation report is produced, it includes pass/fail per body type and a summary of any schema discrepancies found.
- [ ] **AC-7**: The script has tests covering the signature generation logic and response schema comparison (mocked HTTP -- no live API calls in tests). The gc-signature algorithm implementation can reference `data/raw/gc-signature-algorithm.md` for the spec.

## Technical Approach
Build a validation script that implements the gc-signature HMAC-SHA256 signing algorithm and tests each POST /auth body type. The algorithm spec is at `data/raw/gc-signature-algorithm.md` and the JS reference is at `data/raw/gc-auth-module.js`. The existing `docs/api/auth.md` documents the full flow.

Critical constraints:
- Steps 2-4 (login flow) must be executed in sequence with gc-signature chaining
- Step 2 (client-auth) uses `usePreviousSignature: false`
- Steps 3-4 chain the server's response gc-signature into the next request
- Step 5 (logout) invalidates the session -- must re-establish credentials afterward
- The script should be idempotent: leave the operator's credentials in a valid state when done

Credentials are loaded from `.env` via the standard `dotenv_values` pattern. Required env vars: `GAMECHANGER_REFRESH_TOKEN_WEB`, `GAMECHANGER_CLIENT_ID_WEB`, `GAMECHANGER_CLIENT_KEY_WEB`, `GAMECHANGER_DEVICE_ID_WEB`, `GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-073-05 (documentation corrections use this story's report)

## Files to Create or Modify
- `scripts/validate_auth_flow.py` (new)
- `tests/test_validate_auth_flow.py` (new)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-073-05**: Auth flow validation report listing schema discrepancies (if any) in `docs/api/endpoints/post-auth.md` and `docs/api/auth.md`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The refresh body type is the only one confirmed working programmatically today. The other four are documented from browser captures and should work with the cracked gc-signature algorithm, but this story is the first programmatic test of steps 2-4 and step 5.
- After running logout (step 5), the refresh token used for logout is invalidated. The script MUST refresh credentials after the logout test to leave the operator's `.env` in a working state. This means: after testing logout, execute a fresh login flow (steps 2-4) and update `.env` with the new refresh token.
- The gc-signature algorithm uses raw bytes for nonce and previousSignature in the HMAC message, NOT Base64 strings. This is a critical implementation detail documented in `docs/api/auth.md`.
- PII handling: the email address is sent in the user-auth step body but must NOT appear in logs or validation reports.
