---
method: GET
path: /game-streams/gamestream-recap-story/{event_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: partial
    notes: >
      HTTP 404 returned for event 1e0f8dfc on 2026-03-07. Endpoint exists (confirmed via
      2026-03-05 proxy capture with 200 OK). Recap may not be generated for all games.
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
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [games, events]
caveats:
  - >
    HTTP 404 FOR SOME EVENTS: Returns 404 when a recap has not been generated for the
    event. May require the game to be fully processed and scored. Not available for
    all games.
related_schemas: []
see_also:
  - path: /game-streams/insight-story/bats/{event_id}
    reason: Related insight endpoint (also returns 404 for some events)
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Play-by-play data -- preferred for coaching use
---

# GET /game-streams/gamestream-recap-story/{event_id}

**Status:** OBSERVED (proxy capture 2026-03-05). HTTP 404 for event tested 2026-03-07. Recap may not be generated for all games.

Returns a narrative recap story for a completed game event.

```
GET https://api.team-manager.gc.com/game-streams/gamestream-recap-story/{event_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

## Investigation Status

**404 confirmed:** Event `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` returned 404 on 2026-03-07. The recap may not be generated for all games or may require additional processing time after game completion. Full response schema not captured.

**Discovered:** 2026-03-05 (proxy). **Last tested:** 2026-03-07 (404).
