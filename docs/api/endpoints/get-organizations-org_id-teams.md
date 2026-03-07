---
method: GET
path: /organizations/{org_id}/teams
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 200. Previously returned HTTP 500 without required parameters. Confirmed 2026-03-07
      with required params. 7 teams observed.
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
raw_sample_size: "7 teams observed"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [organization, team]
caveats:
  - >
    REQUIRED PARAMS: Must include ?page_starts_at=0&page_size=50 AND x-pagination: true header.
    Server returns HTTP 500 without these parameters.
  - >
    root_team_id IS THE TEAM UUID: Use root_team_id for /teams/{team_id} and all team-scoped
    endpoints. team_public_id enables public endpoint access without extra bridge calls.
related_schemas: []
see_also:
  - path: /me/related-organizations
    reason: Source of org_id values
  - path: /teams/{team_id}
    reason: Team detail using root_team_id from this response
---

# GET /organizations/{org_id}/teams

**Status:** CONFIRMED LIVE -- 200 OK. 7 teams observed. Last verified: 2026-03-07.

Returns all teams belonging to an organization. **Requires `?page_starts_at=0&page_size=50` query parameters AND `x-pagination: true` request header.** Server returns HTTP 500 without these.

**Coaching relevance: HIGH.** Single call enumerates all teams in an organization; replaces per-team discovery.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/teams?page_starts_at=0&page_size=50
```

## Required Headers (in addition to standard auth)

```
x-pagination: true
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Required Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_starts_at` | integer | Pagination offset. Use `0` for first page. |
| `page_size` | integer | Page size. Use `50`. |

## Response

Bare JSON array of team objects. 7 teams observed for Lincoln Rebels organization.

| Field | Type | Description |
|-------|------|-------------|
| `root_team_id` | UUID | Team's primary UUID -- use for `/teams/{team_id}` and all team-scoped endpoints |
| `organization_id` | UUID | Organization UUID |
| `status` | string | Team status: `"active"`, `"org_invite"` |
| `name` | string | Team display name |
| `sport` | string | Sport (e.g., `"baseball"`) |
| `season_name` | string | Season name (e.g., `"summer"`, `"spring"`) |
| `season_year` | integer | Season year |
| `city` | string | City |
| `state` | string | State/province |
| `country` | string | Country |
| `staff_ids` | array | Array of user UUIDs for team staff (populated for `org_invite` teams) |
| `proxy_team_id` | UUID or null | Internal proxy team ID (null for `"org_invite"` status teams) |
| `age_group` | string | Age group (e.g., `"14U"`, `"9U"`) |
| `team_public_id` | string | Public ID slug -- enables public endpoint access without additional bridge calls |

## Example Record

```json
{
  "root_team_id": "cb67372e-REDACTED",
  "organization_id": "87452e66-REDACTED",
  "status": "active",
  "name": "Lincoln Rebels 9U",
  "sport": "baseball",
  "season_name": "summer",
  "season_year": 2026,
  "city": "Lincoln",
  "state": "NE",
  "country": "United States",
  "staff_ids": [],
  "proxy_team_id": "3d0e3553-REDACTED",
  "age_group": "9U",
  "team_public_id": "KCRUFIkaHGXI"
}
```

**Discovered:** 2026-03-07. **Confirmed with required params:** 2026-03-07.
