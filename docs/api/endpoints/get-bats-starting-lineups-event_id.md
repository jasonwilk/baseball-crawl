---
method: GET
path: /bats-starting-lineups/{event_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 403 for away game (e3471c3b). HTTP 200 with full lineup for home game.
      Confirmed 2026-03-07.
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
tags: [games, lineup]
caveats:
  - >
    HTTP 403 FOR AWAY GAMES: Access is restricted to events where the authenticated
    user's team was the primary scorer. Away games where the opponent managed scoring
    return HTTP 403.
  - >
    NO latest_lineup WRAPPER: Response is the lineup object directly. Differs from
    GET /bats-starting-lineups/latest/{team_id} which wraps the same object in
    {"latest_lineup": {...}}.
related_schemas: []
see_also:
  - path: /bats-starting-lineups/latest/{team_id}
    reason: Most recent lineup for a team (same schema with latest_lineup wrapper)
  - path: /events/{event_id}
    reason: Event detail -- pregame_data.lineup_id links to this endpoint's lineup id field
  - path: /teams/{team_id}/lineup-recommendation
    reason: GC algorithm recommendation -- compare to actual coach lineup from this endpoint
---

# GET /bats-starting-lineups/{event_id}

**Status:** CONFIRMED LIVE -- 200 OK (home game). HTTP 403 for away game. Last verified: 2026-03-07.

Returns the stored starting lineup for a specific game event. Array order = batting order. Access limited to events where the authenticated user's team was the primary scorer.

The lineup `id` matches `pregame_data.lineup_id` in `GET /events/{event_id}`.

```
GET https://api.team-manager.gc.com/bats-starting-lineups/{event_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID. Must be for a game where the authenticated team was the primary scorer. |

## Response

Single JSON object (the lineup object directly, no `latest_lineup` wrapper).

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique ID for this lineup record. Same `id` referenced as `pregame_data.lineup_id` in `GET /events/{event_id}`. |
| `dh` | UUID or null | DH player UUID (null when not using DH) |
| `dh_batting_for` | UUID or null | UUID of the player the DH bats for (null when not using DH) |
| `creator` | UUID | User UUID who created this lineup (**PII -- redact in stored files**) |
| `entries` | array | Lineup entries. **Array order = batting order** (first entry = leadoff). |
| `entries[].player_id` | UUID | Player UUID |
| `entries[].fielding_position` | string | Field position (e.g., `"CF"`, `"P"`, `"RF"`, `"LF"`, `"1B"`, `"3B"`, `"C"`, `"2B"`, `"SS"`) |

## Example Response

```json
{
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
```

**Discovered:** 2026-03-07. **Confirmed (home game):** 2026-03-07.
