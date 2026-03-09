---
method: GET
path: /game-streams/gamestream-recap-story/{event_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 200 confirmed for event 3cab6a64 (Nighthawks Navy game) on 2026-03-09.
      Query params game_stream_id and team_id observed in this call. HTTP 404
      for event 1e0f8dfc on 2026-03-07 -- recap not generated for all games.
      Status upgraded from OBSERVED to CONFIRMED.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params:
  - name: game_stream_id
    required: unknown
    description: >
      The game stream UUID for the event. May be used to resolve the stream
      when the event_id alone is ambiguous.
  - name: team_id
    required: unknown
    description: >
      The team UUID. May scope the recap to a team-specific narrative perspective.
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-09"
tags: [games, events]
caveats:
  - >
    HTTP 404 FOR SOME EVENTS: Returns 404 when a recap has not been generated for the
    event. May require the game to be fully processed and scored. Not available for
    all games. Event 1e0f8dfc returned 404 on 2026-03-07; event 3cab6a64 returned
    200 on 2026-03-09.
  - >
    RESPONSE BODY NOT CAPTURED: The proxy log confirms 200 OK and the query params
    (game_stream_id, team_id) but does not capture the response body. Schema unknown.
  - >
    QUERY PARAMS: game_stream_id and team_id observed as query params (not path params)
    in the 2026-03-09 capture. Whether these are required or optional is not confirmed.
related_schemas: []
see_also:
  - path: /game-streams/insight-story/bats/{event_id}
    reason: Related insight endpoint (also returns 404 for some events)
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Play-by-play data -- preferred for coaching use
  - path: /events/{event_id}/best-game-stream-id
    reason: Resolves event_id to game_stream_id (needed for game_stream_id query param)
---

# GET /game-streams/gamestream-recap-story/{event_id}

**Status:** CONFIRMED LIVE -- 200 OK (some games). HTTP 404 for events without a generated recap. Last verified: 2026-03-09.

Returns a narrative recap story for a completed game event. Accepts optional `game_stream_id` and `team_id` query params that may scope or resolve the recap.

```
GET https://api.team-manager.gc.com/game-streams/gamestream-recap-story/{event_id}?game_stream_id={game_stream_id}&team_id={team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `game_stream_id` | UUID | unknown | Game stream UUID for the event (see `/events/{event_id}/best-game-stream-id`) |
| `team_id` | UUID | unknown | Team UUID -- may scope narrative to team's perspective |

## Investigation Status

**200 confirmed:** Event `3cab6a64-6c99-497d-8674-eb7576dda41e` (Nighthawks Navy vs. opponent, 2026-03-09 session) returned 200. The call included `game_stream_id` and `team_id` query params. Response body not captured -- schema unknown.

**404 confirmed:** Event `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` returned 404 on 2026-03-07. Recap may not be generated for all games.

**Priority:** Capture the response body to document the recap schema. The narrative recap may contain structured team/player references useful for coaching context.

**Discovered:** 2026-03-05 (proxy). **Last confirmed (200):** 2026-03-09.
