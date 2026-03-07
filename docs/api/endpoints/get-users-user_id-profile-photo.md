---
method: GET
path: /users/{user_id}/profile-photo
status: OBSERVED
auth: required
profiles:
  web:
    status: partial
    notes: HTTP 404 returned -- no profile photo for user tested. Endpoint pattern exists. Discovered 2026-03-07.
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
tags: [user, media]
caveats:
  - >
    HTTP 404 WHEN NO PHOTO SET: "No profile photo found for user: <uuid>" returned when
    user has no profile photo. This is a normal 404 (resource missing), not an error.
related_schemas: []
see_also:
  - path: /players/{player_id}/profile-photo
    reason: Player profile photo (same 404 behavior when no photo set)
  - path: /users/{user_id}
    reason: User profile data
---

# GET /users/{user_id}/profile-photo

**Status:** OBSERVED (proxy pattern). HTTP 404 for user tested 2026-03-07 (no photo set).

Returns the profile photo for a user. HTTP 404 returned when the user has no profile photo set.

```
GET https://api.team-manager.gc.com/users/{user_id}/profile-photo
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | UUID | User UUID |

## Investigation Status

HTTP 404 returned with message: `"No profile photo found for user: <uuid>"`. User had no profile photo set. Full success response schema (signed URL) not captured.

**Discovered:** 2026-03-07. **Last tested:** 2026-03-07 (404).
