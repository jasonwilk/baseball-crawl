---
method: GET
path: /teams/{team_id}/schedule/events/{event_id}/video-stream
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.schedule_event_video_stream+json; version=0.0.0"
gc_user_action: "data_loading:event"
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-11"
tags: [games, video]
caveats:
  - >
    CREDENTIAL IN RESPONSE: publish_url and ingest_endpoints[].stream_key contain live
    stream credentials. Do not log or store these values.
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule/events/{event_id}/video-stream/assets
    reason: Video recording segments for this event
  - path: /teams/{team_id}/schedule/events/{event_id}/video-stream/live-status
    reason: Live/ended status check without full video metadata
---

# GET /teams/{team_id}/schedule/events/{event_id}/video-stream

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-11.

Returns video stream configuration and metadata for a specific game event.

**Coaching relevance: LOW for stat analytics.**

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule/events/{event_id}/video-stream
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `stream_id` | UUID | Video stream UUID (different from `game_stream.id`) |
| `schedule_event_id` | UUID | Event UUID (matches path parameter) |
| `disabled` | boolean | Whether streaming is disabled for this event |
| `is_muted` | boolean | Whether stream audio is muted |
| `team_id` | UUID | Team UUID |
| `user_id` | UUID | User who configured the stream (**PII -- redact**) |
| `viewer_count` | integer | Current viewer count (0 for completed games) |
| `audience_type` | string | `"players_family"` or other audience restriction |
| `is_playable` | boolean | Whether the stream is currently playable |
| `thumbnail_url` | string or null | Thumbnail URL |
| `playable_at` | string or null | When playback becomes available (null for past games) |
| `live_at` | string or null | When the stream went live |
| `status` | string | Stream status. Observed: `"ended"` |
| `publish_url` | string | RTMPS ingest URL (**contains stream key -- treat as credential**) |
| `shared_by_opponent` | boolean | Whether opponent shared their stream |
| `aws_ivs_account_id` | string | AWS IVS account identifier |
| `associated_external_camera` | object or null | External camera configuration |
| `ingest_endpoints` | array | Available ingest protocols (RTMPS, SRT) |
| `person_id` | string | Person identifier. Observed: empty string `""`. Purpose unclear. |
| `active_asset_playback_url` | string | Playback URL for active VOD asset. Observed: empty string `""` on ended streams. |

## Accept Header

Confirmed from proxy session 2026-03-11:
```
Accept: application/vnd.gc.com.schedule_event_video_stream+json; version=0.0.0
gc-user-action: data_loading:event
```

## Example Response

```json
{
  "stream_id": "00000000-REDACTED",
  "schedule_event_id": "00000000-REDACTED",
  "disabled": false,
  "is_muted": false,
  "team_id": "00000000-REDACTED",
  "user_id": "00000000-REDACTED",
  "viewer_count": 0,
  "audience_type": "players_family",
  "is_playable": false,
  "thumbnail_url": null,
  "playable_at": null,
  "live_at": null,
  "status": "ended",
  "publish_url": "[REDACTED -- stream key credential]",
  "person_id": "",
  "active_asset_playback_url": "",
  "playback_url": "[REDACTED -- signed IVS URL]"
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-11 (Accept header, gc-user-action, and two new fields added).
