---
method: POST
path: /auth
status: PARTIAL
auth: required
profiles:
  web:
    status: partial
    notes: >
      HTTP 400 received due to expired gc-signature (gc-timestamp was ~6.2 hours stale).
      Endpoint existence confirmed. Success response schema NOT YET CAPTURED.
      Discovered 2026-03-04.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "*/*"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [auth, user]
caveats:
  - >
    SUCCESS RESPONSE SCHEMA UNKNOWN: HTTP 400 was received before a valid response
    could be captured. The response schema is inferred from context -- likely returns
    a new gc-token JWT, but field name and structure are unconfirmed.
  - >
    PROGRAMMATIC REFRESH NOT POSSIBLE: The gc-signature header requires a secret
    signing key embedded in browser JavaScript. Without the signing algorithm, this
    endpoint cannot be called programmatically. Fresh gc-token values must be
    obtained via browser traffic capture.
  - >
    GC-SIGNATURE FRESHNESS WINDOW UNKNOWN: A gc-timestamp 22,316 seconds (~6.2 hours)
    stale was rejected with HTTP 400. The actual freshness window may be shorter.
    Browser signatures should be used immediately after capture.
  - >
    ACCEPT HEADER EXCEPTION: Uses Accept: "*/*" -- NOT a vendor-typed header.
    This is the only endpoint in the API with this Accept value. All GET endpoints
    use application/vnd.gc.com.* vendor types.
related_schemas: []
see_also:
  - path: /me/user
    reason: Lightweight token health check (GET /me/user returns 200 if token is valid, 401 if expired) -- use as pre-flight before long ingestion runs
---

# POST /auth

**Status:** PARTIALLY CONFIRMED -- endpoint exists and responds. HTTP 400 received due to expired `gc-signature`. Success response schema not yet captured. Last attempt: 2026-03-04.

This is the **only POST endpoint** documented in this API. All other endpoints are GET requests. This is the token refresh flow -- used by the browser to extend the authenticated session without requiring the user to log in again.

**Practical note:** With a 14-day token lifetime, programmatic refresh is rarely needed. The immediate priority is using the token before it expires rather than refreshing it.

```
POST https://api.team-manager.gc.com/auth
```

## Request Body

```json
{"type": "refresh"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Refresh type. Observed value: `"refresh"`. Other values unknown. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-client-id: {GC_CLIENT_ID}
gc-signature: {GC_SIGNATURE}
gc-timestamp: {GC_TIMESTAMP}
gc-app-name: web
gc-app-version: 0.0.0
Accept: */*
Content-Type: application/json; charset=utf-8
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Key differences from GET endpoints:**
- `Accept: */*` -- not vendor-typed (all GET endpoints use `application/vnd.gc.com.*`)
- `Content-Type: application/json; charset=utf-8` -- not the vendor-typed `application/vnd.gc.com.none+json` used by GET requests
- No `gc-user-action` or `gc-user-action-id` headers
- Three extra headers: `gc-signature`, `gc-timestamp`, `gc-client-id`
- `gc-app-version: 0.0.0` -- not observed on any GET endpoint

## gc-signature Mechanics

The `gc-signature` and `gc-timestamp` headers implement request signing.

| Header | Format | Notes |
|--------|--------|-------|
| `gc-signature` | Two base64 segments joined by `.` (e.g., `{b64}={period}{b64}=`) | HMAC computed by browser JavaScript |
| `gc-timestamp` | Unix seconds string | Time the signature was computed |
| `gc-client-id` | UUID | Matches `cid` field in the JWT payload. Likely an input to the signature. |

**Freshness window:** A gc-timestamp 22,316 seconds (~6.2 hours) stale was rejected with HTTP 400. Actual window may be shorter.

**Cannot be replicated programmatically:** The signing algorithm and secret key are embedded in the GameChanger browser JavaScript bundle. The key is not publicly documented and has not been extracted.

## Response Schema (Successful -- NOT YET CAPTURED)

The successful response schema has not been confirmed. Based on request structure, the expected response is a new gc-token JWT.

| Field | Type | Description |
|-------|------|-------------|
| `token` | string (inferred) | New gc-token JWT. **Field name is speculative -- must be confirmed.** |

Additional fields (expiry, user context, refresh token) may be present.

## Error Response (HTTP 400 -- Confirmed)

When `gc-signature` is stale:

```
HTTP/2 400
Content-Type: text/plain; charset=utf-8
x-server-epoch: <current-unix-seconds>
gc-timestamp: <current-unix-seconds>

Bad Request
```

Error body is plain text `"Bad Request"` (11 bytes), not JSON. Note the server returns `gc-timestamp` in response headers (its current Unix time).

## Implications for Programmatic Auth

**Current status:** Programmatic token refresh is NOT possible. The `gc-signature` requires a key and algorithm embedded in browser JavaScript that are not yet known.

**Practical consequence:** Fresh `gc-token` values must be obtained by capturing browser traffic. Token lifetime is 14 days (`exp - iat = 1,209,600 seconds`), so manual rotation is needed approximately every 2 weeks.

**gc-client-id:** The `gc-client-id` request header matches the `cid` field in the JWT payload. This is a stable client identifier (not session-specific) that should be stored alongside `gc-device-id` in the `.env` file.

**Future investigation:** The signing algorithm could potentially be reverse-engineered from the GameChanger web app JavaScript bundle. This would enable fully programmatic token refresh and eliminate browser captures entirely.

## Token Health Check Alternative

Instead of refresh, use `GET /me/user` as a lightweight pre-flight check:
- Returns `200 OK` if the `gc-token` is valid
- Returns `401` if expired
- Use before long ingestion runs to detect stale credentials early

**Discovered:** 2026-03-04.
