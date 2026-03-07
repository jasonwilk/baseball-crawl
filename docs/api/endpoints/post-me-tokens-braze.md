---
method: POST
path: /me/tokens/braze
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Single token field returned. Captured 2026-03-07 proxy session.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/braze-token-response.json
raw_sample_size: "single JWT token"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [me, auth]
caveats:
  - >
    THIRD-PARTY TOKEN: This endpoint returns a JWT for the Braze push notification
    service (https://www.braze.com/). It is NOT a GameChanger API token. The token
    is used by the app to authenticate with Braze for push notifications.
  - >
    NOT RELEVANT FOR DATA INGESTION: This is a push notification service credential.
    It has no utility for analytics or data crawling.
  - >
    TOKEN LIFETIME ~7 DAYS: Braze JWT exp is approximately 7 days from issuance.
    Decoded: {"sub": "{USER_UUID}", "exp": <timestamp>, "aud": "braze"}.
see_also:
  - path: /me/user
    reason: User profile -- sub field in Braze JWT matches the user UUID
---

# POST /me/tokens/braze

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns a short-lived JWT for authenticating with the Braze push notification service. Used by the GameChanger mobile/web app to register for push notifications. Not relevant for data analytics or ingestion pipelines.

```
POST https://api.team-manager.gc.com/me/tokens/braze
```

## Request Body

No request body observed. Likely an empty POST or minimal body.

## Response

| Field | Type | Description |
|-------|------|-------------|
| `token` | string | JWT for Braze push notification service. Not a gc-token. |

### Braze JWT Payload

The `token` is a JWT with payload:

| Field | Type | Description |
|-------|------|-------------|
| `sub` | UUID | User UUID (matches the authenticated user's ID) |
| `exp` | integer | Unix timestamp expiry (~7 days from issuance) |
| `aud` | string | Always `"braze"` -- audience is the Braze service |

## Example Response

```json
{
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.REDACTED.REDACTED"
}
```

## Notes

This endpoint is called by the app during session initialization to set up push notification capability. It is unrelated to the GC authentication flow documented in `POST /auth`. The Braze token cannot be used for any GameChanger API request.

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
