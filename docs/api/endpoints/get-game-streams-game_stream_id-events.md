---
method: GET
path: /game-streams/{game_stream_id}/events
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: 319 events for a 6-inning game. Full schema documented. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "319 events (6-inning game)"
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

**Status:** CONFIRMED LIVE -- 200 OK. 319 events for a 6-inning game. Last verified: 2026-03-07.

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

| Code | Description |
|------|-------------|
| `set_teams` | Game initialization -- sets home team UUID (`homeId`) and away team UUID (`awayId`) |
| `fill_lineup_index` | Assigns a player to a lineup slot by index. Attributes: `teamId`, `playerId`, `index`. |
| `reorder_lineup` | Reorders the batting lineup |
| `fill_position` | Assigns a player to a field position |
| `sub_players` | Substitution event |
| `pitch` | A single pitch recorded |
| `transaction` | At-bat transaction (hit, out, walk, etc.) |
| `base_running` | Baserunning event (stolen base, advance, out on bases) |
| `edit_group` | Batch edit/correction to prior events |
| `replace_runner` | Courtesy runner substitution |
| `undo` | Undo of a prior event |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
