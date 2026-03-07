---
method: GET
path: /teams/public/{public_id}/players
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Captured with gc-token present. Auth may not be required -- endpoint uses
      /teams/public/ path pattern. Unauthenticated access not yet tested.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.public_player:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/players-roster-sample.json
raw_sample_size: "20 players, LSB JV roster, 2.3 KB"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [team, player]
caveats:
  - >
    URL PATTERN WARNING: This endpoint uses `/teams/public/{public_id}/players`
    (teams before public). Do NOT confuse with `/public/teams/{public_id}` which
    uses the inverted order. Both path structures coexist in the API and have
    different auth behaviors.
  - >
    AUTH UNVERIFIED: Frontmatter says `auth: required` because the confirmed capture
    used gc-token, but unauthenticated access has NOT been tested. The `/teams/public/`
    path pattern suggests auth may not be required. Until a no-auth test is done,
    treat auth as assumed, not confirmed.
related_schemas: []
see_also:
  - path: /teams/{team_id}/players
    reason: Authenticated roster endpoint using UUID instead of public_id slug
  - path: /public/teams/{public_id}
    reason: Public team profile (inverted URL -- truly no-auth endpoint)
  - path: /teams/{team_id}/public-team-profile-id
    reason: UUID-to-public_id bridge (get the public_id from a team UUID)
---

# GET /teams/public/{public_id}/players

**Status:** CONFIRMED LIVE -- 200 OK. 20 players returned. LSB JV Grizzlies (`y24fFdnr3RAN`). Last verified: 2026-03-04.

Returns the roster for a team identified by its `public_id` slug. Same 5-field schema as `GET /teams/{team_id}/players` (authenticated UUID endpoint). The distinction is this endpoint uses the short alphanumeric `public_id` instead of the team UUID.

**IMPORTANT URL PATTERN:** This endpoint uses `/teams/public/{public_id}/players` -- the `teams` segment comes before `public`. This is the INVERSE of other public endpoints which use `/public/teams/{public_id}`. Both path structures coexist in the API and have different auth behaviors. Do not assume all endpoints with "public" in the path are unauthenticated.

```
GET https://api.team-manager.gc.com/teams/public/{public_id}/players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Alphanumeric public ID slug (e.g., `"y24fFdnr3RAN"`). NOT a UUID. Available from `GET /me/teams` (`public_id` field) or from `GET /teams/{team_id}` (`public_id` field). |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.public_player:list+json; version=0.0.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

Auth requirement uncertain -- captured with gc-token but may work without it.

## Response

Bare JSON array of player objects. 20 players returned in single response (no pagination triggered). Same 5-field schema as authenticated `GET /teams/{team_id}/players`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Canonical player UUID. Same join key as in authenticated roster endpoint. |
| `first_name` | string | First name. May be initials only. |
| `last_name` | string | Last name. |
| `number` | string | Jersey number (string, not integer). NOT unique within a team. |
| `avatar_url` | string | Avatar URL. Empty string `""` when unset. Normalize with `.get("avatar_url") or None`. |

## Known Limitations

- Auth requirement is unconfirmed. Captured with gc-token. Whether it works without auth is unknown.
- `avatar_url` is an empty string `""` when unset (not null). Same normalization needed as authenticated roster endpoint.
- `number` is NOT unique within a team (two players sharing #15 observed).
- The URL pattern (`/teams/public/`) is the INVERSE of other public endpoints (`/public/teams/`). This is critical -- do not assume auth rules apply consistently based on the presence of "public" in the path.

**Discovered:** 2026-03-04. **Schema confirmed:** 2026-03-04.
