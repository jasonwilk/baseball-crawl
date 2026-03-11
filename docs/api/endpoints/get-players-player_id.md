---
method: GET
path: /players/{player_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. Full schema observed.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.player+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: "1 record"
discovered: "2026-03-11"
last_confirmed: null
tags: [player, team]
caveats:
  - >
    MINIMAL SCHEMA: Observed response contains only id, team_id, status, first_name,
    last_name, number, and person_id. Does NOT include batting/throwing handedness --
    use GET /player-attributes/{player_id}/bats for handedness.
see_also:
  - path: /teams/{team_id}/players
    reason: Returns all players for a team (bulk alternative to per-player fetch)
  - path: /player-attributes/{player_id}/bats
    reason: Batting side and throwing hand for a player
  - path: /players/{player_id}/profile-photo
    reason: Player profile photo URL (returns 404 when not set)
  - path: /athlete-profile/{athlete_profile_id}/players
    reason: Cross-team career view of a player's identity
---

# GET /players/{player_id}

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns individual player metadata for a specific player UUID. Returns the per-team player record (not the cross-team athlete profile). The response is minimal -- it does not include handedness or stats.

```
GET https://api.team-manager.gc.com/players/{player_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `player_id` | UUID | The player UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.player+json; version=0.1.0
```

## Response

**HTTP 200.** Single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Player UUID (same as path param) |
| `team_id` | UUID | The team this player record belongs to |
| `status` | string | Player status. Observed: `"active"`. |
| `first_name` | string | Player first name |
| `last_name` | string | Player last name |
| `number` | string | Jersey number as string |
| `person_id` | UUID | Person UUID (may be same as `id` for players who also have user accounts) |

## Example Response

```json
{
  "id": "00000000-REDACTED",
  "team_id": "00000000-REDACTED",
  "status": "active",
  "first_name": "Player",
  "last_name": "One",
  "number": "28",
  "person_id": "00000000-REDACTED"
}
```

**Note:** `person_id` equaling `id` suggests this player has a user account associated with their player record.

**Coaching relevance: LOW.** Most player data is more efficiently retrieved via `/teams/{team_id}/players` (bulk). Use this endpoint only when a specific player UUID is known and a quick identity lookup is needed.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
