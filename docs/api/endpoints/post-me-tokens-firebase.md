---
method: POST
path: /me/tokens/firebase
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile. Web apps do not typically use FCM directly.
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 1 hit, HTTP 204 No Content.
      Content-Type: application/vnd.gc.com.post_firebase_token+json; version=0.0.0.
      Fired at app startup (06:26:47), immediately after POST /me/tokens/stream-chat.
      HTTP 204 means no response body is returned.
accept: null
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
    NOT RELEVANT FOR DATA INGESTION: Firebase Cloud Messaging (FCM) is Google's
    push notification platform. This endpoint registers the device's FCM token
    with the GC backend so the app can receive push notifications. Not part of
    the stats or scheduling data flows.
  - >
    REQUEST BODY: The request body likely contains the FCM device token (a long
    string unique to each device installation). Content-type post_firebase_token
    confirms this.
  - >
    HTTP 204: No response body -- the server just acknowledges receipt of the token.
  - >
    COMPARE TO BRAZE AND STREAM-CHAT: Three third-party token endpoints fired at
    startup: POST /me/tokens/braze (Braze push), POST /me/tokens/firebase (FCM push),
    POST /me/tokens/stream-chat (Stream Chat). All are third-party integration
    token registrations.
see_also:
  - path: /me/tokens/braze
    reason: Similar third-party token registration (Braze)
  - path: /me/tokens/stream-chat
    reason: Similar third-party token exchange (Stream Chat)
---

# POST /me/tokens/firebase

**Status:** CONFIRMED (mobile proxy, 1 hit, HTTP 204). Response body not returned (204). Last verified: 2026-03-09.

Registers the iOS device's Firebase Cloud Messaging (FCM) push notification token with the GC backend. Called at app startup so the server knows where to send push notifications for this device.

**Not relevant for data ingestion.** Documented for completeness.

```
POST https://api.team-manager.gc.com/me/tokens/firebase
Content-Type: application/vnd.gc.com.post_firebase_token+json; version=0.0.0
```

## Request Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.post_firebase_token+json; version=0.0.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
```

## Request Body

Body not captured. Based on the content-type `post_firebase_token`, expected:

```json
{
  "token": "{fcm_device_token}"
}
```

Where `fcm_device_token` is the Firebase registration token for the device.

## Response

**HTTP 204 No Content.** No response body.

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
