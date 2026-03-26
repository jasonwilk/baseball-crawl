---
method: GET
path: /game-stream-processing/{event_id}/plays
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Full schema documented. 58 plays from a 6-inning game (37 KB). Confirmed
      2026-03-26 via fresh browser curl using event_id as path parameter.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.event_plays+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/game-plays-fresh.json
raw_sample_size: "58 plays, 37 KB, 6-inning game"
discovered: "2026-03-04"
last_confirmed: "2026-03-26"
tags: [games, events, player, stats]
caveats:
  - >
    NOT RESTRICTED TO MANAGED TEAMS: Confirmed 2026-03-26 -- event_id
    2baad490-68f2-49e5-b034-be21e0ca7db1 returned HTTP 200 with full play-by-play
    data (player names, pitch sequences, outcomes) for a game involving teams the
    authenticated user does NOT manage. This event was confirmed absent from our
    local games table. Any event_id discoverable via the public API (e.g., from
    opponent schedules) can be used to fetch plays with a standard gc-token.
  - >
    CRITICAL ID MAPPING: The URL path parameter is `event_id` from game-summaries
    (top-level field). This equals `game_stream.game_id` but is NOT `game_stream.id`.
    Confirmed 2026-03-26: browser curl using event_id returned 200; our Python client
    previously got 500 likely because it was sending game_stream.id per the old (wrong)
    doc. The old doc caveat "NOT event_id" was incorrect -- event_id IS the correct parameter.
  - >
    PLAYER UUID TEMPLATE PATTERN: All player references are ${uuid} tokens embedded
    in template strings. Must regex-extract (pattern: \$\{([0-9a-f-]{36})\}) and
    resolve against team_players array by matching player id field.
  - >
    team_players STRUCTURE: Each team key maps to an ARRAY of player objects
    (not a nested dict keyed by player UUID as the old doc claimed). Player objects
    include id, first_name, last_name, and number (jersey number).
  - >
    LAST PLAY EDGE CASE: Final play may have name_template.template = "${uuid} at bat"
    with empty at_plate_details and final_details arrays. Skip plays where final_details
    is empty.
related_schemas: []
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Required first -- provides event_id (top-level field) needed for this endpoint's path
  - path: /game-stream-processing/{event_id}/boxscore
    reason: Per-player box score using the same event_id
  - path: /public/game-stream-processing/{game_stream_id}/details
    reason: Inning-by-inning line scores (no-auth) using game_stream.id (different ID!)
---

# GET /game-stream-processing/{event_id}/plays

**Status:** CONFIRMED LIVE -- 200 OK. 58 plays from a 6-inning game. Last verified: 2026-03-26.

Returns pitch-by-pitch play data for a game. Each play represents one plate appearance with the full pitch sequence, outcome, baserunner events, and in-game substitutions.

**ID chain for this endpoint:**
```
GET /teams/{team_id}/game-summaries -> event_id (top-level field)
  -> GET /game-stream-processing/{event_id}/plays (this endpoint)
```

> **ID WARNING**: Use `event_id` (= `game_stream.game_id`) as the path parameter.
> Do NOT use `game_stream.id` -- that is a different UUID and caused HTTP 500 in our Python client.
> Both boxscore and plays endpoints use `event_id`.

```
GET https://api.team-manager.gc.com/game-stream-processing/{event_id}/plays
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | From `event_id` top-level field in game-summaries. Equals `game_stream.game_id`. NOT `game_stream.id`. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.event_plays+json; version=0.0.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36
```

No `gc-user-action` observed for this endpoint.

## Response

Single JSON object with three top-level keys.

### Top-Level Structure

| Field | Type | Description |
|-------|------|-------------|
| `sport` | string | Always `"baseball"` |
| `team_players` | object | Roster dict keyed by team identifier (asymmetric slug/UUID format -- own team uses public_id slug, opponent uses UUID) |
| `plays` | array | Plate appearances in game order |

### `team_players` Dict

Each team key maps to an **array** of player objects (NOT a nested dict keyed by player UUID):

```json
{
  "xXxXxXxXxXxX": [
    {"id": "72bb77d8-REDACTED", "first_name": "Player", "last_name": "One", "number": "25"},
    {"id": "72bb77d8-REDACTED", "first_name": "Player", "last_name": "Two", "number": "2"}
  ],
  "00000000-0000-0000-0000-000000000002": [
    {"id": "72bb77d8-REDACTED", "first_name": "Player", "last_name": "Three", "number": "10"}
  ]
}
```

**Asymmetric key pattern:** Own team uses `public_id` slug (short alphanumeric), opponent uses UUID. Reuse boxscore key-detection logic if both endpoints are consumed in the same pipeline.

**Player object fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Player identifier (used in `${uuid}` template tokens) |
| `first_name` | string | Player first name |
| `last_name` | string | Player last name |
| `number` | string | Jersey number |

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

Then resolve against `team_players` by searching each team's player array for matching `id`.

### `at_plate_details` Array

Each element has a single `template` string field. Observed values:

**Pitch events:**
- `"Ball 1"`, `"Ball 2"`, `"Ball 3"`, `"Ball 4"`
- `"Strike 1 looking"`, `"Strike 1 swinging"`
- `"Strike 2 looking"`, `"Strike 2 swinging"`
- `"Strike 3 looking"`, `"Strike 3 swinging"`
- `"Foul"`, `"Foul tip"`
- `"In play"`

**Baserunner events (mid-AB):**
- `"${uuid} advances to 2nd on error by pitcher ${uuid}"`
- `"${uuid} advances to 2nd on the same pitch"`
- `"${uuid} advances to 2nd on wild pitch"`
- `"${uuid} advances to 3rd on passed ball"`
- `"${uuid} advances to 3rd on wild pitch"`
- `"${uuid} scores on error by catcher ${uuid}"`
- `"${uuid} scores on error by shortstop ${uuid}"`
- `"${uuid} scores on passed ball"`
- `"${uuid} scores on wild pitch"`
- `"${uuid} steals 2nd"`
- `"${uuid} steals 3rd"`
- `"Pickoff attempt at 1st"`

**Substitution events:**
- `"Lineup changed: ${uuid} in at pitcher"`
- `"Lineup changed: ${uuid} in for batter ${uuid}"`
- `"${uuid} in for pitcher ${uuid}"`
- `"Courtesy runner ${uuid} in for ${uuid}"`
- `"(Play Edit) ${uuid} in for ${uuid}"`

### `final_details` Array

Each element has a `template` string field with the outcome narration. Observed values:

**Outs:**
- `"${uuid} flies out to right fielder ${uuid}"`
- `"${uuid} grounds out to first baseman ${uuid}"`
- `"${uuid} grounds out, pitcher ${uuid} to first baseman ${uuid}"`
- `"${uuid} grounds out, second baseman ${uuid} to first baseman ${uuid}"`
- `"${uuid} pops out in foul territory to first baseman ${uuid}"`
- `"${uuid} pops out to first baseman ${uuid}"`
- `"${uuid} pops out to third baseman ${uuid}"`
- `"${uuid} is out on foul tip, ${uuid} pitching"`
- `"${uuid} strikes out looking, ${uuid} pitching"`
- `"${uuid} strikes out swinging, ${uuid} pitching"`

**Hits:**
- `"${uuid} singles on a bunt to third baseman ${uuid}"`
- `"${uuid} singles on a fly ball to {position} ${uuid}"`
- `"${uuid} singles on a ground ball to second baseman ${uuid}"`
- `"${uuid} singles on a hard ground ball to {position} ${uuid}"`
- `"${uuid} singles on a line drive to center fielder ${uuid}"`
- `"${uuid} doubles on a fly ball to left fielder ${uuid}"`
- `"${uuid} doubles on a hard ground ball to left fielder ${uuid}"`
- `"${uuid} doubles on a line drive to left fielder ${uuid}"`

**Errors:**
- `"${uuid} hits a ground ball and reaches on an error by shortstop ${uuid}"`
- `"${uuid} hits a hard ground ball and reaches on an error by shortstop ${uuid}"`
- `"${uuid} hits a hard ground ball and reaches on an error by third baseman ${uuid}"`

**Walks / HBP:**
- `"${uuid} walks, ${uuid} pitching"`
- `"${uuid} is hit by pitch, ${uuid} pitching"`

**Baserunner outcomes (trailing, accompanying primary outcome):**
- `"${uuid} advances to 2nd"`, `"${uuid} advances to 3rd"`
- `"${uuid} advances to 2nd on the same error"`
- `"${uuid} advances to 2nd on the throw"`
- `"${uuid} remains at 1st"`, `"${uuid} remains at 2nd"`, `"${uuid} remains at 3rd"`
- `"${uuid} scores"`, `"${uuid} scores on the throw"`

### `name_template.template` Values

Outcome label strings (access as `play["name_template"]["template"]`):
- `"Fly Out"`, `"Ground Out"`, `"Pop Out"`, `"Line Out"`
- `"Single"`, `"Double"`, `"Triple"`, `"Home Run"`
- `"Walk"`, `"Strikeout"`, `"Hit By Pitch"`
- `"Error"`, `"Fielder's Choice"`, `"Runner Out"`
- `"${uuid} at bat"` -- incomplete/abandoned at-bat (see Known Limitations)

## Example Response (Truncated, Redacted)

```json
{
  "sport": "baseball",
  "team_players": {
    "xXxXxXxXxXxX": [
      {"id": "72bb77d8-REDACTED", "first_name": "Player", "last_name": "One", "number": "25"}
    ],
    "00000000-0000-0000-0000-000000000002": [
      {"id": "72bb77d8-REDACTED", "first_name": "Player", "last_name": "Three", "number": "10"}
    ]
  },
  "plays": [
    {
      "order": 0,
      "inning": 1,
      "half": "top",
      "name_template": {"template": "Walk"},
      "home_score": 0,
      "away_score": 0,
      "did_score_change": false,
      "outs": 0,
      "did_outs_change": false,
      "at_plate_details": [
        {"template": "Lineup changed: ${00000000-0000-0000-0000-000000000001} in at pitcher"},
        {"template": "Ball 1"},
        {"template": "Ball 2"},
        {"template": "Ball 3"},
        {"template": "Ball 4"}
      ],
      "final_details": [
        {"template": "${00000000-0000-0000-0000-000000000001} walks, ${00000000-0000-0000-0000-000000000001} pitching"}
      ],
      "messages": []
    }
  ]
}
```

## Coaching Analytics Extractable from This Endpoint

- Full pitch sequence per at-bat (ball/strike counts, pitch results)
- Stolen base attempts (`steals 2nd/3rd` in `at_plate_details`)
- Wild pitch / passed ball events (`advances on wild pitch`, `scores on passed ball`)
- Contact quality by batted ball type ("hard ground ball" vs "fly ball" vs "line drive")
- Fielder identity on outs (resolve `${uuid}` from `final_details`)
- In-game substitutions and pinch runners (inline in `at_plate_details`)
- Batting order by inning (reconstruct from `order` + `half` + `inning`)
- Score progression play-by-play (`home_score` / `away_score` per play)

## Known Limitations

- **Access scope:** This endpoint is NOT restricted to teams the authenticated user manages. Confirmed 2026-03-26: a game not in our local `games` table (non-managed teams) returned HTTP 200 with full play-by-play data. Any `event_id` discoverable via the public API (e.g., from opponent schedules) can be fetched with a standard gc-token. This makes the endpoint suitable for opponent scouting without special access.
- **Last play edge case:** The final play in some games has `name_template.template = "${uuid} at bat"` with empty `at_plate_details` and `final_details` arrays. This represents an incomplete/abandoned at-bat. Skip plays where `final_details` is empty.
- **`messages` array:** Always empty in observed capture (58 plays). Purpose unknown when non-empty.
- **Python client 500 history:** Our client previously received HTTP 500 on this endpoint. Root cause was using `game_stream.id` instead of `event_id` as the path parameter. Confirmed fixed by using `event_id`.
- Reuse boxscore key-detection logic for `team_players` asymmetric key pattern.

**Discovered:** 2026-03-04. **Schema corrected and re-confirmed:** 2026-03-26.
