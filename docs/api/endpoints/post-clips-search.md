---
method: POST
path: /clips/search
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile. The web app uses /clips/search/v2 (observed 2026-03-09).
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 3 hits, all HTTP 200.
      Content-Type: application/vnd.gc.com.video_clip_search_query+json; version=0.0.0.
      Fired when viewing a game event (event_id ba140306-34a7-43a9-833c-eecb4353628d)
      and when viewing an existing game (event_id 07c39def). The version-less path
      appears to be the mobile client's clip search endpoint, while /v2 is the web client's.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: "2026-03-09"
tags: [video, search, games]
caveats:
  - >
    VERSION SPLIT: The mobile iOS app calls /clips/search (no version suffix) while
    the web app calls /clips/search/v2. Both use identical Content-Type:
    application/vnd.gc.com.video_clip_search_query+json; version=0.0.0.
    The two paths may return different response schemas or be identical -- not yet
    confirmed. For new implementations, prefer /clips/search/v2 if targeting web
    behavior, or /clips/search for mobile behavior.
  - >
    REQUEST BODY UNKNOWN: Body schema not captured (proxy logs metadata only).
    Content-Type suggests a structured query body (filters by team_id, event_id,
    player_id, clip type, date range). Same content-type as /v2 endpoint.
  - >
    RESPONSE BODY UNKNOWN: HTTP 200 observed. Body not captured.
  - >
    3 HITS IN SESSION: Called at 06:27:29, 06:27:30, and 06:30:10 during the session --
    once when viewing game event 07c39def (twice in quick succession suggesting pagination
    or parallel requests), and once when navigating to the newly-created game ba140306.
see_also:
  - path: /clips/search/v2
    reason: Web profile equivalent -- same content-type, /v2 suffix. Compare schemas when both are captured.
  - path: /events/{event_id}/highlight-reel
    reason: Structured highlight playlist for a game -- may overlap with clip search results
  - path: /teams/{team_id}/video-stream/assets
    reason: Full video recording assets (different from short clips)
---

# POST /clips/search

**Status:** CONFIRMED (mobile proxy, 3 hits, HTTP 200). Request/response bodies not captured. Last verified: 2026-03-09.

Searches for video highlight clips using a POST request body as a search query. This is the mobile app's version of the clip search endpoint; the web app uses `/clips/search/v2`.

```
POST https://api.team-manager.gc.com/clips/search
Content-Type: application/vnd.gc.com.video_clip_search_query+json; version=0.0.0
```

## Request Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.video_clip_search_query+json; version=0.0.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
gc-app-version: 2026.8.0.0
Accept-Language: en-US;q=1.0
Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8
```

## Request Body

Not captured. Based on the vendor content-type `video_clip_search_query`, expected to contain search filters. Likely same structure as `/clips/search/v2`:

- `event_id` or `game_stream_id` -- filter to a specific game
- `team_id` -- filter to a specific team
- `player_id` -- filter to a specific player
- `clip_type` -- filter by play type

## Response

**HTTP 200.** Body not captured. Expected to return clip objects with thumbnail URLs, video URLs, and play metadata.

## Relationship to /clips/search/v2

| Attribute | /clips/search (mobile) | /clips/search/v2 (web) |
|-----------|----------------------|----------------------|
| Profile | iOS mobile | Web browser |
| Content-Type | `video_clip_search_query+json; version=0.0.0` | `video_clip_search_query+json; version=0.0.0` |
| Response schema | Unknown | Unknown |
| Status | 200 (3 observations) | 200 (1 observation) |

The identical content-type suggests these may accept the same request body schema. Whether the response schemas differ is unknown -- both need body capture.

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
