---
method: POST
path: /teams/{team_id}/follow
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: >
      Captured from web proxy session 2026-03-11. HTTP 204 No Content.
  mobile:
    status: observed
    notes: >
      Captured from iOS proxy session 2026-03-12 (app version 2026.9.0). HTTP 204 No
      Content. Sequence: operator clicked "Follow as fan" on team 468c0fe0-... --
      iOS app first issued DELETE /teams/{id}/users/{user_id} + DELETE
      /me/relationship-requests/{team_id} to remove prior membership, then POST
      /follow to re-associate as fan.
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
    FOLLOW-GATED ACCESS (CONFIRMED 2026-03-12, two independent tests): Following a
    team as a fan via this endpoint unlocks follow-gated authenticated endpoints for
    that team. Specifically, the reverse bridge GET /teams/public/{public_id}/id
    returns HTTP 200 for teams the user has followed, but HTTP 403 for teams not
    followed. This means programmatic auto-following is a prerequisite for the
    opponent scouting pipeline to resolve public_ids via the reverse bridge.
  - >
    WRITE OPERATION: This endpoint modifies server state (adds a team to the
    authenticated user's followed-teams list). Use deliberately; excessive following
    may trigger rate limits or anomaly detection.
  - >
    UNFOLLOW SEQUENCE (observed 2026-03-12): The iOS app uses a two-step unfollow
    process before re-following. Step 1: DELETE /teams/{team_id}/users/{user_id}
    (HTTP 204). Step 2: DELETE /me/relationship-requests/{team_id} (HTTP 200 "OK").
    Both steps are documented in separate endpoint files.
see_also:
  - path: /teams/public/{public_id}/id
    reason: Reverse bridge -- returns 200 for followed teams, 403 for non-followed teams
  - path: /teams/{team_id}
    reason: Team metadata for the team being followed
  - path: /me/teams
    reason: Returns teams the user is a member of (not the same as fan-followed teams)
  - path: /teams/{team_id}/users/{user_id}
    reason: DELETE to remove user membership (step 1 of unfollow sequence)
  - path: /me/relationship-requests/{team_id}
    reason: DELETE to cancel pending relationship request (step 2 of unfollow sequence)
---

# POST /teams/{team_id}/follow

**Status:** OBSERVED -- HTTP 204 in web proxy session 2026-03-11 and iOS proxy session 2026-03-12.

Follows a team as the authenticated user ("fan" association). Called when a user clicks "Follow as fan" on a team page. Returns HTTP 204 No Content on success.

```
POST https://api.team-manager.gc.com/teams/{team_id}/follow
```

## Access Model: Follow-Gating (CONFIRMED 2026-03-12)

Following a team unlocks authenticated access to follow-gated endpoints for that team. The reverse bridge (`GET /teams/public/{public_id}/id`) is the most important follow-gated endpoint -- it returns HTTP 200 for followed teams and HTTP 403 for non-followed teams.

This was confirmed by two independent tests on 2026-03-12:
- Reverse bridge WITHOUT following a team: HTTP 403 Forbidden
- Reverse bridge AFTER following as fan: HTTP 200 OK with UUID

This makes `POST /teams/{team_id}/follow` a **prerequisite for the opponent scouting pipeline**. To resolve an opponent's public_id to a UUID (or vice versa) via the authenticated reverse bridge, the operator must first follow the team. This endpoint enables programmatic auto-following to remove that manual prerequisite.

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

## Unfollow Sequence (iOS, observed 2026-03-12)

The iOS app uses a two-step unfollow when removing a fan-follow or converting from team member to fan:

1. `DELETE /teams/{team_id}/users/{user_id}` (HTTP 204) -- removes user from team membership
2. `DELETE /me/relationship-requests/{team_id}` (HTTP 200, body: "OK") -- cancels any pending relationship request

After unfollowing, `POST /teams/{team_id}/follow` re-establishes the fan association.

## Coaching Relevance

This is a write operation for team association management. It is relevant to the **opponent scouting pipeline**: programmatic auto-following is needed to unlock reverse bridge access for newly discovered opponent teams before their UUIDs can be resolved.

**Discovered:** 2026-03-11. Sessions: 2026-03-11_034739 (web), 2026-03-12_034919 (mobile, follow-gating confirmed).
