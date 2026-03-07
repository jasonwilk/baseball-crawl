---
method: GET
path: /bats-starting-lineups/latest/{team_id}
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
response_sample: data/raw/bats-starting-lineups-latest-sample.json
raw_sample_size: "9-player lineup (1 game)"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [team, lineup]
caveats:
  - >
    latest_lineup WRAPPER: Response wraps the lineup object in {"latest_lineup": {...}}.
    Differs from GET /bats-starting-lineups/{event_id} which returns the lineup object directly.
related_schemas: []
see_also:
  - path: /bats-starting-lineups/{event_id}
    reason: Lineup for a specific game event (same schema, no wrapper, may return 403 for away games)
  - path: /teams/{team_id}/lineup-recommendation
    reason: GC algorithm recommendation -- compare to coach's actual lineup here
---

# GET /bats-starting-lineups/latest/{team_id}

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the most recently entered starting lineup for a team. Contains the actual batting order and fielding assignments as entered by the coach -- not GC's algorithm recommendation.

```
GET https://api.team-manager.gc.com/bats-starting-lineups/latest/{team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

Single JSON object with `latest_lineup` wrapper.

| Field | Type | Description |
|-------|------|-------------|
| `latest_lineup` | object | The lineup object |
| `latest_lineup.id` | UUID | Unique ID for this lineup record |
| `latest_lineup.dh` | UUID or null | DH player UUID (null when not using DH) |
| `latest_lineup.dh_batting_for` | UUID or null | UUID of the player the DH bats for (null when not using DH) |
| `latest_lineup.creator` | UUID | User UUID who created this lineup (**PII -- redact in stored files**) |
| `latest_lineup.entries` | array | Lineup entries. **Array order = batting order.** |
| `latest_lineup.entries[].player_id` | UUID | Player UUID |
| `latest_lineup.entries[].fielding_position` | string | Field position (e.g., `"CF"`, `"P"`, `"RF"`, etc.) |

## Example Response

```json
{
  "latest_lineup": {
    "id": "65b1ba56-cbef-41cf-bb2f-e8be239c2bf1",
    "dh": null,
    "dh_batting_for": null,
    "creator": "e07b2d06-REDACTED",
    "entries": [
      {"player_id": "d5645a1b-REDACTED", "fielding_position": "CF"},
      {"player_id": "11ceb5ee-REDACTED", "fielding_position": "P"},
      {"player_id": "879a99fd-REDACTED", "fielding_position": "RF"},
      {"player_id": "e8534cc3-REDACTED", "fielding_position": "LF"},
      {"player_id": "8119312c-REDACTED", "fielding_position": "1B"},
      {"player_id": "3050e40b-REDACTED", "fielding_position": "3B"},
      {"player_id": "e9a04fc5-REDACTED", "fielding_position": "C"},
      {"player_id": "77c74470-REDACTED", "fielding_position": "2B"},
      {"player_id": "996c48ba-REDACTED", "fielding_position": "SS"}
    ]
  }
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
