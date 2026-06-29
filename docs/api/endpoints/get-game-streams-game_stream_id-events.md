---
method: GET
path: /game-streams/{game_stream_id}/events
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      368 events for a different game captured 2026-03-07. Re-confirmed 2026-06-28
      against a controlled test team: documented the structured `pitch` event
      attributes (speed int MPH, speedProvider, style lowercase pitch type) and the
      per-pitch createdAt timestamp. This is the typed pitch-level source the plays
      endpoint flattens into its template suffix.
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
last_confirmed: "2026-06-28"
tags: [games, events, stats]
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
  - path: /game-stream-processing/{event_id}/plays
    reason: Processed play-by-play -- FLATTENS this endpoint's structured pitch attributes (speed/style) into a template-string suffix and carries no timestamp; preferred for outcomes/sequence
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Processed box score -- preferred for per-player stats
  - path: /teams/{team_id}/schedule/events/{event_id}/player-stats
    reason: Processed spray-chart / player-stats -- preferred view of the ball_in_play x/y coordinates this endpoint carries in transaction sub-events
  - path: /teams/{team_id}/game-summaries
    reason: Source of game_stream.id (= game_stream_id) needed for this endpoint
---

# GET /game-streams/{game_stream_id}/events

**Status:** CONFIRMED LIVE -- 200 OK. 368 events for second game confirmed 2026-03-07 (previously: 319 events for first game). Structured `pitch` attributes + per-pitch `createdAt` re-confirmed against a controlled test team 2026-06-28. Last verified: 2026-06-28.

Returns the raw event stream for a completed game. This is the low-level event log from which all higher-level game data (boxscore, plays, stats) is derived.

**Coaching relevance: LOW for box/play use, but this is the STRUCTURED PITCH-LEVEL SOURCE.** For boxscore and play-by-play, use the processed `GET /game-stream-processing/{id}/plays` or `.../boxscore`. BUT for typed pitch data — pitch **speed** (MPH), pitch **type**, and per-pitch **timing** (`createdAt`) — this endpoint is the source of truth: the plays endpoint flattens those fields into a template-string suffix and carries no timestamp at all. See the `pitch` Event subsection below.

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
| `pitch` | `result`, `speed`, `speedProvider`, `style`, `advancesRunners`, `advancesCount` | A single pitch recorded. **The structured pitch-level source** — see dedicated subsection below. |
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

### `pitch` Event — the STRUCTURED pitch-level source

This endpoint is the **typed source of truth for pitch-level data** (result, speed, type, timing). The processed plays endpoint (`GET /game-stream-processing/{event_id}/plays`) FLATTENS these structured fields into a single template string — e.g. the plays `at_plate_details` template `"Strike 1 looking (101 MPH Curveball)"` is a render of the structured `{result: "strike_looking", speed: 101, style: "curveball"}` here. If you need pitch velocity, pitch type, or per-pitch timing as typed fields (rather than string-parsing the plays suffix), read this endpoint.

A `pitch` event's `event_data.attributes` (verified 2026-06-28 against a controlled test team that charted speed + type):

| Attribute | Type | Description |
|-----------|------|-------------|
| `result` | string (enum) | Pitch result. Observed: `"ball"`, `"strike_looking"`, `"strike_swinging"`, `"foul"`. (A ball put in play is recorded via the `ball_in_play` sub-event of a `transaction`, not as a `pitch` result.) |
| `speed` | integer \| absent | Pitch speed in **MPH** (integer in-sample). Absent when the scorekeeper did not chart speed. |
| `speedProvider` | string | Provenance of `speed`. Observed: `"user"` (manually entered). The field name implies a device/radar alternative may exist for teams with radar integration — unconfirmed. Use it to distinguish manual vs automated speeds for data-quality gating. |
| `style` | string \| null | Pitch type, **lowercase**: `"fastball"`, `"curveball"`, `"slider"`, `"changeup"`, `"cutter"` (and presumably an `"unclear"` value — unobserved). `null` when speed was charted but type was not (this is the structured form of the plays speed-only suffix `"(75 MPH)"`). |
| `advancesCount` | boolean | Whether this pitch advanced the ball/strike count. |
| `advancesRunners` | boolean | Whether this pitch advanced runners. |

Plus, on the `event_data` wrapper itself: `id` (UUID), `code` (`"pitch"`), `createdAt` (epoch ms), `compactorAttributes.stream`. And on the top-level event object: `id`, `stream_id`, `sequence_number`.

**`createdAt` is a RECORD timestamp, not an official pitch clock.** It is the moment the pitch event was entered. For a live-scored real game it approximates actual pitch tempo; on a manually-backfilled game (e.g. the test team, where `speedProvider: "user"`) the inter-event deltas are typing cadence, not real pitch timing. There is no official game-clock / pitch-clock field. NOTE: the plays endpoint carries NO timestamp at all — `createdAt` here is the only per-pitch time signal in the GameChanger data.

**Style case differs from plays.** `style` here is lowercase (`"curveball"`); the plays template renders it title-case (`"Curveball"`). Normalize case if correlating the two.

**Discovered:** 2026-03-07. **368-event sample confirmed:** 2026-03-07. **`pitch` structured attributes (speed/speedProvider/style) + createdAt timing documented, ground-truthed against test team:** 2026-06-28.
