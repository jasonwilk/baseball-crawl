---
method: PATCH
path: /me/team-notification-settings/{team_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not independently captured from web profile.
  mobile:
    status: observed
    notes: >
      2 hits, HTTP 200. Captured from iOS proxy session 2026-03-12_034919
      (app version 2026.9.0). Full request body and response body captured.
      Called when operator adjusted notification preferences on a followed team page.
accept: "application/json; charset=utf-8"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-12"
last_confirmed: null
tags: [me, team, user, write]
caveats:
  - >
    WRITE OPERATION: Updates the authenticated user's personal notification preferences
    for this team. Not relevant for data ingestion.
  - >
    PER-FIELD PATCHING CONFIRMED: The iOS app sends one or two fields per call inside
    an "updates" wrapper object. It does NOT send the full settings object. Two observed
    calls: {"updates":{"video_stream_start":false}} and
    {"updates":{"video_stream_end":false,"video_stream_start":false}}.
  - >
    CONTENT-TYPE IS VENDOR-TYPED: Request Content-Type is
    application/vnd.gc.com.patch_user_team_notification_settings+json; version=0.0.0.
    Accept header was not separately specified in the iOS request -- the response
    Content-Type was application/json; charset=utf-8.
  - >
    RESPONSE CONTAINS FULL SETTINGS OBJECT: The response echoes all notification
    preference fields regardless of what was patched. Null fields indicate "use default
    / not configured".
  - >
    RESPONSE CONTAINS PII: The response object includes team_id and user_id UUIDs.
see_also:
  - path: /me/team-notification-settings/{team_id}
    reason: GET endpoint for the same per-user notification settings
  - path: /teams/{team_id}/team-notification-setting
    reason: Team-admin-level notification setting (not per-user)
---

# PATCH /me/team-notification-settings/{team_id}

**Status:** OBSERVED -- HTTP 200 (12 hits) in web proxy session 2026-03-12_034919.

Updates the authenticated user's personal notification settings for a specific team. High hit count (12) suggests this is called per-toggle in the notification settings UI rather than batching all preferences into a single call.

```
PATCH https://api.team-manager.gc.com/me/team-notification-settings/{team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.patch_user_team_notification_settings+json; version=0.0.0
```

## Request Body

Partial update using an `updates` wrapper. Send only the fields being changed:

```json
{
  "updates": {
    "video_stream_start": false
  }
}
```

Known updatable fields (from observed calls): `video_stream_start`, `video_stream_end`. Other notification fields likely include: `game_start`, `game_end`, `scoring_play`, `lead_changes`, `player_activity`, `player_clips`, `event_clips_processed`, `end_of_period`.

## Response

**HTTP 200.** Returns the full notification settings object for the team/user pair:

```json
{
  "team_id": "00000000-0000-0000-0000-000000000001",
  "user_id": "00000000-0000-0000-0000-000000000002",
  "end_of_period": null,
  "event_clips_processed": null,
  "game_end": null,
  "game_start": null,
  "lead_changes": false,
  "player_activity": null,
  "player_clips": null,
  "scoring_play": null,
  "video_stream_end": false,
  "video_stream_start": false
}
```

`null` fields indicate the preference is using the server default (not explicitly configured by the user). `false` indicates the user has explicitly disabled the notification.

**Coaching relevance: NONE.** User notification preferences. Not relevant to data ingestion.

**Discovered:** 2026-03-12. Session: 2026-03-12_034919 (mobile).
