---
method: GET
path: /game-streams/player-insights/bats/{event_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: partial
    notes: HTTP 404 confirmed for event e3471c3b on 2026-03-07. Endpoint exists (proxy capture). Schema unknown.
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
tags: [games, player]
caveats:
  - >
    HTTP 404 FOR SOME EVENTS: Returns 404 for the event tested on 2026-03-07. Full
    response schema not captured.
related_schemas: []
see_also:
  - path: /game-streams/insight-story/bats/{event_id}
    reason: Related team-level batting insights (also returns 404)
---

# GET /game-streams/player-insights/bats/{event_id}

**Status:** OBSERVED (proxy capture). HTTP 404 for event tested 2026-03-07. Response schema unknown.

Returns per-player batting insights for a game event. Full schema not captured.

```
GET https://api.team-manager.gc.com/game-streams/player-insights/bats/{event_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

## Investigation Status

HTTP 404 returned for event `e3471c3b-8c6d-450c-9541-dd20107e9ace` on 2026-03-07. Consistent with prior proxy observation of 404. Full response schema not captured.

**Discovered:** 2026-03-05 (proxy). **Last tested:** 2026-03-07 (404).
