---
method: POST
path: /me/tokens/stream-chat
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 1 hit, HTTP 200.
      Accept: application/vnd.gc.com.none+json; version=0.0.0 (no body sent).
      Fired at app startup (06:26:46, within seconds of app launch and auth).
accept: "application/vnd.gc.com.none+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: "2026-03-09"
tags: [auth, me, user]
caveats:
  - >
    NOT RELEVANT FOR DATA INGESTION: Stream.io is a third-party real-time messaging
    platform (https://getstream.io). This endpoint issues a Stream Chat JWT that
    the iOS app uses to connect to GC's team chat/messaging feature. It is not
    part of the stats or scheduling data flows.
  - >
    REQUEST BODY: The request content-type is application/vnd.gc.com.none+json,
    suggesting no body is sent -- the GC API derives the user identity from the
    gc-token header and issues the Stream Chat token accordingly.
  - >
    RESPONSE BODY UNKNOWN: HTTP 200. Body not captured. Based on Stream.io docs,
    expected response: {"token": "{stream_chat_jwt}"}.
  - >
    COMPARE TO BRAZE: Similar in purpose to POST /me/tokens/braze (push notifications)
    and POST /me/tokens/firebase (FCM push notifications). All three are third-party
    integration token issuance endpoints.
see_also:
  - path: /me/tokens/braze
    reason: Similar third-party token issuance (Braze push notifications)
  - path: /me/tokens/firebase
    reason: Similar third-party token issuance (Firebase push notifications)
---

# POST /me/tokens/stream-chat

**Status:** CONFIRMED (mobile proxy, 1 hit, HTTP 200). Response body not captured. Last verified: 2026-03-09.

Issues a Stream Chat JWT for the authenticated user. Stream.io is a third-party real-time messaging SDK used by the GC app for team chat functionality. This token is exchanged at app startup and grants the user access to Stream Chat channels.

**Not relevant for data ingestion.** Documented for completeness.

```
POST https://api.team-manager.gc.com/me/tokens/stream-chat
```

## Request Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.none+json; version=0.0.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
```

## Request Body

No body sent (content-type is `none`). Identity derived from `gc-token`.

## Response

**HTTP 200.** Body not captured. Expected to contain a Stream Chat JWT:

```json
{
  "token": "{stream_chat_jwt}"
}
```

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
