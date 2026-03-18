# Mobile Auth Notes

## Existing Mobile Proxy Session (2026-03-06_211209)

744 iOS-sourced requests. 6 POST /auth calls (all HTTP 200). Session reviewed 2026-03-08 for E-075-R-01.

**Key finding -- eden_auth:** Mobile POST /auth uses content-type `application/vnd.gc.com.post_eden_auth+json; version=1.0.0`. Web POST /auth uses `application/json; charset=utf-8`. Different protocol version suspected. Request/response body structure unknown -- no response handler in addon.

**gc-client-id status:** NOT captured. Header capture addon missed POST /auth headers (first-seen-wins race: sync endpoint headers won, but POST /auth was first request). Credential extractor does not capture gc-client-id at all. Whether iOS sends it is unknown.

**Naming inconsistency (gc-app-name):** `headers.md` says mobile sends `"mobile"` (inferred). `.env.example` says `GAMECHANGER_APP_NAME_MOBILE=iOS`. Client.py docstring says iOS "does not send it". Actual value is in `.env` as `GAMECHANGER_APP_NAME_MOBILE` (written by credential extractor during session) -- check there to resolve.

**E-075-01 status (as of 2026-03-08):** The GAMECHANGER_AUTH_TOKEN -> GAMECHANGER_REFRESH_TOKEN rename appears ALREADY COMPLETE across client.py, credential_parser.py, credential_extractor.py, and all tests. E-075-01 implementer should verify ACs before making changes.

## To Resolve Client Key Parity

Decode `GAMECHANGER_REFRESH_TOKEN_MOBILE` from `.env` (if present -- credential extractor wrote it during 2026-03-06 mobile session). Extract `cid` field. Compare to `GAMECHANGER_CLIENT_ID_WEB`. If equal, client keys are shared.

```python
import base64, json
token = "eyJ..."  # from GAMECHANGER_REFRESH_TOKEN_MOBILE in .env
payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
print(payload.get('cid'))  # compare to GAMECHANGER_CLIENT_ID_WEB
```

## iOS Client ID Version History (Confirmed via Proxy)

| App Version | iOS Version | Client ID |
|-------------|-------------|-----------|
| Odyssey/2026.8.0 | 26.3.0 | `0f18f027-c51e-4122-a330-9d537beb83e0` |
| Odyssey/2026.9.0 | 26.3.1 | `23e37466-2878-43f4-a9f8-5f1751b7efcf` (current as of 2026-03-12) |

Client IDs rotate with major iOS app versions. The JS bundle multi-match issue (E-127-02) is related: web bundle also contains multiple EDEN_AUTH_CLIENT_KEY entries (web + current mobile).

## Mobile vs Web Differences (Confirmed)

| Header | Web | Mobile |
|--------|-----|--------|
| POST /auth content-type | `application/json; charset=utf-8` | `application/vnd.gc.com.post_eden_auth+json; version=1.0.0` |
| POST /auth Accept | N/A | `application/vnd.gc.com.eden_auth+json; version=1.0.0` |
| GET content-type | `application/vnd.gc.com.none+json; version=undefined` | `application/vnd.gc.com.none+json; version=0.0.0` |
| gc-app-version | `0.0.0` (POST /auth only) | `2026.9.0.0` (all requests; was 2026.7.0.0) |
| Accept-Encoding | `gzip, deflate, br, zstd` (real Chrome) | `br;q=1.0, gzip;q=0.9, deflate;q=0.8` |

## Proxy Addon Gaps (E-075-02 targets)

1. No response handler -- POST /auth response bodies (refresh token in `refresh.data`) never captured
2. gc-client-id not in _BASE_CREDENTIAL_HEADERS
3. First-seen-wins strategy misses POST /auth headers when it's the first request

## Full Findings

`epics/E-075-mobile-credential-capture/R-01-findings.md`
