---
method: GET
path: /teams/public/{public_id}/id
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 200 for OWN team public_id -- two teams confirmed via HAR 2026-03-11;
      independently re-confirmed via direct curl 2026-03-12 (public_id DolZd7TTaXj5,
      gc-app-name: web). HTTP 403 for OPPONENT team public_id (smgRExWHuBJJ returned
      403, 8+ hits, 2026-03-11). Access restricted to teams the authenticated user
      belongs to.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.team_id+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-12"
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
    ACCESS MODEL REFINEMENT (operator-reported 2026-03-12): The companion forward bridge
    (GET /teams/{team_id}/public-team-profile-id) has the same restriction pattern. The
    operator characterized both bridges as restricted to "teams the user follows," which
    is more precise than "teams the user is a member of." The exact association types
    (coaching staff, admin, explicitly followed, bookmarked) that permit access have not
    been independently verified for this endpoint, but the 403 behavioral outcome is
    confirmed 2026-03-09/2026-03-11 via proxy capture and curl. Needs re-verification
    to confirm whether "follows" includes non-admin followed teams or only coaching/admin roles.
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

**Status:** CONFIRMED -- 200 OK for own teams, 403 for opponent teams. Last verified: 2026-03-12 (direct curl).

Reverse bridge: resolves a team's `public_id` slug to its internal UUID. **Access is restricted to teams the authenticated user belongs to.** Opponent team public_ids return HTTP 403 Forbidden.

**Auth warning:** Despite the `/public/` path segment, this endpoint requires `gc-token` authentication. This is the `/teams/public/` URL pattern (auth required) vs. `/public/teams/` (truly no-auth).

```
GET https://api.team-manager.gc.com/teams/public/{public_id}/id
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Team public ID slug |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_id+json; version=0.0.0
```

## Response (200 -- own teams only)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | The team's internal UUID |

## Example Response (authenticated, own team)

```json
{"id": "00000000-0000-0000-0000-000000000001"}
```

Content-Length: 45 bytes. Single JSON object with one field.

Confirmed on two distinct owned teams (HAR capture 2026-03-11). This is the reverse of `GET /teams/{team_id}/public-team-profile-id`.

## Error Response (HTTP 403 -- opponent team)

Returned when querying the public_id of a team the authenticated user does NOT belong to:

```json
{
  "message": "Forbidden"
}
```

Observed: opponent public_id returned 403 on 2026-03-11. Eight consecutive attempts in proxy session, all 403. Body is the bare string `"Forbidden"` (not a JSON object).

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

**Discovered:** 2026-03-07. **Full 200 response confirmed:** 2026-03-11 (HAR capture, two owned teams). **403 for opponent confirmed:** 2026-03-11 (proxy session, 8 consecutive 403s). **Re-confirmed via direct curl:** 2026-03-12 (public_id DolZd7TTaXj5, gc-app-name: web). **Access model refinement (operator-reported):** 2026-03-12 -- restriction is specifically "teams the user follows," not arbitrary authenticated access; same restriction as the forward bridge. Exact association types (coaching staff, admin, followed, bookmarked) not yet independently verified.
