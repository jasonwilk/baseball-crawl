---
method: GET
path: /teams/{team_id}/users/count
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
tags: [team, user]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/users
    reason: Full user list -- use count here to determine page count before paginating
---

# GET /teams/{team_id}/users/count

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the count of users associated with a team without loading the full user list. Use this before paginating `/teams/{team_id}/users` to know how many pages to expect.

```
GET https://api.team-manager.gc.com/teams/{team_id}/users/count
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Total number of users on the team |

## Example Response

```json
{"count": 243}
```

(243 users observed for Lincoln Rebels 14U team `72bb77d8` -- requires at least 3 pages of `/users`.)

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
