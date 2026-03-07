---
method: GET
path: /teams/{team_id}/season-stats
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Complete batting/pitching/fielding field tables confirmed.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.team_season_stats+json; version=0.2.0"
gc_user_action: "data_loading:team_stats"
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [team, player, stats, season]
related_schemas: []
see_also:
  - path: /teams/{team_id}/players
    reason: Get player UUIDs to cross-reference player keys in this response (players keyed by UUID, no names)
  - path: /teams/{team_id}/players/{player_id}/stats
    reason: Per-game per-player stats (season-stats gives aggregates; player-stats gives game-by-game)
  - path: /teams/{team_id}/schedule/events/{event_id}/player-stats
    reason: Both teams' player stats per game in one call (includes spray charts)
  - path: docs/gamechanger-stat-glossary.md
    reason: Authoritative definitions for all stat abbreviations in this response
---

# GET /teams/{team_id}/season-stats

**Status:** CONFIRMED LIVE -- 200 OK. Full schema documented including all batting, pitching, and fielding fields. Last verified: 2026-03-04.

Returns full season batting, pitching, and fielding aggregate statistics for every player on a team. Also includes team-level aggregates and hot/cold streak data. Players are keyed by UUID -- cross-reference with `GET /teams/{team_id}/players` to get player names.

For authoritative stat abbreviation definitions see [`docs/gamechanger-stat-glossary.md`](../../gamechanger-stat-glossary.md).

```
GET https://api.team-manager.gc.com/teams/{team_id}/season-stats
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_season_stats+json; version=0.2.0
gc-user-action: data_loading:team_stats
gc-user-action-id: {UUID}
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Response

Single JSON object (not an array).

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID (same as `team_id`) |
| `team_id` | UUID | Team UUID |
| `stats_data.players` | object | Per-player stats keyed by player UUID |
| `stats_data.streaks` | object | Hot/cold streak data keyed by player UUID. Only players on an active streak are included. |
| `stats_data.stats` | object | Team aggregate stats (same structure as a player's stats) |

### Response Structure

```json
{
  "id": "<team_uuid>",
  "team_id": "<team_uuid>",
  "stats_data": {
    "players": {
      "<player_uuid>": {
        "stats": {
          "offense": { ... },
          "defense": { ... },
          "general": { "GP": 84 }
        }
      }
    },
    "streaks": {
      "<player_uuid>": {
        "streak_H": {
          "offense": { ... },
          "defense": { ... },
          "general": { "GP": 2 }
        }
      }
    },
    "stats": {
      "offense": { ... },
      "defense": { ... },
      "general": { "GP": 92 }
    }
  }
}
```

### Offense (Batting) Fields

These fields appear in `stats.offense` for both individual players and the team aggregate.

| Field | Type | Description |
|-------|------|-------------|
| `AB` | int | At bats |
| `PA` | int | Plate appearances |
| `H` | int | Hits |
| `1B` | int | Singles |
| `2B` | int | Doubles |
| `3B` | int | Triples |
| `HR` | int | Home runs |
| `TB` | int | Total bases |
| `XBH` | int | Extra base hits |
| `BB` | int | Walks |
| `SO` | int | Strikeouts |
| `SOL` | int | Strikeouts looking |
| `HBP` | int | Hit by pitch |
| `SHB` | int | Sacrifice bunts |
| `SHF` | int | Sacrifice flies |
| `GIDP` | int | Grounded into double play |
| `ROE` | int | Reached on error |
| `FC` | int | Fielder's choice |
| `CI` | int | Catcher's interference |
| `PIK` | int | Picked off |
| `R` | int | Runs scored |
| `RBI` | int | Runs batted in |
| `GSHR` | int | Grand slam home runs |
| `2OUTRBI` | int | RBI with 2 outs |
| `SB` | int | Stolen bases |
| `CS` | int | Caught stealing |
| `LOB` | int | Left on base |
| `3OUTLOB` | int | Left on base with 3 outs |
| `OB` | int | Times on base |
| `AVG` | float | Batting average |
| `OBP` | float | On-base percentage |
| `SLG` | float | Slugging percentage |
| `OPS` | float | On-base plus slugging |
| `BABIP` | float | Batting average on balls in play |
| `BA/RISP` | float | Batting average with runners in scoring position |
| `HRISP` | int | Hits with RISP |
| `ABRISP` | int | At bats with RISP |
| `SB%` | float | Stolen base success rate |
| `AB/HR` | float | At bats per home run. **Present only when HR > 0** |
| `QAB` | int | Quality at bats |
| `QAB%` | float | Quality at bat percentage |
| `BB/K` | float | Walk to strikeout ratio |
| `PS` | int | Pitches seen |
| `PS/PA` | float | Pitches per plate appearance |
| `PA/BB` | float | Plate appearances per walk |
| `SW` | int | Swings |
| `SW%` | float | Swing percentage |
| `SM` | int | Swinging misses |
| `SM%` | float | Swinging miss percentage |
| `C%` | float | Contact percentage |
| `GB` | int | Ground balls |
| `GB%` | float | Ground ball percentage |
| `FLB` | int | Fly balls |
| `FLB%` | float | Fly ball percentage |
| `HARD` | int | Hard contact count |
| `WEAK` | int | Weak contact count |
| `FULL` | int | Full count plate appearances |
| `2STRIKES` | int | Plate appearances reaching a 2-strike count |
| `2S+3` | int | Plate appearances where a 2-strike count went 3+ pitches |
| `2S+3%` | float | Percentage form of 2S+3 |
| `6+` | int | Plate appearances lasting 6+ pitches |
| `6+%` | float | Percentage of PAs going 6+ pitches |
| `INP` | int | In play count (balls put in play) |
| `LND` | int | Line drives |
| `LND%` | float | Line drive percentage |
| `LOBB` | int | Leadoff base on balls (times batter drew a leadoff walk) |
| `GP` | int | Games played |
| `TS` | int | Total swings |

### Defense (Pitching) Fields

These fields in `stats.defense` reflect pitching performance.

| Field | Type | Description |
|-------|------|-------------|
| `ERA` | float | Earned run average |
| `IP` | float | Innings pitched |
| `ER` | int | Earned runs |
| `H` | int | Hits allowed |
| `BB` | int | Walks allowed |
| `SO` | int | Strikeouts |
| `HR` | int | Home runs allowed |
| `BK` | int | Balks |
| `WP` | int | Wild pitches |
| `HBP` | int | Hit batters |
| `GS` | int | Games started (pitching) |
| `SVO` | int | Save opportunities |
| `WHIP` | float | Walks plus hits per inning pitched |
| `FIP` | float | Fielding independent pitching |
| `BAA` | float | Batting average against |
| `K/G` | float | Strikeouts per 9 innings |
| `K/BB` | float | Strikeout to walk ratio |
| `K/BF` | float | Strikeouts per batter faced |
| `BB/INN` | float | Walks per inning |
| `BF` | int | Batters faced |
| `GO` | int | Ground outs recorded |
| `AO` | int | Air outs recorded |
| `GO/AO` | float | Ground out to air out ratio |
| `P/BF` | float | Pitches per batter faced |
| `P/IP` | float | Pitches per inning pitched |
| `#P` | int | Total pitches thrown |
| `S%` | float | Strike percentage |
| `LOO` | int | Opponent runners left on base |
| `0BBINN` | int | Innings without a walk |
| `123INN` | int | 1-2-3 innings retired |
| `FPS` | int | First pitch strikes thrown |
| `FPS%` | float | First pitch strike percentage |
| `LBFPN` | int | Last batter faced pitch number (cumulative pitch count at last batter) |
| `SB` | int | Stolen bases allowed (pitcher) |
| `CS` | int | Caught stealing charged to pitcher |
| `GP:P` | int | Games played as pitcher |

### Defense (Fielding) Fields

Fielding stats co-reside in `stats.defense` alongside pitching stats.

| Field | Type | Description |
|-------|------|-------------|
| `PO` | int | Putouts |
| `A` | int | Assists |
| `E` | int | Errors |
| `TC` | int | Total chances |
| `FPCT` | float | Fielding percentage |
| `DP` | int | Double plays |
| `GP:F` | int | Games played in field positions (non-pitcher) |
| `GP:C` | int | Games played as catcher |
| `outs` | int | Total outs recorded across all positions |
| `outs-P` | int | Outs recorded while pitching |
| `outs-1B` | int | Outs at 1B |
| `outs-2B` | int | Outs at 2B |
| `outs-3B` | int | Outs at 3B |
| `outs-SS` | int | Outs at SS |
| `outs-LF` | int | Outs at LF |
| `outs-CF` | int | Outs at CF |
| `outs-RF` | int | Outs at RF |
| `outs-C` | int | Outs while catching |
| `IP:1B` | float | Innings played at 1B (fractional thirds) |
| `IP:2B` | float | Innings played at 2B |
| `IP:3B` | float | Innings played at 3B |
| `IP:SS` | float | Innings played at SS |
| `IP:LF` | float | Innings played at LF |
| `IP:CF` | float | Innings played at CF |
| `IP:RF` | float | Innings played at RF |
| `IP:F` | float | Total innings in field positions |
| `IC:C` | float | Innings caught (catcher) |
| `CI:C` | int | Catcher's interference committed as catcher |
| `PB:C` | int | Passed balls (catcher) |
| `SB:C` | int | Stolen bases allowed (catcher) |
| `CS:C` | int | Caught stealing (catcher) |
| `SB:C%` | float | Opponent stolen base percentage (catcher) |
| `SBATT:C` | int | Stolen base attempts against catcher |

**Note on `IP:POS` values:** These represent innings played at a position as fractional thirds. A value of `218.67` = 218 full innings + 2 outs.

### Streaks Object

```json
"streaks": {
  "<player_uuid>": {
    "streak_H": {
      "offense": { ... },
      "defense": { ... },
      "general": { "GP": 2 }
    }
  }
}
```

Key format: `streak_H` (hot streak). A cold streak key `streak_C` is inferred but not yet observed. `general.GP` in streaks = number of games in the current streak.

## Known Limitations

- Player names are NOT in this response. Cross-reference player UUIDs with `GET /teams/{team_id}/players` for names.
- `AB/HR` field is only present when `HR > 0`. Parse defensively.
- The `defense` stats section contains BOTH pitching and fielding fields co-mingled. Use `GP:P` to detect pitching appearances.
- Not all fields appear for all players (e.g., catcher fields only appear for catchers). Parse all fields defensively.

**Discovered:** 2026-03-04. **Schema fully documented:** 2026-03-04.
