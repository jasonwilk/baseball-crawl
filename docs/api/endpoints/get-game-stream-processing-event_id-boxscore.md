---
method: GET
path: /game-stream-processing/{event_id}/boxscore
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Full schema documented. Both teams' batting and pitching lines confirmed.
      Path parameter is event_id -- empirically verified 2026-03-18: event_id
      returns 200, game_stream.id returns 500 (same game, direct A/B test,
      Example Team Freshman). Prior documentation incorrectly identified
      the parameter as game_stream.id.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.event_box_score+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/boxscore-sample.json
raw_sample_size: "13 KB, both teams' batting and pitching lines"
discovered: "2026-03-04"
last_confirmed: "2026-03-18"
tags: [games, events, player, stats]
caveats:
  - >
    CORRECTED ID MAPPING (2026-03-18): The URL parameter is event_id -- NOT
    game_stream.id. In game-summaries: event_id == game_stream.game_id (always
    equal); game_stream.id is a third distinct UUID that returns 500
    {"error":"[scheduling] Cannot find event[...]"}. Direct A/B test confirmed
    2026-03-18 (Example Team Freshman). Prior documentation (2026-03-04,
    2026-03-12) incorrectly identified the parameter as game_stream.id -- likely
    caused by confusion between game_stream.id and game_stream.game_id when
    reading game-summaries records. The /public/teams/{public_id}/games `id` field
    equals event_id (confirmed 2026-03-19) -- it is the public-endpoint equivalent
    of event_id from the authenticated flow.
  - >
    TOP-LEVEL KEYS ARE NOT RELIABLY ASYMMETRIC (corrected 2026-08-02): each team's
    envelope is keyed by that team's public_id slug when the team has a public
    GameChanger presence, and by its UUID otherwise. A slug/UUID pair is the COMMON
    case, not the rule -- when the opponent has also been scored on GC, BOTH keys are
    slugs. Classify by IDENTITY (match a key against your own public_id, then your
    gc_uuid; the other key is the opponent), NEVER by key shape. Shape-based detection
    reads an all-slug payload as having no opponent key and discards the opponent's
    entire batting and pitching envelope.
related_schemas: []
see_also:
  - path: /public/teams/{public_id}/games
    reason: Confirmed event_id source (public path) -- `id` field equals event_id (confirmed 2026-03-19); no bridge call needed
  - path: /teams/{team_id}/game-summaries
    reason: Confirmed event_id source -- use `event_id` field (= game_stream.game_id); NOT game_stream.id
  - path: /game-stream-processing/{event_id}/plays
    reason: Pitch-by-pitch play data using the same event_id path parameter
  - path: /public/game-stream-processing/{game_stream_id}/details
    reason: No-auth inning-by-inning line scores (complementary view of same game)
  - path: /teams/{team_id}/schedule/events/{event_id}/player-stats
    reason: Alternative endpoint returning both teams' per-player stats (includes spray charts)
---

# GET /game-stream-processing/{event_id}/boxscore

**Status:** CONFIRMED LIVE -- 200 OK. Per-game box score for both teams. Last verified: 2026-03-18.

Returns the per-player box score for both teams (home and away) in a single response. Includes batting lines, pitching lines, batting order, positions, and player names. This is the primary source for per-player game stats (alongside the event player-stats endpoint).

**ID source for this endpoint:**

```
GET /teams/{team_id}/game-summaries -> event_id  (= game_stream.game_id -- always equal)
  -> GET /game-stream-processing/{event_id}/boxscore (this endpoint)
```

Use `event_id` from game-summaries. **Do NOT use `game_stream.id`** -- that UUID returns 500 `{"error":"[scheduling] Cannot find event[...]"}`. Confirmed 2026-03-18 via direct A/B test. Prior documentation incorrectly stated the parameter was `game_stream.id`.

```
GET https://api.team-manager.gc.com/game-stream-processing/{event_id}/boxscore
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | The game's `event_id` from game-summaries (= `game_stream.game_id` -- always equal). NOT `game_stream.id` (that UUID returns 500). Corrected 2026-03-18 via direct A/B test. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.event_box_score+json; version=0.0.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

No `gc-user-action` observed for this endpoint.

## Response

Single JSON object. Top-level keys are team identifiers (exactly 2 -- one per team). A key is either:
- a `public_id` slug (short alphanumeric, no dashes, e.g., `"xXxXxXxXxXxX"`) -- used for a team that has a public GameChanger presence, or
- a UUID (with dashes, e.g., `"f0e73e42-f248-402b-8171-524b4e56a535"`) -- used otherwise.

**Which form a key takes is a property of that TEAM, not of which side it is.** A slug (own) + UUID (opponent) pair is common, because most scouted opponents were never scored on GC -- but an opponent that *was* scored on GC gets a slug key too, so both keys are slugs.

Detect which key is which by **identity, not shape**: find the key equal to your own `public_id`, else the key equal to your own `gc_uuid`; the remaining key is the opponent's, whatever its form. A shape-based check ("the one with dashes is the opponent") silently yields *no opponent key* on an all-slug payload and drops that team's whole envelope; it also picks the own key by JSON insertion order, which can load the opponent's stats as yours.

### Team Entry Structure

| Field | Type | Description |
|-------|------|-------------|
| `players` | array | Roster of all players in the game (identity lookup table -- names not in stat entries) |
| `players[].id` | UUID | Player UUID. Matches `player_id` in stat entries. |
| `players[].first_name` | string | First name |
| `players[].last_name` | string | Last name |
| `players[].number` | string | Jersey number (string) |
| `groups` | array | Stat groups: `[{category: "lineup"}, {category: "pitching"}]` |

### `groups` Array

Two groups per team: `category: "lineup"` (batting) and `category: "pitching"`.

Each group contains:
- `category` (string): `"lineup"` or `"pitching"`.
- `team_stats` (object): Aggregate team totals for validation (AB, R, H, RBI, BB, SO for lineup; IP, H, R, ER, BB, SO for pitching). **`team_stats` is a per-group field, not a top-level team field.**
- `stats` (array): Per-player stat lines. Array order = batting order for lineup group.
- `extra` (array): Sparse non-zero stats. Only players with non-zero values listed.

### Main Stats (Always Present Per Player)

**Batting (lineup group):**

| Stat | Type |
|------|------|
| `AB` | int |
| `R` | int |
| `H` | int |
| `RBI` | int |
| `BB` | int |
| `SO` | int |

**Pitching (pitching group):**

| Stat | Type |
|------|------|
| `IP` | float (decimal innings -- 3⅓ IP stored as 3.3333..., 3⅔ IP as 3.6666...) |
| `H` | int |
| `R` | int |
| `ER` | int |
| `BB` | int |
| `SO` | int |

### Sparse Extra Stats Pattern

`extra` array contains `{stat_name: str, stats: [{player_id: uuid, value: int}]}`. Only non-zero players are listed.

**Batting extras:** `2B`, `3B`, `HR`, `TB`, `HBP`, `SB`, `CS`, `E`

**Pitching extras:** `WP`, `HBP`, `#P` (pitch count), `TS` (strikes), `BF` (batters faced)

### Per-Player Stat Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | UUID | Player UUID |
| `stats` | object | Key/value stat pairs (see main stats above) |
| `player_text` | string | **Lineup:** positions played e.g., `"(CF)"`, `"(SS, P)"`. **Pitching:** decision e.g., `"(W)"`, `"(L)"`, `"(SV)"`, `""`. |
| `is_primary` | boolean | **Lineup only:** `false` for substitutes. Absent from pitching group. |

## Key Observations

- **Batting order:** Implicit in `stats` array order within lineup group. Index 0 = leadoff.
- **Substitutes:** `is_primary: false` in lineup group. Subs may have `player_text: ""`.
- **Player names embedded:** No separate `/players` join needed for display names.
- **`IP` in boxscore is float decimal innings** (e.g., `3.3333...` for 3⅓ IP, `3.6666...` for 3⅔ IP -- see Known Limitations). The loader converts this to integer `ip_outs` on ingest.
- **`team_stats`:** Use for validation -- should match sum of individual player stats.

## Known Limitations

- Top-level keys require detection logic, and it must be IDENTITY-based: match a key against your own `public_id`, else your own `gc_uuid`; the other key is the opponent. A UUID regex must NOT be used to decide which side is which (both keys are slugs when the opponent was also scored on GC) -- it is only a last-resort tiebreak when neither identifier is known.
- `IP` is stored as **float decimal innings** (e.g., `3.3333...` for 3⅓ IP, `3.6666...` for 3⅔ IP). CORRECTION: earlier docs incorrectly stated IP was stored as integer outs. Confirmed float from /tmp/lsw-boxscore.json (2026-03-12).
- `is_primary` field is only in the lineup group, not pitching group.
- `player_text` encoding may be empty for subs.
- No `gc-user-action` observed -- may be optional for this endpoint.

**Discovered:** 2026-03-04. **Schema fully documented:** 2026-03-04. **Path parameter corrected:** 2026-03-18 -- parameter is `event_id`, not `game_stream.id` (direct A/B test, Example Team Freshman).
