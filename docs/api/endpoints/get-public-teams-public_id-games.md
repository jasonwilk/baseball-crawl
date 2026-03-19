---
method: GET
path: /public/teams/{public_id}/games
status: CONFIRMED
auth: none
profiles:
  web:
    status: confirmed
    notes: No auth required. 32 records confirmed for team QTiLIb2Lui3b.
  mobile:
    status: not_applicable
    notes: Public endpoint -- no auth profile distinction.
accept: "application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/public-team-games-sample.json
raw_sample_size: "32 game records, 25.7 KB"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [games, team, public]
related_schemas: []
see_also:
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: The `id` field from this response IS the event_id for boxscore (confirmed 2026-03-12, terminology corrected 2026-03-19) -- no bridge call needed
  - path: /public/teams/{public_id}/games/preview
    reason: Near-duplicate endpoint; uses event_id instead of id, lacks has_videos_available; prefer /games
  - path: /public/teams/{public_id}
    reason: Team profile (also no-auth)
  - path: /teams/{team_id}/schedule
    reason: Authenticated schedule including practices and other events
  - path: /public/game-stream-processing/{game_stream_id}/details
    reason: Inning-by-inning line scores for individual games (no-auth)
---

# GET /public/teams/{public_id}/games

**Status:** CONFIRMED LIVE -- 200 OK. 32 records confirmed. **AUTHENTICATION: NOT REQUIRED.** Last verified: 2026-03-04.

Returns all completed games for a team, with final scores, opponent names, and home/away status. No credentials required. Provides final scores and opponent names for any team with a known `public_id`, enabling scouting without authentication.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}/games
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Alphanumeric public ID slug (e.g., `"QTiLIb2Lui3b"`). NOT a UUID. |

## Headers

```
Accept: application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0
User-Agent: Mozilla/5.0 ...
```

Do NOT include `gc-token` or `gc-device-id` headers.

## Response

Bare JSON array of completed game records. 32 records in a single response (no pagination observed). All observed records had `game_status: "completed"` and `has_live_stream: false`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | **This IS the `event_id`** used by the boxscore endpoint. Pass directly to `GET /game-stream-processing/{event_id}/boxscore` -- no bridge call needed (confirmed 2026-03-12, terminology corrected 2026-03-19). Equivalent to `event_id` in the authenticated flow (game-summaries); distinct from `event_id` (used by `/games/preview` as a different field name for the same value). |
| `opponent_team` | object | Opponent team info |
| `opponent_team.name` | string | Opponent team name |
| `opponent_team.avatar_url` | string or absent | Opponent avatar URL. Present on 21/32 records. Absent (not null, not empty) when no avatar. |
| `is_full_day` | boolean | Whether this is a full-day event |
| `start_ts` | ISO 8601 | Game start timestamp |
| `end_ts` | ISO 8601 | Game end timestamp |
| `timezone` | string | IANA timezone string |
| `home_away` | string | `"home"` or `"away"` |
| `score` | object | Final score |
| `score.team` | int | This team's final score |
| `score.opponent_team` | int | Opponent's final score |
| `game_status` | string | `"completed"` for all observed records |
| `has_videos_available` | boolean | Whether game video is available |
| `has_live_stream` | boolean | `false` for all observed (post-game records) |

## Example Response Item

```json
{
  "id": "48c79654-REDACTED",
  "opponent_team": {
    "name": "Kearney Mavericks 14U",
    "avatar_url": "https://media-service.gc.com/..."
  },
  "is_full_day": false,
  "start_ts": "2025-05-24T16:00:00.000Z",
  "end_ts": "2025-05-24T18:00:00.000Z",
  "timezone": "America/Chicago",
  "home_away": "away",
  "score": {"team": 4, "opponent_team": 8},
  "game_status": "completed",
  "has_videos_available": false,
  "has_live_stream": false
}
```

## Comparison to /games/preview

| Dimension | `/games` | `/games/preview` |
|-----------|----------|-----------------|
| Game UUID field | `id` | `event_id` |
| `has_videos_available` | Present | Absent |
| All other fields | Identical | Identical |
| Preferred for | General use | When `has_videos_available` not needed |

**Recommendation:** Use `/games` (this endpoint) in all cases. The UUID field name difference (`id` vs `event_id`) is important if you need to join to other endpoints.

## Known Limitations

- `opponent_team.avatar_url` is absent (not null, not empty) when no avatar exists. Use `.get("avatar_url")` to handle this.
- No pagination observed for 32 games. Behavior for teams with very large game histories unknown.
- Only `"completed"` games appear -- scheduled or canceled games are not included. For in-progress or upcoming games, use the authenticated `GET /teams/{team_id}/game-summaries`.
- `has_live_stream` is `false` for all observed (historical) records.
- The `id` field is the `event_id` parameter for the boxscore endpoint (confirmed 2026-03-12, terminology corrected 2026-03-19). This is the public-endpoint equivalent of `event_id` in the authenticated flow (game-summaries). `/games/preview` uses `event_id` as the field name for the same value; `/games` uses `id`.

**Discovered:** 2026-03-04. **Confirmed no-auth:** 2026-03-04.
