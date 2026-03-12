---
method: DELETE
path: /me/relationship-requests/{team_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not independently captured from web profile.
  mobile:
    status: observed
    notes: >
      1 hit, HTTP 200. Captured from iOS proxy session 2026-03-12_034919
      (app version 2026.9.0). Called as step 2 of the unfollow/convert-to-fan
      sequence, immediately after DELETE /teams/{team_id}/users/{user_id}.
      Response body was the literal string "OK" (2 bytes, text/plain).
accept: "application/vnd.gc.com.none+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: string
response_sample: null
raw_sample_size: "2 bytes"
discovered: "2026-03-12"
last_confirmed: null
tags: [team, write, me]
caveats:
  - >
    WRITE OPERATION: Modifies server state (cancels a pending follow/join request
    or removes a team association). Not relevant for data ingestion.
  - >
    HTTP 200 WITH PLAIN TEXT BODY: Unlike most 204 delete endpoints, this returns
    HTTP 200 with Content-Type text/plain and body "OK" (2 bytes). This is unusual
    and may indicate different internal semantics from the DELETE /teams/.../users
    endpoint.
  - >
    UNFOLLOW STEP 2 OF 2: Called immediately after DELETE /teams/{team_id}/users/{user_id}
    as part of the two-step unfollow sequence. The team_id in the path is the same
    team as the one being unfollowed.
  - >
    RELATIONSHIP REQUEST SEMANTICS: The path name suggests this cancels a pending
    "relationship request" (e.g., a join/follow request not yet approved). When
    called as part of the unfollow sequence for an already-associated team, it may
    serve as a general cleanup of any pending state.
see_also:
  - path: /teams/{team_id}/users/{user_id}
    reason: DELETE to remove user from team (step 1 of unfollow sequence)
  - path: /teams/{team_id}/follow
    reason: POST to re-associate as fan after unfollow
  - path: /teams/{team_id}/relationships/requests
    reason: GET endpoint for pending relationship requests on a team (admin view)
---

# DELETE /me/relationship-requests/{team_id}

**Status:** OBSERVED -- HTTP 200 in iOS proxy session 2026-03-12_034919.

Cancels a pending relationship request or cleans up team association state. Observed as step 2 of the unfollow sequence, called immediately after `DELETE /teams/{team_id}/users/{user_id}`. Returns HTTP 200 with body "OK" (text/plain).

```
DELETE https://api.team-manager.gc.com/me/relationship-requests/{team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | The team UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.none+json; version=0.0.0
Content-Type: application/vnd.gc.com.none+json; version=0.0.0
```

## Request Body

None.

## Response

**HTTP 200.** Content-Type: `text/plain; charset=utf-8`. Body: `OK` (literal 2-byte string).

This is atypical -- most delete endpoints return HTTP 204 with no body. The HTTP 200 + text/plain response suggests different internal semantics.

## Observed Call Sequence (Unfollow Flow, 2026-03-12)

1. `DELETE /teams/{team_id}/users/{user_id}` (HTTP 204) -- removes self from team
2. `DELETE /me/relationship-requests/{team_id}` (HTTP 200, "OK") -- this endpoint
3. `GET /me/teams-summary` (HTTP 304) -- app refreshes team list
4. ... ~12 seconds later ...
5. `POST /teams/{team_id}/follow` (HTTP 204) -- re-associates as fan

## Coaching Relevance

None for data ingestion. Documented to complete the follow/unfollow lifecycle picture.

**Discovered:** 2026-03-12. Session: 2026-03-12_034919 (mobile).
