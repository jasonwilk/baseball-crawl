# E-075-02: Add gc-client-id and Response Body Capture to Proxy Addon

## Epic
[E-075: Mobile Profile Credential Capture and Validation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the proxy credential extractor addon will capture two additional credential sources: the `gc-client-id` request header (written to `GAMECHANGER_CLIENT_ID_*` env vars) and the refresh token from POST /auth response bodies (written to `GAMECHANGER_REFRESH_TOKEN_*` env vars, overriding any stale request-header value). This enables automatic mobile credential capture during proxy sessions.

## Context
The addon currently captures credentials only from request headers: `gc-token`, `gc-device-id`, and `gc-app-name`. Two gaps block mobile credential capture:

1. **`gc-client-id` is not captured.** This header is sent on every authenticated request (web and mobile) but is not in the addon's `_BASE_CREDENTIAL_HEADERS` mapping.
2. **Response bodies are not parsed.** The refresh token for mobile is returned in the POST /auth response body (`refresh.data` field), not echoed back in request headers. The addon only has a `request()` handler -- no `response()` handler.

After E-075-01 aligns env var names, this story adds both capture paths.

## Acceptance Criteria
- [ ] **AC-1**: The `gc-client-id` request header is captured and written to `GAMECHANGER_CLIENT_ID_{WEB|MOBILE}` in `.env`, with the same profile-detection and deduplication logic as existing headers.
- [ ] **AC-2**: A `response()` handler is added to `CredentialExtractor`. It parses the JSON body of POST /auth responses that return HTTP 200 and contain a `refresh.data` field. The refresh token value is written to `GAMECHANGER_REFRESH_TOKEN_{WEB|MOBILE}`.
- [ ] **AC-3**: The `response()` handler only fires for POST requests to the `/auth` path on GameChanger domains. Other responses are ignored (no JSON parsing overhead).
- [ ] **AC-4**: The `response()` handler uses the same profile-detection logic (User-Agent from the request) as the `request()` handler. Mobile traffic writes `_MOBILE` suffix, web traffic writes `_WEB` suffix.
- [ ] **AC-5**: Response body parsing errors (non-JSON, missing fields) are logged as WARNING and do not crash the addon.
- [ ] **AC-6**: The response-captured refresh token takes precedence over the request-header gc-token for the `GAMECHANGER_REFRESH_TOKEN_*` key. If both are present in a single flow, the response body value wins (it is the newly issued token).
- [ ] **AC-7**: Tests cover: gc-client-id capture from request, refresh token extraction from response body, profile routing for both capture paths, error handling for malformed responses, deduplication (no write when value unchanged).
- [ ] **AC-8**: Credential values are never logged -- only env key names appear in log messages.

## Technical Approach
The `CredentialExtractor` class needs a new `response()` method (mitmproxy calls this automatically for addons with the method defined). The method should check: (a) is this a GC domain, (b) is this POST /auth, (c) is the response 200 OK, (d) does the JSON body contain `refresh.data`. If all checks pass, extract the refresh token and write it using the existing `merge_env_file` function.

For `gc-client-id`, add it to `_BASE_CREDENTIAL_HEADERS` with the base name `GAMECHANGER_CLIENT_ID`. This follows the existing pattern -- no structural changes needed for request-header capture.

Key constraint: the addon runs inside the mitmproxy Docker container on the Mac host. Changes take effect when the user restarts the proxy (`cd proxy && ./stop.sh && ./start.sh`).

Reference files:
- `/workspaces/baseball-crawl/proxy/addons/credential_extractor.py` (current addon)
- `/workspaces/baseball-crawl/proxy/addons/gc_filter.py` (domain detection, source detection)
- `/workspaces/baseball-crawl/docs/api/auth.md` (POST /auth response shape: `{"type":"token","access":{"data":"..."},"refresh":{"data":"..."}}`)
- `/workspaces/baseball-crawl/epics/E-075-mobile-credential-capture/R-01-findings.md` (research findings -- read before implementing)

## Dependencies
- **Blocked by**: E-075-R-01 (findings may change what we capture), E-075-01 (env var names must be aligned first)
- **Blocks**: None

## Files to Create or Modify
- `proxy/addons/credential_extractor.py` -- add gc-client-id to header map, add response() handler
- `tests/test_credential_extractor.py` -- new tests for gc-client-id and response body capture

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The mitmproxy `response()` hook receives the same `flow` object as `request()`, with `flow.response` populated. The response body is accessed via `flow.response.content` (bytes) or `flow.response.text` (str).
- The deduplication cache (`self._cache`) should cover response-sourced credentials too. Use the same suffixed env key as the cache key.
- **R-01 outcome (2026-03-08):** Mobile client key is confirmed different from web (web key tested, 401). This story's scope is unchanged -- gc-client-id capture and response body parsing are both still valuable. The captured mobile client ID (`0f18f027-c51e-4122-a330-9d537beb83e0`) confirms this header is present in mobile traffic. Response body capture enables automatic refresh token extraction for future proxy sessions.
