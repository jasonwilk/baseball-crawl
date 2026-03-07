---
method: GET
path: /game-streams/{game_stream_id}/events
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: 368 events for a different game captured 2026-03-07. Second capture confirms schema.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/game-stream-events-sample.json
raw_sample_size: "368 events (second game capture, 2026-03-07)"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [games, events]
caveats:
  - >
    event_data IS A JSON-ENCODED STRING: The event_data field is a JSON string, not a
    JSON object. Must JSON-parse the string to access inner fields (code, attributes, etc.).
  - >
    SOME EVENTS ARE BATCHED: Some events use an "events" array inside event_data (batched
    multi-event records) rather than a single code/attributes object.
related_schemas: []
see_also:
  - path: /game-streams/gamestream-viewer-payload-lite/{event_id}
    reason: Same events with additional created_at field and summary wrapper -- alternative access via event_id
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Processed play-by-play -- preferred for coaching use cases
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Processed box score -- preferred for per-player stats
  - path: /teams/{team_id}/game-summaries
    reason: Source of game_stream.id (= game_stream_id) needed for this endpoint
---

# GET /game-streams/{game_stream_id}/events

**Status:** CONFIRMED LIVE -- 200 OK. 368 events for second game confirmed 2026-03-07 (previously: 319 events for first game). Last verified: 2026-03-07.

Returns the raw event stream for a completed game. This is the low-level event log from which all higher-level game data (boxscore, plays, stats) is derived.

**Coaching relevance: LOW for direct use.** Use `GET /game-stream-processing/{id}/plays` (processed play-by-play) or `GET /game-stream-processing/{id}/boxscore` for most coaching use cases. This is the underlying raw data.

```
GET https://api.team-manager.gc.com/game-streams/{game_stream_id}/events
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_stream_id` | UUID | The `game_stream.id` from game-summaries |

## Response

Bare JSON array of event objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Event record UUID |
| `stream_id` | UUID | The game stream UUID (matches path parameter) |
| `sequence_number` | integer | Ordering position (0-based) |
| `event_data` | string | **JSON-encoded string** containing the actual event payload. Must be JSON-parsed separately. |

### `event_data` Inner Object (after JSON-parsing)

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Event type code (see below) |
| `id` | UUID | Event UUID |
| `createdAt` | integer | Unix timestamp in milliseconds |
| `attributes` | object | Code-specific attributes |
| `compactorAttributes` | object | Stream compaction metadata. `stream` field: `"head"` or `"main"`. |
| `events` | array | For batched events -- array of individual event objects (same shape) |

### Observed Event Codes

Confirmed codes from 368-event sample (2026-03-07):

| Code | Attributes | Description |
|------|-----------|-------------|
| `set_teams` | `homeId`, `awayId`, `aniFT` | Game initialization -- sets home and away team UUIDs |
| `fill_lineup_index` | `teamId`, `playerId`, `index` | Assigns a player to a lineup slot by index |
| `fill_position` | `teamId`, `playerId`, `position` | Assigns a player to a field position |
| `message` | `content`, `sender` | In-game message or note from scorekeeper |
| `pitch` | `result`, `advancesRunners`, `advancesCount` | A single pitch recorded |
| `transaction` | (none -- contains nested `events` array) | At-bat completion event. Contains a nested `events` array with sub-events. |
| `base_running` | varies | Baserunning event (stolen base, advance, out on bases) |
| `replace_runner` | varies | Courtesy runner substitution |
| `undo` | varies | Undo of a prior event |
| `edit_group` | varies | Batch edit/correction to prior events |

### transaction Event -- Nested Events and Spray Chart Data

`transaction` events use the `events` array (NOT `attributes`) for their payload. The nested array can contain:
- `fill_position` -- fielding assignments (position + teamId + playerId)
- `fill_lineup_index` -- batting order assignments
- `ball_in_play` -- **SOURCE OF SPRAY CHART DATA** (see below)

**`ball_in_play` sub-event attributes:**
```json
{
  "playResult": "fielders_choice",
  "defenders": [
    {
      "error": false,
      "position": "2B",
      "location": {"x": 205.0, "y": 132.4}
    }
  ],
  "playType": "ground_ball"
}
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `playResult` | string | Outcome: `"fielders_choice"`, `"single"`, `"out"`, `"home_run"`, etc. |
| `playType` | string | Contact type: `"ground_ball"`, `"line_drive"`, `"fly_ball"`, `"pop_up"`, etc. |
| `defenders` | array | Fielders involved in the play |
| `defenders[].position` | string | Fielder's position (`"2B"`, `"SS"`, `"1B"`, etc.) |
| `defenders[].location.x` | float | Fielder x-coordinate on the spray chart canvas |
| `defenders[].location.y` | float | Fielder y-coordinate on the spray chart canvas |
| `defenders[].error` | boolean | Whether the fielder committed an error |

**Discovered:** 2026-03-07. **368-event sample confirmed:** 2026-03-07.
