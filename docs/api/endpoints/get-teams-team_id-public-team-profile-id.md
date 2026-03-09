---
method: GET
path: /teams/{team_id}/public-team-profile-id
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Single-field response confirmed 2026-03-04 with gc-token. One own-team confirmed
      (cb67372e -> KCRUFIkaHGXI). OPPONENT UUID RETURNS 403: tested 2026-03-09 with
      progenitor_team_id 14fd6cb6-43ab-4c61-a26c-5486c949e7b5 (Nighthawks Navy AAA 14U).
      Credentials confirmed valid (GET /me/user returned 200). Access is restricted
      to teams the authenticated user is a member of -- opponents are blocked.
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
    other `/teams/{team_id}/*` endpoints, auth is required.
  - >
    OPPONENT UUID RETURNS 403 (CONFIRMED 2026-03-09): Tested with opponent progenitor_team_id
    14fd6cb6-43ab-4c61-a26c-5486c949e7b5 (Nighthawks Navy AAA 14U) -- HTTP 403 Forbidden.
    Credentials confirmed valid via /me/user. Access is restricted to teams the
    authenticated user is a member of. The "ID chain" from UUID to public endpoints
    does NOT work for opponents via this endpoint. Alternative routes to opponent
    public_ids must be found (e.g., scraping the GC web app URL, or checking if the
    public API exposes the team slug directly).
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

**Status:** CONFIRMED LIVE -- 200 OK for own teams. **HTTP 403 for opponent UUIDs (confirmed 2026-03-09).** Last verified: 2026-03-09.

UUID-to-`public_id` bridge. Resolves a team's internal UUID to its `public_id` slug. This is the bridge endpoint between the authenticated API (which identifies teams by UUID) and the public API (which identifies teams by `public_id` slug).

**CRITICAL LIMITATION:** This endpoint returns 403 Forbidden when called with an opponent team UUID. It only works for teams the authenticated user is a member of. The "ID chain" from opponent UUID to public API data via this bridge does NOT work. Alternative approaches to obtaining opponent `public_id` values are required (e.g., the GC web URL for the team contains the slug, or the boxscore `game_stream_id` is already usable without needing the public_id for per-game detail calls).

```
GET https://api.team-manager.gc.com/teams/{team_id}/public-team-profile-id
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID to resolve. Returns 200 for own teams (user is a member). Returns 403 for opponent/external team UUIDs (confirmed 2026-03-09). |

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

**This chain works only for own teams (user is a member). Opponent UUIDs return 403.**

For own teams:
```
own team UUID (from /me/teams)
  -> GET /teams/{team_id}/public-team-profile-id
  -> {"id": "<public_id>"}
  -> GET /public/teams/{public_id}           (team profile, no auth)
  -> GET /public/teams/{public_id}/games     (game schedule/scores, no auth)
  -> GET /public/game-stream-processing/{game_stream_id}/details  (line scores, no auth)
```

For opponent teams, this bridge is blocked. Alternatives:
- The GC web app URL for a team contains the public_id slug (e.g., `https://web.gc.com/teams/smgRExWHuBJJ`).
- Per-game line scores are accessible via `game_stream_id` from game-summaries without needing the opponent public_id.
- The boxscore endpoint uses the game_stream_id directly, not the public_id.

## Cross-References

| Endpoint | Uses `public_id` from this response? |
|----------|--------------------------------------|
| `GET /public/teams/{public_id}` | YES -- direct substitute |
| `GET /public/teams/{public_id}/games` | YES -- direct substitute |
| `GET /public/teams/{public_id}/games/preview` | YES -- direct substitute |
| `GET /teams/public/{public_id}/players` | YES -- note inverted URL pattern `/teams/public/` not `/public/teams/` |

## Known Limitations

- **Auth required:** `gc-token` required. Unauthenticated access not tested.
- **Own-team only:** Returns 200 only for teams where the authenticated user is a member. Returns HTTP 403 for opponent/external team UUIDs. Tested 2026-03-09 with progenitor_team_id `14fd6cb6-43ab-4c61-a26c-5486c949e7b5` (Nighthawks Navy AAA 14U -- expected public_id `smgRExWHuBJJ`).
- **Cannot bridge opponents to public API via this endpoint.** Use `game_stream_id` from game-summaries to access per-game data for any team without needing a `public_id`.
- **Minimal response:** Under 100 bytes. No pagination.

**Discovered:** 2026-03-04. **Confirmed:** 2026-03-04. **Opponent 403 confirmed:** 2026-03-09.
