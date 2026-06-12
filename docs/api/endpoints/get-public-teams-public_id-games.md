---
method: GET
path: /public/teams/{public_id}/games
status: CONFIRMED
auth: none
profiles:
  web:
    status: confirmed
    notes: >
      No auth required. 32 records confirmed for team QTiLIb2Lui3b (2026-03-04).
      Re-confirmed 2026-06-12 against a different team (WThfCgtHecNF, 34 records):
      response now includes UPCOMING/scheduled games (game_status null, future
      start_ts), not just completed games. opponent_team carries name +
      optional avatar_url ONLY -- no opponent identity ID of any kind.
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
last_confirmed: "2026-06-12"
tags: [games, team, public]
caveats:
  - >
    opponent_team carries `name` and an optional `avatar_url` ONLY. There is NO
    opponent identity ID in this payload -- no `public_id`, no `root_team_id`, no
    `progenitor_team_id`, no slug -- for ANY game, completed or upcoming, and
    regardless of how the coach entered the opponent (manual typing vs. team
    lookup). The own-team public schedule therefore CANNOT auto-resolve an
    opponent's public_id. A scheduler must resolve opponents by name (e.g., via
    `POST /search`) or fall back to operator input. See "Opponent identity" below.
  - >
    Response now includes UPCOMING/scheduled games (confirmed 2026-06-12), not
    just completed ones. Upcoming games have `game_status: null` and a future
    `start_ts`; they omit `score`, `game_status` value, and `has_videos_available`
    in observed records. The earlier "completed games only" claim is superseded.
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

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-06-12 (34 records, team WThfCgtHecNF; previously 32 records, team QTiLIb2Lui3b, 2026-03-04). **AUTHENTICATION: NOT REQUIRED.**

Returns a team's games -- both **completed** and **upcoming/scheduled** -- with final scores (completed only), opponent **names** (no opponent ID), and home/away status. No credentials required. Provides scores and opponent names for any team with a known `public_id`, enabling scouting without authentication.

> **Opponent identity (verified 2026-06-12):** `opponent_team` carries `name` and an optional `avatar_url` ONLY. There is **NO** opponent identity ID of any kind in this payload -- no `public_id`, no `root_team_id`, no `progenitor_team_id`. This holds for every game and is independent of the coach's opponent entry mode (manual typing vs. team lookup). See the **Opponent Identity** section below for what this means for schedulers.

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

Bare JSON array of game records (completed and upcoming). 34 records in a single response (no pagination observed for this team). Upcoming games have `game_status: null` and a future `start_ts`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | **This IS the `event_id`** used by the boxscore endpoint. Pass directly to `GET /game-stream-processing/{event_id}/boxscore` -- no bridge call needed (confirmed 2026-03-12, terminology corrected 2026-03-19). Equivalent to `event_id` in the authenticated flow (game-summaries); distinct from `event_id` (used by `/games/preview` as a different field name for the same value). |
| `opponent_team` | object | Opponent team info. **Carries `name` and optional `avatar_url` ONLY -- no identity ID.** See Opponent Identity below. |
| `opponent_team.name` | string | Opponent team name (free-text label; not guaranteed to match any GC team record). |
| `opponent_team.avatar_url` | string or absent | Opponent avatar URL. Present on 11/34 records (2026-06-12). Absent (not null, not empty) when no avatar. |
| `is_full_day` | boolean | Whether this is a full-day event. |
| `start_ts` | ISO 8601 | Game start timestamp (UTC). |
| `end_ts` | ISO 8601 | Game end timestamp (UTC). |
| `timezone` | string | IANA timezone string. |
| `home_away` | string | `"home"` or `"away"`. |
| `score` | object or absent | Final score. **Present on completed games only**; absent on upcoming games. |
| `score.team` | int | This team's final score. |
| `score.opponent_team` | int | Opponent's final score. |
| `game_status` | string or null | `"completed"` for completed games; **`null` for upcoming/scheduled games** (verified 2026-06-12). |
| `has_videos_available` | boolean or absent | Whether game video is available. Present on completed games; absent on upcoming games in observed records. |
| `has_live_stream` | boolean | `false` for all observed records. |

### Opponent Identity

**The opponent in this payload is identified by a free-text `name` string only.** Verified 2026-06-12 across all 34 records for team `WThfCgtHecNF`: no record carries `public_id`, `root_team_id`, `progenitor_team_id`, or any slug under `opponent_team` (or anywhere else). This is true for both completed and upcoming games, and is independent of how the coach entered the opponent.

This matters for any feature that needs to **machine-resolve** the opponent (e.g., a scheduler that auto-ingests opponent rosters/schedules):

- The own-team public schedule does **NOT** distinguish the two GC opponent entry modes (manual typing vs. team lookup). The dual-entry signal (`progenitor_team_id` present = team lookup; absent = manual entry) lives only in the **authenticated** opponent endpoints (`GET /teams/{team_id}/opponents`, `GET /teams/{team_id}/opponent/{opponent_id}`), and even there it is a UUID, not a `public_id` slug.
- To get an opponent's `public_id` starting from this endpoint, resolve by `name` via `POST /search` (the gc_uuid bridge, `.claude/rules/gc-uuid-bridge.md`), accepting the name-match ambiguity and punctuation quirks; or fall back to operator input.
- The authenticated `GET /teams/{team_id}/game-summaries` is no better for this purpose: its `game_stream.opponent_id` is the opponent's team **UUID** (root_team_id namespace), not a `public_id`.

## Example Response Items

**Completed game** (has `score`, `game_status: "completed"`):

```json
{
  "id": "48c79654-REDACTED",
  "opponent_team": {
    "name": "Anytown Eagles 12U",
    "avatar_url": "https://media-service.gc.com/example-avatar-url"
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

**Upcoming game** (verified 2026-06-12 -- no `score`, `game_status: null`, no `has_videos_available`; `opponent_team` carries `name` only, no identity ID):

```json
{
  "id": "e234cf54-REDACTED",
  "opponent_team": {
    "name": "Example Team 14U"
  },
  "is_full_day": false,
  "start_ts": "2026-06-12T20:00:00.000Z",
  "end_ts": "2026-06-12T22:00:00.000Z",
  "timezone": "America/Chicago",
  "home_away": "home",
  "game_status": null,
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

- **No opponent identity ID.** `opponent_team` carries `name` + optional `avatar_url` only -- see the Opponent Identity section. Machine-resolving an opponent requires a name-based `POST /search` or operator input.
- `opponent_team.avatar_url` is absent (not null, not empty) when no avatar exists. Use `.get("avatar_url")` to handle this.
- No pagination observed (32 games on team QTiLIb2Lui3b; 34 on WThfCgtHecNF). Behavior for teams with very large game histories unknown.
- **Both completed AND upcoming games appear** (verified 2026-06-12). Upcoming games have `game_status: null`, a future `start_ts`, and omit `score`/`has_videos_available`. (Earlier observation of "completed only" was incomplete -- likely a team with no upcoming games at capture time.) For richer in-progress / live data, the authenticated `GET /teams/{team_id}/game-summaries` may still be preferred, but it returns completed games only.
- `has_live_stream` is `false` for all observed records.
- The `id` field is the `event_id` parameter for the boxscore endpoint (confirmed 2026-03-12, terminology corrected 2026-03-19). This is the public-endpoint equivalent of `event_id` in the authenticated flow (game-summaries). `/games/preview` uses `event_id` as the field name for the same value; `/games` uses `id`.

**Discovered:** 2026-03-04. **Confirmed no-auth:** 2026-03-04. **Opponent-identity + upcoming-games behavior verified:** 2026-06-12.
