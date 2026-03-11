---
method: GET
path: /me/organizations
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Previously returned HTTP 500 without required params. CONFIRMED 2026-03-07 with
      required params. Empty array for account with org access via team membership only.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.organization_with_role:list+json; version=0.3.2"
gc_user_action: null
query_params:
  - name: page_size
    required: true
    description: Page size. Use 50. Server returns HTTP 500 without this.
pagination: true
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [me, organization]
caveats:
  - >
    REQUIRED PARAMS: Must include ?page_size=50 AND x-pagination: true header. Server
    returns HTTP 500 without these.
  - >
    EMPTY FOR TEAM-BASED ORG ACCESS: Returns [] for accounts where org access is via
    team membership rather than direct org membership. Use /me/related-organizations
    for team-based org discovery.
related_schemas: []
see_also:
  - path: /me/related-organizations
    reason: Organizations discovered via team membership (more likely to be populated)
---

# GET /me/organizations

**Status:** CONFIRMED LIVE -- 200 OK (empty array). Previously HTTP 500 without required params. Last verified: 2026-03-07.

Returns organizations the authenticated user is directly a member of. Returns empty array for accounts where org access is via team membership.

```
GET https://api.team-manager.gc.com/me/organizations?page_size=50
```

## Required Headers (in addition to standard auth)

```
x-pagination: true
```

## Required Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_size` | integer | Page size. Use `50`. |

## Response

Empty array `[]` observed for account with team-based org access only. Full schema unknown from this response.

**Discovered:** 2026-03-05. **Confirmed (empty, with required params):** 2026-03-07.
