---
method: GET
path: /teams/{team_id}/opponents/players
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: 758 records across 61 opponent teams. Full schema documented 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "758 records, 61 teams"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [team, opponent, player, bulk]
caveats:
  - >
    REMOVED PLAYERS INCLUDED: attributes.status="removed" records appear in the response.
    Filter to "active" only when building scouting rosters.
  - >
    bats CAN BE NULL: 30 of 758 records had null bats (all were "removed" status). Handle
    null bats before accessing batting_side or throwing_hand.
  - >
    batting_side CAN BE "both": Observed in addition to "left", "right", and null.
    Treat "both" as switch hitter.
  - >
    team_id IS root_team_id: The team_id field on each record is the opponent's local
    registry UUID (root_team_id), not the progenitor_team_id. Do not use for other endpoints.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents
    reason: Opponent list with progenitor_team_id and is_hidden fields
  - path: /player-attributes/{player_id}/bats
    reason: Same handedness fields but for individual players -- prefer this bulk endpoint for all opponents at once
---

# GET /teams/{team_id}/opponents/players

**Status:** CONFIRMED LIVE -- 200 OK. 758 records across 61 opponent teams. Last verified: 2026-03-07.

Returns all players from all opponent teams for the owning team in a single response. This is the most efficient way to bulk-load opponent rosters and handedness data without iterating per-opponent team.

**Coaching relevance: CRITICAL.** One call gives full opponent roster including batting/throwing handedness for all 61 opponent teams. No per-opponent iteration required. Enables pitcher-batter matchup analysis for upcoming opponents.

```
GET https://api.team-manager.gc.com/teams/{team_id}/opponents/players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | The owning team's UUID |

## Response

Bare JSON array of player records. 758 records observed for Lincoln Rebels 14U (no pagination triggered for this dataset).

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | The opponent team's local registry UUID (`root_team_id`) |
| `player_id` | UUID | The player's canonical UUID |
| `person` | object | Player identity |
| `person.id` | UUID | Same as `player_id` |
| `person.first_name` | string | First name |
| `person.last_name` | string | Last name |
| `attributes` | object | Player attributes |
| `attributes.player_number` | string | Jersey number (string, not integer) |
| `attributes.status` | string | `"active"` or `"removed"`. Removed players included in response -- filter to active. |
| `bats` | object or null | Batting/throwing handedness. `null` for removed players who never had handedness set. |
| `bats.batting_side` | string or null | `"left"`, `"right"`, `"both"` (switch hitter), or `null` if not set |
| `bats.throwing_hand` | string or null | `"left"`, `"right"`, or `null` if not set |

## Example Record

```json
{
  "team_id": "6e898958-c6e3-48c7-a97e-e281a35cfc50",
  "player_id": "68396d70-111c-4593-9df0-849051e1e96a",
  "person": {
    "id": "68396d70-111c-4593-9df0-849051e1e96a",
    "first_name": "Jackson",
    "last_name": "Dowling"
  },
  "attributes": {
    "player_number": "10",
    "status": "active"
  },
  "bats": {
    "batting_side": "right",
    "throwing_hand": "right"
  }
}
```

## Known Limitations

- `team_id` on each record is the opponent's `root_team_id`, not `progenitor_team_id`. Do not use for other team endpoints.
- No pagination observed for 758 records. Monitor `x-next-page` response header for larger datasets.
- `bats` is null for removed players -- always null-check before accessing `batting_side`.
- No `player_id` join needed for names -- names are embedded inline.

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
