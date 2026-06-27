---
method: GET
path: /players/{player_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Live-verified 2026-06-21 via direct GET against multiple player UUIDs on a
      non-managed (tracked) team -- returns 200 for both active and removed
      records. Reachable without team management. Earlier capture: web proxy
      session 2026-03-11.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.player+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: "1 record"
discovered: "2026-03-11"
last_confirmed: "2026-06-21"
tags: [player, team]
caveats:
  - >
    SCHEMA VARIES BY RECORD: Core fields always present (id, team_id, status,
    first_name, last_name, number, person_id). Two fields are CONDITIONAL:
    `user_id` (present only when the player record is linked to a GameChanger
    user account) and `bats` (an embedded handedness object, observed on some
    records -- so handedness is sometimes inline, not only at
    GET /player-attributes/{player_id}/bats). Do not assume the minimal 7-field
    shape; tolerate the extra optional fields.
  - >
    STATUS ENUM: `status` takes at least `"active"` and `"removed"`. Removed
    records are former/replaced player entries whose historical stats still
    appear in boxscores but which are EXCLUDED from the roster endpoints
    (/teams/public/{public_id}/players and /teams/{team_id}/players). This is
    the discriminator that explains why a team's boxscore identity tables can
    contain more players than its roster. Verified 2026-06-21 (Elkhorn North
    Reserve PkMl2UWGdrgG: 14 active on roster, 11 additional `removed` records
    in boxscores).
  - >
    person_id DOES NOT UNIFY DUPLICATES: `person_id == id` was observed on
    EVERY record sampled (active and removed, with and without a user account).
    It is therefore NOT a cross-record identity key and does NOT link two
    player UUIDs that represent the same human. Two records for one person
    (an early `removed` record and a later `active` record) each carry their
    own `person_id` equal to their own `id`. GameChanger exposes no
    unification field here.
see_also:
  - path: /teams/{team_id}/players
    reason: Returns all players for a team (bulk alternative to per-player fetch)
  - path: /player-attributes/{player_id}/bats
    reason: Batting side and throwing hand for a player
  - path: /players/{player_id}/profile-photo
    reason: Player profile photo URL (returns 404 when not set)
  - path: /athlete-profile/{athlete_profile_id}/players
    reason: Cross-team career view of a player's identity
---

# GET /players/{player_id}

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns individual player metadata for a specific player UUID. Returns the per-team player record (not the cross-team athlete profile). The response is minimal -- it does not include handedness or stats.

```
GET https://api.team-manager.gc.com/players/{player_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `player_id` | UUID | The player UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.player+json; version=0.1.0
```

## Response

**HTTP 200.** Single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Player UUID (same as path param) |
| `team_id` | UUID | The team this player record belongs to |
| `status` | string | Player status. Observed values: `"active"`, `"removed"`. Roster endpoints return only `active` records. |
| `first_name` | string | Player first name |
| `last_name` | string | Player last name |
| `number` | string | Jersey number as string. Empty string `""` for many `removed` records. |
| `person_id` | UUID | Person UUID. Observed equal to `id` on every record (active and removed). NOT a cross-record unification key -- see caveats. |
| `user_id` | UUID | **Optional.** Present only when the record is linked to a GameChanger user account. Absent on unlinked (typically `removed`) records. This -- not `person_id` -- is the "has a user account" signal. |
| `bats` | object | **Optional.** Embedded handedness `{throwing_hand, batting_side, player_id}`. Observed on some records; absent on others. |

## Example Response

Active record linked to a user account:

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "user_id": "00000000-0000-0000-0000-000000000002",
  "team_id": "00000000-0000-0000-0000-000000000003",
  "status": "active",
  "first_name": "Jane",
  "last_name": "Doe",
  "number": "7",
  "person_id": "00000000-0000-0000-0000-000000000001"
}
```

Removed record (no user account, jersey cleared, handedness inline):

```json
{
  "id": "00000000-0000-0000-0000-000000000004",
  "team_id": "00000000-0000-0000-0000-000000000003",
  "status": "removed",
  "first_name": "Player",
  "last_name": "One",
  "number": "",
  "bats": {
    "throwing_hand": "right",
    "batting_side": "right",
    "player_id": "00000000-0000-0000-0000-000000000004"
  },
  "person_id": "00000000-0000-0000-0000-000000000004"
}
```

**Note:** `person_id == id` on every record observed (active and removed, with and without a user account), so it is NOT a signal of a user account and NOT a key that unifies duplicate player records for the same human. The presence of `user_id` is the actual "claimed by a user account" signal.

**Coaching relevance: LOW.** Most player data is more efficiently retrieved via `/teams/{team_id}/players` (bulk). Use this endpoint only when a specific player UUID is known and a quick identity lookup is needed.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
