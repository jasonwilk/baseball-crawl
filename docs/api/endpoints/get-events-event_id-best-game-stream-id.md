---
method: GET
path: /events/{event_id}/best-game-stream-id
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Returns single-field JSON with game_stream_id. Confirmed 2026-03-04.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.game_stream_id+json; version=0.0.2"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/best-game-stream-id-sample.json
raw_sample_size: "58 bytes"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [games, bridge]
related_schemas: []
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Alternative for bulk game_stream_id resolution -- preferred for full ingestion (one call per page vs one call per game)
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Downstream consumer of game_stream_id resolved by this endpoint
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Downstream consumer of game_stream_id resolved by this endpoint
  - path: /teams/{team_id}/schedule
    reason: Source of event_id values used as path parameter here
---

# GET /events/{event_id}/best-game-stream-id

**Status:** CONFIRMED LIVE -- 200 OK. Single-field response confirmed. Last verified: 2026-03-04.

Resolves a schedule `event_id` to the `game_stream_id` required by the boxscore and plays endpoints. This is an ID bridge endpoint -- its only purpose is converting one identifier type to another.

**Two paths to `game_stream_id`:**
1. `GET /teams/{team_id}/game-summaries` (bulk, preferred for full ingestion) -- returns all games with their `game_stream.id` values
2. This endpoint (on-demand) -- one extra call per game, but avoids paginating game-summaries when you already have an `event_id`

```
GET https://api.team-manager.gc.com/events/{event_id}/best-game-stream-id
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID. From `event.id` in `GET /teams/{team_id}/schedule`, or `pregame_data.game_id` (same value). |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.game_stream_id+json; version=0.0.2
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Note:** Accept header version is `0.0.2` -- higher than most endpoints which use `0.0.0`. No `gc-user-action` observed.

## Response

Single-field JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `game_stream_id` | UUID | The game stream identifier for use with boxscore and plays endpoints |

## Example Response

```json
{"game_stream_id": "9f2a1b3c-REDACTED"}
```

## ID Relationship Summary

```
schedule event.id == pregame_data.game_id == event_id (all identical)
                      |
                      v
             /events/{event_id}/best-game-stream-id
                      |
                      v
             game_stream_id (this response field)
             == game_stream.id in game-summaries
             != game_stream.game_id in game-summaries
```

## Known Limitations

- This adds one API call per game when you already have event_ids from the schedule. For bulk ingestion, prefer game-summaries (which returns `game_stream.id` as part of the paginated response).
- Accept header uses version `0.0.2` (not `0.0.0`) -- unusual for this API.

**Discovered:** 2026-03-04. **Confirmed:** 2026-03-04.
