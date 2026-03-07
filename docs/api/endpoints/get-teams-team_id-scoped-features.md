---
method: GET
path: /teams/{team_id}/scoped-features
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Returns empty scoped_features object. Confirmed 2026-03-07.
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
  - path: /organizations/{org_id}/scoped-features
    reason: Same concept at organization level
---

# GET /teams/{team_id}/scoped-features

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns feature flags scoped to the team.

```
GET https://api.team-manager.gc.com/teams/{team_id}/scoped-features
```

## Response

```json
{"scoped_features": {}}
```

Empty `scoped_features` object observed for this team.

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
