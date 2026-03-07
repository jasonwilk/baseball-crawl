---
method: GET
path: /teams/{team_id}/video-stream/videos
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Returns empty array []. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [team, video]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule/events/{event_id}/video-stream/assets
    reason: Event-specific video assets -- confirmed populated (3 assets observed)
---

# GET /teams/{team_id}/video-stream/videos

**Status:** CONFIRMED LIVE -- 200 OK (empty array). Last verified: 2026-03-07.

Returns standalone videos for a team (distinct from per-event video stream assets). Empty array observed.

```
GET https://api.team-manager.gc.com/teams/{team_id}/video-stream/videos
```

## Response

`[]` (empty array observed). Full schema unknown when records are present.

**Discovered:** 2026-03-07. **Confirmed (empty):** 2026-03-07.
