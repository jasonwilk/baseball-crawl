---
method: GET
path: /players/{player_id}/profile-photo
status: OBSERVED
auth: required
profiles:
  web:
    status: partial
    notes: HTTP 404 returned -- no profile photo for player tested. Endpoint pattern exists. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.person_profile_photo+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [player, media]
caveats:
  - >
    HTTP 404 WHEN NO PHOTO SET: "No profile photo found for player: <uuid>" returned when
    player has no profile photo. This is a normal 404 (resource missing), not an error.
related_schemas: []
see_also:
  - path: /users/{user_id}/profile-photo
    reason: User profile photo (same 404 behavior)
  - path: /teams/{team_id}/players
    reason: Player roster -- source of player_id values
---

# GET /players/{player_id}/profile-photo

**Status:** OBSERVED (proxy pattern). HTTP 404 for player tested 2026-03-07 (no photo set).

Returns the profile photo for a player. HTTP 404 returned when the player has no profile photo set.

```
GET https://api.team-manager.gc.com/players/{player_id}/profile-photo
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `player_id` | UUID | Player UUID |

## Investigation Status

HTTP 404 returned with message: `"No profile photo found for player: <uuid>"`. Player had no profile photo set. Full success response schema (signed URL) not captured.

**Discovered:** 2026-03-07. **Last tested:** 2026-03-07 (404).
