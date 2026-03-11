---
method: POST
path: /clips/search
status: CONFIRMED
auth: required
profiles:
  web:
    status: observed
    notes: >
      Captured from web proxy session 2026-03-11. Full request and response body
      documented. The web app also calls this path (not /v2) -- the original
      assumption that web uses /v2 only is INCORRECT. Both profiles use /clips/search.
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 3 hits, all HTTP 200.
      Confirmed same Content-Type as web.
accept: "application/vnd.gc.com.video_clip_search_results+json; version=0.3.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: "2026-03-11"
tags: [video, search, games, player]
caveats:
  - >
    SPEC CORRECTION 2026-03-11: Previous docs stated "web app uses /clips/search/v2,
    not /clips/search." This is WRONG. The web app calls /clips/search (this path)
    extensively. The /v2 path was observed only once in an earlier mobile session.
    Prefer /clips/search for implementations targeting either profile.
  - >
    ACCEPT HEADER VERSION: Accept header is version=0.3.0 (not 0.0.0). This differs
    from Content-Type (version=0.0.0 for request body).
  - >
    TWO SEARCH MODES: The request body `select.kind` field determines the search mode:
    "event" (search within a game event) or "player" (search by player across games).
    The sort strategy differs between modes.
see_also:
  - path: /clips/search/v2
    reason: Web app version (v2 suffix) -- observed once but full schema now confirmed on /clips/search
  - path: /events/{event_id}/highlight-reel
    reason: Structured highlight playlist for a game -- alternative source for game highlights
  - path: /teams/{team_id}/video-stream/assets
    reason: Full video recording assets (different from short clips)
---

# POST /clips/search

**Status:** CONFIRMED -- HTTP 200 in web proxy session 2026-03-11. Full request and response schema documented.

Searches for video highlight clips using a POST request body as a structured query. Supports two search modes: game-event clips (filtered by team + event) and player clips (filtered by player across games). Returns clip metadata with thumbnail URLs and play context.

```
POST https://api.team-manager.gc.com/clips/search
Content-Type: application/vnd.gc.com.video_clip_search_query+json; version=0.0.0
Accept: application/vnd.gc.com.video_clip_search_results+json; version=0.3.0
```

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.video_clip_search_query+json; version=0.0.0
Accept: application/vnd.gc.com.video_clip_search_results+json; version=0.3.0
```

## Request Body

JSON object with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `match_all` | object | yes | Filter criteria -- all conditions must match |
| `match_all.team_id` | UUID | conditional | Required for event-mode searches |
| `match_all.event_id` | UUID | conditional | Game event UUID -- use for game-scoped search |
| `match_all.player_id` | UUID | conditional | Player UUID -- use for player-scoped search |
| `match_all.play_type` | array of string | no | Filter by play types. Values: `"single"`, `"double"`, `"triple"`, `"home_run"`, `"strikeout"`, `"walk"`, `"fielders_choice"`, `"error"`, etc. |
| `select` | object | yes | Response shape configuration |
| `select.kind` | string | yes | Search mode: `"event"` (game scope) or `"player"` (player scope) |
| `select.include_totals` | boolean | no | Include `total_count` in response when true |
| `sort` | array | yes | Sort specification (see below) |
| `sort[].by` | string | yes | Field to sort by: `"timestamp"`, `"event_id"` |
| `sort[].order` | string | yes | Sort direction: `"asc"`, `"desc"`, or `"custom"` |
| `sort[].custom` | array of UUID | conditional | Ordered list of event_ids for custom sort order (used in player-mode) |
| `paging` | string | yes | Pagination mode. Observed: `"page"`. |
| `offset` | integer | yes | Pagination offset (0-based) |
| `limit` | integer | yes | Maximum results to return. Observed: 50. |

## Example Request Body (Event Mode)

```json
{
  "sort": [{"by": "timestamp", "order": "asc"}],
  "paging": "page",
  "select": {"kind": "event", "include_totals": true},
  "match_all": {
    "team_id": "00000000-REDACTED",
    "event_id": "00000000-REDACTED"
  },
  "offset": 0,
  "limit": 50
}
```

## Example Request Body (Player Mode)

```json
{
  "select": {"kind": "player", "include_totals": true},
  "paging": "page",
  "offset": 0,
  "limit": 50,
  "match_all": {"player_id": "00000000-REDACTED"},
  "sort": [
    {
      "by": "event_id",
      "order": "custom",
      "custom": ["00000000-REDACTED", "00000000-REDACTED"]
    }
  ]
}
```

## Response

**HTTP 200.** JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `hits` | array | Array of clip objects. Empty array when no clips match. |
| `total_count` | integer | Total count of matching clips (only present when `include_totals: true`). |
| `hits[].clip_metadata_id` | UUID | Unique clip ID |
| `hits[].hidden` | boolean | Whether clip is hidden from audience |
| `hits[].audience_type` | string | Who can view this clip. Observed: `"players_family"`, `"players_family_fans"`. |
| `hits[].last_edited_by` | UUID or null | User who last edited the clip |
| `hits[].last_updated_at` | ISO8601 | Clip metadata last update timestamp |
| `hits[].related_ids` | object | Cross-reference IDs |
| `hits[].related_ids.event_id` | UUID | Game event UUID |
| `hits[].related_ids.team_id` | UUID | Team UUID |
| `hits[].related_ids.stream_id` | UUID | Game stream UUID |
| `hits[].sport` | string | Sport. Observed: `"bats"` (baseball). |
| `hits[].duration` | number | Clip duration in seconds |
| `hits[].timestamp` | ISO8601 | When the clip was created |
| `hits[].thumbnail_url` | string | CDN URL for clip thumbnail image (vod-archive.gc.com) |
| `hits[].play_summary` | string or null | Human-readable play description with `${player_uuid}` template placeholders |
| `hits[].player_metadata` | object or null | Player context (present in player-mode results) |
| `hits[].player_metadata.player_id` | UUID | Player UUID |
| `hits[].player_metadata.player_role` | string | Role: `"batter"`, `"pitcher"` |
| `hits[].player_metadata.perspective` | string | Play description from player's perspective (with `${uuid}` placeholders) |
| `hits[].play_metadata` | object | Play type metadata |
| `hits[].play_metadata.type` | string | Play engine. Observed: `"sabertooth"`. |
| `hits[].play_metadata.pbp_id` | UUID or null | Pitch-by-pitch play UUID (null for some plays) |
| `hits[].play_metadata.play_type` | string | Play type. Observed: `"single"`, `"double"`, `"strikeout"`, `"walk"`, `"fielders_choice"`, `"error"`, etc. |
| `hits[].sport_metadata` | object | Sport context |
| `hits[].sport_metadata.type` | string | Sport. Observed: `"bats"`. |
| `hits[].sport_metadata.inning` | integer | Inning number |
| `hits[].sport_metadata.inning_half` | string | `"top"` or `"bottom"` |
| `hits[].cv_generated` | boolean | Whether clip was computer-vision generated |
| `hits[].exceptional_play` | boolean | Whether this is flagged as an exceptional/highlight play |

## Example Response (truncated)

```json
{
  "hits": [
    {
      "clip_metadata_id": "00000000-REDACTED",
      "hidden": false,
      "audience_type": "players_family",
      "last_edited_by": null,
      "last_updated_at": "2025-05-04T19:23:55.403Z",
      "related_ids": {
        "event_id": "00000000-REDACTED",
        "team_id": "00000000-REDACTED",
        "stream_id": "00000000-REDACTED"
      },
      "sport": "bats",
      "play_summary": "${00000000-REDACTED} singles on a ground ball to third baseman ${00000000-REDACTED}",
      "duration": 51.701,
      "timestamp": "2025-05-04T19:23:51.473Z",
      "thumbnail_url": "https://vod-archive.gc.com/example-thumbnail-url",
      "play_metadata": {
        "type": "sabertooth",
        "pbp_id": "00000000-REDACTED",
        "play_type": "single"
      },
      "sport_metadata": {
        "type": "bats",
        "inning": 1,
        "inning_half": "top"
      },
      "cv_generated": false,
      "exceptional_play": false
    }
  ],
  "total_count": 23
}
```

**Note:** The `${uuid}` placeholders in `play_summary` and `perspective` fields must be resolved to player names using the roster data from `/teams/{team_id}/players`.

**Coaching relevance: MEDIUM.** Enables video clip browsing per game event or per player. The `play_type` filter is useful for finding specific play types (hits, strikeouts). The `pbp_id` cross-references to `/game-stream-processing/{game_stream_id}/plays` for full pitch sequence context.

**Previously documented:** Body schema unknown. Both web and response schemas were completely undocumented prior to 2026-03-11. **Schema updated 2026-03-11** from web proxy session 2026-03-11_034739.

**Discovered:** 2026-03-09. Schema fully documented: 2026-03-11.
