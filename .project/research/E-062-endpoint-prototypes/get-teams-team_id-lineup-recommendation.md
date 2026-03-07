---
method: GET
path: /teams/{team_id}/lineup-recommendation
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Confirmed 2026-03-07. Returns 9-player lineup with field positions and batting order.
  mobile:
    status: unverified
    notes: Not captured in iOS proxy session.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [lineup, recommendation, team, coaching]
related_schemas: []
see_also:
  - path: /bats-starting-lineups/latest/{team_id}
    reason: Coach's most recently entered actual lineup (vs. GC's algorithmic recommendation)
  - path: /bats-starting-lineups/{event_id}
    reason: Pre-game lineup for a specific event
  - path: /teams/{team_id}/players
    reason: Resolve player UUIDs in lineup entries to names
---

# GET /teams/{team_id}/lineup-recommendation

**Status:** CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.

Returns GameChanger's algorithmically-generated batting order and fielding assignment recommendation for the team. The recommendation is recalculated live on each request (not cached).

```
GET https://api.team-manager.gc.com/teams/{team_id}/lineup-recommendation
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Query Parameters

None observed.

## Headers (Web Profile)

Standard authenticated GET request headers. No `gc-user-action` header observed for this endpoint.

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: (not yet confirmed -- standard GC vendor-typed accept assumed)
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

> **Note on Accept header:** The exact vendor-typed Accept value for this endpoint was not captured in the 2026-03-07 probe session. The live probe succeeded -- the server returned 200 OK. The Accept header above is incomplete and should be confirmed with a browser proxy capture.

## Response

Single JSON object with `lineup` array and `metadata` object.

| Field | Type | Description |
|-------|------|-------------|
| `lineup` | array | Recommended lineup entries (9 players observed -- standard starting lineup) |
| `lineup[].player_id` | UUID | Player UUID |
| `lineup[].field_position` | string | Recommended field position (e.g., `"C"`, `"1B"`, `"P"`, `"CF"`, `"LF"`, `"RF"`, `"2B"`, `"3B"`, `"SS"`) |
| `lineup[].batting_order` | integer | Batting order position (1 = leadoff) |
| `metadata` | object | Generation metadata |
| `metadata.generated_at` | string (ISO 8601) | When this recommendation was generated |
| `metadata.team_id` | UUID | The team UUID |

## Example Response

```json
{
  "lineup": [
    {"player_id": "11ceb5ee-REDACTED", "field_position": "C",  "batting_order": 1},
    {"player_id": "8119312c-REDACTED", "field_position": "1B", "batting_order": 2},
    {"player_id": "879a99fd-REDACTED", "field_position": "RF", "batting_order": 3},
    {"player_id": "d5645a1b-REDACTED", "field_position": "P",  "batting_order": 4},
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

## Key Observations

- Returns exactly 9 players (standard starting 9, not a full roster).
- `generated_at` timestamp changes on each request (recommendation is recalculated live, not cached).
- Field positions use standard baseball position abbreviations.
- Player UUIDs match those in `GET /teams/{team_id}/players`.
- Compare with `GET /bats-starting-lineups/latest/{team_id}` to see where the coach deviated from GC's algorithm.

## Known Limitations

- **Accept header unconfirmed.** The exact vendor-typed Accept header was not captured. The endpoint returned 200 OK with whatever Accept header the probe tool sent.
- **9-player limit.** Only 9 players appear (standard starting lineup). No bench players or DH extension observed. Whether a 10-player lineup appears when the team uses a DH is unknown.
- **Algorithm opacity.** The recommendation algorithm is not documented. Whether it uses recent performance, historical patterns, handedness, or all of the above is unknown.
- **Single team confirmed.** Team UUID `72bb77d8-...` (Lincoln Rebels 14U). Behavior for teams without enough historical data to generate a recommendation is unknown.

**Coaching Relevance:** HIGH. The GC recommendation serves as a data-driven baseline for lineup construction. Comparing this recommendation to the coach's actual lineup reveals which players GC ranks higher or lower than the coach's judgment.

**Confirmed:** 2026-03-07.
