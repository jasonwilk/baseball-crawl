---
method: GET
path: /teams/public/{public_id}/id
status: PARTIAL
auth: required
profiles:
  web:
    status: partial
    notes: >
      HTTP 200 for OWN team public_id (a1GFM9Ku0BbF -> UUID confirmed 2026-03-07).
      HTTP 403 for OPPONENT team public_id (smgRExWHuBJJ returned 403, 4 hits,
      2026-03-09). Access appears restricted to teams the authenticated user belongs to.
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
last_confirmed: "2026-03-09"
tags: [team, bridge]
caveats:
  - >
    AUTH REQUIRED: Despite /public/ in the path, this endpoint requires gc-token
    authentication. HTTP 401 returned without a valid token. Do not confuse with truly
    public /public/teams/ endpoints (different URL prefix order).
  - >
    RESTRICTED TO OWN TEAMS ONLY (confirmed 2026-03-09): HTTP 403 Forbidden returned
    when attempting to resolve an opponent team's public_id. Tested with opponent
    public_id smgRExWHuBJJ (Nighthawks Navy AAA 14U) -- 4 hits, all 403. Only returns
    the UUID for teams the authenticated user has membership in. This endpoint CANNOT
    be used to resolve arbitrary opponent public_ids to UUIDs.
  - >
    ALTERNATIVE: Use GET /search/opponent-import to find opponent team UUIDs by name.
    The search endpoint returns team UUIDs without requiring membership.
related_schemas: []
see_also:
  - path: /teams/{team_id}/public-team-profile-id
    reason: Forward bridge (UUID -> public_id). Also restricted to own teams.
  - path: /teams/public/{public_id}/access-level
    reason: Also uses /teams/public/ URL pattern (auth required)
  - path: /search/opponent-import
    reason: Alternative for resolving opponent team UUIDs -- search by name returns UUID
---

# GET /teams/public/{public_id}/id

**Status:** PARTIAL -- 200 OK for own teams only. HTTP 403 for opponent teams. Last verified: 2026-03-09.

Reverse bridge: resolves a team's `public_id` slug to its internal UUID. **Access is restricted to teams the authenticated user belongs to.** Opponent team public_ids return HTTP 403 Forbidden.

**Auth warning:** Despite the `/public/` path segment, this endpoint requires `gc-token` authentication. This is the `/teams/public/` URL pattern (auth required) vs. `/public/teams/` (truly no-auth).

```
GET https://api.team-manager.gc.com/teams/public/{public_id}/id
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Team public ID slug |

## Response (200 -- own teams only)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | The team's internal UUID |

## Example Response (authenticated, own team)

```json
{"id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4"}
```

Confirmed symmetry: public_id `a1GFM9Ku0BbF` resolves to UUID `72bb77d8-54ca-42d2-8547-9da4880d0cb4` (own team). This is the reverse of `GET /teams/{team_id}/public-team-profile-id`.

## Error Response (HTTP 403 -- opponent team)

Returned when querying the public_id of a team the authenticated user does NOT belong to:

```json
{
  "message": "Forbidden"
}
```

Observed: opponent `smgRExWHuBJJ` (Nighthawks Navy AAA 14U) returned 403 on 2026-03-09. Four separate attempts, all 403.

## Error Response (HTTP 401 -- unauthenticated)

```json
{
  "message": "The request was missing user authentication, please try again with valid token(s)",
  "missing_authentication": ["user"]
}
```

## Access Model

| Scenario | Result |
|----------|--------|
| Own team's public_id | HTTP 200 + UUID |
| Opponent's public_id | HTTP 403 Forbidden |
| No auth token | HTTP 401 |

## Alternatives for Opponent UUID Resolution

Use `GET /search/opponent-import?name={team_name}&sport=baseball` to find opponent team UUIDs programmatically. The search endpoint does not require team membership and returns UUID in its results.

**Discovered:** 2026-03-07. **403 for opponent confirmed:** 2026-03-09.
