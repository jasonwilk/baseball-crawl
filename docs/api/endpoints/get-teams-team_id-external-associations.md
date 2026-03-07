---
method: GET
path: /teams/{team_id}/external-associations
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Returns empty array []. Confirmed 2026-03-07.
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
caveats: []
related_schemas: []
see_also: []
---

# GET /teams/{team_id}/external-associations

**Status:** CONFIRMED LIVE -- 200 OK (empty array). Last verified: 2026-03-07.

Returns external system associations for a team. Schema unknown -- returned empty array for team tested.

```
GET https://api.team-manager.gc.com/teams/{team_id}/external-associations
```

## Response

`[]` (empty array observed). Full schema unknown when records are present.

**Discovered:** 2026-03-05. **Confirmed (empty):** 2026-03-07.
