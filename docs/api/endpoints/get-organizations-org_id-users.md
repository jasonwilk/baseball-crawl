---
method: GET
path: /organizations/{org_id}/users
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Schema documented. 1 admin user observed. Discovered 2026-03-05.
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
discovered: "2026-03-05"
last_confirmed: null
tags: [organization, user]
caveats:
  - >
    OBSERVED STATUS: Schema documented from web headers only -- not confirmed via
    independent curl call.
  - >
    PII: `user_id` values are UUIDs mapped to real users. Redact in stored files.
  - >
    LIMITED DATA: Only 1 admin user observed. Other association types (coach, member)
    likely exist but not confirmed.
related_schemas: []
see_also:
  - path: /teams/{team_id}/users
    reason: Team-level user list (more commonly needed)
  - path: /me/related-organizations
    reason: List of organizations the authenticated user belongs to
---

# GET /organizations/{org_id}/users

**Status:** OBSERVED (web headers, schema documented). Not confirmed via independent curl.

Returns users associated with the organization.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/users
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization identifier |

## Response

A single JSON object (not an array).

| Field | Type | Description |
|-------|------|-------------|
| `organization_id` | UUID | The organization UUID |
| `users` | array | Array of user association objects |

### User Association Object

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | UUID | User UUID (PII -- redact in stored files) |
| `association` | string | User's role in the organization. Observed: `"admin"` |

## Example Response

```json
{
  "organization_id": "<org-uuid>",
  "users": [
    {"user_id": "<user-uuid>", "association": "admin"}
  ]
}
```

**Coaching relevance:** Low. Admin/membership data, not coaching analytics.

**Discovered:** 2026-03-05.
