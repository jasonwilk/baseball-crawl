---
method: GET
path: /game-streams/gamestream-viewer-payload-lite/{event_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 368 events from second game capture. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/gamestream-viewer-payload-lite-sample.json
raw_sample_size: "368 events (second capture, 2026-03-07)"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [games, events]
caveats:
  - >
    USES event_id NOT game_stream_id: Despite the name, this endpoint takes an event_id
    from the schedule (UUID), not a game_stream_id. It resolves to the game stream internally.
  - >
    event_data IS A JSON-ENCODED STRING: Same as /game-streams/{game_stream_id}/events.
    Must JSON-parse the event_data field to access inner fields.
related_schemas: []
see_also:
  - path: /game-streams/{game_stream_id}/events
    reason: Same events without the wrapper structure or created_at field
  - path: /teams/{team_id}/schedule
    reason: Source of event_id values used as path parameter here
---

# GET /game-streams/gamestream-viewer-payload-lite/{event_id}

**Status:** CONFIRMED LIVE -- 200 OK. 368 events in second capture (2026-03-07). Last verified: 2026-03-07.

Returns the lightweight game viewer payload for a completed game. Contains the same event stream as `GET /game-streams/{game_stream_id}/events` but with additional fields and a summary structure.

**Note on path:** Takes the `event_id` from the schedule directly -- it resolves to the game stream internally. Does NOT require a `game_stream_id`.

```
GET https://api.team-manager.gc.com/game-streams/gamestream-viewer-payload-lite/{event_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID (from `GET /teams/{team_id}/schedule`) -- NOT a game_stream_id |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `stream_id` | UUID | The resolved game stream UUID (= `game_stream.id` from game-summaries) |
| `latest_events` | array | Event records with 5 fields per record (see below) |
| `all_event_data_ids` | array | Array of inner event UUIDs (the `id` from inside parsed `event_data`) |
| `marker` | string or null | Cursor for incremental polling. For completed games: string of last sequence_number (e.g., `"367"` for 368-event stream -- confirmed from sample) |

### `latest_events` Record Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Outer event record UUID |
| `stream_id` | UUID | Game stream UUID |
| `created_at` | string (ISO 8601) | When event was created (extra field vs `/game-streams/{id}/events`) |
| `event_data` | string | **JSON-encoded string** -- same as other events endpoint, must be JSON-parsed |
| `sequence_number` | integer | Ordering position |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
