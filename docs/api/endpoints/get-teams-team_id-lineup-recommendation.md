---
method: GET
path: /teams/{team_id}/lineup-recommendation
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 9 players returned. Discovered 2026-03-07.
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
tags: [team, lineup]
caveats:
  - >
    LIVE RECALCULATION: generated_at timestamp changes on each request. Recommendation
    is recalculated live, not cached.
  - >
    STANDARD 9 ONLY: Returns exactly 9 players (starting lineup), not the full roster.
related_schemas: []
see_also:
  - path: /bats-starting-lineups/latest/{team_id}
    reason: Coach's actual most recent lineup -- compare to GC recommendation to see deviations
  - path: /bats-starting-lineups/{event_id}
    reason: Coach's lineup for a specific game
  - path: /teams/{team_id}/players
    reason: Full roster -- player_id values in this response reference roster UUIDs
---

# GET /teams/{team_id}/lineup-recommendation

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns GameChanger's algorithmically-generated batting order and fielding assignment recommendation for the team.

**Coaching relevance: HIGH.** The GC recommendation serves as a data-driven baseline for lineup construction. Comparing this recommendation to the coach's actual lineup (from `/bats-starting-lineups/latest/{team_id}`) reveals which players GC ranks higher/lower and where the coach deviates from the algorithm.

```
GET https://api.team-manager.gc.com/teams/{team_id}/lineup-recommendation
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

Single JSON object with `lineup` array and `metadata` object.

| Field | Type | Description |
|-------|------|-------------|
| `lineup` | array | Recommended lineup entries -- 9 players (standard starting lineup) |
| `lineup[].player_id` | UUID | Player UUID |
| `lineup[].field_position` | string | Recommended field position (e.g., `"C"`, `"1B"`, `"P"`, `"CF"`, `"LF"`, `"RF"`, `"2B"`, `"3B"`, `"SS"`) |
| `lineup[].batting_order` | integer | Batting order position (1 = leadoff) |
| `metadata` | object | Generation metadata |
| `metadata.generated_at` | string (ISO 8601) | When this recommendation was generated (changes each call) |
| `metadata.team_id` | UUID | The team UUID |

## Example Response

```json
{
  "lineup": [
    {"player_id": "11ceb5ee-REDACTED", "field_position": "C", "batting_order": 1},
    {"player_id": "8119312c-REDACTED", "field_position": "1B", "batting_order": 2},
    {"player_id": "879a99fd-REDACTED", "field_position": "RF", "batting_order": 3},
    {"player_id": "d5645a1b-REDACTED", "field_position": "P", "batting_order": 4},
    {"player_id": "e8534cc3-REDACTED", "field_position": "LF", "batting_order": 5},
    {"player_id": "996c48ba-REDACTED", "field_position": "SS", "batting_order": 6},
    {"player_id": "3050e40b-REDACTED", "field_position": "3B", "batting_order": 7},
    {"player_id": "77c74470-REDACTED", "field_position": "2B", "batting_order": 8},
    {"player_id": "b7790d88-REDACTED", "field_position": "CF", "batting_order": 9}
  ],
  "metadata": {
    "generated_at": "2026-03-07T04:09:32.884Z",
    "team_id": "72bb77d8-REDACTED"
  }
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
