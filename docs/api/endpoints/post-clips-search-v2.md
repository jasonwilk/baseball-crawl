---
method: POST
path: /clips/search/v2
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: 1 hit, status 200. Triggered when viewing the game video/clips view. Discovered 2026-03-09.
  mobile:
    status: not_applicable
    notes: >
      The iOS app uses /clips/search (without /v2 suffix). 3 hits observed in
      session 2026-03-09_062610 at /clips/search. Identical content-type. Whether
      response schemas differ is unknown.
accept: "application/vnd.gc.com.video_clip_search_query+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: unknown
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: null
tags: [video, search, games]
caveats:
  - >
    WRITE-STYLE POST: This is a search query sent as a POST body, not a resource creation.
    The response body was not captured in the proxy log (proxy captures metadata only).
  - >
    REQUEST BODY UNKNOWN: Body schema not captured. Content-Type is
    application/vnd.gc.com.video_clip_search_query+json; version=0.0.0 which suggests
    a structured query (filters by team, date range, event_id, player_id, or clip type).
  - >
    CONTEXT: Triggered at 06:15:22 in the session, shortly after viewing a game event
    (event_id 07c39def-7720-49d8-83e7-c08c6055a557). The /clips/ prefix suggests this
    is the video highlight clips search -- distinct from full video assets under
    /teams/{team_id}/video-stream/assets.
related_schemas: []
see_also:
  - path: /teams/{team_id}/video-stream/assets
    reason: Full video recording assets for a team (different from highlight clips)
  - path: /teams/{team_id}/video-stream/videos
    reason: Video list for a team
  - path: /events/{event_id}/highlight-reel
    reason: Structured highlight playlist for a specific game event
---

# POST /clips/search/v2

**Status:** OBSERVED (proxy log, 1 hit, status 200). Response body not captured. Last verified: 2026-03-09.

Searches for video highlight clips using a POST request body as a search query. Triggered when the web app displays the clips/highlights view for a game.

```
POST https://api.team-manager.gc.com/clips/search/v2
Content-Type: application/vnd.gc.com.video_clip_search_query+json; version=0.0.0
```

## Request Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Content-Type: application/vnd.gc.com.video_clip_search_query+json; version=0.0.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Request Body

Request body schema not captured in proxy log. Based on the vendor content type (`video_clip_search_query`) and context (viewing a specific game), expected fields include:

- `event_id` or `game_stream_id` -- filter to a specific game
- `team_id` -- filter to a specific team
- `player_id` -- filter to a specific player
- `clip_type` -- filter by play type or highlight category
- Pagination parameters

## Response

Response body not captured. Status 200 observed. Expected to return an array or paginated list of clip objects, each likely containing:

- Clip identifier
- Thumbnail URL
- Video URL or signed asset URL
- Associated player_id and event_id
- Timestamp and play metadata

## Known Limitations

- Request body schema unknown -- needs follow-up capture.
- Response schema unknown -- needs follow-up capture.
- Relationship to `/events/{event_id}/highlight-reel` unclear -- may return the same clips with different schema.
- The `/v2` suffix implies a v1 exists (likely `/clips/search/v1` or `/clips/search`); not observed.

**Discovered:** 2026-03-09. Session: 2026-03-09_061156.
