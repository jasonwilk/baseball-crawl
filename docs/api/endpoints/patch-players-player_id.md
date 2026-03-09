---
method: PATCH
path: /players/{player_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: >
      2 hits, status 200. Triggered when viewing an opponent player profile.
      Content-Type: application/vnd.gc.com.patch_player+json; version=0.1.0.
      Discovered 2026-03-09.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.patch_player+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: null
tags: [player, write]
caveats:
  - >
    WRITE OPERATION: Updates player profile attributes. Not relevant to read-only
    data ingestion.
  - >
    OBSERVED CONTEXT: Triggered twice (06:16:46 and 06:16:51) while viewing Justin Werner
    (player_id a473bdac-763d-407b-8a18-b2ac8df925b9) on the opponent player page.
    The GC web app appears to trigger a PATCH when the user sets or edits player
    attributes such as batting side or throwing hand. The player_id is from OUR team
    roster (a473bdac is a Lincoln Rebels player), not the opponent being viewed --
    suggesting the PATCH was on a roster player being updated while navigating.
  - >
    REQUEST BODY UNKNOWN: Body schema not captured. Based on content type
    (patch_player) and context, likely includes player attribute fields such as
    throwing_hand, batting_side, jersey number, or other mutable profile fields.
    Compare with GET /player-attributes/{player_id}/bats for the read equivalent.
  - >
    DISTINCT FROM /me/user PATCH: This endpoint patches a player record, not a user
    account. Player records are the sports-identity objects linked to teams; user
    accounts are authentication identities. Different data models.
related_schemas: []
see_also:
  - path: /player-attributes/{player_id}/bats
    reason: Read equivalent for batting side and throwing hand (GET)
  - path: /teams/{team_id}/players
    reason: Player roster -- source of player_id values for own team
  - path: /teams/{team_id}/opponents/players
    reason: Opponent player roster with handedness (read-only -- no PATCH for opponent players)
---

# PATCH /players/{player_id}

**Status:** OBSERVED (proxy log, 2 hits, status 200). Write operation -- not relevant to read-only data ingestion. Last verified: 2026-03-09.

Updates mutable attributes on a player record. Triggered by the GC web app when a staff member edits player attributes (batting side, throwing hand, jersey number, or other profile fields).

```
PATCH https://api.team-manager.gc.com/players/{player_id}
Content-Type: application/vnd.gc.com.patch_player+json; version=0.1.0
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `player_id` | UUID | Player UUID (from `/teams/{team_id}/players` or `/teams/{team_id}/opponents/players`) |

## Request Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Content-Type: application/vnd.gc.com.patch_player+json; version=0.1.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Request Body

Schema not captured. Based on the content type (`patch_player`) and the context in which this was triggered (player attribute editing screen), expected fields include some subset of:

- `throwing_hand` -- `"right"`, `"left"`, or `"switch"`
- `batting_side` -- `"right"`, `"left"`, or `"switch"`
- `number` -- jersey number (string)
- `first_name`, `last_name` -- name fields

Standard JSON PATCH semantics -- only include fields that are being updated.

## Response

Schema not captured. Status 200 observed. Likely returns the updated player object.

## Known Limitations

- Request body and response body not captured in proxy log.
- Whether staff can PATCH opponent players (vs. only own-team players) is unknown.
- The session context suggests this was triggered by editing a roster player's attributes while navigating the opponent view -- may have been a sidebar or parallel UI action.

**Discovered:** 2026-03-09. Session: 2026-03-09_061156.
