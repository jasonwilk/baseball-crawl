---
method: GET
path: /teams/{team_id}/relationships
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 86+ records for 243-user team. Confirmed 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [team, user]
caveats:
  - >
    PII: user_id values are GameChanger account UUIDs. Handle with appropriate access controls.
    Do not log or store without redaction.
related_schemas: []
see_also:
  - path: /teams/{team_id}/users
    reason: Full user list -- relationships link user_id to player_id
  - path: /teams/{team_id}/relationships/requests
    reason: Pending relationship requests for this team
---

# GET /teams/{team_id}/relationships

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns user-to-player relationship mappings for the team. Links parent/guardian GameChanger accounts to their associated player records.

```
GET https://api.team-manager.gc.com/teams/{team_id}/relationships
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

Bare JSON array of relationship objects.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Team UUID (same as path parameter) |
| `user_id` | UUID | GameChanger user UUID (**PII -- handle with care**) |
| `player_id` | UUID | Player UUID on this team |
| `relationship` | string | Relationship type. Observed values: `"primary"` (parent/guardian), `"self"` (player's own account) |

**Key observations:**
- Multiple `user_id` values can map to the same `player_id` (e.g., both parents linked to same player).
- `"self"` indicates the user IS the player (player has their own GC account).
- `"primary"` indicates the user is a parent/guardian.
- 243 total users on this team; relationships list has 86+ records for a subset of players.

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
