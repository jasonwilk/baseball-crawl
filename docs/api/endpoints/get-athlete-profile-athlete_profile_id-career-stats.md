---
method: GET
path: /athlete-profile/{athlete_profile_id}/career-stats
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. 31KB payload observed spanning multiple seasons.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.athlete_profile_career_stats+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: "9 player_stats entries across 5+ seasons, ~31KB"
discovered: "2026-03-11"
last_confirmed: null
tags: [player, stats, season]
caveats:
  - >
    LARGE PAYLOAD: Observed ~31KB for a single athlete profile with 9 team seasons.
    Payload grows with career length. Use only when full career stats are needed.
  - >
    STAT FIELD NAMES: The stats object uses GameChanger internal abbreviations
    (AB, H, RBI, etc.) which map to UI labels documented in docs/gamechanger-stat-glossary.md.
see_also:
  - path: /athlete-profile/{athlete_profile_id}
    reason: Profile metadata (name, handle, graduation year, positions)
  - path: /athlete-profile/{athlete_profile_id}/career-stats-association
    reason: Player ID mapping across teams (lighter weight than career-stats if only IDs are needed)
  - path: /athlete-profile/{athlete_profile_id}/players
    reason: Team-level player identity records linked to this athlete profile
  - path: /teams/{team_id}/season-stats
    reason: Season aggregate stats per team (alternative source for single-season stats)
---

# GET /athlete-profile/{athlete_profile_id}/career-stats

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data. ~31KB payload.

Returns cross-team career statistics for an athlete profile. Each entry in `player_stats_data` represents one team season, containing both the team metadata and the full stat block for that season. This is the primary endpoint for longitudinal player stat tracking across all teams and seasons.

```
GET https://api.team-manager.gc.com/athlete-profile/{athlete_profile_id}/career-stats
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `athlete_profile_id` | UUID | The athlete profile UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.athlete_profile_career_stats+json; version=0.0.0
```

## Response

**HTTP 200.** Single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `athlete_profile_id` | UUID | The athlete profile UUID |
| `player_stats_data` | array | Career stats entries, one per team season |
| `player_stats_data[].player_id` | UUID | Per-team player UUID |
| `player_stats_data[].team_id` | UUID | Team UUID for this season |
| `player_stats_data[].info` | object | Season display metadata |
| `player_stats_data[].info.season_display_name` | string | Human-readable season label (e.g., `"Spring 2021"`) |
| `player_stats_data[].info.team_display_name` | string | Team name for this season |
| `player_stats_data[].stats` | object | Full stat block -- contains `defense` (batting/fielding) key at minimum |
| `player_stats_data[].stats.defense` | object | Batting and fielding stats using GC abbreviations (AB, H, R, RBI, etc.) |

## Stat Fields (Observed in `defense` block)

The `defense` stat block uses GameChanger stat abbreviations. See `docs/gamechanger-stat-glossary.md` for full definitions.

Observed fields include: `A`, `E`, `H`, `R`, `#P`, `1B`, `2B`, `3B`, `<3`, `AB`, `AO`, `BB`, `BF`, `BK`, `CI`, `CS`, `DP`, `ER`, `FC`, `GB`, `GO`, `GS`, `HR`, `IF`, `IP`, `OS`, `PO`, `S%`, and many more.

## Example Response (truncated)

```json
{
  "athlete_profile_id": "00000000-REDACTED",
  "player_stats_data": [
    {
      "player_id": "00000000-REDACTED",
      "team_id": "00000000-REDACTED",
      "info": {
        "season_display_name": "Spring 2024",
        "team_display_name": "Example Team 14U"
      },
      "stats": {
        "defense": {
          "AB": 87,
          "H": 26,
          "R": 25,
          "2B": 1,
          "3B": 1,
          "HR": 1,
          "BB": 18,
          "IP": 21
        }
      }
    }
  ]
}
```

**Coaching relevance: HIGH.** The only single-call source for a player's full career stats across all teams and seasons. Key for multi-year player development analysis.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
