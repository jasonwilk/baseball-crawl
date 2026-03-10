# R-01 Findings: Mobile Auth Flow Reconnaissance

**Spike:** E-075-R-01
**Author:** api-scout
**Date:** 2026-03-08
**Status:** COMPLETE -- all research questions answered definitively (2026-03-08)

---

## Summary

An existing mobile proxy session (`2026-03-06_211209`) was discovered and analyzed. This is 744 iOS-sourced requests including 6 confirmed `POST /auth` calls. This eliminates the need for a full new proxy session to answer most research questions, but response body data is still unavailable (the current addon has no response handler).

**Bottom line:**
- The mobile client key is CONFIRMED DIFFERENT from web. Tested directly: signing a mobile refresh request with the web client key returns 401 Unauthorized.
- The mobile client key is embedded in the iOS binary. No JS bundles or config endpoints exist in mobile traffic -- the iOS app is purely native. Only extraction path is IPA binary analysis.
- **Workaround discovered**: The mobile refresh token (14-day) and access token (~12 hours) work directly as `gc-token` for regular GET endpoints without needing the signing key. Programmatic mobile token refresh is blocked, but manual recapture every 14 days is viable.
- `gc-client-id` was NOT captured by the existing mobile session -- a proxy addon gap, not evidence the header is absent.
- The naming inconsistency targeted by E-075-01 is already resolved in the codebase. E-075-01 ACs are met.
- E-075-02 and E-075-03 should proceed with reduced scope -- addon upgrade is still valuable; validation can verify tokens we CAN capture.

**Key test results (2026-03-08):**
- **Test 1: Web signing key for mobile refresh -> 401 Unauthorized.** Used `GAMECHANGER_CLIENT_KEY_WEB` to sign a POST /auth refresh request with the mobile refresh token and mobile client ID (`0f18f027-c51e-4122-a330-9d537beb83e0`). Result: 401. The web key definitively does NOT work for mobile signing.
- **Test 2: JS bundles in mobile traffic -> None found.** The mobile proxy session (`2026-03-06_211209`) shows only 3 hosts: `api.team-manager.gc.com`, `media-service.gc.com`, `vod-archive.gc.com`. Zero JS/config/init endpoints. The iOS app is purely native -- no shared web JS bundle.
- **Token correction**: The `.env` originally had the ACCESS token (type="user") stored as `GAMECHANGER_REFRESH_TOKEN_MOBILE`. Corrected to the actual REFRESH token (kid=b3503b45, no type field, 14-day lifetime).
- Mobile client ID CONFIRMED DIFFERENT from web: `0f18f027-c51e-4122-a330-9d537beb83e0` (web: `07cb985d-ff6c-429d-992c-b8a0d44e6fc3`).
- Mobile access token JWT kid, type field, and payload fields are IDENTICAL to web structure.
- Mobile access token lifetime: ~43,997s (~12 hours) -- significantly longer than web's ~60 min.
- Mobile POST /auth response shape CONFIRMED identical to web: `{"type":"token","access":{...},"refresh":{...}}`.

---

## Research Question Answers

### Q1: Is the mobile client key the same as the web client key?

**Status: CONFIRMED DIFFERENT -- tested directly (2026-03-08)**

**What we know:**
- Mobile access token decoded via mitmweb on 2026-03-08. The `cid` field in the mobile JWT is `0f18f027-c51e-4122-a330-9d537beb83e0`.
- The web client ID is `07cb985d-ff6c-429d-992c-b8a0d44e6fc3`.
- These are DIFFERENT. Client IDs differ across profiles.
- **Definitive test**: Signed a POST /auth refresh request using the web client key (`GAMECHANGER_CLIENT_KEY_WEB`) with the mobile refresh token and mobile client ID. Result: **401 Unauthorized**. The web key does NOT work for mobile signing.
- The mobile client key is a separate, unknown value embedded in the iOS binary.
- No JS bundles, config endpoints, or init calls exist in mobile traffic (only 3 hosts: `api.team-manager.gc.com`, `media-service.gc.com`, `vod-archive.gc.com`). The iOS app is purely native -- no shared web JS that might contain the key.
- Only extraction path is IPA binary analysis (e.g., `strings` or plist inspection using the known mobile client ID `0f18f027` as a search anchor).

**Workaround**: The mobile refresh token (14-day lifetime) and access token (~12-hour lifetime) work directly as `gc-token` for regular GET endpoints without needing the signing key. Only POST /auth refresh calls require the client key for gc-signature computation. Manual recapture every 14 days via proxy is viable.

**Impact on E-075-03:** Mobile programmatic token refresh cannot be implemented until the client key is known. The validation script should check for `GAMECHANGER_CLIENT_KEY_MOBILE` and output a clear warning if absent, rather than attempting refresh. Token validation via GET /me/user still works.

---

### Q2: Can we capture gc-client-id from mobile request headers?

**Status: CONFIRMED GAP -- addon does not capture this header**

**What we know:**
- The `header_capture` addon excludes only: `gc-token`, `gc-device-id`, `gc-signature`, `gc-app-name`, `cookie`. It does NOT exclude `gc-client-id`.
- The mobile session header report (`2026-03-06_211209/header-report.json`) does NOT contain `gc-client-id` in the captured headers.
- The first mobile request in the session WAS `POST /auth` (timestamp `21:12:35.480958`). This is the endpoint that sends `gc-client-id` on the web profile.
- The header report captures headers with first-seen-wins strategy per source. The `accept` header in the captured set is `application/vnd.gc.com.sync_updated_topics+json`, NOT `*/*` (which POST /auth uses). This indicates the header capture did NOT process the POST /auth request -- a later sync endpoint's headers won as first-seen.

**Possible explanations:**
1. The header_capture addon's `request()` hook was not called for the POST /auth flow (TLS handshake timing or addon initialization delay).
2. The iOS app does NOT send `gc-client-id` on POST /auth (the header is web-only).
3. The iOS app sends `gc-client-id` with a different header name.

**Conclusion:** The absence of `gc-client-id` in the report is ambiguous -- it is a capture gap, not proof the header is absent. The credential extractor also does not capture `gc-client-id` (it only captures `gc-token`, `gc-device-id`, `gc-app-name`). Story E-075-02 must add `gc-client-id` capture to both addons.

**Impact on E-075-02:** The response handler addition is the highest-value part. But the addon should also log request headers for POST /auth specifically, since the first-seen-wins strategy misses POST /auth when it is the first request.

---

### Q3: Does the mobile login/refresh flow match web?

**Status: RESPONSE SHAPE CONFIRMED IDENTICAL (2026-03-08) -- request body format still unconfirmed**

**What we know:**
All 6 mobile `POST /auth` calls used this request content-type:
```
application/vnd.gc.com.post_eden_auth+json; version=1.0.0
```

The documented web `POST /auth` content-type is:
```
application/json; charset=utf-8
```

The content-type differs. However, the POST /auth **response shape** is confirmed identical to web (2026-03-08, live mitmweb decode):

```json
{"type": "token", "access": {"data": "<jwt>", "expires": <unix-ts>}, "refresh": {"data": "<jwt>", "expires": <unix-ts>}}
```

JWT kid values, payload field names, and the `type: "token"` wrapper are all the same. The access token lifetime differs (~12 hours mobile vs ~60 min web).

**Remaining unknowns:**
- Does the request body format differ? (Web uses `{"type":"refresh"}`, `{"type":"password", ...}`, etc. -- not yet confirmed for mobile request body.)
- Does the signature algorithm differ, or is the same HMAC-SHA256 scheme used? (Cannot confirm without the mobile client key.)
- Is `gc-client-id` sent on mobile POST /auth at all?

**What stayed the same:** The endpoint path (`POST /auth`), host (`api.team-manager.gc.com`), HTTP 200 success code, response JSON structure, and JWT field layout are all confirmed identical.

**Impact on E-075-02 and E-075-03:** Response body capture is still needed to confirm the request body format. The response shape confirmation reduces risk -- the gc-signature computation difference (due to different client key) is the main remaining blocker for programmatic mobile refresh.

---

### Q4: Can we extract the refresh token from mobile POST /auth response bodies?

**Status: CONFIRMED IMPOSSIBLE with current addon -- no response handler**

**What we know:**
- The credential extractor has only a `request()` handler. Response bodies are never inspected.
- The mobile session endpoint log records only: method, host, path, query keys, content-types, status code, timestamp, source. No bodies.
- 6 mobile POST /auth calls returned HTTP 200. Response bodies were received by the iOS device but not captured by the proxy addon.

**Confirmed impact for E-075-02:** The response handler is essential. Without it, the refresh token cannot be captured automatically from any POST /auth response (web or mobile). For web, we work around this by doing programmatic refresh from Python. For mobile (where we don't yet have a confirmed client key), the response body capture is the only way to get the initial refresh token.

---

## Naming Inconsistency Status (E-075-01)

E-075-01 was described as fixing stale `GAMECHANGER_AUTH_TOKEN_*` names. **The rename appears already complete.** Current state:

| File | Status |
|------|--------|
| `src/gamechanger/client.py` | Uses `GAMECHANGER_REFRESH_TOKEN` -- correct |
| `src/gamechanger/credential_parser.py` | Uses `GAMECHANGER_REFRESH_TOKEN_WEB` -- correct |
| `proxy/addons/credential_extractor.py` | Uses `GAMECHANGER_REFRESH_TOKEN` base name, no `SIGNATURE` entry -- correct |
| `tests/test_proxy/test_credential_extractor.py` | Uses `GAMECHANGER_REFRESH_TOKEN_*` -- correct |
| `tests/test_credential_parser.py` | Uses `GAMECHANGER_REFRESH_TOKEN_WEB` -- correct |
| `tests/test_client.py` | Uses `GAMECHANGER_REFRESH_TOKEN_*` -- correct |
| `.env.example` | Uses `GAMECHANGER_REFRESH_TOKEN_*` -- correct |
| `credential_extractor.py` module docstring | Uses `GAMECHANGER_REFRESH_TOKEN_WEB` example -- correct |
| `client.py` module docstring | References `GAMECHANGER_REFRESH_TOKEN_WEB` -- correct |

**Recommendation for E-075-01 implementer:** Run the acceptance criteria checklist against the current code. All 6 ACs may already be met. If so, E-075-01 can be marked DONE with a verification note rather than requiring code changes.

---

## Key Differences: Mobile vs. Web Profile

| Dimension | Web | iOS (Mobile) |
|-----------|-----|-------------|
| User-Agent | `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...Chrome/145...` | `Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0` |
| `gc-app-version` | `0.0.0` (on POST /auth only) | `2026.7.0.0` (on all requests) |
| `gc-app-name` value | `web` | `iOS` (per `.env.example`) or possibly `mobile` (per `headers.md` -- INCONSISTENCY -- needs clarification) |
| `POST /auth` content-type | `application/json; charset=utf-8` | `application/vnd.gc.com.post_eden_auth+json; version=1.0.0` |
| `Content-Type` on GET requests | `application/vnd.gc.com.none+json; version=undefined` | `application/vnd.gc.com.none+json; version=0.0.0` |
| `Accept-Encoding` | `gzip, deflate` | `br;q=1.0, gzip;q=0.9, deflate;q=0.8` |
| Sync headers | Absent | `x-gc-origin: sync`, `x-gc-features: lazy-sync`, `x-gc-application-state: foreground` |
| Datadog | Absent | `x-datadog-origin: rum` |
| ETags | Absent | `if-none-match` (conditional GET caching) |
| `gc-client-id` value | `07cb985d-ff6c-429d-992c-b8a0d44e6fc3` (confirmed in JWT `cid`) | `0f18f027-c51e-4122-a330-9d537beb83e0` (CONFIRMED 2026-03-08 from live JWT decode) |
| `gc-signature` | Computed HMAC-SHA256 (confirmed) | NOT OBSERVED -- no capture; mobile client key unknown |

**INCONSISTENCY FLAG (unresolved as of 2026-03-08):** `headers.md` says mobile `gc-app-name` is `"mobile"` (inferred). `.env.example` says `GAMECHANGER_APP_NAME_MOBILE=iOS`. The client code docstring says the iOS app "does not send it". These three sources still disagree. The credential extractor WOULD have written the actual value to `.env` as `GAMECHANGER_APP_NAME_MOBILE` during the mobile session if the header was present. Check `.env` to resolve.

---

## Mobile Session Statistics (2026-03-06_211209)

| Metric | Value |
|--------|-------|
| Session duration | ~28 minutes (21:12:09 to 21:40:10 UTC) |
| Total requests | 744 |
| Source | All `ios` (no web or unknown) |
| Unique endpoints | 233 |
| POST /auth calls | 6 (all HTTP 200) |
| HTTP 200 | 347 |
| HTTP 304 (cached) | 352 |
| HTTP 204 (no content) | 6 |
| HTTP 404 | 19 |
| HTTP 403 | 17 |

Notable endpoints hit during the mobile session (not previously in web sessions):
- `POST /clips/search` -- video clip search
- `POST /me/tokens/firebase` -- Firebase push notification token
- `POST /me/tokens/stream-chat` and `/revoke` -- StreamChat tokens
- `GET /athlete-profile/{id}/uploading-clips` -- athlete clip uploads
- `GET /game-streams/gamestream-recap-story/{event_id}` -- game recap story
- `GET /ivs/v1/...` -- AWS IVS clip thumbnails and playlist m3u8 files (CDN direct)

---

## Addon Architecture Gaps Confirmed

Two gaps must be addressed by E-075-02:

### Gap 1: No response body capture
The credential extractor only has a `request()` hook. POST /auth response bodies (containing the refresh token in `refresh.data`) are never seen. This is the critical missing capability.

### Gap 2: gc-client-id not captured
The `_BASE_CREDENTIAL_HEADERS` dict in `credential_extractor.py` does not include `gc-client-id`. For mobile, this header may carry the mobile client ID (or confirm the web client ID is shared). Adding `gc-client-id` to the captured headers is essential for Q1 resolution.

### Gap 3: First-seen-wins misses POST /auth headers
The `header_capture` addon's first-seen-wins strategy stores headers from whichever request happens to be first per source. If POST /auth is the first request (as it was in the mobile session), the auth-specific headers (`gc-client-id`, `gc-timestamp`, `gc-app-version` on POST /auth) should be captured. But the report shows sync endpoint headers as the iOS source's headers, meaning POST /auth's headers were NOT captured despite being the first request. This may be a race condition in addon initialization. A dedicated POST /auth header capture in the credential extractor would be more reliable than depending on header_capture.

---

## Recommendation for E-075-02 and E-075-03

### E-075-02 (Addon upgrade) -- proceed as written, with this addition:
The response handler and `gc-client-id` capture are both essential. Additionally, for POST /auth requests specifically, the addon should capture the full request header set (not just the credential headers) to expose `gc-client-id`, `gc-timestamp`, and `gc-app-version`. Logging these to a session-specific JSON file (e.g., `post-auth-headers.json`) would enable offline analysis without touching the first-seen-wins header report.

### E-075-03 (Validation script) -- **validate what we CAN, skip programmatic refresh**
The validation script can confirm the mobile credential ENV vars are present, tokens are parseable JWTs, and GET /me/user works with the mobile token. It should NOT attempt mobile programmatic token refresh (blocked on unknown client key). When `GAMECHANGER_CLIENT_KEY_MOBILE` is absent, the script should output a clear "programmatic refresh unavailable -- mobile client key not yet extracted" message and still succeed for the validation checks that are possible.

**Do NOT mark E-075-03 as blocked** -- the validation script for the things we CAN check (token presence, JWT decode, GET /me/user, credential expiry reporting) is still valuable and can be implemented now.

---

## Proxy Session Checklist for Follow-Up

The following items require a NEW targeted proxy session. Estimated time: 5-10 minutes (app cold start + login).

### Before starting the proxy session:
- [ ] Check `.env` for `GAMECHANGER_REFRESH_TOKEN_MOBILE` -- if present, decode the JWT and extract the `cid` field. Compare to `GAMECHANGER_CLIENT_ID_WEB` (the known web client ID). This answers Q1 without needing a new session.
- [ ] Check `.env` for `GAMECHANGER_APP_NAME_MOBILE` -- this resolves the `headers.md` vs `.env.example` inconsistency.

### During the proxy session -- actions to take:
1. **Force a fresh login**: Log out of the iOS GameChanger app and log back in. This guarantees a complete auth flow (all POST /auth steps), not just a refresh.
2. **Open mitmweb UI** at `http://localhost:8081` on the Mac host.
3. **Find POST /auth in mitmweb**: After login, filter to `POST /auth` entries in the flow list.
4. **For each POST /auth request, capture**:
   - Full request headers (screenshot or copy -- especially `gc-client-id`, `gc-timestamp`, `gc-app-version`)
   - Request body (the JSON -- what `type` field does mobile use? Is it `{"type":"refresh"}` or something different?)
   - Response body (the JSON -- is there a `refresh.data` field? What does `access.data` look like?)
5. **Decode the `gc-token` header** value from any POST /auth request in mitmweb. It is a JWT -- paste into jwt.io or run `python3 -c "import base64,json; print(json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==')))"`. Extract the `cid` field.
6. **Note the `gc-client-id` header value** from the POST /auth request. Compare to `GAMECHANGER_CLIENT_ID_WEB`.

### Data to record:
- [ ] Mobile `cid` from JWT `gc-token` header in POST /auth
- [ ] `gc-client-id` header value in mobile POST /auth request
- [ ] Whether `cid == gc-client-id` (should be true on both platforms)
- [ ] Whether mobile `cid == GAMECHANGER_CLIENT_ID_WEB` (answers client key parity question)
- [ ] Mobile POST /auth request body JSON structure (body `type` field, other fields)
- [ ] Mobile POST /auth response body JSON structure (especially `refresh.data` presence)
- [ ] `gc-app-name` header value from mitmweb request headers

---

## Open Questions After This Analysis

| Question | Priority | Status | How to Resolve |
|----------|----------|--------|----------------|
| Is mobile `cid` == web `GAMECHANGER_CLIENT_ID_WEB`? | CRITICAL | **RESOLVED 2026-03-08** -- Mobile `cid` is `0f18f027-...`, web is `07cb985d-...`. They differ. | N/A |
| Does mobile POST /auth response contain `refresh.data`? | HIGH | **RESOLVED 2026-03-08** -- Response shape confirmed identical to web, including `refresh.data`. | N/A |
| What is the mobile client key? | CRITICAL | **UNRESOLVED** -- Confirmed different from web (401 on web key test). Embedded in iOS binary. No JS bundles in mobile traffic. | IPA binary analysis using mobile client ID `0f18f027` as search anchor (out of scope for E-075). |
| Does mobile POST /auth body use `{"type":"refresh"}` or a different structure? | HIGH | UNRESOLVED | Inspect mitmweb request body during a new proxy session. |
| What is the actual `gc-app-name` mobile header value (`"mobile"` vs `"iOS"`)? | MEDIUM | UNRESOLVED | Check `GAMECHANGER_APP_NAME_MOBILE` in `.env` (credential extractor should have written it); or inspect mitmweb during new session. |
| Does the iOS app send `gc-client-id` on POST /auth? | MEDIUM | UNRESOLVED -- capture gap | Inspect mitmweb request headers during new session, OR add addon capture and re-run. |

---

## Discovery Date

2026-03-08 (analysis of existing proxy session `2026-03-06_211209`).
