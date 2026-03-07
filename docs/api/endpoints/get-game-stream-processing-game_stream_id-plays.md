---
method: GET
path: /game-stream-processing/{game_stream_id}/plays
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 58 plays from a 6-inning game (37 KB).
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.event_plays+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/game-plays-sample.json
raw_sample_size: "58 plays, 37 KB, 6-inning game"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [games, events, player, stats]
caveats:
  - >
    CRITICAL ID MAPPING: Same as boxscore -- URL parameter is game_stream.id from
    game-summaries, NOT event_id, NOT game_stream.game_id.
  - >
    PLAYER UUID TEMPLATE PATTERN: All player references are ${uuid} tokens embedded
    in template strings. Must regex-extract (pattern: \$\{([0-9a-f-]{36})\}) and
    resolve against team_players dict.
  - >
    LAST PLAY EDGE CASE: Final play may have name_template.template = "${uuid} at bat"
    with empty at_plate_details and final_details arrays. Skip plays where final_details
    is empty.
related_schemas: []
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Required first -- provides game_stream.id needed for this endpoint's path
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Per-player box score using the same game_stream_id
  - path: /public/game-stream-processing/{game_stream_id}/details
    reason: Inning-by-inning line scores (no-auth) using same game_stream_id
---

# GET /game-stream-processing/{game_stream_id}/plays

**Status:** CONFIRMED LIVE -- 200 OK. 58 plays from a 6-inning game. Last verified: 2026-03-04.

Returns pitch-by-pitch play data for a game. Each play represents one plate appearance with the full pitch sequence, outcome, baserunner events, and in-game substitutions. Uses the same `game_stream_id` as the boxscore endpoint.

**ID chain for this endpoint:**
```
GET /teams/{team_id}/game-summaries -> game_stream.id
  -> GET /game-stream-processing/{game_stream_id}/plays (this endpoint)
```

```
GET https://api.team-manager.gc.com/game-stream-processing/{game_stream_id}/plays
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
Accept: application/vnd.gc.com.event_plays+json; version=0.0.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

No `gc-user-action` observed for this endpoint.

## Response

Single JSON object with three top-level keys.

### Top-Level Structure

| Field | Type | Description |
|-------|------|-------------|
| `sport` | string | Always `"baseball"` |
| `team_players` | object | Roster dict keyed by team identifier (same asymmetric slug/UUID format as boxscore) |
| `plays` | array | Plate appearances in game order |

### `team_players` Dict

Same asymmetric key pattern as boxscore: own team uses `public_id` slug, opponent uses UUID. Each team value maps player UUID to player info:

```json
{
  "a1GFM9Ku0BbF": {
    "<player_uuid>": {"id": "<uuid>", "first_name": "...", "last_name": "..."}
  },
  "<opponent_uuid>": {
    "<player_uuid>": {"id": "<uuid>", "first_name": "...", "last_name": "..."}
  }
}
```

### Play Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `order` | int | Sequential plate appearance number (0-indexed) |
| `inning` | int | Inning number |
| `half` | string | `"top"` or `"bottom"` |
| `name_template` | object | Outcome label. Access as `play["name_template"]["template"]`. |
| `home_score` | int | Cumulative home score after this play |
| `away_score` | int | Cumulative away score after this play |
| `did_score_change` | boolean | Whether the score changed on this play |
| `outs` | int | Running out count (0-3) after this play |
| `did_outs_change` | boolean | Whether outs changed on this play |
| `at_plate_details` | array | Pitch-by-pitch sequence and in-AB events |
| `final_details` | array | Outcome narration |
| `messages` | array | Always empty in observed capture |

### Player UUID Template Pattern

All player references in template strings are `${uuid}` tokens. Extract with regex:

```python
import re
PLAYER_UUID_PATTERN = re.compile(r'\$\{([0-9a-f-]{36})\}')
uuids = PLAYER_UUID_PATTERN.findall(template_string)
```

### `at_plate_details` Array

Each element has a single `template` string field describing the pitch or event:
- Pitches: `"Ball 1"`, `"Strike 1 looking"`, `"Strike 2 swinging"`, `"Foul"`, `"In play"`
- Events: `"Lineup changed: ${uuid} in at pitcher"`, `"Pinch runner ${uuid} in for designated hitter ${uuid}"`
- `"Courtesy runner ${uuid} in for ${uuid}"`

### `final_details` Array

Each element has a `template` string field with the outcome narration:
- `"${uuid} singles on a hard ground ball to shortstop ${uuid}"`
- `"${uuid} flies out to center fielder ${uuid}"`
- `"${uuid} walks"`

Contact quality descriptions include: `"hard ground ball"`, `"line drive"`, `"fly ball"`, `"bunt"`.

### `name_template.template` Values

Outcome label strings (access as `play["name_template"]["template"]`):
- `"Fly Out"`, `"Single"`, `"Walk"`, `"Strikeout"`, `"Error"`, `"Double"`
- `"Hit By Pitch"`, `"Runner Out"`, `"Fielder's Choice"`, `"Pop Out"`
- `"Line Out"`, `"Ground Out"`, `"Triple"`, `"Home Run"`

## Coaching Analytics Extractable from This Endpoint

- Full pitch sequence per at-bat (ball/strike counts, pitch results)
- Stolen base attempts (mid-AB events in `at_plate_details`)
- Contact quality by batted ball type ("hard ground ball" vs "fly ball" vs "line drive")
- Fielder identity on outs (resolve `${uuid}` from `final_details`)
- In-game substitutions and pinch runners (inline in `at_plate_details`)
- Batting order by inning (reconstruct from `order` + `half` + `inning`)

## Known Limitations

- **Last play edge case:** The final play in some games has `name_template.template = "${uuid} at bat"` with empty `at_plate_details` and `final_details` arrays. This represents an incomplete/abandoned at-bat. Skip plays where `final_details` is empty.
- **`messages` array:** Always empty in observed capture (58 plays). Purpose unknown when non-empty.
- Same asymmetric key detection needed as boxscore for `team_players`.
- Reuse boxscore key-detection logic if both endpoints are consumed in the same pipeline.

**Discovered:** 2026-03-04. **Schema fully documented:** 2026-03-04.
