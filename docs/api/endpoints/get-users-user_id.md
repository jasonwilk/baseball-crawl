---
method: GET
path: /users/{user_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
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
tags: [user, team]
caveats:
  - >
    ALL FIELDS ARE PII: id, status, first_name, last_name, email are all sensitive.
    Do not log, store, or display without appropriate access controls.
related_schemas: []
see_also:
  - path: /teams/{team_id}/users
    reason: Team user list -- same 5-field schema
  - path: /users/{user_id}/profile-photo
    reason: Profile photo for this user
---

# GET /users/{user_id}

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns profile data for any GameChanger user by UUID. All fields are PII.

```
GET https://api.team-manager.gc.com/users/{user_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | UUID | User UUID (**PII -- treat as sensitive**) |

## Response

Same 5-field schema as individual records in `GET /teams/{team_id}/users`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | User UUID (**PII**) |
| `status` | string | `"active"` or `"inactive"` |
| `first_name` | string | First name (**PII**) |
| `last_name` | string | Last name (**PII**) |
| `email` | string | Email address (**PII -- redact in all storage**) |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
