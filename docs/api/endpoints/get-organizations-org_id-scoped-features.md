---
method: GET
path: /organizations/{org_id}/scoped-features
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Empty scoped_features object. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.scoped_features+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [organization, team]
caveats: []
related_schemas: []
see_also:
  - path: /teams/{team_id}/scoped-features
    reason: Same concept at team level
---

# GET /organizations/{org_id}/scoped-features

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns feature flags scoped to the organization.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/scoped-features
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Response

```json
{"scoped_features": {}}
```

Empty `scoped_features` object observed -- no features enabled for this org.

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
