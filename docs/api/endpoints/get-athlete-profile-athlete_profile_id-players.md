---
method: GET
path: /athlete-profile/{athlete_profile_id}/players
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. Multiple records observed spanning seasons 2019-2025.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.athlete_profile_players:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "9 records spanning 2019-2025"
discovered: "2026-03-11"
last_confirmed: null
tags: [player, team]
see_also:
  - path: /athlete-profile/{athlete_profile_id}
    reason: Profile metadata (name, handle, graduation year, positions)
  - path: /athlete-profile/{athlete_profile_id}/career-stats
    reason: Full career statistics across all teams
  - path: /athlete-profile/{athlete_profile_id}/career-stats-association
    reason: Lightweight player_id list only (no team metadata)
---

# GET /athlete-profile/{athlete_profile_id}/players

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns the list of per-team player identity records linked to an athlete profile. Each record contains team name, season, jersey number, games played, and avatar URL. This is the "roster card" view of a player's career -- richer than the ID-only `career-stats-association` endpoint but lighter than the full `career-stats` endpoint.

```
GET https://api.team-manager.gc.com/athlete-profile/{athlete_profile_id}/players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `athlete_profile_id` | UUID | The athlete profile UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.athlete_profile_players:list+json; version=0.0.0
```

## Response

**HTTP 200.** JSON array of player identity records.

| Field | Type | Description |
|-------|------|-------------|
| `[].athlete_profile_id` | UUID | The athlete profile UUID (same as path param) |
| `[].player_id` | UUID | Per-team player UUID |
| `[].player_display_name` | string | Full player name |
| `[].team_id` | UUID | Team UUID |
| `[].team_name` | string | Team display name |
| `[].team_season_name` | string | Season label (e.g., `"spring 2019"`) |
| `[].team_record` | string | Team's win-loss record (e.g., `"16-34"`) |
| `[].jersey_number` | string | Player's jersey number as string |
| `[].games_played` | integer | Number of games played in this team season |
| `[].avatar_url` | string or null | Player profile photo URL (null when not set) |
| `[].is_archived` | boolean | Whether this team season is archived |

## Example Response

```json
[
  {
    "athlete_profile_id": "00000000-REDACTED",
    "player_id": "00000000-REDACTED",
    "player_display_name": "Player One",
    "team_id": "00000000-REDACTED",
    "team_name": "Example Team 8U",
    "team_season_name": "spring 2019",
    "team_record": "12-8",
    "jersey_number": "28",
    "games_played": 18,
    "avatar_url": null,
    "is_archived": true
  },
  {
    "athlete_profile_id": "00000000-REDACTED",
    "player_id": "00000000-REDACTED",
    "player_display_name": "Player One",
    "team_id": "00000000-REDACTED",
    "team_name": "Example Team 14U",
    "team_season_name": "summer 2025",
    "team_record": "14-6",
    "jersey_number": "28",
    "games_played": 20,
    "avatar_url": null,
    "is_archived": false
  }
]
```

**Note:** `is_archived: false` identifies current-season team memberships.

**Coaching relevance: HIGH.** Best endpoint for building a career timeline view -- maps a player's identity across all team seasons with roster details. Use in conjunction with `career-stats` for the full longitudinal picture.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
