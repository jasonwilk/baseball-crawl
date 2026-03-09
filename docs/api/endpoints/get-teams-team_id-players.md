---
method: GET
path: /teams/{team_id}/players
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: "Full schema documented from 20-player capture. Auth requirement: captured with gc-token."
  mobile:
    status: observed
    notes: >
      2 hits (200 + 304). Observed 2026-03-09 (session 063531). Called with opponent
      progenitor_team_id (14fd6cb6) -- confirms the endpoint works for opponent teams.
accept: "application/vnd.gc.com.player:list+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/players-roster-sample.json
raw_sample_size: "20 players, LSB JV roster, 2.3 KB"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [team, player]
related_schemas: []
see_also:
  - path: /teams/public/{public_id}/players
    reason: Public (no-auth) roster endpoint with same 5-field schema; uses public_id slug
  - path: /teams/{team_id}/season-stats
    reason: Player UUIDs from here are used as keys in the season-stats response
  - path: /teams/{team_id}/players/{player_id}/stats
    reason: Per-game per-player stats requiring a player_id from this roster
  - path: /teams/{team_id}/opponents/players
    reason: Bulk opponent roster with handedness (avoid per-opponent iteration)
---

# GET /teams/{team_id}/players

**Status:** CONFIRMED LIVE -- 200 OK. 20 players returned in single response. Last verified: 2026-03-04.

Returns the roster for a team. The response is a bare JSON array of player objects. Each player record contains identity and jersey information.

```
GET https://api.team-manager.gc.com/teams/{team_id}/players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.player:list+json; version=0.1.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

No `gc-user-action` was observed for this endpoint.

## Response

Bare JSON array of player objects. 20 players returned in a single response (no pagination triggered). Each player has 5 fields.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | **Canonical player UUID.** THE join key for all player-scoped endpoints (`/players/{player_id}/stats`, season-stats player keys, boxscore player_id values). |
| `first_name` | string | First name. May be initials only (LSB JV returned single-letter names). |
| `last_name` | string | Last name. |
| `number` | string | Jersey number. **String, not integer.** NOT unique within a team (two players sharing #15 observed). |
| `avatar_url` | string | Avatar URL. Empty string `""` when unset (not null, not absent). Use `.get("avatar_url") or None` to normalize. |

## Example Response

```json
[
  {
    "id": "77c74470-5d1c-4723-a7e3-348c0ed84e5f",
    "first_name": "A",
    "last_name": "REDACTED",
    "number": "15",
    "avatar_url": ""
  },
  {
    "id": "d5645a1b-REDACTED",
    "first_name": "B",
    "last_name": "REDACTED",
    "number": "7",
    "avatar_url": ""
  }
]
```

## Opponent Team Access: root_team_id vs. progenitor_team_id

**Confirmed 2026-03-09:** When viewing an opponent's player roster, the GC web app calls this endpoint using the `root_team_id` (from `GET /teams/{team_id}/opponents`), NOT the `progenitor_team_id`. This was observed with the Nighthawks Navy AAA 14U:

- `root_team_id`: `bd05f3d5-1dfb-47c1-8e81-93c0660eaaef` (local opponent registry ID)
- `progenitor_team_id`: `14fd6cb6-43ab-4c61-a26c-5486c949e7b5` (canonical GC UUID)

The app called `GET /teams/bd05f3d5-.../players` (23+ hits, all 304/200) and simultaneously `GET /teams/14fd6cb6...` (the progenitor) separately for team metadata.

**Implication:** Use `root_team_id` for `/teams/{id}/players` and `/teams/{id}/avatar-image` when fetching opponent roster and avatar. Use `progenitor_team_id` for `/teams/{id}` (team metadata). Both IDs are available from `GET /teams/{team_id}/opponents`.

## Known Limitations

- `first_name` may be initials only -- LSB JV returned single-letter first names ("A", "B"). This is a data-entry pattern on that team, not an API limitation.
- `number` is a string and is NOT unique within a team. Do not use as a key.
- `avatar_url` is an empty string `""` when unset (not null). Normalize with `.get("avatar_url") or None`.
- No pagination observed for 20-player roster. Behavior for larger rosters unknown.
- Auth requirement: captured with gc-token. Whether it works without auth is untested.

**Discovered:** 2026-03-04. **Schema confirmed:** 2026-03-04. **root_team_id for opponents confirmed:** 2026-03-09.
