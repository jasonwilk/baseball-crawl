---
method: GET
path: /teams/{team_id}/relationships/requests
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Returns empty array []. Discovered 2026-03-07.
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
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [team, user]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/relationships
    reason: Active relationship mappings (user_id to player_id)
---

# GET /teams/{team_id}/relationships/requests

**Status:** CONFIRMED LIVE -- 200 OK (empty array). Last verified: 2026-03-07.

Returns pending relationship requests for a team. No pending requests observed -- schema unknown from empty response.

```
GET https://api.team-manager.gc.com/teams/{team_id}/relationships/requests
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

`[]` (empty array observed). Full schema unknown when records are present.

**Discovered:** 2026-03-07. **Confirmed (empty):** 2026-03-07.
