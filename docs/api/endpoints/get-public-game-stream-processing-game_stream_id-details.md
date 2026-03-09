---
method: GET
path: /public/game-stream-processing/{game_stream_id}/details
status: CONFIRMED
auth: none
profiles:
  web:
    status: confirmed
    notes: >
      No auth required. Line scores confirmed with include=line_scores param.
      Also confirmed: endpoint accepts event_id directly in the path (not just
      game_stream_id). GC web app used event_id 07c39def-7720-49d8-83e7-c08c6055a557
      and received HTTP 200 (2026-03-09).
  mobile:
    status: not_applicable
    notes: Public endpoint -- no auth profile distinction.
accept: "application/vnd.gc.com.public_team_schedule_event_details+json; version=0.0.0"
gc_user_action: null
query_params:
  - name: include
    required: false
    description: >
      Pass `include=line_scores` to receive inning-by-inning scoring data in the
      `line_score` field. Without this param, `line_score` is absent from the response.
pagination: false
response_shape: object
response_sample: data/raw/public-game-details-sample.json
raw_sample_size: "~500 bytes"
discovered: "2026-03-04"
last_confirmed: "2026-03-09"
tags: [games, events, public]
caveats:
  - >
    ACCEPTS EITHER event_id OR game_stream_id: Confirmed 2026-03-09. The GC web app
    passed event_id (07c39def-7720-49d8-83e7-c08c6055a557) directly and received
    HTTP 200 with ?include=line_scores. The same game has game_stream_id
    aad088a2-df87-4c0f-b39a-cf42e8c8f24a which was used in other game-stream
    endpoints in the same session. Both IDs appear to resolve to the same game.
    This eliminates the need to call /events/{event_id}/best-game-stream-id first
    when using this public endpoint.
  - >
    line_score field is CONDITIONAL: only present when ?include=line_scores query param
    is included. Without the param, the field is absent entirely.
  - >
    totals is a 3-ELEMENT POSITIONAL ARRAY: [R, H, E]. NOT a named object.
    totals[0] = Runs, totals[1] = Hits, totals[2] = Errors.
related_schemas: []
see_also:
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Authenticated per-player box score using same game_stream_id (complementary -- details=game level, boxscore=player level)
  - path: /teams/{team_id}/game-summaries
    reason: Provides game_stream.id needed for this endpoint's path
  - path: /events/{event_id}/best-game-stream-id
    reason: Alternative way to get game_stream_id from schedule event_id
---

# GET /public/game-stream-processing/{game_stream_id}/details

**Status:** CONFIRMED LIVE -- 200 OK. **AUTHENTICATION: NOT REQUIRED.** Last verified: 2026-03-04.

Returns game-level metadata and optional inning-by-inning line scores for a game. Uses the same `game_stream_id` as the authenticated boxscore endpoint. No credentials required.

Complementary to the authenticated boxscore:
- **This endpoint:** Game-level scoring (line score, R/H/E totals)
- **Authenticated boxscore:** Per-player stats (batting/pitching lines, batting order)

```
GET https://api.team-manager.gc.com/public/game-stream-processing/{game_stream_id}/details?include=line_scores
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_stream_id` | UUID | Game stream identifier. From `game_stream.id` in game-summaries. Same ID as authenticated boxscore. |

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `include` | No | Pass `line_scores` to get inning-by-inning scoring. Without this param, `line_score` field is absent. |

## Headers

```
Accept: application/vnd.gc.com.public_team_schedule_event_details+json; version=0.0.0
User-Agent: Mozilla/5.0 ...
```

Do NOT include `gc-token` or `gc-device-id` headers.

## Response

Single JSON object with 12 fields.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Game stream UUID (same as path parameter) |
| `opponent_team` | object | Opponent team metadata |
| `opponent_team.name` | string | Opponent team name |
| `is_full_day` | boolean | Whether this is a full-day event |
| `start_ts` | ISO 8601 | Game start timestamp |
| `end_ts` | ISO 8601 | Game end timestamp |
| `timezone` | string | IANA timezone string |
| `home_away` | string | `"home"` or `"away"` |
| `score` | object | Final score: `{team: int, opponent_team: int}` |
| `game_status` | string | `"completed"` for finished games |
| `has_videos_available` | boolean | Whether video is available |
| `has_live_stream` | boolean | Whether a live stream exists |
| `line_score` | object | Inning-by-inning scoring. **Only present when `?include=line_scores`.** |

### `line_score` Object (Conditional)

| Field | Type | Description |
|-------|------|-------------|
| `team.scores` | array of int | Runs scored per inning for this team. Length = innings played. |
| `team.totals` | array of 3 ints | `[R, H, E]` -- **POSITIONAL, not named.** `totals[0]`=Runs, `totals[1]`=Hits, `totals[2]`=Errors. |
| `opponent_team.scores` | array of int | Runs per inning for opponent. |
| `opponent_team.totals` | array of 3 ints | Same positional format: `[R, H, E]`. |

**totals cross-validation:** The `totals[0]` (Runs) value matches `score.team` or `score.opponent_team`. The `totals[1]` (Hits) matches `team_stats.H` in the authenticated boxscore. Use for cross-validation.

## Example Response

```json
{
  "id": "9f2a1b3c-REDACTED",
  "opponent_team": {"name": "Kearney Mavericks 14U"},
  "is_full_day": false,
  "start_ts": "2025-05-24T16:00:00.000Z",
  "end_ts": "2025-05-24T18:00:00.000Z",
  "timezone": "America/Chicago",
  "home_away": "away",
  "score": {"team": 4, "opponent_team": 8},
  "game_status": "completed",
  "has_videos_available": false,
  "has_live_stream": false,
  "line_score": {
    "team": {
      "scores": [2, 0, 0, 0, 2, 0],
      "totals": [4, 7, 1]
    },
    "opponent_team": {
      "scores": [0, 3, 2, 0, 3, 0],
      "totals": [8, 10, 0]
    }
  }
}
```

## Known Limitations

- `line_score` is only present with `?include=line_scores`. Without this param, the field is absent.
- `totals` is a positional array `[R, H, E]`, not a named object. `totals[1]` is Hits.
- `line_score.team` and `line_score.opponent_team` have the same structure but which is "team" vs "opponent" depends on whose perspective the `home_away` field reflects.
- `scores` array length equals innings played -- a 7-inning game with a last-inning rally will have 7 elements.

**Discovered:** 2026-03-04. **Confirmed no-auth with line scores:** 2026-03-04. **event_id accepted directly in path (no game_stream_id lookup needed):** 2026-03-09.
