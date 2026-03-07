---
method: GET
path: /teams/public/{public_id}/id
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      AUTH REQUIRED despite /public/ path. Full schema documented. Reverse bridge:
      public_id -> UUID. Confirmed 2026-03-07.
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
tags: [team, bridge]
caveats:
  - >
    AUTH REQUIRED: Despite /public/ in the path, this endpoint requires gc-token
    authentication. HTTP 401 returned without a valid token. Do not confuse with truly
    public /public/teams/ endpoints (different URL prefix order).
related_schemas: []
see_also:
  - path: /teams/{team_id}/public-team-profile-id
    reason: Forward bridge (UUID -> public_id). This is the reverse direction.
  - path: /teams/public/{public_id}/access-level
    reason: Also uses /teams/public/ URL pattern (auth required)
---

# GET /teams/public/{public_id}/id

**Status:** CONFIRMED LIVE -- 200 OK. **AUTH REQUIRED** despite `/public/` path. Last verified: 2026-03-07.

Reverse bridge: resolves a team's `public_id` slug to its internal UUID. This is the reverse of `GET /teams/{team_id}/public-team-profile-id` (which resolves UUID -> public_id slug).

**Auth warning:** Despite the `/public/` path segment, this endpoint requires `gc-token` authentication. This is the `/teams/public/` URL pattern (auth required) vs. `/public/teams/` (truly no-auth).

```
GET https://api.team-manager.gc.com/teams/public/{public_id}/id
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Team public ID slug |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | The team's internal UUID |

## Example Response (authenticated)

```json
{"id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4"}
```

Confirmed symmetry: public_id `a1GFM9Ku0BbF` resolves to UUID `72bb77d8-54ca-42d2-8547-9da4880d0cb4` (Lincoln Rebels 14U). This is the reverse of `GET /teams/{team_id}/public-team-profile-id`.

## Error Response (unauthenticated -- HTTP 401)

```json
{
  "message": "The request was missing user authentication, please try again with valid token(s)",
  "missing_authentication": ["user"]
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
