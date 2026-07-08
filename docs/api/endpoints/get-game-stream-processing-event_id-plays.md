---
method: GET
path: /game-stream-processing/{event_id}/plays
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Full schema documented. 9,398 plays across 165 games (4 teams). Confirmed
      2026-03-26 via fresh browser curl using event_id as path parameter.
      Re-confirmed 2026-06-28 via live pulls; surfaced the trailing pitch
      parenthetical (type and/or MPH speed; see "Pitch annotation" in the
      at_plate_details section). Pitch timing/structured pitch fields live in
      the raw game-streams events endpoint, not here.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.event_plays+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/game-plays-fresh.json
raw_sample_size: "9,398 plays across 165 games (4 teams)"
discovered: "2026-03-04"
last_confirmed: "2026-06-28"
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
    ABANDONED/IN-PROGRESS PA EDGE CASE: A play with name_template.template = "${uuid} at bat"
    and empty final_details is an unresolved PA. Usually at_plate_details is also empty, but
    it CAN carry charted pitches while final_details is empty (verified 2026-06-28). The
    skip-on-empty-final_details rule deliberately discards those pitches (no batter outcome
    to attribute) -- do not assume empty final_details implies empty at_plate_details.
  - >
    PITCH TEMPLATE GRAMMAR: at_plate_details pitch templates are a base result plus an
    OPTIONAL single trailing parenthetical carrying speed and/or type -- "(Fastball)",
    "(101 MPH Curveball)", or "(75 MPH)". Earlier "147 normalized patterns" framing
    normalized this away and caused the parser to drop annotated pitches. Strip
    \s*\([^)]*\)\s*$ then match the base; sub-parse inner with ^(?:(\d+)\s*MPH\s*)?(.*?)$.
    No pitch timestamp in this payload; structured pitch fields + per-pitch createdAt are
    in GET /game-streams/{game_stream_id}/events.
related_schemas: []
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Required first -- provides event_id (top-level field) needed for this endpoint's path
  - path: /game-stream-processing/{event_id}/boxscore
    reason: Per-player box score using the same event_id
  - path: /public/game-stream-processing/{game_stream_id}/details
    reason: Inning-by-inning line scores (no-auth); accepts either event_id or game_stream.id -- the same event_id works there too
---

# GET /game-stream-processing/{event_id}/plays

**Status:** CONFIRMED LIVE -- 200 OK. Original schema sample: 9,398 plays across 165 games (4 teams). Pitch-template grammar re-documented and ground-truthed 2026-06-28 against real team-133 games (bare/type-only) and a controlled test team that charted speed + type. Last verified: 2026-06-28.

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

> **Source-of-truth map (which endpoint has what).** This plays endpoint is the PROCESSED/FLATTENED view. Three things are NOT in this payload:
> - **Pitch TIME and clean structured speed/type** → `GET /game-streams/{game_stream_id}/events` (the typed `pitch` event: `result`/`speed`/`speedProvider`/`style` + per-pitch `createdAt`). The plays `"(101 MPH Curveball)"` template suffix is a flattened render of those structured fields; plays carries no timestamp at all.
> - **Ball-in-play x/y coordinates** → the spray-chart / player-stats endpoint `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` (`spray_chart_data...defenders[].location.{x,y}`), already ingested into `spray_charts`.
> - **What plays DOES carry:** the pitch sequence as template strings (base result + optional `(speed/type)` suffix), the outcome via `name_template`, and `final_details` free-text narration (contact quality, fielder, result) — text only, no coordinates.

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
| `messages` | array | Free-text scorekeeper notes (mound visits, delays, game times). Usually empty; ~130 non-empty across 165 games. |

### Player UUID Template Pattern

All player references in template strings are `${uuid}` tokens. Extract with regex:

```python
import re
PLAYER_UUID_PATTERN = re.compile(r'\$\{([0-9a-f-]{36})\}')
uuids = PLAYER_UUID_PATTERN.findall(template_string)
```

Then resolve against `team_players` by searching each team's player array for matching `id`.

### `at_plate_details` Array

Each element is a **single-key object** — `{"template": "<string>"}` — with no other field. Pitch result, pitch type, and pitch speed are all encoded INSIDE the template string (see Pitch event grammar); there is **no timestamp** at this or any level of the plays payload (see "No pitch timestamp" below).

Two classes of event appear in this array, distinguished only by the template string:

1. **Pitch events** — one per pitch thrown (the pitch sequence). A fixed base result, optionally annotated with speed and/or pitch type.
2. **Mid-AB events** — baserunner movement, steals, pickoffs, balks, substitutions — `${uuid}`-bearing free-text, catalogued after the grammar.

> **Why this section was rewritten (the parser bug):** an earlier version of this doc described `at_plate_details` as "147 normalized unique patterns across 9,398 plays." That count was produced by NORMALIZING the trailing pitch parenthetical away — which erased the real grammar below and is the direct cause of the plays-parser regression: the parser (built against the normalized vocabulary, exact-matching bare templates) silently dropped every annotated pitch, yielding `pitch_count = 0` and `is_first_pitch_strike = 0` for any game charted with pitch type/speed. Do NOT reintroduce a normalized-pattern framing; document the actual grammar. Re-verified 2026-06-28 against real team-133 games (type-only / bare) and a controlled test team `dw3a8qivTMvA` that charted speed + type.

#### Pitch event grammar

A pitch event template is a **base result** plus an **optional single trailing parenthetical**:

```
<pitch-template> = <base> [ " (" <annotation> ")" ]
<base>           = "Ball 1" | "Ball 2" | "Ball 3" | "Ball 4"
                 | "Strike {1,2,3} looking" | "Strike {1,2,3} swinging"
                 | "Foul" | "Foul tip" | "Foul bunt" | "In play"
<annotation>     = <speed> " MPH " <type>      ; speed + type
                 | <speed> " MPH"              ; speed only
                 | <type>                      ; type only
<speed>          = integer, unit "MPH" (uppercase)
<type>           = Fastball | Curveball | Slider | Changeup | Cutter | Unclear
```

The annotation is ALWAYS a single trailing `(...)` group — never mid-template, never two parentheticals. Speed (when present) precedes the type; either component may be absent. Worked examples (all real forms; bare and annotated can interleave within one game):

| Template | base | speed_mph | pitch_type |
|----------|------|-----------|------------|
| `"Ball 1"` | Ball 1 | — | — |
| `"Strike 1 looking (Curveball)"` | Strike 1 looking | — | Curveball |
| `"Strike 1 looking (101 MPH Curveball)"` | Strike 1 looking | 101 | Curveball |
| `"Ball 1 (75 MPH)"` | Ball 1 | 75 | — |
| `"In play (75 MPH Curveball)"` | In play | 75 | Curveball |

Approximate bare-form counts in the original 9,398-play sample (bare only — the sample predates annotation capture): `"Foul"` 4,389, `"In play"` 5,685, `"Foul bunt"` 52, `"Foul tip"` 40; Ball/Strike variants make up the remainder.

**Pitch-type vocabulary (closed, 6 values):**

| Value | Observed? | Note |
|-------|-----------|------|
| `Fastball`, `Curveball`, `Slider`, `Changeup`, `Cutter` | yes (all 5) | Real pitch types. All five observed in live data (2026-06-28); `Slider` e.g. `"Ball 1 (75 MPH Slider)"`. |
| `Unclear` | **NOT yet observed** | From GameChanger's stated vocabulary; never seen in any capture. Semantic: a pitch *was* charted but the scorekeeper couldn't identify the type — NOT a real pitch type; treat as "type unknown." **Open question:** whether it emits a literal `(Unclear)` token or renders as type-absent (bare, or speed-only `(75 MPH)`). The capture regex handles both. |

**Parsing rules:**
- **pitch_count / FPS:** strip the trailing group with `\s*\([^)]*\)\s*$`, then exact-match the bare base. Apply **per-event** (bare and annotated interleave within a game).
- **To capture speed/type:** sub-parse the stripped inner content with `^(?:(\d+)\s*MPH\s*)?(.*?)$` → optional `speed_mph` + optional `pitch_type` (either may be absent; empty type → unknown).
- **Gate the strip:** only pitch templates take the parenthetical. Do NOT strip parentheticals off mid-AB/non-pitch templates — strip-and-match only when the post-strip base is a known pitch template.
- **Parser forward-note:** the plays parser (`src/gamechanger/parsers/plays_parser.py`) still exact-matches the bare vocabulary; until it adopts strip-then-match it drops annotated pitches. This is the open regression.

**No pitch timestamp.** An exhaustive scan (every key name and value at every nesting level) found NO time/timestamp/clock/epoch field anywhere in the plays payload — the `at_plate_details` entry is single-key (`template`).

**Structured alternative.** The plays payload is the FLATTENED/processed view. The raw events endpoint `GET /game-streams/{game_stream_id}/events` carries the same pitch data as STRUCTURED fields — `event_data.attributes.{result, speed, speedProvider, style, advancesCount, advancesRunners}` (speed an int MPH, style the lowercase pitch type, `speedProvider` e.g. `"user"`) plus a per-pitch `createdAt` (epoch milliseconds, the record timestamp). Use that endpoint for pitch timing or clean structured speed/type. See `docs/api/endpoints/get-game-streams-game_stream_id-events.md`.

#### Mid-AB events

**Steal events:**
- `"${uuid} steals 2nd"` (656), `"${uuid} steals 3rd"` (180)
- `"${uuid} scores on steal of home"` (43)

**Wild pitch advances:**
- `"${uuid} advances to 2nd on wild pitch"` (161)
- `"${uuid} advances to 3rd on wild pitch"` (246)
- `"${uuid} scores on wild pitch"` (127)

**Passed ball advances:**
- `"${uuid} advances to 2nd on passed ball"` (82)
- `"${uuid} advances to 3rd on passed ball"` (88)
- `"${uuid} scores on passed ball"` (51)

**Same-pitch advances (secondary runner movement):**
- `"${uuid} advances to 2nd on the same pitch"` (196)
- `"${uuid} advances to 3rd on the same pitch"` (91)
- `"${uuid} scores on the same pitch"` (5)

**Same-error advances:**
- `"${uuid} advances to {base} on the same error"` (various, ~39 total)

**Error-specific advances:**
- `"${uuid} advances to {base} on error by {position} ${uuid}"` (~55 total)
- `"${uuid} scores on error by {position} ${uuid}"` (~40 total)
- Positions observed: pitcher, catcher, first baseman, second baseman, shortstop, third baseman
- Some error-by templates omit the fielder UUID (~5 instances)

**Defensive indifference:**
- `"${uuid} advances to 2nd on defensive indifference"` (26)
- `"${uuid} advances to 3rd on defensive indifference"` (3)

**Generic advances (no mechanism specified):**
- `"${uuid} advances to 1st"` (8), `"${uuid} advances to 2nd"` (40)
- `"${uuid} advances to 3rd"` (23), `"${uuid} scores"` (26)

**Pickoff attempts (non-out):**
- `"Pickoff attempt at 1st"` (1,059), `"Pickoff attempt at 2nd"` (193), `"Pickoff attempt at 3rd"` (51)

**Caught stealing (out on steal attempt):**
- `"${uuid} caught stealing {base}, catcher ${uuid} to {position} ${uuid}"` (most common)
- Also: pitcher-initiated, single-fielder variants, relay chain variants (~100 total across ~20 patterns)

**Picked off (out on pickoff play):**
- `"${uuid} picked off at {base}, pitcher ${uuid} to {position} ${uuid}"` (most common)
- Relay chains up to 7 fielders observed (~35 total across ~15 patterns)

**Runner outs (during AB):**
- `"${uuid} out at {base}, {fielder chain}"` (rare, ~3 total)
- `"${uuid} out due to offensive interference"` (1)

**Balk:**
- `"Balk by pitcher ${uuid}"` (33)

**Extra-inning runner placement:**
- `"${uuid} gets placed on 2nd"` (4), `"${uuid} gets placed on 3rd"` (1)

**Scorekeeper corrections:**
- `"Outs changed to 1"` (4)

**Substitution events:**
- `"Lineup changed: ${uuid} in at pitcher"` (349)
- `"Lineup changed: ${uuid} in for batter ${uuid}"` (93)
- `"Lineup changed: Pinch runner ${uuid} in for {position} ${uuid}"` (~25; all 9 fielder positions + extra hitter observed)
- `"${uuid} in for pitcher ${uuid}"` (63)
- `"Courtesy runner ${uuid} in for ${uuid}"` (289)
- `"(Play Edit) ${uuid} in for ${uuid}"` (17)

### `final_details` Array

Each element has a `template` string field with the outcome narration. 486 unique normalized patterns observed across 165 games -- the list below is representative, not exhaustive. Parsers should use regex-based pattern extraction, not exhaustive enum matching.

> **Ball-in-play boundary — contact detail is NARRATION ONLY here; coordinates are NOT in this payload.** For a ball in play, the plays payload gives you the terminal `"In play (...)"` pitch in `at_plate_details` plus a free-text `final_details` narration carrying contact quality, fielder, and result — e.g. `"${uuid} singles on a ground ball to second baseman"` (quality = "ground ball", fielder = 2B, result = single). There are **no x/y coordinates, no hit location, no trajectory/exit fields** anywhere on the play (verified against the test team's BIP play, 2026-06-28). Structured ball-in-play data — `x`/`y` coordinates, `playType`, `playResult`, fielder `position`, `error` — comes ONLY from the spray-chart / player-stats endpoint `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` (`spray_chart_data.{offense,defense}.{playerUUID}[].attributes`), which the project already ingests into `spray_charts`. Plays and spray are complementary views of the same BIP; correlate on `game_id` + player identity + sequence, not on outcome string (vocabularies differ: `"Single"` vs `"single"`).

**Baserunner outcomes (most frequent, trailing the primary outcome):**
- `"${uuid} scores"` (1,445), `"${uuid} advances to 2nd"` (1,263), `"${uuid} advances to 3rd"` (1,125)
- `"${uuid} remains at 2nd"` (1,086), `"${uuid} remains at 3rd"` (775), `"${uuid} remains at 1st"` (615)
- `"${uuid} out advancing to {base}"` (various, ~402 total)
- `"${uuid} held up at {base}"` (various, ~114 total)
- `"${uuid} advances to {base} on the throw"` (various, ~162 total)
- `"${uuid} advances to {base} on the same error"` / `"${uuid} scores on the same error"` (various, ~87 total)
- `"${uuid} scores after tagging up"` (31), `"${uuid} advances to 3rd after tagging up"` (25)
- `"${uuid} did not score"` (20)
- `"Half-inning ended by out on the base paths"` (74; note: no UUID in this template)

**Walk / HBP / IBB:**
- `"${uuid} walks, ${uuid} pitching"` (1,414)
- `"${uuid} walks"` (24; no pitcher UUID)
- `"${uuid} is hit by pitch, ${uuid} pitching"` (391)
- `"${uuid} is hit by pitch"` (21; no pitcher UUID)
- `"${uuid} is intentionally walked, ${uuid} pitching"` (20)

**Strikeouts:**
- `"${uuid} strikes out swinging, ${uuid} pitching"` (824)
- `"${uuid} strikes out looking, ${uuid} pitching"` (676)
- `"${uuid} strikes out swinging"` / `"${uuid} strikes out looking"` (8 each; no pitcher UUID)
- `"${uuid} is out on foul tip, ${uuid} pitching"` (40)
- `"${uuid} out at first on dropped 3rd strike"` (29)

**Groundouts (with fielding chain):**
- `"${uuid} grounds out, {position} ${uuid} to {position} ${uuid}"` (most common; SS-1B, 2B-1B, 3B-1B, P-1B, C-1B, 1B-P chains)
- `"${uuid} grounds out to {position} ${uuid}"` (unassisted; all infield positions)
- Some omit fielder UUID (~12 instances)

**Fly outs:**
- `"${uuid} flies out to {position} ${uuid}"` (all 8 fielder positions; CF 331, LF 194, RF 178 most common)

**Pop outs:**
- `"${uuid} pops out to {position} ${uuid}"` (all infield positions + catcher + CF)
- `"${uuid} pops out in foul territory to {position} ${uuid}"` (~100 total)

**Line outs:**
- `"${uuid} lines out to {position} ${uuid}"` (all 8 fielder positions, ~170 total)

**Singles (contact quality + trajectory + fielder):**
- `"${uuid} singles on a {quality} to {position} ${uuid}"`
- Contact qualities: line drive, fly ball, ground ball, hard ground ball, bunt, pop fly

**Doubles:**
- `"${uuid} doubles on a {quality} to {position} ${uuid}"`
- Contact qualities: fly ball, line drive, hard ground ball, ground ball, pop fly (rare)

**Triples:**
- `"${uuid} triples on a {quality} to {position} ${uuid}"`
- Contact qualities: fly ball, line drive, hard ground ball

**Home runs (distinct grammar -- zone names, no fielder UUID):**
- `"${uuid} homers on a fly ball to {zone}"` (left field, center field, right field, right center, left center)
- `"${uuid} homers on a line drive to {zone}"` (rare)

**Sacrifice bunts:**
- `"${uuid} sacrifices, {fielding chain}"` / `"${uuid} sacrifices to {position} ${uuid}"` (~79 total)

**Sacrifice flies:**
- `"${uuid} out on sacrifice fly to {position} ${uuid}"` (CF 24, RF 16, LF 15)

**Errors (reaching on error):**
- `"${uuid} hits a {quality} and reaches on an error by {position} ${uuid}"`
- Contact qualities: ground ball, hard ground ball, fly ball, line drive, bunt
- All 9 fielder positions observed

**Fielder's choice:**
- `"${uuid} grounds into fielder's choice to {position} ${uuid}"` (~50 total)
- `"${uuid} grounds into fielder's choice, {pos} ${uuid} to {pos} ${uuid}"` (~60 total)

**Double plays:**
- `"${uuid} grounds into a double play, {fielding chain}"` (~40 total; up to 3 fielders in chain)

**Infield fly:**
- `"${uuid} out on infield fly to {position} ${uuid}"` (~25 total across 5 positions)

**Bunt outs (non-sacrifice):**
- `"${uuid} bunts out, {fielding chain}"` (~12 total)
- `"${uuid} bunts into a double play, {fielding chain}"` (2)

**Catcher's interference:**
- `"${uuid} reaches on catcher's interference"` (4)

**Missing fielder UUIDs:** ~50 templates across all categories omit the fielder UUID while keeping the position name. Parser must handle both `"to shortstop ${uuid}"` and `"to shortstop"` (no UUID).

### `name_template.template` Values

Outcome label strings (access as `play["name_template"]["template"]`). Complete vocabulary from 9,398 plays across 165 games (4 teams):

| Count | Template | Notes |
|------:|----------|-------|
| 1,557 | `"Strikeout"` | |
| 1,545 | `"Single"` | |
| 1,438 | `"Walk"` | |
| 1,279 | `"Ground Out"` | |
| 885 | `"Fly Out"` | |
| 523 | `"Pop Out"` | |
| 412 | `"Hit By Pitch"` | |
| 374 | `"Double"` | |
| 331 | `"Error"` | |
| 200 | `"Fielder's Choice"` | |
| 173 | `"Line Out"` | |
| 165 | `"${uuid} at bat"` | Abandoned at-bat (1 per game, always last play, empty final_details) |
| 91 | `"Double Play"` | |
| 85 | `"Triple"` | |
| 79 | `"Sacrifice Bunt"` | |
| 74 | `"Runner Out"` | Runner caught out (not a batting outcome) |
| 61 | `"Sacrifice Fly"` | |
| 37 | `"Dropped 3rd Strike"` | Strikeout where catcher drops ball, batter may advance |
| 26 | `"Infield Fly"` | Infield fly rule call |
| 22 | `"Home Run"` | |
| 20 | `"Intentional Walk"` | Distinct from regular Walk |
| 7 | `"Batter Out"` | Generic out classification |
| 6 | `"Inning Ended"` | Game-state marker, not a plate appearance |
| 4 | `"FC Double Play"` | Fielder's Choice leading to double play |
| 4 | `"Catcher's Interference"` | Batter awarded first base |

25 unique values confirmed. Original spec listed 13; 12 new outcomes discovered in exploration.

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
    },
    {
      "order": 1,
      "inning": 1,
      "half": "top",
      "name_template": {"template": "Strikeout"},
      "home_score": 0,
      "away_score": 0,
      "did_score_change": false,
      "outs": 1,
      "did_outs_change": true,
      "at_plate_details": [
        {"template": "Strike 1 looking (75 MPH Fastball)"},
        {"template": "Ball 1 (Curveball)"},
        {"template": "Foul (75 MPH)"},
        {"template": "Strike 3 swinging (Slider)"}
      ],
      "final_details": [
        {"template": "${00000000-0000-0000-0000-000000000001} strikes out swinging, ${00000000-0000-0000-0000-000000000001} pitching"}
      ],
      "messages": []
    }
  ]
}
```

The two `at_plate_details` blocks above show the bare and annotated forms: the first play uses the bare form (`"Ball 1"`), the second uses annotated forms — type only (`"Strike 1 looking (75 MPH Fastball)"` is speed + type, `"Strike 3 swinging (Slider)"` is type only) and speed only (`"Foul (75 MPH)"`). All forms can occur in the same game. See the "Pitch annotation" subsection above for the full three-form grammar.

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
- **Abandoned / in-progress PA edge case (empty `final_details` can still carry pitches):** A play with `name_template.template = "${uuid} at bat"` and empty `final_details` is an incomplete/abandoned plate appearance. The common case has empty `at_plate_details` too (the trailing "on deck" placeholder). BUT — confirmed against the test team `dw3a8qivTMvA` on 2026-06-28 — such a play **can carry charted pitches in `at_plate_details` while `final_details` is empty** (a PA scored pitch-by-pitch but not yet resolved to an outcome). The current parser rule "skip plays where `final_details` is empty" therefore **discards any pitches on an unresolved PA**. For completed-PA stats (FPS, P/PA, QAB) that is the correct, conscious choice — an unresolved PA has no batter outcome to attribute. Code relying on this rule should treat it as deliberate, not assume empty `final_details` implies empty `at_plate_details`.
- **`messages` array:** Free-text scorekeeper notes. Usually empty; ~130 non-empty instances observed across 165 games. Common patterns: mound visit notes (~130), game time notes (~15), weather delays, and miscellaneous commentary. Store as raw JSON array; do not parse.
- **Python client 500 history:** Our client previously received HTTP 500 on this endpoint. Root cause was using `game_stream.id` instead of `event_id` as the path parameter. Confirmed fixed by using `event_id`.
- Reuse boxscore key-detection logic for `team_players` asymmetric key pattern.

**Discovered:** 2026-03-04. **Schema corrected and re-confirmed:** 2026-03-26. **Pitch-template grammar re-documented (three-form trailing parenthetical incl. MPH velocity), abandoned-PA edge clarified, BIP boundary and structured-events cross-reference added, ground-truthed against test team:** 2026-06-28.
