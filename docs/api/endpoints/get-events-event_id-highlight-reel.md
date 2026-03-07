---
method: GET
path: /events/{event_id}/highlight-reel
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-05, confirmed 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/event-highlight-reel-sample.json
raw_sample_size: "13 playlist entries (1 game, 609 second duration)"
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [games, video]
caveats:
  - >
    CLOUDFRONT SIGNED COOKIES: All video URLs require CloudFront signed cookies for
    playback. Cookies are embedded per-playlist entry.
  - >
    URLS EXPIRE: Signed CloudFront URLs and cookies have time-limited validity.
    Do not cache long-term.
related_schemas: []
see_also:
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: pbp_id in playlist links to id in plays response
  - path: /teams/{team_id}/schedule/events/{event_id}/video-stream/assets
    reason: Individual video assets for same event
---

# GET /events/{event_id}/highlight-reel

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns a structured highlight reel for a completed game event. Playlist interleaves inning-transition plates with play clips, each linked to a play-by-play event via `pbp_id`.

**Coaching relevance: LOW for stat analytics.** Not needed for data ingestion.

```
GET https://api.team-manager.gc.com/events/{event_id}/highlight-reel
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `multi_asset_video_id` | UUID | Multi-asset video identifier (matches `event_id`) |
| `event_id` | UUID | Event UUID (matches path parameter) |
| `status` | string | Highlight reel status. Observed: `"finalized"` |
| `type` | string | Asset type. Observed: `"event"` |
| `playlist` | array | Ordered list of video segments |
| `playlist[].media_type` | string | `"video"` |
| `playlist[].url` | string (URL) | HLS (.m3u8) CloudFront-signed video URL |
| `playlist[].is_transition` | boolean | `true` for inning marker plates, `false` for play clips |
| `playlist[].clip_id` | UUID (optional) | Clip identifier -- absent on transition plates |
| `playlist[].pbp_id` | UUID (optional) | Play-by-play ID -- links to `id` in `/game-stream-processing/{id}/plays`. Absent on transitions. |
| `playlist[].cookies` | object | CloudFront signed cookies: `CloudFront-Key-Pair-Id`, `CloudFront-Signature`, `CloudFront-Policy` |
| `duration` | integer | Total highlight reel duration in seconds |
| `thumbnail_url` | string (URL) | CloudFront-signed thumbnail URL |
| `small_thumbnail_url` | string | Small thumbnail URL (observed: empty string `""`) |

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
