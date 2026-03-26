# Play-by-Play Data Ingestion — Developer Reference

This document covers the full pipeline for fetching and storing pitch-by-pitch play data from the GameChanger API: which endpoint to call, how to discover event IDs, how to parse the response, how to resolve player names, and how to store the data idempotently.

**Confirmed:** 2026-03-26. Endpoint re-verified via fresh browser curl and Python client fix applied.

---

## 1. Overview

The plays endpoint returns every plate appearance in a game, with the full pitch sequence, outcome narration, baserunner events, and in-game substitutions — all as template strings with `${uuid}` tokens that resolve to player names via a roster dict in the same response.

One call per game. No pagination. Not restricted to teams you manage. Works for opponent games.

**Critical ID fact:** The path parameter is `event_id` (= `game_stream.game_id` from game-summaries). It is **NOT** `game_stream.id`. These are two different UUIDs. Our Python client previously sent `game_stream.id` and received HTTP 500 — confirmed root cause 2026-03-26. Always use `event_id`.

---

## 2. Endpoint Reference

```
GET https://api.team-manager.gc.com/game-stream-processing/{event_id}/plays
```

Full endpoint specification: `docs/api/endpoints/get-game-stream-processing-event_id-plays.md`

### Required Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.event_plays+json; version=0.0.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36
```

No `gc-user-action` header is sent for this endpoint.

### Path Parameters

| Parameter | Source | Notes |
|-----------|--------|-------|
| `event_id` | `game_summaries.json` → top-level `event_id` field | Equals `game_stream.game_id`. NOT `game_stream.id`. |

### Response

Single JSON object (not paginated). HTTP 200 on success.

| Status | Meaning |
|--------|---------|
| 200 | OK — full play data returned |
| 401 | Auth expired — rotate token, retry |
| 404 | `event_id` not found — verify you are sending `event_id`, not `game_stream.id` |
| 500 | Wrong ID sent (legacy — sending `game_stream.id` instead of `event_id`), or incomplete game stream |

**Access scope:** This endpoint is NOT restricted to teams the authenticated user manages. Any `event_id` discoverable via the public API (opponent schedules, our own schedules) returns full play-by-play data with player names. Confirmed 2026-03-26.

---

## 3. Discovering event_ids

### Own-Team Games

The game loader stores `event_id` in the `games` table. Query:

```sql
SELECT game_id FROM games WHERE home_team_id = ? OR away_team_id = ?
```

`games.game_id` is the `event_id` (see CLAUDE.md Data Model section). Use this for plays just as you use it for the boxscore.

Alternatively, load `data/raw/{season}/teams/{gc_uuid}/game_summaries.json` — the top-level `event_id` field in each game object is the plays path parameter.

### Opponent Games

Use the opponent's public schedule endpoint to enumerate their games:

```
GET /public/teams/{public_id}/games
```

Each game object includes an `event_id` (or `id` depending on the endpoint variant). The same `event_id` identifies the game from both teams' perspectives — there is no per-team variant of the plays URL.

### ID Chain Summary

```
GET /teams/{team_id}/game-summaries
  → event_id (top-level field)
  → GET /game-stream-processing/{event_id}/plays   ← THIS ENDPOINT

game_summaries also returns:
  → game_stream.id    (NOT the plays path parameter — DO NOT use here)
  → game_stream.game_id  (= event_id — same UUID, different field name)
```

---

## 4. Response Structure

The response has three top-level keys:

```json
{
  "sport": "baseball",
  "team_players": { ... },
  "plays": [ ... ]
}
```

### `team_players`

Roster dict used to resolve `${uuid}` tokens in template strings. Keys are team identifiers with an **asymmetric format**:

- **Own team**: Short alphanumeric `public_id` slug (e.g., `"xXxXxXxXxXxX"`)
- **Opponent team**: UUID string (e.g., `"00000000-0000-0000-0000-000000000002"`)

Each key maps to an **array** of player objects — NOT a nested dict keyed by player UUID:

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

**Common mistake:** Do not index `team_players` by UUID key — the values are arrays that must be iterated to find a player by their `id` field.

### `plays`

Array of play objects in game order. Each play is one plate appearance:

| Field | Type | Description |
|-------|------|-------------|
| `order` | int | Sequential plate appearance index (0-based) |
| `inning` | int | Inning number |
| `half` | string | `"top"` or `"bottom"` |
| `name_template` | object | Outcome label — access as `play["name_template"]["template"]` |
| `home_score` | int | Cumulative home score after this play |
| `away_score` | int | Cumulative away score after this play |
| `did_score_change` | boolean | Score changed on this play |
| `outs` | int | Running out count (0–3) after this play |
| `did_outs_change` | boolean | Outs changed on this play |
| `at_plate_details` | array | Pitch-by-pitch and mid-AB events (each has a `template` string) |
| `final_details` | array | Outcome narration (each has a `template` string) |
| `messages` | array | Always empty in observed captures |

---

## 5. Player Name Resolution

All player references in template strings are `${uuid}` tokens. Resolution procedure:

**Step 1 — Build a lookup dict** at the start of each game:

```python
import re

PLAYER_UUID_PATTERN = re.compile(r'\$\{([0-9a-f-]{36})\}')

def build_player_lookup(team_players: dict) -> dict:
    """Returns {player_uuid: {"first_name": ..., "last_name": ..., "number": ...}}"""
    lookup = {}
    for team_key, players in team_players.items():
        for player in players:          # players is an array, not a dict
            lookup[player["id"]] = player
    return lookup
```

**Step 2 — Extract UUIDs from a template** and look up names:

```python
def resolve_template(template: str, player_lookup: dict) -> str:
    def replace(m):
        uuid = m.group(1)
        p = player_lookup.get(uuid)
        if p:
            return f"{p['first_name']} {p['last_name']}"
        return f"Unknown ({uuid[:8]})"
    return PLAYER_UUID_PATTERN.sub(replace, template)
```

**Step 3 — Apply to both template fields:**

```python
for play in plays:
    outcome = resolve_template(
        play["name_template"]["template"], player_lookup
    )
    details = [
        resolve_template(d["template"], player_lookup)
        for d in play["final_details"]
    ]
    pitch_seq = [
        resolve_template(d["template"], player_lookup)
        for d in play["at_plate_details"]
    ]
```

---

## 6. Template Vocabulary

Templates are free-text strings. The values below are all observed values from confirmed captures — treat as representative, not exhaustive.

### `name_template.template` — Plate Appearance Outcome

```
Fly Out      Ground Out    Pop Out      Line Out
Single       Double        Triple       Home Run
Walk         Strikeout     Hit By Pitch
Error        Fielder's Choice    Runner Out
${uuid} at bat          ← incomplete/abandoned at-bat (see Section 10)
```

### `at_plate_details[].template` — Pitch Sequence and Mid-AB Events

**Pitch count events:**
```
Ball 1  Ball 2  Ball 3  Ball 4
Strike 1 looking    Strike 1 swinging
Strike 2 looking    Strike 2 swinging
Strike 3 looking    Strike 3 swinging
Foul    Foul tip    In play
```

**Baserunner events (mid-at-bat):**
```
${uuid} advances to 2nd on error by pitcher ${uuid}
${uuid} advances to 2nd on the same pitch
${uuid} advances to 2nd on wild pitch
${uuid} advances to 3rd on passed ball
${uuid} advances to 3rd on wild pitch
${uuid} scores on error by catcher ${uuid}
${uuid} scores on error by shortstop ${uuid}
${uuid} scores on passed ball
${uuid} scores on wild pitch
${uuid} steals 2nd
${uuid} steals 3rd
Pickoff attempt at 1st
```

**Substitution events:**
```
Lineup changed: ${uuid} in at pitcher
Lineup changed: ${uuid} in for batter ${uuid}
${uuid} in for pitcher ${uuid}
Courtesy runner ${uuid} in for ${uuid}
(Play Edit) ${uuid} in for ${uuid}
```

### `final_details[].template` — Outcome Narration

**Outs:**
```
${uuid} flies out to right fielder ${uuid}
${uuid} grounds out to first baseman ${uuid}
${uuid} grounds out, pitcher ${uuid} to first baseman ${uuid}
${uuid} grounds out, second baseman ${uuid} to first baseman ${uuid}
${uuid} pops out in foul territory to first baseman ${uuid}
${uuid} pops out to first baseman ${uuid}
${uuid} pops out to third baseman ${uuid}
${uuid} is out on foul tip, ${uuid} pitching
${uuid} strikes out looking, ${uuid} pitching
${uuid} strikes out swinging, ${uuid} pitching
```

**Hits:**
```
${uuid} singles on a bunt to third baseman ${uuid}
${uuid} singles on a fly ball to {position} ${uuid}
${uuid} singles on a ground ball to second baseman ${uuid}
${uuid} singles on a hard ground ball to {position} ${uuid}
${uuid} singles on a line drive to center fielder ${uuid}
${uuid} doubles on a fly ball to left fielder ${uuid}
${uuid} doubles on a hard ground ball to left fielder ${uuid}
${uuid} doubles on a line drive to left fielder ${uuid}
```

**Errors:**
```
${uuid} hits a ground ball and reaches on an error by shortstop ${uuid}
${uuid} hits a hard ground ball and reaches on an error by shortstop ${uuid}
${uuid} hits a hard ground ball and reaches on an error by third baseman ${uuid}
```

**Walks / HBP:**
```
${uuid} walks, ${uuid} pitching
${uuid} is hit by pitch, ${uuid} pitching
```

**Trailing baserunner outcomes (accompany the primary outcome):**
```
${uuid} advances to 2nd
${uuid} advances to 3rd
${uuid} advances to 2nd on the same error
${uuid} advances to 2nd on the throw
${uuid} remains at 1st
${uuid} remains at 2nd
${uuid} remains at 3rd
${uuid} scores
${uuid} scores on the throw
```

---

## 7. Pagination

**None.** The endpoint returns all plays for a game in a single response object. There are no pagination headers (`x-pagination`, `x-next-page`) and no cursor or page parameters.

Largest confirmed capture: 58 plays from a 6-inning game (37 KB). A 9-inning game with roughly 70–80 plate appearances produces a response in the 45–55 KB range — well within a single HTTP response. Do not implement pagination handling for this endpoint.

---

## 8. Recommended Storage Schema

The schema below is suggested for a `plays` table. Adapt to your needs.

```sql
CREATE TABLE plays (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT    NOT NULL REFERENCES games(game_id),
    play_order      INTEGER NOT NULL,           -- `order` field (0-based)
    inning          INTEGER NOT NULL,
    half            TEXT    NOT NULL,           -- 'top' or 'bottom'
    outcome         TEXT,                       -- name_template.template (resolved)
    home_score      INTEGER,
    away_score      INTEGER,
    did_score_change INTEGER,                   -- 0/1
    outs            INTEGER,
    did_outs_change INTEGER,                    -- 0/1
    pitch_sequence  TEXT,                       -- JSON array of at_plate_details templates
    final_detail    TEXT,                       -- JSON array of final_details templates
    season_year     INTEGER,
    UNIQUE(game_id, play_order)                 -- idempotency key
);
```

**Notes:**
- Store templates as resolved human-readable strings OR as raw `${uuid}` strings — resolved is more useful for display; raw is smaller and re-resolvable later. Choose based on your downstream needs.
- `UNIQUE(game_id, play_order)` is a safe idempotency key because `order` is sequential and deterministic per game.
- `pitch_sequence` and `final_detail` as JSON-encoded arrays keep the schema flat while preserving multi-event structure.
- Add `pitcher_id`, `batter_id`, `fielder_ids` UUID columns if you need player-linked analytics queries.

---

## 9. Idempotency Strategy

Use `INSERT OR IGNORE` on the `UNIQUE(game_id, play_order)` constraint. Re-running the loader for the same game produces zero new inserts — existing rows are silently skipped.

```python
cursor.execute("""
    INSERT OR IGNORE INTO plays
        (game_id, play_order, inning, half, outcome, ...)
    VALUES (?, ?, ?, ?, ?, ...)
""", (game_id, play["order"], play["inning"], play["half"], outcome, ...))
```

Do NOT delete-and-reinsert. Partial failures are safe — already-stored plays persist, new plays append on the next run.

---

## 10. Coverage Notes and Edge Cases

### Scorekeeper Dependency

Play data is recorded by volunteer scorekeepers in real time. Coverage is game-dependent, not 100%.

- Games with no scorekeeper produce no `plays` entries (empty array) or may not appear in game-summaries at all.
- Partially-scored games may have plays for some innings only.

### HTTP 500 History — Wrong ID

Our Python client received HTTP 500 for all Freshman team games from 2026-03-04 through 2026-03-26. Root cause: the client was sending `game_stream.id` as the path parameter instead of `event_id`. These are two different UUIDs that live in the same game-summaries response object.

**Fix:** Use `event_id` (top-level field in game-summaries). This equals `game_stream.game_id` — a second way to access the same value. Never use `game_stream.id` for the plays or boxscore endpoints.

Confirmed fix 2026-03-26 via browser curl: `event_id` → HTTP 200; `game_stream.id` → HTTP 500.

### Last Play Edge Case

The final entry in `plays` may represent an incomplete or abandoned at-bat:

```json
{
  "name_template": {"template": "${uuid} at bat"},
  "at_plate_details": [],
  "final_details": []
}
```

**Skip plays where `final_details` is empty.** These are not completed plate appearances and contain no outcome data to store.

Detection:
```python
for play in response["plays"]:
    if not play["final_details"]:
        continue  # abandoned at-bat — skip
    # ... process play
```

### `messages` Array

Always empty in all observed captures (58-play game, 72-play game). Purpose unknown. Skip for now.

---

## 11. Relationship to Spray Charts

The plays endpoint and the spray chart endpoint cover different layers of the same game. They are complementary, not redundant.

| | Plays endpoint | Spray chart endpoint |
|---|---|---|
| **URL** | `GET /game-stream-processing/{event_id}/plays` | `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` |
| **Path parameter** | `event_id` | `event_id` (same UUID) |
| **Auth** | Required | Required |
| **Content** | Pitch sequence, outcome type, baserunner events, substitutions | Ball-in-play x/y coordinates, play result, fielder position |
| **Coverage** | Scorekeeper-dependent | ~93% offensive, ~16% defensive |
| **Player resolution** | `${uuid}` tokens, resolved via `team_players` in response | Player UUIDs as dict keys — look up via `players` table |
| **Idempotency key** | `(game_id, play_order)` | `event_gc_id` (UUID on each spray event) |

**Key overlap:** `name_template.template` (plays) and `spray_chart_data[player_uuid][].attributes.playResult` (spray charts) both describe the plate appearance outcome, but use different vocabulary (`"Single"` vs `"single"`, `"Ground Out"` vs `"batter_out"`). They cannot be joined directly on outcome string; use `game_id` + player identity + approximate sequence position if correlation is needed.

Both endpoints use `event_id` as the path parameter — not `game_stream.id`.

**See also:**
- `docs/api/endpoints/get-game-stream-processing-event_id-plays.md` — Full endpoint spec with all confirmed template values
- `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md` — Spray chart data endpoint
- `docs/api/flows/spray-chart-rendering.md` — Spray chart coordinate transform and rendering pipeline
- `docs/api/endpoints/get-teams-team_id-game-summaries.md` — Source of `event_id` values
