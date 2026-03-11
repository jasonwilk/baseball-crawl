---
method: GET
path: /me/associated-players
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 13 player records across 13 teams. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.associated_players+json; version=1.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/me-associated-players-sample.json
raw_sample_size: "13 player records across 13 teams"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [me, player]
caveats: []
related_schemas: []
see_also:
  - path: /me/teams
    reason: Team list -- team_id in player records links back to these teams
  - path: /me/archived-teams
    reason: Historical teams -- some player records span archived teams
---

# GET /me/associated-players

**Status:** CONFIRMED LIVE -- 200 OK. 13 player records across 13 teams. Last verified: 2026-03-07.

Returns all player records associated with the authenticated user across all teams and seasons. Primary endpoint for longitudinal player tracking -- seeing a player's UUID on each team they've played for.

**Coaching relevance: HIGH.** Enables stat aggregation across seasons for tracked players.

```
GET https://api.team-manager.gc.com/me/associated-players
```

## Response

Single JSON object with 3 top-level keys.

| Field | Type | Description |
|-------|------|-------------|
| `teams` | object | Map of team UUIDs to team metadata. 13 teams observed. |
| `teams.<uuid>.name` | string | Team display name |
| `teams.<uuid>.sport` | string | Sport |
| `players` | object | Map of player UUIDs to player identity + team reference. 13 players observed (one per team). |
| `players.<player_uuid>.first_name` | string | Player first name |
| `players.<player_uuid>.last_name` | string | Player last name |
| `players.<player_uuid>.team_id` | UUID | The team this player record belongs to |
| `associations` | array | Array of player-user relationship objects |
| `associations[].relation` | string | Relationship type. Observed: `"primary"` (primary family/guardian) |
| `associations[].player_id` | UUID | Player UUID (links to `players` map keys) |

## Example (redacted)

```json
{
  "teams": {
    "72bb77d8-REDACTED": {"name": "Lincoln Rebels 14U", "sport": "baseball"}
  },
  "players": {
    "9e5faf37-REDACTED": {
      "first_name": "Reid",
      "last_name": "Wilkinson",
      "team_id": "103e1cb5-REDACTED"
    }
  },
  "associations": [
    {"relation": "primary", "player_id": "9e5faf37-REDACTED"}
  ]
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
