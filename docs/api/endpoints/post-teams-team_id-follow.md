---
method: POST
path: /teams/{team_id}/follow
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 204 No Content.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.none+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: string
response_sample: null
raw_sample_size: null
discovered: "2026-03-11"
last_confirmed: null
tags: [team, write]
caveats:
  - >
    HTTP 204: Returns No Content on success. No response body.
  - >
    NO REQUEST BODY: Both the Accept and Content-Type headers are
    application/vnd.gc.com.none+json; version=0.0.0 -- confirming no body is sent.
  - >
    WRITE OPERATION: This endpoint modifies server state (adds a team to the
    authenticated user's "followed teams" list). Not relevant for data ingestion.
see_also:
  - path: /teams/{team_id}
    reason: Team metadata for the team being followed
  - path: /me/teams
    reason: Returns teams the user is a member of (not the same as followed teams)
---

# POST /teams/{team_id}/follow

**Status:** OBSERVED -- HTTP 204 in web proxy session 2026-03-11.

Follows a team as the authenticated user. Called when a user clicks "Follow" on a team's public profile page. Returns HTTP 204 No Content on success.

```
POST https://api.team-manager.gc.com/teams/{team_id}/follow
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | The team UUID to follow |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.none+json; version=0.0.0
Content-Type: application/vnd.gc.com.none+json; version=0.0.0
```

## Request Body

None. Both Accept and Content-Type indicate no body.

## Response

**HTTP 204 No Content.** Empty response body.

**Coaching relevance: NONE.** Write operation for the user-facing team follow feature. Not relevant to data ingestion.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
