# GameChanger API Specification

**Base URL**: `https://api.team-manager.gc.com`

**Status**: Living document. Sections marked `[NEEDS VERIFICATION]` were inferred or partially observed and have not been confirmed by a full live response. Sections marked `[NOT YET DISCOVERED]` represent endpoints that are needed but have not been found.

**Last updated**: 2026-03-01

---

## Table of Contents

1. [Credential Scheme](#credential-scheme)
2. [Content Type Convention](#content-type-convention)
3. [Pagination Scheme](#pagination-scheme)
4. [Endpoints](#endpoints)
   - [List User's Teams](#get-meteams)
   - [Team Roster (Players)](#get-teamsteam_idplayers)
   - [Team Schedule](#get-teamsteam_idschedule)
   - [Game Summaries](#get-teamsteam_idgame-summaries)
   - [Game Stats / Box Score](#game-stats--box-score)
   - [Player Season Aggregate Stats](#player-season-aggregate-stats)
   - [Opponent / Away Team Data](#opponent--away-team-data)
   - [Video Stream Assets](#get-teamsteam_idvideo-streamassets)
5. [Known Limits and Quirks](#known-limits-and-quirks)
6. [Discovery Log](#discovery-log)

---

## Credential Scheme

### Source

Credentials are extracted from browser network traffic (Chrome DevTools / `curl --include` captures). GameChanger does not expose a public developer API or OAuth flow.

### Required Headers (All Requests)

| Header | Value | Notes |
|--------|-------|-------|
| `gc-token` | `<JWT>` | Primary auth. Custom header — NOT `Authorization: Bearer`. Required on every request. |
| `gc-app-name` | `web` | Static string. Identifies the client type. |
| `gc-device-id` | `<32 hex chars>` | Stable device fingerprint. Use the same value for all requests in a session. Do not randomize per-request. |
| `User-Agent` | `Mozilla/5.0 ...` | Must be a realistic browser UA. Never send the Python `requests` or `httpx` library default. |
| `DNT` | `1` | Do Not Track. Present in all observed browser requests. |
| `Referer` | `https://web.gc.com/` | Required. Matches the web app origin. |
| `sec-ch-ua` | `"Chromium";v="..."` | Browser fingerprint header. Use a realistic current Chrome value. |
| `sec-ch-ua-mobile` | `?0` | Browser fingerprint. |
| `sec-ch-ua-platform` | `"macOS"` (or Windows) | Browser fingerprint. |

### Per-Request Optional Headers

| Header | Value | When Present |
|--------|-------|--------------|
| `gc-user-action-id` | `<UUID v4>` | Per-request action tracking UUID. Observed on schedule and some game endpoints. May be optional. |
| `gc-user-action` | `<action_string>` | Human-readable action descriptor. Examples: `data_loading:events`, `data_loading:team`, `data_loading:event`. |
| `x-pagination` | `true` | Enables paginated response mode (see [Pagination Scheme](#pagination-scheme)). |
| `cache-control` | `no-cache` | Observed on schedule and team list requests. |
| `pragma` | `no-cache` | Observed alongside `cache-control: no-cache`. |
| `origin` | `https://web.gc.com` | Present on CORS requests. |
| `sec-fetch-dest` | `empty` | Standard CORS preflight header. |
| `sec-fetch-mode` | `cors` | Standard CORS header. |
| `sec-fetch-site` | `same-site` | Standard CORS header. |

### JWT Structure

The `gc-token` value is a JWT (three base64url segments separated by dots). Decoded payload fields observed:

| Field | Description |
|-------|-------------|
| `type` | Token type string |
| `cid` | Client ID (GameChanger internal) |
| `email` | User's email address |
| `userId` | User's UUID |
| `rtkn` | Refresh token reference |
| `iat` | Issued-at timestamp (Unix seconds) |
| `exp` | Expiry timestamp (Unix seconds) |

### Expiry Detection

- Expiry window: approximately 1 hour (`exp - iat ≈ 3864 seconds` based on captured token).
- Detect expiry by comparing current Unix time to the `exp` claim in the JWT payload.
- When expired, the API returns an HTTP 401. There is no observed grace period.
- **Token refresh endpoint**: `[NOT YET DISCOVERED]`. Rotation currently requires re-capturing from browser network traffic.

### Example Credential Block (Redacted)

```
gc-token: TOKEN_REDACTED
gc-app-name: web
gc-device-id: DEVICE_ID_REDACTED
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
DNT: 1
Referer: https://web.gc.com/
sec-ch-ua: "Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
```

---

## Content Type Convention

GameChanger uses custom versioned media types rather than `application/json`.

**For GET requests with no body:**
```
Content-Type: application/vnd.gc.com.none+json; version=undefined
```

**For Accept headers**, the pattern is:
```
application/vnd.gc.com.<resource_type>:<cardinality>+json; version=<semver>
```

Known resource type / version combinations observed:

| Resource Type | Cardinality | Version | Used By |
|---------------|-------------|---------|---------|
| `game_summary` | `list` | `0.1.0` | Game Summaries endpoint |
| `player` | `list` | `0.1.0` | Team Roster endpoint |
| `team` | `list` | `0.10.0` | List User's Teams endpoint |
| `event` | `list` | `0.2.0` | Team Schedule endpoint |
| `video_stream_asset_metadata` | `list` | `0.0.0` | Video Stream Assets endpoint |

The version number appears to be an API evolution version for that resource type, not a global API version. Use the version observed in curl captures -- sending an incorrect version may return a 406 Not Acceptable.

---

## Pagination Scheme

**Type**: Cursor-based (integer offset/cursor, not page number).

**Activation**: Send `x-pagination: true` header. Without this header, the endpoint may return all records or a default set.

**Cursor parameter**: `?start_at=<integer>` appended to the URL.

**Cursor source**: The cursor value for the next page appears in the response (exact response field name `[NEEDS VERIFICATION]`). Observed cursor values from live pagination: initial request (no cursor), then `?start_at=16734063`, then `?start_at=19308506`.

**End of results**: `[NEEDS VERIFICATION]` -- likely an empty list or a response with no next-cursor field.

**Observed on**: Game Summaries, Video Stream Assets.

**Not observed on**: Team Roster, Team Schedule (may not be paginated or may use a different scheme).

---

## Endpoints

---

### GET /me/teams

**Description**: Returns the list of teams the authenticated user has access to (the entry point for discovering team IDs).

**Auth**: Required (see [Credential Scheme](#credential-scheme)).

**Path parameters**: None.

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include` | string | Observed required | `user_team_associations` — includes membership/role data alongside each team. |

**Required headers** (in addition to base auth headers):

```
Accept: application/vnd.gc.com.team:list+json; version=0.10.0
cache-control: no-cache
pragma: no-cache
origin: https://web.gc.com
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
```

**Example request**:

```
GET https://api.team-manager.gc.com/me/teams?include=user_team_associations
Accept: application/vnd.gc.com.team:list+json; version=0.10.0
gc-token: TOKEN_REDACTED
gc-app-name: web
gc-device-id: DEVICE_ID_REDACTED
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
DNT: 1
Referer: https://web.gc.com/
cache-control: no-cache
pragma: no-cache
origin: https://web.gc.com
```

**Example response** (condensed, schema inferred): `[NEEDS VERIFICATION -- no full response sample captured]`

```json
[
  {
    "id": "TEAM_ID_REDACTED",
    "name": "Team Name",
    "sport": "baseball",
    "user_team_associations": [
      {
        "role": "manager",
        "user_id": "USER_ID_REDACTED"
      }
    ]
  }
]
```

**Pagination**: Not observed. Assumed to return all teams for the user.

**Notes**: Use this endpoint first in any session to discover the `team_id` values needed for all subsequent requests. The `id` field on each returned team object is the `{team_id}` used throughout the API.

---

### GET /teams/{team_id}/players

**Description**: Returns the roster (player list) for a given team. Also used to retrieve opponent team rosters by substituting the opponent's `team_id`.

**Auth**: Required.

**Path parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | UUID string | Yes | GameChanger team identifier. |

**Query parameters**: None observed.

**Required headers** (in addition to base auth headers):

```
Accept: application/vnd.gc.com.player:list+json; version=0.1.0
```

**Notes from curl capture**: The observed curl for this endpoint did NOT include `gc-user-action-id` or `gc-user-action` headers, suggesting those are optional for this endpoint.

**Example request**:

```
GET https://api.team-manager.gc.com/teams/TEAM_ID_REDACTED/players
Accept: application/vnd.gc.com.player:list+json; version=0.1.0
gc-token: TOKEN_REDACTED
gc-app-name: web
gc-device-id: DEVICE_ID_REDACTED
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
DNT: 1
Referer: https://web.gc.com/
```

**Example response**: `[NEEDS VERIFICATION -- no response sample captured]`

```json
[
  {
    "id": "PLAYER_ID_REDACTED",
    "first_name": "FIRST_NAME_REDACTED",
    "last_name": "LAST_NAME_REDACTED",
    "jersey_number": "10",
    "position": "pitcher"
  }
]
```

**Pagination**: Not observed. `[NEEDS VERIFICATION]`

**Notes**: This endpoint serves double duty -- it returns the roster for any team (own team or opponent) when given that team's `team_id`. Opponent `team_id` values are discovered from the `opponent_id` field in game summaries.

---

### GET /teams/{team_id}/schedule

**Description**: Returns the full schedule (events) for a team, including game dates, opponents, and location details.

**Auth**: Required.

**Path parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | UUID string | Yes | GameChanger team identifier. |

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fetch_place_details` | boolean | Observed as `true` | When `true`, includes venue/location details in the response. |

**Required headers** (in addition to base auth headers):

```
Accept: application/vnd.gc.com.event:list+json; version=0.2.0
gc-user-action: data_loading:team
gc-user-action-id: ACTION_ID_REDACTED
cache-control: no-cache
pragma: no-cache
origin: https://web.gc.com
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
```

**Example request**:

```
GET https://api.team-manager.gc.com/teams/TEAM_ID_REDACTED/schedule?fetch_place_details=true
Accept: application/vnd.gc.com.event:list+json; version=0.2.0
gc-token: TOKEN_REDACTED
gc-app-name: web
gc-device-id: DEVICE_ID_REDACTED
gc-user-action: data_loading:team
gc-user-action-id: ACTION_UUID_REDACTED
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
DNT: 1
Referer: https://web.gc.com/
cache-control: no-cache
pragma: no-cache
origin: https://web.gc.com
```

**Example response**: `[NEEDS VERIFICATION -- no response sample captured]`

```json
[
  {
    "id": "EVENT_ID_REDACTED",
    "event_type": "game",
    "start_time": "2025-04-15T18:00:00Z",
    "home_away": "home",
    "opponent_name": "Opponent Team Name",
    "location": {
      "name": "Venue Name",
      "address": "ADDRESS_REDACTED"
    }
  }
]
```

**Pagination**: Not observed. `[NEEDS VERIFICATION]`

**Notes**: The `gc-user-action-id` is a fresh UUID per request (observed in curl captures). The schedule event objects are expected to include `event_id` values that correspond to the `event_id` fields in game summaries.

---

### GET /teams/{team_id}/game-summaries

**Description**: Returns a paginated list of game summaries for a team. Each summary includes scores, game status, home/away designation, and baseball-specific completion data. This is the primary endpoint for discovering game results.

**Auth**: Required.

**Path parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | UUID string | Yes | GameChanger team identifier. |

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_at` | integer | No (pagination only) | Cursor for the next page. Omit for first page. |

**Required headers** (in addition to base auth headers):

```
Accept: application/vnd.gc.com.game_summary:list+json; version=0.1.0
gc-user-action: data_loading:events
x-pagination: true
```

**Note**: `gc-user-action` value `data_loading:event` (singular) was also observed for some game-related requests. Use `data_loading:events` (plural) for the list endpoint.

**Example request (first page)**:

```
GET https://api.team-manager.gc.com/teams/TEAM_ID_REDACTED/game-summaries
Accept: application/vnd.gc.com.game_summary:list+json; version=0.1.0
gc-token: TOKEN_REDACTED
gc-app-name: web
gc-device-id: DEVICE_ID_REDACTED
gc-user-action: data_loading:events
x-pagination: true
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
DNT: 1
Referer: https://web.gc.com/
```

**Example request (subsequent page)**:

```
GET https://api.team-manager.gc.com/teams/TEAM_ID_REDACTED/game-summaries?start_at=136418700
Accept: application/vnd.gc.com.game_summary:list+json; version=0.1.0
gc-token: TOKEN_REDACTED
gc-app-name: web
gc-device-id: DEVICE_ID_REDACTED
gc-user-action: data_loading:events
x-pagination: true
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
DNT: 1
Referer: https://web.gc.com/
```

**Example response** (confirmed from live response, 34 records observed, condensed to one representative record):

```json
[
  {
    "event_id": "EVENT_ID_REDACTED",
    "game_stream": {
      "id": "GAME_STREAM_ID_REDACTED",
      "game_id": "GAME_ID_REDACTED",
      "game_status": "completed",
      "home_away": "away",
      "is_archived": false,
      "opponent_id": "OPPONENT_TEAM_ID_REDACTED",
      "scoring_user_id": "USER_ID_REDACTED",
      "sabertooth_major_version": 4,
      "game_clock_elapsed_seconds_at_last_pause": "0",
      "game_clock_enabled": false,
      "game_clock_mode": "up",
      "game_clock_start_time_milliseconds": "0",
      "game_clock_state": "paused"
    },
    "last_scoring_update": "2025-05-24T19:10:40.662Z",
    "opponent_team_score": 8,
    "owning_team_score": 4,
    "home_away": "away",
    "game_status": "completed",
    "sport_specific": {
      "bats": {
        "total_outs": 28,
        "inning_details": {
          "inning": 5,
          "half": "bottom"
        }
      }
    }
  }
]
```

**Pagination**: Cursor-based via `?start_at=<integer>`. Enable with `x-pagination: true` header. The response was observed returning 34 records; the mechanism for communicating the next cursor is `[NEEDS VERIFICATION]`.

**Field notes**:

| Field | Notes |
|-------|-------|
| `event_id` | UUID. Links this summary to a schedule event. |
| `game_stream.opponent_id` | UUID of the opponent team. Use this to query opponent roster via `/teams/{opponent_id}/players`. |
| `game_stream.sabertooth_major_version` | Internal versioning field. Value `4` observed. |
| `game_stream.game_clock_*` | Fields only present on some records (game-type dependent). Omitted when not applicable. |
| `home_away` | Appears at both root level and inside `game_stream` with identical values. |
| `game_status` | Appears at both root level and inside `game_stream` with identical values. |
| `sport_specific.bats.total_outs` | Total outs recorded in the game (baseball-specific). |
| `sport_specific.bats.inning_details.inning` | Inning number when the game ended. |
| `sport_specific.bats.inning_details.half` | `"top"` or `"bottom"` — half-inning when the game ended. |

---

### Game Stats / Box Score

**Status**: `[NOT YET DISCOVERED]`

This endpoint category is required for E-002 (ingestion) and is the highest-priority undiscovered endpoint.

**What we need**: An endpoint that returns per-game batting and pitching statistics at the individual player level (box score equivalent). Expected data: at-bats, hits, runs, RBIs, strikeouts, walks per player per game.

**Discovery approach**: Capture network traffic while clicking into a completed game in the GameChanger web app (`https://web.gc.com`). The URL pattern is expected to reference either `event_id` or `game_id` from the game summaries response.

**Candidate URL patterns** (inferred, unconfirmed):

```
GET /teams/{team_id}/events/{event_id}/stats
GET /events/{event_id}/box-score
GET /game-streams/{game_stream_id}/stats
```

**Action required**: Provide a curl capture from the GameChanger web app while viewing a completed game's box score or stats tab.

---

### Player Season Aggregate Stats

**Status**: `[NOT YET DISCOVERED]`

**What we need**: An endpoint returning season-level batting and pitching statistics aggregated per player (OBP, K%, BB%, ERA, etc.).

**Discovery approach**: Capture network traffic while viewing a team's season stats page or a player's profile page in the GameChanger web app.

**Candidate URL patterns** (inferred, unconfirmed):

```
GET /teams/{team_id}/stats?season={year}
GET /players/{player_id}/stats?season={year}
GET /teams/{team_id}/players/{player_id}/stats
```

**Action required**: Provide a curl capture from the GameChanger web app while viewing team or player season stats.

---

### Opponent / Away Team Data

**Pattern**: Confirmed via observation.

Opponent teams are first-class team objects in the GameChanger data model. There is no separate "opponent" or "away team" API -- opponent data is accessed by using the opponent's `team_id` with the same endpoints used for any team.

**Discovery flow**:

1. Call `/teams/{own_team_id}/game-summaries` to get a list of games.
2. Extract `game_stream.opponent_id` from each game summary record.
3. Use `opponent_id` as `team_id` in subsequent calls:
   - `/teams/{opponent_id}/players` -- opponent roster `[NEEDS VERIFICATION -- access not confirmed for all opponent teams]`
   - `/teams/{opponent_id}/game-summaries` -- opponent game history `[NEEDS VERIFICATION]`
   - `/teams/{opponent_id}/schedule` -- opponent schedule `[NEEDS VERIFICATION]`

**Confirmed**: The players endpoint was successfully queried for a second team ID that appeared as `opponent_id` in game data (two distinct team UUIDs were observed in session). This supports the first-class team model.

**Note**: Access to opponent team data may depend on whether that team also uses GameChanger. Teams not on GameChanger may not have queryable records.

---

### GET /teams/{team_id}/video-stream/assets

**Description**: Returns a paginated list of video stream assets (recorded game video) for a team.

**Auth**: Required.

**Path parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | UUID string | Yes | GameChanger team identifier. |

**Query parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_at` | integer | No (pagination only) | Cursor for the next page. |

**Required headers** (in addition to base auth headers):

```
Accept: application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0
x-pagination: true
```

**Example request**:

```
GET https://api.team-manager.gc.com/teams/TEAM_ID_REDACTED/video-stream/assets
Accept: application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0
gc-token: TOKEN_REDACTED
gc-app-name: web
gc-device-id: DEVICE_ID_REDACTED
x-pagination: true
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
DNT: 1
Referer: https://web.gc.com/
```

**Example response**: `[NEEDS VERIFICATION -- no response sample captured]`

**Pagination**: Cursor-based via `?start_at=<integer>`. Three pages observed in live session with cursors: (none), `16734063`, `19308506`.

**Notes**: Video assets are low priority for the coaching analytics use case. Documented for completeness. The version `0.0.0` for the Accept header may indicate this is an early/unstable resource type.

---

## Known Limits and Quirks

### Rate Limiting

**Observed behavior**: Unknown. No rate limit response (HTTP 429) has been observed.

**Working assumption**: A delay of 500ms between sequential requests is safe. Tune upward if 429s are observed.

**Recommendation**: Implement exponential backoff on any 4xx or 5xx response. Start with 1 second, double on each retry, cap at 30 seconds.

**Note**: If a `Retry-After` header is present in a 429 response, honor it exactly.

### Fields That Appear in Some Responses but Not Others

| Field | Endpoint | Condition |
|-------|----------|-----------|
| `game_stream.game_clock_elapsed_seconds_at_last_pause` | Game Summaries | Present only on games that used game clock (non-baseball game types, or specific configurations). |
| `game_stream.game_clock_enabled` | Game Summaries | Same as above. |
| `game_stream.game_clock_mode` | Game Summaries | Same as above. |
| `game_stream.game_clock_start_time_milliseconds` | Game Summaries | Same as above. |
| `game_stream.game_clock_state` | Game Summaries | Same as above. |

### Duplicate Fields in Game Summaries

`home_away` and `game_status` both appear at the root level of a game summary record AND inside the nested `game_stream` object, with identical values in all observed cases. Prefer the root-level fields for simplicity; use `game_stream.*` for additional context only.

### Endpoints That Require Team/Season Scoping

All data endpoints are scoped to a specific `{team_id}` in the URL path. There are no observed "global" query endpoints. Season scoping (e.g., `?season=2025`) has not been observed on any confirmed endpoint but is expected on stats endpoints once discovered.

### `sabertooth_major_version`

The field `game_stream.sabertooth_major_version: 4` appears in game summary records. This is an internal GameChanger versioning field (presumably the scoring engine version). Value `4` was observed. The implications of different values are unknown. Do not use this field for application logic.

### `gc-user-action-id` Requirement

This per-request UUID header was present in some curl captures (schedule, some game endpoints) but absent in others (players endpoint). It appears to be optional for most endpoints but may be required for some. When in doubt, include it with a fresh UUID per request.

### Custom Media Types Are Strict

The `Accept` header must match the resource type and version exactly. Sending `application/json` instead of the custom media type may result in a 406 Not Acceptable. The version component (e.g., `version=0.10.0`) must also be correct -- sending a mismatched version may fail silently or return an error.

### Authentication Is a Custom Header, Not Standard Bearer

Many HTTP client libraries and API testers default to `Authorization: Bearer <token>`. GameChanger uses `gc-token: <JWT>` instead. Standard OAuth tooling will not work out of the box.

---

## Discovery Log

Entries in reverse chronological order (most recent first).

| Date | Endpoint / Finding | Method | Notes |
|------|--------------------|--------|-------|
| 2026-03-01 | Video stream assets pagination cursors (`16734063`, `19308506`) | curl capture | Three paginated pages observed. |
| 2026-03-01 | `GET /teams/{team_id}/video-stream/assets` | curl capture | Endpoint exists; response schema not captured. |
| 2026-03-01 | Opponent team roster access confirmed | curl capture | Second team UUID (appearing as `opponent_id`) successfully used with `/teams/{id}/players`. |
| 2026-03-01 | `GET /teams/{team_id}/players` | curl capture | Endpoint URL and headers confirmed; response schema not captured. |
| 2026-03-01 | `GET /teams/{team_id}/schedule?fetch_place_details=true` | curl capture | Endpoint URL and headers confirmed; response schema not captured. |
| 2026-03-01 | Game summaries response schema | curl capture + live response | 34 records observed. Full root-level and `game_stream` field inventory documented. |
| 2026-03-01 | `GET /teams/{team_id}/game-summaries` (with pagination) | curl capture + live response | Pagination confirmed working. |
| 2026-03-01 | `GET /me/teams?include=user_team_associations` | curl capture | Entry point endpoint confirmed. Response schema inferred. |
| 2026-03-01 | JWT payload field inventory (`type`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp`) | token decode | Expiry window ~1 hour confirmed from `exp - iat`. |
| 2026-03-01 | Auth scheme: `gc-token`, `gc-app-name`, `gc-device-id` headers | curl capture | All three required on every request. |
| 2026-03-01 | Base URL: `https://api.team-manager.gc.com` | curl capture | Confirmed from multiple endpoint captures. |
| 2026-03-01 | Custom versioned media types (`application/vnd.gc.com.*`) | curl capture | Content-Type and Accept conventions documented. |
| 2026-03-01 | Cursor-based pagination via `x-pagination: true` + `?start_at=` | curl capture | Pattern confirmed on game-summaries and video-stream endpoints. |
