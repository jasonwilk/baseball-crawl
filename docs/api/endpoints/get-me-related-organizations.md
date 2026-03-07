---
method: GET
path: /me/related-organizations
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Previously returned HTTP 500 without required params. CONFIRMED 2026-03-07 with
      required params. 2 organizations observed.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params:
  - name: page_starts_at
    required: true
    description: Pagination offset. Use 0 for first page. Server returns HTTP 500 without this.
  - name: page_size
    required: true
    description: Page size. Use 50. Server returns HTTP 500 without this.
pagination: true
response_shape: array
response_sample: null
raw_sample_size: "2 organizations"
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [me, organization]
caveats:
  - >
    REQUIRED PARAMS: Must include ?page_starts_at=0&page_size=50 AND x-pagination: true header.
    Server returns HTTP 500 without these.
  - >
    ngb DOUBLE-PARSE: ngb field is a JSON-encoded string. Parse with json.loads(org["ngb"]).
related_schemas: []
see_also:
  - path: /me/organizations
    reason: Direct org memberships (vs. team-based access here)
  - path: /organizations/{org_id}/teams
    reason: Enumerate teams within orgs discovered here
---

# GET /me/related-organizations

**Status:** CONFIRMED LIVE -- 200 OK. 2 organizations observed. Previously HTTP 500 without required params. Last verified: 2026-03-07.

Returns organizations the authenticated user is associated with via team membership. Distinct from `/me/organizations` (direct org membership).

**Coaching relevance: MEDIUM.** Org discovery endpoint -- use to find org UUIDs for subsequent org-level calls.

```
GET https://api.team-manager.gc.com/me/related-organizations?page_starts_at=0&page_size=50
```

## Required Headers (in addition to standard auth)

```
x-pagination: true
```

## Required Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_starts_at` | integer | Pagination offset. Use `0` for first page. |
| `page_size` | integer | Page size. Use `50`. |

## Response

Bare JSON array of organization objects. 2 organizations observed.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Organization UUID |
| `city` | string | City |
| `country` | string | Country |
| `end_date` | string (ISO 8601) or null | Organization/season end date |
| `name` | string | Organization display name |
| `ngb` | string | National Governing Body (**JSON-encoded string -- double-parse**) |
| `season_name` | string | Season name (e.g., `"fall"`, `"summer"`) |
| `season_year` | integer | Season year |
| `sport` | string | Sport |
| `start_date` | string (ISO 8601) or null | Organization/season start date |
| `state` | string | State/province |
| `status` | string | Organization status (e.g., `"active"`) |
| `type` | string | Organization type: `"tournament"`, `"travel"`, `"league"` |
| `public_id` | string | Public ID slug |

## Example Response

```json
[
  {
    "id": "8881846c-REDACTED",
    "city": "Lincoln",
    "country": "United States",
    "end_date": null,
    "name": "Lincoln Rebels",
    "ngb": "[\"usssa\"]",
    "season_name": "summer",
    "season_year": 2025,
    "sport": "baseball",
    "start_date": null,
    "state": "NE",
    "status": "active",
    "type": "travel",
    "public_id": "8uNxSKmeevE0"
  }
]
```

**Discovered:** 2026-03-05. **Confirmed with required params:** 2026-03-07.
