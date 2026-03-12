---
method: GET
path: /organizations/{org_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: 3 hits, HTTP 304. Observed in session 2026-03-12_034919.
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
discovered: "2026-03-12"
last_confirmed: null
tags: [organization]
caveats:
  - >
    SCHEMA UNKNOWN: All 3 hits returned HTTP 304 (Not Modified / cached). Response body
    not captured from this session.
  - >
    EXPECTED CONTENT: Organization metadata -- name, league/association type, sport,
    location. Likely mirrors the shape of /public/teams/{public_id} but for organizations.
see_also:
  - path: /organizations/{org_id}/teams
    reason: Teams within this organization
  - path: /organizations/{org_id}/standings
    reason: Current-season standings for the organization's teams
  - path: /organizations/{org_id}/game-summaries
    reason: Aggregated game summaries across org teams
---

# GET /organizations/{org_id}

**Status:** OBSERVED -- HTTP 304 (3 hits) in web proxy session 2026-03-12_034919.

Returns metadata for an organization. The base org endpoint -- analogous to `GET /teams/{team_id}` for teams. Schema not captured (304 responses only).

```
GET https://api.team-manager.gc.com/organizations/{org_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Response

Schema unknown (304 cached responses only). Expected: organization metadata object with fields such as name, sport, competition level, location, and administrative details.

**Discovered:** 2026-03-12. Session: 2026-03-12_034919 (web).
