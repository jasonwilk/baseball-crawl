---
method: GET
path: /events/{event_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
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
tags: [games, events]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule
    reason: Source of event_id values (individual event lookup without paginating full schedule)
  - path: /bats-starting-lineups/{event_id}
    reason: Lineup linked via pregame_data.lineup_id in this response
  - path: /events/{event_id}/best-game-stream-id
    reason: Resolves event_id to game_stream_id for boxscore/plays access
---

# GET /events/{event_id}

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns full details for a single scheduled event. Same data as an individual event in the schedule list (`GET /teams/{team_id}/schedule`) but as a single-object lookup without needing to paginate.

`pregame_data.lineup_id` links to the `id` field in `GET /bats-starting-lineups/{event_id}`.

```
GET https://api.team-manager.gc.com/events/{event_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

## Response

Single JSON object with two top-level keys: `event` and `pregame_data`.

### `event` Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Event UUID (matches path parameter) |
| `event_type` | string | `"game"`, `"practice"`, or other event type |
| `sub_type` | array | Sub-type tags (empty array `[]` observed for standard games) |
| `status` | string | `"scheduled"`, `"completed"`, etc. |
| `full_day` | boolean | Whether this is an all-day event |
| `team_id` | UUID | The team this event belongs to |
| `start.datetime` | string (ISO 8601) | Game start time in UTC |
| `end.datetime` | string (ISO 8601) | Scheduled end time in UTC |
| `arrive.datetime` | string (ISO 8601) | Requested arrival time in UTC |
| `timezone` | string | IANA timezone (e.g., `"America/Chicago"`) |

### `pregame_data` Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Same as `event.id` |
| `game_id` | UUID | Same as `event.id` (redundant field) |
| `opponent_name` | string | Opponent team display name |
| `opponent_id` | UUID | Opponent team UUID (= `progenitor_team_id` for opponent endpoint lookups) |
| `home_away` | string | `"home"` or `"away"` |
| `lineup_id` | UUID | UUID of the pre-game lineup -- links to `GET /bats-starting-lineups/{event_id}` id field |

## Example Response

```json
{
  "event": {
    "id": "e3471c3b-8c6d-450c-9541-dd20107e9ace",
    "event_type": "game",
    "sub_type": [],
    "status": "scheduled",
    "full_day": false,
    "team_id": "72bb77d8-REDACTED",
    "start": {"datetime": "2025-04-06T19:00:00.000Z"},
    "end": {"datetime": "2025-04-06T21:00:00.000Z"},
    "arrive": {"datetime": "2025-04-06T19:00:00.000Z"},
    "timezone": "America/Chicago"
  },
  "pregame_data": {
    "id": "e3471c3b-8c6d-450c-9541-dd20107e9ace",
    "game_id": "e3471c3b-8c6d-450c-9541-dd20107e9ace",
    "opponent_name": "Nebraska Prime Gold 14u",
    "opponent_id": "f00549a8-84b1-4c9f-97e9-79942531d13b",
    "home_away": "away",
    "lineup_id": "a39fbbeb-05bd-4b2c-b7cc-b249a3d17a6c"
  }
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
