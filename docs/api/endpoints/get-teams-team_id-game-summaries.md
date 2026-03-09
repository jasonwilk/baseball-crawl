---
method: GET
path: /teams/{team_id}/game-summaries
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 92 records across 2 pages confirmed 2026-03-04.
  mobile:
    status: observed
    notes: >
      2 hits, HTTP 200. Observed 2026-03-09 (session 063531). Called with opponent
      progenitor_team_id (14fd6cb6), confirming this endpoint works for opponent teams.
      Both paginated (no query_keys, then start_at).
accept: "application/vnd.gc.com.game_summary:list+json; version=0.1.0"
gc_user_action: "data_loading:events"
query_params:
  - name: start_at
    required: false
    description: >
      Pagination cursor integer. Provided by the `x-next-page` response header
      on the previous page. Do not construct manually -- use the full URL from
      the x-next-page header.
pagination: true
response_shape: array
response_sample: data/raw/game-summaries-sample.json
raw_sample_size: "50 records (page 1); page2: data/raw/game-summaries-page2-sample.json (42 records); refresh: data/raw/game-summaries-refresh-sample.json"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [games, team]
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule
    reason: Full event schedule including practices and other events; includes pregame_data.opponent_id
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Per-player box score -- requires game_stream.id from this endpoint
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Pitch-by-pitch play log -- requires game_stream.id from this endpoint
  - path: /events/{event_id}/best-game-stream-id
    reason: Alternative to this endpoint for resolving event_id to game_stream_id
---

# GET /teams/{team_id}/game-summaries

**Status:** CONFIRMED LIVE -- 200 OK. 92 total records across 2 pages confirmed. Last verified: 2026-03-04.

Returns game-level summaries for completed games. Each record includes the game's final score, outcome, home/away status, and the critical `game_stream.id` needed for boxscore and plays endpoints. This endpoint is the primary way to discover `game_stream_id` values.

**Pagination required:** Send `x-pagination: true` request header. The `x-next-page` response header contains the full URL for the next page. When absent, you are on the last page.

**ID routing note:** The `game_stream.id` field in this response is the parameter needed by `GET /game-stream-processing/{game_stream_id}/boxscore` and `GET /game-stream-processing/{game_stream_id}/plays`. This value is NOT the same as `game_stream.game_id` or `event_id` -- they are different UUIDs.

```
GET https://api.team-manager.gc.com/teams/{team_id}/game-summaries
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `start_at` | No | Pagination cursor (integer). Use the full URL from `x-next-page` response header, not this parameter directly. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.game_summary:list+json; version=0.1.0
gc-user-action: data_loading:events
gc-user-action-id: {UUID}
x-pagination: true
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Note on `gc-user-action`:** Use `data_loading:events` (plural). An earlier observation of `data_loading:event` (singular) may have been incidental. The plural form is confirmed correct.

## Pagination Response Header

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/game-summaries?start_at={cursor}
```

Use the full URL from `x-next-page` as-is for the next page. When `x-next-page` is absent, you are on the last page. See `pagination.md` for the reference implementation.

## Response

Bare JSON array of game summary objects. Page size: 50 records max. Final page may have fewer records (42 records on page 2 of 92 total for the observed season).

### Game Summary Object

| Field | Type | Notes |
|-------|------|-------|
| `event_id` | UUID | Game event UUID. **Confirmed equal to `game_stream.game_id` on all 92 records.** |
| `game_stream` | object | Game stream metadata. See below. |
| `last_scoring_update` | ISO 8601 | Timestamp of last score update. |
| `opponent_team_score` | int | Opponent's final score. Range observed: 0-13. |
| `owning_team_score` | int | Requesting team's final score. Range observed: 0-19. |
| `home_away` | string | Duplicate of `game_stream.home_away`. `"home"` or `"away"`. |
| `game_status` | string | Duplicate of `game_stream.game_status`. Observed: `"completed"` only. |
| `sport_specific` | object | Baseball-specific game data. See below. |

### `game_stream` Object

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | **Game stream identifier.** USE THIS for boxscore and plays endpoints. Always differs from `game_stream.game_id`. |
| `game_id` | UUID | Game identifier. Always equals top-level `event_id`. |
| `game_status` | string | `"completed"` only observed. |
| `home_away` | string | `"home"` or `"away"` from owning team's perspective. |
| `is_archived` | boolean | All observed: `false`. |
| `opponent_id` | UUID | Opponent's team UUID -- usable with `/teams/{opponent_id}/players`. |
| `scoring_user_id` | UUID | GameChanger user who scored the game. |
| `sabertooth_major_version` | int | Internal game engine version. All observed: `4`. |
| `game_clock_elapsed_seconds_at_last_pause` | **string** | Optional clock field. **Type is string, not int.** Observed: `"0"`. Present on ~42% of records. |
| `game_clock_enabled` | boolean | Optional clock field. Observed: `false`. |
| `game_clock_mode` | string | Optional clock field. Observed: `"up"`. |
| `game_clock_start_time_milliseconds` | **string** | Optional clock field. **Type is string, not int.** Observed: `"0"`. |
| `game_clock_state` | string | Optional clock field. Observed: `"paused"`. |

**Clock fields:** When present, all five clock fields appear together. When absent, they do not appear at all (not null -- just missing). Present on 39/92 records (42%) in observed season.

### `sport_specific` Object

| Field | Type | Notes |
|-------|------|-------|
| `bats.total_outs` | int | Total outs recorded. Range: 15-53. Semantics unclear -- may be combined outs from both teams. |
| `bats.inning_details.inning` | int | Last inning played. Range: 3-9. |
| `bats.inning_details.half` | string | `"top"` or `"bottom"` -- last half-inning played. |

## Key ID Relationships

Confirmed across all 92 records:
- `event_id` == `game_stream.game_id` (always identical)
- `game_stream.id` != `game_stream.game_id` (always different)
- Use `game_stream.id` for boxscore and plays endpoints

## Example Record

```json
{
  "event_id": "48c79654-REDACTED",
  "game_stream": {
    "id": "9f2a1b3c-REDACTED",
    "game_id": "48c79654-REDACTED",
    "game_status": "completed",
    "home_away": "away",
    "is_archived": false,
    "opponent_id": "bbe7a634-REDACTED",
    "scoring_user_id": "abc12345-REDACTED",
    "sabertooth_major_version": 4
  },
  "last_scoring_update": "2025-05-24T19:10:40.662Z",
  "opponent_team_score": 8,
  "owning_team_score": 4,
  "home_away": "away",
  "game_status": "completed",
  "sport_specific": {
    "bats": {
      "total_outs": 28,
      "inning_details": {
        "inning": 5,
        "half": "bottom"
      }
    }
  }
}
```

## Known Limitations

- This endpoint does NOT contain per-player stats. Use `/teams/{team_id}/season-stats` or `/teams/{team_id}/schedule/events/{event_id}/player-stats` for player-level statistics.
- Only `"completed"` game_status observed. In-progress game statuses are unknown.
- `total_outs` semantics unclear -- may be combined outs from both teams.
- Clock fields (`game_clock_*`) have numeric-looking values stored as strings (type: string, not int). Parse accordingly.
- No game summaries where the team did not score (or where no scoring data was recorded) were observed -- edge case behavior unknown.

**Discovered:** 2026-03-04. **Both pages confirmed:** 2026-03-04.
