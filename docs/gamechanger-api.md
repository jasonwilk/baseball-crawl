# GameChanger API Reference

This document is the single source of truth for GameChanger API knowledge. It is maintained by the `api-scout` agent and updated whenever new endpoints or behaviors are confirmed from live traffic captures.

**Last updated:** 2026-03-04 (NEW: /teams/{team_id}/players/{player_id}/stats -- per-game player stats with spray charts and cumulative rolling stats)
**Status of each endpoint is noted inline.**

---

## Table of Contents

1. [Base URL](#base-url)
2. [Authentication](#authentication)
3. [Request Headers](#request-headers)
4. [Content-Type Convention](#content-type-convention)
5. [Pagination](#pagination)
6. [Endpoints](#endpoints)
   - [GET /me/teams](#get-meteams)
   - [GET /teams/{team_id}/schedule](#get-teamsteam_idschedule)
   - [GET /teams/{team_id}/game-summaries](#get-teamsteam_idgame-summaries)
   - [GET /teams/{team_id}/players](#get-teamsteam_idplayers)
   - [GET /teams/{team_id}/video-stream/assets](#get-teamsteam_idvideo-streamassets)
   - [GET /teams/{team_id}/season-stats](#get-teamsteam_idseason-stats)
   - [GET /teams/{team_id}/associations](#get-teamsteam_idassociations)
   - [GET /teams/{team_id}/players/{player_id}/stats](#get-teamsteam_idplayersplayer_idstats)
7. [Response Schemas](#response-schemas)
   - [me-teams](#schema-me-teams)
   - [game-summaries](#schema-game-summaries)
   - [season-stats](#schema-season-stats)
   - [associations](#schema-associations)
   - [player-stats](#schema-player-stats)
8. [Key Observations](#key-observations)
9. [Header Quick Reference](#header-quick-reference)
10. [Notes for Implementers](#notes-for-implementers)

---

## Base URL

```
https://api.team-manager.gc.com
```

The web app is served from `https://web.gc.com`. The API and web app are on different subdomains (same-site, not same-origin), which is why requests include `sec-fetch-site: same-site`.

---

## Authentication

### Token Header

GameChanger does **not** use `Authorization: Bearer`. Auth is carried in a custom header:

```
gc-token: <JWT>
```

> **Important for implementers:** The `http-integration-guide.md` session factory pattern shows `Authorization: Bearer` as an example. For GameChanger, you must inject `gc-token` instead. See [Notes for Implementers](#notes-for-implementers).

### JWT Structure

The `gc-token` value is a standard JWT. The decoded payload contains:

| Field    | Description                                      |
|----------|--------------------------------------------------|
| `type`   | Token type (e.g., `"access"`)                   |
| `cid`    | Client ID                                        |
| `email`  | Authenticated user's email address               |
| `userId` | GameChanger user UUID                            |
| `rtkn`   | Refresh token reference                          |
| `iat`    | Issued-at timestamp (Unix seconds)               |
| `exp`    | Expiration timestamp (Unix seconds)              |

**Token lifetime:** Approximately 1 hour (observed: exp - iat ≈ 3864 seconds). Auth expiration must be handled gracefully — see CLAUDE.md "GameChanger API" section.

### Device ID

Each session also sends a stable 32-character hex string in `gc-device-id`. This appears to be a persistent browser/device identifier, not a per-session value. It should be stored alongside credentials and reused across sessions.

```
gc-device-id: <32-char hex string>
```

### App Identity

```
gc-app-name: web
```

This tells the API the request is coming from the web application.

---

## Request Headers

### Required Headers (send on every request)

| Header          | Value                                              | Notes                                           |
|-----------------|----------------------------------------------------|-------------------------------------------------|
| `gc-token`      | `<JWT>`                                            | Auth token — never log or commit               |
| `gc-device-id`  | `<32-char hex>`                                    | Stable device identifier — treat as credential |
| `gc-app-name`   | `web`                                              | Fixed value                                     |
| `User-Agent`    | Chrome on macOS (see below)                        | Must match a real browser UA                    |
| `Accept`        | Endpoint-specific (see each endpoint)              | Resource-typed accept header                    |

### Standard Browser Headers (include on all requests)

These are sent by Chrome automatically. Including them makes traffic look authentic:

| Header                 | Value                                                                      |
|------------------------|----------------------------------------------------------------------------|
| `sec-ch-ua`            | `"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"`       |
| `sec-ch-ua-mobile`     | `?0`                                                                       |
| `sec-ch-ua-platform`   | `"macOS"`                                                                  |
| `DNT`                  | `1`                                                                        |
| `Referer`              | `https://web.gc.com/`                                                      |

### Navigation-Context Headers (appear in some requests)

These are added by Chrome for top-level navigations and certain fetch patterns. They are optional but should be included when observed in captures for the relevant endpoint:

| Header            | Value         | When seen                                 |
|-------------------|---------------|-------------------------------------------|
| `origin`          | `https://web.gc.com` | Schedule, /me/teams                |
| `sec-fetch-dest`  | `empty`       | Schedule, /me/teams                       |
| `sec-fetch-mode`  | `cors`        | Schedule, /me/teams                       |
| `sec-fetch-site`  | `same-site`   | Schedule, /me/teams                       |
| `cache-control`   | `no-cache`    | Schedule, /me/teams                       |
| `pragma`          | `no-cache`    | Schedule, /me/teams                       |
| `priority`        | `u=1, i`      | Schedule, /me/teams                       |

### Optional Per-Request Tracking Headers

| Header                | Value                  | Notes                                                   |
|-----------------------|------------------------|---------------------------------------------------------|
| `gc-user-action-id`   | `<UUID v4>`            | Per-request UUID for action tracking. Absent from /players capture. |
| `gc-user-action`      | `<action string>`      | Action label. Values seen: `data_loading:events`, `data_loading:event`, `data_loading:team`. Absent from /players capture. |

### Confirmed User-Agent String

```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

This is Chrome 145 on macOS. Update `src/http/headers.py` when Chrome falls more than 2 major versions behind — see `docs/http-integration-guide.md`.

---

## Content-Type Convention

GameChanger uses vendor-typed media types for both `Content-Type` and `Accept`.

### GET requests (no body)

```
Content-Type: application/vnd.gc.com.none+json; version=undefined
```

### Accept header pattern

```
Accept: application/vnd.gc.com.<resource_type>:<cardinality>+json; version=<semver>
```

| Component       | Examples                                                                |
|-----------------|-------------------------------------------------------------------------|
| `resource_type` | `game_summary`, `player`, `team`, `event`, `video_stream_asset_metadata` |
| `cardinality`   | `list` (for collections)                                                |
| `version`       | `0.1.0`, `0.2.0`, `0.10.0`, `0.0.0`                                   |

Version numbers vary per resource type and must match exactly what the client sends — use the versions confirmed in captures below.

---

## Pagination

### How it works

- Enable pagination by sending the **request** header: `x-pagination: true`
- The **response** carries the full URL for the next page in the `x-next-page` response header
- The cursor embedded in that URL is the `start_at` query parameter (an integer, not a UUID or offset count)
- The response body is a **bare JSON array** -- no pagination wrapper or metadata object

### Request pattern

```
GET /teams/{team_id}/game-summaries
x-pagination: true
```

### Response headers (pagination-relevant)

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/game-summaries?start_at=136418700
```

### Behavior

- First page: omit `start_at` (or use no cursor); send `x-pagination: true`
- Subsequent pages: use the full URL from the `x-next-page` response header (or extract its `start_at` value)
- When there are no more pages: `x-next-page` header is absent from the response
- Observed page size: **50 records per page** on game-summaries with `x-pagination: true`
- Observed in video-stream assets: 3 pages with cursors `16734063` and `19308506`

**Confirmed 2026-03-04 (both pages):** `x-next-page` response header carries the full next-page URL. Page 1 (no cursor) returned 50 records and `x-next-page: .../game-summaries?start_at=136418700`. Page 2 (`start_at=136418700`) returned 42 records and **no `x-next-page` header** -- confirming end-of-pagination behavior. Total records in this full-season dataset: 92. The cursor value `136418700` is an integer sequence number (not a Unix timestamp, not a record offset).

---

## Endpoints

### GET /me/teams

**Status:** CONFIRMED LIVE -- 200 OK, 15 team records returned. Schema fully documented 2026-03-04.

Discover all teams the authenticated user belongs to. This is the recommended entry point for finding team UUIDs without hardcoding them. The response includes full team metadata for every team the authenticated user has any association with (manager, player, family, or fan).

```
GET https://api.team-manager.gc.com/me/teams?include=user_team_associations
```

#### Query Parameters

| Parameter               | Required | Description                                          |
|-------------------------|----------|------------------------------------------------------|
| `include`               | No       | `user_team_associations` — when present, adds a `user_team_associations` array to each team object listing the authenticated user's roles for that team. Without this parameter the field may be absent or empty. |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team:list+json; version=0.10.0
accept-language: en-US,en;q=0.9
cache-control: no-cache
pragma: no-cache
priority: u=1, i
dnt: 1
origin: https://web.gc.com
referer: https://web.gc.com/
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
x-pagination: true
```

**Note on gc-user-action:** No `gc-user-action` or `gc-user-action-id` headers were present in this capture. Consistent with other informational endpoints -- these tracking headers appear optional.

**Note on x-pagination:** The `x-pagination: true` request header was sent. No `x-next-page` response header appeared -- all 15 teams returned in a single response (13,597 bytes). Pagination infrastructure is available but not triggered by this dataset size.

#### Response Headers (observed 2026-03-04)

```
HTTP/2 200
content-type: application/json; charset=utf-8
content-length: 13597
x-server-epoch: <unix-seconds>
etag: "351d-2rxOY7bb2sc+UHzGkqqVG8IAtTw"
vary: Origin, Accept-Encoding
access-control-allow-origin: https://web.gc.com
access-control-expose-headers: Location,x-next-page,gc-signature,gc-timestamp,x-datadog-trace-id,...
x-cache: Miss from cloudfront
via: 1.1 <cloudfront-node> (CloudFront)
```

#### Response

See [Schema: me-teams](#schema-me-teams). The response is a **bare JSON array** of team objects -- no wrapper object.

#### Known Limitations

- **team_player_count always null** -- the `team_player_count` field was `null` for all 15 teams in this capture. It appears reserved for future use or requires a different access level.
- **team_avatar_image always null** -- all 15 teams had `null` for this field. Teams may not have custom avatars or this field may reflect something else.
- **ngb is a JSON-encoded string, not a native array** -- the `ngb` field contains a JSON string of an array (e.g., `"[\"usssa\"]"` or `"[]"`), not a native JSON array. Must be double-decoded when parsing.
- **No LSB high school teams observed** -- the 15 teams returned are all youth travel ball / recreational teams. The LSB Freshman, JV, Varsity, and Reserve teams expected from the project scope do not appear. This gc-token is associated with Jason's personal travel ball account, not an LSB program coaching account. A separate account with coaching access to the LSB high school teams will be needed.
- **No pagination observed** -- all 15 teams returned in one response. The page-size ceiling is unknown.
- **Scope is per-account** -- only teams the authenticated user has a relationship to appear. Opponent teams not in the user's association list are not shown here.

---

### GET /teams/{team_id}/schedule

**Status:** Confirmed from curl capture.

Returns the full event schedule for a team, including game metadata and location details.

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule?fetch_place_details=true
```

#### Path Parameters

| Parameter  | Description          |
|------------|----------------------|
| `team_id`  | Team UUID            |

#### Query Parameters

| Parameter             | Required | Description                              |
|-----------------------|----------|------------------------------------------|
| `fetch_place_details` | No       | `true` — enriches events with venue data |

#### Headers

```
gc-token: <JWT>
gc-device-id: <32-char hex>
gc-app-name: web
Accept: application/vnd.gc.com.event:list+json; version=0.2.0
gc-user-action: data_loading:team
gc-user-action-id: <UUID>
cache-control: no-cache
pragma: no-cache
priority: u=1, i
origin: https://web.gc.com
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
User-Agent: <browser UA>
```

#### Response

A list of event objects. Response schema not yet fully documented — update when captured.

---

### GET /teams/{team_id}/game-summaries

**Status:** CONFIRMED LIVE — 92 total records across 2 pages fully retrieved. Last verified: 2026-03-04 (page 2 capture).

Returns scored game summaries for a team. Supports cursor-based pagination. The response is a bare JSON array (no wrapper object). Pagination metadata is carried in response headers, not the body.

```
GET https://api.team-manager.gc.com/teams/{team_id}/game-summaries
GET https://api.team-manager.gc.com/teams/{team_id}/game-summaries?start_at={cursor}
```

#### Path Parameters

| Parameter  | Description          |
|------------|----------------------|
| `team_id`  | Team UUID            |

#### Query Parameters

| Parameter  | Required | Description                         |
|------------|----------|-------------------------------------|
| `start_at` | No       | Pagination cursor (integer sequence number). Omit for first page. Obtain from `x-next-page` response header. |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.game_summary:list+json; version=0.1.0
x-pagination: true
gc-user-action: data_loading:events
gc-user-action-id: {UUID}
Content-Type: application/vnd.gc.com.none+json; version=undefined
DNT: 1
Referer: https://web.gc.com/
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
User-Agent: <browser UA>
```

#### Pagination Response Header

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/game-summaries?start_at={cursor}
```

When `x-next-page` is absent from the response headers, the current page is the last page.

**Note on gc-user-action value:** A prior capture showed `data_loading:event` (singular) on a first-page request. The 2026-03-04 page 1 capture used `data_loading:events` (plural) and returned 50 records successfully. The 2026-03-04 page 2 capture (this capture) also used `data_loading:events` (plural) and returned 42 records. Plural form is now confirmed on both pages. The singular form may have been incidental -- current recommendation: use `data_loading:events` (plural) for game-summaries.

#### Other Response Headers (observed 2026-03-04, confirmed on both pages)

```
content-type: application/json; charset=utf-8
x-server-epoch: <unix-seconds>
vary: Origin, Accept-Encoding
etag: "<etag-value>"
access-control-allow-origin: https://web.gc.com
access-control-expose-headers: Location,x-next-page,gc-signature,gc-timestamp,x-datadog-trace-id,x-datadog-parent-id,x-datadog-origin,x-datadog-sampling-priority
x-cache: Miss from cloudfront
via: 1.1 <cloudfront-node> (CloudFront)
x-amz-cf-pop: <CloudFront POP code>
x-amz-cf-id: <CloudFront request ID>
```

The API is served through CloudFront CDN. ETags are present and could be used for conditional requests, though this has not been tested.

**Note on `access-control-expose-headers`:** Lists `gc-signature` and `gc-timestamp` as exposable headers -- these have not been observed in response bodies yet. The `x-datadog-*` headers indicate Datadog APM is in use for backend observability.

#### Response

See [Schema: game-summaries](#schema-game-summaries).

---

### GET /teams/{team_id}/players

**Status:** Confirmed from curl capture.

Returns the roster for a team. This endpoint also works for opponent teams — the `opponent_id` from game-summaries is a full team UUID that can be passed here to retrieve opponent rosters.

```
GET https://api.team-manager.gc.com/teams/{team_id}/players
```

#### Path Parameters

| Parameter  | Description                                                |
|------------|------------------------------------------------------------|
| `team_id`  | Team UUID. Can be your own team or an opponent team UUID.  |

#### Headers

```
gc-token: <JWT>
gc-device-id: <32-char hex>
gc-app-name: web
Accept: application/vnd.gc.com.player:list+json; version=0.1.0
User-Agent: <browser UA>
```

**Note:** The `/players` capture did not include `gc-user-action-id` or `gc-user-action`. These tracking headers appear to be optional across all endpoints.

#### Response

A list of player objects. Response schema not yet fully documented — update when captured.

---

### GET /teams/{team_id}/video-stream/assets

**Status:** Confirmed from curl capture (3 pages observed).

Returns video stream asset metadata for a team. Supports pagination.

```
GET https://api.team-manager.gc.com/teams/{team_id}/video-stream/assets
GET https://api.team-manager.gc.com/teams/{team_id}/video-stream/assets?start_at={cursor}
```

#### Path Parameters

| Parameter  | Description |
|------------|-------------|
| `team_id`  | Team UUID   |

#### Query Parameters

| Parameter  | Required | Description                        |
|------------|----------|------------------------------------|
| `start_at` | No       | Pagination cursor (integer). Observed values: `16734063`, `19308506`. |

#### Headers

```
gc-token: <JWT>
gc-device-id: <32-char hex>
gc-app-name: web
Accept: application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0
x-pagination: true
gc-user-action: data_loading:events
User-Agent: <browser UA>
```

#### Response

A list of video asset metadata objects. Response schema not yet documented — update when captured.

---

### GET /teams/{team_id}/season-stats

**Status:** CONFIRMED LIVE -- 200 OK, 10+ player records returned. Discovered 2026-03-04.

Returns season-aggregate statistics for all players on a team. Includes per-player batting, pitching, and fielding stats, team aggregate totals, and hot/cold streak data.

```
GET https://api.team-manager.gc.com/teams/{team_id}/season-stats
```

#### Path Parameters

| Parameter  | Description          |
|------------|----------------------|
| `team_id`  | Team UUID            |

#### Query Parameters

None observed. No pagination headers were sent or returned -- the response appears to be a single object containing all players.

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_season_stats+json; version=0.2.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
gc-user-action: data_loading:team_stats
gc-user-action-id: {UUID}
cache-control: no-cache
pragma: no-cache
priority: u=1, i
origin: https://web.gc.com
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
DNT: 1
Referer: https://web.gc.com/
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**New gc-user-action value:** `data_loading:team_stats` -- not seen on any previously documented endpoint.

#### Response

See [Schema: season-stats](#schema-season-stats).

#### Known Limitations

- **No player names in response** -- players are keyed by UUID only. Cross-reference with `/teams/{team_id}/players` to resolve names.
- **Season scope is unclear** -- no date range or season year is embedded in the response. Observed GP values of 84-92 suggest a full season. Whether season-scoping query parameters exist is unknown.
- **Defense merges pitching and fielding** -- a player who both pitches and plays the field will have pitcher stats (ERA, IP, K, BB) and fielder stats (PO, A, E, `IP:POS`) combined in the same `defense` object.
- **Many fields consistently 0** -- approximately 15+ fields (`CH%`, `OS%`, `FB%`, `SL%`, `KC%`, `KB%`, `CB%`, `DC%`, `DB%`, `RB%`, `SC%`, `CT%`, `GITP`, `OSSM`, `OSSW`) were 0 for every player in this capture. May be for future features or other sports.
- **Opponent teams untested** -- unknown whether this endpoint returns stats when called with an opponent's team UUID.

---

### GET /teams/{team_id}/associations

**Status:** CONFIRMED LIVE -- 200 OK, 244 records returned. Discovered 2026-03-04.

Returns all user-team associations for a team. Each record maps a GameChanger user UUID to the team with a role label (`manager`, `player`, `family`, or `fan`). This is the team's full membership list -- everyone who has any relationship to the team in GameChanger.

```
GET https://api.team-manager.gc.com/teams/{team_id}/associations
```

#### Path Parameters

| Parameter  | Description          |
|------------|----------------------|
| `team_id`  | Team UUID            |

#### Query Parameters

None observed.

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_associations:list+json; version=0.0.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
x-pagination: true
accept-language: en-US,en;q=0.9
cache-control: no-cache
pragma: no-cache
priority: u=1, i
origin: https://web.gc.com
dnt: 1
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Note on gc-user-action:** This endpoint capture did **not** include `gc-user-action` or `gc-user-action-id` headers -- consistent with the `/players` capture behavior. These tracking headers appear optional for this endpoint.

**Note on x-pagination:** The `x-pagination: true` request header was sent. No `x-next-page` response header appeared -- all 244 records were returned in a single response (29,548 bytes). Pagination infrastructure is available on this endpoint (the `access-control-expose-headers` includes `x-next-page`) but was not triggered by this dataset size.

#### Response Headers (observed 2026-03-04)

```
content-type: application/json; charset=utf-8
content-length: 29548
x-server-epoch: <unix-seconds>
etag: "736c-wfbfBfFmMyl4sOLZ3eQ0LE4vT3w"
access-control-expose-headers: Location,x-next-page,gc-signature,gc-timestamp,...
vary: Origin, Accept-Encoding
x-cache: Miss from cloudfront
via: 1.1 <cloudfront-node> (CloudFront)
```

No `x-next-page` response header was present -- this was a complete single-page response.

#### Response

See [Schema: associations](#schema-associations).

#### Known Limitations

- **No player names** -- `user_id` values must be cross-referenced with `/teams/{team_id}/players` to get names for records where `association == "player"`.
- **Low player count vs. roster size** -- this sample returned only 2 records with `association: "player"` out of 244 total, despite an expected roster of 12-15. The `player` association appears to reflect only GameChanger app users explicitly linked as a player role, not the full active roster. Use `/teams/{team_id}/players` for authoritative roster data.
- **Opponent teams untested** -- unknown whether this endpoint returns data when called with an opponent's team UUID.
- **user_id-to-player UUID mapping unconfirmed** -- it is unknown whether `user_id` values for `association: "player"` records match the player UUIDs returned by `/teams/{team_id}/players`. This cross-reference has not been verified.

---

### GET /teams/{team_id}/players/{player_id}/stats

**Status:** CONFIRMED LIVE -- 200 OK, 80 records returned. Discovered 2026-03-04.

Returns per-game statistics for a specific player, including per-game batting/pitching/fielding stats, rolling cumulative season stats (as of each game), and spray chart data (ball-in-play location coordinates) for both offensive and defensive plays.

This is the **per-game player stats endpoint** -- the missing piece that `/teams/{team_id}/season-stats` aggregates but does not break down by game.

```
GET https://api.team-manager.gc.com/teams/{team_id}/players/{player_id}/stats
```

#### Path Parameters

| Parameter    | Description                                                    |
|--------------|----------------------------------------------------------------|
| `team_id`    | Team UUID. Must be the team the player belongs to.             |
| `player_id`  | Player UUID. Obtain from `GET /teams/{team_id}/players`.       |

#### Query Parameters

None observed in this capture.

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.player_stats:list+json; version=0.0.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
gc-user-action: data_loading:player_stats
gc-user-action-id: {UUID}
accept-language: en-US,en;q=0.9
cache-control: no-cache
pragma: no-cache
priority: u=1, i
origin: https://web.gc.com
referer: https://web.gc.com/
dnt: 1
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**New gc-user-action value:** `data_loading:player_stats` -- not seen on any previously documented endpoint.

#### Pagination

No pagination headers were sent or observed in the response. All 80 records were returned in a single response (387 KB). Whether pagination applies to players with more game appearances is unknown.

#### Response

See [Schema: player-stats](#schema-player-stats).

#### Known Limitations

- **Player ID required** -- there is no team-wide equivalent of this endpoint. To get per-game stats for all players, you must call this endpoint once per player UUID.
- **No player name in response** -- records carry `event_id`, `stream_id`, `game_date`, and stats only. No player identity is embedded. The `player_id` in the URL is the sole link back to the player.
- **Season scope unclear** -- 80 records spanning 2025-04-01 through 2025-07-15 were returned. No query parameters for season/year filtering were observed. The full history for the player (or all games for that team+player) appears to be returned.
- **Stats sections are conditional** -- `player_stats.stats.offense` is absent for games where the player appeared only as a pitcher (2 of 80 records). `player_stats.stats.defense` is absent for 4 records (DH appearances or offensive-only games). Parse defensively.
- **Spray charts are sometimes null** -- `offensive_spray_charts` was null for 24 of 80 games; `defensive_spray_charts` was null for 67 of 80 games. Null indicates no tracked ball-in-play events for that role in that game.
- **Cumulative stats are rolling** -- `cumulative_stats` represents the player's season totals through and including the game date of that record. Records are NOT returned in strict chronological order; sort by `game_date` before interpreting cumulative trajectory.
- **Defense section combines pitching and fielding** -- same behavior as `/season-stats`. Use `GP:P` (games as pitcher) and `GP:F` (games in field) to separate contexts.

---

## Response Schemas

### Schema: me-teams

Returned by `GET /me/teams?include=user_team_associations`. The response is a **bare JSON array** -- no wrapper object. Each element is a team object representing a team the authenticated user has any association with.

**Schema confirmed from 15-record live capture on 2026-03-04.** All teams are baseball teams associated with Jason's travel ball account. LSB high school teams (Freshman, JV, Varsity, Reserve) were NOT present -- a separate coaching account is needed.

```json
[
  {
    "id": "<uuid>",
    "name": "Lincoln Rebels 14U",
    "team_type": "admin",
    "city": "Lincoln",
    "state": "NE",
    "country": "United States",
    "age_group": "14U",
    "competition_level": "club_travel",
    "sport": "baseball",
    "season_year": 2025,
    "season_name": "summer",
    "stat_access_level": "confirmed_full",
    "scorekeeping_access_level": "staff_only",
    "streaming_access_level": "confirmed_members",
    "paid_access_level": null,
    "settings": {
      "scorekeeping": {
        "bats": {
          "innings_per_game": 7,
          "shortfielder_type": "none",
          "pitch_count_alert_1": null,
          "pitch_count_alert_2": null
        }
      },
      "maxpreps": null
    },
    "organizations": [
      {
        "organization_id": "<uuid>",
        "status": "active"
      }
    ],
    "ngb": "[\"usssa\"]",
    "user_team_associations": ["family", "manager"],
    "team_avatar_image": null,
    "team_player_count": null,
    "created_at": "2024-11-02T12:34:20.229Z",
    "public_id": "a1GFM9Ku0BbF",
    "url_encoded_name": "2025-summer-lincoln-rebels-14u",
    "archived": false,
    "record": {
      "wins": 61,
      "losses": 29,
      "ties": 2
    },
    "badge_count": 0
  }
]
```

#### Field Notes

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID string | No | Team UUID. Use this as `team_id` in all other team-scoped endpoints. |
| `name` | string | No | Human-readable team name (e.g., "Lincoln Rebels 14U"). |
| `team_type` | string | No | Access/ownership type. All 15 observed: `"admin"`. May indicate other values for sponsored or league-managed teams. |
| `city` | string | No | City of the team. |
| `state` | string | No | State abbreviation (e.g., `"NE"`). |
| `country` | string | No | Country name (e.g., `"United States"` or `"USA"` -- both observed). |
| `age_group` | string | No | Age bracket string. Observed: `"8U"`, `"9U"`, `"10U"`, `"11U"`, `"12U"`, `"13U"`, `"14U"`, `"Between 13 - 18"`. The last value appears for Legion/recreational adult-range programs. |
| `competition_level` | string | No | Observed: `"club_travel"`, `"recreational"`. |
| `sport` | string | No | Always `"baseball"` in this dataset. |
| `season_year` | int | No | Four-digit year of the season (2019–2026 observed). |
| `season_name` | string | No | Season identifier. Observed: `"spring"`, `"summer"`, `"fall"`. |
| `stat_access_level` | string | No | Who can view stats. Observed: `"confirmed_individual"`, `"confirmed_full"`, `"fans"`. |
| `scorekeeping_access_level` | string | No | Who can keep score. All 15 observed: `"staff_only"`. |
| `streaming_access_level` | string | No | Who can access video streams. Observed: `"confirmed_members"`, `"staff_only"`. |
| `paid_access_level` | string or null | Yes | Observed: `"premium"` or `null`. Null for most teams. |
| `settings` | object | No | Scorekeeping and integration settings. Always present; contains `scorekeeping.bats` and `maxpreps`. |
| `settings.scorekeeping.bats.innings_per_game` | int | No | Default innings per game. Observed: 6 or 7. |
| `settings.scorekeeping.bats.shortfielder_type` | string | No | All observed: `"none"`. |
| `settings.scorekeeping.bats.pitch_count_alert_1` | int or null | Yes | Pitch count warning threshold 1. Usually null; non-null (25) on one team. |
| `settings.scorekeeping.bats.pitch_count_alert_2` | int or null | Yes | Pitch count warning threshold 2. Usually null; non-null (30) on one team. |
| `settings.maxpreps` | null | Yes | MaxPreps integration config. Always null in this dataset. |
| `organizations` | array | No | Organizations this team belongs to. Empty array `[]` for most teams; some have one entry with `organization_id` (UUID) and `status: "active"`. |
| `ngb` | **JSON-encoded string** | No | National Governing Body affiliation. **IMPORTANT: This is a string containing JSON, not a native JSON array.** Must be parsed twice. Observed values: `"[]"` (no NGB), `"[\"usssa\"]"`, `"[\"american_legion\"]"`. |
| `user_team_associations` | array of strings | No | The authenticated user's roles for this team (populated when `include=user_team_associations` is in the query). Observed role values: `"manager"`, `"player"`, `"family"`, `"fan"`. A user may have multiple roles (e.g., `["family", "manager"]`). |
| `team_avatar_image` | null | Yes | Team avatar image URL. All 15 observed: `null`. |
| `team_player_count` | null | Yes | Player count. All 15 observed: `null`. Purpose unclear -- may be populated for some access levels. |
| `created_at` | ISO 8601 string | No | Team creation timestamp (e.g., `"2024-11-02T12:34:20.229Z"`). |
| `public_id` | string | No | Short public identifier for sharing (e.g., `"a1GFM9Ku0BbF"`). Not a UUID. Used in public URLs. |
| `url_encoded_name` | string | No | URL-safe team name slug (e.g., `"2025-summer-lincoln-rebels-14u"`). Encodes year, season, and team name. |
| `archived` | boolean | No | Whether the team is archived. 8 of 15 teams archived. Archived teams are historical; their data remains accessible via other endpoints. |
| `record` | object | No | Team win-loss record. Always present. Contains `wins` (int), `losses` (int), `ties` (int). |
| `badge_count` | int | No | All 15 observed: `0`. Purpose unclear. |

#### user_team_associations Values

| Value | Description |
|-------|-------------|
| `"manager"` | User is a manager or coach of this team. Has administrative access. |
| `"player"` | User is registered as a player on this team. |
| `"family"` | User is a family member (parent/guardian) of a player on this team. |
| `"fan"` | User follows this team without a direct player connection. |

#### Key Facts for Discovery Flow

This endpoint is the recommended first call for bootstrapping. From the response you can:
- Extract all team UUIDs (`id` field) for use with `/teams/{team_id}/game-summaries`, `/teams/{team_id}/season-stats`, etc.
- Filter to current season by `season_year` and `archived: false`
- Filter to teams where the user has `"manager"` in `user_team_associations` to find teams with coaching access
- The `record` field gives quick win-loss totals per team without additional API calls

**ngb parsing note:** The `ngb` field requires double-JSON-parsing:
```python
import json
ngb_list = json.loads(team["ngb"])  # first parse: string -> list
# ngb_list is now ["usssa"] or [] or ["american_legion"]
```

---

### Schema: game-summaries

Returned by `GET /teams/{team_id}/game-summaries`. The response is a **bare JSON array** -- no wrapper object. Each element represents one completed game.

**Schema confirmed from two-page complete capture on 2026-03-04.** Page 1: 50 records (no `start_at` cursor). Page 2: 42 records (`start_at=136418700`; no `x-next-page` in response -- last page confirmed). Total: 92 game records for a full season. Coverage: April–June 2025 season, both home and away games, all game_status values observed: `"completed"` only.

```json
[
  {
    "event_id": "<uuid>",
    "game_stream": {
      "id": "<uuid>",
      "game_id": "<uuid>",
      "game_status": "completed",
      "home_away": "away",
      "is_archived": false,
      "opponent_id": "<uuid>",
      "scoring_user_id": "<uuid>",
      "sabertooth_major_version": 4

      // game_clock_* fields below are OPTIONAL — present on ~46% of records in this capture.
      // When present, all five appear together. Values were all zero/false/paused in this sample.
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

#### game_stream object (with optional clock fields)

```json
{
  "id": "<uuid>",
  "game_id": "<uuid>",
  "game_status": "completed",
  "home_away": "away",
  "is_archived": false,
  "opponent_id": "<uuid>",
  "sabertooth_major_version": 4,
  "scoring_user_id": "<uuid>",

  // Optional clock fields -- present on ~46% of records
  "game_clock_elapsed_seconds_at_last_pause": "0",
  "game_clock_enabled": false,
  "game_clock_mode": "up",
  "game_clock_start_time_milliseconds": "0",
  "game_clock_state": "paused"
}
```

#### Field Notes

| Field                          | Type     | Notes                                                                           |
|--------------------------------|----------|---------------------------------------------------------------------------------|
| `event_id`                     | UUID     | Ties back to a schedule event. **Confirmed equal to `game_stream.game_id` on all 50 records.** |
| `game_stream.id`               | UUID     | Game stream identifier. **Always differs from `game_stream.game_id`** -- it is a separate UUID. |
| `game_stream.game_id`          | UUID     | Game identifier. Confirmed equal to top-level `event_id` on all 50 records.    |
| `game_stream.game_status`      | string   | Observed: `"completed"` only. In-progress game statuses are unknown.           |
| `game_stream.home_away`        | string   | `"home"` or `"away"` -- from owning team's perspective                         |
| `game_stream.is_archived`      | boolean  | All observed values: `false`. Archival behavior unknown.                        |
| `game_stream.opponent_id`      | UUID     | Opponent's team UUID -- can be used directly with `/teams/{opponent_id}/players` |
| `game_stream.scoring_user_id`  | UUID     | GameChanger user who scored the game. Only 3 unique scorers across 50 games.   |
| `game_stream.sabertooth_major_version` | int | Internal game engine version. All observed: `4`.                        |
| `last_scoring_update`          | ISO 8601 | Timestamp of last score update                                                  |
| `opponent_team_score`          | int      | Opponent's final score. Range observed across 92 games: 0–13.                 |
| `owning_team_score`            | int      | Requesting team's final score. Range observed across 92 games: 0–19.          |
| `home_away`                    | string   | Duplicate of `game_stream.home_away` at the top level                          |
| `game_status`                  | string   | Duplicate of `game_stream.game_status` at the top level. Confirmed `"completed"` on all 92 records. |
| `sport_specific.bats.total_outs` | int    | Total outs recorded in the game. Range observed across 92 games: 15–53. Semantics unclear -- may be combined outs from both teams, or outs from the last inning's perspective. Needs further investigation. |
| `sport_specific.bats.inning_details.inning` | int | Last inning played. Range observed across 92 games: 3–9. |
| `sport_specific.bats.inning_details.half`   | string | `"top"` or `"bottom"` -- last half-inning played. |
| `game_clock_elapsed_seconds_at_last_pause` | **string** | Clock field -- **type is string, not int**. Observed value: `"0"`. Optional. |
| `game_clock_enabled`           | boolean  | Clock field. Observed value: `false`. Optional.                                 |
| `game_clock_mode`              | string   | Clock field. Observed value: `"up"`. Optional.                                 |
| `game_clock_start_time_milliseconds` | **string** | Clock field -- **type is string, not int**. Observed value: `"0"`. Optional. |
| `game_clock_state`             | string   | Clock field. Observed value: `"paused"`. Optional.                              |

#### Key ID Relationships (confirmed across all 92 records -- both pages)

- `event_id` == `game_stream.game_id` (always identical -- confirmed on all 92 records)
- `game_stream.id` != `game_stream.game_id` (always different -- two separate identifiers for the game, confirmed on all 92 records)
- `game_stream.opponent_id` is a full team UUID usable with `/teams/{opponent_id}/players`
- `scoring_user_id` was non-null on all 42 page 2 records (combined: non-null on all 92 records)

#### Per-Player Stats

**This endpoint does NOT contain per-player stats.** Confirmed across all 50 records (2026-03-04). The response carries only game-level scores, outcomes, and metadata. For player-level statistics, use `/teams/{team_id}/season-stats`.

#### Clock Fields Behavior (confirmed across both pages, 2026-03-04)

- Clock fields (`game_clock_*`) appeared on 23/50 records (46%) on page 1 and 16/42 records (38%) on page 2 -- combined 39/92 records (42%) across the full season
- When present, all five clock fields appear together (they are always colocated)
- When absent, the fields do not appear at all in the record (they are not present with null values)
- `game_clock_enabled` is `false` when clock fields are present; `null` when clock fields are absent
- All observed clock values: `"0"` for elapsed/start strings, `false` for enabled, `"up"` for mode, `"paused"` for state -- clock feature was not actively used on any of these 92 games
- The two numeric-looking fields (`game_clock_elapsed_seconds_at_last_pause`, `game_clock_start_time_milliseconds`) are **strings** ("0"), not integers -- parse accordingly
- Hypothesis: clock fields are present when the game was created with clock support enabled (likely for timed sports like soccer adapted to baseball) but unused in practice for this HS baseball program

---

### Schema: season-stats

Returned by `GET /teams/{team_id}/season-stats`. The response is a single JSON object (not an array).

For authoritative stat abbreviation definitions sourced from the GameChanger UI, see [`docs/gamechanger-stat-glossary.md`](gamechanger-stat-glossary.md).

```json
{
  "id": "<team_uuid>",
  "team_id": "<team_uuid>",
  "stats_data": {
    "players": {
      "<player_uuid>": {
        "stats": {
          "offense": { ... },
          "defense": { ... },
          "general": { "GP": 84 }
        }
      }
    },
    "streaks": {
      "<player_uuid>": {
        "streak_H": {
          "offense": { ... },
          "defense": { ... },
          "general": { "GP": 2 }
        }
      }
    },
    "stats": {
      "offense": { ... },
      "defense": { ... },
      "general": { "GP": 92 }
    }
  }
}
```

#### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID (same as `team_id`) |
| `team_id` | UUID | Team UUID |
| `stats_data.players` | object | Per-player stats keyed by player UUID |
| `stats_data.streaks` | object | Hot/cold streak data keyed by player UUID. Only players currently on a streak are included. |
| `stats_data.stats` | object | Team aggregate stats (same structure as a player's stats) |

#### Offense (Batting) Fields

These fields appear in `stats.offense` for both individual players and the team aggregate.

| Field | Type | Description |
|-------|------|-------------|
| `AB` | int | At bats |
| `PA` | int | Plate appearances |
| `H` | int | Hits |
| `1B` | int | Singles |
| `2B` | int | Doubles |
| `3B` | int | Triples |
| `HR` | int | Home runs |
| `TB` | int | Total bases |
| `XBH` | int | Extra base hits |
| `BB` | int | Walks |
| `SO` | int | Strikeouts |
| `SOL` | int | Strikeouts looking |
| `HBP` | int | Hit by pitch |
| `SHB` | int | Sacrifice bunts |
| `SHF` | int | Sacrifice flies |
| `GIDP` | int | Grounded into double play |
| `ROE` | int | Reached on error |
| `FC` | int | Fielder's choice |
| `CI` | int | Catcher's interference |
| `PIK` | int | Picked off |
| `R` | int | Runs scored |
| `RBI` | int | Runs batted in |
| `GSHR` | int | Grand slam home runs |
| `2OUTRBI` | int | RBI with 2 outs |
| `SB` | int | Stolen bases |
| `CS` | int | Caught stealing |
| `LOB` | int | Left on base |
| `3OUTLOB` | int | Left on base with 3 outs |
| `OB` | int | Times on base |
| `AVG` | float | Batting average |
| `OBP` | float | On-base percentage |
| `SLG` | float | Slugging percentage |
| `OPS` | float | On-base plus slugging |
| `BABIP` | float | Batting average on balls in play |
| `BA/RISP` | float | Batting average with runners in scoring position |
| `HRISP` | int | Hits with RISP |
| `ABRISP` | int | At bats with RISP |
| `SB%` | float | Stolen base success rate |
| `AB/HR` | float | At bats per home run. **Present only when HR > 0** |
| `QAB` | int | Quality at bats |
| `QAB%` | float | Quality at bat percentage |
| `BB/K` | float | Walk to strikeout ratio |
| `PS` | int | Pitches seen |
| `PS/PA` | float | Pitches per plate appearance |
| `PA/BB` | float | Plate appearances per walk |
| `SW` | int | Swings |
| `SW%` | float | Swing percentage |
| `SM` | int | Swinging misses |
| `SM%` | float | Swinging miss percentage |
| `C%` | float | Contact percentage |
| `BABIP` | float | BABIP |
| `GB` | int | Ground balls |
| `GB%` | float | Ground ball percentage |
| `FLB` | int | Fly balls |
| `FLB%` | float | Fly ball percentage |
| `HARD` | int | Hard contact count |
| `WEAK` | int | Weak contact count |
| `FULL` | int | Full count plate appearances |
| `2STRIKES` | int | Plate appearances reaching a 2-strike count |
| `2S+3` | int | Plate appearances where a 2-strike count went 3+ pitches |
| `2S+3%` | float | Percentage form of 2S+3 |
| `6+` | int | Plate appearances lasting 6+ pitches |
| `6+%` | float | Percentage of PAs going 6+ pitches |
| `INP` | int | In play count (balls put in play) |
| `LND` | int | Line drives |
| `LND%` | float | Line drive percentage |
| `LOBB` | int | Leadoff base on balls (batting context -- times batter drew a leadoff walk) |
| `GP` | int | Games played |
| `TS` | int | Total swings |

#### Defense (Pitching) Fields

These fields in `stats.defense` reflect pitching performance. All apply to the player's innings as a pitcher.

| Field | Type | Description |
|-------|------|-------------|
| `ERA` | float | Earned run average |
| `IP` | float | Innings pitched |
| `ER` | int | Earned runs |
| `H` | int | Hits allowed |
| `BB` | int | Walks allowed |
| `SO` | int | Strikeouts |
| `HR` | int | Home runs allowed |
| `BK` | int | Balks |
| `WP` | int | Wild pitches |
| `HBP` | int | Hit batters |
| `GS` | int | Games started (pitching) |
| `SVO` | int | Save opportunities |
| `WHIP` | float | Walks plus hits per inning pitched |
| `FIP` | float | Fielding independent pitching |
| `BAA` | float | Batting average against |
| `K/G` | float | Strikeouts per 9 innings |
| `K/BB` | float | Strikeout to walk ratio |
| `K/BF` | float | Strikeouts per batter faced |
| `BB/INN` | float | Walks per inning |
| `BF` | int | Batters faced |
| `GO` | int | Ground outs recorded (pitching) |
| `AO` | int | Air outs recorded (pitching) |
| `GO/AO` | float | Ground out to air out ratio |
| `P/BF` | float | Pitches per batter faced |
| `P/IP` | float | Pitches per inning pitched |
| `#P` | int | Total pitches thrown |
| `S%` | float | Strike percentage |
| `LOO` | int | Opponent runners left on base (pitcher's LOB) |
| `LOO%` | float | LOO percentage |
| `LOB%` | float | Opponent LOB percentage |
| `LOB` | int | Opponent left on base |
| `0BBINN` | int | Innings without a walk |
| `123INN` | int | 1-2-3 innings retired |
| `123INN%` | float | Percentage of innings that were 1-2-3 |
| `FPS` | int | First pitch strikes thrown |
| `FPS%` | float | First pitch strike percentage |
| `FPSO` | int | Batters retired after first pitch strike |
| `FPSO%` | float | Percentage of FPS leading to out |
| `FPSH` | int | Batters reaching hit after first pitch strike |
| `FPSH%` | float | Percentage of FPS leading to hit |
| `FPSW` | int | Walks issued after first pitch strike |
| `FPSW%` | float | Percentage of FPS leading to walk |
| `LBFPN` | int | Last batter faced pitch number (cumulative pitch count at last batter) |
| `SB` | int | Stolen bases allowed (pitcher) |
| `CS` | int | Caught stealing charged to pitcher |
| `SB%` | float | Opponent stolen base success rate (pitcher) |
| `PIK` | int | Pickoffs |
| `BBS` | int | Walks that score (base on balls that result in a run scoring) |
| `LOBBS` | int | Leadoff walk that scored (1st batter of inning walked and later scored) |
| `SW` | int | Swings against (pitching) |
| `SM` | int | Swinging misses induced |
| `SM%` | float | Swinging miss percentage (pitching) |
| `GB` | int | Ground balls allowed |
| `FLB` | int | Fly balls allowed |
| `FLY` | int | Air balls (fly balls + line drives?) |
| `GB%` | float | Ground ball percentage allowed |
| `FLB%` | float | Fly ball percentage allowed |
| `FLY%` | float | Fly ball percentage |
| `HARD` | int | Hard contact hits allowed |
| `HARD%` | float | Hard contact hit percentage |
| `WEAK` | int | Weak contact hits allowed |
| `WEAK%` | float | Weak contact percentage |
| `BABIP` | float | BABIP against (pitching) |
| `BA/RISP` | float | Batting average against with RISP |
| `HRISP` | int | Hits allowed with RISP |
| `ABRISP` | int | At bats against with RISP |
| `2STRIKES` | int | Batters reaching a 2-strike count (pitching) |
| `FULL` | int | Full count at bats against |
| `1ST2OUT` | int | Innings with first 2 batters out |
| `1ST2OUT%` | float | Percentage of innings with first 2 batters out |
| `LND` | int | Line drives allowed |
| `LND%` | float | Line drive percentage allowed |
| `LOBB` | int | Leadoff walk allowed (1st batter of inning walked) |
| `<3` | int | Batters retired in fewer than 3 pitches |
| `<3%` | float | Percentage of batters retired in under 3 pitches |
| `<13` | int | Innings of 13 pitches or fewer |
| `<13%` | float | Percentage of innings with 13 pitches or fewer |
| `DP:P` | int | Double plays turned as pitcher |
| `TB` | int | Total bases allowed |
| `R` | int | Runs allowed |
| `AB` | int | At bats against |
| `2B` | int | Doubles allowed |
| `3B` | int | Triples allowed |
| `1B` | int | Singles allowed |
| `FC` | int | Fielder's choices against |
| `SHB` | int | Sacrifice bunts against |
| `SHF` | int | Sacrifice flies against |
| `CI` | int | Catcher's interference against |
| `SOL` | int | Strikeouts looking (from pitcher's view) |
| `GP:P` | int | Games played as pitcher |

#### Defense (Fielding) Fields

Fielding stats co-reside in `stats.defense` alongside pitching stats.

| Field | Type | Description |
|-------|------|-------------|
| `PO` | int | Putouts |
| `A` | int | Assists |
| `E` | int | Errors |
| `TC` | int | Total chances |
| `FPCT` | float | Fielding percentage |
| `DP` | int | Double plays |
| `IF` | int | Infield fly outs |
| `GP:F` | int | Games played in the field (non-pitcher) |
| `GP:C` | int | Games played as catcher |
| `outs` | int | Total outs recorded across all positions |
| `outs:F` | int | Outs recorded while playing field positions |
| `outs:C` | int | Outs recorded while catching |
| `outs-P` | int | Outs recorded while pitching |
| `outs-1B` | int | Outs recorded while playing 1B |
| `outs-2B` | int | Outs recorded while playing 2B |
| `outs-3B` | int | Outs recorded while playing 3B |
| `outs-SS` | int | Outs recorded while playing SS |
| `outs-LF` | int | Outs recorded while playing LF |
| `outs-CF` | int | Outs recorded while playing CF |
| `outs-RF` | int | Outs recorded while playing RF |
| `outs-C` | int | Outs recorded while catching |
| `IP:1B` | float | Innings played at 1B (fractional thirds) |
| `IP:2B` | float | Innings played at 2B |
| `IP:3B` | float | Innings played at 3B |
| `IP:SS` | float | Innings played at SS |
| `IP:LF` | float | Innings played at LF |
| `IP:CF` | float | Innings played at CF |
| `IP:RF` | float | Innings played at RF |
| `IP:F` | float | Total innings played in field positions |
| `IC:C` | float | Innings caught (catcher) |
| `CI` | int | Catcher's interference |
| `CI:C` | int | Catcher's interference committed as catcher |
| `PB:C` | int | Passed balls (catcher) |
| `SB:C` | int | Stolen bases allowed (catcher) |
| `CS:C` | int | Caught stealing (catcher) |
| `SB:C%` | float | Opponent stolen base percentage (catcher) |
| `CS:C%` | float | Caught stealing percentage (catcher) |
| `PIK:C` | int | Pickoffs (catcher) |
| `SBATT:C` | int | Stolen base attempts against catcher |

**Note on `IP:POS` values:** These represent innings played at a position as fractional thirds. A value of `218.67` = 218 full innings + 2 outs. Divide by 3 to get full inning equivalents, or use `floor(val) + (val % 1) / 0.333` for precise conversion.

#### Streaks Object

The `streaks` key holds current hot/cold streak data. Only players actively on a streak appear here. The key format is `streak_H` (hot streak). A cold streak key `streak_C` is inferred but not yet observed.

```json
"streaks": {
  "<player_uuid>": {
    "streak_H": {
      "offense": { /* same fields as player offense */ },
      "defense": { /* same fields as player defense */ },
      "general": { "GP": 2 }   // number of games in the streak
    }
  }
}
```

---

### Schema: associations

Returned by `GET /teams/{team_id}/associations`. The response is a **bare JSON array** -- no wrapper object. Each element represents one user-team membership record.

**Schema confirmed from 244-record live capture on 2026-03-04.** All records share the same `team_id` (the requested team). Distribution observed: 156 fans, 83 family members, 3 managers, 2 players.

```json
[
  {
    "team_id": "<uuid>",
    "user_id": "<uuid>",
    "association": "manager"
  },
  {
    "team_id": "<uuid>",
    "user_id": "<uuid>",
    "association": "family"
  }
]
```

#### Field Notes

| Field         | Type   | Description                                                                 |
|---------------|--------|-----------------------------------------------------------------------------|
| `team_id`     | UUID   | Team UUID. Always matches the `{team_id}` path parameter.                  |
| `user_id`     | UUID   | GameChanger user UUID. Not necessarily the same as the player UUID returned by `/teams/{team_id}/players`. |
| `association` | string | Role of this user relative to the team. Values confirmed: `"manager"`, `"player"`, `"family"`, `"fan"`. |

#### association Values

| Value       | Description                                                            |
|-------------|------------------------------------------------------------------------|
| `"manager"` | Team manager or coach. Has administrative access to the team.          |
| `"player"`  | Registered as a player on the team via GameChanger app. Low count -- does not represent the full active roster. |
| `"family"`  | Family member of a player. Parent or guardian linked to a player.      |
| `"fan"`     | Fan or follower. Anyone who follows the team without a player/family link. |

---

### Schema: player-stats

Returned by `GET /teams/{team_id}/players/{player_id}/stats`. The response is a **bare JSON array** -- no wrapper object. Each element represents one game the player appeared in.

**Schema confirmed from 80-record live capture on 2026-03-04.** Player UUID `77c74470-5d1c-4723-a7e3-348c0ed84e5f` on team `72bb77d8-54ca-42d2-8547-9da4880d0cb4`. Coverage: 2025-04-01 through 2025-07-15 (80 of 92 games in the full team season). Response size: 387 KB.

```json
[
  {
    "event_id": "<uuid>",
    "stream_id": "<uuid>",
    "game_date": "2025-04-03T23:00:00.000Z",
    "player_stats": {
      "stats": {
        "offense": { ... },
        "general": { "GP": 1 },
        "defense": { ... }
      }
    },
    "cumulative_stats": {
      "stats": {
        "offense": { ... },
        "defense": { ... },
        "general": { "GP": 2 }
      }
    },
    "offensive_spray_charts": [
      {
        "id": "<uuid>",
        "code": "ball_in_play",
        "createdAt": "<unix-ms>",
        "attributes": {
          "playType": "ground_ball",
          "playResult": "batter_out_advance_runners",
          "defenders": [
            {
              "position": "3B",
              "location": { "x": 99, "y": 191 },
              "error": false
            }
          ]
        },
        "compactorAttributes": { "stream": "main" }
      }
    ],
    "defensive_spray_charts": null
  }
]
```

#### Top-Level Record Fields

| Field                    | Type             | Nullable | Description |
|--------------------------|------------------|----------|-------------|
| `event_id`               | UUID string      | No       | Game event UUID. Same as `game_stream.game_id` in game-summaries. Use to join with `/teams/{team_id}/game-summaries`. |
| `stream_id`              | UUID string      | No       | Game stream UUID. Same as `game_stream.id` (not `game_id`) in game-summaries. |
| `game_date`              | ISO 8601 string  | No       | Game date/time (UTC). Example: `"2025-04-03T23:00:00.000Z"`. Records are NOT sorted chronologically. |
| `player_stats`           | object           | No       | Per-game statistics for this player in this specific game. |
| `player_stats.stats`     | object           | No       | Container. Keys: `offense` (conditional), `defense` (conditional), `general` (always present). |
| `cumulative_stats`       | object           | No       | Rolling season totals through and including this game. Same structure as `player_stats`. |
| `offensive_spray_charts` | array or null    | Yes      | Ball-in-play location data for batting. Null for 24/80 games (games with no tracked balls in play for this batter). When present, array of 1-3 items. |
| `defensive_spray_charts` | array or null    | Yes      | Ball-in-play location data for fielding. Null for 67/80 games (games where this player did not field a tracked ball in play). |

#### player_stats.stats Sections (Conditional)

The `offense`, `defense`, and `general` sub-keys are conditionally present:

| Key       | Present when                                        | Absent when                                  |
|-----------|-----------------------------------------------------|----------------------------------------------|
| `offense` | Player batted in this game                          | Pitcher-only appearance (2 of 80 records)    |
| `defense` | Player fielded or pitched in this game              | DH-only or rare offensive-only appearance (4 of 80) |
| `general` | Always present                                      | Never absent                                 |

**general fields:**
| Field | Type | Description |
|-------|------|-------------|
| `GP`  | int  | Always `1` in `player_stats` (per-game record). In `cumulative_stats.general`, reflects the running GP total through this game. |

#### Per-Game Offense Fields

Same field set as `/teams/{team_id}/season-stats` offense. All 84 fields (see season-stats schema for full table). Key subset:

| Field     | Type  | Description                             |
|-----------|-------|-----------------------------------------|
| `GP`      | int   | Always `1` (single game)                |
| `PA`      | int   | Plate appearances this game             |
| `AB`      | int   | At bats this game                       |
| `H`       | int   | Hits this game                          |
| `BB`      | int   | Walks this game                         |
| `SO`      | int   | Strikeouts this game                    |
| `R`       | int   | Runs scored this game                   |
| `RBI`     | int   | RBI this game                           |
| `OBP`     | float | On-base percentage (this game only)     |
| `OPS`     | float | OPS (this game only)                    |

**Note:** SB, CS, and PIK are present in `cumulative_stats.offense` but NOT always in `player_stats.offense` -- they may only appear in cumulative totals for this player's travel ball account. Verify presence before parsing.

#### Per-Game Defense Fields

When the player appeared as a **fielder only** (not a pitcher), the defense section contains fielding-only fields (~34 fields). When the player appeared as a **pitcher**, the defense section contains the full pitching + fielding field set (~129 fields). The presence of `GP:P` (int > 0) indicates pitching appearance.

Key pitching fields (only present when `GP:P > 0`):
| Field    | Type  | Description                        |
|----------|-------|------------------------------------|
| `GP:P`   | int   | Games pitched (1 in per-game)      |
| `IP`     | float | Innings pitched this game          |
| `ER`     | int   | Earned runs this game              |
| `SO`     | int   | Strikeouts thrown this game        |
| `BB`     | int   | Walks issued this game             |
| `ERA`    | float | ERA for this game appearance       |
| `WHIP`   | float | WHIP for this game appearance      |
| `FIP`    | float | FIP for this game appearance       |
| `BF`     | int   | Batters faced this game            |
| `#P`     | int   | Total pitches thrown this game     |

**New fields observed in player-stats defense NOT documented in season-stats:**

| Field      | Type  | Notes |
|------------|-------|-------|
| `IP:SF`    | float | Innings played at short field (shortfielder position). All observed values: `0`. May apply to recreational or modified-rules formats. |
| `TP:P`     | int   | Triple plays turned as pitcher. Observed value: `0`. |
| `SB%`      | float | Stolen base success rate (pitcher context). Present in cumulative defense, may appear in per-game. |
| `INP`      | int   | In-play batters (pitching context). Balls put in play against this pitcher. |
| `TS`       | int   | Total swings (pitching context). |
| `OS`, `OSS`, `OSSM`, `OSSW`, `OS%`, `OS#MPH`, `OSMPH` | int/float | Outswing stats (pitch-level tracking). All observed: `0`. Appears reserved for future pitch velocity tracking. |

#### Spray Chart Item Structure

Each spray chart item (in `offensive_spray_charts` or `defensive_spray_charts`) follows this structure:

| Field                          | Type   | Description |
|--------------------------------|--------|-------------|
| `id`                           | UUID   | Unique identifier for this play event |
| `code`                         | string | Event type code. Observed: `"ball_in_play"` only |
| `createdAt`                    | int    | Unix timestamp in **milliseconds** |
| `attributes.playType`          | string | Ball-in-play type. Values: `"ground_ball"`, `"fly_ball"`, `"line_drive"`, `"pop_fly"`, `"bunt"`, `"hard_ground_ball"`, `"other"` |
| `attributes.playResult`        | string | Outcome of the play. Values: `"batter_out"`, `"batter_out_advance_runners"`, `"single"`, `"double"`, `"triple"`, `"home_run"`, `"fielders_choice"`, `"error"`, `"sacrifice_bunt"`, `"sacrifice_fly"`, `"other_out"` |
| `attributes.defenders`         | array  | Fielder(s) involved in the play. Usually 1, occasionally 2 (for double plays). |
| `attributes.defenders[].position`  | string | Position code: `"1B"`, `"2B"`, `"3B"`, `"SS"`, `"LF"`, `"CF"`, `"RF"`, `"P"`, `"C"` |
| `attributes.defenders[].location.x` | int  | X coordinate on the field diagram. Origin/scale unconfirmed. |
| `attributes.defenders[].location.y` | int  | Y coordinate on the field diagram. Origin/scale unconfirmed. |
| `attributes.defenders[].error`     | boolean | Whether this defender committed an error on this play |
| `compactorAttributes.stream`   | string | Always `"main"` in this capture |

**Multiple items per game:** A single game can have 1-3 spray chart items (confirmed: max 3 in this capture). Multiple items represent multiple balls in play for that player in that game.

**Spray chart counts:** Offensive charts present in 56/80 games (70%), defensive in 13/80 games (16%). Null indicates no tracked ball-in-play events for that player in that role.

#### Cumulative Stats Behavior

`cumulative_stats` represents the player's rolling season totals through the game date of each record. Key observations:

- The `GP` value in `cumulative_stats.general` shows the running game count (e.g., 2 after game 1, 3 after game 2, etc.)
- Records are NOT in chronological order -- sort by `game_date` to reconstruct the trajectory
- Cumulative offense has three additional fields not present in per-game: `SB`, `CS`, `PIK`
- Cumulative defense has three additional fields not present in per-game: `A` (assists), `outs-2B`, `outs-RF` (position-specific outs)
- The final record (by game_date) carries the season totals -- equivalent to season-stats data for this player

#### Relationship to Other Endpoints

| This endpoint field | Related endpoint |
|--------------------|-----------------|
| `event_id`          | `game_stream.game_id` and top-level `event_id` in `/teams/{team_id}/game-summaries` |
| `stream_id`         | `game_stream.id` in `/teams/{team_id}/game-summaries` |
| `player_id` (URL)   | Player UUID from `/teams/{team_id}/players` |
| `team_id` (URL)     | Team UUID from `/me/teams` or `game_stream.opponent_id` in game-summaries |

**Pattern for per-game scouting data:**
```
GET /teams/{team_id}/players           -> get player UUID list
GET /teams/{team_id}/players/{player_id}/stats -> per-game stats for each player
```

---

## Key Observations

### Account Scope: Travel Ball Account vs. LSB Coaching Account

**Confirmed 2026-03-04 from /me/teams capture:** The gc-token currently in use is associated with Jason's personal travel ball account. The 15 teams returned are youth travel ball and recreational teams (8U–14U, Nebraska/USSSA affiliation). The LSB high school teams expected from the project scope (Freshman, JV, Varsity, Reserve) did **not** appear.

**Action required:** To ingest LSB high school program data, a gc-token from a GameChanger account with coaching access to the LSB teams is needed. This may be a different login or account. Until then, the current credentials give access only to the travel ball teams.

The travel ball data (particularly "Lincoln Rebels 14U" and "Rebels 13U") may still be useful for development and testing purposes since the team ID and endpoint behavior are identical regardless of program type.

### Opponents Are First-Class Teams

The `opponent_id` in game-summaries is a full GameChanger team UUID. The `/teams/{team_id}/players` endpoint accepts opponent UUIDs directly, meaning opponent rosters can be fetched without any special access. This is the primary mechanism for gathering opponent scouting data.

### Discovery Flow

The recommended flow for finding team UUIDs without hardcoding:

```
GET /me/teams?include=user_team_associations
  -> extract team UUIDs

GET /teams/{team_id}/season-stats
  -> full season batting/pitching/fielding aggregates per player
  -> players keyed by UUID; no names -- cross-reference with /players

GET /teams/{team_id}/game-summaries
  -> extract opponent_id values per game

GET /teams/{opponent_id}/players
  -> fetch opponent rosters

GET /teams/{team_id}/players
  -> get player UUID list (needed for per-game stats below)

GET /teams/{team_id}/players/{player_id}/stats
  -> per-game stats for one player: batting/pitching/fielding lines per game
  -> rolling cumulative season totals through each game
  -> spray chart data (ball-in-play coordinates, play type, play result)
  -> call once per player UUID for full per-game breakdowns
```

### gc-user-action Values Observed

| Value                   | Seen on endpoint             |
|-------------------------|------------------------------|
| `data_loading:events`      | game-summaries, video-stream/assets |
| `data_loading:event`       | game-summaries (seen in one prior capture -- status uncertain) |
| `data_loading:team`        | schedule                     |
| `data_loading:team_stats`  | season-stats                 |
| `data_loading:player_stats` | `/teams/{team_id}/players/{player_id}/stats` |

**2026-03-04 update:** The 2026-03-04 game-summaries capture used `data_loading:events` (plural) on what was the first page and returned 50 records successfully. The earlier observation of `data_loading:event` (singular) on a first-page request may have been incidental or from a different client code path. Current recommendation: use `data_loading:events` (plural) for game-summaries.

### API Delivery Infrastructure

Confirmed from response headers (2026-03-04): GameChanger's API is served through **AWS CloudFront CDN**. Response headers include:

```
x-cache: Miss from cloudfront
via: 1.1 <cloudfront-node>
x-amz-cf-pop: <CloudFront POP>
x-amz-cf-id: <CloudFront request ID>
```

ETags are returned on game-summaries responses (`etag: "..."`). Conditional requests using `If-None-Match` have not been tested but could support efficient polling. The `x-server-epoch` header carries the server's Unix timestamp (seconds) at response time.

### Optional vs. Required Headers

Based on captures:

- `gc-user-action-id` and `gc-user-action` — absent from `/players` and `/associations` captures, so both appear optional. Include them when mimicking browser behavior for endpoints where they were observed.
- Navigation headers (`sec-fetch-*`, `cache-control`, `pragma`, `origin`, `priority`) — appear in schedule and /me/teams captures, likely browser-added during page navigation contexts vs. background XHR. May not be required by the API, but include them to match the browser fingerprint.

### Token Lifecycle

Tokens expire in approximately 1 hour. The `rtkn` field in the JWT payload suggests a refresh token mechanism exists. Refresh flow has not yet been confirmed from captures — document it when observed.

---

## Header Quick Reference

Minimal confirmed headers for a working authenticated request:

```
gc-token: <JWT>
gc-device-id: <32-char hex>
gc-app-name: web
Accept: <resource-specific value>
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
```

Full browser-mimicking header set (recommended):

```
gc-token: <JWT>
gc-device-id: <32-char hex>
gc-app-name: web
gc-user-action: <action string>
gc-user-action-id: <UUID>
Accept: <resource-specific value>
Content-Type: application/vnd.gc.com.none+json; version=undefined
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
Referer: https://web.gc.com/
DNT: 1
origin: https://web.gc.com
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
cache-control: no-cache
pragma: no-cache
```

---

## Notes for Implementers

### Auth Injection — Override the Session Default

The `src/http/session.py` factory (documented in `docs/http-integration-guide.md`) uses `Authorization: Bearer` in its examples, which is the common pattern. GameChanger uses `gc-token` instead. When creating a session for GameChanger:

```python
session = create_session()

# GameChanger auth -- NOT Authorization: Bearer
session.headers["gc-token"] = gc_token          # from env or secret store
session.headers["gc-device-id"] = gc_device_id  # stable hex string, from env
session.headers["gc-app-name"] = "web"
```

Never hardcode or log these values. Load from environment variables locally; from Cloudflare secrets in production.

### Accept Headers by Endpoint

| Endpoint                             | Accept header value                                                         |
|--------------------------------------|-----------------------------------------------------------------------------|
| `/me/teams`                          | `application/vnd.gc.com.team:list+json; version=0.10.0`                    |
| `/teams/{id}/schedule`               | `application/vnd.gc.com.event:list+json; version=0.2.0`                    |
| `/teams/{id}/game-summaries`         | `application/vnd.gc.com.game_summary:list+json; version=0.1.0`             |
| `/teams/{id}/players`                | `application/vnd.gc.com.player:list+json; version=0.1.0`                   |
| `/teams/{id}/video-stream/assets`    | `application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0` |
| `/teams/{id}/season-stats`           | `application/vnd.gc.com.team_season_stats+json; version=0.2.0`             |
| `/teams/{id}/associations`           | `application/vnd.gc.com.team_associations:list+json; version=0.0.0`        |
| `/teams/{id}/players/{player_id}/stats` | `application/vnd.gc.com.player_stats:list+json; version=0.0.0`         |

### Pagination Loop Pattern

**Confirmed 2026-03-04:** Pagination metadata is carried in the `x-next-page` **response header**, not the response body. The response body is a bare JSON array. When there are no more pages, the `x-next-page` header is absent.

```python
def fetch_all_game_summaries(session, team_id: str) -> list:
    """Fetch all game summaries for a team using cursor-based pagination."""
    import time
    import random

    url = f"https://api.team-manager.gc.com/teams/{team_id}/game-summaries"
    headers = {
        "x-pagination": "true",
        "gc-user-action": "data_loading:events",
        "Accept": "application/vnd.gc.com.game_summary:list+json; version=0.1.0",
        # ... other standard headers from session defaults
    }
    results = []
    next_url = url  # start with no cursor (first page)

    while next_url:
        response = session.get(next_url, headers=headers)
        response.raise_for_status()
        page = response.json()

        if not page:
            break

        results.extend(page)

        # Pagination cursor is in the x-next-page response header
        # When absent, this is the last page
        next_url = response.headers.get("x-next-page")

        if next_url:
            # Jitter between pages -- respect rate limiting
            time.sleep(1 + random.random())

    return results
```

**Page size:** 50 records per page observed on page 1 of game-summaries with `x-pagination: true`. Page 2 returned 42 records (final page). Page size of 50 appears to be the maximum; the last page may have fewer records. This may vary by endpoint.

### Undocumented API — Iterative Discovery

This API is undocumented. Every value in this document was confirmed from live browser traffic. When you encounter a new endpoint or unexpected response field:

1. Capture the full request and response (redact all credentials before storing)
2. Add the endpoint to this document with status "Confirmed from capture"
3. Note any fields whose meaning is uncertain
4. Update the response schema with the full structure including optional fields

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-04 | NEW endpoint: `GET /teams/{team_id}/players/{player_id}/stats` -- per-game player stats with rolling cumulative season totals and spray chart data. 80 records, 387 KB, single-page response. Accept header `application/vnd.gc.com.player_stats:list+json; version=0.0.0`, gc-user-action `data_loading:player_stats`. Spray charts confirmed: ball-in-play x/y coordinates, play type, play result, defender positions. Partially answers E-002-03 (per-game breakdowns now available per-player, not as a team box score). |
| 2026-03-04 | Fully documented `/me/teams` response schema: 27 fields across 15 teams, `ngb` double-JSON-parse quirk, `user_team_associations` roles, access level enums, organizations structure. Confirmed LSB high school teams absent -- a separate coaching account is needed. Added `Schema: me-teams` section. |
| 2026-03-04 | Documented `/teams/{team_id}/associations`: 244-record live capture, bare array, 3 fields per record, low player count warning, no pagination triggered. |
| 2026-03-04 | Documented `/teams/{team_id}/season-stats`: full-season batting/pitching/fielding aggregates, complete field tables, stat glossary cross-reference. |
| 2026-03-04 | Documented `/teams/{team_id}/game-summaries` pagination (page 2 of 2, 92 total records, `x-next-page` absence confirms end-of-pagination). |
| 2026-03-04 | Confirmed `/teams/{team_id}/game-summaries` page 1 live (50 records, full season). Documented CloudFront CDN delivery, optional clock fields (42% of records), `total_outs` semantics uncertain. |
| Pre-2026-03-01 | Initial capture of `/me/teams`, `/teams/{team_id}/schedule`, `/teams/{team_id}/players`, `/teams/{team_id}/video-stream/assets` from browser traffic (schemas not fully documented at that time). |
