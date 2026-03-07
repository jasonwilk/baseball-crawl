---
method: GET
path: /teams/{team_id}/video-stream/assets
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Schema partially documented from capture. Coaching relevance is none.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0"
gc_user_action: "data_loading:events"
query_params:
  - name: includeProcessing
    required: false
    description: Whether to include assets still being processed. Value not confirmed.
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-02-28"
last_confirmed: "2026-03-04"
tags: [team, video]
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule/events/{event_id}/video-stream/assets
    reason: Per-event video assets (event-scoped variant of this endpoint)
  - path: /teams/{team_id}/video-stream/videos
    reason: Related team video list endpoint (returned empty in observed capture)
---

# GET /teams/{team_id}/video-stream/assets

**Status:** CONFIRMED LIVE -- 200 OK. Schema partially documented. Coaching relevance: None.

Returns video stream assets for a team. This is video infrastructure metadata, not coaching analytics data. Documented for completeness.

```
GET https://api.team-manager.gc.com/teams/{team_id}/video-stream/assets
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `includeProcessing` | No | Whether to include assets still being processed. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0
gc-user-action: data_loading:events
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Response

Bare JSON array of video asset objects. Schema is partially documented.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Asset UUID |
| `stream_id` | UUID | Parent stream UUID |
| `team_id` | UUID | Team UUID |
| `schedule_event_id` | UUID | Associated event UUID |
| `created_at` | ISO 8601 | Asset creation timestamp |
| `audience_type` | string | Observed: `"players_family"` |
| `duration` | int or null | Duration in seconds (null if not available) |
| `ended_at` | ISO 8601 | When recording ended |
| `thumbnail_url` | string (URL) | VOD archive thumbnail URL |
| `user_id` | UUID | Uploader/recorder user UUID. **PII.** |
| `uploaded` | boolean | Whether this was an uploaded file |
| `is_processing` | boolean | Whether the asset is still processing |

## Known Limitations

- Coaching relevance: None. Video asset metadata, not stat data.
- Schema partially documented from early capture; full field set may differ.

**Discovered:** Pre-2026-03-01. **Confirmed:** 2026-03-04.
