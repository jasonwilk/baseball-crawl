---
method: DELETE
path: /teams/{team_id}/users/{user_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not independently captured from web profile.
  mobile:
    status: observed
    notes: >
      1 hit, HTTP 204. Captured from iOS proxy session 2026-03-12_034919
      (app version 2026.9.0). Called as step 1 of the unfollow/convert-to-fan
      sequence. The user_id in the path matched the authenticated user's own ID --
      this is a self-removal action ("leave team"), not an admin removal.
accept: "application/vnd.gc.com.none+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: string
response_sample: null
raw_sample_size: null
discovered: "2026-03-12"
last_confirmed: null
tags: [team, user, write]
caveats:
  - >
    WRITE OPERATION: Modifies server state (removes a user from a team). Not relevant
    for data ingestion.
  - >
    HTTP 204 NO CONTENT: Returns no response body on success.
  - >
    UNFOLLOW STEP 1 OF 2: In the iOS app this is step 1 of the unfollow sequence.
    Step 2 is DELETE /me/relationship-requests/{team_id}. After both steps,
    POST /teams/{team_id}/follow re-establishes a fan association.
  - >
    SELF-REMOVAL CONFIRMED: The observed call used user_id = the authenticated user's
    own UUID. This is "leave team" -- the user removing themselves. Whether
    admins can specify a different user_id is not confirmed.
see_also:
  - path: /me/relationship-requests/{team_id}
    reason: DELETE to cancel pending relationship request (step 2 of unfollow sequence)
  - path: /teams/{team_id}/follow
    reason: POST to re-associate as fan after unfollow
  - path: /teams/{team_id}/users
    reason: GET the team user list (the resource this endpoint modifies)
---

# DELETE /teams/{team_id}/users/{user_id}

**Status:** OBSERVED -- HTTP 204 in iOS proxy session 2026-03-12_034919.

Removes a user from a team. Observed as step 1 of the unfollow/fan-convert sequence: the authenticated user removes themselves ("leaves") from a team before re-associating as a fan via `POST /teams/{team_id}/follow`. Returns HTTP 204 No Content.

```
DELETE https://api.team-manager.gc.com/teams/{team_id}/users/{user_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |
| `user_id` | UUID | User UUID to remove. Observed with the authenticated user's own UUID (self-removal). |

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

**HTTP 204 No Content.** Empty response body.

## Observed Call Sequence (Unfollow Flow, 2026-03-12)

1. `DELETE /teams/{team_id}/users/{user_id}` (HTTP 204) -- this endpoint (self-removal)
2. `DELETE /me/relationship-requests/{team_id}` (HTTP 200) -- cancel pending request
3. `GET /me/teams-summary` (HTTP 304) -- app refreshes team list
4. ... ~12 seconds later ...
5. `POST /teams/{team_id}/follow` (HTTP 204) -- re-associates as fan

## Coaching Relevance

None for data ingestion. Documented to complete the follow/unfollow lifecycle picture, which is relevant context for the opponent scouting pipeline.

**Discovered:** 2026-03-12. Session: 2026-03-12_034919 (mobile).
