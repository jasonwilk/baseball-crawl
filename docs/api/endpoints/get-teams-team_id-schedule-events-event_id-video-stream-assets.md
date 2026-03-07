---
method: GET
path: /teams/{team_id}/schedule/events/{event_id}/video-stream/assets
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 3 assets observed for one game. Confirmed 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "3 assets observed (one game)"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [games, video]
caveats:
  - >
    user_id FIELD IS PII: Contains UUID of the user who created the recording. Redact in stored files.
  - >
    duration CAN BE NULL: Short or interrupted segments have null duration. Full recordings have integer duration in seconds.
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule/events/{event_id}/video-stream
    reason: Video stream metadata for the same event
  - path: /teams/{team_id}/video-stream/assets
    reason: Team-wide assets with pagination -- alternative to event-scoped version
---

# GET /teams/{team_id}/schedule/events/{event_id}/video-stream/assets

**Status:** CONFIRMED LIVE -- 200 OK. 3 assets observed. Last verified: 2026-03-07.

Returns video recording segments for a specific game event.

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule/events/{event_id}/video-stream/assets
```

## Response

Bare JSON array of asset objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Asset UUID |
| `stream_id` | UUID | Parent video stream UUID |
| `team_id` | UUID | Team UUID |
| `schedule_event_id` | UUID | Event UUID (matches path parameter) |
| `created_at` | string (ISO 8601) | When recording started |
| `audience_type` | string | Audience restriction. Observed: `"players_family"` |
| `duration` | integer or null | Recording duration in seconds. `null` for interrupted segments; integer for complete recordings. |
| `ended_at` | string (ISO 8601) | When recording ended |
| `thumbnail_url` | string (URL) | Thumbnail at `vod-archive.gc.com` CDN |
| `user_id` | UUID | User who created the recording (**PII -- redact**) |
| `uploaded` | boolean | Whether recording was uploaded to external storage |
| `is_processing` | boolean | Whether recording is still being processed |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
