# E-075-R-01: Mobile Auth Flow Reconnaissance

## Epic
[E-075: Mobile Profile Credential Capture and Validation](epic.md)

## Status
`DONE`

## Objective
Determine whether mobile programmatic token refresh is feasible with credentials we can capture, and document the mobile auth flow differences from web.

## Time Box
One focused session. The user will run the proxy capture on the Mac host; this spike analyzes the captured data.

## Research Questions
1. **Is the mobile client key the same as the web client key?** Decode a mobile `gc-token` JWT to extract the `cid` field. If the mobile `cid` matches the web `GAMECHANGER_CLIENT_ID_WEB`, the keys are likely shared. If they differ, the mobile app has its own client credentials embedded in the iOS binary.
2. **Can we capture `gc-client-id` from mobile request headers?** Examine proxy session data for mobile traffic and confirm whether `gc-client-id` appears in request headers (it should -- the web client sends it on every POST /auth).
3. **Does the mobile login/refresh flow match web?** Compare mobile POST /auth requests against the documented 4-step login flow and refresh flow in `/workspaces/baseball-crawl/docs/api/auth.md`. Look for body structure differences, extra headers, or different response shapes.
4. **Can we extract the refresh token from mobile POST /auth response bodies?** The refresh token is returned in the response body (`refresh.data` field), not in headers. Confirm this is true for mobile responses as well by examining proxy capture data.

## Deliverables
- A findings document at `/workspaces/baseball-crawl/epics/E-075-mobile-credential-capture/R-01-findings.md` summarizing answers to all four questions
- A recommendation for whether E-075-02 and E-075-03 should proceed as written, be modified, or be blocked

## Approach

**Prerequisites (user action):** The user must run a mobile proxy session on the Mac host before this spike can execute. The spike needs at least one mobile login or token refresh event captured.

**Analysis steps:**
1. Read proxy session endpoint logs from `proxy/data/sessions/` to find mobile POST /auth requests
2. Read proxy session header capture data to confirm which headers mobile traffic sends (especially `gc-client-id`)
3. Decode any captured `gc-token` JWTs from mobile requests to extract the `cid` field and compare against the known web client ID
4. If response bodies were captured in raw data, examine POST /auth responses for the `refresh.data` field
5. Compare mobile traffic patterns against the web auth flow documented in `/workspaces/baseball-crawl/docs/api/auth.md`

**Note on proxy limitation:** The current addon only has a `request()` handler, so response bodies will NOT be in the endpoint log or credential extractor output. The analysis may need to rely on mitmweb UI captures, raw flow files, or the user manually noting response body contents. If response body data is unavailable from the proxy session, document this as a confirmed gap and note that E-075-02's response handler addition is essential.

## Dependencies
- **Blocked by**: None (but requires a mobile proxy session to have been captured -- user action)
- **Blocks**: E-075-02 (addon upgrade depends on findings), E-075-03 (validation scope depends on whether client key is obtainable)

## Findings
All four research questions answered definitively. Full findings at `/workspaces/baseball-crawl/epics/E-075-mobile-credential-capture/R-01-findings.md`.

Key results:
1. **Q1 (Client key parity)**: CONFIRMED DIFFERENT. Web signing key tested against mobile refresh token -> 401 Unauthorized. Mobile client key is embedded in iOS binary. No JS bundles exist in mobile traffic (iOS app is purely native).
2. **Q2 (gc-client-id capture)**: Confirmed capture gap in addon. Header not in `_BASE_CREDENTIAL_HEADERS`.
3. **Q3 (Auth flow match)**: Response shape CONFIRMED identical to web. Content-type differs (`eden_auth` vs `application/json`).
4. **Q4 (Refresh token from response)**: Confirmed impossible with current addon (no response handler).

**Workaround discovered**: Mobile refresh token (14-day) and access token (~12 hours) work directly as `gc-token` for GET endpoints. Only POST /auth refresh requires the client key.

**Token correction**: `.env` had ACCESS token stored as `GAMECHANGER_REFRESH_TOKEN_MOBILE`. Corrected to actual REFRESH token (kid=b3503b45, 14-day lifetime).

## Recommendation
E-075-02 and E-075-03 should proceed with adjusted expectations:
- **E-075-02**: Addon upgrade still valuable -- captures gc-client-id and response bodies for future sessions. Proceed as written.
- **E-075-03**: Validation script should validate tokens we CAN capture (presence, JWT decode, GET /me/user) and report that programmatic refresh is unavailable without the client key. Proceed as written, with the understanding that AC-4 (client key absent path) is the expected mobile path.
- **Mobile client key extraction**: Out of scope for E-075. IPA binary analysis would be needed (search for `0f18f027` pattern in binary/plist). Captured as future idea consideration.

## Notes
- The web client key is stored in `GAMECHANGER_CLIENT_KEY_WEB` in `.env`. The research agent should compare the `cid` from mobile JWTs against `GAMECHANGER_CLIENT_ID_WEB` (NOT the client key itself -- the key is a secret).
- Mobile device ID is already known: `DC1C1435-EF89-44EE-A2C3-CA89B6A96E9A` (uppercase UUID format, vs web's 32-char hex).
- The `gc-app-name` header for mobile is `iOS` (vs `web` for browser traffic). The iOS app also uses a different User-Agent containing `GameChanger/`, `CFNetwork/`, etc.
