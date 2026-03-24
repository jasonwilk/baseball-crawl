---
method: GET
path: /teams/{team_id}/schedule
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 228 events returned in a single response.
  mobile:
    status: observed
    notes: >
      3 hits, HTTP 200. Observed 2026-03-09 (session 063531). Called with opponent
      progenitor_team_id (14fd6cb6). Query key start_at used for pagination.
accept: "application/vnd.gc.com.event:list+json; version=0.2.0"
gc_user_action: "data_loading:team"
query_params:
  - name: fetch_place_details
    required: false
    description: >
      When set to `true`, enriches location objects with `google_place_details`
      and `place_id` from Google Places API. Without this param, location
      contains only `name` and `coordinates`.
pagination: false
response_shape: array
response_sample: data/raw/schedule-sample.json
raw_sample_size: "228 events, 134 KB"
discovered: "2026-02-28"
last_confirmed: "2026-03-04"
tags: [schedule, events, team, games]
related_schemas: []
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Game-only view with scored results and pagination support
  - path: /public/teams/{public_id}/games
    reason: Public no-auth game-only view with final scores
  - path: /events/{event_id}
    reason: Single-event lookup by event UUID
  - path: /events/{event_id}/best-game-stream-id
    reason: Resolves schedule event_id to game_stream_id for boxscore/plays access
---

# GET /teams/{team_id}/schedule

**Status:** CONFIRMED LIVE -- 228 total records (103 games, 90 practices, 35 other events) fully retrieved. Last verified: 2026-03-04.

Returns the full event schedule for a team, including all event types (games, practices, other), with optional venue enrichment when `fetch_place_details=true`. The response is a bare JSON array. No pagination observed -- all 228 events returned in one response.

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule?fetch_place_details=true
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `fetch_place_details` | No | `true` -- enriches location objects with `google_place_details` and `place_id` from Google Places API. Without this param, location contains only `name` and `coordinates`. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.event:list+json; version=0.2.0
gc-user-action: data_loading:team
gc-user-action-id: {UUID}
Content-Type: application/vnd.gc.com.none+json; version=undefined
cache-control: no-cache
pragma: no-cache
origin: https://web.gc.com
referer: https://web.gc.com/
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Response

A bare JSON array of schedule item objects. Each item is a wrapper object with an `event` key. Game events additionally include a `pregame_data` key.

**Observed counts (2026-03-04, travel ball team, full history):**
- 228 total events; date range: 2024-11-08 to 2025-07-15
- 103 `game` events (66 canceled)
- 90 `practice` events
- 35 `other` events

### Top-Level Item Structure

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `event` | object | Yes | Core event data (all event types) |
| `pregame_data` | object | Games only | Game-specific opponent and lineup data. Present on all 103 game events; absent on practice and other events. |

### `event` Object Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | UUID | Yes | Event UUID. For game events, equals `pregame_data.id` and `pregame_data.game_id`. |
| `event_type` | string | Yes | `"game"`, `"practice"`, or `"other"` |
| `sub_type` | array | Yes | Always an empty array in this sample (228 records). Purpose unknown. |
| `status` | string | Yes | `"scheduled"` or `"canceled"`. 162 scheduled, 66 canceled observed. |
| `full_day` | boolean | Yes | When `true`, `start`/`end` use `{"date": "YYYY-MM-DD"}` format; `timezone` is null. |
| `team_id` | UUID | Yes | The requesting team's UUID. |
| `start` | object | Yes | `{"datetime": "ISO8601"}` for timed events; `{"date": "YYYY-MM-DD"}` for full-day events. |
| `end` | object | Yes | Same shape as `start`. |
| `arrive` | object | No | Arrival time `{"datetime": "ISO8601"}`. Present on 86/228 events (mostly games). |
| `location` | object | No | Venue data. Absent (empty `{}`) on 87/228 events. See Location Object below. |
| `timezone` | string | Conditional | IANA timezone string. `null` for full-day events. |
| `notes` | string | No | Free-text notes. Non-null on 49/228 events. |
| `title` | string | Yes | Human-readable event title. |
| `series_id` | null | Yes | Always `null` in this sample. |

### Location Object

The `location` object has variable shape depending on whether venue data was resolved.

| Field combination observed | Count | Notes |
|---------------------------|-------|-------|
| `{}` (empty) | 87 | No location set |
| `{name}` | 69 | Name only (e.g., `"Indoor"`) |
| `{name, coordinates, address}` | 33 | Has lat/long and street address |
| `{address, coordinates}` | 20 | Has lat/long and street address, no name |
| `{name, google_place_details, place_id}` | 18 | Google Place enrichment, no separate coordinates |
| `{google_place_details, place_id}` | 1 | Google Place enrichment only |

**Coordinate key inconsistency:** `{latitude, longitude}` in `location.coordinates` vs `{lat, long}` in `location.google_place_details.lat_long`. Normalize both key pairs during parsing.

### `pregame_data` Object Fields (Game Events Only)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | UUID | Yes | Always equals `event.id` and `game_id`. |
| `game_id` | UUID | Yes | Always equals `event.id` and `pregame_data.id`. |
| `opponent_name` | string | Yes | Opponent team name. Non-null on all 103 game records. |
| `opponent_id` | UUID | Yes | Opponent team UUID. **Same namespace as `root_team_id` in `GET /teams/{team_id}/opponents` response** (confirmed by cross-referencing `schedule-sample.json` vs `opponents-sample.json` -- 54/54 matches, 0 matches with `progenitor_team_id`). Use to join against the opponent registry. Do NOT use as `gc_uuid` -- that must be `progenitor_team_id`. |
| `home_away` | string | No | `"home"`, `"away"`, or `null`. All three values observed. |
| `lineup_id` | UUID | No | UUID of the pre-set lineup. Null on 25/103, non-null on 78/103. Links to `GET /bats-starting-lineups/{event_id}`. |

## Example Response Items

### Timed Game Event (with Google Place Details)

```json
{
  "event": {
    "id": "48c79654-REDACTED",
    "event_type": "game",
    "sub_type": [],
    "status": "scheduled",
    "full_day": false,
    "team_id": "72bb77d8-REDACTED",
    "start": {"datetime": "2025-04-26T16:00:00.000Z"},
    "end":   {"datetime": "2025-04-26T18:00:00.000Z"},
    "arrive": {"datetime": "2025-04-26T15:00:00.000Z"},
    "location": {
      "name": "Centennial Park",
      "google_place_details": {
        "id": "ChIJxVpa4OkidocRQJDGpUFBIsU",
        "lat_long": {"lat": 40.0, "long": -99.0},
        "address": "{REDACTED_CITY}, NE, USA"
      },
      "place_id": "ChIJxVpa4OkidocRQJDGpUFBIsU"
    },
    "timezone": "America/Chicago",
    "notes": null,
    "title": "Game vs. Kearney Mavericks 14U",
    "series_id": null
  },
  "pregame_data": {
    "id": "48c79654-REDACTED",
    "game_id": "48c79654-REDACTED",
    "opponent_name": "Kearney Mavericks 14U",
    "opponent_id": "bbe7a634-REDACTED",
    "home_away": null,
    "lineup_id": null
  }
}
```

### Full-Day Event (Different `start`/`end` Format)

```json
{
  "event": {
    "id": "26bab872-REDACTED",
    "event_type": "other",
    "sub_type": [],
    "status": "canceled",
    "full_day": true,
    "team_id": "72bb77d8-REDACTED",
    "start": {"date": "2025-04-26"},
    "end":   {"date": "2025-04-28"},
    "timezone": null,
    "notes": null,
    "title": "Flatrock Tournament North Platte 4/26-27",
    "series_id": null
  }
}
```

## Known Limitations

- `sub_type` is always an empty array in this sample. Purpose unknown.
- `series_id` is always `null`. May be populated for tournament series.
- `home_away` can be `null` even for game events. Null vs. explicit value semantics unclear.
- No pagination observed. All 228 events returned in a single response. Behavior with very large histories (500+ events) untested.
- Location coordinates appear in two formats with different key names -- handle both when parsing.
- `opponent_id` is in the `root_team_id` namespace (local registry key), NOT `progenitor_team_id` (canonical UUID). Confirmed 2026-03-24 by cross-referencing 54 unique opponent_ids against `data/raw/opponents-sample.json` -- 54/54 matched `root_team_id`, 0 matched `progenitor_team_id`. Do not use `opponent_id` directly with `GET /teams/{team_id}` for team metadata -- use `progenitor_team_id` from the opponents endpoint instead.
- Filter canceled events (`status: "canceled"`) in ETL pipelines.

**Discovered:** Pre-2026-03-01 (initial capture). **Schema fully documented:** 2026-03-04.
