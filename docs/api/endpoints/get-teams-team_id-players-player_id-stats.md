---
method: GET
path: /teams/{team_id}/players/{player_id}/stats
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented from 80-record capture. 387 KB response.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.player_stats:list+json; version=0.0.0"
gc_user_action: "data_loading:player_stats"
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/player-stats-sample.json
raw_sample_size: "80 records, 387 KB"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [player, stats, season, spray-chart]
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule/events/{event_id}/player-stats
    reason: Both teams' stats per game in one call (most efficient box score source -- preferred for ingestion)
  - path: /teams/{team_id}/season-stats
    reason: Season aggregates for all players (avoids per-player calls for aggregate data)
  - path: /teams/{team_id}/players
    reason: Get player UUIDs for use as player_id in this endpoint
  - path: /teams/{team_id}/game-summaries
    reason: Get game_stream_id values; event_id from game-summaries == event_id in this response
---

# GET /teams/{team_id}/players/{player_id}/stats

**Status:** CONFIRMED LIVE -- 200 OK. 80 records, 387 KB. Last verified: 2026-03-04.

Returns per-game statistics for one player across all games in the season. Includes batting, pitching/fielding stats per game, rolling cumulative season totals, and spray chart data (ball-in-play coordinates). Must be called once per player to build a full team box score.

**ID routing for this endpoint:**
```
GET /teams/{team_id}/players  -> player UUID list
  -> GET /teams/{team_id}/players/{player_id}/stats (this endpoint)

event_id in response == game_stream.game_id in game-summaries (for joining)
stream_id in response == game_stream.id in game-summaries (for boxscore/plays)
```

```
GET https://api.team-manager.gc.com/teams/{team_id}/players/{player_id}/stats
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |
| `player_id` | UUID | Player UUID from `GET /teams/{team_id}/players` |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.player_stats:list+json; version=0.0.0
gc-user-action: data_loading:player_stats
gc-user-action-id: {UUID}
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Response

Bare JSON array of per-game stat records. 80 records in a single response (no pagination). Records are NOT in chronological order -- sort by `game_date` to reconstruct season trajectory.

### Top-Level Record Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `event_id` | UUID | No | Game event UUID. Same as `game_stream.game_id` in game-summaries. Join key. |
| `stream_id` | UUID | No | Game stream UUID. Same as `game_stream.id` in game-summaries (NOT `game_id`). |
| `game_date` | ISO 8601 | No | Game date/time (UTC). Records NOT sorted chronologically. |
| `player_stats` | object | No | Per-game statistics for this player. |
| `player_stats.stats` | object | No | Contains `offense` (conditional), `defense` (conditional), `general` (always). |
| `cumulative_stats` | object | No | Rolling season totals through and including this game. Same structure. |
| `offensive_spray_charts` | array or null | Yes | Ball-in-play locations for batting. Null on 24/80 games. |
| `defensive_spray_charts` | array or null | Yes | Ball-in-play locations for fielding. Null on 67/80 games. |

### player_stats.stats Sections (Conditional)

| Key | Present when | Absent when |
|-----|-------------|-------------|
| `offense` | Player batted in this game | Pitcher-only appearance (2/80 records) |
| `defense` | Player fielded or pitched | DH-only or rare offensive-only appearance (4/80) |
| `general` | Always | Never absent |

**general.GP:** Always `1` in `player_stats.general` (per-game record). In `cumulative_stats.general`, reflects the running GP total.

### Key Per-Game Offense Fields (Subset)

| Field | Type | Description |
|-------|------|-------------|
| `PA` | int | Plate appearances this game |
| `AB` | int | At bats this game |
| `H` | int | Hits this game |
| `BB` | int | Walks this game |
| `SO` | int | Strikeouts this game |
| `R` | int | Runs scored this game |
| `RBI` | int | RBI this game |
| `OBP` | float | On-base percentage (this game only) |
| `OPS` | float | OPS (this game only) |

Full offense field set is the same 84 fields as `GET /teams/{team_id}/season-stats`. See that endpoint for the complete table.

**Note:** SB, CS, and PIK may not appear in `player_stats.offense` -- they may only appear in `cumulative_stats.offense`. Verify presence before parsing.

### Key Per-Game Defense Fields (Pitching Subset)

| Field | Type | Description |
|-------|------|-------------|
| `GP:P` | int | Games pitched (1 in per-game). Presence indicates pitching appearance. |
| `IP` | float | Innings pitched this game |
| `ER` | int | Earned runs this game |
| `SO` | int | Strikeouts thrown this game |
| `BB` | int | Walks issued this game |
| `ERA` | float | ERA for this game appearance |
| `WHIP` | float | WHIP for this game appearance |
| `FIP` | float | FIP for this game appearance |
| `BF` | int | Batters faced this game |
| `#P` | int | Total pitches thrown this game |

When `GP:P` is absent or 0, only fielding-only fields (~34 fields) are present. When `GP:P > 0`, the full pitching + fielding field set (~129 fields) is present.

**New fields in player-stats defense NOT documented in season-stats:**
- `IP:SF` (float) -- Innings at short field position. Observed: `0`.
- `TP:P` (int) -- Triple plays as pitcher. Observed: `0`.
- `OS`, `OSS`, `OSSM`, `OSSW`, `OS%`, `OS#MPH`, `OSMPH` -- Outswing stats. All observed: `0`. Reserved for future pitch velocity tracking.

### Spray Chart Item Structure

Each item in `offensive_spray_charts` or `defensive_spray_charts`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier for this play event |
| `code` | string | Event type. Observed: `"ball_in_play"` only |
| `createdAt` | int | Unix timestamp in **milliseconds** |
| `attributes.playType` | string | Ball-in-play type: `"ground_ball"`, `"fly_ball"`, `"line_drive"`, `"pop_fly"`, `"bunt"`, `"hard_ground_ball"`, `"other"` |
| `attributes.playResult` | string | Outcome: `"batter_out"`, `"batter_out_advance_runners"`, `"single"`, `"double"`, `"triple"`, `"home_run"`, `"fielders_choice"`, `"error"`, `"sacrifice_bunt"`, `"sacrifice_fly"`, `"other_out"` |
| `attributes.defenders` | array | Fielder(s) involved (usually 1, occasionally 2 for double plays) |
| `attributes.defenders[].position` | string | Position code: `"1B"`, `"2B"`, `"3B"`, `"SS"`, `"LF"`, `"CF"`, `"RF"`, `"P"`, `"C"` |
| `attributes.defenders[].location.x` | int | X coordinate on field diagram. Origin/scale unconfirmed. |
| `attributes.defenders[].location.y` | int | Y coordinate on field diagram. Origin/scale unconfirmed. |
| `attributes.defenders[].error` | boolean | Whether this defender committed an error |
| `compactorAttributes.stream` | string | Always `"main"` observed |

**Multiple items per game:** 1-3 spray chart items observed per game (max 3 in this capture). Multiple items = multiple balls in play for that player in that role.

**Counts:** Offensive charts present on 56/80 games (70%), defensive on 13/80 games (16%).

## Cumulative Stats Behavior

`cumulative_stats` = rolling season totals through the game date of each record:
- `general.GP` shows the running game count
- Records are NOT in chronological order -- sort by `game_date` first
- The final record (by game_date) carries the season totals -- equivalent to season-stats data for this player
- Cumulative offense has three additional fields not in per-game: `SB`, `CS`, `PIK`
- Cumulative defense has additional fields: `A` (assists), `outs-2B`, `outs-RF`

## Example Response Item

```json
{
  "event_id": "48c79654-REDACTED",
  "stream_id": "9f2a1b3c-REDACTED",
  "game_date": "2025-04-03T23:00:00.000Z",
  "player_stats": {
    "stats": {
      "offense": {"AB": 3, "H": 1, "BB": 1, "SO": 0, "R": 1, "RBI": 2},
      "general": {"GP": 1},
      "defense": {"GP:F": 1, "PO": 2, "A": 0, "E": 0}
    }
  },
  "cumulative_stats": {
    "stats": {
      "offense": {"AB": 3, "H": 1, "GP": 1},
      "general": {"GP": 2},
      "defense": {}
    }
  },
  "offensive_spray_charts": [
    {
      "id": "uuid-REDACTED",
      "code": "ball_in_play",
      "createdAt": 1743806400000,
      "attributes": {
        "playType": "ground_ball",
        "playResult": "batter_out_advance_runners",
        "defenders": [{"position": "3B", "location": {"x": 99, "y": 191}, "error": false}]
      },
      "compactorAttributes": {"stream": "main"}
    }
  ],
  "defensive_spray_charts": null
}
```

## Known Limitations

- Must be called once per player to build a full team box score. For a 12-player roster, that is 12 calls. Use `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` instead for full game box scores (both teams in one call).
- Records are NOT in chronological order -- always sort by `game_date` before analysis.
- `offense` and `defense` sections are conditionally present. Parse defensively.
- Spray chart coordinate scale and origin are unconfirmed. Cannot map to real field dimensions yet.
- `SB`, `CS`, `PIK` may appear only in `cumulative_stats.offense`, not in `player_stats.offense`.

**Discovered:** 2026-03-04. **Schema fully documented:** 2026-03-04.
