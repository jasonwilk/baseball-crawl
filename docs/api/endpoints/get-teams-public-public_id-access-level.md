---
method: GET
path: /teams/public/{public_id}/access-level
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      AUTH REQUIRED despite /public/ path. HTTP 401 without token. Full schema documented.
      Confirmed 2026-03-07. Also confirmed for OPPONENT team public_id (smgRExWHuBJJ,
      3 hits returning 304/Not Modified, 2026-03-09) -- works for both own and opponent
      teams. Contrast with /teams/public/{public_id}/id which returns 403 for opponents.
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
  - path: /teams/public/{public_id}/id
    reason: Reverse bridge (public_id -> UUID) -- also requires auth despite /public/ path
  - path: /teams/{team_id}/public-team-profile-id
    reason: UUID -> public_id bridge (forward direction)
---

# GET /teams/public/{public_id}/access-level

**Status:** CONFIRMED LIVE -- 200 OK. **AUTH REQUIRED** despite `/public/` path. Last verified: 2026-03-07.

Returns the paid access level for a team's public profile.

**Auth warning:** Despite the `/public/` path segment, this endpoint requires `gc-token` authentication. Returns HTTP 401 without a valid token. This is the `/teams/public/` URL pattern (auth required) vs. `/public/teams/` (truly no-auth).

```
GET https://api.team-manager.gc.com/teams/public/{public_id}/access-level
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Team public ID slug (e.g., `"a1GFM9Ku0BbF"`) |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `paid_access_level` | string or null | Access tier. Observed: `null`. May be `"premium"`, `"plus"`, or other tier strings when team has paid access. |

## Example Response (authenticated)

```json
{"paid_access_level": null}
```

## Error Response (unauthenticated -- HTTP 401)

```json
{
  "message": "The request was missing user authentication, please try again with valid token(s)",
  "missing_authentication": ["user"]
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
