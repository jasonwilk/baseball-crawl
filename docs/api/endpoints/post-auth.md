---
method: POST
path: /auth
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Three-token architecture fully documented 2026-03-07. gc-signature algorithm
      fully reverse-engineered 2026-03-07. Programmatic refresh confirmed working
      from Python. All five body types documented. Browser refresh pattern (401->200
      retry) observed and recorded. Success response schema confirmed from proxy
      session 2026-03-07_171705.
  mobile:
    status: observed
    notes: >
      POST /auth response confirmed from mobile proxy session (mitmweb, 2026-03-08).
      Response shape identical to web: {"type":"token","access":{...},"refresh":{...}}.
      Access token lifetime ~12 hours (vs ~60 min on web). Mobile client ID confirmed
      different from web (0f18f027-... vs 07cb985d-...). Mobile client KEY not yet
      extracted (in iOS binary). Content-Type differs: mobile uses
      application/vnd.gc.com.post_eden_auth+json; version=1.0.0 instead of
      application/json; charset=utf-8. JWT kid values same as web. JWT payload
      fields identical to web. gc-client-id capture gap -- not confirmed sent on
      mobile POST /auth (proxy addon did not record it).
accept: "*/*"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-04"
last_confirmed: "2026-03-07"
tags: [auth, user]
caveats:
  - >
    SIGNATURE CHAINING IN LOGIN FLOW: Steps 2-4 of the full login flow require
    chaining the server's response gc-signature into the next request. The
    previousSignature is the part after the dot in the response gc-signature header.
    Step 2 (client-auth) explicitly uses usePreviousSignature: false.
  - >
    TWO TOKEN TYPES IN gc-token HEADER: For refresh calls, gc-token must contain
    the REFRESH token JWT (14-day lifetime). Using an expired ACCESS token in the
    header results in 401; the browser then retries with the refresh token.
  - >
    CLIENT-AUTH HAS NO gc-token HEADER: Step 2 (client-auth) is the only
    POST /auth call that sends no gc-token. All other body types require gc-token.
  - >
    ACCEPT HEADER EXCEPTION: Uses Accept: "*/*" -- NOT a vendor-typed header.
    This is the only endpoint in the API with this Accept value.
  - >
    RESPONSE SCHEMA INFERRED FOR SOME STEPS: The success response for client-auth,
    user-auth, password, and logout has not been independently confirmed via direct
    curl. Observed from browser proxy session patterns. Refresh response schema
    (new access + refresh tokens) is confirmed.
see_also:
  - path: /me/user
    reason: Lightweight token health check (GET /me/user returns 200 if token is valid, 401 if expired) -- use as pre-flight before long ingestion runs
---

# POST /auth

**Status:** CONFIRMED -- endpoint exists and responds. Programmatic refresh confirmed working from Python (2026-03-07). gc-signature algorithm fully reverse-engineered (2026-03-07). Last confirmed via direct curl/Python: 2026-03-07.

This is the **only POST endpoint** documented in this API. All other endpoints are GET requests. It handles the full authentication lifecycle: login, refresh, and logout.

```
POST https://api.team-manager.gc.com/auth
```

## Three-Token Architecture

GameChanger uses three distinct JWT token types. All are transmitted via the `gc-token` header, but for different steps:

| Token Type | `type` field | Lifetime | JWT Fields | Used As gc-token For |
|-----------|-------------|----------|------------|----------------------|
| **Client token** | `"client"` | 10 minutes | `type`, `sid`, `cid`, `iat`, `exp` | Steps 3 and 4 of full login flow |
| **Access token** | `"user"` | ~60 minutes (3,600s) | `type`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp` | All standard API requests; NOT for POST /auth |
| **Refresh token** | (none) | 14 days (1,209,600s) | `id`, `cid`, `uid`, `email`, `iat`, `exp` | POST /auth refresh and logout calls |

**Key differences in JWT payload fields:**
- Access token uses `userId` (camelCase), `type: "user"`, and `rtkn` (refresh token link)
- Refresh token uses `uid` (not `userId`), no `type` field, and `id` (format: `{session_uuid}:{refresh_token_uuid}`)
- Client token uses `sid` (session ID), `type: "client"`, and has no user identity fields
- All three tokens contain `cid`, which matches the `gc-client-id` header value

## Request Headers

All `POST /auth` calls share this header structure (regardless of body type):

```
gc-device-id:    {GC_DEVICE_ID}
gc-client-id:    {GC_CLIENT_ID}
gc-signature:    {GENERATED_SIGNATURE}
gc-timestamp:    {UNIX_SECONDS}
gc-app-name:     web
gc-app-version:  0.0.0
Accept:          */*
Content-Type:    application/json; charset=utf-8
User-Agent:      Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**gc-token is also required for all body types EXCEPT client-auth.** See per-step documentation below.

**Key differences from GET endpoints:**
- `Accept: */*` -- not vendor-typed (all GET endpoints use `application/vnd.gc.com.*`)
- `Content-Type: application/json; charset=utf-8` -- required for POST body
- No `gc-user-action` or `gc-user-action-id` headers
- Three extra headers: `gc-signature`, `gc-timestamp`, `gc-client-id`
- `gc-app-version: 0.0.0` -- constant for the web app
- `gc-app-version` is absent on GET endpoints; present on POST /auth

## gc-signature Algorithm

The `gc-signature` header is now fully understood and can be generated programmatically. Full documentation: `docs/api/auth.md` and `data/raw/gc-signature-algorithm.md`.

### Format

```
gc-signature: {nonce}.{hmac}
```

- **nonce**: `Base64(random 32 bytes)` -- fresh per request
- **hmac**: `HMAC-SHA256(clientKey, message)` as Base64

### HMAC Message

```
{timestamp}|{nonce_raw_bytes}|{sorted_body_values}[|{previousSig_raw_bytes}]
```

- `nonce` and `previousSignature` are appended as **raw bytes** (parsed from Base64), not Base64 strings
- Body values are extracted recursively with keys sorted alphabetically
- `previousSignature` is the HMAC component (after the `.`) from the server's last response header; omitted for standalone calls

### Client Key

`clientKey` is a Base64-encoded 32-byte secret hardcoded in the web app bundle as `{clientId}:{clientKey}`. Same for all users; stable between GC web bundle redeployments. Store as `GAMECHANGER_CLIENT_KEY_WEB` in `.env`. See `auth.md` [Client ID Rotation](../auth.md#client-id-rotation) for rotation details.

**Freshness:** The `gc-timestamp` must be current. A timestamp 22,316 seconds (~6.2 hours) stale was rejected with HTTP 400.

## Five Body Types

### 1. `client-auth` -- Establish Anonymous Session

Part of the full login flow (step 2).

```json
{"type": "client-auth", "client_id": "{CLIENT_ID}"}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | `"client-auth"` |
| `client_id` | Yes | The GC client UUID. Matches `gc-client-id` header. |

**gc-token:** NOT sent. This is the only body type with no gc-token header.

**gc-signature:** Generated with `usePreviousSignature: false` (no chaining -- first call in the chain).

**Response (200 OK):** Returns a client token JWT (`type: "client"`, 10-minute lifetime). Use as gc-token in steps 3 and 4.

### 2. `user-auth` -- Identify User

Part of the full login flow (step 3).

```json
{"type": "user-auth", "email": "{EMAIL}"}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | `"user-auth"` |
| `email` | Yes | User's email address. **PII -- never log.** |

**gc-token:** Client token from step 2.

**gc-signature:** Generated with previousSignature chained from step 2 response.

**Purpose:** Identifies the user within the anonymous client session. Does not authenticate -- just declares intent. No credentials validated yet.

### 3. `password` -- Authenticate

Part of the full login flow (step 4).

```json
{"type": "password", "password": "{PASSWORD}"}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | `"password"` |
| `password` | Yes | User's password. **Sensitive -- never log.** |

**gc-token:** Client token from step 2 (same token as step 3).

**gc-signature:** Generated with previousSignature chained from step 3 response.

**Response (200 OK):** Returns access token + refresh token on success.

### 4. `refresh` -- Exchange Refresh Token for New Access Token

The standard day-to-day programmatic flow. Confirmed working from Python (2026-03-07).

```json
{"type": "refresh"}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | `"refresh"` |

**gc-token:** Refresh token JWT (14-day lifetime). Using an expired access token here results in 401.

**gc-signature:** Generated fresh, no previousSignature needed for standalone refresh calls.

**Response (200 OK):**

```json
{
  "type": "token",
  "access": {"data": "<access-token-jwt>", "expires": "<unix-timestamp>"},
  "refresh": {"data": "<refresh-token-jwt>", "expires": "<unix-timestamp>"}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"token"` for successful auth responses |
| `access.data` | string | New access token JWT (~60 minutes) |
| `access.expires` | number | Unix timestamp when the access token expires |
| `refresh.data` | string | New refresh token JWT (~14 days). Replace in `.env`. |
| `refresh.expires` | number | Unix timestamp when the refresh token expires |

Both tokens are returned as nested objects. Store `refresh.data` in `.env` as `GAMECHANGER_REFRESH_TOKEN_WEB`. The access token (`access.data`) is used for all API calls until it expires.

### 5. `logout` -- Invalidate Session

Part of the full login flow (step 1), or for explicit logout.

```json
{"type": "logout"}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | `"logout"` |

**gc-token:** Refresh token of the session to invalidate.

**gc-signature:** Required.

**Response (200 OK):** Session invalidated. No body (or empty body).

## Complete Login Flow

For full programmatic login from email/password when no valid refresh token exists:

1. `POST /auth {"type":"logout"}` with old refresh token -- invalidate previous session
2. `POST /auth {"type":"client-auth","client_id":"{id}"}` -- no gc-token, get client token
3. `POST /auth {"type":"user-auth","email":"{email}"}` with client token -- identify user
4. `POST /auth {"type":"password","password":"{pw}"}` with client token -- authenticate, get access + refresh tokens

See `docs/api/auth.md` for full details and `data/raw/auth-login-flow-findings.json` for the captured request sequence.

## Browser 401->200 Retry Pattern

The browser implements automatic token refresh when the access token expires. Observed sequence from proxy session `2026-03-07_171705`:

```
17:19:28 POST /auth -> 200 (initial session auth with refresh token)
17:19:29 POST /auth -> 200 (second team auth)
17:19:49 POST /auth -> 401 (expired access token used as gc-token)
17:19:49 POST /auth -> 200 (immediate retry with refresh token)
17:19:51 POST /auth -> 401 (another expired access token attempt)
17:19:52 POST /auth -> 200 (retry with refresh token)
18:11:06 POST /auth -> 200 (periodic refresh ~51 minutes later)
```

## Error Responses

### HTTP 400 -- Stale Signature

```
HTTP/2 400
Content-Type: text/plain; charset=utf-8
x-server-epoch: <current-unix-seconds>
gc-timestamp: <current-unix-seconds>

Bad Request
```

Body is plain text `"Bad Request"` (not JSON). Server returns its current `gc-timestamp` in response headers -- useful for detecting clock skew.

### HTTP 401 -- Wrong Token Type

When the access token (not refresh token) is sent as `gc-token` for a refresh call:

```
HTTP/2 401
```

The browser immediately retries with the refresh token.

## Mobile Profile Notes (Confirmed 2026-03-08)

| Dimension | Web | Mobile (iOS) |
|-----------|-----|-------------|
| `Content-Type` on request | `application/json; charset=utf-8` | `application/vnd.gc.com.post_eden_auth+json; version=1.0.0` |
| Response shape | `{"type":"token","access":{...},"refresh":{...}}` | Identical (confirmed) |
| Access token lifetime | ~3,600s (~60 min) | ~43,997s (~12 hours) |
| Refresh token lifetime | 1,209,600s (14 days) | 1,209,600s (14 days) |
| JWT `kid` values | `fd4b4904-...` / `b3503b45-...` | Same (confirmed) |
| JWT payload fields | `type`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp` | Identical (confirmed) |
| `gc-client-id` value | `07cb985d-ff6c-429d-992c-b8a0d44e6fc3` | `0f18f027-c51e-4122-a330-9d537beb83e0` (DIFFERENT) |
| Client key status | Extracted from JS bundle | NOT YET EXTRACTED (iOS binary) |

**Important:** Because the mobile client ID differs from web, the mobile client key almost certainly also differs. Do not use `GAMECHANGER_CLIENT_KEY_WEB` to compute `gc-signature` for mobile POST /auth calls. The mobile client key must be extracted from the iOS binary before programmatic mobile token refresh is possible.

The mobile `eden_auth` content-type may indicate a different auth protocol version. Response bodies confirm the same schema, but whether request body format (e.g., `{"type":"refresh"}`) also matches web has not been independently confirmed from a captured request body. See `epics/E-075-mobile-credential-capture/R-01-findings.md` for open questions.

## Token Health Check Alternative

Use `GET /me/user` as a lightweight pre-flight check:
- Returns `200 OK` if the access `gc-token` is valid
- Returns `401` if expired
- Use before long ingestion runs to detect stale credentials early

**Discovered:** 2026-03-04. **gc-signature algorithm cracked / programmatic refresh confirmed:** 2026-03-07.
