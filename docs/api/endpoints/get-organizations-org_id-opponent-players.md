---
method: GET
path: /organizations/{org_id}/opponent-players
status: PARTIAL
auth: required
profiles:
  web:
    status: partial
    notes: HTTP 500 returned with web headers. Proxy log shows 200 from iOS (paginated). Discovered 2026-03-05.
  mobile:
    status: observed
    notes: 2 hits, status 200. Paginated. Discovered 2026-03-05.
accept: null
gc_user_action: null
query_params:
  - name: start_at
    type: string
    required: false
    description: Pagination cursor (observed in proxy log).
pagination: true
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: null
tags: [organization, opponent, player, bulk]
caveats:
  - >
    HTTP 500 FROM WEB HEADERS: Returns {"error":"Cannot read properties of undefined
    (reading 'page_size')"} when called without required pagination parameters. The
    `start_at` cursor or a `page_size` parameter may be required. See IDEA-011.
  - >
    iOS ONLY: Works with iOS Odyssey app headers (2 hits, status 200, paginated).
    Web browser headers return HTTP 500. Response schema not captured from either profile.
  - >
    BLOCKED FOR IMPLEMENTATION: Do not use until HTTP 500 is resolved. Use
    /teams/{team_id}/opponents/players for team-level bulk opponent player data instead.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents/players
    reason: Team-level bulk opponent player roster (confirmed, 758 records) -- use this instead
  - path: /organizations/{org_id}/opponents
    reason: Org-level opponent list (for opponent UUIDs)
---

# GET /organizations/{org_id}/opponent-players

**Status:** OBSERVED (proxy log + web headers). HTTP 500 with web headers; iOS proxy log shows 200 (paginated). Schema not captured.

Returns opponent player rosters at the organization level. **Currently returns HTTP 500 with web headers** due to a missing pagination parameter.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/opponent-players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization identifier |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_at` | string | Unknown | Pagination cursor (observed in iOS traffic) |

## Error Response (Web Headers)

```json
{"error": "Cannot read properties of undefined (reading 'page_size')"}
```

HTTP 500. Indicates a missing or malformed pagination parameter.

## Investigation Status

Schema not confirmed. iOS proxy log shows 2 hits with status 200 and pagination, but response body was not captured. The correct pagination parameter combination is unknown.

**Alternative:** Use `GET /teams/{team_id}/opponents/players` (confirmed, 758 records, 61 teams) instead.

**Discovered:** 2026-03-05.
