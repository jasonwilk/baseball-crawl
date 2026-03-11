---
method: GET
path: /athlete-profile/{athlete_profile_id}/career-stats-association
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. 9 player_id records observed.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.athlete_profile_career_stats_association:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "9 player_id records"
discovered: "2026-03-11"
last_confirmed: null
tags: [player, stats]
see_also:
  - path: /athlete-profile/{athlete_profile_id}/career-stats
    reason: Full career stats (uses the same player_ids this endpoint maps)
  - path: /athlete-profile/{athlete_profile_id}/players
    reason: Richer player identity records including team name, jersey number, and games_played
  - path: /me/associated-players
    reason: Alternative source for player_id list across all teams for the authenticated user
---

# GET /athlete-profile/{athlete_profile_id}/career-stats-association

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns the list of per-team player UUIDs linked to an athlete profile. This is a lightweight "ID map" -- it tells you which `player_id` values belong to this athlete across their career, without returning the full stats or team metadata.

Use this endpoint when you need the player UUID list but not the full career stat block.

```
GET https://api.team-manager.gc.com/athlete-profile/{athlete_profile_id}/career-stats-association
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `athlete_profile_id` | UUID | The athlete profile UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.athlete_profile_career_stats_association:list+json; version=0.0.0
```

## Response

**HTTP 200.** JSON array of player ID objects.

| Field | Type | Description |
|-------|------|-------------|
| `[].player_id` | UUID | Per-team player UUID linked to this athlete profile |

## Example Response

```json
[
  {"player_id": "00000000-REDACTED"},
  {"player_id": "00000000-REDACTED"},
  {"player_id": "00000000-REDACTED"}
]
```

**Note:** 9 player_id values observed for a single athlete profile spanning seasons from 2019 through 2025.

**Coaching relevance: MEDIUM.** Use for building a player UUID index for cross-team joins. Lighter-weight alternative to `/career-stats` when only IDs are needed.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
