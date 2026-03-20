# E-128-08: Proxy Session PII Redaction

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`DONE`

## Description
After this story is complete, the mitmproxy addon will redact email and password values from POST /auth request bodies before writing them to proxy session logs. The `type` field (which identifies the auth step) is preserved. This is defense-in-depth -- session data is gitignored but exists on disk and was observed to contain plaintext credentials.

## Context
Api-scout's proxy data analysis (2026-03-18) found plaintext email and password in POST /auth request bodies in session logs (`proxy/data/sessions/*/endpoint-log.jsonl`). The user's credentials were exposed in login flow captures. While session data is gitignored, defense-in-depth requires redacting sensitive fields at capture time.

## Acceptance Criteria
- [ ] **AC-1**: Given the mitmproxy addon captures a POST /auth request with a user-auth body containing the operator's email, when the request is logged to `endpoint-log.jsonl`, then the email field value is replaced with `"[REDACTED]"` and the `type` field is preserved.
- [ ] **AC-2**: Given the addon captures a POST /auth request with `{"type": "password", "password": "secret"}`, when the request is logged, then the `password` field value is replaced with `"[REDACTED]"` and the `type` field is preserved.
- [ ] **AC-3**: Given the addon captures a non-auth request (e.g., GET /me/teams), when the request is logged, then no redaction is applied (non-auth requests are unchanged).
- [ ] **AC-4**: Given the addon captures a POST /auth request with `{"type": "refresh"}`, when the request is logged, then no redaction is applied (refresh requests contain no PII).
- [ ] **AC-5**: Tests cover: user-auth redaction, password redaction, refresh pass-through, non-auth pass-through.

## Technical Approach
The redaction is applied in `proxy/addons/endpoint_logger.py` per Technical Notes TN-7. The addon does NOT currently parse auth request types -- it captures all request bodies as raw strings via `_extract_body()`. The SE must add auth-path detection: if the request path ends with `/auth` and method is `POST`, parse the request body JSON and replace `email`/`password` field values with `"[REDACTED]"` before the body is serialized to the log. The redaction point is in `_build_capture_fields()` -- apply it to the request body after `_extract_body()` returns.

Key files to study: `proxy/addons/endpoint_logger.py` (the addon that writes `endpoint-log.jsonl`), `proxy/addons/credential_extractor.py` (separate addon that parses auth responses -- different scope), `proxy/data/sessions/` (example session data to understand the log format).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `proxy/addons/endpoint_logger.py` -- add PII redaction for POST /auth request bodies
- `tests/test_proxy/test_endpoint_logger.py` -- redaction unit tests (existing test suite with ~50 tests)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing proxy addon behavior

## Notes
- The mitmproxy addon runs on the Mac host, not in the devcontainer. Agents can read and modify the addon code but cannot start/stop mitmproxy (per proxy boundary rule).
- Existing session data in `proxy/data/sessions/` is NOT retroactively redacted. This story only affects future captures.
