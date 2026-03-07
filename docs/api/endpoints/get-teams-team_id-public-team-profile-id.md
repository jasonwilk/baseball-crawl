---
method: GET
path: /teams/{team_id}/public-team-profile-id
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Single-field response confirmed 2026-03-04 with gc-token. One team confirmed
      (cb67372e -> KCRUFIkaHGXI). Opponent UUID behavior unverified.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.team_public_profile_id+json; version=0.0.0"
gc_user_action: "data_loading:team"
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/public-team-profile-id-sample.json
raw_sample_size: "~20 bytes"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [team, bridge]
caveats:
  - >
    AUTH CONFIRMED (standard pattern): gc-token present in confirmed capture. Like all
    other `/teams/{team_id}/*` endpoints, auth is required. Unauthenticated access not
    explicitly tested but not expected to work given the path pattern.
  - >
    OPPONENT UUID BEHAVIOR UNVERIFIED: If this endpoint works for opponent team UUIDs
    (from schedule pregame_data.opponent_id or opponents progenitor_team_id), it would
    enable full public API access for all opponents without needing opponents in the
    authenticated user's team list. This is the highest-priority follow-up verification.
related_schemas: []
see_also:
  - path: /teams/public/{public_id}/id
    reason: Reverse bridge -- resolves public_id slug back to team UUID (AUTH REQUIRED despite /public/ path)
  - path: /public/teams/{public_id}
    reason: Primary consumer of the public_id returned here (no-auth profile endpoint)
  - path: /public/teams/{public_id}/games
    reason: Consumer of the public_id returned here (no-auth game history endpoint)
  - path: /teams/public/{public_id}/players
    reason: Consumer of the public_id returned here (note inverted URL pattern)
  - path: /teams/{team_id}/opponents
    reason: Source of progenitor_team_id values to resolve via this bridge
---

# GET /teams/{team_id}/public-team-profile-id

**Status:** CONFIRMED LIVE -- 200 OK. Single-field response confirmed. Last verified: 2026-03-04.

UUID-to-`public_id` bridge. Resolves a team's internal UUID to its `public_id` slug. This is the bridge endpoint between the authenticated API (which identifies teams by UUID) and the public API (which identifies teams by `public_id` slug).

Without this endpoint, the only way to obtain a team's `public_id` is from the `GET /me/teams` or `GET /teams/{team_id}` response -- which only covers teams the authenticated user belongs to. This endpoint makes it possible to resolve any team UUID (including opponents) to a `public_id` for use with public endpoints.

```
GET https://api.team-manager.gc.com/teams/{team_id}/public-team-profile-id
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID to resolve. Expected to work with own team, opponent, or any team UUID. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_public_profile_id+json; version=0.0.0
gc-user-action: data_loading:team
gc-user-action-id: {UUID}
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Note:** `gc-user-action: data_loading:team` -- same value as `GET /teams/{team_id}` and `GET /teams/{team_id}/users`. All three endpoints are grouped as "team loading" actions in GameChanger's telemetry.

## Response

Single JSON object with one field.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (slug) | The team's `public_id` slug. 12-character alphanumeric string (e.g., `"KCRUFIkaHGXI"`). Used by all `/public/teams/{public_id}/...` endpoints and `/teams/public/{public_id}/players`. |

## Example Response

```json
{
  "id": "KCRUFIkaHGXI"
}
```

(Team UUID `cb67372e-b75d-472d-83e3-4d39b6d85eb2` maps to public_id `"KCRUFIkaHGXI"`)

## ID Chain: UUID to Public API

This endpoint completes the chain for accessing public data about any team whose UUID is known:

```
schedule pregame_data.opponent_id (UUID)
  -> GET /teams/{opponent_id}/public-team-profile-id
  -> {"id": "<public_id>"}
  -> GET /public/teams/{public_id}           (team profile, no auth)
  -> GET /public/teams/{public_id}/games     (game schedule/scores, no auth)
  -> GET /public/game-stream-processing/{game_stream_id}/details  (line scores, no auth)
```

## Cross-References

| Endpoint | Uses `public_id` from this response? |
|----------|--------------------------------------|
| `GET /public/teams/{public_id}` | YES -- direct substitute |
| `GET /public/teams/{public_id}/games` | YES -- direct substitute |
| `GET /public/teams/{public_id}/games/preview` | YES -- direct substitute |
| `GET /teams/public/{public_id}/players` | YES -- note inverted URL pattern `/teams/public/` not `/public/teams/` |

## Known Limitations

- **Auth required:** `gc-token` confirmed present. Unauthenticated access not tested.
- **Single team confirmed:** Only team `cb67372e` verified. Opponent UUID behavior (using `pregame_data.opponent_id` or opponents `progenitor_team_id` as the path `team_id`) not yet verified. If it works, this enables bulk opponent public API resolution.
- **Minimal response:** Under 100 bytes. No pagination.

**Discovered:** 2026-03-04. **Confirmed:** 2026-03-04.
