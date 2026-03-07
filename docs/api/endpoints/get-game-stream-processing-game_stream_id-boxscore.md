---
method: GET
path: /game-stream-processing/{game_stream_id}/boxscore
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Both teams' batting and pitching lines confirmed.
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
last_confirmed: "2026-03-04"
tags: [games, events, player, stats]
caveats:
  - >
    CRITICAL ID MAPPING: The URL parameter is game_stream.id from game-summaries,
    NOT event_id, NOT game_stream.game_id. These are three different UUIDs for the
    same game. Must crawl game-summaries first to get game_stream.id.
  - >
    ASYMMETRIC TOP-LEVEL KEYS: Own team key is the public_id slug (short alphanumeric,
    no dashes); opponent key is a UUID (with dashes). Detect via regex or match against
    known public_id from /me/teams.
related_schemas: []
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Required first -- provides game_stream.id needed for this endpoint's path
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Pitch-by-pitch play data using the same game_stream_id
  - path: /public/game-stream-processing/{game_stream_id}/details
    reason: No-auth inning-by-inning line scores (complementary view of same game)
  - path: /teams/{team_id}/schedule/events/{event_id}/player-stats
    reason: Alternative endpoint returning both teams' per-player stats (includes spray charts)
---

# GET /game-stream-processing/{game_stream_id}/boxscore

**Status:** CONFIRMED LIVE -- 200 OK. Per-game box score for both teams. Last verified: 2026-03-04.

Returns the per-player box score for both teams (home and away) in a single response. Includes batting lines, pitching lines, batting order, positions, and player names. This is the primary source for per-player game stats (alongside the event player-stats endpoint).

**ID chain for this endpoint:**
```
GET /teams/{team_id}/game-summaries -> game_stream.id
  -> GET /game-stream-processing/{game_stream_id}/boxscore (this endpoint)
```

Use `game_stream.id` (NOT `game_stream.game_id`, NOT `event_id`). See [game-summaries](get-teams-team_id-game-summaries.md).

```
GET https://api.team-manager.gc.com/game-stream-processing/{game_stream_id}/boxscore
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_stream_id` | UUID | Game stream identifier. From `game_stream.id` in game-summaries. NOT `event_id`. |

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

Single JSON object. Top-level keys are team identifiers (exactly 2 -- one per team). Keys are asymmetric:
- **Own team:** `public_id` slug (short alphanumeric, no dashes, e.g., `"a1GFM9Ku0BbF"`)
- **Opponent:** UUID (with dashes, e.g., `"f0e73e42-f248-402b-8171-524b4e56a535"`)

Detect which key is which: check if the key matches UUID format (contains dashes) or slug format (alphanumeric only, no dashes).

### Team Entry Structure

| Field | Type | Description |
|-------|------|-------------|
| `players` | array | Roster of players appearing in this game |
| `players[].id` | UUID | Player UUID |
| `players[].first_name` | string | First name |
| `players[].last_name` | string | Last name |
| `players[].number` | string | Jersey number (string) |
| `groups` | array | Stat groups: `[{category: "lineup"}, {category: "pitching"}]` |
| `team_stats` | object | Aggregate team totals for validation |

### `groups` Array

Two groups per team: `category: "lineup"` (batting) and `category: "pitching"`.

Each group contains:
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
| `IP` | int (outs -- 1 IP = 3) |
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
- **`IP` in boxscore is integer outs** (not float innings). `3` = 1 IP, `9` = 3 IP.
- **`team_stats`:** Use for validation -- should match sum of individual player stats.

## Known Limitations

- Asymmetric top-level keys require detection logic. Match against known `public_id` from `/me/teams` or detect by UUID regex.
- `IP` is stored as integer outs in boxscore (different from float innings in season-stats and player-stats).
- `is_primary` field is only in the lineup group, not pitching group.
- `player_text` encoding may be empty for subs.
- No `gc-user-action` observed -- may be optional for this endpoint.

**Discovered:** 2026-03-04. **Schema fully documented:** 2026-03-04.
