# GameChanger API Reference

This document is the single source of truth for GameChanger API knowledge. It is maintained by the `api-scout` agent and updated whenever new endpoints or behaviors are confirmed from live traffic captures.

**Last updated:** 2026-03-01
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
7. [Response Schemas](#response-schemas)
   - [game-summaries](#schema-game-summaries)
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

- Enable pagination by sending the request header: `x-pagination: true`
- Use cursor-based pagination via the `start_at` query parameter
- The cursor value is an integer (not a UUID or offset count)

### Request pattern

```
GET /teams/{team_id}/game-summaries?start_at=136418700
x-pagination: true
```

### Behavior

- First page: omit `start_at` (or use no cursor)
- Subsequent pages: use the cursor value returned by the previous page
- Observed in video-stream assets: 3 pages with cursors `16734063` and `19308506`
- Observed in game-summaries: returned 34 records on confirmed live call

The exact field name in the response that carries the next-page cursor has not yet been confirmed — document it when observed.

---

## Endpoints

### GET /me/teams

**Status:** Confirmed from curl capture.

Discover all teams the authenticated user belongs to. This is the recommended entry point for finding team UUIDs without hardcoding them.

```
GET https://api.team-manager.gc.com/me/teams?include=user_team_associations
```

#### Query Parameters

| Parameter               | Required | Description                                          |
|-------------------------|----------|------------------------------------------------------|
| `include`               | No       | `user_team_associations` — includes role/membership data |

#### Headers

```
gc-token: <JWT>
gc-device-id: <32-char hex>
gc-app-name: web
Accept: application/vnd.gc.com.team:list+json; version=0.10.0
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

A list of team objects. Response schema not yet fully documented — update when captured.

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

**Status:** CONFIRMED LIVE — returned 34 game records.

Returns scored game summaries for a team. Supports pagination.

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
| `start_at` | No       | Pagination cursor (integer). Omit for first page. |

#### Headers

```
gc-token: <JWT>
gc-device-id: <32-char hex>
gc-app-name: web
Accept: application/vnd.gc.com.game_summary:list+json; version=0.1.0
x-pagination: true
gc-user-action: data_loading:events    (first page: "data_loading:event" — singular)
gc-user-action-id: <UUID>
Content-Type: application/vnd.gc.com.none+json; version=undefined
DNT: 1
Referer: https://web.gc.com/
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
User-Agent: <browser UA>
```

**Note on gc-user-action value:** The first-page request used `data_loading:event` (singular). The paginated request used `data_loading:events` (plural). The distinction may be intentional or incidental — document further as observed.

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

## Response Schemas

### Schema: game-summaries

Returned by `GET /teams/{team_id}/game-summaries`. Each element in the array represents one game.

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
      "sabertooth_major_version": 4,

      // The following fields appear only on some records (likely clock-enabled games):
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

#### Field Notes

| Field                          | Type     | Notes                                                                           |
|--------------------------------|----------|---------------------------------------------------------------------------------|
| `event_id`                     | UUID     | Ties back to a schedule event                                                   |
| `game_stream.id`               | UUID     | Game stream identifier                                                          |
| `game_stream.game_id`          | UUID     | Game identifier                                                                 |
| `game_stream.game_status`      | string   | Observed: `"completed"`                                                         |
| `game_stream.home_away`        | string   | `"home"` or `"away"` — from owning team's perspective                          |
| `game_stream.is_archived`      | boolean  |                                                                                 |
| `game_stream.opponent_id`      | UUID     | Opponent's team UUID — can be used directly with `/teams/{opponent_id}/players` |
| `game_stream.scoring_user_id`  | UUID     | GameChanger user who scored the game                                            |
| `game_stream.sabertooth_major_version` | int | Internal game engine version. Observed: `4`                              |
| `last_scoring_update`          | ISO 8601 | Timestamp of last score update                                                  |
| `opponent_team_score`          | int      | Opponent's final score                                                          |
| `owning_team_score`            | int      | Requesting team's final score                                                   |
| `home_away`                    | string   | Duplicate of `game_stream.home_away` at the top level                          |
| `game_status`                  | string   | Duplicate of `game_stream.game_status` at the top level                        |
| `sport_specific.bats.total_outs` | int    | Total outs recorded in the game                                                 |
| `sport_specific.bats.inning_details.inning` | int | Last inning played                                                  |
| `sport_specific.bats.inning_details.half`   | string | `"top"` or `"bottom"` — last half-inning played                    |
| `game_clock_*` fields          | mixed    | Optional — present only when game clock feature is enabled                      |

---

## Key Observations

### Opponents Are First-Class Teams

The `opponent_id` in game-summaries is a full GameChanger team UUID. The `/teams/{team_id}/players` endpoint accepts opponent UUIDs directly, meaning opponent rosters can be fetched without any special access. This is the primary mechanism for gathering opponent scouting data.

### Discovery Flow

The recommended flow for finding team UUIDs without hardcoding:

```
GET /me/teams?include=user_team_associations
  -> extract team UUIDs

GET /teams/{team_id}/game-summaries
  -> extract opponent_id values per game

GET /teams/{opponent_id}/players
  -> fetch opponent rosters
```

### gc-user-action Values Observed

| Value                  | Seen on endpoint             |
|------------------------|------------------------------|
| `data_loading:events`  | game-summaries (paginated), video-stream/assets |
| `data_loading:event`   | game-summaries (first page)  |
| `data_loading:team`    | schedule                     |

The difference between `event` and `events` (singular vs. plural) on the same endpoint across pages may be intentional client behavior or incidental. Monitor for any API-side significance.

### Optional vs. Required Headers

Based on captures:

- `gc-user-action-id` and `gc-user-action` — absent from `/players` capture, so both appear optional. Include them when mimicking browser behavior for endpoints where they were observed.
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

### Pagination Loop Pattern

```python
def fetch_all_pages(session, url: str, headers: dict) -> list:
    results = []
    cursor = None

    while True:
        params = {"start_at": cursor} if cursor else {}
        response = session.get(url, headers=headers, params=params)
        response.raise_for_status()
        page = response.json()

        if not page:
            break

        results.extend(page)

        # TODO: extract cursor from response when next-page field is confirmed
        # cursor = page_metadata.get("next_cursor")
        # if not cursor:
        #     break
        break  # remove this line once cursor extraction is confirmed

    return results
```

The field name carrying the next-page cursor in the response has not yet been confirmed. Update this when the pagination metadata structure is documented from a live capture.

### Undocumented API — Iterative Discovery

This API is undocumented. Every value in this document was confirmed from live browser traffic. When you encounter a new endpoint or unexpected response field:

1. Capture the full request and response (redact all credentials before storing)
2. Add the endpoint to this document with status "Confirmed from capture"
3. Note any fields whose meaning is uncertain
4. Update the response schema with the full structure including optional fields
