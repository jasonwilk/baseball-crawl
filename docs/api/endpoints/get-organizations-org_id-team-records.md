---
method: GET
path: /organizations/{org_id}/team-records
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Same response as /standings for tested org. Discovered 2026-03-07.
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
tags: [organization, stats]
caveats:
  - >
    IDENTICAL TO /standings IN TEST: Both endpoints returned the same data for the tested
    org. The distinction may be semantic (standings = league context, team-records = raw view)
    but behavior is indistinguishable for this org.
related_schemas: []
see_also:
  - path: /organizations/{org_id}/standings
    reason: Returns identical data in testing -- may be same endpoint with different semantic intent
---

# GET /organizations/{org_id}/team-records

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns season win/loss records for all teams in an organization. Response schema is identical to `GET /organizations/{org_id}/standings`.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/team-records
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Response

Same schema as `GET /organizations/{org_id}/standings`. See that endpoint for field documentation.

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
