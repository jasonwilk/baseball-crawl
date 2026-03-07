---
method: GET
path: /player-attributes/{player_id}/bats
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [player, stats]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents/players
    reason: Same handedness fields inline for all opponents in one bulk call -- prefer for opponent scouting
  - path: /teams/{team_id}/players
    reason: Source of player_id values for own-team players
---

# GET /player-attributes/{player_id}/bats

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns batting/throwing handedness attributes for a single player.

**Note:** For bulk opponent handedness, prefer `GET /teams/{team_id}/opponents/players` which returns the same fields inline for all opponents in one call. Use this endpoint for individual player lookups or for own-team players.

```
GET https://api.team-manager.gc.com/player-attributes/{player_id}/bats
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `player_id` | UUID | Player UUID (from `GET /teams/{team_id}/players`) |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | UUID | The player UUID (matches path parameter) |
| `throwing_hand` | string | `"right"` or `"left"` |
| `batting_side` | string | `"right"`, `"left"`, or `"switch"` |

## Example Response

```json
{
  "player_id": "879a99fd-ef90-4cce-9794-4ec0f78224bb",
  "throwing_hand": "right",
  "batting_side": "left"
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
