---
method: GET
path: /teams/{team_id}/avatar-image
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Full schema documented. Returns signed CloudFront URL. Discovered 2026-03-07.
      Confirmed with opponent root_team_id 2026-03-09: HTTP 200 with image URL.
      HTTP 404 when team has no avatar set.
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
tags: [team, media]
caveats:
  - >
    URL EXPIRES: Signed CloudFront URL has time-limited validity. Do not cache long-term.
  - >
    HTTP 404 WHEN NO AVATAR: Returns HTTP 404 (not 200 with null) when a team has no
    avatar image set. Handle 404 as "no avatar" rather than treating it as an error.
    Observed 2026-03-09: many opponent teams returned 404 while others returned 200.
  - >
    USE root_team_id FOR OPPONENTS: When fetching an opponent team's avatar, use the
    root_team_id from GET /teams/{team_id}/opponents, NOT the progenitor_team_id.
    Confirmed 2026-03-09: GC app used bd05f3d5-1dfb-47c1-8e81-93c0660eaaef
    (root_team_id) for Nighthawks Navy AAA 14U avatar, not 14fd6cb6-43ab-4c61-a26c-5486c949e7b5
    (progenitor_team_id). Same pattern observed for all opponent teams in this session.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents
    reason: Source of root_team_id for opponent teams (use root_team_id with this endpoint)
  - path: /organizations/{org_id}/avatar-image
    reason: Organization-level avatar image (same concept, org scope)
---

# GET /teams/{team_id}/avatar-image

**Status:** CONFIRMED LIVE -- 200 OK. HTTP 404 when no avatar set. Last verified: 2026-03-09.

Returns a signed URL for the team's avatar/logo image. Returns HTTP 404 when the team has no avatar image set (treat 404 as "no avatar", not as an error).

```
GET https://api.team-manager.gc.com/teams/{team_id}/avatar-image
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID. For own teams: team UUID from `/me/teams`. For opponents: use `root_team_id` from `/teams/{team_id}/opponents` (NOT `progenitor_team_id`). |

## Response

Single JSON object when avatar exists (HTTP 200). HTTP 404 when no avatar is set.

| Field | Type | Description |
|-------|------|-------------|
| `full_media_url` | string (URL) | Time-limited signed CloudFront URL to the team avatar image |

URL pattern: `https://media-service.gc.com/{image-uuid}?Policy={base64}&Key-Pair-Id={id}&Signature={sig}`

## Opponent Team Access: root_team_id

**Confirmed 2026-03-09:** When fetching an opponent's avatar, the GC app uses the `root_team_id` (local opponent registry entry), NOT the `progenitor_team_id` (canonical GC UUID). Both IDs are available from `GET /teams/{team_id}/opponents`. Use `root_team_id` here.

In the 2026-03-09 session, 61 distinct opponent UUIDs (all root_team_ids) were used with this endpoint. Approximately half returned 200 OK (avatar exists) and half returned 404 (no avatar set).

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07. **root_team_id for opponents, 404 for no-avatar:** 2026-03-09.
