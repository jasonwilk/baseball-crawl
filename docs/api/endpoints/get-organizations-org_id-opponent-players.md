---
method: GET
path: /organizations/{org_id}/opponent-players
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: >
      HTTP 200 observed in web proxy session 2026-03-11 (107 players, ~32KB).
      Previously returned HTTP 500 with web headers (2026-03-05 session). The
      HTTP 500 "page_size" bug appears to have been resolved server-side.
  mobile:
    status: observed
    notes: 2 hits, status 200, paginated. Discovered 2026-03-05. Schema not captured from mobile.
accept: "application/vnd.gc.com.player:list+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: "107 players, ~32KB (web, 2026-03-11)"
discovered: "2026-03-05"
last_confirmed: null
tags: [organization, opponent, player, bulk]
caveats:
  - >
    HTTP 500 RESOLVED: Previously returned HTTP 500 with web headers due to missing
    pagination parameter. As of 2026-03-11 web proxy session, returns HTTP 200 without
    pagination parameters. The server-side bug appears fixed. If HTTP 500 recurs,
    try adding `?page_size=50` or `?start_at=0`.
  - >
    STATUS UPDATE 2026-03-11: Changed from PARTIAL to OBSERVED. Schema now documented
    from live web proxy data. Previous "iOS only" limitation no longer observed.
see_also:
  - path: /teams/{team_id}/opponents/players
    reason: Team-level bulk opponent player roster (confirmed, 758 records) -- team scope
  - path: /organizations/{org_id}/opponents
    reason: Org-level opponent list (for team names and UUIDs)
---

# GET /organizations/{org_id}/opponent-players

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. 107 players. Schema based on observed data.

Returns opponent player rosters at the organization level. As of 2026-03-11, the previously-documented HTTP 500 bug with web headers appears resolved -- the endpoint returns HTTP 200 without requiring explicit pagination parameters.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/opponent-players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization identifier |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.player:list+json; version=0.1.0
```

## Response

**HTTP 200.** JSON array of player objects.

| Field | Type | Description |
|-------|------|-------------|
| `[].id` | UUID | Player UUID |
| `[].team_id` | UUID | The opponent team this player belongs to |
| `[].status` | string | Player status. Observed: `"active"`. |
| `[].first_name` | string | Player first name |
| `[].last_name` | string | Player last name (may be abbreviated) |
| `[].number` | string | Jersey number as string |
| `[].bats` | object | Batting/throwing handedness (may be partially populated) |
| `[].bats.player_id` | UUID | Player UUID (repeated within bats object) |
| `[].bats.throwing_hand` | string | Throwing hand. Observed: `"right"`. (May be absent) |
| `[].bats.batting_side` | string | Batting side. Observed: `"right"`. (May be absent) |
| `[].person_id` | UUID | Person UUID |

## Example Response (truncated)

```json
[
  {
    "id": "00000000-REDACTED",
    "team_id": "00000000-REDACTED",
    "status": "active",
    "first_name": "Player",
    "last_name": "A",
    "number": "99",
    "bats": {
      "player_id": "00000000-REDACTED"
    },
    "person_id": "00000000-REDACTED"
  },
  {
    "id": "00000000-REDACTED",
    "team_id": "00000000-REDACTED",
    "status": "active",
    "first_name": "Player",
    "last_name": "B",
    "number": "7",
    "bats": {
      "throwing_hand": "right",
      "batting_side": "right",
      "player_id": "00000000-REDACTED"
    },
    "person_id": "00000000-REDACTED"
  }
]
```

**Coaching relevance: HIGH.** Bulk opponent player roster at org scope. Useful for building a comprehensive scouting database of all players the org's teams have faced. The `bats` object provides handedness when populated.

**Previously documented as PARTIAL (HTTP 500 from web).**  Status updated to OBSERVED 2026-03-11 after web proxy session confirmed HTTP 200.

**Discovered:** 2026-03-05. Status updated: 2026-03-11.
