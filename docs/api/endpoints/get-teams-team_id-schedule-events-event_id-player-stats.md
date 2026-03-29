---
method: GET
path: /teams/{team_id}/schedule/events/{event_id}/player-stats
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 200. Three data sections in one call (both teams' players when called with
      the owning team's UUID; only that team's players otherwise). No game_stream_id
      resolution needed. Confirmed 2026-03-05.
  mobile:
    status: observed
    notes: >
      55 hits, all HTTP 200. Observed 2026-03-09 (session 063531). All calls used
      opponent progenitor_team_id (14fd6cb6) as the path team_id, CONFIRMING this
      endpoint works with opponent team IDs from search. See caveats update.
      All 206 calls in session 034739 used Accept: application/vnd.gc.com.player_game_stats+json; version=0.2.0. Response structure identical to web profile.
accept: "application/json, text/plain, */*"
accept_mobile: "application/vnd.gc.com.player_game_stats+json; version=0.2.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/player-stats-sample.json
raw_sample_size: "~106 KB (25 players, full season cumulative stats)"
discovered: "2026-03-05"
last_confirmed: "2026-03-26"
tags: [games, player, stats, spray-chart]
caveats:
  - >
    NON-VENDOR ACCEPT HEADER: Uses "application/json, text/plain, */*" rather than
    a vendor-typed application/vnd.gc.com.*+json Accept header. This is unusual for
    this API -- all other authenticated endpoints use vendor-typed Accept headers.
  - >
    NO PLAYER NAMES: Player UUIDs are the only identifier in the response. A join to
    GET /teams/{team_id}/players or the boxscore endpoint is needed to resolve names
    and jersey numbers.
  - >
    NO BATTING ORDER: The "players" dict is keyed by UUID with no ordering. Use the
    boxscore endpoint if batting order is required.
  - >
    OPPONENT CUMULATIVE STATS ARE SINGLE-GAME: Opponents' cumulative_player_stats.GP
    = 1; their season history is not tracked across sessions via this endpoint.
  - >
    IP IN FRACTIONAL THIRDS: Innings pitched is a float where 1 1/3 IP = 1.333...
    (not 1.1). Convert with: full_innings + (fraction * 3) / 10 for display.
  - >
    TEAM_ID SCOPE CONFIRMED BROAD (2026-03-09): This endpoint works with opponent
    team IDs (progenitor_team_id), not just teams the authenticated user manages. In
    session 063531, 55 calls were made using an opponent progenitor_team_id, all
    returning HTTP 200. This means the mobile app (and likely the web app) can fetch
    any team's per-game player-stats using that team's progenitor_team_id. The
    authenticated user's team membership is NOT required for access.
  - >
    ASYMMETRIC TEAM SCOPE (2026-03-29): This endpoint is team-scoped and asymmetric.
    When called with the owning team's UUID (the team whose schedule contains the game),
    the response includes both teams' players. When called with a participant's UUID
    (a team that played but does not own the schedule entry), only that team's players
    are returned. An unrelated team's UUID returns 404. Earlier documentation stated
    "both teams" unconditionally -- this was incorrect.
  - >
    PLAY RESULT ENUM COMPLETENESS (2026-03-26): Mobile data (session 034739) exposes
    additional playResult values not in the original web capture: other_out,
    offensive_interference, sacrifice_bunt_error, sacrifice_fly_error. Full observed
    set: single, double, triple, home_run, batter_out, batter_out_advance_runners,
    fielders_choice, error, sac_fly, dropped_third_strike, other_out,
    offensive_interference, sacrifice_bunt_error, sacrifice_fly_error. Treat as
    open enum -- additional values may exist.
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule
    reason: Source of event_id values used as path parameter here
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Complementary -- has player names, batting order, and position data. Lacks cumulative stats and spray charts.
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Pitch-by-pitch data for the same game. stream_id returned in this response body.
  - path: /teams/{team_id}/players
    reason: Player name/jersey join -- needed to resolve UUID keys in this response to display names
---

# GET /teams/{team_id}/schedule/events/{event_id}/player-stats

**Status:** CONFIRMED LIVE -- 200 OK. Three data sections (both teams' players when called with the owning team's UUID; only that team's players otherwise). Last verified: 2026-03-26 (mobile session 034739).

Returns per-player stats for a specific game event. Returns three sections: `player_stats` (this-game per-player stats), `cumulative_player_stats` (season-to-date for own-team players; single-game for opponent players), and `spray_chart_data` (ball-in-play x/y coordinates). When called with the owning team's UUID (the team whose schedule contains the game), both own-team and opponent players are included in the same response. When called with a participant's UUID, only that team's players are returned. All players are keyed by player UUID.

This is potentially the most efficient single API call for comprehensive stat ingestion:
- Per-game batting and pitching lines for both teams
- Cumulative season stats for own-team players (eliminates separate season-stats calls)
- Spray chart data for defensive positioning analysis
- `stream_id` returned inline -- no separate ID resolution needed for plays/boxscore

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule/events/{event_id}/player-stats
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID. Works with own teams AND opponent `progenitor_team_id` values (confirmed 2026-03-09). |
| `event_id` | UUID | Event UUID from the schedule (`GET /teams/{team_id}/schedule` event `id` field). |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/json, text/plain, */*
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Note:** Web Accept header is `application/json, text/plain, */*` -- NOT a vendor-typed `application/vnd.gc.com.*` header. This is unusual for this API.

## Headers (Mobile Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.player_game_stats+json; version=0.2.0
User-Agent: {MOBILE_USER_AGENT}
```

**Note:** Mobile profile uses a standard vendor-typed Accept header (`application/vnd.gc.com.player_game_stats+json; version=0.2.0`). Response structure is identical to the web profile. Confirmed across 206 calls in session 034739 (2026-03-26).

## Response

Top-level JSON object with 6 fields.

| Field | Type | Description |
|-------|------|-------------|
| `stream_id` | UUID | The `game_stream_id` for this game -- same ID used in `/boxscore` and `/plays` endpoints. Returned inline so no separate lookup is needed. |
| `team_id` | UUID | Matches the path parameter `team_id` |
| `event_id` | UUID | Matches the path parameter `event_id` |
| `player_stats` | object | Per-game stats for THIS specific game |
| `cumulative_player_stats` | object | Season-to-date cumulative stats (own team) or single-game (opponent) |
| `spray_chart_data` | object | Ball-in-play coordinate data for this game |

### `player_stats` and `cumulative_player_stats` Structure

Both objects share the same structure:

```json
{
  "stats": {
    "general": {"GP": 1},
    "offense": {"<stat_key>": <number>, ...},
    "defense": {"<stat_key>": <number>, ...}
  },
  "players": {
    "<player_uuid>": {
      "stats": {
        "general": {"GP": 1},
        "offense": {"<stat_key>": <number>, ...},
        "defense": {"<stat_key>": <number>, ...}
      }
    }
  }
}
```

Not every player has all three stat groups:
- Batting-only players: `offense` + `general`, no `defense`
- Pitching/fielding-only players: `defense` + `general`, no `offense`
- Both roles: all three groups

### Key Per-Game Offense Stats (`player_stats.players[uuid].stats.offense`)

| Field | Type | Description |
|-------|------|-------------|
| `AB` | int | At-bats |
| `H` | int | Hits |
| `BB` | int | Walks |
| `SO` | int | Strikeouts |
| `RBI` | int | Runs batted in |
| `R` | int | Runs scored |
| `1B` | int | Singles |
| `2B` | int | Doubles |
| `3B` | int | Triples |
| `HR` | int | Home runs |
| `HBP` | int | Hit by pitch |
| `SB` | int | Stolen bases |
| `CS` | int | Caught stealing |
| `PA` | int | Plate appearances |
| `TB` | int | Total bases |
| `AVG` | float | Batting average |
| `OBP` | float | On-base percentage |
| `SLG` | float | Slugging percentage |
| `OPS` | float | OBP + SLG |

Approximately 83 offense keys total. See `docs/gamechanger-stat-glossary.md` for the full list.

### Key Per-Game Defense/Pitching Stats (`player_stats.players[uuid].stats.defense`)

| Field | Type | Description |
|-------|------|-------------|
| `IP` | float | Innings pitched (fractional thirds: 1 1/3 IP = 1.333) |
| `ERA` | float | Earned run average |
| `SO` | int | Strikeouts |
| `BB` | int | Walks |
| `H` | int | Hits allowed |
| `ER` | int | Earned runs |
| `R` | int | Runs allowed |
| `BF` | int | Batters faced |
| `WP` | int | Wild pitches |
| `HBP` | int | Hit batters |
| `BK` | int | Balks |
| `HR` | int | Home runs allowed |

### Key Cumulative Defense/Pitching Stats (`cumulative_player_stats.players[uuid].stats.defense`)

Approximately 149 keys total. Additional cumulative-only fields:

| Field | Type | Description |
|-------|------|-------------|
| `WHIP` | float | Season WHIP |
| `FIP` | float | Fielding Independent Pitching |
| `K/BF` | float | Strikeout rate per batter faced |
| `K/BB` | float | Strikeout-to-walk ratio |
| `K/G` | float | Strikeouts per game (9 innings) |
| `BB/INN` | float | Walks per inning |
| `#P` | int | Cumulative pitch count |
| `TS` | int | Total strikes thrown |
| `GS` | int | Games started |

### Distinguishing Own-Team vs. Opponent Players

No explicit team flag per player. Use `cumulative_player_stats.players[uuid].stats.general.GP`:
- **Own team:** `GP` = large number (60-90+ for a full travel ball season)
- **Opponent:** `GP` = 1 (no cross-game tracking for opponents)

### `spray_chart_data` Structure

```json
{
  "offense": {
    "<player_uuid>": [
      {
        "code": "ball_in_play",
        "id": "<event_uuid>",
        "compactorAttributes": {"stream": "main"},
        "attributes": {
          "playResult": "single",
          "playType": "hard_ground_ball",
          "defenders": [
            {
              "error": false,
              "position": "CF",
              "location": {"x": 129.06, "y": 79.08}
            }
          ]
        },
        "createdAt": 1752607496602
      }
    ]
  },
  "defense": {
    "<player_uuid>": [...]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Always `"ball_in_play"` |
| `attributes.playResult` | string | Open enum. Confirmed values: `single`, `double`, `triple`, `home_run`, `batter_out`, `batter_out_advance_runners`, `fielders_choice`, `error`, `sac_fly`, `dropped_third_strike`, `other_out`, `offensive_interference`, `sacrifice_bunt_error`, `sacrifice_fly_error` |
| `attributes.playType` | string | `"hard_ground_ball"`, `"ground_ball"`, `"line_drive"`, `"fly_ball"`, `"bunt"`, ... |
| `attributes.defenders` | array | Fielders involved: each has `error` (bool), `position` (string), `location.x` (float), `location.y` (float) |
| `createdAt` | int | Unix millisecond timestamp |

`offense` dict keys are batting players; `defense` dict keys are fielding players involved in those same plays.

## Comparison to Boxscore Endpoint

| Dimension | This endpoint | `GET /game-stream-processing/{game_stream_id}/boxscore` |
|-----------|---------------|--------------------------------------------------------|
| **ID required** | `team_id` + `event_id` (from schedule directly) | `game_stream_id` (requires prior lookup) |
| **Stat richness** | ~83 offense + ~149 defense fields + cumulative | 6 batting + 6 pitching main stats + ~10 sparse extras |
| **Spray charts** | Yes -- x/y coordinates, play type, play result | No |
| **Cumulative season stats** | Yes -- own team has full season totals | No -- game stats only |
| **Player names** | No -- UUID keys only (join needed) | Yes -- first_name, last_name, number included |
| **Batting order** | No -- dict keyed by UUID (unordered) | Yes -- array order = batting order |
| **Position data** | No explicit position field | Yes -- player_text (e.g., "(CF)") |
| **Both teams** | Yes -- when called with the owning team's UUID; only that team's data otherwise (asymmetric, verified 2026-03-29) | Yes |
| **Response size** | ~106 KB | Smaller (~13 KB) |

**Recommendation:** Use this endpoint for full per-player stat ingestion (game and cumulative). Use boxscore when batting order, positions, or player names are required without a separate join.

## Example Response (Redacted)

```json
{
  "stream_id": "c05a5413-d250-4f28-bd92-efbe67bac348",
  "team_id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4",
  "event_id": "1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6",
  "player_stats": {
    "players": {
      "<own_player_uuid>": {
        "stats": {
          "general": {"GP": 1},
          "offense": {"AB": 1, "H": 1, "BB": 0, "SO": 0, "RBI": 0, "R": 1},
          "defense": {"IP": 1.333, "ERA": 0.0, "SO": 3, "BB": 1}
        }
      }
    },
    "stats": {"general": {"GP": 1}, "offense": {"AB": 30, "H": 10}, "defense": {"IP": 5.0}}
  },
  "cumulative_player_stats": {
    "players": {
      "<own_player_uuid>": {
        "stats": {
          "general": {"GP": 83},
          "offense": {"AB": 160, "H": 41, "BB": 43, "SO": 37, "OBP": 0.4251}
        }
      },
      "<opponent_player_uuid>": {
        "stats": {
          "general": {"GP": 1},
          "offense": {"AB": 2, "H": 1, "BB": 0}
        }
      }
    }
  },
  "spray_chart_data": {
    "offense": {
      "<player_uuid>": [
        {
          "code": "ball_in_play",
          "id": "11E72536-DE41-43AB-A90F-56B0606BFA7C",
          "compactorAttributes": {"stream": "main"},
          "attributes": {
            "playResult": "single",
            "playType": "hard_ground_ball",
            "defenders": [{"error": false, "position": "CF", "location": {"x": 129.06, "y": 79.08}}]
          },
          "createdAt": 1752607496602
        }
      ]
    },
    "defense": {}
  }
}
```

## Known Limitations

- **No player names:** Player UUIDs are the only identifier. Join to `/teams/{team_id}/players` or boxscore for display names.
- **No batting order:** `players` dict is keyed by UUID with no ordering.
- **Opponent cumulative stats are single-game:** Opponents' GP = 1; their season history not available.
- **IP in fractional thirds:** 1 1/3 IP = 1.333 (not 1.1). Convert for display.
- **team_id scope:** Works with opponent `progenitor_team_id` values -- NOT restricted to teams the authenticated user manages. Confirmed in session 063531 (2026-03-09) with 55 successful calls using an opponent team ID. Earlier assumption that this required own-team membership was WRONG.
- **playResult enum is open:** Mobile traffic (session 034739, 2026-03-26) surfaced additional values beyond web capture: `other_out`, `offensive_interference`, `sacrifice_bunt_error`, `sacrifice_fly_error`. Always parse defensively; do not use an exhaustive enum.

**Discovered:** 2026-03-05. **Last confirmed:** 2026-03-26 (mobile session 034739, 206 calls).
