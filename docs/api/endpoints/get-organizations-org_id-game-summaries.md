---
method: GET
path: /organizations/{org_id}/game-summaries
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Empty array for travel ball org. Discovered 2026-03-07.
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
tags: [organization, games]
caveats:
  - >
    EMPTY FOR TRAVEL BALL ORG: Returned [] for travel ball org. Likely populated for
    league/school program orgs where the organization manages the game schedule directly.
related_schemas: []
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Team-scoped game summaries -- confirmed populated with full schema
  - path: /organizations/{org_id}/events
    reason: Org-level events (also empty for travel ball org)
---

# GET /organizations/{org_id}/game-summaries

**Status:** CONFIRMED LIVE -- 200 OK (empty array). Last verified: 2026-03-07.

Returns game summaries for an organization. Full schema unknown -- returned empty array `[]` for the travel ball org tested. Likely populated for league/school program orgs.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/game-summaries
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

**Discovered:** 2026-03-07. **Confirmed (empty):** 2026-03-07.
