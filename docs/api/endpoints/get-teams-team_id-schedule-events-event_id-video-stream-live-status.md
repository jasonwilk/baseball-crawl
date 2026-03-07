---
method: GET
path: /teams/{team_id}/schedule/events/{event_id}/video-stream/live-status
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Schema documented. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [games, video]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule/events/{event_id}/video-stream
    reason: Full video stream metadata including status field
---

# GET /teams/{team_id}/schedule/events/{event_id}/video-stream/live-status

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns whether a game event currently has an active live stream.

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule/events/{event_id}/video-stream/live-status
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `isLive` | boolean | `true` if streaming is currently live, `false` otherwise |

## Example Response

```json
{"isLive": false}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
