# GameChanger API Reference

This document is the single source of truth for GameChanger API knowledge. It is maintained by the `api-scout` agent and updated whenever new endpoints or behaviors are confirmed from live traffic captures.

**Last updated:** 2026-03-07 (BULK RAW-JSON DOCUMENTATION SESSION: Full schema documentation added from raw JSON files captured in data/raw/bulk-20260307-040838/. Key updates: `/me/permissions` upgraded from HTTP 501 to CONFIRMED -- requires `?entityId={uuid}&entityType=team`; `/me/organizations` upgraded from HTTP 500 to CONFIRMED -- requires `?page_size=50` + `x-pagination: true`; `/me/related-organizations` upgraded from HTTP 500 to CONFIRMED -- requires `?page_starts_at=0&page_size=50` + `x-pagination: true`; `/organizations/{org_id}/teams` upgraded from HTTP 500 to CONFIRMED -- requires `?page_starts_at=0&page_size=50` + `x-pagination: true`; `/me/associated-players` `associations` schema completed -- bare array with `relation` + `player_id`; HTTP 500 Endpoints section updated to reflect 3 of 4 endpoints now resolved; Priority Matrix updated. Prior update: LIVE PROBE SESSION: 64 endpoints executed via curl; 50 returned HTTP 200; all org, me, subscription, search, and sync endpoints CONFIRMED)
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
   - [GET /me/user](#get-meuser)
   - [GET /teams/{team_id}](#get-teamsteam_id)
   - [GET /teams/{team_id}/schedule](#get-teamsteam_idschedule)
   - [GET /teams/{team_id}/game-summaries](#get-teamsteam_idgame-summaries)
   - [GET /teams/{team_id}/players](#get-teamsteam_idplayers)
   - [GET /teams/public/{public_id}/players](#get-teamspublicpublic_idplayers)
   - [GET /teams/{team_id}/video-stream/assets](#get-teamsteam_idvideo-streamassets)
   - [GET /teams/{team_id}/season-stats](#get-teamsteam_idseason-stats)
   - [GET /teams/{team_id}/associations](#get-teamsteam_idassociations)
   - [GET /teams/{team_id}/players/{player_id}/stats](#get-teamsteam_idplayersplayer_idstats)
   - [GET /public/teams/{public_id}](#get-publicteamspublic_id) **-- NO AUTH REQUIRED**
   - [GET /public/teams/{public_id}/games](#get-publicteamspublic_idgames) **-- NO AUTH REQUIRED**
   - [GET /public/teams/{public_id}/games/preview](#get-publicteamspublic_idgamespreview) **-- NO AUTH REQUIRED**
   - [GET /teams/{team_id}/opponents](#get-teamsteam_idopponents)
   - [GET /game-stream-processing/{game_stream_id}/boxscore](#get-game-stream-processinggame_stream_idboxscore)
   - [GET /game-stream-processing/{game_stream_id}/plays](#get-game-stream-processinggame_stream_idplays)
   - [GET /public/game-stream-processing/{game_stream_id}/details](#get-publicgame-stream-processinggame_stream_iddetails) **-- NO AUTH REQUIRED**
   - [GET /events/{event_id}/best-game-stream-id](#get-eventsevent_idbest-game-stream-id)
   - [GET /teams/{team_id}/users](#get-teamsteam_idusers)
   - [GET /teams/{team_id}/public-team-profile-id](#get-teamsteam_idpublic-team-profile-id)
   - [POST /auth](#post-auth) **-- FIRST POST ENDPOINT. Token refresh flow.**
   - [GET /teams/{team_id}/schedule/events/{event_id}/player-stats](#get-teamsteam_idscheduleventsevent_idplayer-stats) **-- CONFIRMED. Both teams + spray charts. No game_stream_id needed.**
7. [Response Schemas](#response-schemas)
   - [me-teams](#schema-me-teams)
   - [game-summaries](#schema-game-summaries)
   - [season-stats](#schema-season-stats)
   - [associations](#schema-associations)
   - [player-stats](#schema-player-stats)
8. [Confirmed Endpoints (2026-03-07 Live Probe Session)](#confirmed-endpoints-2026-03-07-live-probe-session)
9. [Proxy-Discovered Endpoints (2026-03-05)](#proxy-discovered-endpoints-2026-03-05)
   - [Sync / Realtime](#sync--realtime)
   - [Announcements](#announcements)
   - [Subscription](#subscription)
   - [Me (additional)](#me-additional)
   - [Organizations](#organizations)
   - [Teams (additional)](#teams-additional)
   - [Events (additional)](#events-additional)
   - [Game Streams](#game-streams)
   - [Clips / Video](#clips--video)
   - [Users](#users)
   - [Places](#places)
   - [Search](#search)
   - [Media CDN Hosts](#media-cdn-hosts)
10. [Proxy-Discovered Endpoints (2026-03-07)](#proxy-discovered-endpoints-2026-03-07)
   - [Teams -- Per-Opponent Scouting](#teams----per-opponent-scouting)
   - [Bats / Starting Lineups](#bats--starting-lineups)
   - [Player Attributes](#player-attributes)
   - [Events (standalone)](#events-standalone)
   - [Organizations (additional)](#organizations-additional)
   - [Teams -- Additional (2026-03-07)](#teams----additional-2026-03-07)
   - [Web-Route Public Endpoints](#web-route-public-endpoints)
   - [Me -- Additional (2026-03-07)](#me----additional-2026-03-07)
   - [Write Operations Catalog](#write-operations-catalog)
10. [Endpoint Priority Matrix](#endpoint-priority-matrix)
11. [Key Observations](#key-observations)
12. [Header Quick Reference](#header-quick-reference)
13. [Notes for Implementers](#notes-for-implementers)

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

The `gc-token` value is a standard JWT (HMAC-SHA256, `alg: HS256`). The decoded payload contains:

| Field   | Description                                                                          |
|---------|--------------------------------------------------------------------------------------|
| `id`    | Compound token ID: `{session_uuid}:{refresh_token_uuid}` -- two UUIDs separated by a colon |
| `cid`   | Client ID UUID -- matches the `gc-client-id` request header exactly                 |
| `uid`   | GameChanger user UUID                                                                |
| `email` | Authenticated user's email address -- PII, never log                                |
| `iat`   | Issued-at timestamp (Unix seconds)                                                   |
| `exp`   | Expiration timestamp (Unix seconds)                                                  |

**Token lifetime:** 14 days (observed: exp - iat = 1,209,600 seconds). Confirmed from decoded JWT payload of the `POST /auth` token (2026-03-04). Earlier observation of ~1 hour was incorrect -- either a different token type or a misread. Auth expiration must be handled gracefully -- see CLAUDE.md "GameChanger API" section.

> **Schema correction (2026-03-04):** Earlier documentation listed `type`, `userId`, and `rtkn` as JWT fields. These were not observed in the decoded payload from the 2026-03-04 capture. The actual fields are `id`, `cid`, `uid`, `email`, `iat`, `exp`. The `rtkn` field may have been speculative or from a different token type. Mark as CORRECTED.

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

### Signature Headers (POST /auth only)

These headers appear exclusively on `POST /auth` (the token refresh call). They are **not** observed on any other endpoint. They appear to implement request signing to authenticate the refresh request independently of the existing token.

| Header           | Value format                          | Notes                                                                                                                |
|------------------|---------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `gc-signature`   | `<base64>=.<base64>=`                 | Request signature. Two base64-encoded segments joined by a period. Likely HMAC over `{body}:{timestamp}` or similar. **Time-bound** -- expires; a stale signature produces HTTP 400. Treat as credential -- never log. |
| `gc-timestamp`   | Unix seconds (integer string)         | Timestamp when the signature was computed. Server validates this is within an acceptable window. Observed: 22,316 seconds stale = HTTP 400. Window upper bound unknown but under 22,316 seconds. The server echoes its own `gc-timestamp` in the response header. |
| `gc-client-id`   | UUID v4                               | Stable client identifier. Matches the `cid` field in the gc-token JWT payload. Treat as credential -- store alongside `gc-device-id`. |
| `gc-app-version` | Semver string                         | App version. Observed value: `"0.0.0"` (likely constant for the web app). Safe to hardcode as `"0.0.0"`.             |

### Confirmed User-Agent String

```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

This is Chrome 145 on macOS. Update `src/http/headers.py` when Chrome falls more than 2 major versions behind — see `docs/http-integration-guide.md`.

### Header Profiles

The codebase supports two header profiles, selectable via `create_session(profile=...)` in `src/http/session.py`. The canonical header values are defined in `src/http/headers.py`.

| Aspect | Web Browser (`"web"`) | Mobile Odyssey (`"mobile"`) |
|--------|----------------------|----------------------------|
| **User-Agent** | `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36` | `Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0` |
| **Accept** | `application/json, text/plain, */*` | `*/*` (callers override per endpoint) |
| **Accept-Language** | `en-US,en;q=0.9` | `en-US;q=1.0` |
| **Accept-Encoding** | `gzip, deflate` | `br;q=1.0, gzip;q=0.9, deflate;q=0.8` |
| **sec-ch-ua headers** | Present (`sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform`) | Absent (browser-only) |
| **sec-fetch headers** | Present (`sec-fetch-site`, `sec-fetch-mode`, `sec-fetch-dest`) | Absent (browser-only) |
| **DNT** | `1` | Absent |
| **Referer** | `https://web.gc.com/` | Absent |
| **gc-app-version** | Not included (web uses `0.0.0` only on POST /auth) | `2026.7.0.0` |
| **x-gc-features** | Absent | `lazy-sync` |
| **x-gc-application-state** | Absent | `foreground` |
| **Auth headers** | `gc-token`, `gc-device-id` (injected by caller) | `gc-token`, `gc-device-id` (injected by caller) |

Both profiles share the same authentication mechanism (`gc-token` + `gc-device-id`). The profiles differ in browser fingerprint, app identification, and optional feature headers. The default profile is `"web"` -- all existing callers are unaffected.

**Source data**: Web profile from browser curl captures (2026-02-28 through 2026-03-05). Mobile profile from mitmproxy iOS capture (2026-03-05), documented in `proxy/data/header-report.json`.

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

### GET /me/user

**Status:** CONFIRMED LIVE -- 200 OK. Schema fully documented 2026-03-04.

Returns the authenticated user's profile: identity fields (id, email, first/last name), account status, subscription tier and source, and detailed subscription information. This is the canonical way to retrieve the authenticated user's UUID and confirm that a `gc-token` is valid and active.

```
GET https://api.team-manager.gc.com/me/user
```

#### Query Parameters

None observed.

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.user+json; version=0.3.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
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
```

**Note on gc-user-action:** No `gc-user-action` or `gc-user-action-id` headers observed in this capture. Consistent with other self-referential endpoints (`/me/teams`) -- these tracking headers appear optional for profile reads.

**Note on x-pagination:** Not sent; this endpoint returns a single object, not a collection.

#### Response

A **single JSON object** (not an array). Size observed: approximately 500 bytes.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | The authenticated user's GameChanger user UUID. Stable identifier across sessions. |
| `is_bats_account_linked` | boolean | Whether the user's BATS (baseball stats) account is linked. |
| `is_bats_team_imported` | boolean | Whether BATS team data has been imported. |
| `email` | string | The user's email address. **PII -- redact in all stored files.** |
| `first_name` | string | User's first name. **PII -- redact in all stored files.** |
| `last_name` | string | User's last name. **PII -- redact in all stored files.** |
| `registration_date` | string (ISO 8601) | When the user's account was created. |
| `status` | string | Account status. Observed: `"active"`. |
| `has_subscription` | boolean | Whether the user currently has an active subscription. |
| `access_level` | string | Top-level access tier. Observed: `"premium"`. |
| `subscription_source` | string | Source of the current subscription. Observed: `"team_manager"`. |
| `subscription_information` | object | Detailed subscription breakdown (see below). |

**`subscription_information` object:**

| Field | Type | Description |
|-------|------|-------------|
| `best_subscription` | object | The highest-tier active subscription. |
| `best_subscription.type` | string | Subscription product type. Observed: `"team_manager"`. |
| `best_subscription.provider_type` | string | Billing provider. Observed: `"recurly"`. |
| `best_subscription.is_gc_classic` | boolean | Whether this is a legacy GC Classic subscription. |
| `best_subscription.is_trial` | boolean | Whether the subscription is a trial. |
| `best_subscription.end_date` | string (ISO 8601) | Subscription expiration date. |
| `best_subscription.access_level` | string | Access level granted by this subscription. Observed: `"premium"`. |
| `best_subscription.billing_cycle` | string | Billing frequency. Observed: `"year"`. |
| `best_subscription.amount_in_cents` | integer | Subscription cost in US cents. Observed: `9999` ($99.99/year). |
| `best_subscription.provider_details` | object | Provider-specific renewal/termination flags. |
| `best_subscription.provider_details.will_renew` | boolean | Whether the subscription auto-renews. |
| `best_subscription.provider_details.was_terminated_by_provider` | boolean | Whether the provider terminated early. |
| `best_subscription.provider_details.was_terminated_by_staff` | boolean | Whether GC staff terminated early. |
| `highest_access_level` | string | Highest access level across all subscriptions. Observed: `"premium"`. |
| `is_free_trial_eligible` | boolean | Whether the user is eligible for a free trial. |

#### Example Response (PII redacted)

```json
{
  "id": "REDACTED_USER_UUID",
  "is_bats_account_linked": true,
  "is_bats_team_imported": true,
  "email": "{REDACTED_EMAIL}",
  "first_name": "REDACTED",
  "last_name": "REDACTED",
  "registration_date": "2018-10-24T16:36:07.659Z",
  "status": "active",
  "has_subscription": true,
  "access_level": "premium",
  "subscription_source": "team_manager",
  "subscription_information": {
    "best_subscription": {
      "type": "team_manager",
      "provider_type": "recurly",
      "is_gc_classic": false,
      "is_trial": false,
      "end_date": "2026-10-07T20:14:38.000Z",
      "access_level": "premium",
      "billing_cycle": "year",
      "amount_in_cents": 9999,
      "provider_details": {
        "will_renew": true,
        "was_terminated_by_provider": false,
        "was_terminated_by_staff": false
      }
    },
    "highest_access_level": "premium",
    "is_free_trial_eligible": false
  }
}
```

**Schema drift check (2026-03-06):** Verified against `data/raw/bulk-20260305-234522/me-user.json`. No schema differences detected -- all fields match the documented schema exactly. Field count, types, and nesting are consistent.

#### Known Limitations

- **PII-dense endpoint**: `email`, `first_name`, and `last_name` are present in the response. These must be redacted in any stored sample files. Never log or commit the real values.
- **User UUID in JWT payload**: The `userId` field in the decoded `gc-token` JWT payload is the same UUID as the `id` field returned here. You can obtain the user UUID without making this API call by decoding the JWT (no signature verification needed for the `userId` field alone). However, this endpoint serves as an authoritative, server-side confirmation of token validity.
- **Token validation use case**: A 200 response from this endpoint is a reliable signal that `gc-token` is still valid. A 401 confirms expiration. Consider using this endpoint as a lightweight auth check before longer ingestion workflows.
- **Subscription fields may vary**: `best_subscription` and `is_free_trial_eligible` may differ for accounts without a team_manager subscription. Not yet observed for free-tier accounts.

**Discovered:** 2026-03-04

---

### GET /teams/{team_id}

**Status:** CONFIRMED LIVE -- 200 OK, single team object returned. Schema fully documented 2026-03-04. **Opponent team validation confirmed 2026-03-04**: `pregame_data.opponent_id` UUIDs from `/schedule` work as `team_id` here.

Returns full metadata for a single team by UUID. The response is a single JSON object (not an array) containing team identity, access levels, settings, organizational affiliations, season metadata, and win/loss record. This is the detail endpoint for a team already known by UUID (e.g., from `/me/teams` or from `pregame_data.opponent_id` in schedule).

**Confirmed for both own teams and opponent teams.** When fetching an opponent team, the browser sends `gc-user-action: data_loading:opponents` instead of `data_loading:team`. Both return the same 25-field schema. See gc-user-action notes below.

```
GET https://api.team-manager.gc.com/teams/{team_id}
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
Accept: application/vnd.gc.com.team+json; version=0.10.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
gc-user-action: data_loading:team          # use this when fetching your own team
# gc-user-action: data_loading:opponents   # use this when fetching an opponent team
gc-user-action-id: {UUID}
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
```

**Note on Accept header:** This endpoint uses `application/vnd.gc.com.team+json; version=0.10.0` (singular, no `:list` cardinality), matching the single-object response shape. Compare with `/me/teams` which uses `application/vnd.gc.com.team:list+json; version=0.10.0` for a collection.

**Note on gc-user-action:** The browser sends `data_loading:team` when viewing your own team and `data_loading:opponents` when viewing an opponent team. Both values return a successful 200 response with the same schema. Either value is functionally accepted by the server -- the distinction appears to be for client-side analytics/telemetry only.

#### Response

A single JSON team object -- not an array. 910 bytes for the observed record (Lincoln Rebels 14U).

| Field                         | Type    | Notes |
|-------------------------------|---------|-------|
| `id`                          | UUID    | Team UUID. Same as path parameter. |
| `name`                        | string  | Full team name (e.g., `"Lincoln Rebels 14U"`). |
| `team_type`                   | string  | Observed value: `"admin"`. May reflect access level or team class. |
| `city`                        | string  | Team's home city. |
| `state`                       | string  | Two-letter state abbreviation (e.g., `"NE"`). |
| `country`                     | string  | Country name (e.g., `"United States"`). |
| `age_group`                   | string  | Age division (e.g., `"14U"`). |
| `competition_level`           | string  | Competition tier (e.g., `"club_travel"`). |
| `sport`                       | string  | Sport (e.g., `"baseball"`). |
| `season_year`                 | integer | Current season year (e.g., `2025`). |
| `season_name`                 | string  | Season name (e.g., `"summer"`). |
| `stat_access_level`           | string  | Controls who can view stats (e.g., `"confirmed_full"`). |
| `scorekeeping_access_level`   | string  | Controls who can keep score (e.g., `"staff_only"`). |
| `streaming_access_level`      | string  | Controls video access (e.g., `"confirmed_members"`). |
| `paid_access_level`           | string or null | Premium access tier. `null` when no paid tier is active. |
| `settings`                    | object  | Team settings sub-object. See below. |
| `organizations`               | array   | Array of organization membership objects. See below. |
| `ngb`                         | string  | JSON-encoded string containing an array of governing body affiliations (e.g., `"[\"usssa\"]"`, `"[]"`). Must be double-decoded: `json.loads(team["ngb"])`. |
| `team_avatar_image`           | null    | Always `null` in observed samples. Reserved for future use or requires different access. |
| `team_player_count`           | null    | Always `null` in observed samples. |
| `created_at`                  | string  | ISO 8601 timestamp of team creation (e.g., `"2024-11-02T12:34:20.229Z"`). |
| `public_id`                   | string  | Short alphanumeric public identifier (e.g., `"a1GFM9Ku0BbF"`). Used in public-facing URLs. |
| `url_encoded_name`            | string  | URL-safe team name slug (e.g., `"2025-summer-lincoln-rebels-14u"`). |
| `archived`                    | boolean | `false` for active teams; `true` for archived/historical teams. |
| `record`                      | object  | `{"wins": int, "losses": int, "ties": int}`. Cumulative win/loss record. Present even for archived teams. |

**`settings` sub-object:**

| Field                                       | Type         | Notes |
|---------------------------------------------|--------------|-------|
| `settings.scorekeeping`                     | object       | Scorekeeping configuration. |
| `settings.scorekeeping.bats`                | object       | Baseball-specific scorekeeping settings. |
| `settings.scorekeeping.bats.innings_per_game` | integer    | Default number of innings per game (e.g., `7`). |
| `settings.scorekeeping.bats.shortfielder_type` | string    | Shortfielder rule setting (e.g., `"none"`). |
| `settings.scorekeeping.bats.pitch_count_alert_1` | integer or null | First pitch count threshold for alerts. `null` if not configured. |
| `settings.scorekeeping.bats.pitch_count_alert_2` | integer or null | Second pitch count threshold for alerts. `null` if not configured. |
| `settings.maxpreps`                         | null         | MaxPreps integration settings. `null` in this sample -- may be configured for high school programs. |

**`organizations` array items:**

| Field             | Type   | Notes |
|-------------------|--------|-------|
| `organization_id` | UUID   | UUID of the organization this team belongs to. |
| `status`          | string | Membership status (e.g., `"active"`). |

#### Example Response (redacted)

```json
{
  "id": "72bb77d8-REDACTED",
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
      "organization_id": "8881846c-REDACTED",
      "status": "active"
    }
  ],
  "ngb": "[\"usssa\"]",
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
  }
}
```

#### Known Limitations

- **team_avatar_image always null** -- same as observed in `/me/teams`. Reserved or requires different access.
- **team_player_count always null** -- same as observed in `/me/teams`.
- **ngb is a JSON-encoded string** -- must be double-decoded. See `/me/teams` limitations for details.
- **Single-record sample** -- schema confirmed from one team. Fields like `paid_access_level`, `settings.maxpreps`, `settings.scorekeeping.bats.pitch_count_alert_*`, and `team_type` may have other values for high school or premium teams.
- **Relationship to /me/teams** -- the field set appears nearly identical to what `/me/teams` returns per-item, but this endpoint returns a single object rather than an array, and does not include `user_team_associations` (that is a query-parameter addition on `/me/teams`).
- **Opponent team access** -- CONFIRMED. Opponent `pregame_data.opponent_id` UUIDs from `/schedule` work as `team_id` here (validated 2026-03-04 with SE Elites 14U, team_id `ab7d4522-...`). Full 25-field schema returned identically. Differences observed vs. own-team: `organizations` was empty array `[]` (vs. one entry for own team), `ngb` was `"[]"` (vs. `"[\"usssa\"]"` for own team). These differences reflect the opponent's actual data, not access restrictions.

**Discovered:** 2026-03-04. **Opponent validation:** 2026-03-04.

---

### GET /teams/{team_id}/schedule

**Status:** CONFIRMED LIVE -- 228 total records (103 games, 90 practices, 35 other events) fully retrieved. Last verified: 2026-03-04.

Returns the full event schedule for a team, including all event types (games, practices, other), with optional venue enrichment when `fetch_place_details=true`. The response is a bare JSON array. No pagination observed for this endpoint (all 228 events returned in one response).

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
| `fetch_place_details` | No       | `true` -- enriches location objects with `google_place_details` and `place_id` from Google Places API. Without this param, location contains only `name` and `coordinates`. |

#### Headers

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
priority: u=1, i
origin: https://web.gc.com
referer: https://web.gc.com/
DNT: 1
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

#### Response

A bare JSON array of schedule item objects. Each item is a wrapper object with an `event` key. Game events additionally include a `pregame_data` key.

**Observed counts (2026-03-04, travel ball team, full history):**
- 228 total events
- 103 `game` events
- 90 `practice` events
- 35 `other` events
- Date range: 2024-11-08 to 2025-07-15

**Top-level item structure:**

| Field          | Type   | Always Present | Description |
|----------------|--------|----------------|-------------|
| `event`        | object | Yes            | Core event data (all event types) |
| `pregame_data` | object | Games only     | Game-specific opponent and lineup data. Present on all 103 game events; absent on practice and other events. |

**`event` object fields:**

| Field        | Type    | Required | Notes |
|--------------|---------|----------|-------|
| `id`         | UUID    | Yes      | Event UUID. For game events, equals `pregame_data.id` and `pregame_data.game_id`. |
| `event_type` | string  | Yes      | One of: `"game"`, `"practice"`, `"other"` |
| `sub_type`   | array   | Yes      | Always an empty array in this sample (228 records). Purpose unknown. |
| `status`     | string  | Yes      | One of: `"scheduled"`, `"canceled"`. 162 scheduled, 66 canceled in this sample. |
| `full_day`   | boolean | Yes      | `true` for all-day events (12/228). When `true`, `start` and `end` contain `date` (YYYY-MM-DD) instead of `datetime`. `timezone` is `null` for full-day events. |
| `team_id`    | UUID    | Yes      | The requesting team's UUID. |
| `start`      | object  | Yes      | `{"datetime": "ISO8601"}` for timed events; `{"date": "YYYY-MM-DD"}` for full-day events. |
| `end`        | object  | Yes      | Same shape as `start`. |
| `arrive`     | object  | No       | Arrival time: `{"datetime": "ISO8601"}`. Present on 86/228 events (mostly games). Absent for most practices. |
| `location`   | object  | No       | Venue data. See Location Object below. Absent (empty object `{}`) on 87/228 events. |
| `timezone`   | string  | Yes*     | IANA timezone string (e.g., `"America/Chicago"`). `null` for full-day events. |
| `notes`      | string  | No       | Free-text notes (e.g., field number like `"Field 7"`). Non-null on 49/228 events. |
| `title`      | string  | Yes      | Human-readable event title (e.g., `"Away Game vs. Nebraska Prime Gold 14u"`, `"Practice"`). |
| `series_id`  | null    | Yes      | Always `null` in this sample. May reference a tournament or series in other contexts. |

**Location object fields (conditional by `fetch_place_details`):**

The `location` object has variable shape depending on whether venue data was resolved and whether `fetch_place_details=true` was sent.

| Field combination observed          | Count | Notes |
|-------------------------------------|-------|-------|
| `{}` (empty)                        | 87    | No location set for this event |
| `{name}`                            | 69    | Name only (e.g., `"Indoor"`) |
| `{name, coordinates, address}`      | 33    | Has lat/long and street address |
| `{address, coordinates}`            | 20    | Has lat/long and street address, no name |
| `{name, google_place_details, place_id}` | 18 | Google Place enrichment, no separate coordinates field |
| `{google_place_details, place_id}`  | 1     | Google Place enrichment only |

| Field                  | Type   | Description |
|------------------------|--------|-------------|
| `name`                 | string | Venue name (e.g., `"Densmore 3"`, `"Centennial Park"`) |
| `coordinates`          | object | `{"latitude": float, "longitude": float}` -- WGS84 decimal degrees |
| `address`              | array  | `["street line", "city state"]` -- two-element string array |
| `place_id`             | string | Google Places place ID (e.g., `"ChIJxVpa4OkidocRQJDGpUFBIsU"`) |
| `google_place_details` | object | Enriched venue data from Google Places. See below. |

**`google_place_details` sub-object:**

| Field            | Type   | Description |
|------------------|--------|-------------|
| `id`             | string | Google Places place ID (same as `place_id`) |
| `lat_long`       | object | `{"lat": float, "long": float}` -- note: uses `long` (not `longitude`) |
| `address`        | string | Full formatted address string (e.g., `"North Platte, NE 69101, USA"`) |
| `address_object` | object | Structured address: `{city, state, country, postal_code}` |
| `location_name`  | string | Short location name (e.g., `"North Platte"`) |
| `types`          | array  | Google Place type tags (e.g., `["premise", "street_address"]`) |

**`pregame_data` object fields (game events only):**

| Field           | Type   | Required | Notes |
|-----------------|--------|----------|-------|
| `id`            | UUID   | Yes      | Always equals `event.id` and `game_id`. |
| `game_id`       | UUID   | Yes      | Always equals `event.id` and `pregame_data.id`. Confirmed on all 103 game records. |
| `opponent_name` | string | Yes      | Opponent team name (e.g., `"Blackhawks 14U"`). Non-null on all 103 game records. |
| `opponent_id`   | UUID   | Yes      | Opponent team UUID. Non-null on all 103 game records. **CONFIRMED** usable as `team_id` in `GET /teams/{team_id}` (validated 2026-03-04). Likely also usable in other team-scoped endpoints (season-stats, players, etc.) -- not yet tested. |
| `home_away`     | string | No       | `"home"`, `"away"`, or `null`. All three values observed. |
| `lineup_id`     | UUID   | No       | UUID of the pre-set lineup, if one was saved. Null on 25/103, non-null on 78/103. |

#### Example Response Item (game event, with google_place_details)

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
        "address": "{REDACTED_CITY}, NE, USA",
        "address_object": {
          "city": "{REDACTED_CITY}",
          "state": "NE",
          "country": "United States",
          "postal_code": "69101"
        },
        "location_name": "North Platte",
        "types": ["premise", "street_address"]
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

#### Example Response Item (full-day event)

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

#### Known Limitations

- `sub_type` is always an empty array in this sample (228 records). Its purpose is unknown.
- `series_id` is always `null`. May be populated for tournament series -- not yet observed.
- `home_away` can be `null` even for game events. Null vs. explicit value semantics unclear.
- No pagination headers observed; all 228 events returned in a single response. Behavior with very large histories (500+ events) untested.
- Coordinates appear in two formats: `{latitude, longitude}` in `location.coordinates` and `{lat, long}` in `location.google_place_details.lat_long`. These use different key names -- handle both when parsing.
- `opponent_id` in `pregame_data` is **confirmed** usable as `team_id` in `GET /teams/{team_id}` (validated 2026-03-04). Usability with other team-scoped endpoints (season-stats, players, game-summaries) is structurally consistent but not yet confirmed with live captures.

**Discovered:** Pre-2026-03-01 (initial capture). **Schema fully documented:** 2026-03-04.

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

**Status:** Confirmed from curl capture. Schema confirmed via public variant 2026-03-04.

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
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.player:list+json; version=0.1.0
User-Agent: <browser UA>
```

**Note:** The `/players` capture did not include `gc-user-action-id` or `gc-user-action`. These tracking headers appear to be optional across all endpoints.

#### Response

A **bare JSON array** of player objects. Schema confirmed from the public variant (`GET /teams/public/{public_id}/players`) -- both endpoints return the same 5-field structure.

| Field         | Type   | Description                                                          |
|---------------|--------|----------------------------------------------------------------------|
| `id`          | string | Player UUID. Use as `player_id` in `/teams/{team_id}/players/{player_id}/stats`. |
| `first_name`  | string | Player's first name.                                                 |
| `last_name`   | string | Player's last name.                                                  |
| `number`      | string | Jersey number as a string (e.g., `"14"`, `"25"`). May have duplicates on a roster. |
| `avatar_url`  | string | Player avatar image URL, or empty string `""` if not set.            |

**Note:** This endpoint does NOT return position information. Positions appear only in boxscore `player_text` fields (e.g., `"(CF)"`, `"(SS, P)"`).

**Note:** Player UUIDs returned here are the same UUIDs used as keys in `GET /teams/{team_id}/season-stats` `stats_data.players` and as `player_id` in `GET /teams/{team_id}/players/{player_id}/stats`. This is the correct endpoint for resolving UUID-to-name mapping.

#### Example Response (redacted — first names truncated to initials, IDs preserved)

```json
[
  {"id": "{PLAYER_UUID_1}", "first_name": "A", "last_name": "{LAST_1}", "number": "14", "avatar_url": ""},
  {"id": "{PLAYER_UUID_2}", "first_name": "A", "last_name": "{LAST_2}", "number": "7",  "avatar_url": ""},
  {"id": "{PLAYER_UUID_3}", "first_name": "A", "last_name": "{LAST_3}", "number": "5",  "avatar_url": ""}
]
```

#### Known Limitations

- No position data. Position assignment is only derivable from boxscore `player_text` fields on a per-game basis.
- `avatar_url` is an empty string when not set (not null). In the LSB JV 2026-03-04 capture, 0 of 20 players had avatars.
- Duplicate jersey numbers are possible (observed: two players wearing #15 on LSB JV).
- No pagination observed on this endpoint -- all players returned in a single response.

**Discovered:** Pre-2026-03-01 (schema confirmed via public variant 2026-03-04)

---

### GET /teams/public/{public_id}/players

**Status:** CONFIRMED LIVE -- 200 OK, 20 players returned. Discovered 2026-03-04.

**IMPORTANT URL PATTERN NOTE:** This endpoint uses the path segment `/teams/public/` (not `/public/teams/`). This is the reverse of the public team profile endpoints (`GET /public/teams/{public_id}`). Both path structures exist -- this is an intentional API distinction, not a typo.

Returns the public roster for a team identified by its `public_id` slug. Returns the same 5-field player structure as the authenticated `GET /teams/{team_id}/players`. Despite the "public" label in the path, this endpoint DOES include gc-token and gc-device-id in the captured curl -- authentication may be required (see Known Limitations).

```
GET https://api.team-manager.gc.com/teams/public/{public_id}/players
```

#### Path Parameters

| Parameter   | Description                                                                          |
|-------------|--------------------------------------------------------------------------------------|
| `public_id` | Team public ID slug (e.g., `y24fFdnr3RAN` for LSB Standing Bear JV Grizzlies). NOT a UUID. Obtain from `GET /me/teams` (`public_id` field) or from `GET /teams/{team_id}` (`public_id` field). |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.public_player:list+json; version=0.0.0
x-pagination: true
User-Agent: <browser UA>
```

**Key observations:**
- Accept header uses resource type `public_player` (not `player`) and version `0.0.0` (not `0.1.0`).
- `x-pagination: true` was sent in the capture. No `x-next-page` response header observed -- all 20 records fit on a single page.
- No `gc-user-action` or `gc-user-action-id` observed in this capture.
- Authentication headers (gc-token, gc-device-id) were included. Whether auth is truly required has NOT been tested without credentials -- see Known Limitations.

#### Response

A **bare JSON array** of player objects. 20 players returned for LSB JV in a single page.

| Field         | Type   | Description                                                          |
|---------------|--------|----------------------------------------------------------------------|
| `id`          | string | Player UUID. Same UUID used in authenticated player-stats endpoints. |
| `first_name`  | string | Player's first name.                                                 |
| `last_name`   | string | Player's last name.                                                  |
| `number`      | string | Jersey number as a string. May have duplicates on a roster.          |
| `avatar_url`  | string | Player avatar image URL, or empty string `""` if not set.            |

**Relationship to other endpoints:** The `id` values returned here are valid as `player_id` in `GET /teams/{team_id}/players/{player_id}/stats` and as keys in `GET /teams/{team_id}/season-stats` `stats_data.players`.

#### Example Response (first names truncated to initial for privacy; full names are real LSB JV players)

```json
[
  {"id": "{PLAYER_UUID_1}", "first_name": "A", "last_name": "{LAST_1}", "number": "14", "avatar_url": ""},
  {"id": "{PLAYER_UUID_2}", "first_name": "A", "last_name": "{LAST_2}", "number": "7",  "avatar_url": ""},
  {"id": "{PLAYER_UUID_3}", "first_name": "A", "last_name": "{LAST_3}", "number": "5",  "avatar_url": ""},
  {"id": "{PLAYER_UUID_4}", "first_name": "B", "last_name": "{LAST_4}", "number": "15", "avatar_url": ""},
  {"id": "{PLAYER_UUID_5}", "first_name": "B", "last_name": "{LAST_5}", "number": "4",  "avatar_url": ""},
  {"id": "{PLAYER_UUID_6}", "first_name": "S", "last_name": "{LAST_6}", "number": "1",  "avatar_url": ""}
]
```

*(20 total players -- 14 additional records omitted from example)*

#### Known Limitations

- **Auth requirement unverified:** The capture included gc-token and gc-device-id. Whether this endpoint works without credentials (as a fully public endpoint) has NOT been tested. The `/public/teams/{public_id}` endpoints do work without auth -- this endpoint may too, given the "public" path segment. Test without credentials to confirm.
- **No position data.** Only id, name, number, avatar. Positions are not returned.
- **Duplicate jersey numbers possible.** Observed: two players wearing #15 on LSB JV 2026-03-04 capture.
- **All avatar_url empty.** In the LSB JV capture, 0 of 20 players had avatar photos set.
- **No pagination triggered.** All 20 players returned on a single page despite `x-pagination: true` being sent. Page size for larger rosters is unknown -- send `x-pagination: true` as a precaution.
- **First names truncated.** This API returns first_name as a single character (initial) for this team. This may be a data entry pattern on this specific team, not an API behavior. The authenticated `/teams/{team_id}/players` endpoint may return full names.

**Discovered:** 2026-03-04

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

### GET /public/teams/{public_id}

**Status:** CONFIRMED LIVE -- 200 OK, single public team profile returned. Schema fully documented 2026-03-04.

**AUTHENTICATION: NOT REQUIRED.** This endpoint returns team profile data without any `gc-token` or `gc-device-id` headers. No authentication headers were present in the confirmed live capture. This is a public endpoint accessible to anyone with the team's `public_id`.

Returns a lightweight public profile for a team identified by its short alphanumeric `public_id` slug (e.g., `a1GFM9Ku0BbF`). The `public_id` is available in the response of `GET /teams/{team_id}` as the `public_id` field. This endpoint returns a subset of the fields available in the authenticated `GET /teams/{team_id}` endpoint -- no access levels, settings, organizations, or internal UUIDs are exposed.

**Key implication:** For opponent teams whose `public_id` is known, this endpoint provides name, location, sport, age group, current season record, team avatar, and coaching staff -- without any credential rotation dependency.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}
```

#### Path Parameters

| Parameter   | Type   | Description |
|-------------|--------|-------------|
| `public_id` | string | Short alphanumeric public identifier (e.g., `"a1GFM9Ku0BbF"`). NOT a UUID. Found in the `public_id` field of `GET /teams/{team_id}` and `GET /me/teams` responses. |

#### Query Parameters

None observed.

#### Headers

**Authentication headers (`gc-token`, `gc-device-id`) are NOT required and were NOT sent in the confirmed live capture.**

```
gc-app-name: web
Accept: application/vnd.gc.com.public_team_profile+json; version=0.1.0
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
```

**Note on gc-user-action:** No `gc-user-action` or `gc-user-action-id` headers were present in this capture. Consistent with the unauthenticated nature of the endpoint.

**Note on Accept header:** This endpoint uses a distinct resource type `public_team_profile` (not `team`), versioned at `0.1.0`. This confirms the public profile is a separate, intentionally limited API resource -- not a degraded view of the private team object.

#### Response

A single JSON object. Approximately 1,200 bytes for the observed record. No pagination (single object by design).

| Field                   | Type    | Notes |
|-------------------------|---------|-------|
| `id`                    | string  | The team's `public_id` (short slug, e.g., `"a1GFM9Ku0BbF"`). NOT the UUID. This field name is `id` but the value is the public slug, not the internal UUID. |
| `name`                  | string  | Full team name (e.g., `"Lincoln Rebels 14U"`). |
| `sport`                 | string  | Sport (e.g., `"baseball"`). |
| `ngb`                   | string  | JSON-encoded string containing an array of governing body affiliations (e.g., `"[\"usssa\"]"`). Same double-decode quirk as the authenticated endpoints: `json.loads(obj["ngb"])`. |
| `location`              | object  | Team's home location. See sub-fields below. |
| `location.city`         | string  | City name (e.g., `"Lincoln"`). |
| `location.state`        | string  | State abbreviation (e.g., `"NE"`). |
| `location.country`      | string  | Country name (e.g., `"United States"`). |
| `age_group`             | string  | Age division (e.g., `"14U"`). |
| `team_season`           | object  | Current season context. See sub-fields below. |
| `team_season.season`    | string  | Season name (e.g., `"summer"`). |
| `team_season.year`      | integer | Season year (e.g., `2025`). |
| `team_season.record`    | object  | Win/loss/tie record for the current season. See sub-fields below. |
| `team_season.record.win`   | integer | Wins in the current season. |
| `team_season.record.loss`  | integer | Losses in the current season. |
| `team_season.record.tie`   | integer | Ties in the current season. |
| `avatar_url`            | string or null | Signed CloudFront URL for the team's avatar image. Includes expiry embedded in the signature (Policy/Key-Pair-Id/Signature query params). The URL itself is not a credential. `null` if no avatar is set. |
| `staff`                 | array of string | List of staff member names (coaches, managers). Observed as full name strings (e.g., `["Ryan Treat", "Jason Jackson", "Jason Wilkinson"]`). May be empty `[]` if no staff configured. |

**Important field distinction:** The `id` field in this response is the `public_id` slug (e.g., `"a1GFM9Ku0BbF"`), not the internal UUID. The internal UUID is not exposed in this public response. To get the internal UUID, use the authenticated `GET /teams/{team_id}` endpoint.

**Record field name difference:** The authenticated `GET /teams/{team_id}` response uses `record.wins`/`record.losses`/`record.ties` (plural). The public endpoint uses `team_season.record.win`/`record.loss`/`record.tie` (singular). These are the same data with different key names.

**Season scope:** The `team_season.record` reflects the current season totals only (keyed by `season` + `year`), unlike the authenticated `GET /teams/{team_id}` `record` object which reflects cumulative all-time history.

#### Example Response (redacted)

```json
{
  "id": "a1GFM9Ku0BbF",
  "name": "Lincoln Rebels 14U",
  "sport": "baseball",
  "ngb": "[\"usssa\"]",
  "location": {
    "city": "Lincoln",
    "state": "NE",
    "country": "United States"
  },
  "age_group": "14U",
  "team_season": {
    "season": "summer",
    "year": 2025,
    "record": {
      "win": 61,
      "loss": 29,
      "tie": 2
    }
  },
  "avatar_url": "https://media-service.gc.com/REDACTED?Policy=REDACTED&Key-Pair-Id=REDACTED&Signature=REDACTED",
  "staff": [
    "Ryan Treat",
    "Jason Jackson",
    "Jason Wilkinson"
  ]
}
```

#### Known Limitations

- **No internal UUID exposed** -- the `id` field is the `public_id` slug, not the internal UUID. Cross-referencing with authenticated endpoints requires mapping `public_id` to UUID via the authenticated team detail endpoint.
- **Limited field set** -- this endpoint intentionally omits access levels, settings, internal organization IDs, `url_encoded_name`, `competition_level`, `archived`, and `created_at`. These require authenticated access.
- **Staff names only, no roles** -- the `staff` array lists full names as plain strings. No roles (head coach, assistant, manager) are included. Count and order may vary.
- **avatar_url is a time-limited signed URL** -- the CloudFront signature in the URL has an embedded expiry (Policy contains `DateLessThan` epoch). The URL will expire and must be fetched again. Do not cache the URL itself; cache the image bytes if needed.
- **ngb double-decode quirk** -- same as all other GC endpoints: `ngb` is a JSON-encoded string, not a native JSON array. Must be double-decoded: `json.loads(obj["ngb"])`.
- **Single sample** -- confirmed from one team (Lincoln Rebels 14U, USSSA travel ball, 14U). Fields like `staff` (empty vs. populated), `avatar_url` (null vs. populated), and `ngb` variants have not been tested across many teams.
- **Rate limiting behavior unknown** -- since authentication is not required, this endpoint may have stricter rate limits for unauthenticated clients, or it may be more permissive. Rate limit behavior has not been tested.
- **public_id availability** -- not all teams may have a `public_id`. Only teams with `public_id` non-null in the authenticated team detail response are addressable here.

**Discovered:** 2026-03-04.

---

### GET /public/teams/{public_id}/games

**Status:** CONFIRMED LIVE -- 200 OK, 32 game records returned. Schema fully documented 2026-03-04.

**AUTHENTICATION: NOT REQUIRED.** This endpoint returns a team's completed game schedule without any `gc-token` or `gc-device-id` headers. No authentication headers were present in the confirmed live capture.

Returns a list of all games (past and future) for a team identified by its short alphanumeric `public_id` slug. This is the public-facing companion to `GET /teams/{team_id}/schedule` -- it provides game-only events (no practices or "other" events) with final scores and opponent information. All 32 records in this capture had `game_status: "completed"`, suggesting it may only surface completed games, or this team's season was fully completed at time of capture.

**Key implication:** Final scores, home/away context, opponent names, and video availability can be retrieved for any team whose `public_id` is known -- without any credential dependency. This enables scouting data collection for opponent teams at zero authentication cost.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}/games
```

#### Path Parameters

| Parameter   | Type   | Description |
|-------------|--------|-------------|
| `public_id` | string | Short alphanumeric public identifier (e.g., `"QTiLIb2Lui3b"`). NOT a UUID. Found in the `public_id` field of `GET /teams/{team_id}` and `GET /me/teams` responses. Same identifier used by `GET /public/teams/{public_id}`. |

#### Query Parameters

None observed.

#### Headers

**Authentication headers (`gc-token`, `gc-device-id`) are NOT required and were NOT sent in the confirmed live capture.**

```
gc-app-name: web
Accept: application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0
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
```

**Note on gc-user-action:** No `gc-user-action` or `gc-user-action-id` headers were present in this capture. Consistent with the unauthenticated nature of the endpoint.

**Note on Accept header:** New resource type `public_team_schedule_event` (not `event` used on the authenticated `/schedule` endpoint), cardinality `list`, version `0.0.0`. Full value: `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0`.

#### Response

A **bare JSON array** of game event objects. No pagination observed (32 records in a single response; no `x-next-page` header). Response size: approximately 25.7 KB.

All 11 top-level fields are present on every record (no optional top-level fields observed in this sample of 32).

| Field                        | Type            | Notes |
|------------------------------|-----------------|-------|
| `id`                         | string (UUID)   | Game event UUID. Matches `event.id` in the authenticated schedule endpoint. |
| `opponent_team`              | object          | Opponent information. See sub-fields below. Always present (non-null). |
| `opponent_team.name`         | string          | Opponent team display name (e.g., `"Jr Bluejays 15U"`). Always present on all 32 records. |
| `opponent_team.avatar_url`   | string or absent | Signed CloudFront URL for the opponent team's avatar image. Present on 21/32 records. Absent (key not present) when the opponent has no avatar -- field is not included, not null. |
| `is_full_day`                | boolean         | Whether the event is an all-day event (no specific time). All 32 records: `false`. Full-day game events may use a different date format -- see schedule endpoint full-day handling. |
| `start_ts`                   | string (ISO 8601) | Game start timestamp in UTC (e.g., `"2025-05-27T22:30:00.000Z"`). Always present. |
| `end_ts`                     | string (ISO 8601) | Game end timestamp in UTC. Always present. |
| `timezone`                   | string          | IANA timezone name for the event (e.g., `"America/Chicago"`). All 32 records present. Consistent with `is_full_day: false` -- when `is_full_day: true`, `timezone` would be `null` per authenticated schedule behavior. |
| `home_away`                  | string          | `"home"` or `"away"`. Always present. 16 home / 16 away in this sample. |
| `score`                      | object          | Final score. Always present. See sub-fields below. |
| `score.team`                 | integer         | Score for the requesting team (the team identified by `public_id`). |
| `score.opponent_team`        | integer         | Score for the opponent team. |
| `game_status`                | string          | Current game status. All 32 records: `"completed"`. Other possible values not yet observed (e.g., `"scheduled"`, `"in_progress"`, `"canceled"` likely exist by analogy with authenticated endpoint). |
| `has_videos_available`       | boolean         | Whether game video is available. 20/32 `true`, 12/32 `false`. |
| `has_live_stream`            | boolean         | Whether a live stream was or is available. All 32 records: `false`. |

#### Example Response (redacted -- signed URLs shortened)

```json
[
  {
    "id": "ce8f15e7-8658-45cd-aef4-e9cacc61a0db",
    "opponent_team": {
      "name": "Jr Bluejays 15U"
    },
    "is_full_day": false,
    "start_ts": "2025-05-27T22:30:00.000Z",
    "end_ts": "2025-05-28T00:30:00.000Z",
    "timezone": "America/Chicago",
    "home_away": "home",
    "score": {
      "team": 10,
      "opponent_team": 5
    },
    "game_status": "completed",
    "has_videos_available": false,
    "has_live_stream": false
  },
  {
    "id": "77475a1d-f8fb-4844-8303-da579eb73c80",
    "opponent_team": {
      "name": "Lincoln East Top Dogg 15U",
      "avatar_url": "https://media-service.gc.com/REDACTED?Policy=REDACTED&Key-Pair-Id=REDACTED&Signature=REDACTED"
    },
    "is_full_day": false,
    "start_ts": "2025-05-29T22:30:00.000Z",
    "end_ts": "2025-05-29T23:30:00.000Z",
    "timezone": "America/Chicago",
    "home_away": "home",
    "score": {
      "team": 5,
      "opponent_team": 16
    },
    "game_status": "completed",
    "has_videos_available": true,
    "has_live_stream": false
  }
]
```

#### Comparison to Authenticated Endpoints

| Feature | `/public/teams/{id}/games` (this endpoint) | `/teams/{id}/schedule` (authenticated) | `/teams/{id}/game-summaries` (authenticated) |
|---|---|---|---|
| **Auth required** | No | Yes | Yes |
| **Event types** | Games only | Games, practices, other | Games only |
| **Includes score** | Yes | No (only in pregame_data as `lineup_id` etc.) | Yes (via game_stream) |
| **Includes opponent name** | Yes | Via `pregame_data.opponent_id` (needs join) | No direct opponent name |
| **Includes home/away** | Yes | Yes (in `pregame_data.home_away`) | No |
| **Includes video availability** | Yes (has_videos_available) | No | Yes (via game_stream) |
| **Includes per-player stats** | No | No | No (summary only) |
| **Location/venue details** | No | Yes (google_place_details) | No |
| **Pagination** | Not observed (32 records) | Not observed (228 records) | Yes (x-next-page, 50/page) |
| **Date range** | Full season (May-Jul 2025) | Full history (Nov 2024 - Jul 2025) | Full history (92 games) |
| **game_status values seen** | `"completed"` only | `"scheduled"`, `"canceled"` | Not observed |

**Key differences from authenticated schedule:**
- No location/venue information (no `location` object or `google_place_details`)
- No practice or "other" events -- games only
- Includes final scores directly (authenticated schedule does not)
- Includes `has_videos_available` flag
- `opponent_team.name` is directly embedded (authenticated schedule requires join via `pregame_data.opponent_id`)
- `id` field matches `event.id` in authenticated schedule (join key confirmed by type: both are UUID strings)

#### Known Limitations

- **game_status values incomplete** -- only `"completed"` observed in this 32-record sample. Future/scheduled games likely produce a different status but this is unconfirmed. Behavior for in-progress or canceled games is unknown.
- **No location data** -- no venue information (field name, address, coordinates) is provided. If venue context is needed for scouting, the authenticated schedule endpoint is required.
- **No player-level data** -- scores only; no at-bats, pitching stats, or play-by-play.
- **No opponent internal UUID** -- the `opponent_team` object contains only `name` and optionally `avatar_url`. The opponent's GameChanger UUID (needed for authenticated scouting endpoints) is not exposed. To obtain it, cross-reference against `/teams/{team_id}/schedule`'s `pregame_data.opponent_id` by matching game `id` (join key).
- **`avatar_url` is time-limited** -- signed CloudFront URL with embedded expiry. Do not cache the URL string; fetch fresh when needed.
- **No pagination observed** -- 32 records returned in a single response. It is unknown whether teams with longer histories trigger pagination. No `x-next-page` header was present.
- **Single team tested** -- confirmed from one team (`QTiLIb2Lui3b`, a different team from the `/public/teams/{public_id}` sample). Cross-team behavior (varying record counts, scheduled future games, etc.) not yet explored.
- **`opponent_team.avatar_url` absent on 11/32 records** -- field is completely absent (not null) when the opponent has no avatar image configured.
- **Rate limiting for unauthenticated clients** -- unknown. May be more permissive than authenticated endpoints, or may have different limits.
- **public_id availability** -- not all teams may have a `public_id`. Only teams with a non-null `public_id` in the authenticated team detail response are addressable here.

**Discovered:** 2026-03-04.

---

### GET /public/teams/{public_id}/games/preview

**Status:** CONFIRMED LIVE -- 200 OK, 32 game records returned. Schema fully documented 2026-03-04.

**AUTHENTICATION: NOT REQUIRED.** This endpoint returns a team's recent completed games without any `gc-token` or `gc-device-id` headers.

Returns a list of recent completed games for a team identified by its short alphanumeric `public_id` slug. This is a closely related sibling to `GET /public/teams/{public_id}/games` -- both return unauthenticated public game data from the same team, same record count (32), same records in the same order. The key structural differences are:

- **`event_id` instead of `id`** -- the UUID field has a different key name
- **Missing `has_videos_available`** -- this field present in `/games` is absent here
- **Different Accept header resource type** -- `public_team_event` (not `public_team_schedule_event`)

The "preview" naming may indicate this endpoint powers a preview widget or widget-style embed in the GameChanger web app. Based on the 32-record sample, the "preview" endpoint returns the same underlying data as `/games` with a slightly reduced field set and different field naming. When `has_videos_available` is not needed, both endpoints are functionally equivalent.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}/games/preview
```

#### Path Parameters

| Parameter   | Type   | Description |
|-------------|--------|-------------|
| `public_id` | string | Short alphanumeric public identifier (e.g., `"QTiLIb2Lui3b"`). NOT a UUID. Found in the `public_id` field of `GET /teams/{team_id}` and `GET /me/teams` responses. Same identifier used by `GET /public/teams/{public_id}` and `GET /public/teams/{public_id}/games`. |

#### Query Parameters

None observed.

#### Headers

**Authentication headers (`gc-token`, `gc-device-id`) are NOT required and were NOT sent in the confirmed live capture.**

```
gc-app-name: web
Accept: application/vnd.gc.com.public_team_event:list+json; version=0.0.0
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
```

**Note on gc-user-action:** No `gc-user-action` or `gc-user-action-id` headers were present in this capture. Consistent with the unauthenticated nature of the endpoint.

**Note on Accept header:** Resource type `public_team_event` -- distinct from `public_team_schedule_event` used on the sibling `/games` endpoint. Cardinality `list`, version `0.0.0`. Full value: `application/vnd.gc.com.public_team_event:list+json; version=0.0.0`.

#### Response

A **bare JSON array** of game event objects. No pagination observed (32 records in a single response; no `x-next-page` header present). Response size: approximately 25.0 KB. Content-type: `application/json; charset=utf-8`.

**10 top-level fields per record** (compared to 11 in `/games` -- `has_videos_available` is absent here).

| Field                        | Type              | Notes |
|------------------------------|-------------------|-------|
| `event_id`                   | string (UUID)     | Game event UUID. **Note: key is `event_id`, not `id` as in `/games`.** Matches `event.id` in the authenticated schedule endpoint and `id` in `/games`. |
| `opponent_team`              | object            | Opponent information. Always present (non-null). |
| `opponent_team.name`         | string            | Opponent team display name. Always present on all 32 records. |
| `opponent_team.avatar_url`   | string or absent  | Signed CloudFront URL for the opponent team's avatar image. Present on 21/32 records. Absent (key not present) when the opponent has no avatar. |
| `is_full_day`                | boolean           | Whether the event is an all-day event. All 32 records: `false`. |
| `start_ts`                   | string (ISO 8601) | Game start timestamp in UTC (e.g., `"2025-05-27T22:30:00.000Z"`). Always present. |
| `end_ts`                     | string (ISO 8601) | Game end timestamp in UTC. Always present. |
| `timezone`                   | string            | IANA timezone name (e.g., `"America/Chicago"`). All 32 records present. |
| `home_away`                  | string            | `"home"` or `"away"`. Always present. 16 home / 16 away in this sample. |
| `score`                      | object            | Final score. Always present. |
| `score.team`                 | integer           | Score for the requesting team (the team identified by `public_id`). |
| `score.opponent_team`        | integer           | Score for the opponent team. |
| `game_status`                | string            | All 32 records: `"completed"`. Other values not observed. |
| `has_live_stream`            | boolean           | All 32 records: `false`. |

**Fields present in `/games` but ABSENT here:**
- `has_videos_available` -- not included in this endpoint's response schema.
- `id` -- the UUID field is named `event_id` here instead.

#### Example Response (redacted -- signed URLs shortened)

```json
[
  {
    "opponent_team": {
      "name": "Jr Bluejays 15U"
    },
    "is_full_day": false,
    "start_ts": "2025-05-27T22:30:00.000Z",
    "end_ts": "2025-05-28T00:30:00.000Z",
    "timezone": "America/Chicago",
    "home_away": "home",
    "score": {
      "team": 10,
      "opponent_team": 5
    },
    "game_status": "completed",
    "event_id": "ce8f15e7-8658-45cd-aef4-e9cacc61a0db",
    "has_live_stream": false
  },
  {
    "opponent_team": {
      "name": "Lincoln East Top Dogg 15U",
      "avatar_url": "https://media-service.gc.com/REDACTED?Policy=REDACTED&Key-Pair-Id=REDACTED&Signature=REDACTED"
    },
    "is_full_day": false,
    "start_ts": "2025-05-29T22:30:00.000Z",
    "end_ts": "2025-05-29T23:30:00.000Z",
    "timezone": "America/Chicago",
    "home_away": "home",
    "score": {
      "team": 5,
      "opponent_team": 16
    },
    "game_status": "completed",
    "event_id": "77475a1d-f8fb-4844-8303-da579eb73c80",
    "has_live_stream": false
  }
]
```

#### Comparison to /public/teams/{public_id}/games

| Feature | `/games/preview` (this endpoint) | `/games` |
|---|---|---|
| **Auth required** | No | No |
| **Record count** | 32 (same team, same capture) | 32 |
| **Record order** | Same as `/games` | Reverse chronological |
| **Primary UUID field name** | `event_id` | `id` |
| **`has_videos_available`** | ABSENT | Present |
| **`game_status` values** | `"completed"` only | `"completed"` only |
| **`has_live_stream`** | Present (all `false`) | Present (all `false`) |
| **`score`** | Present | Present |
| **`opponent_team`** | Present (name + optional avatar_url) | Present (name + optional avatar_url) |
| **Accept header resource type** | `public_team_event` | `public_team_schedule_event` |
| **Pagination** | Not observed | Not observed |
| **Useful for implementors** | When `has_videos_available` is not needed and `event_id` naming is acceptable | Preferred -- includes `has_videos_available`, uses `id` which is consistent with authenticated schedule |

**Join key alignment:** The `event_id` UUID value in `/games/preview` is identical to the `id` UUID value in `/games` for the same game record. Both match `event.id` in the authenticated schedule endpoint.

#### Known Limitations

- **`has_videos_available` absent** -- if video availability is needed, use `/games` instead.
- **`event_id` field naming** -- unlike `/games` which uses `id`, this endpoint uses `event_id`. Implementors joining against `/games` or authenticated schedule must account for this field name difference.
- **game_status values incomplete** -- only `"completed"` observed. Future/scheduled game behavior unknown.
- **No location data** -- no venue information.
- **No player-level data** -- scores only.
- **No opponent internal UUID** -- opponent UUID not exposed; cross-reference via `/games` `id` join key.
- **`avatar_url` is time-limited** -- signed CloudFront URL. Do not cache URL strings.
- **No pagination observed** -- 32 records single response. Teams with larger histories may paginate (unconfirmed).
- **Single team tested** -- confirmed from one team (`QTiLIb2Lui3b`). Cross-team behavior not verified.
- **Purpose unclear** -- the "preview" naming suggests a limited/widget use case. It is unknown whether this endpoint has a different record limit or recency window vs. `/games`.

**Discovered:** 2026-03-04.

---

### GET /teams/{team_id}/opponents

**Status:** CONFIRMED LIVE -- 200 OK, 70 records across 2 pages. Discovered 2026-03-04.

Returns the list of opponent teams stored in the owning team's opponent registry. Each record is a local "copy" of an opponent, carrying a local `root_team_id` (the identifier within this team's opponent list), an optional `progenitor_team_id` (the canonical GameChanger team UUID for this opponent, when linked), a display `name`, an `is_hidden` flag, and the `owning_team_id`. Supports cursor-based pagination.

```
GET https://api.team-manager.gc.com/teams/{team_id}/opponents
GET https://api.team-manager.gc.com/teams/{team_id}/opponents?start_at={cursor}
```

#### Path Parameters

| Parameter  | Description                                                   |
|------------|---------------------------------------------------------------|
| `team_id`  | UUID of the team whose opponent list to fetch (owning team).  |

#### Query Parameters

| Parameter  | Required | Description                                                      |
|------------|----------|------------------------------------------------------------------|
| `start_at` | No       | Pagination cursor (integer sequence number). Omit for first page. Obtain from `x-next-page` response header. Observed cursor value: `51999720`. |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.opponent_team:list+json; version=0.0.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
gc-user-action: data_loading:opponents
gc-user-action-id: {UUID}
x-pagination: true
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
```

**Note on gc-user-action:** This endpoint uses `data_loading:opponents` -- the same value used when fetching a single opponent team via `GET /teams/{team_id}`. This is a confirmed second endpoint that uses this action value.

**Note on Accept header:** New resource type `opponent_team` (distinct from `team` used on `/teams/{team_id}`) with cardinality `list` and version `0.0.0`. Full value: `application/vnd.gc.com.opponent_team:list+json; version=0.0.0`.

#### Pagination Response Header

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/opponents?start_at={cursor}
```

When `x-next-page` is absent from the response headers, the current page is the last page.

**Confirmed 2026-03-04:** Page 1 (no cursor): 50 records, `x-next-page: .../opponents?start_at=51999720` (10,465 bytes). Page 2 (`start_at=51999720`): 20 records, no `x-next-page` header (4,482 bytes). Total: 70 opponent records.

#### Response Headers (observed 2026-03-04, both pages)

```
HTTP/2 200
content-type: application/json; charset=utf-8
x-server-epoch: <unix-seconds>
etag: <etag-value>
vary: Origin, Accept-Encoding
access-control-allow-origin: https://web.gc.com
access-control-expose-headers: Location,x-next-page,gc-signature,gc-timestamp,x-datadog-trace-id,...
x-cache: Miss from cloudfront
via: 1.1 <cloudfront-node> (CloudFront)
```

#### Response

A **bare JSON array** of opponent team objects. No wrapper object. Each element represents one opponent entry in the owning team's opponent registry.

| Field                | Type    | Nullable | Always Present | Description |
|----------------------|---------|----------|----------------|-------------|
| `root_team_id`       | UUID    | No       | Yes (70/70)    | Local identifier for this opponent record in the owning team's registry. Unique within the response. NOT the canonical GameChanger team UUID. |
| `owning_team_id`     | UUID    | No       | Yes (70/70)    | UUID of the team that owns this opponent registry. Always matches the `team_id` path parameter -- all 70 records had the same value. |
| `name`               | string  | No       | Yes (70/70)    | Display name of the opponent team (e.g., `"SE Elites 14U"`, `"Lincoln Dodgers 14U"`). May include suffixes like `"(bad)"` for placeholder or error entries. |
| `is_hidden`          | boolean | No       | Yes (70/70)    | Whether this opponent is hidden from the UI. `false` = visible (57/70); `true` = hidden (13/70). Hidden entries include duplicates, test records, and stale opponents. |
| `progenitor_team_id` | UUID    | Yes      | No (60/70)     | The canonical GameChanger team UUID for this opponent -- the "real" team in GC's system that this local record links to. Present on 60/70 records (86%); absent on 10/70 records (14%). See notes below. |

**`progenitor_team_id` -- the canonical opponent UUID:**

- When present, `progenitor_team_id` is the UUID that can be used with `GET /teams/{progenitor_team_id}`, `/season-stats`, `/players`, etc. to fetch the opponent's data.
- When absent (`null`-equivalent via field omission), the opponent was entered manually or as a placeholder and has no linked GC team record. All 10 records missing this field are notable: 7 are `is_hidden: true` (deleted/bad entries), 3 are visible but unlinked (e.g., `"Omaha Tigers Black 14U"`, `"Nebraska Legends 14U"`, `"Opponent TBD"`).
- `progenitor_team_id` values are NOT the same as `root_team_id` -- they are different UUID namespaces. Progenitor IDs link to the canonical team object; root IDs are local registry keys.
- `progenitor_team_id` is **the correct UUID to use for `/teams/{id}` and other authenticated team endpoints** when working from this response. The `root_team_id` is a registry artifact and does not work as a team_id in other endpoints (unconfirmed -- but structurally expected).

**`is_hidden` distribution:**

| `is_hidden` | Count | Description |
|-------------|-------|-------------|
| `false`     | 57    | Active visible opponents |
| `true`      | 13    | Hidden: duplicates, test data, bad entries, stale records |

**Relationship to schedule `pregame_data.opponent_id`:**

The `pregame_data.opponent_id` in `/teams/{team_id}/schedule` was confirmed to equal the `progenitor_team_id` here (validated against SE Elites 14U: `progenitor_team_id` = `ab7d4522-c839-482e-a837-4f8972b2aaca` matches expected canonical team ID). The schedule opponent_id and the opponents list progenitor_team_id point to the same canonical team object.

#### Example Response Items

```json
[
  {
    "root_team_id": "f1404ac2-fa56-4f57-9d3b-23756ba5c51a",
    "owning_team_id": "72bb77d8-REDACTED",
    "name": "SE Elites 14U",
    "is_hidden": false,
    "progenitor_team_id": "ab7d4522-REDACTED"
  },
  {
    "root_team_id": "536ea0c0-bf69-436a-b732-1b3c09530446",
    "owning_team_id": "72bb77d8-REDACTED",
    "name": "Omaha Tigers Black 14U",
    "is_hidden": false
  },
  {
    "root_team_id": "3a810c1b-1613-4118-8c77-37289a009d4e",
    "owning_team_id": "72bb77d8-REDACTED",
    "name": "Beatrice Bullets 14U (bad)",
    "is_hidden": true
  }
]
```

#### Known Limitations

- **`progenitor_team_id` absent on 10/70 records** -- opponents without this field cannot be looked up in other authenticated endpoints without additional matching by name. These include placeholder entries (`"Opponent TBD"`) and unlinked teams.
- **`root_team_id` is NOT a canonical team UUID** -- do not use `root_team_id` as a `team_id` in other endpoints. Use `progenitor_team_id` when available.
- **No stats or record in response** -- this endpoint returns only identity/registry data (name, IDs, visibility). To get wins/losses/stats for each opponent, call `GET /teams/{progenitor_team_id}` or `GET /teams/{progenitor_team_id}/season-stats` separately.
- **Includes all historical opponents** -- the list appears to include opponents from all prior seasons, not just the current season. 13 hidden entries suggest the team has accumulated stale/duplicate records over time.
- **Pagination confirmed** -- page size is 50 (same as game-summaries). For teams with many opponents, multiple pages may be needed.
- **Opponent teams only** -- this is the owning team's opponent registry, not a global team search. Only opponents explicitly added to this team's registry appear.
- **Single owning team tested** -- behavior for teams with different access levels or fewer/more opponents is unknown. The 70-record count is specific to `72bb77d8-...` (Lincoln Rebels 14U travel ball).

**Discovered:** 2026-03-04.

---

### GET /game-stream-processing/{game_stream_id}/boxscore

**Status:** CONFIRMED LIVE -- 200 OK, full per-game team box score with player names included. Discovered 2026-03-04. **UNBLOCKS E-002-03.**

Returns the complete box score for a single game: per-player batting lines, per-pitcher lines, and sparse "extra" stats (TB, SB, 2B, 3B, HR, HBP, E, WP, #P, TS, BF) for both teams. Player names and jersey numbers are embedded directly in the response -- no join to `/players` required for box score rendering.

```
GET https://api.team-manager.gc.com/game-stream-processing/{game_stream_id}/boxscore
```

#### Critical ID Mapping: Which ID to Use

This is the most important implementation detail for this endpoint. The path parameter is **`game_stream.id`** from the game-summaries response -- NOT `event_id`, NOT `game_stream.game_id`.

| ID source | Field name | Equals | Used for |
|-----------|-----------|--------|----------|
| `/teams/{id}/game-summaries` | `event_id` | `game_stream.game_id` | Schedule cross-reference, public games join |
| `/teams/{id}/game-summaries` | `game_stream.game_id` | `event_id` | Same as above -- duplicate field |
| `/teams/{id}/game-summaries` | `game_stream.id` | **boxscore URL param** | **Use this for the boxscore endpoint** |

In game-summaries: `event_id == game_stream.game_id` always (confirmed 92 records). `game_stream.id != game_stream.game_id` always. The `game_stream.id` is a distinct identifier that refers to the game stream processing record, not the schedule event.

**The data pipeline for box score crawling:**
1. Call `GET /teams/{team_id}/game-summaries` -- get `game_stream.id` for each completed game
2. Call `GET /game-stream-processing/{game_stream.id}/boxscore` -- get the box score

**Note:** The schedule endpoint (`GET /teams/{team_id}/schedule`) does NOT expose `game_stream.id`. You must go through game-summaries to get the correct ID for box score requests.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_stream_id` | UUID | The `game_stream.id` value from a game-summaries record. NOT the `event_id` or `game_stream.game_id`. |

#### Headers

No `gc-user-action` header was observed in this capture -- it may be optional for this endpoint (consistent with `/players` and `/associations`).

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.event_box_score+json; version=0.0.0
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
```

#### Response Schema

The response is a **JSON object** (not an array). Top-level keys are **team identifiers** -- one key per team, two keys total (home team and away team). This is the only endpoint observed so far that uses team identifiers as top-level response keys.

**Critical observation -- asymmetric key formats:** The two team keys use different ID formats:
- The team that "owns" the game stream (the account the gc-token belongs to) uses a **public_id slug** (e.g., `"y24fFdnr3RAN"`) as its key.
- The opponent team uses a **UUID** (e.g., `"16d38cf9-4f73-438c-83e4-1c28fbb23628"`) as its key.

This asymmetry is the single most surprising implementation detail. The slug format matches `public_id` from `/me/teams` and `/public/teams/{public_id}`. The UUID format matches the `team_id` used throughout other endpoints. Code that parses this response must handle both key formats.

```
{
  "<team_public_id_or_uuid>": {        // one entry per team (2 total: own + opponent)
    "players": [                        // roster context -- ALL players on team roster (not just those in lineup)
      {
        "id": "<uuid>",                 // player UUID
        "first_name": "<string>",
        "last_name": "<string>",
        "number": "<string>"            // jersey number (string, not int)
      }
    ],
    "groups": [                         // array of stat group objects
      {
        "category": "<string>",         // "lineup" (batting) or "pitching"
        "team_stats": {                 // team aggregate totals for this group
          // Lineup group totals: AB, R, H, RBI, BB, SO
          // Pitching group totals: IP, H, R, ER, BB, SO
        },
        "extra": [                      // sparse stats -- only players with non-zero values appear
          {
            "stat_name": "<string>",    // stat abbreviation (see Extra Stats table below)
            "stats": [
              {
                "player_id": "<uuid>",
                "value": <int>
              }
            ]
          }
        ],
        "stats": [                      // per-player main stats -- all batters/pitchers in lineup/rotation
          {
            "player_id": "<uuid>",
            "player_text": "<string>",  // position string e.g. "(CF)" "(SS, P)" "(2B, P, 2B)" or "" for sub
            "is_primary": <bool>,       // true for starters/primary player at position; false for subs
            "stats": {
              // Batting stats (lineup group):
              //   AB, R, H, RBI, BB, SO -- all int, always present
              // Pitching stats (pitching group):
              //   IP, H, R, ER, BB, SO -- all int, always present
            }
          }
        ]
      }
    ]
  }
}
```

**Note:** The `is_primary` field is present in the lineup `stats` array but NOT in the pitching `stats` array (confirmed in this capture). Pitchers are listed in order of appearance; no `is_primary` flag needed since relievers naturally follow starters.

#### Group Categories

| `category` | Stat group | Main stats fields | Notes |
|------------|-----------|------------------|-------|
| `"lineup"` | Batting/fielding | `AB`, `R`, `H`, `RBI`, `BB`, `SO` | Batters listed in batting order. `player_text` contains position(s) played. |
| `"pitching"` | Pitching | `IP`, `H`, `R`, `ER`, `BB`, `SO` | Pitchers listed in order pitched. `player_text` contains result: `"(W)"`, `"(L)"`, `"(SV)"`, or `""`. |

#### `player_text` Encoding

In the **lineup group**, `player_text` encodes the position(s) played:
- `"(CF)"` -- played one position the whole game
- `"(SS, P)"` -- multi-position player (shortstop and pitcher)
- `"(2B, P, 2B)"` -- played 2B, switched to pitcher, then back to 2B (position sequence)
- `""` -- player appeared as a substitute but `is_primary: false`; did not have a positional designation

In the **pitching group**, `player_text` encodes the game decision:
- `"(W)"` -- winning pitcher
- `"(L)"` -- losing pitcher
- `"(SV)"` -- save (not observed in this capture, but standard)
- `""` -- no decision (middle relievers)

#### Extra Stats (sparse)

The `extra` array carries stats where most players have 0 (zero-value players are omitted). Both lineup and pitching groups can have their own `extra` arrays.

**Lineup group extra stats observed:**

| `stat_name` | Description | Notes |
|-------------|-------------|-------|
| `2B`        | Doubles | Only players with doubles listed |
| `3B`        | Triples | Only players with triples listed (not observed in this sample) |
| `HR`        | Home runs | (not observed in this sample) |
| `TB`        | Total bases | |
| `HBP`       | Hit by pitch | |
| `SB`        | Stolen bases | |
| `CS`        | Caught stealing | |
| `E`         | Errors | Players who committed errors |

**Pitching group extra stats observed:**

| `stat_name` | Description | Notes |
|-------------|-------------|-------|
| `WP`        | Wild pitches | |
| `HBP`       | Hit batters | |
| `#P`        | Pitch count | Total pitches thrown |
| `TS`        | Strikes thrown | Total strikes |
| `BF`        | Batters faced | |

**Important:** `#P` and `TS` appear in pitching `extra` only (not in the main `stats` dict). Pitch count and strike data are only available here -- they require reconstructing from the sparse list.

#### Team Stats (Team Totals)

Each group has a `team_stats` object with team aggregate totals:

| Group | Fields |
|-------|--------|
| Lineup (batting) | `AB`, `R`, `H`, `RBI`, `BB`, `SO` |
| Pitching | `IP`, `H`, `R`, `ER`, `BB`, `SO` |

#### Example Response (redacted)

```json
{
  "y24fFdnr3RAN": {
    "players": [
      {"id": "06fd1556-REDACTED", "first_name": "Ashton", "last_name": "Tucker", "number": "7"},
      {"id": "7a2e8eff-REDACTED", "first_name": "Camden", "last_name": "Ledgerwood", "number": "2"}
    ],
    "groups": [
      {
        "category": "lineup",
        "team_stats": {"AB": 20, "R": 2, "H": 3, "RBI": 1, "BB": 4, "SO": 8},
        "extra": [
          {"stat_name": "TB", "stats": [{"player_id": "88cd80f1-REDACTED", "value": 1}]},
          {"stat_name": "SB", "stats": [{"player_id": "06fd1556-REDACTED", "value": 1}]},
          {"stat_name": "E",  "stats": [{"player_id": "7a2e8eff-REDACTED", "value": 1}]}
        ],
        "stats": [
          {
            "player_id": "bd13e8b0-REDACTED",
            "player_text": "(2B, P, 2B)",
            "is_primary": true,
            "stats": {"AB": 1, "R": 1, "H": 0, "RBI": 0, "BB": 2, "SO": 1}
          },
          {
            "player_id": "16886749-REDACTED",
            "player_text": "",
            "is_primary": false,
            "stats": {"AB": 0, "R": 0, "H": 0, "RBI": 0, "BB": 0, "SO": 0}
          }
        ]
      },
      {
        "category": "pitching",
        "team_stats": {"IP": 5, "H": 7, "R": 13, "ER": 7, "BB": 7, "SO": 2},
        "extra": [
          {"stat_name": "WP",  "stats": [{"player_id": "bd13e8b0-REDACTED", "value": 1}]},
          {"stat_name": "#P",  "stats": [{"player_id": "bd13e8b0-REDACTED", "value": 41}]},
          {"stat_name": "TS",  "stats": [{"player_id": "bd13e8b0-REDACTED", "value": 22}]},
          {"stat_name": "BF",  "stats": [{"player_id": "bd13e8b0-REDACTED", "value": 14}]}
        ],
        "stats": [
          {
            "player_id": "bd23c497-REDACTED",
            "player_text": "(L)",
            "stats": {"IP": 1, "H": 2, "R": 5, "ER": 5, "BB": 2, "SO": 1}
          },
          {
            "player_id": "bd13e8b0-REDACTED",
            "player_text": "",
            "stats": {"IP": 2, "H": 4, "R": 6, "ER": 0, "BB": 2, "SO": 1}
          }
        ]
      }
    ]
  },
  "16d38cf9-4f73-438c-83e4-1c28fbb23628": {
    "players": [
      {"id": "84a895b4-REDACTED", "first_name": "Max", "last_name": "Yager", "number": "27"}
    ],
    "groups": [
      {
        "category": "lineup",
        "team_stats": {"AB": 24, "R": 13, "H": 7, "RBI": 9, "BB": 7, "SO": 2},
        "extra": [
          {"stat_name": "2B", "stats": [{"player_id": "84a895b4-REDACTED", "value": 1}]},
          {"stat_name": "SB", "stats": [{"player_id": "8e5a6638-REDACTED", "value": 1}]},
          {"stat_name": "CS", "stats": [{"player_id": "9e3b717f-REDACTED", "value": 1}]}
        ],
        "stats": [
          {
            "player_id": "9e3b717f-REDACTED",
            "player_text": "(CF)",
            "is_primary": true,
            "stats": {"AB": 2, "R": 1, "H": 0, "RBI": 1, "BB": 2, "SO": 0}
          }
        ]
      },
      {
        "category": "pitching",
        "team_stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 4, "SO": 8},
        "extra": [
          {"stat_name": "#P", "stats": [{"player_id": "b0bf1bcb-REDACTED", "value": 62}]},
          {"stat_name": "BF", "stats": [{"player_id": "b0bf1bcb-REDACTED", "value": 13}]}
        ],
        "stats": [
          {
            "player_id": "b0bf1bcb-REDACTED",
            "player_text": "",
            "stats": {"IP": 3, "H": 1, "R": 0, "ER": 0, "BB": 3, "SO": 7}
          }
        ]
      }
    ]
  }
}
```

#### Comparison: Boxscore vs. Per-Player Stats Endpoint

| Dimension | `GET /game-stream-processing/{id}/boxscore` | `GET /teams/{id}/players/{pid}/stats` |
|-----------|---------------------------------------------|---------------------------------------|
| Scope | One game, both teams | One player, all games (season) |
| Player names | Included in response (`players` array) | Not included -- UUID only |
| Batting stats | AB, R, H, RBI, BB, SO + sparse extras | Comprehensive (25+ batting fields per game) |
| Pitching stats | IP, H, R, ER, BB, SO + #P, TS, BF, WP, HBP | Not available in this endpoint |
| Spray charts | Not available | Available (56/80 games in sample) |
| Cumulative stats | Not available | Rolling cumulative totals per game |
| Position data | `player_text` field (parseable string) | Not available |
| Batting order | Implicit (list order = batting order) | Not available |
| Both teams | Yes -- home AND away box score in one call | Only the player's own team |
| Auth required | Yes | Yes |
| Pagination | Not observed (single object response) | Not observed (single-page array) |

**Use boxscore for:** Game-level scouting (opponent lineup, pitcher sequencing, errors), real-time-style game reconstruction, any use case requiring both teams' data in one call.

**Use per-player stats for:** Season trend analysis, spray chart / batted ball data, comprehensive counting stats beyond the box score core six.

#### Known Limitations

- **Own team key is public_id slug, opponent key is UUID** -- code must detect key format (alphanumeric slug vs. UUID) to identify which team is which. The slug matches `public_id` in `/me/teams`.
- **Batting stats limited to core six** -- main `stats` dict has only AB, R, H, RBI, BB, SO. Advanced stats (2B, 3B, HR, OBP, SLG) require reconstructing from the `extra` sparse array. Players with zero doubles will not appear in the 2B extra list at all.
- **IP is integer innings** -- fractional innings (e.g., 2.1 innings) may be rounded or expressed as whole numbers. Confirm with more samples. In this capture, all IP values are whole integers.
- **`players` array is full roster context, not just the lineup** -- the `players` list includes all rostered players, not just those who played. Cross-reference `player_id` in `stats` to identify who actually appeared.
- **Batting order is positional in the array** -- lineup order follows the batting order (starters listed first, subs after `is_primary: false`). The API does not expose an explicit batting order integer field.
- **No inning-by-inning scoring** -- runs by inning are not in this response. Use the PUBLIC endpoint `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` (same `game_stream_id`, no auth required) to get the per-inning `scores` array and R/H/E `totals`. These two endpoints are complementary: this one provides player-level stats; the public details endpoint provides the line score.
- **`game_stream_id` not available from schedule** -- must use game-summaries to get `game_stream.id`. Two-step data pipeline required (game-summaries -> boxscore).
- **Single game confirmed** -- this is a single-game response. No evidence of batch boxscore retrieval. One call per game.
- **gc-user-action absent from this capture** -- may be optional. Consistent with `/players` and `/associations` captures. Recommend omitting for now.

**Discovered:** 2026-03-04.

---

### GET /game-stream-processing/{game_stream_id}/plays

**Status:** CONFIRMED LIVE -- 200 OK, 58 play records from a 6-inning game. Discovered 2026-03-04.

Returns a pitch-by-pitch play log for a completed game. Each record represents one at-bat plate appearance, containing pitch sequence (`at_plate_details`), play outcome narration (`final_details`), inning/half context, running score, and out count. Player identities are rendered as UUID references embedded in `${uuid}` template strings; the `team_players` roster dictionary (keyed by team identifier) is included in the response and must be used to resolve UUIDs to player names.

This endpoint provides the most granular game narrative data available: every pitch, every stolen base attempt, every balk, every lineup change, every baserunner advancement -- all tied to the specific at-bat in which the event occurred.

```
GET https://api.team-manager.gc.com/game-stream-processing/{game_stream_id}/plays
```

#### Critical ID Mapping

Same ID as the boxscore endpoint: use `game_stream.id` from game-summaries -- NOT `event_id` or `game_stream.game_id`.

| ID source | Field name | Use for |
|-----------|-----------|---------|
| `/teams/{id}/game-summaries` | `game_stream.id` | Path parameter for this endpoint |

#### Path Parameters

| Parameter        | Type | Description |
|------------------|------|-------------|
| `game_stream_id` | UUID | The `game_stream.id` value from a game-summaries record. Same UUID as used in `/game-stream-processing/{id}/boxscore`. |

#### Query Parameters

None observed.

#### Headers

No `gc-user-action` or `gc-user-action-id` headers were present in this capture (consistent with boxscore, `/players`, and `/associations`).

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.event_plays+json; version=0.0.0
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
```

#### Response Schema

The response is a **JSON object** with three top-level keys:

| Field          | Type   | Description |
|----------------|--------|-------------|
| `sport`        | string | Always `"baseball"` in this sample. |
| `team_players` | object | Roster dictionary. Keys are team identifiers (same asymmetric format as boxscore: own team uses public_id slug, opponent uses UUID). Values are arrays of player objects used to resolve UUID references in play templates. |
| `plays`        | array  | Ordered array of play objects. One entry per plate appearance / significant event. Length = total plate appearances in the game (58 for a 6-inning game in this sample). |

**`team_players` value (player object):**

| Field        | Type   | Description |
|--------------|--------|-------------|
| `id`         | UUID   | Player UUID. Matches UUIDs embedded in template strings. |
| `first_name` | string | Player first name. |
| `last_name`  | string | Player last name. |
| `number`     | string | Jersey number (string, not int). |

**Observed `team_players` key formats (same asymmetric pattern as boxscore):**
- Own team key: public_id slug (e.g., `"y24fFdnr3RAN"`)
- Opponent key: UUID (e.g., `"16d38cf9-4f73-438c-83e4-1c28fbb23628"`)

**Play object fields:**

| Field              | Type    | Description |
|--------------------|---------|-------------|
| `order`            | int     | Zero-based index of this play within the game. Plays are delivered in game order. |
| `inning`           | int     | Inning number (1-based). |
| `half`             | string  | `"top"` or `"bottom"` -- which half-inning. |
| `name_template`    | object  | Short outcome label for the play (e.g., `{"template": "Single"}`). May contain a `${uuid}` reference when the play is an ongoing at-bat entry (see note below). |
| `home_score`       | int     | Home team score **after** this play resolves. |
| `away_score`       | int     | Away team score **after** this play resolves. |
| `did_score_change` | boolean | `true` if one or more runs scored during this at-bat. |
| `outs`             | int     | Total outs in the current half-inning **after** this play resolves (0–3). |
| `did_outs_change`  | boolean | `true` if this play resulted in one or more additional outs. |
| `at_plate_details` | array   | Pitch-by-pitch narrative for the at-bat. Each element is `{"template": "<string>"}`. May contain `${uuid}` player references. |
| `final_details`    | array   | Outcome narration for the play. Each element is `{"template": "<string>"}`. Contains `${uuid}` player references. Empty for ongoing at-bats. |
| `messages`         | array   | Additional messages. All 58 records in this sample had empty arrays (`[]`). Purpose unknown. |

**Note on `name_template` with UUID reference:** The last play in this sample (`order: 57`) had a `name_template.template` value of `"${ec74bea0-fbc2-480a-aea6-0f26e9a11bed} at bat"` with empty `final_details`. This appears to represent an at-bat that was in progress when the game ended (game-ending walk-off or final batter with the game decided). Only 1 of 58 plays had this pattern.

#### Template String System

Player identities are encoded as `${<uuid>}` placeholders in all `template` string values. These UUIDs correspond to `id` values in the `team_players` dictionary. At render time, replace each `${uuid}` with the matching player's name from `team_players`.

**UUID reference resolution example:**

```
template: "${BATTER_UUID} flies out to shortstop ${FIELDER_UUID}"
```

Resolved by looking up `BATTER_UUID` and `FIELDER_UUID` in `team_players` across both team arrays.

**Important:** A single UUID may belong to either team. Resolution requires searching both team arrays in `team_players`.

#### Observed `at_plate_details` Template Patterns

These are the distinct template types seen in the `at_plate_details` array (58 plays, 1 game):

| Template pattern | Notes |
|-----------------|-------|
| `"Ball 1"`, `"Ball 2"`, `"Ball 3"`, `"Ball 4"` | Individual ball calls |
| `"Strike 1 looking"`, `"Strike 1 swinging"` | Strike calls (both called and swinging; observed through Strike 3) |
| `"Foul"` | Foul ball (not split by count) |
| `"In play"` | Ball put in play; outcome described in `final_details` |
| `"Pickoff attempt at 1st"`, `"Pickoff attempt at 2nd"` | Pickoff throw (result not specified) |
| `"${uuid} steals 2nd"` | Stolen base mid-at-bat |
| `"${uuid} scores on wild pitch"` | Runner scores; wild pitch credited mid-at-bat |
| `"${uuid} advances to 2nd on the same pitch"`, `"${uuid} advances to 3rd on the same pitch"` | Runner advancement on wild pitch / passed ball |
| `"${uuid} advances to 3rd on wild pitch"` | Runner advancement |
| `"${uuid} caught stealing 3rd, third baseman ${uuid}"` | Caught stealing (position player credited) |
| `"${uuid} scores"` | Runner scores mid-at-bat (before final_details) |
| `"Courtesy runner ${uuid} in for ${uuid}"` | Courtesy runner substitution |
| `"Lineup changed: ${uuid} in at pitcher"` | Mid-game pitching change |
| `"Lineup changed: ${uuid} in for batter ${uuid}"` | Pinch hitter |
| `"Lineup changed: Pinch runner ${uuid} in for designated hitter ${uuid}"` | Pinch runner |
| `"Balk by pitcher ${uuid}"` | Balk (pitcher identified) |

#### Observed `final_details` Template Patterns

Selected representative patterns from `final_details` (58 plays, 1 game):

| Template pattern | Notes |
|-----------------|-------|
| `"${uuid} singles on a [contact type] to [fielder position] ${uuid}"` | Single; contact type varies (fly ball, ground ball, line drive, hard ground ball, bunt) |
| `"${uuid} doubles on a [contact type] to [fielder position] ${uuid}"` | Double |
| `"${uuid} flies out to [fielder position] ${uuid}"` | Fly out |
| `"${uuid} grounds out to [fielder position] ${uuid}"` | Ground out |
| `"${uuid} lines out to [fielder position] ${uuid}"` | Line out |
| `"${uuid} pops out to [fielder position] ${uuid}"` | Pop out |
| `"${uuid} bunts out to pitcher ${uuid}"` | Bunt out |
| `"${uuid} grounds into fielder's choice to [fielder position] ${uuid}"` | Fielder's choice |
| `"${uuid} hits a [quality] ground ball and reaches on an error by [position] ${uuid}"` | Reached on error; quality may be absent or "hard" |
| `"${uuid} strikes out [looking\|swinging], ${uuid} pitching"` | Strikeout; pitcher identified |
| `"${uuid} walks, ${uuid} pitching"` | Walk; pitcher identified |
| `"${uuid} is hit by pitch, ${uuid} pitching"` | HBP; pitcher identified |
| `"${uuid} scores"` | Runner scores as a consequence of this play |
| `"${uuid} advances to [2nd\|3rd]"` | Runner advancement |
| `"${uuid} advances to [2nd\|3rd] on the same error"` | Advancement on the same error play |
| `"${uuid} advances to 2nd on the throw"` | Advancement on throw |
| `"${uuid} advances to 3rd on error by third baseman ${uuid}"` | Advancement on error |
| `"${uuid} remains at [1st\|2nd\|3rd]"` | Runner did not advance |
| `"${uuid} out advancing to 2nd"` | Runner thrown out |
| `"${uuid} scores on error by [position] ${uuid}"` | Run scored on an error |
| `"Half-inning ended by out on the base paths"` | Runner Out play type -- half inning ends |
| `"${uuid} singles on a bunt, pitcher ${uuid} to first baseman ${uuid}"` | Bunt single with fielder sequence |

#### Observed `name_template` Play Type Values

All `name_template.template` values observed in this 58-play game sample:

| Value | Description |
|-------|-------------|
| `"Single"` | Base hit (single) |
| `"Double"` | Base hit (double) |
| `"Error"` | Reached on error |
| `"Fly Out"` | Fly out |
| `"Ground Out"` | Ground out |
| `"Line Out"` | Line out |
| `"Pop Out"` | Pop out |
| `"Strikeout"` | Strikeout (looking or swinging) |
| `"Walk"` | Base on balls |
| `"Hit By Pitch"` | HBP |
| `"Fielder's Choice"` | Fielder's choice |
| `"Runner Out"` | Out recorded on the base paths (not a batted ball out) |
| `"${uuid} at bat"` | Ongoing/unresolved at-bat (observed once -- final at-bat of game) |

Play type counts from this 58-play sample: Walk (11), Strikeout (10), Ground Out (7), Single (6), Fly Out (5), Error (5), Line Out (5), Double (4), HBP (1), Fielder's Choice (1), Pop Out (1), Runner Out (1), ongoing at-bat (1).

#### Example Response (redacted)

```json
{
  "team_players": {
    "y24fFdnr3RAN": [
      {"id": "06fd1556-REDACTED", "first_name": "Ashton", "last_name": "Tucker", "number": "7"},
      {"id": "7a2e8eff-REDACTED", "first_name": "Camden", "last_name": "Ledgerwood", "number": "2"}
    ],
    "16d38cf9-REDACTED": [
      {"id": "84a895b4-REDACTED", "first_name": "Max", "last_name": "Yager", "number": "27"}
    ]
  },
  "sport": "baseball",
  "plays": [
    {
      "order": 0,
      "inning": 1,
      "half": "top",
      "name_template": {"template": "Fly Out"},
      "home_score": 0,
      "away_score": 0,
      "did_score_change": false,
      "outs": 1,
      "did_outs_change": true,
      "at_plate_details": [
        {"template": "Ball 1"},
        {"template": "Foul"},
        {"template": "Ball 2"},
        {"template": "Ball 3"},
        {"template": "Foul"},
        {"template": "In play"}
      ],
      "final_details": [
        {"template": "${9e3b717f-REDACTED} flies out to shortstop ${2a19938e-REDACTED}"}
      ],
      "messages": []
    },
    {
      "order": 7,
      "inning": 1,
      "half": "bottom",
      "name_template": {"template": "Ground Out"},
      "home_score": 1,
      "away_score": 0,
      "did_score_change": true,
      "outs": 2,
      "did_outs_change": true,
      "at_plate_details": [
        {"template": "Courtesy runner ${4d14da48-REDACTED} in for ${6f4a5e91-REDACTED}"},
        {"template": "Pickoff attempt at 1st"},
        {"template": "Strike 1 looking"},
        {"template": "Foul"},
        {"template": "Ball 1"},
        {"template": "${4d14da48-REDACTED} steals 2nd"},
        {"template": "Foul"},
        {"template": "Ball 2"},
        {"template": "In play"}
      ],
      "final_details": [
        {"template": "${8e04e7ff-REDACTED} grounds out to second baseman ${c58c0e4d-REDACTED}"},
        {"template": "${bd13e8b0-REDACTED} scores"},
        {"template": "${4d14da48-REDACTED} advances to 3rd"}
      ],
      "messages": []
    }
  ]
}
```

#### Relationship to Other Game-Level Endpoints

| Dimension | `/game-stream-processing/{id}/plays` (this endpoint) | `/game-stream-processing/{id}/boxscore` | `/public/game-stream-processing/{id}/details` |
|-----------|------------------------------------------------------|------------------------------------------|-----------------------------------------------|
| **Auth required** | Yes | Yes | No |
| **Granularity** | Per-pitch (at_plate_details) + per-play outcome | Per-player batting/pitching line | Game metadata + inning-by-inning line score |
| **Pitch sequence** | Yes (Ball/Strike/Foul/In play per pitch) | No | No |
| **Batting outcomes** | Yes (play result narration in templates) | Yes (AB, R, H, RBI, BB, SO per player) | No |
| **Baserunner events** | Yes (SB, WP, balk, advancement in templates) | Partial (SB, CS in extras) | No |
| **Lineup changes** | Yes (substitutions in at_plate_details) | Yes (is_primary flag) | No |
| **Line score (per-inning runs)** | Computable from `home_score`/`away_score` deltas | No | Yes (line_score.scores array) |
| **Player names** | Via `team_players` dictionary (included in response) | Via `players` array (included in response) | No (no player data) |
| **Score after each play** | Yes (home_score, away_score per play) | No | Final score only |
| **Fielder identity on outs** | Yes (embedded in final_details template) | No | No |
| **Pitcher identity on K/BB/HBP** | Yes (embedded in final_details template) | Via groups[pitching] | No |
| **URL parameter** | Same `game_stream.id` | Same `game_stream.id` | Same `game_stream.id` |

**Coaching use cases for this endpoint:**
- **Pitch-by-pitch sequence reconstruction**: Identify specific at-bats by batter UUID, then read the full pitch count and contact type
- **Stolen base and baserunning analysis**: All SB, CS, WP, balk, and advancement events are explicit in templates
- **Pitcher effectiveness by at-bat**: Combine `name_template` outcome with the pitch sequence in `at_plate_details` to compute strikeout rates, walks per inning, counts reached
- **Lineup change tracking**: All substitutions (courtesy runners, pinch hitters, pitching changes) appear in-sequence within the relevant at-bat
- **Contact quality by type**: Hit descriptions include contact quality (`"hard ground ball"`, `"line drive"`, `"fly ball"`, `"bunt"`) and fielder position -- richer than boxscore

#### Known Limitations

- **Template strings require UUID resolution** -- every player reference is a `${uuid}` token. All rendering requires looking up the UUID in `team_players`. No player names appear directly in play templates; the `team_players` dict is the only name source in this response.
- **Same asymmetric key format as boxscore** -- `team_players` keys use public_id slug for own team and UUID for opponent (same pattern as boxscore). Code must detect key format to identify which team is which.
- **No explicit batter/pitcher assignment per play** -- the play record does not have dedicated `batter_id` or `pitcher_id` fields. The batter is identified from the first `final_details` template (first UUID mentioned is typically the batter). The pitcher is embedded in strikeout/walk/HBP templates (`"${uuid} strikes out ..., ${uuid} pitching"`).
- **Score fields are cumulative after the play** -- `home_score` and `away_score` reflect the score **after** the play, not the change. To derive runs scored in this at-bat, compare to the previous play's scores or use `did_score_change`.
- **No explicit batting order integer** -- batters appear in at-bat sequence order; no explicit batting order position field. Batting order must be inferred from sequence (same as boxscore).
- **`messages` array purpose unknown** -- all 58 records have `[]`. Unclear what content would appear here.
- **Ongoing at-bat at game end** -- when a game ends mid-at-bat (e.g., walk-off scoring mid-pitch), the final record may have a UUID-based `name_template` and empty `final_details`. Handle this gracefully.
- **Contact quality not consistently present** -- hit descriptions sometimes include quality descriptors ("hard ground ball", "line drive") and sometimes just the fielder. Do not assume all hits have a quality descriptor.
- **Single game confirmed** -- schema from one game (game_stream_id `7ba971c1-7e42-46bf-8b0e-662b42524190`, 6-inning game vs. Elkhorn North, 2025-03-21). Play type distribution and `messages` content may vary for other game types (extra innings, weather shortening, DH format).
- **Response size** -- 37 KB for a 6-inning game (58 plays). Longer games (9 innings, 90+ plays) will be proportionally larger.
- **No `gc-user-action` header observed** -- consistent with boxscore, `/players`, and `/associations`. Recommend omitting.

**Discovered:** 2026-03-04.

---

### GET /public/game-stream-processing/{game_stream_id}/details

**Status:** CONFIRMED LIVE -- 200 OK, single game details object with inning-by-inning line score. Discovered 2026-03-04.

**AUTHENTICATION: NOT REQUIRED.** No `gc-token` or `gc-device-id` headers needed.

Returns public game details for a completed game, including metadata (opponent name, start/end times, home/away, final score, game status) and the `line_score` object with per-inning runs for both teams plus totals (Runs, Hits, Errors). This endpoint is publicly accessible using the same `game_stream_id` UUID used by the authenticated `GET /game-stream-processing/{game_stream_id}/boxscore` endpoint.

**Critical ID note:** The path parameter is `game_stream.id` from game-summaries (same ID as the authenticated boxscore endpoint), NOT the schedule `event_id`. Use `GET /teams/{team_id}/game-summaries` to obtain this ID.

```
GET https://api.team-manager.gc.com/public/game-stream-processing/{game_stream_id}/details?include=line_scores
```

#### Path Parameters

| Parameter        | Type | Description |
|------------------|------|-------------|
| `game_stream_id` | UUID | The `game_stream.id` value from a game-summaries record. NOT `event_id` or `game_stream.game_id`. Same UUID used by authenticated `/game-stream-processing/{id}/boxscore`. |

#### Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `include` | Conditional | `line_scores` -- triggers inclusion of the `line_score` object (inning-by-inning runs and totals). Without this parameter, line score data may be absent. **Always include `include=line_scores` to get inning data.** |

#### Headers

No `gc-token`, `gc-device-id`, or `gc-user-action` headers are needed or expected. Standard browser headers are sufficient.

```
gc-app-name: web
Accept: application/vnd.gc.com.public_team_schedule_event_details+json; version=0.0.0
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
```

#### Response Schema

A single JSON object (not an array). 12 top-level fields observed.

| Field                  | Type    | Nullable | Description |
|------------------------|---------|----------|-------------|
| `id`                   | UUID    | No       | The `game_stream_id` -- matches the path parameter and `game_stream.id` in game-summaries. |
| `opponent_team`        | object  | No       | Opponent identity object. Contains `name` (string). In this sample only `name` was present; other samples may include `avatar_url` (as seen in `/public/teams/{public_id}/games`). |
| `opponent_team.name`   | string  | No       | Opponent team display name (e.g., `"Elkhorn North"`). |
| `is_full_day`          | boolean | No       | Whether this is an all-day event. `false` for timed games. |
| `start_ts`             | string  | No       | Game start timestamp in ISO 8601 UTC (e.g., `"2025-03-21T23:30:00.000Z"`). |
| `end_ts`               | string  | No       | Game end timestamp in ISO 8601 UTC. |
| `timezone`             | string  | No       | IANA timezone string for local time display (e.g., `"America/Chicago"`). |
| `home_away`            | string  | No       | `"home"` or `"away"` -- perspective of the team whose `game_stream_id` was used. |
| `score`                | object  | No       | Final score: `{"team": int, "opponent_team": int}`. Matches `line_score.*.totals[0]`. |
| `game_status`          | string  | No       | `"completed"` in this sample. Other values unknown (`"in_progress"`, `"scheduled"` expected). |
| `has_videos_available` | boolean | No       | Whether video recordings exist for this game. |
| `has_live_stream`      | boolean | No       | Whether a live stream is/was available. |
| `line_score`           | object  | No       | Per-inning scoring object (present when `include=line_scores` sent). See below. |

**`line_score` object:**

The `line_score` object has two keys: `"team"` and `"opponent_team"`, each with the same shape.

| Field     | Type           | Description |
|-----------|----------------|-------------|
| `scores`  | array of int   | Runs scored per inning, in order. Length equals number of innings played (e.g., `[2,0,0,0,0]` = 5 innings). Length varies per game. |
| `totals`  | array of int   | Three-element array: `[Runs, Hits, Errors]`. Standard box score line summary. Confirmed by cross-referencing with authenticated boxscore response for same game. |

**`totals` array interpretation:**

| Index | Meaning | Sample: team | Sample: opponent |
|-------|---------|-------------|-----------------|
| `[0]` | Runs (R) | `2` | `13` |
| `[1]` | Hits (H) | `3` | `7` |
| `[2]` | Errors (E) | `4` | `3` |

**Cross-reference verification (same `game_stream_id` = `7ba971c1-7e42-46bf-8b0e-662b42524190`):**

The authenticated boxscore for this game showed `team_stats: {R:2, H:3}` and `opponent team_stats: {R:13, H:7}`. The public details `totals` match: `[2,3,4]` and `[13,7,3]`. This confirms the `totals` array is `[R, H, E]`.

#### Example Response

```json
{
  "id": "7ba971c1-7e42-46bf-8b0e-662b42524190",
  "opponent_team": {"name": "Elkhorn North"},
  "is_full_day": false,
  "start_ts": "2025-03-21T23:30:00.000Z",
  "end_ts": "2025-03-22T00:30:00.000Z",
  "timezone": "America/Chicago",
  "home_away": "home",
  "score": {"team": 2, "opponent_team": 13},
  "game_status": "completed",
  "has_videos_available": true,
  "has_live_stream": false,
  "line_score": {
    "team":          {"scores": [2, 0, 0, 0, 0], "totals": [2, 3, 4]},
    "opponent_team": {"scores": [0,11, 0, 2, 0], "totals": [13, 7, 3]}
  }
}
```

*(No credentials in this response -- safe to store as-is.)*

#### Relationship to Authenticated Boxscore Endpoint

| Dimension | `GET /public/game-stream-processing/{id}/details` (this endpoint) | `GET /game-stream-processing/{id}/boxscore` (authenticated) |
|-----------|-------------------------------------------------------------------|-------------------------------------------------------------|
| **Auth required** | No | Yes (`gc-token`, `gc-device-id`) |
| **Line score (inning-by-inning)** | Yes -- `line_score.*.scores` array | No -- not in boxscore response |
| **R/H/E totals** | Yes -- `line_score.*.totals` | Computable from `team_stats` (R, H) + sparse `extra` E |
| **Per-player batting lines** | No | Yes -- `groups[lineup].stats` per player |
| **Per-pitcher lines** | No | Yes -- `groups[pitching].stats` per pitcher |
| **Batting order** | No | Yes (implicit -- list order) |
| **Player names** | No | Yes -- `players` array |
| **URL parameter** | Same `game_stream.id` | Same `game_stream.id` |
| **Game metadata** | Full (opponent name, start/end time, home/away, score, game_status, videos) | None (only stat data) |

**Complementary use case:** Call this endpoint for inning-by-inning context (comeback patterns, late-inning scoring) and the authenticated boxscore for per-player batting/pitching breakdown. Both use the same `game_stream_id`.

#### Comparison to /public/teams/{public_id}/games

Both endpoints return public game data without authentication, but from different perspectives:

| Dimension | `/public/game-stream-processing/{id}/details` | `/public/teams/{public_id}/games` |
|-----------|----------------------------------------------|-----------------------------------|
| **Identifier required** | `game_stream_id` (from game-summaries) | Team `public_id` slug |
| **Scope** | Single game | All completed games for team (32 observed) |
| **Line scores** | Yes (with `include=line_scores`) | No |
| **Hits + Errors** | Yes (in `totals`) | No |
| **Game metadata overlap** | `id`, `opponent_team`, `start_ts`, `end_ts`, `is_full_day`, `timezone`, `home_away`, `score`, `game_status`, `has_videos_available`, `has_live_stream` | Same fields (id/start_ts/end_ts/timezone/home_away/score/game_status/has_videos_available/has_live_stream) |
| **Auth required** | No | No |

#### Known Limitations

- **`include=line_scores` required for line score data** -- without this parameter the `line_score` field may be absent. Always include this query param when inning data is needed.
- **Game identity is `game_stream_id`, not `event_id`** -- the `id` field returned matches the URL param (`game_stream.id`), which differs from the schedule `event_id`. Cross-reference the authenticated game-summaries to resolve both IDs.
- **`totals` indexing is positional** -- the `totals` array has no field labels. Order is confirmed as `[R, H, E]` from one sample. This must be validated against additional game samples.
- **`scores` array length varies** -- one inning per element; extra innings and shortened games will produce different lengths. A 7-inning game will have 7+ elements if extra innings were played.
- **`opponent_team` object may be minimal** -- this sample contained only `name`. Other public endpoints include `avatar_url`; whether it appears here is unconfirmed.
- **`game_status` values incomplete** -- only `"completed"` observed. Behavior for in-progress or future games is unknown.
- **No player-level data** -- scores and metadata only. No batting or pitching lines.
- **Single game confirmed** -- schema validated from one game (`7ba971c1-7e42-46bf-8b0e-662b42524190`). Cross-game variance in `line_score` structure (e.g., extra innings, mercy rule) not yet observed.
- **No pagination** -- single-object response; pagination not applicable.

**Discovered:** 2026-03-04.

---

### GET /events/{event_id}/best-game-stream-id

**Status:** CONFIRMED LIVE -- 200 OK, single-field JSON object. Discovered 2026-03-04.

Resolves an event UUID (from the schedule endpoint) to the canonical `game_stream_id` UUID required by the boxscore and plays endpoints. This is the **bridge endpoint** between the schedule/game-summaries world and the game-stream-processing world.

```
GET https://api.team-manager.gc.com/events/{event_id}/best-game-stream-id
```

#### Path Parameters

| Parameter  | Type   | Description                                                                 |
|------------|--------|-----------------------------------------------------------------------------|
| `event_id` | UUID   | The event UUID. Confirmed source: the `id` field from `GET /teams/{team_id}/schedule` event objects. |

#### Query Parameters

None observed.

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.game_stream_id+json; version=0.0.2
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
```

**Note on gc-user-action:** No `gc-user-action` or `gc-user-action-id` headers were present in this capture.

#### Response Schema

```json
{
  "game_stream_id": "<UUID>"
}
```

| Field           | Type   | Description                                                                |
|-----------------|--------|----------------------------------------------------------------------------|
| `game_stream_id` | string (UUID) | The canonical game stream identifier. Use this value as the `{game_stream_id}` path parameter in `GET /game-stream-processing/{game_stream_id}/boxscore` and `GET /game-stream-processing/{game_stream_id}/plays`. |

#### Example Response (redacted -- no PII in this endpoint)

```json
{"game_stream_id":"ff5096e0-3d4c-4543-947e-df2898de2f65"}
```

The `event_id` used was `7ba971c1-7e42-46bf-8b0e-662b42524190` (from a completed LSB game in the schedule).

#### ID Chain -- Critical Routing Context

This endpoint is the **missing link** in the ID chain from schedule to box score:

```
GET /teams/{team_id}/schedule
  -> event.id (event_id UUID)
      -> GET /events/{event_id}/best-game-stream-id
          -> game_stream_id UUID
              -> GET /game-stream-processing/{game_stream_id}/boxscore
              -> GET /game-stream-processing/{game_stream_id}/plays
              -> GET /public/game-stream-processing/{game_stream_id}/details
```

**Previously documented (MEMORY.md):** The game-summaries endpoint (`GET /teams/{team_id}/game-summaries`) also exposes `game_stream.id` directly, which sidesteps the need for this endpoint when iterating over game-summaries records. However, if you have a schedule `event_id` and do not want to paginate through game-summaries, this endpoint resolves the ID in a single call.

**Accept header note:** The version is `0.0.2` (not `0.0.0` like many other endpoints). This is the exact value confirmed from the browser capture -- use it precisely.

#### Known Limitations

- **Single sample** -- confirmed from one game (`event_id: 7ba971c1-7e42-46bf-8b0e-662b42524190`). Behavior for future/scheduled games or cancelled games is unknown -- may return 404 or a different error.
- **Only "best" stream** -- the endpoint name implies there may be multiple game streams per event; this returns the canonical (best) one. Multi-stream behavior is undocumented.
- **No public variant observed** -- all confirmed game_stream_id lookups have gone through authenticated paths or via `game_stream.id` in game-summaries. An unauthenticated `/public/events/{event_id}/best-game-stream-id` has not been tested.
- **Version 0.0.2** -- this Accept header version is higher than most `0.0.0` endpoints, suggesting this endpoint may have been updated at some point. Schema differences between versions are unknown.

**Discovered:** 2026-03-04.

---

### GET /teams/{team_id}/users

**Status:** CONFIRMED LIVE -- 200 OK. Page 2 (start_at=100) returned 33 records. Discovered 2026-03-04.

**PII WARNING:** This endpoint returns real user names, email addresses, and UUIDs. All stored samples must be fully redacted. Never log, display, or commit actual values.

Returns the user roster for a team -- the list of GameChanger accounts associated with that team (parents, coaches, players, fans). Each record is a flat user object with identity and account status fields. No role or association type is returned per record; this endpoint does not indicate whether a user is a coach, player, or family member.

The team UUID in the confirmed capture (`cb67372e-b75d-472d-83e3-4d39b6d85eb2`) is a different team than the primary LSB or Lincoln Rebels team UUIDs. This team has at least 133 associated users (100+ on page 1, 33 on page 2).

```
GET https://api.team-manager.gc.com/teams/{team_id}/users
GET https://api.team-manager.gc.com/teams/{team_id}/users?start_at={cursor}
```

#### Path Parameters

| Parameter  | Description          |
|------------|----------------------|
| `team_id`  | Team UUID            |

#### Query Parameters

| Parameter  | Required | Description |
|------------|----------|-------------|
| `start_at` | No       | Pagination cursor (integer). Omit for first page. Obtain from `x-next-page` response header. Page 2 confirmed with `start_at=100`. |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_user:list+json; version=0.0.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
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
gc-user-action: data_loading:team
gc-user-action-id: {UUID}
```

**Note on gc-user-action:** Value `data_loading:team` observed -- same as `GET /teams/{team_id}` (team detail endpoint). Suggests both are considered "team loading" actions in GameChanger's telemetry.

**Note on x-pagination:** Sent in this capture. The `x-next-page` response header behavior is confirmed for page 2 (captured with `start_at=100`). Page 1 would use no `start_at` parameter.

#### Response Schema

A **bare JSON array** of user objects. No wrapper. 33 records on page 2 (start_at=100). Page 1 is presumed to contain 100 records based on the cursor value, giving ~133 total users on this team.

Each user object has 5 fields:

| Field        | Type            | Nullable | Description |
|--------------|-----------------|----------|-------------|
| `id`         | string (UUID)   | No       | User UUID. Stable identifier for this GameChanger account. **PII -- redact in all stored files.** |
| `status`     | string          | No       | Account status. Two values observed: `"active"` (31/33 records) and `"active-confirmed"` (2/33 records). See status enum below. |
| `first_name` | string          | No       | User's first name. **PII -- redact in all stored files.** |
| `last_name`  | string          | No       | User's last name. **PII -- redact in all stored files.** |
| `email`      | string          | No       | User's email address. **PII -- redact in all stored files.** |

**No role/association field is present.** This endpoint returns who is associated with a team but not in what capacity (coach, player, parent, fan). To determine roles, use `GET /me/teams?include=user_team_associations` (for the authenticated user's own roles) or the associations endpoint.

#### Status Enum

| Value              | Description |
|--------------------|-------------|
| `"active"`         | Standard active account. The majority of users. |
| `"active-confirmed"` | Active account with email confirmation explicitly recorded. May indicate a separate confirmation step, perhaps for coaches or staff roles. |
| `"invited"` | User has been invited but has not yet accepted / set up their account. Confirmed in 2026-03-07 capture of team `72bb77d8` (Lincoln Rebels 14U). |

Other values (e.g., `"inactive"`, `"pending"`, `"removed"`) may exist but were not observed.

#### Example Response (PII fully redacted)

```json
[
  {
    "id": "REDACTED_UUID_1",
    "status": "active",
    "first_name": "REDACTED_FIRST",
    "last_name": "REDACTED_LAST",
    "email": "{REDACTED_EMAIL}"
  },
  {
    "id": "REDACTED_UUID_2",
    "status": "active-confirmed",
    "first_name": "REDACTED_FIRST",
    "last_name": "REDACTED_LAST",
    "email": "{REDACTED_EMAIL}"
  }
]
```

#### Known Limitations

- **PII-dense endpoint** -- every record contains a real name, email, and user UUID. This is among the most sensitive endpoints in the API. Raw responses must never be stored without full redaction. The sample file at `data/raw/team-users-sample.json` has all PII replaced with placeholders.
- **No role information** -- the response does not indicate whether a user is a coach, player, parent, or fan. Role information is not available from this endpoint alone. Cross-reference with `/teams/{team_id}/associations` or `/me/teams?include=user_team_associations` for role context.
- **Page 1 confirmed (2026-03-07)** -- A full (unsegmented) page-1 call to team `72bb77d8` (Lincoln Rebels 14U) returned 100 records in the bulk crawl. Combined with `/users/count` confirming 243 total users, this team requires at least 3 pages. Page-1 schema confirmed identical to page-2.
- **Multiple teams confirmed** -- originally captured from unidentified team `cb67372e`. Re-confirmed 2026-03-07 against Lincoln Rebels 14U (`72bb77d8`), 243 total users. Schema consistent across teams.
- **Total user count** -- cross-reference with `GET /teams/{team_id}/users/count` for exact totals before paginating.
- **`active-confirmed` semantics unclear** -- observed on 2 of 33 records. The distinction from `"active"` is undocumented. May relate to email verification, coach/staff confirmation, or a separate invite-acceptance flow.
- **Other status values not observed** -- values like `"invited"`, `"pending"`, `"inactive"`, `"removed"` may exist. Do not assume this enum is exhaustive from this single-page capture.
- **Response size** -- 33 records on page 2: approximately 3.5 KB. Full dataset for this team (~133 users across 2 pages) would be approximately 14 KB.

#### Coaching Relevance

Moderate. This endpoint reveals who has a GameChanger account associated with a team -- potentially useful for:
- Identifying coaching staff accounts by `status: "active-confirmed"` (tentative)
- Cross-referencing with player roster to identify non-player users (parents, coaches, fans)
- Auditing team membership size for large programs

However, without role data, the utility for directly coaching-relevant scouting is limited. The `/teams/{team_id}/season-stats`, `/teams/{team_id}/players`, and `/game-stream-processing/{id}/boxscore` endpoints are higher priority for coaching analytics.

**Discovered:** 2026-03-04.

---

### GET /teams/{team_id}/public-team-profile-id

**Status:** CONFIRMED LIVE -- 200 OK. Single-field response. Discovered 2026-03-04.

Resolves a team's internal UUID to its `public_id` slug. This is the **bridge endpoint** between the authenticated API (which identifies teams by UUID) and the public API (which identifies teams by `public_id` slug). Without this endpoint, the only way to obtain a team's `public_id` is from the `GET /me/teams` or `GET /teams/{team_id}` response -- which only covers teams the authenticated user belongs to. This endpoint makes it possible to resolve any team UUID (including opponents) to a `public_id` for use with the public endpoints.

```
GET https://api.team-manager.gc.com/teams/{team_id}/public-team-profile-id
```

#### Path Parameters

| Parameter  | Description |
|------------|-------------|
| `team_id`  | Team UUID   |

#### Query Parameters

None observed.

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_public_profile_id+json; version=0.0.0
Content-Type: application/vnd.gc.com.none+json; version=undefined
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
gc-user-action: data_loading:team
gc-user-action-id: {UUID}
```

**Note on gc-user-action:** Value `data_loading:team` -- same as `GET /teams/{team_id}` (team detail) and `GET /teams/{team_id}/users`. All three endpoints are grouped as "team loading" actions in GameChanger's telemetry.

#### Response Schema

A **single JSON object** with one field:

| Field | Type          | Nullable | Description |
|-------|---------------|----------|-------------|
| `id`  | string (slug) | No       | The team's `public_id` slug. This is the identifier used in all `/public/teams/{public_id}/...` endpoints and in `/teams/public/{public_id}/players`. Format: 12-character alphanumeric string (e.g., `"KCRUFIkaHGXI"`). |

#### Example Response

```json
{
  "id": "KCRUFIkaHGXI"
}
```

(Team UUID `cb67372e-b75d-472d-83e3-4d39b6d85eb2` maps to public_id `KCRUFIkaHGXI`. Identity of this team is not yet confirmed -- it is the same unidentified team from the `/teams/{team_id}/users` capture.)

#### Known Limitations

- **Auth required** -- `gc-token` and `gc-device-id` are present in the confirmed capture. Whether this endpoint works without authentication has not been tested.
- **Single team confirmed** -- team UUID `cb67372e-b75d-472d-83e3-4d39b6d85eb2`. Behavior for other teams (especially opponent UUIDs obtained from schedule `pregame_data.opponent_id`) has not been verified but is expected to work identically.
- **Opponent UUID behavior unverified** -- if this endpoint works for opponent team UUIDs, it would be a significant capability: resolving an opponent's UUID (from the schedule) to their `public_id`, enabling access to `/public/teams/{public_id}/games`, `/public/teams/{public_id}`, and `/public/game-stream-processing/{id}/details` without needing the opponent to be in the user's team list.
- **Response size** -- minimal (under 100 bytes). No pagination.

#### ID Chain: UUID to Public API

This endpoint completes the chain for accessing public data about any team whose UUID is known:

```
schedule pregame_data.opponent_id (UUID)
  -> GET /teams/{opponent_id}/public-team-profile-id
  -> {"id": "<public_id>"}
  -> GET /public/teams/{public_id}           (team profile, no auth)
  -> GET /public/teams/{public_id}/games     (game schedule/scores, no auth)
  -> GET /public/game-stream-processing/{game_stream_id}/details  (line scores, no auth)
```

Combined with `GET /events/{event_id}/best-game-stream-id` (authenticated), this creates a full two-track access pattern: authenticated endpoints for detailed per-player stats, public endpoints for line scores and opponent context.

#### Cross-References

| Endpoint | Uses `public_id` from this response? |
|----------|--------------------------------------|
| `GET /public/teams/{public_id}` | YES -- direct substitute |
| `GET /public/teams/{public_id}/games` | YES -- direct substitute |
| `GET /public/teams/{public_id}/games/preview` | YES -- direct substitute |
| `GET /teams/public/{public_id}/players` | YES -- URL uses `/teams/public/` prefix instead of `/public/teams/` but same `public_id` value |

#### Coaching Relevance

High. This is an enabler endpoint, not a data endpoint. Its value comes from unlocking the full public API surface for any opponent whose schedule UUID is known. Use cases:

- **Opponent scouting from public data**: Given an opponent's UUID from the schedule, resolve to `public_id`, then pull their public game history, scores, and game details without needing the opponent to be in the authenticated user's team list.
- **Roster bridging**: Combine with `/teams/public/{public_id}/players` to get opponent roster data.
- **No-credential fallback**: Once `public_id` values are resolved and cached, many follow-up data pulls can proceed without gc-token credentials (which expire hourly).

**Discovered:** 2026-03-04.

---

### POST /auth

**Status:** PARTIALLY CONFIRMED -- endpoint exists and responds. Received HTTP 400 (not 401/403) due to expired `gc-signature`/`gc-timestamp`. The gc-token JWT itself was valid. Successful response schema not yet captured. Discovered 2026-03-04.

**This is the first POST endpoint documented.** All other endpoints in this spec are GET requests. This is the token refresh flow -- used by the browser to extend the authenticated session without requiring the user to log in again.

```
POST https://api.team-manager.gc.com/auth
```

#### Request Body

```json
{"type": "refresh"}
```

| Field  | Type   | Required | Description                                    |
|--------|--------|----------|------------------------------------------------|
| `type` | string | Yes      | Refresh type. Observed value: `"refresh"`. Other values unknown. |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-client-id: {GC_CLIENT_ID}
gc-signature: {GC_SIGNATURE}
gc-timestamp: {GC_TIMESTAMP}
gc-app-name: web
gc-app-version: 0.0.0
Accept: */*
Content-Type: application/json; charset=utf-8
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
```

**Key differences from GET endpoints:**

- `Accept: */*` -- not a vendor-typed accept header (all GET endpoints use `application/vnd.gc.com.*`)
- `Content-Type: application/json; charset=utf-8` -- not the vendor-typed `application/vnd.gc.com.none+json` used by GET requests
- No `gc-user-action` or `gc-user-action-id` -- not observed in capture
- Three new headers: `gc-signature`, `gc-timestamp`, `gc-client-id` (see Signature Headers section above)
- `gc-app-version: 0.0.0` -- not observed on any GET endpoint capture

#### Path / Query Parameters

None.

#### Response Schema (successful -- NOT YET CAPTURED)

The successful response schema has not been captured -- the attempt received HTTP 400 due to a stale `gc-signature`. Based on the request structure (it sends the current gc-token and a body of `{"type":"refresh"}`), the expected response is a new gc-token JWT. Likely fields:

| Field       | Type   | Description (inferred)                          |
|-------------|--------|-------------------------------------------------|
| `token`     | string | New gc-token JWT (access or refresh)            |

> **Note:** Field name is speculative. Must be confirmed from a successful capture. The server may return additional fields (expiry, user context, etc.).

#### Error Response (HTTP 400)

When `gc-signature` is stale:

```
HTTP/2 400
Content-Type: text/plain; charset=utf-8
x-server-epoch: <current-unix-seconds>
gc-timestamp: <current-unix-seconds>

Bad Request
```

The error body is plain text `"Bad Request"` (11 bytes), not JSON.

#### gc-signature Mechanics (Inferred)

The `gc-signature` and `gc-timestamp` headers implement request signing. Observations:

- Format: `{base64-segment-1}={period}{base64-segment-2}=` (two segments joined by `.`)
- The `gc-timestamp` is the Unix timestamp when the signature was computed
- The server validates that `gc-timestamp` is within a freshness window (exact window unknown; 22,316 seconds = ~6.2 hours was rejected with 400)
- `gc-client-id` in the request matches the `cid` field in the JWT payload -- likely an input to the signature computation
- **Cannot be replicated programmatically** without knowing the signing algorithm and secret key. The browser computes this signature in JavaScript -- decompiling or capturing fresh signatures from the browser is required for programmatic refresh.

#### Implications for Programmatic Auth

**Current status:** Programmatic token refresh is NOT possible with current knowledge. The `gc-signature` requires a key and algorithm that are embedded in the browser JavaScript and are not yet known. Without the ability to compute a valid signature, the refresh endpoint cannot be called programmatically.

**Practical consequence:** Fresh `gc-token` values must continue to be obtained by capturing browser traffic. The token lifetime is 14 days (see JWT Structure section), which is much longer than the previously estimated 1 hour -- so manual rotation frequency is much lower than assumed.

**Future investigation:** The signing algorithm could potentially be reverse-engineered from the GameChanger web app JavaScript bundle. This would enable fully programmatic token refresh and eliminate the need for browser captures entirely.

#### gc-timestamp in Response Headers

The server returns its own `gc-timestamp` in every response header (observed on both 200 and 400 responses). This is the server's current Unix time. On the 400 response, the delta between request timestamp and server epoch was ~22,300 seconds (~6.2 hours), confirming the signature was stale.

#### Known Limitations

- **Successful response schema unknown** -- HTTP 400 was received before a valid response could be captured. Schema is inferred, not confirmed.
- **gc-signature cannot be computed programmatically** -- signing key and algorithm are not known. This is the primary blocker for programmatic token refresh.
- **gc-timestamp freshness window unknown** -- 22,316 seconds (6.2 hours) was rejected. The actual window may be minutes, not hours. Any fresh browser capture should be executed immediately.
- **`{"type":"refresh"}` may not be the only valid body** -- other `type` values (e.g., `"access"`) may exist but have not been tested.
- **Confirmed once (400)** -- endpoint existence confirmed, schema partially inferred. Needs re-testing with a fresh signature to confirm the success response.

#### Coaching Relevance

Low (infrastructure). This endpoint supports session longevity for data ingestion pipelines. If token refresh could be automated, ingestion runs could proceed indefinitely without manual intervention. For now, the 14-day token lifetime reduces but does not eliminate the need for periodic browser captures.

**Discovered:** 2026-03-04.

---

### GET /teams/{team_id}/schedule/events/{event_id}/player-stats

**Status: CONFIRMED LIVE (2026-03-05, HTTP 200). Both teams' players, three data sections in one call. No game_stream_id resolution needed.**

Returns per-player stats for a specific game event, identified directly by team UUID and event UUID. Returns three sections: `player_stats` (this-game per-player stats), `cumulative_player_stats` (season-to-date per-player stats for own-team players; single-game for opponent players), and `spray_chart_data` (ball-in-play x/y coordinates, play type, play result). Critically, **both own-team and opponent players are included in the same response**, keyed by player UUID throughout.

This endpoint uses the event_id from the schedule directly -- no intermediate `GET /events/{event_id}/best-game-stream-id` call is required. It also returns the `stream_id` (= `game_stream_id`) in the response body, so a single call to this endpoint provides both the per-game stats AND the stream_id needed for boxscore/plays if required.

#### Path Parameters

| Parameter  | Type   | Description |
|------------|--------|-------------|
| `team_id`  | UUID   | Team UUID (from `/me/teams` or schedule `pregame_data.opponent_id`). Must be your own team's UUID -- endpoint is scoped to teams you manage. |
| `event_id` | UUID   | Event UUID from the schedule (`GET /teams/{team_id}/schedule` event `id` field). |

#### HTTP Method

`GET`

#### Required Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {DEVICE_ID}
accept: application/json, text/plain, */*
accept-language: en-US,en;q=0.9
gc-app-name: web
origin: https://web.gc.com
referer: https://web.gc.com/
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

Note: Unlike most GameChanger endpoints, this endpoint uses `Accept: application/json, text/plain, */*` (not a vendor-typed `application/vnd.gc.com.*+json` Accept header). This was observed in the live curl capture.

#### Query Parameters

None observed. No pagination parameters observed -- the response appears to be a single object (not a paginated list).

#### Response Schema

Top-level JSON object with 6 fields:

```
{
  "stream_id": string,              // game_stream_id UUID -- same ID used in /boxscore and /plays endpoints
  "team_id": string,                // UUID -- matches the path param team_id
  "event_id": string,               // UUID -- matches the path param event_id
  "player_stats": object,           // Per-game stats for THIS specific game only
  "cumulative_player_stats": object, // Season-to-date cumulative stats (own team) or single-game (opponent)
  "spray_chart_data": object        // Ball-in-play coordinate data for this game
}
```

**`player_stats` object:**

```
{
  "stats": {                        // Team-aggregate stats for this game
    "general": { "GP": int },
    "offense": { <stat_key>: number, ... },   // ~83 offense keys for team totals
    "defense": { <stat_key>: number, ... }    // ~148 defense/pitching keys for team totals
  },
  "players": {
    "<player_uuid>": {
      "stats": {
        "general": { "GP": int },
        "offense": { <stat_key>: number, ... },  // ~80 keys, present for players who batted
        "defense": { <stat_key>: number, ... }   // ~26 keys, present for players who fielded/pitched
      }
    },
    ...
  }
}
```

Not every player has all three stat groups. Players who only batted (no fielding/pitching innings) have `offense` + `general` but no `defense`. Players who only pitched/fielded without batting have `defense` + `general` but no `offense`. Players with both roles have all three groups.

Key `player_stats.players[uuid].stats.offense` fields for this game:

| Field  | Type   | Description |
|--------|--------|-------------|
| `AB`   | int    | At-bats this game |
| `H`    | int    | Hits this game |
| `BB`   | int    | Walks this game |
| `SO`   | int    | Strikeouts this game |
| `RBI`  | int    | Runs batted in this game |
| `R`    | int    | Runs scored this game |
| `1B`   | int    | Singles |
| `2B`   | int    | Doubles |
| `3B`   | int    | Triples |
| `HR`   | int    | Home runs |
| `HBP`  | int    | Hit by pitch |
| `SB`   | int    | Stolen bases |
| `CS`   | int    | Caught stealing |
| `PA`   | int    | Plate appearances |
| `TB`   | int    | Total bases |
| `AVG`  | float  | Batting average |
| `OBP`  | float  | On-base percentage |
| `SLG`  | float  | Slugging percentage |
| `OPS`  | float  | OBP + SLG |

Key `player_stats.players[uuid].stats.defense` fields (pitchers, this game):

| Field  | Type   | Description |
|--------|--------|-------------|
| `IP`   | float  | Innings pitched (fractional thirds: 1.333 = 1 1/3 IP) |
| `ERA`  | float  | Earned run average |
| `SO`   | int    | Strikeouts |
| `BB`   | int    | Walks |
| `H`    | int    | Hits allowed |
| `ER`   | int    | Earned runs |
| `R`    | int    | Runs allowed |
| `BF`   | int    | Batters faced |
| `WP`   | int    | Wild pitches |
| `HBP`  | int    | Hit batters |
| `BK`   | int    | Balks |
| `HR`   | int    | Home runs allowed |

**`cumulative_player_stats` object:**

Same structure as `player_stats` but contains season-to-date cumulative stats. For own-team players, this reflects the full season accumulated prior to and including this game. For opponent players, `GP` = 1 and stats reflect only this game (opponents are not tracked across sessions -- their cumulative is this-game only).

Key `cumulative_player_stats.players[uuid].stats.defense` pitching fields (cumulative, ~149 keys):

| Field    | Type   | Description |
|----------|--------|-------------|
| `IP`     | float  | Cumulative innings pitched |
| `ERA`    | float  | Season ERA |
| `SO`     | int    | Season strikeouts |
| `BB`     | int    | Season walks |
| `WHIP`   | float  | Season WHIP |
| `FIP`    | float  | Fielding Independent Pitching |
| `K/BF`   | float  | Strikeout rate per batter faced |
| `K/BB`   | float  | Strikeout-to-walk ratio |
| `K/G`    | float  | Strikeouts per game (9 innings) |
| `BB/INN` | float  | Walks per inning |
| `#P`     | int    | Cumulative pitch count |
| `TS`     | int    | Total strikes thrown |
| `BF`     | int    | Total batters faced |
| `WP`     | int    | Wild pitches |
| `HBP`    | int    | Hit batters |
| `BK`     | int    | Balks |
| `ER`     | int    | Earned runs |
| `H`      | int    | Hits allowed |
| `HR`     | int    | Home runs allowed |
| `GS`     | int    | Games started |

**`spray_chart_data` object:**

```
{
  "offense": {
    "<player_uuid>": [          // Array of ball-in-play events (may be empty [])
      {
        "code": "ball_in_play", // Always "ball_in_play"
        "id": string,           // Event UUID (uppercase)
        "compactorAttributes": {
          "stream": "main"      // Always "main" in this sample
        },
        "attributes": {
          "playResult": string, // "single", "double", "triple", "home_run", "out", "error", "field_choice", ...
          "playType": string,   // "hard_ground_ball", "ground_ball", "line_drive", "fly_ball", "bunt", ...
          "defenders": [        // Array of fielders involved in the play
            {
              "error": bool,    // Whether this fielder committed an error
              "position": string, // Fielder position: "CF", "SS", "1B", "3B", "RF", "LF", "2B", "C", "P"
              "location": {
                "x": float,    // X coordinate (pixels in a field diagram coordinate system)
                "y": float     // Y coordinate
              }
            }
          ]
        },
        "createdAt": int        // Unix millisecond timestamp
      }
    ]
  },
  "defense": {
    "<player_uuid>": [          // Same structure as offense -- plays where this player was a fielder
      { ... }                   // Same fields as offense spray items
    ]
  }
}
```

In this sample: 21 players had offense spray events (total 30 events across the game), 4 players had defense spray events (total 30 events -- same 30 plays, different player perspective). The `offense` dictionary keys are batting players; the `defense` dictionary keys are fielding players involved in those same plays.

#### Distinguishing Own-Team vs. Opponent Players

There is no explicit "team" flag per player in the response. Use the `cumulative_player_stats.players[uuid].stats.general.GP` field to distinguish:

- **Own team**: `GP` = large number (60-90+ in a ~90-game travel ball season). Cumulative stats reflect the full season.
- **Opponent**: `GP` = 1. Cumulative stats reflect only this game (no cross-game tracking for opponents).

The `stream_id` returned in the response body equals the `game_stream_id` used by the boxscore and plays endpoints.

#### Example Response (Redacted)

```json
{
  "stream_id": "c05a5413-d250-4f28-bd92-efbe67bac348",
  "team_id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4",
  "event_id": "1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6",
  "cumulative_player_stats": {
    "players": {
      "<own_player_uuid>": {
        "stats": {
          "general": { "GP": 83 },
          "offense": { "AB": 160, "H": 41, "BB": 43, "SO": 37, "RBI": 35, "R": 48, "AVG": 0.25625, "OBP": 0.4251, "OPS": 0.7126, "HR": 0, "2B": 5, "3B": 0, "SB": 7, "CS": 2 },
          "defense": { "IP": 18.0, "ERA": 5.06, "SO": 19, "BB": 28, "WHIP": 2.44, "FIP": 6.28, "#P": 391, "TS": 180, "BF": 103 }
        }
      },
      "<opponent_player_uuid>": {
        "stats": {
          "general": { "GP": 1 },
          "offense": { "AB": 2, "H": 1, "BB": 0, "SO": 0 }
        }
      }
    },
    "stats": { "general": { "GP": 1 }, "offense": { "AB": 160, "H": 41 }, "defense": { "IP": 18.0 } }
  },
  "player_stats": {
    "players": {
      "<own_player_uuid>": {
        "stats": {
          "general": { "GP": 1 },
          "offense": { "AB": 1, "H": 1, "BB": 0, "SO": 0, "RBI": 0, "R": 1 },
          "defense": { "IP": 1.333, "ERA": 0.0, "SO": 3, "BB": 1 }
        }
      }
    },
    "stats": { "general": { "GP": 1 }, "offense": { "AB": 30, "H": 10 }, "defense": { "IP": 5.0 } }
  },
  "spray_chart_data": {
    "offense": {
      "<player_uuid>": [
        {
          "code": "ball_in_play",
          "id": "11E72536-DE41-43AB-A90F-56B0606BFA7C",
          "compactorAttributes": { "stream": "main" },
          "attributes": {
            "playResult": "single",
            "playType": "hard_ground_ball",
            "defenders": [{ "error": false, "position": "CF", "location": { "x": 129.06, "y": 79.08 } }]
          },
          "createdAt": 1752607496602
        }
      ]
    },
    "defense": {}
  }
}
```

#### Comparison to Boxscore Endpoint

| Dimension | `GET /teams/.../schedule/events/.../player-stats` | `GET /game-stream-processing/{game_stream_id}/boxscore` |
|-----------|---------------------------------------------------|--------------------------------------------------------|
| **ID required** | `team_id` + `event_id` (from schedule directly) | `game_stream_id` (requires prior lookup via game-summaries or best-game-stream-id) |
| **Stat richness** | ~83 offense + ~148 defense fields per player + cumulative | 6 batting + 6 pitching main stats + ~10 sparse extras |
| **Spray charts** | Yes -- x/y coordinates, play type, play result | No |
| **Cumulative season stats** | Yes -- own team players have full season totals | No -- game stats only |
| **Player names** | No -- UUID keys only. Must join to /teams/.../players or boxscore for names. | Yes -- `first_name`, `last_name`, `number` included inline |
| **Batting order** | Not preserved -- dict keyed by UUID, unordered | Yes -- array list order = batting order |
| **Position data** | No explicit position field | Yes -- `player_text` field (e.g., `"(CF)"`) |
| **Substitutes** | Not flagged | Yes -- `is_primary: false` |
| **Both teams** | Yes -- own + opponent players in same response | Yes -- home and away teams both present |
| **Response size** | ~106 KB (25 players, full season stats) | Smaller (game-only, fewer stat fields) |

**Recommendation:** Use this endpoint for full per-player stat ingestion (both game and cumulative). Use the boxscore endpoint when batting order, lineup position, or player names are required without a separate join.

#### Coaching Relevance

Very high. This is potentially the most efficient single API call for comprehensive stat ingestion:
- Per-game batting and pitching lines for every player on both teams
- Cumulative season stats for own-team players (eliminate separate season-stats call for per-player data)
- Spray chart data (ball-in-play location, type, result) for defensive positioning analysis
- Opponent player stats available in the same call, enabling in-game prep from a single request
- `stream_id` returned inline -- no separate ID resolution step needed to access plays/boxscore

#### Known Limitations

- **No player names**: Player UUIDs are the only identifier. A join to `GET /teams/{team_id}/players` or the boxscore endpoint is needed to resolve names and jersey numbers.
- **No batting order**: The `players` dict is keyed by UUID with no ordering -- use the boxscore endpoint if batting order is needed.
- **No position data**: The fielding position per player per at-bat is not present -- use the plays or boxscore endpoint for position strings.
- **Opponent cumulative stats are single-game**: Opponents' `cumulative_player_stats.GP` = 1; their season history is not available through this endpoint.
- **IP in fractional thirds**: Innings pitched is a float where 1 1/3 IP = 1.333... (not 1.1). Convert with `full_innings + (fraction * 3) / 10` for display.
- **Confirmed once (200 OK)**: Single observation. The response shape is documented from this one call. Mark as stable after 3+ independent verifications.
- **team_id scope**: The path's `team_id` must be a team the authenticated user manages. Opponent team UUIDs used as the path's `team_id` have not been tested and may return 403.
- **Accept header**: Unlike other GC endpoints, this uses `application/json, text/plain, */*` rather than a vendor-typed Accept. The vendor type for this endpoint is not yet known.

**Discovered:** 2026-03-05.

---

## Confirmed Endpoints (2026-03-07 Live Probe Session)

All endpoints in this section were confirmed via live curl calls on 2026-03-07. Where prior sections listed these as "PROXY CAPTURE" or "OBSERVED", this section upgrades their status to CONFIRMED with full schema documentation.

---

### GET /teams/{team_id}/opponent/{opponent_id}

**Status: CONFIRMED LIVE -- 200 OK. Discovered 2026-03-07.**

Returns the opponent entry record for a specific opponent within a team's opponent registry. This is the per-opponent lookup complement to `GET /teams/{team_id}/opponents` (the paginated list).

**Note on URL structure:** This endpoint uses `/opponent/` (singular), not `/opponents/` (plural). Both coexist: the plural form returns the full list, the singular form returns a specific opponent.

#### Path Parameters

| Parameter     | Type | Description |
|---------------|------|-------------|
| `team_id`     | UUID | The owning team's UUID |
| `opponent_id` | UUID | The opponent's `root_team_id` from `GET /teams/{team_id}/opponents` (NOT the `progenitor_team_id`) |

#### Response Schema

Single JSON object (not an array).

| Field                | Type    | Description |
|----------------------|---------|-------------|
| `root_team_id`       | UUID    | The local opponent registry ID (matches the `opponent_id` path parameter) |
| `owning_team_id`     | UUID    | UUID of the requesting team |
| `name`               | string  | Opponent display name (e.g., `"Blackhawks 14U"`) |
| `is_hidden`          | boolean | Whether this opponent is hidden from the UI |
| `progenitor_team_id` | UUID    | The canonical GameChanger team UUID for this opponent -- use this for other team endpoints |

#### Example Response

```json
{
  "root_team_id": "6e898958-c6e3-48c7-a97e-e281a35cfc50",
  "owning_team_id": "72bb77d8-REDACTED",
  "name": "Blackhawks 14U",
  "is_hidden": false,
  "progenitor_team_id": "f0e73e42-f248-402b-8171-524b4e56a535"
}
```

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/opponents/players

**Status: CONFIRMED LIVE -- 200 OK. 758 records, 61 unique opponent teams. Discovered 2026-03-07.**

Returns all players from all opponent teams for the owning team in a single response. This is the most efficient way to bulk-load opponent rosters without iterating per-opponent team.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | The owning team's UUID |

#### Response Schema

Bare JSON array of player records.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | The opponent team's UUID (the team this player belongs to) |
| `player_id` | UUID | The player's UUID |
| `person` | object | Player identity |
| `person.id` | UUID | Same as `player_id` |
| `person.first_name` | string | First name |
| `person.last_name` | string | Last name |
| `attributes` | object | Player attributes |
| `attributes.player_number` | string | Jersey number (string, not integer) |
| `attributes.status` | string | `"active"` or `"removed"`. Removed players are included in the response. |
| `bats` | object or null | Batting/throwing attributes. `null` for removed players who never had handedness set. |
| `bats.batting_side` | string or null | `"left"`, `"right"`, `"both"`, or `null` if not set |
| `bats.throwing_hand` | string or null | `"left"`, `"right"`, or `null` if not set |

#### Example Record

```json
{
  "team_id": "6e898958-c6e3-48c7-a97e-e281a35cfc50",
  "player_id": "68396d70-111c-4593-9df0-849051e1e96a",
  "person": {
    "id": "68396d70-111c-4593-9df0-849051e1e96a",
    "first_name": "Jackson",
    "last_name": "Dowling"
  },
  "attributes": {
    "player_number": "10",
    "status": "active"
  },
  "bats": {
    "batting_side": "right",
    "throwing_hand": "right"
  }
}
```

**Key Observations:**
- Returns 758 records across 61 opponent teams for the Lincoln Rebels 14U team.
- Includes `bats.batting_side` and `bats.throwing_hand` -- same fields as `/player-attributes/{player_id}/bats` but inline in the roster record. This is the most efficient way to get handedness for all opponents at once.
- **Removed players are included** -- `attributes.status = "removed"` records appear in the response. Filter to `"active"` only when building scouting rosters.
- **`bats` can be `null`** -- 30 of 758 records had null `bats` (all were `"removed"` status). Handle null `bats` before accessing `batting_side` or `throwing_hand`.
- **`batting_side` can be `"both"`** -- observed value in addition to `"left"`, `"right"`, and `null`. Treat `"both"` as equivalent to `"switch"` (switch hitter).
- No pagination observed in this response (758 records returned in one call). May paginate for larger datasets -- monitor `x-next-page` response header.
- **Coaching relevance: CRITICAL.** One call gives full opponent roster including handedness for all 61 opponent teams. No per-opponent iteration required.

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/lineup-recommendation

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns GameChanger's algorithmically-generated batting order and fielding assignment recommendation for the team.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

#### Response Schema

Single JSON object with `lineup` array and `metadata` object.

| Field | Type | Description |
|-------|------|-------------|
| `lineup` | array | Recommended lineup entries (9 players observed -- standard starting lineup) |
| `lineup[].player_id` | UUID | Player UUID |
| `lineup[].field_position` | string | Recommended field position (e.g., `"C"`, `"1B"`, `"P"`, `"CF"`, `"LF"`, `"RF"`, `"2B"`, `"3B"`, `"SS"`) |
| `lineup[].batting_order` | integer | Batting order position (1 = leadoff) |
| `metadata` | object | Generation metadata |
| `metadata.generated_at` | string (ISO 8601) | When this recommendation was generated |
| `metadata.team_id` | UUID | The team UUID |

#### Example Response

```json
{
  "lineup": [
    {"player_id": "11ceb5ee-REDACTED", "field_position": "C", "batting_order": 1},
    {"player_id": "8119312c-REDACTED", "field_position": "1B", "batting_order": 2},
    {"player_id": "879a99fd-REDACTED", "field_position": "RF", "batting_order": 3},
    {"player_id": "d5645a1b-REDACTED", "field_position": "P", "batting_order": 4},
    {"player_id": "e8534cc3-REDACTED", "field_position": "LF", "batting_order": 5},
    {"player_id": "996c48ba-REDACTED", "field_position": "SS", "batting_order": 6},
    {"player_id": "3050e40b-REDACTED", "field_position": "3B", "batting_order": 7},
    {"player_id": "77c74470-REDACTED", "field_position": "2B", "batting_order": 8},
    {"player_id": "b7790d88-REDACTED", "field_position": "CF", "batting_order": 9}
  ],
  "metadata": {
    "generated_at": "2026-03-07T04:09:32.884Z",
    "team_id": "72bb77d8-REDACTED"
  }
}
```

**Key Observations:**
- Returns exactly 9 players (standard starting 9, not a full roster).
- `generated_at` timestamp changes on each request (recommendation is recalculated live, not cached).
- Field positions use standard baseball position abbreviations.
- Player UUIDs match those in `GET /teams/{team_id}/players`.
- **Coaching relevance: HIGH.** The GC recommendation serves as a data-driven baseline for lineup construction. Comparing this recommendation to the coach's actual lineup reveals which players GC ranks higher/lower.

**Confirmed:** 2026-03-07.

---

### GET /bats-starting-lineups/{event_id}

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07 (confirmed via retry with home game event_id).**

Returns the stored starting lineup for a specific game event. Returns HTTP 403 if the authenticated user is not the scorer for that event (e.g., an away game where the opponent managed scoring).

**Auth note:** HTTP 403 was returned for event `e3471c3b-8c6d-450c-9541-dd20107e9ace` (away game). A retry with a home game event_id returned 200 OK with the full lineup. Access is restricted to events where the authenticated user's team was the scorer.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID. Must be for a game where the authenticated team was the primary scorer. |

#### Response Schema

Single JSON object (no wrapper -- the lineup object directly, unlike `/latest/{team_id}` which wraps in `latest_lineup`).

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique ID for this lineup record. Same `id` is referenced as `pregame_data.lineup_id` in `GET /events/{event_id}`. |
| `dh` | UUID or null | DH player UUID (null when not using DH) |
| `dh_batting_for` | UUID or null | UUID of the player the DH bats for (null when not using DH) |
| `creator` | UUID | User UUID who created this lineup (PII -- redact in stored files) |
| `entries` | array | Lineup entries. Array order = batting order (first entry = leadoff). |
| `entries[].player_id` | UUID | Player UUID |
| `entries[].fielding_position` | string | Field position (e.g., `"CF"`, `"P"`, `"RF"`, `"LF"`, `"1B"`, `"3B"`, `"C"`, `"2B"`, `"SS"`) |

#### Example Response

```json
{
  "id": "65b1ba56-cbef-41cf-bb2f-e8be239c2bf1",
  "dh": null,
  "dh_batting_for": null,
  "creator": "e07b2d06-REDACTED",
  "entries": [
    {"player_id": "d5645a1b-REDACTED", "fielding_position": "CF"},
    {"player_id": "11ceb5ee-REDACTED", "fielding_position": "P"},
    {"player_id": "879a99fd-REDACTED", "fielding_position": "RF"},
    {"player_id": "e8534cc3-REDACTED", "fielding_position": "LF"},
    {"player_id": "8119312c-REDACTED", "fielding_position": "1B"},
    {"player_id": "3050e40b-REDACTED", "fielding_position": "3B"},
    {"player_id": "e9a04fc5-REDACTED", "fielding_position": "C"},
    {"player_id": "77c74470-REDACTED", "fielding_position": "2B"},
    {"player_id": "996c48ba-REDACTED", "fielding_position": "SS"}
  ]
}
```

**Key Observations:**
- The response is the lineup object directly (no `latest_lineup` wrapper). This differs from `GET /bats-starting-lineups/latest/{team_id}` which wraps the same object in `{"latest_lineup": {...}}`.
- The lineup `id` matches `pregame_data.lineup_id` in `GET /events/{event_id}` -- enabling navigation from event to lineup directly.
- Array order corresponds to batting order.
- DH fields present but null when not using designated hitter.
- Access limited to events where the authenticated user's team was the scorer. Returns HTTP 403 for away games where the opponent managed scoring.

**Confirmed:** 2026-03-07 (confirmed with home game event_id after initial 403 on away game event_id).

---

### GET /bats-starting-lineups/latest/{team_id}

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns the most recently entered starting lineup for a team, identified by batting-order position and fielding assignment.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

#### Response Schema

Single JSON object with `latest_lineup` wrapper.

| Field | Type | Description |
|-------|------|-------------|
| `latest_lineup` | object | The lineup object |
| `latest_lineup.id` | UUID | Unique ID for this lineup record |
| `latest_lineup.dh` | UUID or null | DH player UUID (null when not using DH) |
| `latest_lineup.dh_batting_for` | UUID or null | UUID of the player the DH bats for (null when not using DH) |
| `latest_lineup.creator` | UUID | User UUID who created this lineup |
| `latest_lineup.entries` | array | Lineup entries (one per player in the starting lineup) |
| `latest_lineup.entries[].player_id` | UUID | Player UUID |
| `latest_lineup.entries[].fielding_position` | string | Field position (e.g., `"CF"`, `"P"`, `"RF"`, `"LF"`, `"1B"`, `"3B"`, `"C"`, `"2B"`, `"SS"`) |

**Note:** The `entries` array order corresponds to batting order -- first entry = leadoff, etc.

#### Example Response

```json
{
  "latest_lineup": {
    "id": "65b1ba56-cbef-41cf-bb2f-e8be239c2bf1",
    "dh": null,
    "dh_batting_for": null,
    "creator": "e07b2d06-REDACTED",
    "entries": [
      {"player_id": "d5645a1b-REDACTED", "fielding_position": "CF"},
      {"player_id": "11ceb5ee-REDACTED", "fielding_position": "P"},
      {"player_id": "879a99fd-REDACTED", "fielding_position": "RF"},
      {"player_id": "e8534cc3-REDACTED", "fielding_position": "LF"},
      {"player_id": "8119312c-REDACTED", "fielding_position": "1B"},
      {"player_id": "3050e40b-REDACTED", "fielding_position": "3B"},
      {"player_id": "e9a04fc5-REDACTED", "fielding_position": "C"},
      {"player_id": "77c74470-REDACTED", "fielding_position": "2B"},
      {"player_id": "996c48ba-REDACTED", "fielding_position": "SS"}
    ]
  }
}
```

**Key Observations:**
- Returns the actual batting order as entered by the coach (as opposed to `/lineup-recommendation` which is GC's algorithm).
- DH fields present but null when not using designated hitter.
- `creator` field is a user UUID (PII -- redact in stored files).
- Compare with `/lineup-recommendation` to see where the coach deviated from GC's algorithm.

**Confirmed:** 2026-03-07.

---

### GET /game-streams/{game_stream_id}/events

**Status: CONFIRMED LIVE -- 200 OK. 319 events, 10 unique event codes. Discovered 2026-03-07.**

Returns the raw event stream for a completed game. This is the low-level event log from which all higher-level game data (boxscore, plays, stats) is derived.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_stream_id` | UUID | The `game_stream.id` from game-summaries |

#### Response Schema

Bare JSON array of event objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Event record UUID |
| `stream_id` | UUID | The game stream UUID (matches path parameter) |
| `sequence_number` | integer | Ordering position (0-based). Events are ordered by this field. |
| `event_data` | string | **JSON-encoded string** containing the actual event payload. Must be JSON-parsed separately. |

**`event_data` inner object fields (after JSON-parsing the string):**

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Event type code (see below) |
| `id` | UUID | Event UUID |
| `createdAt` | integer | Unix timestamp in milliseconds |
| `attributes` | object | Code-specific attributes |
| `compactorAttributes` | object | Stream compaction metadata. `stream` field: `"head"` or `"main"`. |
| `events` | array | For batched events -- array of individual event objects (same shape) |

**Observed event codes:**

| Code | Description |
|------|-------------|
| `set_teams` | Game initialization -- sets home team UUID (`homeId`) and away team UUID (`awayId`) |
| `fill_lineup_index` | Assigns a player to a lineup slot by index. Attributes: `teamId`, `playerId`, `index`. |
| `reorder_lineup` | Reorders the batting lineup. |
| `fill_position` | Assigns a player to a field position. Attributes: `teamId`, `playerId`, field position code. |
| `sub_players` | Substitution event. |
| `pitch` | A single pitch recorded. Attributes include pitch result, count, and related context. |
| `transaction` | At-bat transaction (hit, out, walk, etc.). |
| `base_running` | Baserunning event (stolen base, advance, out on bases). |
| `edit_group` | Batch edit/correction to prior events. |
| `replace_runner` | Courtesy runner substitution. |
| `undo` | Undo of a prior event. |

**Key Observations:**
- Total of 319 events for a 6-inning game (game_stream `5f54ba22-c23f-4301-bf0f-85e0f947a1ff`).
- The `event_data` field is a **JSON string, not an object**. Must call `JSON.parse(event.event_data)` to access inner fields.
- Some events use `events` array inside `event_data` (batched multi-event records) rather than a single `code`/`attributes` object.
- This is the raw data that the boxscore and plays endpoints are derived from. Use the higher-level endpoints for most coaching use cases.
- The `gamestream-viewer-payload-lite` endpoint (below) returns the same events array with one additional field (`created_at` timestamp) per record.

**Coaching Relevance:** Low for direct use. This is raw event stream data -- use `GET /game-stream-processing/{id}/plays` (processed play-by-play) or `GET /game-stream-processing/{id}/boxscore` instead.

**Confirmed:** 2026-03-07.

---

### GET /game-streams/gamestream-viewer-payload-lite/{event_id}

**Status: CONFIRMED LIVE -- 200 OK. Schema documented. Discovered 2026-03-07.**

Returns the lightweight game viewer payload for a completed game. Contains the same event stream as `GET /game-streams/{game_stream_id}/events` but with additional fields and a summary structure.

**Note on path:** Despite the name including `event_id`, this endpoint accepts the `event_id` from the schedule (UUID) directly -- it resolves to the game stream internally. The event_id used (`e3471c3b-8c6d-450c-9541-dd20107e9ace`) is a schedule event UUID, not a game_stream_id.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID (from `GET /teams/{team_id}/schedule`) |

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `stream_id` | UUID | The resolved game stream UUID (= `game_stream.id` from game-summaries) |
| `latest_events` | array | Event records with 5 fields: `id`, `stream_id`, `created_at` (ISO 8601 string), `event_data` (JSON-encoded string), `sequence_number`. One additional field vs `/game-streams/{id}/events`: `created_at` replaces the inner `createdAt` (ms timestamp). |
| `all_event_data_ids` | array | Array of inner event UUIDs (the `id` field inside parsed `event_data`, not the outer record `id`) |
| `marker` | string or null | Cursor for incremental polling. For completed games, observed as the last `sequence_number` string (e.g., `"318"` for a 319-event stream). For live games, likely `null` or a cursor token until the game is complete. |

**Observed counts:**
- `latest_events`: 319 events (same count as `/game-streams/{stream_id}/events`)
- `all_event_data_ids`: 319 UUIDs (same events, just the inner event_data UUIDs, not the wrapper record UUIDs)
- `marker`: `"318"` (string of last sequence number for this completed game)

**Confirmed:** 2026-03-07.

---

### GET /game-streams/gamestream-recap-story/{event_id}

**Status: HTTP 404 for event `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6`. Schema documented in 2026-03-05 proxy section above.**

The endpoint exists and was confirmed via proxy capture, but returned 404 for the event_id tested on 2026-03-07. The recap may not be generated for all games -- it may require a game to have been processed and scored completely.

**Confirmed schema:** See the `gamestream-recap-story` entry in the Proxy-Discovered Endpoints (2026-03-05) section above.

**Discovered:** 2026-03-07 (404 confirmed for this event).

---

### GET /game-streams/insight-story/bats/{event_id}

**Status: HTTP 404 -- endpoint does not return data for this event. Discovered 2026-03-07.**

Returned 404 for event `e3471c3b-8c6d-450c-9541-dd20107e9ace`. Consistent with prior proxy observation of 404.

---

### GET /game-streams/player-insights/bats/{event_id}

**Status: HTTP 404 -- endpoint does not return data for this event. Discovered 2026-03-07.**

Returned 404 for event `e3471c3b-8c6d-450c-9541-dd20107e9ace`. Consistent with prior proxy observation of 404.

---

### GET /player-attributes/{player_id}/bats

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns batting/throwing handedness attributes for a player.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `player_id` | UUID | Player UUID (from `GET /teams/{team_id}/players`) |

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `player_id` | UUID | The player UUID (matches path parameter) |
| `throwing_hand` | string | `"right"` or `"left"` |
| `batting_side` | string | `"right"`, `"left"`, or `"switch"` |

#### Example Response

```json
{
  "player_id": "879a99fd-ef90-4cce-9794-4ec0f78224bb",
  "throwing_hand": "right",
  "batting_side": "left"
}
```

**Note:** The same fields appear inline in `GET /teams/{team_id}/opponents/players` responses. For bulk opponent handedness, prefer the opponents/players bulk call. Use this endpoint for individual player lookups or for own-team players.

**Confirmed:** 2026-03-07.

---

### GET /organizations/{org_id}/standings

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns win/loss standings for all teams in an organization.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

#### Response Schema

Bare JSON array. Each element is a team standing record.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Team UUID |
| `home` | object | Home game record |
| `home.wins` | integer | Home wins |
| `home.losses` | integer | Home losses |
| `home.ties` | integer | Home ties |
| `away` | object | Away game record (same shape as `home`) |
| `overall` | object | Overall record (same shape as `home`) |
| `last10` | object | Last 10 games record (same shape as `home`) |
| `winning_pct` | float | Overall winning percentage (0.0 to 1.0) |
| `runs` | object | Run differential data |
| `runs.scored` | integer | Total runs scored |
| `runs.allowed` | integer | Total runs allowed |
| `runs.differential` | integer | `scored - allowed` |
| `streak` | object | Current win/loss streak |
| `streak.count` | integer | Length of current streak |
| `streak.type` | string | `"win"` or `"loss"` |

**Note:** The org used for testing (`87452e66-ac31-4d72-8cda-467cce2fe832`) returned 6 teams with all zeros. This is likely a travel ball org without active league standings. The schema is fully populated for org types that track standings (e.g., high school leagues with scheduled in-conference games).

**Confirmed:** 2026-03-07.

---

### GET /organizations/{org_id}/team-records

**Status: CONFIRMED LIVE -- 200 OK. Same schema as `/standings`. Discovered 2026-03-07.**

Returns season win/loss records for all teams in an organization. Response schema is identical to `GET /organizations/{org_id}/standings` -- same fields, same structure.

**Relationship to `/standings`:** The two endpoints appear to return the same data from the same org. The distinction may be that `/standings` is for league/conference standings context (includes home/away/last10/streak) while `/team-records` is a raw record view. Both were identical in this test. Use either; they serve the same data.

**Confirmed:** 2026-03-07.

---

### GET /organizations/{org_id}/pitch-count-report

**Status: CONFIRMED LIVE -- 200 OK. CSV format response. Discovered 2026-03-07.**

Returns a pitch count report for all pitchers in the organization for the past week. Unlike other endpoints, the response is **CSV format** (not JSON).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

#### Response Schema

The response is a **CSV string** (content-type likely `text/csv` or `text/plain`). Columns (confirmed from header row):

| Column | Description |
|--------|-------------|
| `Game Date` | Date of the game |
| `Start Time` | Game start time |
| `Pitcher` | Pitcher name |
| `Team` | Pitcher's team name |
| `Opponent` | Opposing team |
| `Pitch Count` | Total pitches thrown |
| `Last Batter, First Pitch #` | Pitch number of the first pitch to the last batter faced |
| `Innings Pitched` | Innings pitched |
| `Innings Caught` | Innings the pitcher caught (if they also caught) |
| `Final Score` | Final game score |
| `Scored By` | Who recorded the scoring |

#### Example Response

```
Game Date,Start Time,Pitcher,Team,Opponent,Pitch Count,"Last Batter, First Pitch #",Innings Pitched,Innings Caught,Final Score,Scored By
No games with pitcher data were found in the past week.
```

**Notes:**
- The response body is a CSV string, not JSON. This is the only non-JSON API response documented in this spec.
- "No games with pitcher data were found in the past week." message returned when no recent games exist.
- The report appears to cover the past 7 days by default. Query parameter for date range not yet confirmed.
- The `org_id` used (`8881846c-7a9c-4230-ac17-09627aac7f59`) returned the "no games" message, confirming the endpoint works but the org had no recent games.
- **Coaching relevance: HIGH.** Pitch count tracking is a safety and regulatory requirement. This endpoint provides org-wide pitch counts in one call vs. per-game aggregation.

**Confirmed:** 2026-03-07.

---

### GET /organizations/{org_id}/events

**Status: CONFIRMED LIVE -- 200 OK. Empty array for travel ball org. Discovered 2026-03-07.**

Returns events (scheduled games/practices) for an organization. Returned `[]` for the travel ball org (`87452e66-...`). This endpoint likely has data for organized league orgs (e.g., high school programs with league game calendars).

**Confirmed:** 2026-03-07.

---

### GET /organizations/{org_id}/game-summaries

**Status: CONFIRMED LIVE -- 200 OK. Empty array for travel ball org. Discovered 2026-03-07.**

Returns game summaries for an organization. Returned `[]` for the travel ball org. Likely populated for league/school program orgs where the organization manages the game schedule directly.

**Confirmed:** 2026-03-07.

---

### GET /organizations/{org_id}/scoped-features

**Status: CONFIRMED LIVE -- 200 OK. Empty features object. Discovered 2026-03-07.**

Returns feature flags scoped to the organization. Returned `{"scoped_features": {}}` -- no features enabled for this org.

**Confirmed:** 2026-03-07.

---

### GET /organizations/{org_id}/teams

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Previously returned HTTP 500 with web headers due to missing pagination parameters. CONFIRMED 2026-03-07 with required parameters.**

Returns all teams belonging to an organization. Requires `?page_starts_at=0&page_size=50` query parameters and the `x-pagination: true` request header.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

#### Required Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page_starts_at` | integer | YES | Pagination offset. Use `0` for first page. |
| `page_size` | integer | YES | Page size. Use `50`. |

#### Required Headers (in addition to standard auth headers)

| Header | Value | Description |
|--------|-------|-------------|
| `x-pagination` | `true` | Must be present; server returns HTTP 500 without it |

#### Response Schema

Bare JSON array of team objects. 7 teams observed for the Lincoln Rebels travel ball organization.

| Field | Type | Description |
|-------|------|-------------|
| `root_team_id` | UUID | The team's root UUID (use for `/teams/{id}` calls) |
| `organization_id` | UUID | Organization UUID |
| `status` | string | Team status: `"active"`, `"org_invite"` |
| `name` | string | Team display name |
| `sport` | string | Sport (e.g., `"baseball"`) |
| `season_name` | string | Season name (e.g., `"summer"`, `"spring"`) |
| `season_year` | integer | Season year |
| `city` | string | City |
| `state` | string | State/province |
| `country` | string | Country |
| `staff_ids` | array | Array of user UUIDs for team staff (populated for org_invite teams, empty for active) |
| `proxy_team_id` | UUID or null | Internal proxy team ID (null for `"org_invite"` status teams) |
| `age_group` | string | Age group (e.g., `"14U"`, `"9U"`) |
| `team_public_id` | string | Public ID slug for the team |

#### Example Response

```json
[
  {
    "root_team_id": "cb67372e-REDACTED",
    "organization_id": "87452e66-REDACTED",
    "status": "active",
    "name": "Lincoln Rebels 9U",
    "sport": "baseball",
    "season_name": "summer",
    "season_year": 2026,
    "city": "Lincoln",
    "state": "NE",
    "country": "United States",
    "staff_ids": [],
    "proxy_team_id": "3d0e3553-REDACTED",
    "age_group": "9U",
    "team_public_id": "KCRUFIkaHGXI"
  }
]
```

**Key Observations:**
- `root_team_id` is the primary team UUID for use with `/teams/{team_id}` and all team-scoped endpoints.
- `team_public_id` enables public endpoint access without additional UUID-to-public_id bridge calls.
- Teams with `status: "org_invite"` have `proxy_team_id: null` -- invited but not yet fully provisioned.
- **Coaching relevance: HIGH.** Single call enumerates all teams in an organization; replaces per-team discovery.

**Confirmed:** 2026-03-07. Required params: `?page_starts_at=0&page_size=50` + `x-pagination: true` header.

---

### GET /events/{event_id}

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns full details for a single scheduled event. Contains both the base event metadata and pre-game data (opponent, home/away, lineup).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

#### Response Schema

Single JSON object with two top-level keys.

**`event` object:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Event UUID (matches path parameter) |
| `event_type` | string | `"game"`, `"practice"`, or other event type |
| `sub_type` | array | Sub-type tags (empty array `[]` observed for standard games) |
| `status` | string | `"scheduled"`, `"completed"`, etc. |
| `full_day` | boolean | Whether this is an all-day event |
| `team_id` | UUID | The team this event belongs to |
| `start.datetime` | string (ISO 8601) | Game start time in UTC |
| `end.datetime` | string (ISO 8601) | Scheduled end time in UTC |
| `arrive.datetime` | string (ISO 8601) | Requested arrival time in UTC |
| `timezone` | string | IANA timezone (e.g., `"America/Chicago"`) |

**`pregame_data` object:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Same as `event.id` |
| `game_id` | UUID | Same as `event.id` (redundant field) |
| `opponent_name` | string | Opponent team display name |
| `opponent_id` | UUID | Opponent team UUID (= `progenitor_team_id` for opponent lookup) |
| `home_away` | string | `"home"` or `"away"` perspective of the team |
| `lineup_id` | UUID | UUID of the pre-game lineup entry (links to bats-starting-lineups) |

#### Example Response

```json
{
  "event": {
    "id": "e3471c3b-8c6d-450c-9541-dd20107e9ace",
    "event_type": "game",
    "sub_type": [],
    "status": "scheduled",
    "full_day": false,
    "team_id": "72bb77d8-REDACTED",
    "start": {"datetime": "2025-04-06T19:00:00.000Z"},
    "end": {"datetime": "2025-04-06T21:00:00.000Z"},
    "arrive": {"datetime": "2025-04-06T19:00:00.000Z"},
    "timezone": "America/Chicago"
  },
  "pregame_data": {
    "id": "e3471c3b-8c6d-450c-9541-dd20107e9ace",
    "game_id": "e3471c3b-8c6d-450c-9541-dd20107e9ace",
    "opponent_name": "Nebraska Prime Gold 14u",
    "opponent_id": "f00549a8-84b1-4c9f-97e9-79942531d13b",
    "home_away": "away",
    "lineup_id": "a39fbbeb-05bd-4b2c-b7cc-b249a3d17a6c"
  }
}
```

**Key Observations:**
- `pregame_data.lineup_id` links to the `id` field in `GET /bats-starting-lineups/{event_id}` -- enables resolving from event to lineup directly.
- This endpoint provides the same data as an individual event in the schedule list, but as a single-object lookup without needing to paginate through the full schedule.

**Confirmed:** 2026-03-07.

---

### GET /events/{event_id}/highlight-reel

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented below. Discovered 2026-03-05, confirmed 2026-03-07.**

Returns a structured highlight reel for a completed game event. The playlist interleaves inning-transition plates with actual play clips, each linked to a play-by-play event via `pbp_id`.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `multi_asset_video_id` | UUID | Multi-asset video identifier (matches `event_id`) |
| `event_id` | UUID | Event UUID (matches path parameter) |
| `status` | string | Highlight reel status. Observed: `"finalized"` |
| `type` | string | Asset type. Observed: `"event"` |
| `playlist` | array | Ordered list of video segments |
| `playlist[].media_type` | string | `"video"` |
| `playlist[].url` | string (URL) | HLS (.m3u8) CloudFront-signed video URL |
| `playlist[].is_transition` | boolean | `true` for inning marker plates, `false` for play clips |
| `playlist[].clip_id` | UUID (optional) | Clip identifier -- absent on transition plates |
| `playlist[].pbp_id` | UUID (optional) | Play-by-play ID -- links to `id` in `/game-stream-processing/{id}/plays`. Absent on transitions. |
| `playlist[].cookies` | object | CloudFront signed cookies: `CloudFront-Key-Pair-Id`, `CloudFront-Signature`, `CloudFront-Policy` |
| `duration` | integer | Total highlight reel duration in seconds |
| `thumbnail_url` | string (URL) | CloudFront-signed thumbnail URL |
| `small_thumbnail_url` | string | Small thumbnail URL (observed: empty string `""`) |

**Key Observations:**
- Transition plates use static `vod-archive.gc.com/static-content/startplate-transitions/baseball/inning_N.m3u8` paths.
- Play clips use IVS paths: `vod-archive.gc.com/ivs/v1/{account_id}/{channel_id}/clips/{timestamp}.m3u8`.
- `pbp_id` enables cross-reference between video clips and play-by-play data.
- All video URLs require CloudFront signed cookies for playback.

**Coaching Relevance:** Low for stat analytics. Not needed for data ingestion.

**Confirmed:** 2026-03-07.

---

### Web-Route Season-Slug Endpoints

**Status: ALL HTTP 404 -- route pattern does not resolve on `api.team-manager.gc.com`. Discovered 2026-03-07.**

The following endpoints from the 2026-03-07 proxy section all returned HTTP 404 when tested:

- `GET /teams/{public_id}/{season-slug}/opponents`
- `GET /teams/{public_id}/{season-slug}/schedule/{event_id}/plays`
- `GET /teams/{public_id}/{season-slug}/season-stats`
- `GET /teams/{public_id}/{season-slug}/team`
- `GET /teams/{public_id}/{season-slug}/tools`
- `GET /teams/{public_id}/players/{player_id}`
- `GET /public/teams/{public_id}/live`

**Interpretation:** These URL patterns may be served by the **web app** (`https://web.gc.com`) rather than the API (`https://api.team-manager.gc.com`). The proxy capture may have captured web-frontend navigation requests rather than API calls. These endpoints are NOT available on the API domain.

**Action:** Re-test against `https://web.gc.com` if these patterns are needed. For stat data, use the authenticated endpoints which are confirmed to work on the API domain.

---

### GET /teams/public/{public_id}/access-level

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

**AUTH REQUIRED:** Despite the `/public/` path segment, this endpoint requires `gc-token` authentication. Requests without a valid token return HTTP 401 with: `{"message":"The request was missing user authentication, please try again with valid token(s)","missing_authentication":["user"]}`. Do not confuse this with the truly public `/public/teams/` endpoints which require no auth.

Returns the paid access level for a team's public profile.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Team public ID slug (e.g., `"a1GFM9Ku0BbF"`) |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
```

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `paid_access_level` | string or null | Access tier. Observed: `null` for this team. May be `"premium"`, `"plus"`, or other tier strings when the team has paid access. |

#### Example Response (authenticated)

```json
{"paid_access_level": null}
```

#### Error Response (unauthenticated -- HTTP 401)

```json
{
  "message": "The request was missing user authentication, please try again with valid token(s)",
  "missing_authentication": ["user"]
}
```

**Confirmed:** 2026-03-07.

---

### GET /teams/public/{public_id}/id

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

**AUTH REQUIRED:** Despite the `/public/` path segment, this endpoint requires `gc-token` authentication. Requests without a valid token return HTTP 401 with: `{"message":"The request was missing user authentication, please try again with valid token(s)","missing_authentication":["user"]}`. Do not confuse this with the truly public `/public/teams/` endpoints which require no auth.

**Reverse bridge: public_id slug -> team UUID.** This is the reverse of `GET /teams/{team_id}/public-team-profile-id` (which resolves UUID -> public_id slug).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Team public ID slug |

#### Headers

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
```

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | The team's internal UUID |

#### Example Response (authenticated)

```json
{"id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4"}
```

#### Error Response (unauthenticated -- HTTP 401)

```json
{
  "message": "The request was missing user authentication, please try again with valid token(s)",
  "missing_authentication": ["user"]
}
```

**Confirmed:** The public_id `a1GFM9Ku0BbF` resolves to UUID `72bb77d8-54ca-42d2-8547-9da4880d0cb4` (Lincoln Rebels 14U). This confirms the symmetry between the two bridge endpoints.

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/users/count

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns the count of users associated with a team without loading the full user list.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Total number of users on the team |

#### Example Response

```json
{"count": 243}
```

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/relationships

**Status: CONFIRMED LIVE -- 200 OK. Previously documented in proxy section -- status upgraded. Confirmed 2026-03-07.**

Returns user-to-player relationship mappings for the team. Links parent/guardian GameChanger accounts to their associated player records. Contains PII -- user UUIDs should not be stored or logged without appropriate access controls.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

#### Response Schema

Bare JSON array of relationship objects.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Team UUID (same as path parameter) |
| `user_id` | UUID | GameChanger user UUID (PII -- handle with care) |
| `player_id` | UUID | Player UUID on this team |
| `relationship` | string | Relationship type. Observed values: `"primary"` (parent/guardian), `"self"` (player's own account) |

**Key observations:**
- Multiple `user_id` values can map to the same `player_id` (e.g., both parents linked to the same player).
- `"self"` relationship indicates the user IS the player (player has their own GameChanger account).
- `"primary"` relationship indicates the user is a parent/guardian of the player.
- 243 total users on this team (from `/users/count`), relationships list has 86+ records for a subset of players.

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/relationships/requests

**Status: CONFIRMED LIVE -- 200 OK. Returns empty array `[]`. Discovered 2026-03-07.**

No pending relationship requests for this team. Schema unknown (no records in response).

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/scoped-features

**Status: CONFIRMED LIVE -- 200 OK. Returns empty features. Confirmed 2026-03-07.**

```json
{"scoped_features": {}}
```

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/team-notification-setting

**Status: CONFIRMED LIVE -- 200 OK. Previously documented in proxy section -- status upgraded. Confirmed 2026-03-07.**

```json
{"team_id": "72bb77d8-REDACTED", "event_reminder_setting": "never"}
```

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/web-widgets

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns the web widget configurations for a team.

#### Response Schema

Bare JSON array of widget objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Widget UUID |
| `type` | string | Widget type. Observed: `"schedule"` |

#### Example Response

```json
[{"id": "5417dbce-11ad-44d3-afc4-244147272961", "type": "schedule"}]
```

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/external-associations

**Status: CONFIRMED LIVE -- 200 OK. Returns empty array `[]`. Previously documented in proxy section -- confirmed. Discovered 2026-03-07.**

No external system associations for this team. Schema unknown from this response (empty array).

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/avatar-image

**Status: CONFIRMED LIVE -- 200 OK. Returns signed CloudFront URL. Discovered 2026-03-07.**

Returns a signed URL for the team's avatar/logo image.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `full_media_url` | string (URL) | Time-limited signed CloudFront URL to the team avatar image |

The URL follows the pattern: `https://media-service.gc.com/{image-uuid}?Policy={base64}&Key-Pair-Id={id}&Signature={sig}`

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/video-stream/videos

**Status: CONFIRMED LIVE -- 200 OK. Returns empty array `[]`. Discovered 2026-03-07.**

No standalone videos for this team (distinct from per-event video stream assets).

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/schedule/events/{event_id}/video-stream

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns the video stream configuration and metadata for a specific game event. Contains both the live stream setup info and post-game status.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `stream_id` | UUID | Video stream UUID (different from `game_stream.id`) |
| `schedule_event_id` | UUID | Event UUID (matches path parameter) |
| `disabled` | boolean | Whether streaming is disabled for this event |
| `is_muted` | boolean | Whether stream audio is muted |
| `team_id` | UUID | Team UUID |
| `user_id` | UUID | User who configured the stream (PII -- redact) |
| `viewer_count` | integer | Current viewer count (0 for completed games) |
| `audience_type` | string | `"players_family"` or other audience restriction |
| `is_playable` | boolean | Whether the stream is currently playable |
| `thumbnail_url` | string or null | Thumbnail URL |
| `playable_at` | string or null | When playback becomes available (null for past games) |
| `live_at` | string or null | When the stream went live |
| `status` | string | Stream status. Observed: `"ended"` |
| `publish_url` | string | RTMPS ingest URL (contains stream key -- treat as credential) |
| `shared_by_opponent` | boolean | Whether opponent shared their stream |
| `aws_ivs_account_id` | string | AWS IVS account identifier |
| `associated_external_camera` | object or null | External camera configuration |
| `ingest_endpoints` | array | Available ingest protocols (RTMPS, SRT) |

**Security note:** `publish_url` and `ingest_endpoints[].stream_key` contain live stream credentials. Do not log or store these values.

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/schedule/events/{event_id}/video-stream/assets

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Confirmed 2026-03-07.**

Returns the list of video recording segments for a specific game event. Three assets observed for a 2025-07-15 game. This is the event-scoped equivalent of `GET /teams/{team_id}/video-stream/assets` (which returns team-wide assets with pagination).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |
| `event_id` | UUID | Schedule event UUID |

#### Response Schema

Bare JSON array of asset objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Asset UUID |
| `stream_id` | UUID | Parent video stream UUID (matches `stream_id` in the `/video-stream` response) |
| `team_id` | UUID | Team UUID |
| `schedule_event_id` | UUID | Event UUID (matches path parameter) |
| `created_at` | string (ISO 8601) | When recording started |
| `audience_type` | string | Audience restriction. Observed: `"players_family"` |
| `duration` | integer or null | Recording duration in seconds. `null` for very short/interrupted segments; integer for complete recordings (e.g., `3848` = ~64-minute main game recording) |
| `ended_at` | string (ISO 8601) | When recording ended |
| `thumbnail_url` | string (URL) | Thumbnail hosted at `vod-archive.gc.com` CDN |
| `user_id` | UUID | User who created the recording (PII -- redact) |
| `uploaded` | boolean | Whether the recording has been uploaded to external storage |
| `is_processing` | boolean | Whether the recording is still being processed |

#### Example Response (PII redacted, 2 of 3 assets shown)

```json
[
  {
    "id": "27e27ea8-f82d-4a68-a13d-dd099e3d4575",
    "stream_id": "660727ab-f035-4df0-a327-a8d0e2dbd892",
    "team_id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4",
    "schedule_event_id": "1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6",
    "created_at": "2025-07-15T17:58:02.698Z",
    "audience_type": "players_family",
    "duration": null,
    "ended_at": "2025-07-15T18:00:28.768Z",
    "thumbnail_url": "https://vod-archive.gc.com/ivs/v1/...",
    "user_id": "{REDACTED_USER_UUID}",
    "uploaded": false,
    "is_processing": false
  },
  {
    "id": "6a5b023f-1d4c-401f-82df-4da651c32698",
    "stream_id": "660727ab-f035-4df0-a327-a8d0e2dbd892",
    "team_id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4",
    "schedule_event_id": "1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6",
    "created_at": "2025-07-15T18:19:26.497Z",
    "audience_type": "players_family",
    "duration": 3848,
    "ended_at": "2025-07-15T19:20:27.662Z",
    "thumbnail_url": "https://vod-archive.gc.com/ivs/v1/...",
    "user_id": "{REDACTED_USER_UUID}",
    "uploaded": false,
    "is_processing": false
  }
]
```

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/schedule/events/{event_id}/video-stream/live-status

**Status: CONFIRMED LIVE -- 200 OK. Discovered 2026-03-07.**

Returns whether a game event currently has an active live stream.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `isLive` | boolean | `true` if streaming is currently live, `false` otherwise |

#### Example Response

```json
{"isLive": false}
```

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/schedule/events/{event_id}/rsvp-responses

**Status: CONFIRMED LIVE -- 200 OK. Returns empty array `[]`. Discovered 2026-03-07.**

No RSVPs for this event. Schema unknown from empty response.

**Confirmed:** 2026-03-07.

---

### GET /teams/{team_id}/schedule/event-series/{series_id}

**Status: HTTP 404 -- series not found. Discovered 2026-03-07.**

Returned 404 for series UUID `40b6a03f-c666-4448-9c36-f33764eb3442`. The series may not exist for this team, or the series UUID may be from a different team's scope.

---

### GET /me/permissions

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Previously returned HTTP 501 (Not Implemented) without required parameters. CONFIRMED 2026-03-07 with required parameters.**

Returns the authenticated user's permissions for a specific entity (team, organization, etc.). Requires `entityId` and `entityType` query parameters.

#### Required Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entityId` | UUID | YES | UUID of the entity to check permissions for |
| `entityType` | string | YES | Type of entity. Observed: `"team"` |

#### Response Schema

Single JSON object with one key.

| Field | Type | Description |
|-------|------|-------------|
| `results` | array | Array of permission result objects |
| `results[].permissions` | array of strings | List of permission strings granted to the user |
| `results[].entity` | object | The entity this permission applies to |
| `results[].entity.type` | string | Entity type (e.g., `"team"`) |
| `results[].entity.id` | UUID | Entity UUID |

#### Observed Permission Values

Full set observed for a team admin user:
`can_view_team_details`, `can_view_team_relationships`, `can_manage_team`, `can_view_video`,
`can_view_team_announcements`, `can_manage_lineup`, `can_invite_fans`, `can_manage_opponent`,
`can_manage_player`, `can_view_stats`, `can_view_team_schedule`, `can_view_lineup`,
`can_receive_player_alerts`, `can_manage_event_video`, `can_view_event_rsvps`,
`can_manage_messaging`, `can_purchase_team_pass`, `can_manage_game_scorekeeping`

#### Example Response

```json
{
  "results": [
    {
      "permissions": ["can_view_team_details", "can_manage_team", "can_view_stats"],
      "entity": {
        "type": "team",
        "id": "72bb77d8-REDACTED"
      }
    }
  ]
}
```

**Key Observations:**
- Without `?entityId=<uuid>&entityType=team`, server returns HTTP 501 `"Not Implemented"`.
- The 18 permissions observed indicate full admin access to the team.
- **Coaching relevance: LOW** for data ingestion. Useful for understanding what access a given token has before attempting data pulls.

**Confirmed:** 2026-03-07. Required params: `?entityId={team_uuid}&entityType=team`.

---

### GET /me/organizations

**Status: CONFIRMED LIVE -- 200 OK (empty array). Previously returned HTTP 500 with web headers due to missing pagination parameters. CONFIRMED 2026-03-07 with required parameters.**

Returns organizations the authenticated user is directly a member of (as opposed to `/me/related-organizations` which returns organizations associated via team membership). Returns an empty array for accounts where organization membership is via team associations only.

#### Required Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page_size` | integer | YES | Page size. Use `50`. |

#### Required Headers (in addition to standard auth headers)

| Header | Value | Description |
|--------|-------|-------------|
| `x-pagination` | `true` | Must be present; server returns HTTP 500 without it |

#### Response Schema

Bare JSON array of organization objects. Empty array `[]` observed (no direct org memberships for this account).

**Key Observations:**
- Without `?page_size=50` and `x-pagination: true`, server returns HTTP 500.
- Returns empty array for accounts where org access is via team membership rather than direct org membership.
- Distinct from `/me/related-organizations` which returned 2 orgs via team associations.
- **Coaching relevance: LOW** for this account. May be relevant if the user is an org admin.

**Confirmed:** 2026-03-07. Required params: `?page_size=50` + `x-pagination: true` header.

---

### GET /me/schedule

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns a unified cross-team schedule for all teams the authenticated user belongs to. Very high coaching value -- a single call returns upcoming and recent events across all 26 active teams.

#### Response Schema

Single JSON object with 5 top-level keys.

| Field | Type | Description |
|-------|------|-------------|
| `teams` | object | Map of team UUIDs to team metadata objects. 26 teams observed. |
| `teams.<uuid>.name` | string | Team display name |
| `teams.<uuid>.sport` | string | Sport (e.g., `"baseball"`). Present for newer teams only. |
| `teams.<uuid>.createdAt` | string (ISO 8601) | Team creation date. Present for newer teams only. |
| `organizations` | object | Map of organization UUIDs to org metadata (empty `{}` in this capture) |
| `config` | object | Schedule query configuration |
| `config.max_teams` | integer | Maximum teams returned (observed: `150`) |
| `config.max_future_days` | integer | How many days ahead events are returned (observed: `180`) |
| `config.max_past_days` | integer | How many days back events are returned (observed: `90`) |
| `expire_in_seconds` | integer | Cache TTL for this response (observed: `30`) |
| `events` | array | Flat array of upcoming/recent events across all teams. 71 events observed. |

**`events` array item schema:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Event UUID |
| `team_id` | UUID | Which team this event belongs to |
| `kind` | string | Event type: `"game"`, `"practice"`, etc. |
| `notes` | string | Coach notes for this event |
| `is_all_day` | boolean | Whether the event spans the full day |
| `start_time` | string (ISO 8601) | Event start in UTC |
| `end_time` | string (ISO 8601) | Event end in UTC |
| `arrive_by_time` | string (ISO 8601) | Requested arrival time in UTC |
| `timezone` | string | IANA timezone |
| `opponent_id` | UUID or null | Opponent team UUID (for games) |
| `is_home_game` | boolean | Whether this is a home game |
| `location_name` | string | Venue name |
| `rsvps` | array | RSVP responses for this event |
| `rsvps[].attending_status` | string | `"going"`, `"not_going"`, `"maybe"` |
| `rsvps[].attendee_user_id` | UUID | User or player UUID who RSVPed |
| `rsvps[].attending_id_type` | string | `"user"` or `"player"` |
| `video` | object | Video availability summary |
| `video.is_live` | boolean | Whether stream is currently live |
| `video.has_videos` | boolean | Whether recorded videos exist |
| `video.is_test_stream` | boolean | Whether this was a test stream |

**Key Observations:**
- Returns events from the past 90 days through the next 180 days across all teams.
- RSVPs are embedded inline (no separate API call needed for RSVP data).
- `expire_in_seconds: 30` -- very short cache TTL; this endpoint likely reflects near-real-time event status.
- **Coaching relevance: HIGH.** Single call gives the full schedule picture across all teams, with RSVP status and video availability inline.

**Confirmed:** 2026-03-07.

---

### GET /me/associated-players

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns all player records associated with the authenticated user across all teams and seasons. Key endpoint for longitudinal player tracking.

#### Response Schema

Single JSON object with 3 top-level keys.

| Field | Type | Description |
|-------|------|-------------|
| `teams` | object | Map of team UUIDs to team metadata. 13 teams observed. |
| `teams.<uuid>.name` | string | Team display name |
| `teams.<uuid>.sport` | string | Sport |
| `players` | object | Map of player UUIDs to player identity + team reference. 13 players observed (one per team). |
| `players.<player_uuid>.first_name` | string | Player first name |
| `players.<player_uuid>.last_name` | string | Player last name |
| `players.<player_uuid>.team_id` | UUID | The team this player record belongs to |
| `associations` | array | Array of player-user relationship objects. One entry per player record. |
| `associations[].relation` | string | Relationship type. Observed: `"primary"` (indicates primary family/guardian relationship) |
| `associations[].player_id` | UUID | Player UUID (links to `players` map keys) |

#### Example (redacted)

```json
{
  "teams": {
    "72bb77d8-REDACTED": {"name": "Lincoln Rebels 14U", "sport": "baseball"}
  },
  "players": {
    "9e5faf37-REDACTED": {
      "first_name": "Reid",
      "last_name": "Wilkinson",
      "team_id": "103e1cb5-REDACTED"
    }
  }
}
```

**Key Observations:**
- Returns 13 player records across 13 teams, one per team-player combination.
- All observed players are the same person (Reid Wilkinson) across different season teams -- this is the player identity timeline.
- The `team_id` on each player record links back to the `teams` map in this response.
- **Coaching relevance: HIGH.** This is the primary endpoint for longitudinal player tracking -- seeing a player's UUID on each team they've played for, enabling stat aggregation across seasons.

**Confirmed:** 2026-03-07.

---

### GET /me/teams-summary

**Status: CONFIRMED LIVE -- 200 OK. Schema documented in Proxy-Discovered section above -- status upgraded to CONFIRMED. Discovered 2026-03-07.**

```json
{"archived_teams": {"count": 8, "range": {"from_year": 2019, "to_year": 2023}}}
```

**Confirmed:** 2026-03-07.

---

### GET /me/widgets

**Status: CONFIRMED LIVE -- 200 OK. Returns empty widgets array. Discovered 2026-03-07.**

```json
{"widgets": []}
```

**Confirmed:** 2026-03-07.

---

### GET /me/archived-teams

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns the list of archived (prior season) teams the authenticated user was associated with.

#### Response Schema

Bare JSON array of archived team objects. 8 records observed. Schema is identical to `GET /me/teams` response objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID |
| `name` | string | Team display name |
| `team_type` | string | Role of the authenticated user: `"admin"`, etc. |
| `city` | string | City |
| `state` | string | State/province |
| `country` | string | Country |
| `age_group` | string | Age group (e.g., `"13U"`) |
| `competition_level` | string | `"club_travel"`, `"school"`, `"recreational"` |
| `sport` | string | Sport |
| `season_year` | integer | Season year |
| `season_name` | string | Season name (`"summer"`, `"fall"`) |
| `stat_access_level` | string | Stat visibility setting |
| `scorekeeping_access_level` | string | Scorekeeping permission level |
| `streaming_access_level` | string | Streaming permission level |
| `organizations` | array | Organization memberships |
| `ngb` | string | National Governing Body (JSON-encoded string e.g., `"[\"usssa\"]"`) |
| `user_team_associations` | array | User's roles on this team (e.g., `["family", "manager"]`) |
| `team_avatar_image` | string (URL) | Signed CloudFront avatar URL |
| `created_at` | string (ISO 8601) | Team creation date |
| `public_id` | string | Public ID slug for this archived team |
| `archived` | boolean | Always `true` in this response |
| `record` | object | Season record: `{"wins": int, "losses": int, "ties": int}` |

**Observed seasons:** 8 archived teams from 2019 through 2023, including:
- Nebraska Connect 13U (fall 2023, 8-6 record)
- Lincoln Rebels 12U (summer 2023)
- Nebraska Connect 14U (summer 2024)
- Other travel ball teams from 2019-2023

**Key Observations:**
- `ngb` field is a JSON-encoded string (double-serialized), not a native array. Parse with `JSON.parse(team.ngb)` to get the list.
- `archived: true` is always set in this response.
- Same schema as active teams in `GET /me/teams` -- they can be processed by the same code.
- **Coaching relevance: HIGH.** Gives access to historical season team objects for multi-season longitudinal analysis.

**Confirmed:** 2026-03-07.

---

### GET /me/advertising/metadata

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns advertising and targeting metadata for the authenticated user.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `ppid` | string | Publisher Provided ID -- a hashed identifier for ad targeting. Not PII directly but derived from user identity. |
| `do_not_sell` | boolean | Whether the user has opted out of data selling |
| `is_staff` | boolean | Whether the user is a GameChanger staff member (observed: `true` for this account) |
| `targeting` | object | Ad targeting key-value pairs |
| `targeting.gc_ppid_v1` | string | Same as `ppid` |
| `targeting.gc_user-id_v1` | UUID | User UUID (PII -- redact) |
| `targeting.gc_age-groups_v1` | string | Comma-separated list of age groups the user coaches (e.g., `"Under 13,Between 13 - 18"`) |
| `targeting.gc_comp-levels_v1` | string | Comma-separated competition levels (e.g., `"club_travel,school,recreational"`) |
| `targeting.gc_teams-sports_v1` | string | Sports involved (e.g., `"baseball"`) |
| `targeting.gc_subscription-type` | string | Subscription tier (e.g., `"premium"`) |

**Security note:** Contains user UUID in targeting fields -- treat as PII.

**Confirmed:** 2026-03-07.

---

### GET /me/subscription-information

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns subscription summary for the authenticated user. Higher-level view than `GET /subscription/details`.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `best_subscription` | object | The user's best (highest tier) active subscription |
| `best_subscription.type` | string | Subscription type. Observed: `"team_manager"` |
| `best_subscription.provider_type` | string | Billing provider. Observed: `"recurly"` |
| `best_subscription.is_gc_classic` | boolean | Whether this is a legacy GC Classic subscription |
| `best_subscription.is_trial` | boolean | Whether this is a free trial |
| `best_subscription.end_date` | string (ISO 8601) | Subscription expiration date |
| `best_subscription.access_level` | string | Access tier. Observed: `"premium"` |
| `best_subscription.billing_cycle` | string | Billing frequency. Observed: `"year"` |
| `best_subscription.amount_in_cents` | integer | Amount charged per cycle in cents (9999 = $99.99) |
| `best_subscription.provider_details` | object | Provider-specific renewal/cancellation state |
| `best_subscription.provider_details.will_renew` | boolean | Whether the subscription auto-renews |
| `best_subscription.provider_details.was_terminated_by_provider` | boolean | |
| `best_subscription.provider_details.was_terminated_by_staff` | boolean | |
| `highest_access_level` | string | The overall highest access level across all subscriptions |
| `is_free_trial_eligible` | boolean | Whether the user can start a free trial |

**Confirmed:** 2026-03-07.

---

### GET /me/team-tile/{team_id}

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns a compact team summary for the specified team -- the "tile" used in the app's team list UI.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID |
| `name` | string | Team display name |
| `team_type` | string | User's role (`"admin"`, etc.) |
| `sport` | string | Sport |
| `season_year` | integer | Current season year |
| `season_name` | string | Season name |
| `stat_access_level` | string | Stat visibility |
| `streaming_access_level` | string | Streaming permission |
| `organizations` | array | Organization memberships |
| `ngb` | string | NGB (JSON-encoded string) |
| `user_team_associations` | array | User's roles on this team |
| `team_avatar_image` | string or null | Avatar URL (null if no avatar set) |
| `created_at` | string (ISO 8601) | Team creation date |
| `public_id` | string | Public ID slug |
| `archived` | boolean | Whether team is archived |
| `record` | object | `{"wins": int, "losses": int, "ties": int}` |
| `badge_count` | integer | Count of notification badges (e.g., pending actions) |

#### Example Response

```json
{
  "id": "72bb77d8-REDACTED",
  "name": "Lincoln Rebels 14U",
  "sport": "baseball",
  "season_year": 2025,
  "season_name": "summer",
  "stat_access_level": "confirmed_full",
  "archived": false,
  "record": {"wins": 61, "losses": 29, "ties": 2},
  "badge_count": 0
}
```

**Confirmed:** 2026-03-07.

---

### GET /me/related-organizations

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Previously returned HTTP 500 with web headers due to missing pagination parameters. CONFIRMED 2026-03-07 with required parameters.**

Returns organizations that the authenticated user is associated with via team membership (as opposed to direct org membership in `/me/organizations`). 2 organizations observed.

#### Required Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page_starts_at` | integer | YES | Pagination offset. Use `0` for first page. |
| `page_size` | integer | YES | Page size. Use `50`. |

#### Required Headers (in addition to standard auth headers)

| Header | Value | Description |
|--------|-------|-------------|
| `x-pagination` | `true` | Must be present; server returns HTTP 500 without it |

#### Response Schema

Bare JSON array of organization objects. 2 organizations observed.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Organization UUID |
| `city` | string | City |
| `country` | string | Country |
| `end_date` | string (ISO 8601) or null | Organization/season end date |
| `name` | string | Organization display name |
| `ngb` | string | National Governing Body (JSON-encoded string, e.g., `"[\"usssa\"]"`) |
| `season_name` | string | Season name (e.g., `"fall"`, `"summer"`) |
| `season_year` | integer | Season year |
| `sport` | string | Sport |
| `start_date` | string (ISO 8601) or null | Organization/season start date |
| `state` | string | State/province |
| `status` | string | Organization status (e.g., `"active"`) |
| `type` | string | Organization type: `"tournament"`, `"travel"`, `"league"` |
| `public_id` | string | Public ID slug |

#### Example Response

```json
[
  {
    "id": "8881846c-REDACTED",
    "city": "Lincoln",
    "country": "United States",
    "end_date": null,
    "name": "Lincoln Rebels",
    "ngb": "["usssa"]",
    "season_name": "summer",
    "season_year": 2025,
    "sport": "baseball",
    "start_date": null,
    "state": "NE",
    "status": "active",
    "type": "travel",
    "public_id": "8uNxSKmeevE0"
  }
]
```

**Key Observations:**
- Without `?page_starts_at=0&page_size=50` and `x-pagination: true`, server returns HTTP 500.
- Returns organizations accessed via team membership; compare with `/me/organizations` (direct membership).
- 2 orgs observed: a tournament org (USA Prime Prodigy Fall Tourney) and a travel ball org (Lincoln Rebels).
- `ngb` is a JSON-encoded string (double-serialized) -- parse with `JSON.parse(org.ngb)`.
- `public_id` slug can be used with `/organizations/{public_id}` or related org endpoints.
- **Coaching relevance: MEDIUM.** Org discovery endpoint -- use to find org UUIDs for subsequent org-level calls.

**Confirmed:** 2026-03-07. Required params: `?page_starts_at=0&page_size=50` + `x-pagination: true` header.

---

### GET /users/{user_id}

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns profile data for any GameChanger user by UUID. This is the same data visible on public team rosters.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | UUID | User UUID (PII -- treat as sensitive) |

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | User UUID |
| `status` | string | `"active"` or `"inactive"` |
| `first_name` | string | First name (PII) |
| `last_name` | string | Last name (PII) |
| `email` | string | Email address (PII -- redact in all storage) |

**Security:** All fields in this response are PII. Do not log, store, or display without appropriate access controls.

**Confirmed:** 2026-03-07.

---

### GET /users/{user_id}/profile-photo

**Status: HTTP 404 -- no profile photo found. Discovered 2026-03-07.**

Returned 404 with message: `"No profile photo found for user: <uuid>"`. User had no profile photo set.

---

### GET /players/{player_id}/profile-photo

**Status: HTTP 404 -- no profile photo found. Discovered 2026-03-07.**

Returned 404 with message: `"No profile photo found for player: <uuid>"`. Player had no profile photo set.

---

### GET /subscription/details

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Previously observed in proxy -- status upgraded. Discovered 2026-03-07.**

Returns detailed subscription information for the authenticated user.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `highest_tier` | string | User's highest subscription tier. Observed: `"premium"` |
| `is_free_trial_eligible` | boolean | Whether the user can start a free trial |
| `subscriptions` | array | Array of active subscription objects |
| `subscriptions[].id` | UUID | Subscription UUID |
| `subscriptions[].plan` | object | Plan details |
| `subscriptions[].plan.provider` | string | Billing provider (`"recurly"`) |
| `subscriptions[].plan.code` | string | Plan code (e.g., `"premium_year"`) |
| `subscriptions[].plan.level` | integer | Tier level number (3 for premium) |
| `subscriptions[].plan.tier` | string | Tier name (`"premium"`) |
| `subscriptions[].plan.max_allowed_members` | integer | Max users on this subscription |
| `subscriptions[].status` | object | Billing status flags |
| `subscriptions[].status.is_billing` | boolean | Whether billing is active |
| `subscriptions[].status.is_in_free_trial` | boolean | |
| `subscriptions[].status.is_canceled` | boolean | |
| `subscriptions[].status.is_paused` | boolean | |
| `subscriptions[].status.is_expired` | boolean | |
| `subscriptions[].status.is_unpaid` | boolean | |
| `subscriptions[].billing_info` | object | Billing amounts |
| `subscriptions[].billing_info.amount_in_cents` | integer | Amount in cents |
| `subscriptions[].billing_info.currency` | string | Currency code (`"USD"`) |
| `subscriptions[].billing_info.cycle` | string | `"yearly"` or `"monthly"` |
| `subscriptions[].dates.start` | string (ISO 8601) | Subscription start date |
| `subscriptions[].dates.end` | string (ISO 8601) | Subscription end/renewal date |
| `subscriptions[].is_owner` | boolean | Whether this user owns the subscription |
| `subscriptions[].is_gc_classic` | boolean | Legacy subscription flag |
| `subscriptions[].members` | array | Shared subscription members |

**Confirmed:** 2026-03-07.

---

### GET /subscription/recurly/plans

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns all available subscription plans offered by GameChanger via Recurly.

#### Response Schema

Bare JSON array of plan objects. 6 plans observed.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Plan UUID |
| `name` | string | Plan display name |
| `code` | string | Plan code (e.g., `"premium_year"`, `"plus_month"`) |
| `tier` | string | Tier name: `"plus"` or `"premium"` |
| `level` | integer | Tier level (1=plus, 3=premium solo, 7=premium shared) |
| `maximum_allowed_members` | integer | Max users on shared plan |
| `provider` | string | `"recurly"` |
| `billing.interval` | integer | Billing interval count |
| `billing.interval_unit` | string | `"months"` |
| `billing.price_in_cents` | integer | Price per cycle in cents |
| `billing.currency` | string | `"USD"` |
| `free_trial.length_in_days` | integer | Free trial length |
| `free_trial.is_user_eligible` | boolean | Whether this user can start a trial for this plan |

**Observed plans (2026-03-07):**
- Premium Yearly Shared Plan: $179.99/yr, up to 4 users
- Premium Monthly Shared Plan: $24.99/mo, up to 4 users
- Plus Monthly Plan: $9.99/mo, 1 user
- Plus Yearly Plan: $39.99/yr, 1 user
- Premium Yearly Plan: $99.99/yr, 1 user
- Premium Monthly Plan: $14.99/mo, 1 user

**Confirmed:** 2026-03-07.

---

### GET /search/history

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns the authenticated user's recent search history. Contains team search results with public metadata.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `max_results` | integer | Maximum history entries (observed: `10`) |
| `history` | array | Ordered list of recent searches (most recent first) |
| `history[].type` | string | Result type. Observed: `"team"` |
| `history[].result` | object | The search result object |

**`result` object (when `type = "team"`):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Team UUID |
| `public_id` | string | Team public ID slug |
| `name` | string | Team display name |
| `sport` | string | Sport |
| `season` | object | `{"name": "summer", "year": 2019}` |
| `location` | object | `{"city": "...", "state": "...", "country": "..."}` |
| `staff` | array of strings | Coach/staff names for this team |
| `number_of_players` | integer | Player count on the team |
| `avatar_url` | string (URL, optional) | Signed CloudFront avatar URL |

**Note:** The `staff` array contains plain name strings, not UUIDs. No PII beyond publicly-visible team staff names.

**Coaching relevance:** Low for analytics. High for discovering team UUIDs from team names when a user has searched for those teams. The `public_id` and `id` fields enable bridging to all other endpoints.

**Confirmed:** 2026-03-07.

---

### GET /announcements/user/read-status

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Discovered 2026-03-07.**

Returns the read status of in-app announcements for the authenticated user.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `read_status` | string | `"read"` if all announcements have been read, `"unread"` otherwise |

#### Example Response

```json
{"read_status": "read"}
```

**Confirmed:** 2026-03-07.

---

### GET /sync-topics/me/updated-topics

**Status: CONFIRMED LIVE -- 200 OK. Full schema documented. Previously observed in proxy -- status upgraded. Discovered 2026-03-07.**

Returns the real-time sync state for the authenticated user. Used by the app's live sync mechanism.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Sync status. Observed: `"update-all"` |
| `updates` | array | Array of specific topic updates (empty array when status is `"update-all"`) |
| `next_cursor` | string | Cursor for the next poll. Format: `v2_{sequence}_{timestamp}_{user_id}_{counter}_{uuid}` |

#### Example Response

```json
{
  "status": "update-all",
  "updates": [],
  "next_cursor": "v2_72081_1750259143790_e07b2d06-REDACTED_0_5e87d41c-REDACTED"
}
```

**Note:** `"update-all"` status means the client should refresh all data rather than process incremental updates. The `next_cursor` contains the user UUID -- treat as PII.

**Confirmed:** 2026-03-07.

---

## Proxy-Discovered Endpoints (2026-03-05)

The following endpoints were observed in mitmproxy traffic captures from the GameChanger iOS app ("Odyssey") on 2026-03-05. These are **observed but not yet fully documented** -- response schemas are not confirmed, Accept headers are not captured, and behavior has not been verified via independent curl calls. Each entry documents what was learned from the traffic log alone: HTTP method, path pattern, observed query keys, status codes, and request Content-Type.

**Source:** `proxy/data/endpoint-log.jsonl` captured 2026-03-05 via mitmproxy intercept of iOS Odyssey app traffic.

**Status convention:** All entries in this section are `OBSERVED (proxy log only)` unless noted otherwise. An endpoint is not `CONFIRMED` until it has been exercised via an independent curl call with response schema documented.

**Request Content-Type observed on all Odyssey GET requests:** `application/vnd.gc.com.none+json; version=0.0.0` (same as web browser).

**Note on 404 endpoints:** Several endpoints returned HTTP 404 in the capture. These are documented to record that the path pattern exists in client code but the resource did not exist for the specific UUID at the time of capture. The endpoint pattern itself may be valid.

---

### Sync / Realtime

#### GET /sync-topics/me/updated-topics

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

- **Response:** `{"status": "update-all", "updates": [], "next_cursor": "v2_..."}` -- real-time sync cursor for incremental polling.
- **Query keys observed:** `cursor`, `timeout`
- **Notes:** The `cursor` parameter is likely a sequence position, `timeout` likely the long-poll timeout in seconds. This endpoint is the app's heartbeat. Not relevant to data ingestion.
- **Discovered:** 2026-03-05

#### POST /sync-topics/updates

**Status:** OBSERVED (proxy log, 11 hits, status 200). Batch sync update push.

- **Request Content-Type:** `application/vnd.gc.com.post_batch_scoped_sync_updates+json; version=0.0.0`
- **Notes:** Used by the app to push state updates. Not relevant to data ingestion.
- **Discovered:** 2026-03-05

#### POST /sync-topics/topic-subscriptions

**Status:** OBSERVED (proxy log, 1 hit, status 201). Subscribe to a sync topic.

- **Request Content-Type:** Not captured (POST body not in log)
- **Notes:** Part of the app's real-time notification infrastructure. Not relevant to data ingestion.
- **Discovered:** 2026-03-05

---

### Announcements

#### GET /announcements/user/read-status

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Previously observed with 304 only in proxy capture.

- **Response:** `{"read_status": "read"}` -- see full schema in Confirmed Endpoints (2026-03-07) section.
- **Query keys observed:** none
- **Discovered:** 2026-03-05

---

### Subscription

#### GET /subscription/details

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Previously observed with 304 only in proxy capture.

- **Response:** Full subscription object with plan details, status flags, billing info, and dates. See full schema in Confirmed Endpoints (2026-03-07) section.
- **Query keys observed:** none
- **Discovered:** 2026-03-05

#### GET /me/subscription-information

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema documented in Confirmed Endpoints section.

- **Response:** `best_subscription` object + `highest_access_level` + `is_free_trial_eligible`. Different structure from `GET /subscription/details` -- more concise.
- **Query keys observed:** none
- **Discovered:** 2026-03-05

---

### Me (additional)

These endpoints extend the `/me/` namespace beyond `GET /me/user` and `GET /me/teams` (already documented).

#### GET /me/teams-summary

**Status:** CONFIRMED (web headers, schema documented).

Lightweight summary of the authenticated user's team history. Returns archived and active team counts with a year range -- much smaller payload than `GET /me/teams`.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

A single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `archived_teams` | object | Summary of archived teams |
| `archived_teams.count` | integer | Number of archived teams (observed: `8`) |
| `archived_teams.range` | object | Year range of archived teams |
| `archived_teams.range.from_year` | integer | Earliest season year (observed: `2019`) |
| `archived_teams.range.to_year` | integer | Latest season year (observed: `2023`) |

**Example (redacted):**

```json
{
  "archived_teams": {
    "count": 8,
    "range": {
      "from_year": 2019,
      "to_year": 2023
    }
  }
}
```

**Key Observations:**
- Very lightweight -- useful for a quick "how many teams does this user have?" check without loading full team objects.
- Only `archived_teams` was present; no `active_teams` counterpart observed. Active teams may not appear in this endpoint, or they may appear under a different key when the user has active teams.
- **Coaching relevance:** Low. Use `GET /me/teams` for full team data.

#### GET /me/associated-players

**Status:** CONFIRMED (web headers, schema documented).

Returns all player records associated with the authenticated user's account across all teams. This is a **goldmine for longitudinal player tracking** -- it maps a single real person across multiple teams, seasons, and age groups, each with a different `player_id` UUID.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

A single JSON object with three top-level keys:

| Field | Type | Description |
|-------|------|-------------|
| `teams` | object (map) | Map of `team_id` (UUID) -> team summary object |
| `players` | object (map) | Map of `player_id` (UUID) -> player record object |
| `associations` | array | Array of association objects linking accounts to players |

**`teams` map values:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Team name. **PII -- redact in stored files.** |
| `sport` | string | Sport type (observed: `"baseball"`) |

**`players` map values:**

| Field | Type | Description |
|-------|------|-------------|
| `first_name` | string | Player first name. **PII -- redact in stored files.** |
| `last_name` | string | Player last name. **PII -- redact in stored files.** |
| `team_id` | string (UUID) | The team this player record belongs to. References a key in the `teams` map. |

**`associations` array elements:**

| Field | Type | Description |
|-------|------|-------------|
| `relation` | string | Relationship type. Observed: `"primary"` |
| `player_id` | string (UUID) | References a key in the `players` map |

**Example (redacted):**

```json
{
  "teams": {
    "<team-uuid-1>": {"name": "Team Name 8U", "sport": "baseball"},
    "<team-uuid-2>": {"name": "Team Name 10U", "sport": "baseball"}
  },
  "players": {
    "<player-uuid-1>": {"first_name": "REDACTED", "last_name": "REDACTED", "team_id": "<team-uuid-1>"},
    "<player-uuid-2>": {"first_name": "REDACTED", "last_name": "REDACTED", "team_id": "<team-uuid-2>"}
  },
  "associations": [
    {"relation": "primary", "player_id": "<player-uuid-1>"},
    {"relation": "primary", "player_id": "<player-uuid-2>"}
  ]
}
```

**Key Observations:**
- In the observed payload, one player appears across 13 teams (8U through 14U, 2019-2026) with a **different `player_id` UUID per team**. This is the key to longitudinal player tracking -- same real person, different GC player records per team/season.
- A second player appears across 2 teams with different UUIDs.
- All associations have `relation: "primary"` -- no other relation types observed.
- The `teams` map only includes `name` and `sport` -- no season, year, or location data. Cross-reference with `GET /me/teams` or `GET /me/archived-teams` for full team details.
- **PII sensitivity:** Contains real player names. Redact in all stored files and documentation.
- **Coaching relevance:** Critical (Tier 1). Enables cross-team, cross-season player identity resolution -- essential for longitudinal player development tracking.

#### GET /me/archived-teams

**Status:** CONFIRMED (web headers, schema documented).

Returns archived (inactive/past season) teams for the authenticated user. Response is a **bare JSON array** -- same schema as `GET /me/teams`.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

Bare JSON array of team objects. Each element has the same schema as `GET /me/teams` (see [Schema: me-teams](#schema-me-teams)). Observed: 8 archived teams spanning 2019-2023.

Key fields per team object:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Team UUID |
| `name` | string | Team name. **PII -- redact.** |
| `team_type` | string | Observed: `"admin"` |
| `city` | string | City |
| `state` | string | State code |
| `country` | string | Country name (observed: `"United States"`, `"USA"` -- inconsistent) |
| `age_group` | string | Age group (e.g., `"8U"`, `"10U"`, `"14U"`) |
| `competition_level` | string | Observed: `"club_travel"` |
| `sport` | string | Observed: `"baseball"` |
| `season_year` | integer | Season year (e.g., `2019`, `2023`) |
| `season_name` | string | Season name (e.g., `"spring"`, `"summer"`, `"fall"`) |
| `stat_access_level` | string | Observed: `"confirmed_full"`, `"confirmed_individual"` |
| `scorekeeping_access_level` | string | Observed: `"staff_only"` |
| `streaming_access_level` | string | Observed: `"staff_only"`, `"confirmed_members"` |
| `paid_access_level` | string (optional) | Observed: `"premium"`. Not present on all teams. |
| `organizations` | array | Organization associations. Observed: empty `[]` for all archived teams. |
| `ngb` | string | National governing body. JSON-encoded array (e.g., `"[\"usssa\"]"`, `"[]"`). |
| `user_team_associations` | array of strings | User's roles on this team. Observed: `["family", "manager"]`, `["family"]` |
| `team_avatar_image` | string (URL, optional) | CloudFront signed URL for team avatar. Not present on all teams. |
| `created_at` | string (ISO 8601) | Team creation timestamp |
| `public_id` | string | Short alphanumeric public ID slug (e.g., `"SGjVrqy6YZOi"`) |
| `archived` | boolean | Always `true` for this endpoint |
| `record` | object | Team win/loss/tie record: `{"wins": int, "losses": int, "ties": int}` |

**Key Observations:**
- Identical schema to `GET /me/teams` -- both return bare arrays of team objects.
- All teams have `archived: true`.
- The `ngb` field is a JSON string containing an array -- not a native JSON array. Must be parsed as string then decoded.
- `country` values are inconsistent: `"United States"` vs `"USA"` across teams.
- `paid_access_level` is only present on some teams (older ones in this dataset).
- **Coaching relevance:** Medium-High. Access to historical team data enables season-over-season analysis. Stats for archived teams may still be accessible via team-scoped endpoints.

#### GET /me/related-organizations

**Status:** CONFIRMED (2026-03-07). Previously HTTP 500 (web headers). Fixed with `?page_starts_at=0&page_size=50` + `x-pagination: true` header.

Returns organizations the authenticated user is associated with via team membership. Full schema documented in the Confirmed Endpoints section above.

- **Accept header:** not yet confirmed
- **Required query params:** `?page_starts_at=0&page_size=50`
- **Required header:** `x-pagination: true`
- **Discovered:** 2026-03-05
- **Coaching relevance:** Medium. Organization membership data for org discovery. 2 orgs returned for this account.

#### GET /me/schedule

**Status:** CONFIRMED (web headers, schema documented).

Cross-team unified schedule for the authenticated user. Returns events from **all** teams the user belongs to in a single response. Large payload (34K+ tokens observed).

- **Accept header:** not yet confirmed
- **Query keys observed:** `showAllRSVPs`
- **Discovered:** 2026-03-05

**Response Schema:**

Bare JSON array of event objects. Each event represents a game, practice, or other team event.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Event UUID |
| `team_id` | string (UUID) | Team this event belongs to |
| `event_type` | string | Event type. Observed: `"game"`, `"practice"`, `"other"` |
| `title` | string | Event title (e.g., team name for games, `"Practice"` for practices) |
| `sub_title` | string or null | Subtitle (e.g., opponent name for games) |
| `start_date` | string (ISO 8601) | Event start datetime |
| `end_date` | string (ISO 8601) or null | Event end datetime |
| `location` | object or null | Location details with `name`, `address` fields |
| `game_stream_id` | string (UUID) or null | Game stream ID (for games only; null for practices/other) |
| `is_home` | boolean or null | Whether this is a home game (for games only) |
| `opponent` | object or null | Opponent details (for games only) |
| `rsvp_status` | string or null | RSVP status for this event |
| `notes` | string or null | Event notes |

**Key Observations:**
- Very large payload -- the observed response contains events across all 13+ teams for the authenticated user.
- Spans multiple seasons and years (archived teams included).
- Includes both past and future events.
- The `showAllRSVPs` query parameter suggests filtering is available but was not tested.
- **Coaching relevance:** Low. Use `GET /teams/{team_id}/schedule` for per-team schedules. This cross-team view is more useful for the app's unified calendar than for coaching analytics.

#### GET /me/permissions

**Status:** CONFIRMED (2026-03-07). Previously returned HTTP 501 "Not Implemented" without query params. Works with `?entityId={uuid}&entityType=team`. Full schema in Confirmed Endpoints section.

- **Required query params:** `?entityId={entity_uuid}&entityType={entity_type}`
- **Notes:** High-frequency endpoint -- app calls this across many entities. Returns all permissions the authenticated user has for a specific entity. 18 permissions observed for a team admin.
- **Discovered:** 2026-03-05

#### GET /me/permissions/bulk

**Status:** OBSERVED (proxy log, 4 hits, status 200 and 304). Batch permission check.

- **Query keys observed:** `childType`, `parentId`, `parentType`, `permissions`
- **Notes:** Bulk variant of `/me/permissions`. Checks permissions for a class of child entities under a parent. Not useful for data ingestion.
- **Discovered:** 2026-03-05

#### GET /me/external-calendar-sync-url/team/{team_id}

**Status:** OBSERVED (proxy log, 1 hit, status 200). Calendar sync URL for a specific team.

- **Path parameters:** `team_id` (UUID)
- **Query keys observed:** none
- **Notes:** Returns a URL for subscribing to the team's schedule in an external calendar app (iCal/Google Calendar). Not relevant to data ingestion.
- **Discovered:** 2026-03-05

#### GET /me/advertising/metadata

**Status:** OBSERVED (proxy log, 1 hit, status 304). Advertising metadata for the app.

- **Notes:** Not relevant to data ingestion.
- **Discovered:** 2026-03-05

#### GET /me/widgets

**Status:** CONFIRMED (web headers, schema documented).

Returns widget configuration for the app's home screen. Contains live stream information when a team has an active stream.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

A single JSON object with a `widgets` array.

| Field | Type | Description |
|-------|------|-------------|
| `widgets` | array | Array of widget objects |

**Widget object (observed type: `live_stream`):**

| Field | Type | Description |
|-------|------|-------------|
| `live_stream` | object | Live stream widget data |
| `live_stream.team_id` | string (UUID) | Team UUID |
| `live_stream.sport` | string | Observed: `"baseball"` |
| `live_stream.event_id` | string (UUID) | Event UUID |
| `live_stream.event_kind` | string | Event type. Observed: `"practice"` |
| `live_stream.stream_id` | string (UUID) | Stream UUID |
| `live_stream.channel_id` | string (UUID) | Channel UUID |
| `live_stream.title` | string | Widget title (e.g., `"Practice"`) |
| `live_stream.thumbnail_url` | string (URL) | VOD archive thumbnail URL |
| `live_stream.team_name` | string | Team name. **PII -- redact.** |
| `live_stream.streamer_name` | string | Name of the streamer. **PII -- redact.** |
| `live_stream.is_user` | boolean | Whether the streamer is the authenticated user |
| `live_stream.is_staff` | boolean | Whether the streamer is team staff |
| `live_stream.is_accessible` | boolean | Whether the stream is accessible |
| `live_stream.shared_by_opponent` | boolean | Whether the stream was shared by the opponent |
| `live_stream.can_end_stream` | boolean | Whether the user can end this stream |
| `live_stream.is_test_stream` | boolean | Whether this is a test stream |

**Key Observations:**
- The `widgets` array can be empty when no active streams or relevant widgets exist.
- Only one widget type observed (`live_stream`). Other widget types may exist.
- **Coaching relevance:** Low. Widget configuration is for the app UI, not coaching analytics.

#### PATCH /me/user

**Status:** OBSERVED (proxy log, 1 hit, status 200). Update authenticated user profile.

- **Query keys observed:** none
- **Notes:** Write endpoint -- updates the user's own profile (likely name, preferences, etc.). Not relevant to read-only data ingestion.
- **Discovered:** 2026-03-05

---

### Organizations

The `/organizations/{org_id}` path family was entirely new in this capture. An organization UUID (`8881846c-7a9c-4230-ac17-09627aac7f59`) appears in multiple endpoints -- this is an organization the authenticated user belongs to (likely the travel ball program hosting the team).

**Organization UUID observed:** `8881846c-7a9c-4230-ac17-09627aac7f59` (present in `organizations` field of `/me/teams` team objects).

**Path parameter:** All endpoints take `{org_id}` (UUID) -- the organization identifier.

#### GET /organizations/{org_id}/teams

**Status:** CONFIRMED (2026-03-07). Previously HTTP 500 (web headers). Fixed with `?page_starts_at=0&page_size=50` + `x-pagination: true` header.

Returns all teams in an organization. Full schema documented in the Confirmed Endpoints section above. 7 teams observed.

- **Accept header:** not yet confirmed
- **Required query params:** `?page_starts_at=0&page_size=50`
- **Required header:** `x-pagination: true`
- **Priority:** HIGH -- confirmed working; can enumerate all org teams in one call.
- **Coaching relevance:** High. Discovery of all teams under an org eliminates per-team iteration.
- **Discovered:** 2026-03-05

#### GET /organizations/{org_id}/events

**Status:** CONFIRMED (web headers, empty response).

Cross-team event schedule at the organization level.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response:** Returned an empty array `[]` for the travel ball org (no current season events). Schema likely mirrors event objects from `GET /me/schedule` or `GET /teams/{team_id}/schedule`, but cannot be confirmed without a non-empty response.

- **Coaching relevance:** Medium. Organization-scoped schedule could aggregate all team events. Blocked by empty data for the observed org.

#### GET /organizations/{org_id}/game-summaries

**Status:** CONFIRMED (web headers, empty response).

Aggregated game summaries across all teams in an organization.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response:** Returned an empty array `[]` for the travel ball org (no current season games). Schema likely matches `GET /teams/{team_id}/game-summaries`, but cannot be confirmed without a non-empty response.

- **Priority:** HIGH -- if available for LSB coaching account, could eliminate per-team game-summary calls.
- **Coaching relevance:** High. All games across all program teams in one call.

#### GET /organizations/{org_id}/standings

**Status:** CONFIRMED (web headers, schema documented).

Returns standings for all teams within an organization. Each team has home/away/overall/last10 records, winning percentage, run differential, and streak information.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

Bare JSON array of standing objects. Observed: 7 teams.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | string (UUID) | Team UUID |
| `home` | object | Home record: `{"wins": int, "losses": int, "ties": int}` |
| `away` | object | Away record: `{"wins": int, "losses": int, "ties": int}` |
| `overall` | object | Overall record: `{"wins": int, "losses": int, "ties": int}` |
| `last10` | object | Last 10 games record: `{"wins": int, "losses": int, "ties": int}` |
| `winning_pct` | float | Overall winning percentage (0.0 to 1.0). Observed: `0.0` to `0.918...` |
| `runs` | object | Run statistics |
| `runs.scored` | integer | Total runs scored |
| `runs.allowed` | integer | Total runs allowed |
| `runs.differential` | integer | Run differential (scored - allowed) |
| `streak` | object | Current streak |
| `streak.count` | integer | Streak length |
| `streak.type` | string | Streak type. Observed: `"win"`, `"loss"` |

**Example (redacted):**

```json
[
  {
    "team_id": "<team-uuid>",
    "home": {"wins": 33, "losses": 12, "ties": 1},
    "away": {"wins": 28, "losses": 17, "ties": 1},
    "overall": {"wins": 61, "losses": 29, "ties": 2},
    "last10": {"wins": 5, "losses": 4, "ties": 1},
    "winning_pct": 0.674,
    "runs": {"scored": 645, "allowed": 448, "differential": 197},
    "streak": {"count": 1, "type": "loss"}
  }
]
```

**Key Observations:**
- The `team_id` values are `progenitor_team_id` values (matching `org-opponents.json`), not the `root_team_id` or the team `id` from `/me/teams`.
- All 7 teams had all-zero records in the `org-standings.json` file (current season, no games played yet). The `org-team-records.json` file had the same structure with historical non-zero records -- likely the all-time or most-recent-season records.
- **Coaching relevance:** Critical (Tier 1). Standings with run differential and streaks are core scouting data for game preparation.

#### GET /organizations/{org_id}/opponents

**Status:** CONFIRMED (web headers, schema documented).

Returns all opponents across all teams in the organization.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

Bare JSON array of opponent objects. Observed: 7 opponents.

| Field | Type | Description |
|-------|------|-------------|
| `root_team_id` | string (UUID) | The opponent's root team UUID (used as `team_id` in standings) |
| `progenitor_team_id` | string (UUID) | The progenitor (original) team UUID |
| `owning_team_id` | string (UUID) | Organization UUID that owns this opponent record |
| `name` | string | Opponent team name. **PII -- redact.** |
| `is_hidden` | boolean | Whether this opponent is hidden (observed: all `false`) |

**Example (redacted):**

```json
[
  {
    "root_team_id": "<team-uuid>",
    "progenitor_team_id": "<team-uuid>",
    "owning_team_id": "<org-uuid>",
    "name": "REDACTED Team 9U",
    "is_hidden": false
  }
]
```

**Key Observations:**
- Three levels of team identity: `root_team_id` (the opponent record's own ID), `progenitor_team_id` (the original team this opponent derives from), and `owning_team_id` (always the org UUID -- opponents are scoped to the org, not individual teams).
- The `owning_team_id` matches the organization UUID, confirming this is an org-level opponent registry.
- **Coaching relevance:** High. Organization-level opponent list for scouting. Cross-reference with standings for a complete scouting picture.

#### GET /organizations/{org_id}/opponent-players

**Status:** HTTP 500 (web headers). Paginated (per proxy log observations).

Returns opponent player rosters at the organization level. **Returns HTTP 500 with web browser headers.**

- **Accept header:** not yet confirmed
- **Error response:** `{"error":"Cannot read properties of undefined (reading 'page_size')"}`
- **Query keys observed:** `start_at` (pagination cursor)
- **Proxy log:** 2 hits (status 200 in iOS proxy capture, paginated)
- **Notes:** Different error from the `page_starts_at` errors on `/teams` and `/me/related-organizations`. This endpoint has its own pagination parameter issue. See IDEA-011 for investigation. Schema not available from web capture.
- **Coaching relevance:** High. Bulk opponent player data for scouting. Blocked by HTTP 500.
- **Discovered:** 2026-03-05

#### GET /organizations/{org_id}/team-records

**Status:** CONFIRMED (web headers, schema documented).

Returns historical win/loss records for all teams in the organization. Same schema as `/organizations/{org_id}/standings` but with non-zero historical data.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

Same structure as `GET /organizations/{org_id}/standings` (see above). Bare JSON array of standing objects with `team_id`, `home`, `away`, `overall`, `last10`, `winning_pct`, `runs`, and `streak`.

**Key Observations:**
- In the observed data, `org-standings.json` had all-zero records (new season, no games yet) while `org-team-records.json` had full historical records. The two endpoints may represent current-season vs. all-time views, or `team-records` may aggregate across all seasons.
- The `team_id` values match `progenitor_team_id` from `org-opponents.json`.
- **Coaching relevance:** High. Historical records complement current standings for trend analysis.

#### GET /organizations/{org_id}/users

**Status:** CONFIRMED (web headers, schema documented).

Returns users associated with the organization.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

A single JSON object (not an array).

| Field | Type | Description |
|-------|------|-------------|
| `organization_id` | string (UUID) | The organization UUID |
| `users` | array | Array of user association objects |

**User association object:**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string (UUID) | User UUID. **PII -- redact.** |
| `association` | string | User's role in the organization. Observed: `"admin"` |

**Example (redacted):**

```json
{
  "organization_id": "<org-uuid>",
  "users": [
    {"user_id": "<user-uuid>", "association": "admin"}
  ]
}
```

**Key Observations:**
- Only one user (admin) observed. Other association types likely exist (e.g., `"coach"`, `"member"`).
- **PII sensitivity:** Contains user UUIDs. Redact in stored files.
- **Coaching relevance:** Low. Admin/membership data, not coaching analytics.

#### GET /organizations/{org_id}/avatar-image

**Status:** OBSERVED (proxy log, 2 hits, status 200). Organization avatar/logo image.

- **Query keys observed:** none
- **Notes:** Returns organization avatar image metadata (likely a URL). Schema not captured in bulk collection.
- **Discovered:** 2026-03-05

#### GET /organizations/{org_id}/scoped-features

**Status:** CONFIRMED (web headers, schema documented).

Returns feature flags scoped to the organization. Returned an empty feature set.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

A single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `scoped_features` | object | Map of feature flag names to their values. Observed: empty `{}` |

**Example:**

```json
{"scoped_features": {}}
```

- **Coaching relevance:** None. Feature flag infrastructure, not data.

---

### Teams (additional)

These team-scoped endpoints were observed in the proxy log but are not yet in the spec.

#### GET /teams/{team_id}/opponents/players

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section. 758 records, 61 opponent teams.

- **Query keys observed:** `start_at` (pagination cursor -- not required; full 758-record response received without pagination params in bulk probe)
- **Confirmed:** 2026-03-07
- **Discovered:** 2026-03-05
- **Schema:** See Confirmed Endpoints section for full field table. Key difference from proxy capture: fields are `team_id`, `player_id`, `person{id, first_name, last_name}`, `attributes{player_number, status}`, `bats{batting_side, throwing_hand}` -- NOT the old `id`/`number`/`positions`/`bats`/`throws` flat schema.
- **Status values:** `"active"` and `"removed"`. Filter to `"active"` only for scouting.
- **`bats` nullability:** `null` for 30 removed players; `batting_side`/`throwing_hand` can also be individually `null` if not entered. `batting_side` `"both"` observed (= switch hitter).
- **Coaching relevance:** Critical (Tier 1). Bulk opponent player data is foundational for scouting reports.

#### GET /teams/{team_id}/avatar-image

**Status:** OBSERVED (proxy log, 7 hits, status 200). Team avatar/logo image metadata.

- **Query keys observed:** none
- **Notes:** Returns image metadata (likely a signed URL) for the team's avatar. Schema not captured.
- **Discovered:** 2026-03-05

#### GET /teams/{team_id}/external-associations

**Status:** CONFIRMED (web headers, schema documented). External system associations for a team.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response:** Returned an empty array `[]` for the observed team. Schema likely contains objects representing links to external systems (MaxPreps, USSSA, etc.) but cannot be confirmed without a non-empty response.

- **Coaching relevance:** Low. External system links, not coaching data.

#### GET /teams/{team_id}/public-url

**Status:** OBSERVED (proxy log, 1 hit, status 200). Public URL for the team.

- **Query keys observed:** none
- **Notes:** Returns the public web URL for the team's GameChanger profile (e.g., `https://web.gc.com/teams/{public_id}`). Likely a single-field response similar to `GET /teams/{team_id}/public-team-profile-id`. Schema not captured.
- **Discovered:** 2026-03-05

#### GET /teams/{team_id}/relationships

**Status:** CONFIRMED (web headers, schema documented). User-to-player relationship graph for a team.

- **Accept header:** not yet confirmed
- **Query keys observed:** `start_at` (pagination cursor)
- **Discovered:** 2026-03-05

**Response Schema:**

Bare JSON array of relationship objects. Maps users (parents/guardians) to players on the team.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | string (UUID) | Team UUID (same for all records in response) |
| `user_id` | string (UUID) | User UUID (parent/guardian). **PII -- redact.** |
| `player_id` | string (UUID) | Player UUID the user is associated with |
| `relationship` | string | Relationship type. Observed: `"primary"`, `"self"` |

**Key Observations:**
- Multiple users can be associated with the same player (e.g., both parents linked to one player's account).
- The `"self"` relationship type indicates a player who manages their own account (observed for some older players).
- This is a user-player mapping, not team-to-team. Useful for understanding family/guardian structure but not directly for coaching analytics.
- **PII sensitivity:** Contains user UUIDs mapped to player UUIDs. Redact in stored files.
- **Coaching relevance:** Low. Parent/guardian data, not performance data.

#### GET /teams/{team_id}/relationships/requests

**Status:** OBSERVED (proxy log, 3 hits, status 200). Pending relationship requests for a team.

- **Query keys observed:** none
- **Notes:** Incoming/outgoing team relationship requests. Not relevant to data ingestion.
- **Discovered:** 2026-03-05

#### GET /teams/{team_id}/scoped-features

**Status:** CONFIRMED (web headers, schema documented). Feature flags scoped to a specific team.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response:** Same schema as `GET /organizations/{org_id}/scoped-features` -- a single JSON object with `scoped_features` map. Returned empty `{"scoped_features": {}}` for the observed team.

- **Coaching relevance:** None. Feature flag infrastructure.

#### GET /teams/{team_id}/team-notification-setting

**Status:** CONFIRMED (web headers, schema documented). Notification settings for a team.

- **Accept header:** not yet confirmed
- **Discovered:** 2026-03-05

**Response Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | string (UUID) | Team UUID |
| `event_reminder_setting` | string | Notification setting. Observed: `"never"` |

**Example:**

```json
{"team_id": "<team-uuid>", "event_reminder_setting": "never"}
```

- **Coaching relevance:** None. Notification preferences.

#### GET /teams/{team_id}/share-with-opponent/opt-outs

**Status:** OBSERVED (proxy log, 1 hit, status 200). Opt-out list for sharing data with opponents.

- **Query keys observed:** none
- **Notes:** Privacy control -- tracks which opponents a team has opted out of sharing stats with. Could be relevant for understanding data availability (if an opponent has opted out, their data may be limited). Schema not captured.
- **Discovered:** 2026-03-05

#### GET /teams/{team_id}/video-stream/videos

**Status:** OBSERVED (proxy log, 7 hits, status 200 and 304). Video list for a team (distinct from `/video-stream/assets`).

- **Query keys observed:** none
- **Notes:** May return a different level of video metadata than `/video-stream/assets`. Schema not captured. Could be a summary view vs. the per-asset detail in `/assets`.
- **Discovered:** 2026-03-05

#### GET /teams/{team_id}/users/count

**Status:** OBSERVED (proxy log, 4 hits, status 200 and 304). Count of users on a team.

- **Query keys observed:** `associations`
- **Notes:** Returns a count (not the full list) of team users. `associations` query parameter likely filters by association/role type. More efficient than fetching the full `/users` list when only a count is needed.
- **Discovered:** 2026-03-05

#### POST /teams/{team_id}/follow

**Status:** OBSERVED (proxy log, 1 hit, status 204). Follow a team (subscribe to updates).

- **Notes:** Write endpoint -- causes the authenticated user to follow the specified team. Returns 204 No Content on success. Not relevant to data ingestion.
- **Discovered:** 2026-03-05

---

### Events (additional)

#### GET /events/{event_id}/highlight-reel

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section (`GET /events/{event_id}/highlight-reel`).

- **Path parameters:** `event_id` (UUID from schedule)
- **Confirmed:** 2026-03-07
- **Discovered:** 2026-03-05

**Response Schema:**

A single JSON object containing a structured highlight playlist with CloudFront signed video URLs.

| Field | Type | Description |
|-------|------|-------------|
| `multi_asset_video_id` | string (UUID) | Multi-asset video identifier (matches event_id) |
| `event_id` | string (UUID) | Event UUID |
| `status` | string | Highlight reel status. Observed: `"finalized"` |
| `type` | string | Asset type. Observed: `"event"` |
| `playlist` | array | Ordered list of video segments |
| `duration` | integer | Total duration in seconds |
| `thumbnail_url` | string (URL) | CloudFront signed URL for thumbnail |
| `small_thumbnail_url` | string | Small thumbnail URL (observed: empty string) |

**Playlist entry object:**

| Field | Type | Description |
|-------|------|-------------|
| `media_type` | string | Observed: `"video"` |
| `url` | string (URL) | HLS (.m3u8) video segment URL |
| `is_transition` | boolean | Whether this is a transition plate (e.g., inning marker) |
| `clip_id` | string (UUID, optional) | Clip identifier (absent on transitions) |
| `pbp_id` | string (UUID, optional) | Play-by-play event ID this clip corresponds to |
| `cookies` | object | CloudFront signed cookies for authenticated playback |

**Key Observations:**
- The playlist interleaves transition plates (e.g., "inning_1.m3u8") with actual play clips, creating a structured highlight video.
- Each clip maps to a `pbp_id` (play-by-play event), enabling cross-reference with `GET /game-stream-processing/{id}/plays`.
- All video URLs are CloudFront-signed with time-limited access.
- **Coaching relevance:** Low for stat analytics. Could be useful for video review but not needed for data ingestion.

#### GET /teams/{team_id}/schedule/events/{event_id}/player-stats

**Status: CONFIRMED LIVE (2026-03-05, HTTP 200).** Full schema documented in the main Endpoints section -- see [GET /teams/{team_id}/schedule/events/{event_id}/player-stats](#get-teamsteam_idscheduleventsevent_idplayer-stats).

- **Path parameters:** `team_id` (UUID), `event_id` (UUID)
- **Query keys observed:** none
- **Notes:** Confirmed 2026-03-05 via curl. Returns both teams' per-game and cumulative player stats plus spray chart data in a single 106 KB response. Eliminates the two-step game_stream_id resolution. The response also includes `stream_id` (= game_stream_id) inline. Accept header: `application/json, text/plain, */*` (not vendor-typed). Raw sample at `data/raw/player-stats-sample.json`.
- **Priority:** CRITICAL -- confirmed as the optimal ingestion path for per-game per-player stats.
- **Discovered:** 2026-03-05

#### GET /teams/{team_id}/schedule/events/{event_id}/rsvp-responses

**Status:** CONFIRMED (web headers, schema documented). RSVP responses for a scheduled event.

- **Accept header:** not yet confirmed
- **Path parameters:** `team_id` (UUID), `event_id` (UUID)
- **Discovered:** 2026-03-05

**Response:** Returned an empty array `[]` for the observed event. Schema likely contains RSVP objects with user_id, status, and timestamp when RSVPs exist.

- **Coaching relevance:** None. Attendance tracking, not performance data.

#### GET /teams/{team_id}/schedule/events/{event_id}/video-stream

**Status:** CONFIRMED (web headers, schema documented). Video stream metadata for a specific event.

- **Accept header:** not yet confirmed
- **Path parameters:** `team_id` (UUID), `event_id` (UUID)
- **Discovered:** 2026-03-05

**Response Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `stream_id` | string (UUID) | Stream UUID |
| `schedule_event_id` | string (UUID) | Event UUID |
| `disabled` | boolean | Whether streaming is disabled |
| `is_muted` | boolean | Whether audio is muted |
| `team_id` | string (UUID) | Team UUID |
| `user_id` | string (UUID) | Streamer's user UUID. **PII.** |
| `viewer_count` | integer | Current/final viewer count |
| `audience_type` | string | Observed: `"players_family"` |
| `is_playable` | boolean | Whether the stream can be played back |
| `status` | string | Stream status. Observed: `"ended"` |
| `capture_mode` | string | Observed: `"external"` |
| `shared_by_opponent` | boolean | Whether shared with opponent |
| `ingest_endpoints` | array | Streaming ingest URLs (RTMPS/SRT) |

- **Coaching relevance:** None. Video streaming infrastructure.

#### GET /teams/{team_id}/schedule/events/{event_id}/video-stream/assets

**Status:** CONFIRMED (web headers, schema documented). Video assets for a specific event.

- **Accept header:** not yet confirmed
- **Path parameters:** `team_id` (UUID), `event_id` (UUID)
- **Query keys observed:** `includeProcessing`
- **Discovered:** 2026-03-05

**Response Schema:**

Bare JSON array of video asset objects.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Asset UUID |
| `stream_id` | string (UUID) | Parent stream UUID |
| `team_id` | string (UUID) | Team UUID |
| `schedule_event_id` | string (UUID) | Event UUID |
| `created_at` | string (ISO 8601) | Asset creation timestamp |
| `audience_type` | string | Observed: `"players_family"` |
| `duration` | integer or null | Duration in seconds (null if not available) |
| `ended_at` | string (ISO 8601) | When recording ended |
| `thumbnail_url` | string (URL) | VOD archive thumbnail URL |
| `user_id` | string (UUID) | Uploader/recorder user UUID. **PII.** |
| `uploaded` | boolean | Whether this was an uploaded file |
| `is_processing` | boolean | Whether the asset is still processing |

- **Coaching relevance:** None. Video asset metadata, not stat data.

#### GET /teams/{team_id}/schedule/events/{event_id}/video-stream/assets/playback

**Status:** OBSERVED (proxy log, 1 hit, status 200). Playback URLs for event video assets.

- **Path parameters:** `team_id` (UUID), `event_id` (UUID)
- **Query keys observed:** none
- **Notes:** Returns playback URLs for video assets of a specific event. Not needed for stat ingestion.
- **Discovered:** 2026-03-05

#### GET /teams/{team_id}/schedule/events/{event_id}/video-stream/live-status

**Status:** CONFIRMED (web headers, schema documented). Live streaming status for an event.

- **Accept header:** not yet confirmed
- **Path parameters:** `team_id` (UUID), `event_id` (UUID)
- **Discovered:** 2026-03-05

**Response Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `isLive` | boolean | Whether the event is currently being live-streamed |

**Example:**

```json
{"isLive": false}
```

- **Coaching relevance:** None. Live streaming status.

---

### Game Streams

The `/game-streams/` path family (distinct from `/game-stream-processing/`) provides game narrative and viewer payloads.

#### GET /game-streams/{game_stream_id}/events

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema documented in Confirmed Endpoints section. 319 events for a 6-inning game. 10 unique event codes observed.

- **Path parameters:** `game_stream_id` (UUID -- same as in boxscore/plays endpoints)
- **Query keys observed:** `initial`, `start_at`
- **Notes:** Low-level raw event stream. `event_data` field is a JSON-encoded string that must be parsed separately. Full schema and event code documentation in the Confirmed Endpoints section. Not needed for historical stat ingestion (use `/plays` instead).
- **Confirmed:** 2026-03-07
- **Discovered:** 2026-03-05
- **Coaching relevance:** Low for historical analysis (use `/plays` instead). Could be useful for real-time game monitoring.

#### GET /game-streams/gamestream-viewer-payload-lite/{game_stream_id}

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Schema in Confirmed Endpoints section.

Lightweight game viewer payload. Accepts `event_id` (not game_stream_id) in the path.

- **Path parameters:** `event_id` (UUID -- schedule event UUID, NOT game_stream_id despite the name)
- **Query keys observed:** `include_stat_edits`, `marker`, `stream_id`
- **Schema:** `{"stream_id": UUID, "latest_events": [...319 events with created_at added...], "all_event_data_ids": [...319 inner event UUIDs...], "marker": "318"}` (marker = last sequence_number string for completed game)
- **Notes:** The path accepts a schedule `event_id` directly (unlike boxscore/plays which require `game_stream.id`). Returns the same event stream as `GET /game-streams/{stream_id}/events` but with additional fields and the `stream_id` resolved for you.
- **Discovered:** 2026-03-05
- **Coaching relevance:** Medium. Same event data as `/game-streams/{id}/events` -- use the processed `/plays` and `/boxscore` endpoints instead for coaching analytics.

#### GET /game-streams/gamestream-recap-story/{game_stream_id}

**Status:** CONFIRMED (web headers, schema documented). Structured game narrative story.

Returns a richly structured game recap "story" with typed segments referencing teams and players by UUID. This is the narrative text shown in the app's recap view, but in a structured format that enables programmatic extraction of player references, RBI details, and game highlights.

- **Accept header:** not yet confirmed
- **Path parameters:** `game_stream_id` (UUID, after fixed slug `gamestream-recap-story/`)
- **Query keys observed:** `game_stream_id`, `team_id`
- **Discovered:** 2026-03-05

**Response Schema:**

A single JSON object wrapping the recap.

| Field | Type | Description |
|-------|------|-------------|
| `recap` | object | The structured recap |
| `recap._id` | string (UUID) | Recap identifier (matches the event/game UUID) |
| `recap.status` | string | Recap status. Observed: `"active"` |
| `recap.title` | array | Structured title -- array of typed segments |
| `recap.paragraphs` | array of arrays | Body paragraphs -- each paragraph is an array of typed segments |
| `recap.recap_generation_date` | string (ISO 8601) | When the recap was generated |
| `recap.game_utc_start` | string (ISO 8601) | Game start time (UTC) |
| `recap.recap_type` | string | Type identifier. Observed: `"recap_stories"` |

**Typed segment objects (in title and paragraphs):**

Three segment types are used:

**Type: `"team"`**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"team"` |
| `id` | string (UUID) | Team UUID |
| `name` | string | Team name. **PII -- redact.** |
| `is_active` | boolean | Whether the team is active |
| `is_first_mention` | boolean | Whether this is the first mention of this team in the story |

**Type: `"player"`**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"player"` |
| `id` | string (UUID) | Player UUID |
| `name` | string | Player full name. **PII -- redact.** |
| `short_name` | string | Player last name. **PII -- redact.** |
| `team_id` | string (UUID) | The team this player belongs to |
| `num` | string | Jersey number (e.g., `"19"`, `"00"`) |
| `is_first_mention` | boolean | Whether this is the first mention of this player |

**Type: `"text"`**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"text"` |
| `content` | string | Plain text content |

**Example (redacted):**

```json
{
  "recap": {
    "_id": "<game-uuid>",
    "status": "active",
    "title": [
      {"type": "team", "id": "<team-uuid>", "name": "REDACTED Team A", "is_active": true, "is_first_mention": true},
      {"type": "text", "content": " Victorious Over "},
      {"type": "team", "id": "<team-uuid>", "name": "REDACTED Team B", "is_active": true, "is_first_mention": true}
    ],
    "paragraphs": [
      [
        {"type": "team", "id": "<team-uuid>", "name": "REDACTED Team A", "is_active": true, "is_first_mention": true},
        {"type": "text", "content": " were victorious against "},
        {"type": "team", "id": "<team-uuid>", "name": "REDACTED Team B", "is_active": true, "is_first_mention": true},
        {"type": "text", "content": " 8-7 on Tuesday at REDACTED Park."}
      ],
      [
        {"type": "player", "id": "<player-uuid>", "name": "REDACTED", "short_name": "REDACTED", "team_id": "<team-uuid>", "num": "19", "is_first_mention": true},
        {"type": "text", "content": " grounded out, scoring two runs."}
      ]
    ],
    "recap_generation_date": "2026-03-05T23:46:27",
    "game_utc_start": "2026-03-05T23:46:27",
    "recap_type": "recap_stories"
  }
}
```

**Key Observations:**
- The structured segment system is remarkably rich. Each player mention includes their UUID, full name, short name, team ID, and jersey number -- making it possible to programmatically extract every player referenced in the story.
- `is_first_mention` tracks narrative flow -- a player's first appearance has full context, subsequent mentions are abbreviated.
- The observed recap includes pitching summaries (IP, hits, runs, strikeouts, walks), batting highlights (RBI, hit type, at-bat results), and game flow narrative.
- Player UUIDs in the recap match those in `GET /teams/{team_id}/players` -- enabling cross-reference with the full player roster.
- The recap covers BOTH teams -- home and away players are referenced with their respective team UUIDs.
- **Coaching relevance:** High (Tier 2). Could be used to generate human-readable scouting reports. The structured format enables extracting key player performance mentions without parsing natural language. Not a primary stat source (use player-stats/boxscore for that), but excellent for narrative game summaries.

#### GET /game-streams/insight-story/bats/{game_stream_id}

**Status:** OBSERVED (proxy log, 1 hit, **status 404**). Batting insight story for a game.

- **Path parameters:** `game_stream_id` (UUID)
- **Notes:** Returned 404 for this specific game -- the feature may not be available for all games or this game did not have batting insights generated. Path pattern exists in client code. May return AI-generated batting insights when available.
- **Discovered:** 2026-03-05

#### GET /game-streams/player-insights/bats/{game_stream_id}

**Status:** OBSERVED (proxy log, 1 hit, **status 404**). Per-player batting insights for a game.

- **Path parameters:** `game_stream_id` (UUID)
- **Notes:** Similar to `insight-story/bats/` but player-level. Returned 404 -- may require premium subscription or be in limited rollout. Not yet confirmed as a viable data source.
- **Discovered:** 2026-03-05

#### GET /game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}

**Status:** OBSERVED (proxy log, 1 hit, **status 404**). Stat edits collection for a game.

- **Path parameters:** `game_stream_id` (UUID), `collection_id` (UUID)
- **Notes:** Returned 404. Likely retrieves stat corrections/edits applied to a game stream. Not yet confirmed.
- **Discovered:** 2026-03-05

---

### Clips / Video

#### GET /clips/{clip_id}

**Status:** OBSERVED (proxy log, 1 hit, status 200). Video clip metadata.

- **Path parameters:** `clip_id` (UUID)
- **Query keys observed:** `kind`
- **Notes:** Returns metadata for a specific video clip. `kind` parameter likely specifies the clip type (highlight, full-game segment, etc.). Schema not captured.
- **Discovered:** 2026-03-05

#### GET /clips/{clip_id}/playback-data

**Status:** OBSERVED (proxy log, 1 hit, status 200). Playback data for a video clip.

- **Path parameters:** `clip_id` (UUID)
- **Query keys observed:** `kind`
- **Notes:** Returns playback URLs and DRM/signing data for a clip. Schema not captured.
- **Discovered:** 2026-03-05

#### POST /clips/search

**Status:** OBSERVED (proxy log, 10 hits, status 200). Search for video clips.

- **Request Content-Type:** `application/vnd.gc.com.video_clip_search_query+json; version=0.0.0`
- **Notes:** Body-driven search for clips. 10 hits suggests this is called frequently (once per game view, possibly). Likely supports filtering by team, player, event, play type. Schema not captured. Not needed for stat ingestion but could be useful for linking stats to video clips.
- **Discovered:** 2026-03-05

---

### Users

#### GET /users/{user_id}

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

- **Path parameters:** `user_id` (UUID)
- **Schema:** `{"id": UUID, "status": string, "first_name": string, "last_name": string, "email": string}` -- all fields PII.
- **Notes:** Returns the same 5 fields as `GET /teams/{team_id}/users` list. Confirmed with the authenticated user's own UUID.
- **Discovered:** 2026-03-05

#### GET /users/{user_id}/profile-photo

**Status:** HTTP 404 -- confirmed in both proxy log (2026-03-05) and live test (2026-03-07).

- **Path parameters:** `user_id` (UUID)
- **Notes:** No profile photos set for observed users. Endpoint pattern exists; 404 response body: `"No profile photo found for user: <uuid>"`.
- **Discovered:** 2026-03-05

#### GET /players/{player_id}/profile-photo

**Status:** HTTP 404 -- confirmed in both proxy log (2026-03-05) and live test (2026-03-07).

- **Path parameters:** `player_id` (UUID)
- **Notes:** No profile photos set for observed players. Response body: `"No profile photo found for player: <uuid>"`.
- **Discovered:** 2026-03-05

---

### Search

#### GET /search/history

**Status:** OBSERVED (proxy log, 1 hit, status 200). User's recent search history.

- **Query keys observed:** none
- **Notes:** Returns the authenticated user's recent in-app searches. Not relevant to data ingestion.
- **Discovered:** 2026-03-05

#### POST /search/history

**Status:** OBSERVED (proxy log, 1 hit, status 200). Add an entry to search history.

- **Notes:** Write endpoint -- records a search query in history. Not relevant to data ingestion.
- **Discovered:** 2026-03-05

---

### Places

#### GET /places/{place_id}

**Status:** OBSERVED (proxy log, 1 hit, status 200). Place/venue details.

- **Path parameters:** `place_id` (Google Places ID -- observed format: `ChIJQ2fqS8z3k4cRUG4qNPnoWI0`)
- **Query keys observed:** none
- **Notes:** Returns venue information for a location using a Google Places-style ID. The IDs observed in this path (`ChIJ...`) match Google Places API ID format. This endpoint may proxy Google Places data or use GameChanger's own venue database keyed by Google Place IDs. Used by the app when displaying game locations. Not relevant to stat ingestion.
- **Discovered:** 2026-03-05

---

### Media CDN Hosts

Two additional hostnames were observed in the proxy log (beyond `api.team-manager.gc.com`):

#### media-service.gc.com

- **Path pattern:** `/{uuid}` (GET)
- **Status codes:** 200 and 403 (25 hits total)
- **Query keys:** `Key-Pair-Id`, `Policy`, `Signature` (AWS CloudFront signed URL parameters)
- **Notes:** Media asset delivery via CloudFront signed URLs. The `Key-Pair-Id`, `Policy`, and `Signature` query parameters are standard AWS CloudFront signed URL components. 403 responses indicate expired or invalid signatures. This host serves binary media assets (images, avatar photos, etc.). Not relevant to stat ingestion.
- **Discovered:** 2026-03-05

#### vod-archive.gc.com

- **Path pattern:** `/ivs/v1/{account_id}/{channel_id}/{year}/{month}/{day}/{hour}/{minute}/{session_id}/media/{format}` (HLS video segments and thumbnails)
- **Status codes:** 200 only
- **Notes:** AWS IVS (Interactive Video Service) archive host for recorded game video. Paths follow the IVS archive URL structure. This is where actual video content (`.ts` segments, `.m3u8` playlists, thumbnail `.jpg` files) is served from. Not relevant to stat ingestion.
- **Discovered:** 2026-03-05

---

### iOS App Header Observations (2026-03-05)

> **Consolidated**: The detailed header comparison table has been moved to the [Header Profiles](#header-profiles) section under Request Headers. The dual-header system in `src/http/headers.py` now codifies both profiles (`BROWSER_HEADERS` and `MOBILE_HEADERS`).

**Additional observations from mitmproxy capture not covered in the Header Profiles table:**

- **`x-gc-origin`**: `sync` (iOS only, on sync endpoints). Not included in `MOBILE_HEADERS` -- sync endpoints are infrastructure, not data.
- **`x-datadog-origin`**: `rum` (iOS only). Datadog RUM telemetry. Not needed.
- **`if-none-match`**: Present in iOS requests (ETag conditional GET). Not included in `MOBILE_HEADERS` -- could be added for efficiency on repeated calls.
- **`priority`**: `u=3, i` (iOS). Browser sends `u=1, i` on some requests. Not included in either profile -- HTTP priority hints are optional.

**Source "ios" -- Raw CFNetwork (`GameChanger/0 CFNetwork/3860.400.51 Darwin/25.3.0`):**

This source makes requests with a very minimal header set -- `accept: */*`, CFNetwork UA, `accept-language`, `accept-encoding`, `priority`. These are likely direct media download requests (CloudFront signed URLs, video segments) that bypass the Odyssey app layer. No `gc-token` observed -- consistent with CloudFront signed URL delivery not requiring GC auth.

---

## Proxy-Discovered Endpoints (2026-03-07)

These endpoints were catalogued from a second proxy capture session on 2026-03-07. All entries have status **PROXY CAPTURE** unless otherwise noted -- traffic was observed but response bodies were not directly captured. Schema fields are TBD unless stated otherwise. All entries are dated 2026-03-07.

> **Note on status codes:** All GETs in this capture returned 200 or 304 (cached) unless explicitly noted. OPTIONS requests returned 204 (CORS preflight). 404s on batting-insight and player-insight endpoints are documented and suggest premium or subscription-gated features.

---

### Teams -- Per-Opponent Scouting

#### GET /teams/{team_id}/opponent/{opponent_id}

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

Returns the opponent registry entry for a specific opponent. Note: this is the team record, not per-opponent stats. The 50+ unique opponent hits in the proxy capture are the iOS app loading team metadata for each scheduled opponent.

- **Path parameters:** `team_id` (UUID), `opponent_id` (UUID -- use `root_team_id` from opponents list as path param)
- **Schema:** 5 fields -- `root_team_id`, `owning_team_id`, `name`, `is_hidden`, `progenitor_team_id`. Full schema in Confirmed Endpoints section.
- **Relationship:** `opponent_id` path param = `root_team_id` in the response. `progenitor_team_id` is the canonical UUID for accessing other team endpoints.
- **Coaching relevance:** Tier 2. Useful for resolving opponent names and canonical UUIDs, but does not contain aggregate scouting stats. Per-opponent stats come from boxscore/plays/season-stats endpoints.
- **Confirmed:** 2026-03-07
- **Discovered:** 2026-03-07

---

### Bats / Starting Lineups

The `/bats-starting-lineups/` path family provides GameChanger's BATS (Baseball Analytics Tracking System) lineup data. These endpoints are distinct from the general schedule/event system.

#### GET /bats-starting-lineups/{event_id}

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07, confirmed via retry with home game event_id). Full schema in Confirmed Endpoints section.

Starting lineup for a specific game event. Returns the batting order and field positions as entered by the scoring team for the given event.

- **Path parameters:** `event_id` (UUID -- from schedule or game-summaries)
- **Schema:** Same fields as `/latest/{team_id}` but **no `latest_lineup` wrapper** -- the lineup object is returned directly. Fields: `id`, `dh`, `dh_batting_for`, `creator`, `entries[]` (player_id + fielding_position, array order = batting order). Full schema in Confirmed Endpoints section.
- **403 behavior:** Returns HTTP 403 for away games where the authenticated user's team was not the primary scorer. Use home game event_ids or events where the user's team managed scoring.
- **Coaching relevance:** High (Tier 2). Starting lineup data enables batting order analysis, lineup tendency research, and position tracking across the season.
- **Confirmed:** 2026-03-07
- **Discovered:** 2026-03-07

#### GET /bats-starting-lineups/latest/{team_id}

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

Latest starting lineup for a team. Returns the most recently entered lineup -- useful for displaying the current or most recent game's batting order without knowing a specific event_id.

- **Path parameters:** `team_id` (UUID)
- **Schema:** `latest_lineup` object with `id`, `dh`, `dh_batting_for`, `creator`, `entries[]` (player_id + fielding_position per entry, array order = batting order).
- **Coaching relevance:** High (Tier 2). Quick access to the team's current lineup without event_id lookup.
- **Discovered:** 2026-03-07

---

### Teams -- Lineup Recommendation

#### GET /teams/{team_id}/lineup-recommendation

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

GameChanger's automated lineup recommendation engine. Returns an algorithmically generated batting order and fielding assignment based on the team's historical performance data.

- **Path parameters:** `team_id` (UUID)
- **Schema:** `{"lineup": [{"player_id": UUID, "field_position": string, "batting_order": int}, ...], "metadata": {"generated_at": ISO8601, "team_id": UUID}}`. 9 entries (standard starting 9).
- **Coaching relevance:** High (Tier 2). Direct access to GC's recommendation engine could surface data-driven lineup suggestions. Compare with `/bats-starting-lineups/latest/{team_id}` to see where the coach deviated from the algorithm.
- **Notes:** `generated_at` changes on each request -- recommendation is recalculated live, not cached.
- **Discovered:** 2026-03-07

---

### Player Attributes

#### GET /player-attributes/{player_id}/bats

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

Player batting attributes including handedness and throwing hand.

- **Path parameters:** `player_id` (UUID -- from `GET /teams/{team_id}/players`)
- **Schema:** `{"player_id": UUID, "throwing_hand": "right"|"left", "batting_side": "right"|"left"|"switch"}`
- **Note:** `GET /teams/{team_id}/opponents/players` returns the same handedness data in bulk for all opponents. Use this endpoint for individual own-team player lookups only.
- **Related write endpoint:** `PATCH /player-attributes/{player_id}/bats/` (documented in Write Operations Catalog below).
- **Coaching relevance:** High (Tier 2). But prefer the bulk opponents/players endpoint for opponent handedness data.
- **Discovered:** 2026-03-07

#### PATCH /player-attributes/{player_id}/bats/

**Status:** PROXY CAPTURE -- write operation observed.

Updates batting attributes for a player. See [Write Operations Catalog](#write-operations-catalog).

- **Discovered:** 2026-03-07

---

### Events (standalone)

#### GET /events/{event_id}

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

Standalone event detail endpoint. Returns full details for a single scheduled event by UUID.

- **Path parameters:** `event_id` (UUID -- from schedule)
- **Schema:** Two-key JSON object: `event` (id, event_type, sub_type, status, full_day, team_id, start/end/arrive datetimes, timezone) + `pregame_data` (id, game_id, opponent_name, opponent_id, home_away, lineup_id).
- **Key field:** `pregame_data.lineup_id` links directly to `GET /bats-starting-lineups/{event_id}`.
- **Coaching relevance:** Medium (Tier 3). Useful for resolving an event_id to full event metadata. Prefer `GET /events/{event_id}/best-game-stream-id` for game_stream_id resolution.
- **Discovered:** 2026-03-07

---

### Organizations (additional)

These endpoints extend the Organizations section documented in the 2026-03-05 capture.

#### GET /organizations/{org_id}/pitch-count-report

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). **CSV format -- not JSON.**

Pitch count report at the organization level. Returns a CSV string with per-pitcher pitch counts for the past week.

- **Path parameters:** `org_id` (UUID -- organization identifier)
- **Schema:** CSV string with columns: `Game Date, Start Time, Pitcher, Team, Opponent, Pitch Count, "Last Batter, First Pitch #", Innings Pitched, Innings Caught, Final Score, Scored By`
- **Note:** Response is CSV, not JSON. This is the only non-JSON endpoint in the spec.
- **Empty response:** Returns `"No games with pitcher data were found in the past week."` as the CSV row content when no recent games exist.
- **Coaching relevance:** High (Tier 2). Org-level pitch count tracking is critical for pitcher health management across multiple teams. High school programs with JV/Varsity sharing pitchers would use this to enforce pitch count rules and rest requirements.
- **Discovered:** 2026-03-07

---

### Teams -- Additional (2026-03-07)

These team-scoped endpoints are new additions from the 2026-03-07 capture. See the 2026-03-05 "Teams (additional)" section for entries documented in the prior session.

#### GET /teams/{team_id}/web-widgets

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

Web widget configuration for a specific team.

- **Path parameters:** `team_id` (UUID)
- **Schema:** Bare JSON array of `{"id": UUID, "type": string}` objects. Observed: `[{"id": "...", "type": "schedule"}]`.
- **Coaching relevance:** None. Widget configuration -- no coaching analytics value.
- **Discovered:** 2026-03-07

#### GET /teams/public/{public_id}/access-level

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

**AUTH REQUIRED:** Despite the `/public/` path segment, this endpoint requires `gc-token`. Unauthenticated requests return HTTP 401. See the full entry in the Confirmed Endpoints section for error response details.

Returns the paid access level for a team's public profile.

- **Path parameters:** `public_id` (alphanumeric slug)
- **Schema:** `{"paid_access_level": string|null}`. Returned `null` for the test team.
- **Coaching relevance:** Low. Operational -- useful for pre-flight checks before attempting to fetch opponent data via public endpoints.
- **Discovered:** 2026-03-07

#### GET /teams/public/{public_id}/id

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

**AUTH REQUIRED:** Despite the `/public/` path segment, this endpoint requires `gc-token`. Unauthenticated requests return HTTP 401. See the full entry in the Confirmed Endpoints section for error response details.

**Reverse bridge: public_id slug -> team UUID.** Confirmed symmetry with `GET /teams/{team_id}/public-team-profile-id`.

- **Path parameters:** `public_id` (alphanumeric slug)
- **Schema:** `{"id": UUID}`. Confirmed: `a1GFM9Ku0BbF` -> `72bb77d8-54ca-42d2-8547-9da4880d0cb4`.
- **Coaching relevance:** Medium (Tier 3). When starting from a public_id (e.g., from a shared link), enables resolving back to the UUID for authenticated endpoints.
- **Discovered:** 2026-03-07

#### GET /public/teams/{public_id}/live

**Status:** PROXY CAPTURE -- **HTTP 404 observed** (no active game at time of capture).

Live game status for a public team profile. Returns the currently-live game stream for a team, if one exists.

- **Path parameters:** `public_id` (alphanumeric slug)
- **URL note:** Uses the `/public/teams/` prefix (standard public endpoint pattern -- no auth required).
- **Query keys observed:** none confirmed
- **Schema:** TBD -- 404 received when no game was live; response body for a live game not yet captured
- **Expected content (when game is live):** Likely returns the `game_stream_id` and basic game state (inning, score, home/away) for the active game
- **Auth requirement:** Likely no auth required (consistent with other `/public/teams/` endpoints)
- **Coaching relevance:** Low. Live game monitoring -- not needed for historical data ingestion. Could be useful for detecting when a game has just finished (transition from live to completed) as an ingestion trigger.
- **Discovered:** 2026-03-07

---

### Web-Route Public Endpoints

These endpoints follow a **season-slug URL pattern** distinct from all previously documented endpoints. They were observed in iOS proxy capture and thought to be served under `https://api.team-manager.gc.com`.

**CONFIRMED HTTP 404 ON API DOMAIN (2026-03-07):** All season-slug endpoints returned HTTP 404 when tested against `api.team-manager.gc.com`. These URL patterns appear to be served by the **web app** (`https://web.gc.com`) rather than the API domain. The proxy capture likely captured web-frontend navigation requests, not API calls.

**Status for all entries in this section:** PROXY CAPTURE (observed), HTTP 404 on API domain (confirmed 2026-03-07). These routes are NOT available at `https://api.team-manager.gc.com`. Re-test against `https://web.gc.com` if needed.

#### GET /teams/{public_id}/{season-slug}/opponents

Returns opponents for a team in a specific season, accessed via the public_id and season slug. Likely equivalent to `GET /teams/{team_id}/opponents` but scoped to a single season via the slug rather than returning all-time opponents.

- **Path parameters:** `public_id` (alphanumeric slug), `season-slug` (string, format TBD)
- **Schema:** TBD -- proxy traffic observed, response body not yet captured
- **Coaching relevance:** High (Tier 2). Season-scoped opponent list without needing a team UUID -- accessible from a shared link or public profile.

#### GET /teams/{public_id}/{season-slug}/schedule/{event_id}/plays

Returns pitch-by-pitch play data for a specific event, accessible via public_id and season slug. Likely equivalent to `GET /game-stream-processing/{game_stream_id}/plays` but routed via the web URL pattern.

- **Path parameters:** `public_id` (alphanumeric slug), `season-slug` (string), `event_id` (UUID)
- **Schema:** TBD -- proxy traffic observed, response body not yet captured
- **Notes:** If this endpoint returns plays without authentication, it would be a significant discovery -- pitch-by-pitch data for any public team without needing a gc-token. **High-priority verification target.**
- **Coaching relevance:** Critical (Tier 1) if unauthenticated. Pitch-by-pitch plays for any opponent without credentials enables comprehensive opponent scouting.

#### GET /teams/{public_id}/{season-slug}/season-stats

Returns season stats for a team via the public/season-slug route. Likely equivalent to `GET /teams/{team_id}/season-stats` but accessible without authentication.

- **Path parameters:** `public_id` (alphanumeric slug), `season-slug` (string)
- **Schema:** TBD -- proxy traffic observed, response body not yet captured
- **Notes:** If unauthenticated access is confirmed, this is a major capability -- season-level batting/pitching/fielding aggregates for any opponent visible via their public profile.
- **Coaching relevance:** Critical (Tier 1) if unauthenticated. Opponent season stats for scouting without credential dependency.

#### GET /teams/{public_id}/{season-slug}/team

Returns team information for a specific season via the public/season-slug route. Likely equivalent to `GET /public/teams/{public_id}` but season-scoped.

- **Path parameters:** `public_id` (alphanumeric slug), `season-slug` (string)
- **Schema:** TBD -- proxy traffic observed, response body not yet captured
- **Coaching relevance:** Low. Team metadata -- name, location, season info. Duplicate of `GET /public/teams/{public_id}` with season scoping.

#### GET /teams/{public_id}/{season-slug}/tools

Returns tools/features available for a team in a specific season. Likely a feature-flag or capability check -- which GameChanger features are enabled for this team/season combination.

- **Path parameters:** `public_id` (alphanumeric slug), `season-slug` (string)
- **Schema:** TBD -- proxy traffic observed, response body not yet captured
- **Coaching relevance:** None. Feature/capability metadata -- no coaching analytics value.

#### GET /teams/{public_id}/players/{player_id}

Returns a single player record for a team identified by `public_id`. This is the individual-player variant of `GET /teams/public/{public_id}/players` (which returns the full roster).

- **Path parameters:** `public_id` (alphanumeric slug), `player_id` (UUID)
- **URL note:** Uses `/{public_id}/players/{player_id}` directly under `/teams/` -- no `public/` infix and no season slug. Compare with the roster endpoint `GET /teams/public/{public_id}/players` which uses the `public/` infix.
- **Schema:** TBD -- proxy traffic observed, response body not yet captured
- **Expected content:** Single player object -- likely same 5-field schema as `GET /teams/public/{public_id}/players` (`id`, `first_name`, `last_name`, `number`, `avatar_url`)
- **Coaching relevance:** Low. Individual player lookup -- roster endpoint returns all players more efficiently.
- **Discovered:** 2026-03-07

---

### Me -- Additional (2026-03-07)

These `/me/` endpoints are new additions from the 2026-03-07 capture. See the 2026-03-05 "Me (additional)" section for entries documented in the prior session.

#### GET /me/organizations

**Status:** CONFIRMED (2026-03-07) -- returns empty array for this account. Previously HTTP 500 due to missing pagination params. Fixed with `?page_size=50` + `x-pagination: true` header. Full schema in Confirmed Endpoints section.

- **Required query params:** `?page_size=50`
- **Required header:** `x-pagination: true`
- **Notes:** Returns empty array for accounts where org access is via team membership (not direct org membership). Compare with `/me/related-organizations` which returned 2 orgs.
- **Coaching relevance:** Medium (Tier 3). Organization discovery -- useful if the user has direct org membership.
- **Discovered:** 2026-03-07

#### GET /me/team-tile/{team_id}

**Status:** CONFIRMED LIVE -- 200 OK (2026-03-07). Full schema in Confirmed Endpoints section.

Returns the "team tile" summary card for a specific team. Same fields as `GET /me/teams` but for a single team.

- **Path parameters:** `team_id` (UUID)
- **Schema:** Same shape as team objects in `/me/teams` + `badge_count` integer field. `team_avatar_image` may be null.
- **Coaching relevance:** None. App UI component -- no coaching analytics value beyond what `/me/teams` provides.
- **Discovered:** 2026-03-07

---

### Write Operations Catalog

This section documents write endpoints (POST, PATCH, PUT, DELETE) observed in the 2026-03-07 proxy capture. These are **not needed for read-only data ingestion** but are documented here for completeness and to support potential future roster management or lineup submission features.

**Status for all entries:** PROXY CAPTURE -- traffic observed. Request/response bodies not captured unless noted.

#### POST /search

Global search endpoint. Returns search results across teams, players, games, and other entities.

- **Notes:** Distinct from `POST /clips/search` (video clips only). The global search is likely used for the app's search bar. Request body probably contains a query string and optional filters. Not needed for data ingestion.
- **Discovered:** 2026-03-07

#### POST /me/tokens/braze

Registers a Braze push notification token for the authenticated user.

- **Notes:** Mobile push notification infrastructure. Not relevant to data ingestion.
- **Discovered:** 2026-03-07

#### POST /me/tokens/firebase

Registers a Firebase Cloud Messaging (FCM) push notification token for the authenticated user.

- **Notes:** Mobile push notification infrastructure. Not relevant to data ingestion.
- **Discovered:** 2026-03-07

#### POST /me/tokens/stream-chat

Obtains or registers a Stream Chat token for the authenticated user. Stream Chat is the third-party in-app messaging service used by GameChanger.

- **Notes:** In-app chat infrastructure. Not relevant to data ingestion.
- **Discovered:** 2026-03-07

#### POST /me/tokens/stream-chat/revoke

Revokes the authenticated user's Stream Chat token (e.g., on sign-out).

- **Notes:** In-app chat infrastructure. Not relevant to data ingestion.
- **Discovered:** 2026-03-07

#### POST /teams/{team_id}/players/

Creates a new player on a team. Note the trailing slash in the URL pattern.

- **Path parameters:** `team_id` (UUID)
- **Notes:** Write endpoint for roster management -- adds a player record to a team. Request body likely contains `first_name`, `last_name`, `number`, `positions`, `bats`, `throws`. Not needed for read-only ingestion but relevant if roster sync features are built.
- **Discovered:** 2026-03-07

#### PATCH /me/user

Updates the authenticated user's profile. Already documented in the 2026-03-05 Me (additional) section. Listed here for completeness in the write-operations catalog.

- **Discovered:** 2026-03-05

#### PATCH /players/{player_id}

Updates a player's profile fields.

- **Path parameters:** `player_id` (UUID)
- **Notes:** Write endpoint for roster management -- updates player metadata (name, number, etc.). Distinct from `PATCH /player-attributes/{player_id}/bats/` which handles batting-stance-specific attributes.
- **Discovered:** 2026-03-07

#### PATCH /player-attributes/{player_id}/bats/

Updates a player's batting attributes (handedness, stance). Note the trailing slash.

- **Path parameters:** `player_id` (UUID)
- **Notes:** Write counterpart to `GET /player-attributes/{player_id}/bats`. Updates `bats` (left/right/switch) and `throws` fields.
- **Discovered:** 2026-03-07

#### DELETE /players/{player_id}

Deletes a player record.

- **Path parameters:** `player_id` (UUID)
- **Notes:** Destructive roster management operation. Not relevant to read-only ingestion.
- **Discovered:** 2026-03-07

#### PUT /teams/{team_id}/managers/

Adds a manager/coach to a team. Note the trailing slash.

- **Path parameters:** `team_id` (UUID)
- **Notes:** Team management write operation. Not relevant to read-only ingestion.
- **Discovered:** 2026-03-07

#### DELETE /teams/{team_id}/managers/{user_id}

Removes a manager/coach from a team.

- **Path parameters:** `team_id` (UUID), `user_id` (UUID)
- **Notes:** Team management write operation. Not relevant to read-only ingestion.
- **Discovered:** 2026-03-07

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

## Endpoint Priority Matrix

This matrix ranks every documented endpoint by its value for coaching analytics -- scouting, lineup optimization, player development, and game preparation. It guides which endpoints to build crawlers and loaders for next. Tiers are assigned based on the "Key Metrics We Track" in CLAUDE.md: OBP, K rate, splits (home/away, L/R), per-game lines, box scores, spray charts, pitch-by-pitch, player identification, opponent tendencies, and longitudinal tracking.

### Tier 1 -- Critical

Endpoints that directly enable scouting reports, lineup decisions, or game preparation. These should be the next crawlers built after the existing E-002 pipeline.

| Endpoint | Status | Coaching Use Case |
|----------|--------|-------------------|
| `GET /teams/{team_id}/opponent/{opponent_id}` | CONFIRMED (2026-03-07) | Per-opponent record lookup -- name, is_hidden, progenitor_team_id for further queries |
| `GET /teams/{team_id}/opponents/players` | CONFIRMED (758 records, 61 teams) | Bulk opponent roster with handedness for ALL opponents in one call -- most efficient scouting prep |
| `GET /organizations/{org_id}/standings` | CONFIRMED (2026-03-07) | League standings with home/away/last10/streak/run-differential for conference positioning |
| `GET /me/associated-players` | CONFIRMED (2026-03-07) | Cross-team player tracking -- longitudinal analysis of players across seasons, teams, and levels |
| `GET /game-streams/gamestream-recap-story/{id}` | CONFIRMED (schema documented; 404 for some events) | Structured game narrative with player UUIDs, names, RBI/hit details -- automated scouting report generation |
| `GET /game-stream-processing/{game_stream_id}/plays` | CONFIRMED | Pitch-by-pitch play data -- pitch sequences, stolen bases, contact quality, lineup changes. See IDEA-008. |
| `GET /teams/{team_id}/players/{player_id}/stats` | CONFIRMED | Per-player per-game stats with spray charts (x/y coordinates) and rolling cumulative totals. See IDEA-009. |
| `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` | CONFIRMED | Both teams' player stats + spray charts in a single call per game -- most efficient box score source |
| `GET /teams/{public_id}/{season-slug}/season-stats` | PROXY CAPTURE | Season stats via public/season-slug route -- if unauthenticated, enables opponent stat ingestion without credentials |
| `GET /teams/{public_id}/{season-slug}/schedule/{event_id}/plays` | PROXY CAPTURE | Pitch-by-pitch plays via public route -- if unauthenticated, enables pitch sequence analysis for any opponent |

### Tier 2 -- High

Endpoints that enhance analysis but are not blocking core scouting or game-prep workflows.

| Endpoint | Status | Coaching Use Case |
|----------|--------|-------------------|
| `GET /public/game-stream-processing/{game_stream_id}/details` | CONFIRMED | Inning-by-inning line scores and R/H/E totals -- comeback patterns, late-inning scoring. See IDEA-008. No auth required. |
| `GET /me/archived-teams` | CONFIRMED | Access to historical season team objects -- enables multi-season longitudinal analysis |
| `GET /me/schedule` | CONFIRMED | Cross-team schedule in a single call -- useful for multi-team coordination and schedule overlap detection |
| `GET /organizations/{org_id}/opponents` | CONFIRMED | Org-level opponent list with root/progenitor/owning team IDs -- discover opponents without per-team iteration |
| `GET /organizations/{org_id}/opponent-players` | HTTP 500 | Bulk opponent roster at org level -- high value but blocked by HTTP 500 with web headers. See IDEA-011. |
| `GET /organizations/{org_id}/teams` | CONFIRMED (2026-03-07) | All teams in an org in one call -- requires `?page_starts_at=0&page_size=50` + `x-pagination: true` header |
| `GET /me/related-organizations` | CONFIRMED (2026-03-07) | Organization discovery -- requires `?page_starts_at=0&page_size=50` + `x-pagination: true` header |
| `GET /teams/{team_id}/relationships` | CONFIRMED | User-to-player mapping ("primary", "self" associations) -- links coaches/parents to specific players |
| `GET /bats-starting-lineups/{event_id}` | CONFIRMED (2026-03-07) -- 403 on away game, 200 on home game | Per-game starting lineup: batting order + field positions for lineup tendency analysis |
| `GET /bats-starting-lineups/latest/{team_id}` | CONFIRMED (2026-03-07) | Latest starting lineup for a team: batting order and field positions |
| `GET /teams/{team_id}/lineup-recommendation` | CONFIRMED (2026-03-07) | GC's algorithmic lineup recommendation: 9-player batting order + field positions |
| `GET /player-attributes/{player_id}/bats` | CONFIRMED (2026-03-07) | Batter handedness (L/R/switch) -- but `/opponents/players` returns same data in bulk |
| `GET /organizations/{org_id}/pitch-count-report` | CONFIRMED (2026-03-07) -- CSV format | Org-level pitcher pitch counts as CSV -- arm health tracking and pitch count rule enforcement |
| `GET /teams/{public_id}/{season-slug}/opponents` | HTTP 404 -- not on API domain | Season-scoped opponent list -- route may exist on web.gc.com, not api.team-manager.gc.com |

### Tier 3 -- Medium

Nice-to-have data for secondary analysis or operational convenience.

| Endpoint | Status | Coaching Use Case |
|----------|--------|-------------------|
| `GET /organizations/{org_id}/team-records` | CONFIRMED | Season win/loss/tie records per team in an org -- quick standings snapshot |
| `GET /organizations/{org_id}/users` | CONFIRMED | Org admin/user list -- operational, not coaching analytics (PII endpoint) |
| `GET /organizations/{org_id}/events` | CONFIRMED (empty) | Org-level event calendar -- returned empty for travel ball org, may have data for school program orgs |
| `GET /organizations/{org_id}/game-summaries` | CONFIRMED (empty) | Org-level game summaries -- returned empty, may have data for school program orgs |
| `GET /events/{event_id}/best-game-stream-id` | CONFIRMED | Resolves event_id to game_stream_id -- utility for boxscore/plays pipeline |
| `GET /events/{event_id}` | CONFIRMED (2026-03-07) | Standalone event detail -- full event + pregame_data including lineup_id |
| `GET /teams/{team_id}/public-team-profile-id` | CONFIRMED | UUID-to-public_id bridge -- enables public endpoint access for any discovered opponent |
| `GET /teams/public/{public_id}/id` | CONFIRMED (2026-03-07) -- **AUTH REQUIRED** despite `/public/` path | Reverse bridge: public_id -> UUID -- confirmed symmetry with forward bridge |
| `GET /me/teams-summary` | CONFIRMED | Lightweight team count/date range -- quick check for account scope |
| `GET /me/organizations` | CONFIRMED (2026-03-07) -- empty | Organization membership list -- requires `?page_size=50` + `x-pagination: true`; returns empty array for this account |
| `GET /events/{event_id}/highlight-reel` | CONFIRMED (2026-03-07) | Game highlight clips with CloudFront URLs -- potential for game recap visuals |
| `GET /game-streams/{game_stream_id}/events` | CONFIRMED (2026-03-07) | Raw event stream -- 319 events, 10 event codes, `event_data` is JSON-encoded string |
| `GET /game-streams/gamestream-viewer-payload-lite/{id}` | CONFIRMED (2026-03-07) | Lightweight game viewer -- same 319 events as /events plus `created_at`, marker, all_event_data_ids |

### Tier 4 -- Low / None

Infrastructure, config, video, or app-only endpoints with no coaching analytics value.

| Endpoint | Status | Coaching Use Case |
|----------|--------|-------------------|
| `GET /me/widgets` | CONFIRMED (2026-03-07) -- returns `{"widgets":[]}` | App widget configuration -- no coaching value |
| `GET /me/team-tile/{team_id}` | CONFIRMED (2026-03-07) | Compact team tile with record and badge_count -- no additional coaching value beyond /me/teams |
| `GET /me/subscription-information` | CONFIRMED (2026-03-07) | Subscription details with provider_details -- no coaching value |
| `GET /subscription/details` | CONFIRMED (2026-03-07) | Detailed subscription with plan levels and billing -- no coaching value |
| `GET /subscription/recurly/plans` | CONFIRMED (2026-03-07) | Available plans with pricing -- no coaching value |
| `GET /me/advertising/metadata` | CONFIRMED (2026-03-07) | Ad targeting data -- no coaching value |
| `GET /announcements/user/read-status` | CONFIRMED (2026-03-07) -- `{"read_status":"read"}` | In-app announcements read status -- no coaching value |
| `GET /sync-topics/me/updated-topics` | CONFIRMED (2026-03-07) | Real-time sync cursor -- no coaching value for historical ingestion |
| `GET /teams/{team_id}/scoped-features` | CONFIRMED (2026-03-07) -- empty | Feature flags -- no coaching value |
| `GET /teams/{team_id}/team-notification-setting` | CONFIRMED (2026-03-07) | Notification preferences -- no coaching value |
| `GET /teams/{team_id}/external-associations` | CONFIRMED (2026-03-07) -- empty | External system links -- no coaching value |
| `GET /teams/{team_id}/web-widgets` | CONFIRMED (2026-03-07) -- `[{"type":"schedule"}]` | Team web widget config -- no coaching value |
| `GET /teams/public/{public_id}/access-level` | CONFIRMED (2026-03-07) -- `{"paid_access_level":null}` | **AUTH REQUIRED** despite `/public/` path. Access level check -- operational |
| `GET /public/teams/{public_id}/live` | HTTP 404 when no active game | Live game status -- 404 when no active game; not for historical ingestion |
| `GET /organizations/{org_id}/scoped-features` | CONFIRMED (2026-03-07) -- empty | Org feature flags -- no coaching value |
| `GET /organizations/{org_id}/avatar` | OBSERVED | Org logo image -- no coaching value |
| `GET /teams/{team_id}/avatar` | OBSERVED | Team logo image -- no coaching value |
| `GET /teams/{team_id}/videos` | OBSERVED | Team video list -- video infrastructure, not stat data |
| `GET /teams/{team_id}/video-stream/assets` | CONFIRMED | Video stream assets -- video infrastructure |
| `GET /events/{event_id}/video-stream` | CONFIRMED | Event video metadata -- video infrastructure |
| `GET /events/{event_id}/video-stream/assets` | CONFIRMED | Event video assets -- video infrastructure |
| `GET /events/{event_id}/video-stream/live-status` | CONFIRMED | Live streaming status -- video infrastructure |
| `GET /events/{event_id}/video-stream/assets/{id}/playback` | OBSERVED | Video playback URLs -- video infrastructure |
| `GET /events/{event_id}/rsvp-responses` | CONFIRMED | RSVP data (returned empty) -- team management, not coaching |
| `GET /teams/{team_id}/pending-relationships` | OBSERVED | Pending relationship requests -- team management |
| `GET /teams/{team_id}/opponent-sharing-opt-outs` | OBSERVED | Data sharing opt-outs -- team management |
| `GET /teams/{team_id}/users-count` | OBSERVED | User count -- operational |
| `POST /teams/{team_id}/follow` | OBSERVED | Follow a team -- app feature |
| `GET /teams/{team_id}/team-calendar` | OBSERVED | Calendar sync URL -- operational |
| `GET /teams/{public_id}/{season-slug}/team` | PROXY CAPTURE | Season-scoped team info via public route -- duplicate of public team profile |
| `GET /teams/{public_id}/{season-slug}/tools` | PROXY CAPTURE | Feature flags via public route -- no coaching value |
| `GET /teams/{public_id}/players/{player_id}` | PROXY CAPTURE | Single player lookup via public_id -- roster endpoint more efficient |
| `PUT /users/{user_id}` | OBSERVED | Update user profile -- user management |
| `GET /sync-topics/{topic_id}/events` | OBSERVED | Real-time sync events -- infrastructure |
| `POST /sync-topics/{topic_id}/events` | OBSERVED | Push sync updates -- infrastructure |
| `POST /sync-topics` | OBSERVED | Subscribe to sync topics -- infrastructure |
| `GET /announcements/read` | OBSERVED | In-app announcements -- no coaching value |
| `GET /users/{user_id}/subscriptions` | OBSERVED | User subscription info -- billing |
| `GET /teams/{team_id}/ads-information` | OBSERVED | Advertising metadata -- no coaching value |
| `GET /auth/{entity_type}/{entity_id}/permissions` | OBSERVED | Per-entity permission check -- infrastructure |
| `POST /auth/permissions` | OBSERVED | Batch permission check -- infrastructure |
| `POST /auth` | PARTIALLY CONFIRMED | Token refresh -- credential infrastructure (gc-signature unknown) |
| `GET /clips/{clip_id}` | OBSERVED | Video clip metadata -- video infrastructure |
| `GET /clips/{clip_id}/playback` | OBSERVED | Video clip playback -- video infrastructure |
| `GET /clips/search` | OBSERVED | Video clip search -- video infrastructure |
| `GET /users/{user_id}` | OBSERVED | Public user profile -- user management |
| `GET /users/{user_id}/avatar` | OBSERVED (404) | User profile photo -- media |
| `GET /players/{player_id}/avatar` | OBSERVED (404) | Player profile photo -- media |
| `GET /users/{user_id}/search-history` | OBSERVED | Search history -- app feature |
| `POST /users/{user_id}/search-history` | OBSERVED | Add search entry -- app feature |
| `POST /search` | PROXY CAPTURE | Global search -- app feature, not ingestion |
| `POST /me/tokens/braze` | PROXY CAPTURE | Push notification token -- mobile infrastructure |
| `POST /me/tokens/firebase` | PROXY CAPTURE | Push notification token -- mobile infrastructure |
| `POST /me/tokens/stream-chat` | PROXY CAPTURE | Chat token -- in-app messaging infrastructure |
| `POST /me/tokens/stream-chat/revoke` | PROXY CAPTURE | Revoke chat token -- in-app messaging infrastructure |
| `POST /teams/{team_id}/players/` | PROXY CAPTURE | Create player -- roster management write operation |
| `PATCH /players/{player_id}` | PROXY CAPTURE | Update player -- roster management write operation |
| `PATCH /player-attributes/{player_id}/bats/` | PROXY CAPTURE | Update batting stance -- roster management write operation |
| `DELETE /players/{player_id}` | PROXY CAPTURE | Delete player -- roster management write operation |
| `PUT /teams/{team_id}/managers/` | PROXY CAPTURE | Add team manager -- team management write operation |
| `DELETE /teams/{team_id}/managers/{user_id}` | PROXY CAPTURE | Remove team manager -- team management write operation |
| `GET /places/{place_id}` | OBSERVED | Venue details -- operational |
| `GET /game-streams/gamestream-batting-insight-story/{id}` | OBSERVED (404) | Batting insights -- returned 404, may not exist for all games |
| `GET /game-streams/gamestream-batting-insight-story/{id}/players/{pid}` | OBSERVED (404) | Player batting insights -- returned 404 |
| `GET /game-streams/{game_stream_id}/stat-edits` | OBSERVED (404) | Stat edits -- returned 404 |

### Top 5 Endpoints to Integrate Next

After the existing E-002 pipeline (roster, schedule, game-summaries, boxscore, season-stats, opponents), these five endpoints offer the highest coaching value with reasonable implementation feasibility. Updated 2026-03-07 to reflect live probe results.

1. **`GET /teams/{team_id}/opponents/players`** -- Aggregated opponent roster across all opponents INCLUDING handedness. 758 records, 61 teams in a single call. One endpoint replaces N per-opponent roster calls AND N per-player bats calls. CONFIRMED with full schema 2026-03-07. Zero ambiguity about implementation.

2. **`GET /game-stream-processing/{game_stream_id}/plays`** -- Pitch-by-pitch play data for advanced scouting: pitch sequences, stolen base attempts, contact quality, lineup changes. Uses the same `game_stream_id` already captured by E-002. See IDEA-008 for the full epic concept.

3. **`GET /teams/{team_id}/players/{player_id}/stats`** -- Per-player per-game stats with spray chart coordinates. Enables batting tendency analysis, defensive positioning recommendations, and player development tracking across seasons. See IDEA-009 for the full epic concept.

4. **`GET /organizations/{org_id}/standings`** -- Full league standings with run differential, streaks, home/away splits, and last-10 records. CONFIRMED with full schema 2026-03-07 (returned zeros for travel ball org -- will have data for school program orgs with conference standings). Requires the LSB program's org UUID.

5. **`GET /bats-starting-lineups/{event_id}` + `GET /bats-starting-lineups/latest/{team_id}` + `GET /teams/{team_id}/lineup-recommendation`** -- Per-event starting lineup (event-specific), latest lineup snapshot, and GC's algorithmic recommendation. All three CONFIRMED with full schemas 2026-03-07. Together they enable: (a) per-game lineup history, (b) comparison of coach decisions vs. GC algorithm, (c) batting order consistency analysis. Note: `/bats-starting-lineups/{event_id}` returns HTTP 403 for away games where the authenticated user's team was not the scorer -- only accessible for home games or games where the user's team managed scoring.

### HTTP 500 Endpoints -- Integration Blocked

~~Four high-value endpoints previously returned HTTP 500 with web browser headers.~~ **UPDATE 2026-03-07: Three of these four endpoints are now CONFIRMED WORKING.** The required pagination query parameters and `x-pagination: true` header were identified. One endpoint remains blocked.

The error pattern was `"Cannot read properties of undefined (reading 'page_starts_at')"` or `"Cannot read properties of undefined (reading 'page_size')"` -- the server-side pagination handler requires query parameters not sent by default web client requests.

| Endpoint | Previous Status | Current Status | Resolution |
|----------|----------------|----------------|------------|
| `GET /me/related-organizations` | HTTP 500 | **CONFIRMED** | Add `?page_starts_at=0&page_size=50` + `x-pagination: true` header |
| `GET /me/organizations` | HTTP 500 | **CONFIRMED** (empty response) | Add `?page_size=50` + `x-pagination: true` header |
| `GET /organizations/{org_id}/teams` | HTTP 500 | **CONFIRMED** | Add `?page_starts_at=0&page_size=50` + `x-pagination: true` header |
| `GET /organizations/{org_id}/opponent-players` | HTTP 500 | Still blocked | Needs investigation -- `page_size` undefined |

**Workaround confirmed (2026-03-07):** Appending pagination parameters and `x-pagination: true` header resolves the 500s for the three organization/me endpoints above. The same approach should be tried for `GET /organizations/{org_id}/opponent-players`.

### Related Backlog Items

- **IDEA-008** (Plays and Line Scores): Covers `GET /game-stream-processing/{game_stream_id}/plays` (Tier 1) and `GET /public/game-stream-processing/{game_stream_id}/details` (Tier 2). Trigger met -- E-002 and E-004 complete.
- **IDEA-009** (Per-Player Game Stats and Spray Charts): Covers `GET /teams/{team_id}/players/{player_id}/stats` (Tier 1). Trigger met -- E-002 and E-004 complete.
- **IDEA-011** (Investigate HTTP 500 Endpoints): Partially resolved 2026-03-07. Three of four endpoints now confirmed. Remaining: `GET /organizations/{org_id}/opponent-players`.

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

GET /teams/{team_id}
  -> single team detail: name, city, age_group, competition_level, season_year/name
  -> access levels, scorekeeping settings (innings_per_game), organizations, record
  -> CONFIRMED: opponent_id from pregame_data works as team_id (validated 2026-03-04)
  -> use gc-user-action: data_loading:opponents when fetching opponent teams

GET /teams/{team_id}/season-stats
  -> full season batting/pitching/fielding aggregates per player
  -> players keyed by UUID; no names -- cross-reference with /players

GET /teams/{team_id}/opponents
  -> full opponent registry: root_team_id, progenitor_team_id (canonical UUID), name, is_hidden
  -> use progenitor_team_id (not root_team_id) with other team endpoints
  -> alternative to extracting opponent_ids from schedule/game-summaries

GET /teams/{team_id}/game-summaries
  -> extract opponent_id values per game (equivalent to progenitor_team_id in opponents list)

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
| `data_loading:team`        | team detail (`/teams/{id}`) for own team, schedule, `/teams/{id}/users` |
| `data_loading:opponents`   | team detail (`/teams/{id}`) for opponent teams (confirmed 2026-03-04); also `/teams/{id}/opponents` list endpoint |
| `data_loading:team_stats`  | season-stats                 |
| `data_loading:player_stats` | `/teams/{team_id}/players/{player_id}/stats` |
| *(absent)*                  | `/game-stream-processing/{id}/boxscore` -- gc-user-action not observed in capture; may be optional |

**2026-03-04 update:** The 2026-03-04 game-summaries capture used `data_loading:events` (plural) on what was the first page and returned 50 records successfully. The earlier observation of `data_loading:event` (singular) on a first-page request may have been incidental or from a different client code path. Current recommendation: use `data_loading:events` (plural) for game-summaries.

**2026-03-04 update:** `data_loading:opponents` is a distinct value sent when the browser fetches details for an opponent team (not one the user manages). Same endpoint (`GET /teams/{team_id}`), same schema returned, different action label. The distinction is telemetry/analytics on the server side -- both values return 200 OK with the full team object.

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

**Updated 2026-03-04 from decoded JWT payload and POST /auth capture:**

**Token lifetime: 14 days** (confirmed: exp - iat = 1,209,600 seconds from decoded JWT). The earlier estimate of ~1 hour was incorrect. This substantially reduces the frequency of required browser captures for credential rotation.

**Refresh mechanism: `POST /auth` with `{"type":"refresh"}`**

The token refresh flow uses a dedicated POST endpoint (`/auth`) with request signing headers (`gc-signature`, `gc-timestamp`, `gc-client-id`). The signing mechanism prevents programmatic refresh -- the signature requires a secret key embedded in the browser JavaScript that is not yet known.

**gc-timestamp freshness window:** The `gc-signature` and `gc-timestamp` are time-bound. A signature computed 22,316 seconds (~6.2 hours) before the request was rejected with HTTP 400. The actual freshness window is unknown but is at most 22,316 seconds. Browser captures should be executed immediately (within minutes, not hours).

**Practical token lifecycle:**
1. User logs in via browser -- browser receives gc-token (14-day JWT)
2. Browser computes gc-signature from signing key + gc-timestamp and calls `POST /auth` to refresh
3. New gc-token returned -- programmatic code cannot replicate step 2 without the signing key
4. For this project: extract gc-token from fresh browser capture; token is valid for up to 14 days; rotate when expired

**gc-client-id relationship:** The `gc-client-id` request header on `POST /auth` matches the `cid` field in the JWT payload. This is a stable client identifier (not session-specific) that should be stored alongside `gc-device-id` in the `.env` file.

**Previously documented JWT fields `type`, `userId`, `rtkn`** were not observed in the 2026-03-04 decoded payload. These may have been speculative. The actual payload fields are `id`, `cid`, `uid`, `email`, `iat`, `exp`. See JWT Structure section for corrected schema.

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
| `/me/user`                           | `application/vnd.gc.com.user+json; version=0.3.0`                          |
| `/teams/{id}`                        | `application/vnd.gc.com.team+json; version=0.10.0`                         |
| `/teams/{id}/schedule`               | `application/vnd.gc.com.event:list+json; version=0.2.0`                    |
| `/teams/{id}/game-summaries`         | `application/vnd.gc.com.game_summary:list+json; version=0.1.0`             |
| `/teams/{id}/players`                | `application/vnd.gc.com.player:list+json; version=0.1.0`                   |
| `/teams/public/{public_id}/players`  | `application/vnd.gc.com.public_player:list+json; version=0.0.0`            |
| `/teams/{id}/video-stream/assets`    | `application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0` |
| `/teams/{id}/season-stats`           | `application/vnd.gc.com.team_season_stats+json; version=0.2.0`             |
| `/teams/{id}/associations`           | `application/vnd.gc.com.team_associations:list+json; version=0.0.0`        |
| `/teams/{id}/players/{player_id}/stats` | `application/vnd.gc.com.player_stats:list+json; version=0.0.0`         |
| `/public/teams/{public_id}`             | `application/vnd.gc.com.public_team_profile+json; version=0.1.0` -- **no auth required** |
| `/public/teams/{public_id}/games`       | `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0` -- **no auth required** |
| `/public/teams/{public_id}/games/preview` | `application/vnd.gc.com.public_team_event:list+json; version=0.0.0` -- **no auth required** |
| `/teams/{id}/opponents`                 | `application/vnd.gc.com.opponent_team:list+json; version=0.0.0`                          |
| `/game-stream-processing/{id}/boxscore` | `application/vnd.gc.com.event_box_score+json; version=0.0.0`                            |
| `/game-stream-processing/{id}/plays`    | `application/vnd.gc.com.event_plays+json; version=0.0.0`                                |
| `/public/game-stream-processing/{id}/details` | `application/vnd.gc.com.public_team_schedule_event_details+json; version=0.0.0` -- **no auth required** |
| `/events/{event_id}/best-game-stream-id`       | `application/vnd.gc.com.game_stream_id+json; version=0.0.2`                                             |
| `/teams/{id}/users`                            | `application/vnd.gc.com.team_user:list+json; version=0.0.0`                                             |
| `/teams/{id}/public-team-profile-id`           | `application/vnd.gc.com.team_public_profile_id+json; version=0.0.0`                                     |
| `POST /auth`                                   | `*/*` -- **not vendor-typed**. Only POST endpoint; uses standard `Content-Type: application/json; charset=utf-8` for request body. |

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
| 2026-03-07 | BULK CRAWL (50/64 endpoints confirmed 200 OK): Full schema documentation added for team management endpoints (`/users`, `/users/count`, `/relationships`, `/relationships/requests`, `/scoped-features`, `/team-notification-setting`, `/web-widgets`, `/external-associations`, `/avatar-image`), video endpoints (`/video-stream/videos`, `/schedule/events/{event_id}/video-stream`, `/schedule/events/{event_id}/video-stream/assets` full schema, `/video-stream/live-status`, `/rsvp-responses`), public-path endpoints (`/teams/public/{public_id}/access-level` and `/id` -- both REQUIRE AUTH despite path), user endpoints (`/users/{user_id}` full schema confirmed, `/users/{user_id}/profile-photo` 404, `/players/{player_id}/profile-photo` 404), `"invited"` status value confirmed in `/teams/{team_id}/users`. **CONFIRMED non-endpoints:** All season-slug URL patterns (`/teams/{public_id}/{season-slug}/*`) return HTTP 404 on api.team-manager.gc.com -- these are web app frontend routes at web.gc.com, NOT API endpoints. HTTP 500 pagination bug confirmed for `/me/organizations`, `/me/related-organizations`, `/organizations/{org_id}/teams`. |
| 2026-03-07 | PROXY CAPTURE (second session): 75 endpoint patterns catalogued. New high-value discoveries: `GET /teams/{team_id}/opponent/{opponent_id}` (singular `/opponent/` -- per-opponent scouting, 50+ opponents hit -- Tier 1); `GET /bats-starting-lineups/{event_id}` and `GET /bats-starting-lineups/latest/{team_id}` (BATS starting lineup data -- Tier 2); `GET /teams/{team_id}/lineup-recommendation` (GC's algorithmic lineup engine -- Tier 2); `GET /player-attributes/{player_id}/bats` (batter handedness for L/R splits -- Tier 2); `GET /organizations/{org_id}/pitch-count-report` (org-level pitcher pitch counts -- Tier 2); `GET /events/{event_id}` (standalone event detail -- Tier 3); `GET /me/organizations` (org membership discovery -- Tier 3); reverse bridge `GET /teams/public/{public_id}/id` (public_id -> UUID). New URL pattern family documented: **web-route public endpoints** using `GET /teams/{public_id}/{season-slug}/*` (6 endpoints) -- season-slug pattern mirrors web app routing and may provide unauthenticated access to opponent stats/plays (high-priority verification targets). Write operations catalog added: 15 write endpoints (POST/PATCH/PUT/DELETE) covering player management, roster editing, token registration, and team management. New sections in spec: "Proxy-Discovered Endpoints (2026-03-07)", "Bats / Starting Lineups", "Player Attributes", "Events (standalone)", "Organizations (additional)", "Teams -- Additional (2026-03-07)", "Web-Route Public Endpoints", "Me -- Additional (2026-03-07)", "Write Operations Catalog". Priority matrix and ToC updated. |
| 2026-03-05 | CONFIRMED: `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` -- HTTP 200, full schema documented. Response is a single JSON object (~106 KB for a 25-player game) with 6 top-level fields: `stream_id` (game_stream_id UUID, returned inline), `team_id`, `event_id`, `player_stats` (per-game per-player stats), `cumulative_player_stats` (season-to-date for own team; single-game for opponents), `spray_chart_data` (ball-in-play x/y coordinates, play type, play result). Both own-team (GP 60-90) and opponent (GP=1) players are keyed by UUID in the same response. Per-player stats: ~80 offense fields (AB, H, BB, SO, RBI, R, OBP, SLG, OPS, HR, 2B, 3B, SB, CS, PA, TB, ...) and ~26 fielding/pitching fields (IP, ERA, SO, BB, ER, BF, WP, HBP). Cumulative defense: ~149 fields including WHIP, FIP, K/BF, K/BB, K/G, BB/INN, #P, TS. Spray chart: `code: "ball_in_play"`, `attributes.playResult` (single/double/triple/home_run/out/error), `attributes.playType` (hard_ground_ball/ground_ball/line_drive/fly_ball/bunt), `attributes.defenders[].position` (fielder position), `attributes.defenders[].location.x/y` (field coordinates). Accept header: `application/json, text/plain, */*` (not vendor-typed -- unique among confirmed endpoints). No player names or batting order in this endpoint -- join to /players or boxscore for those. `stream_id` returned inline eliminates need for separate ID resolution step. Proxy-discovered entry updated to CONFIRMED. Raw sample: `data/raw/player-stats-sample.json`. |
| 2026-03-05 | PROXY CAPTURE ANALYSIS: 62 unique endpoints observed across `api.team-manager.gc.com`, `media-service.gc.com`, and `vod-archive.gc.com` via mitmproxy intercept of iOS Odyssey app traffic. 12 endpoints already in spec confirmed live. 50 new endpoint patterns discovered including: `/organizations/{uuid}/*` family (teams, events, game-summaries, standings, opponents, users, etc.), `/teams/{uuid}/opponents/players` (bulk opponent roster -- high value), `GET /teams/{uuid}/schedule/events/{uuid}/player-stats` (72 hits -- CRITICAL, may replace game_stream_id resolution), `/me/archived-teams`, `/me/schedule`, `/me/associated-players`, `/game-streams/gamestream-viewer-payload-lite/{uuid}`, `/game-streams/gamestream-recap-story/{uuid}`, `/clips/*`, `/users/{uuid}`, `/places/{place_id}`, `/sync-topics/*`. All added to spec in new "Proxy-Discovered Endpoints" section. iOS header analysis: our canonical browser headers confirmed correct; `gc-app-version: 2026.7.0.0` is iOS app version (our `0.0.0` is web-specific). Two new media CDN hostnames documented: `media-service.gc.com` (signed image/avatar delivery) and `vod-archive.gc.com` (AWS IVS video archive). |
| 2026-03-04 | NEW endpoint: `POST /auth` -- **FIRST POST ENDPOINT. Token refresh flow.** HTTP 400 received (stale gc-signature, not expired gc-token). Request body `{"type":"refresh"}`. New headers discovered: `gc-signature` (HMAC request signature, time-bound), `gc-timestamp` (signing time), `gc-client-id` (stable UUID matching JWT `cid` field), `gc-app-version` (always `"0.0.0"`). `Accept: */*` (not vendor-typed, unlike all other endpoints). JWT payload schema corrected from decoded token: actual fields are `id` (compound `{session_uuid}:{refresh_token_uuid}`), `cid`, `uid`, `email`, `iat`, `exp`. **Token lifetime corrected: 14 days** (exp - iat = 1,209,600 seconds) -- previous 1-hour estimate was wrong. Successful response schema not yet captured -- programmatic refresh is NOT currently possible (signing key unknown). Raw sample (annotated, no live tokens) at `data/raw/auth-refresh-sample.json`. Token Lifecycle section and JWT Structure section updated. |
| 2026-03-04 | NEW endpoint: `GET /teams/{team_id}/public-team-profile-id` -- **UUID-to-public_id bridge**. Authenticated (gc-token + gc-device-id). Returns single JSON object `{"id": "<slug>"}` where `id` is the team's `public_id` slug (12-char alphanumeric). Confirmed: team UUID `cb67372e-b75d-472d-83e3-4d39b6d85eb2` maps to public_id `KCRUFIkaHGXI`. gc-user-action: `data_loading:team` (same as team detail and users endpoints). Accept: `application/vnd.gc.com.team_public_profile_id+json; version=0.0.0`. **Coaching impact**: enables resolving any opponent UUID (from schedule `pregame_data.opponent_id`) to a `public_id` for use with all `/public/teams/{public_id}/...` and `/teams/public/{public_id}/players` endpoints. Opponent behavior unverified -- high-priority follow-up test. Raw sample at `data/raw/public-team-profile-id-sample.json`. |
| 2026-03-04 | NEW endpoint: `GET /teams/{team_id}/users` -- **team user roster**. Authenticated (gc-token + gc-device-id). Page 2 capture (`start_at=100`) returned 33 records. **HEAVY PII**: every record contains `id` (user UUID), `first_name`, `last_name`, `email`, `status`. No role/association field -- endpoint reveals team membership but not user roles. Two `status` values observed: `"active"` (31/33) and `"active-confirmed"` (2/33). Uses `x-pagination: true` request header and `x-next-page` response header (same cursor pattern as game-summaries). gc-user-action: `data_loading:team` (same as team detail endpoint). Accept: `application/vnd.gc.com.team_user:list+json; version=0.0.0`. Team UUID `cb67372e-b75d-472d-83e3-4d39b6d85eb2` (unidentified team, not primary LSB team). Total user count unconfirmed (~133 estimated). Raw sample at `data/raw/team-users-sample.json` fully redacted. |
| 2026-03-04 | NEW endpoint: `GET /events/{event_id}/best-game-stream-id` -- **ID bridge from schedule to game-stream-processing**. Authenticated (gc-token + gc-device-id). Path param is `event_id` from schedule. Returns single-field JSON object: `{"game_stream_id": "<UUID>"}`. Accept: `application/vnd.gc.com.game_stream_id+json; version=0.0.2`. No gc-user-action. Single-call alternative to paginating game-summaries when you have an event_id from the schedule but not a game_stream_id. Completes the ID chain: schedule -> event_id -> /events/{event_id}/best-game-stream-id -> game_stream_id -> boxscore/plays/details. |
| 2026-03-04 | NEW endpoint: `GET /teams/public/{public_id}/players` -- **first LSB team roster captured**. public_id `y24fFdnr3RAN` = LSB Standing Bear JV Grizzlies. 20 players, bare JSON array, 5 fields: `id` (UUID), `first_name`, `last_name`, `number` (string), `avatar_url` (string, empty when unset). 0/20 players have avatar photos. Duplicate jersey number observed (#15 worn by two players). No pagination triggered (all 20 on single page despite `x-pagination: true`). First names returned as initials only -- likely a data-entry pattern on this team, not API behavior. URL pattern DISTINCT from other public endpoints: uses `/teams/public/` not `/public/teams/`. Auth requirement unverified -- gc-token was included in capture but endpoint may work without it. Accept: `application/vnd.gc.com.public_player:list+json; version=0.0.0`. Also: backfilled full schema for authenticated `GET /teams/{team_id}/players` (same 5-field structure, confirmed via this capture). |
| 2026-03-04 | NEW endpoint: `GET /game-stream-processing/{game_stream_id}/plays` -- **pitch-by-pitch play log**. Authenticated (gc-token + gc-device-id required). Same `game_stream.id` path parameter as boxscore. Returns JSON object with 3 keys: `sport` (string), `team_players` (roster dict keyed by team identifier -- same asymmetric slug/UUID format as boxscore), `plays` (array of plate appearances in game order). Each play: `order` (int), `inning` (int), `half` ("top"/"bottom"), `name_template` (outcome label), `home_score`/`away_score` (cumulative after play), `did_score_change` (bool), `outs` (running count 0-3), `did_outs_change` (bool), `at_plate_details` (pitch sequence array), `final_details` (outcome narration array), `messages` (always empty in this sample). Player identities embedded as `${uuid}` template tokens resolved via `team_players`. 58 plays in 6-inning sample (37 KB). Pitch sequence includes Ball N, Strike N looking/swinging, Foul, In play, plus mid-at-bat events (stolen bases, WP advances, balks, lineup changes, pickoff attempts). Final details include contact type and quality (e.g., "hard ground ball", "line drive", "bunt"), fielder positions on outs, and multi-runner scoring narration. No gc-user-action observed. Accept: `application/vnd.gc.com.event_plays+json; version=0.0.0`. Coaching value: full pitch-by-pitch reconstruction, stolen base/baserunning analysis, pitcher sequence by at-bat, contact quality by type, lineup change tracking in-context. |
| 2026-03-04 | NEW endpoint: `GET /public/game-stream-processing/{game_stream_id}/details` -- **UNAUTHENTICATED game details with inning-by-inning line score**. No gc-token or gc-device-id required. Returns single JSON object (12 fields): `id` (game_stream_id UUID), `opponent_team.name`, `is_full_day`, `start_ts`, `end_ts`, `timezone`, `home_away`, `score` (team/opponent_team), `game_status`, `has_videos_available`, `has_live_stream`, `line_score`. The `line_score` object (present when `include=line_scores` sent) has `team` and `opponent_team` keys, each with: `scores` (array of runs per inning, length = innings played) and `totals` (3-element array `[R, H, E]`). Confirmed: totals cross-match authenticated boxscore team_stats R/H values. Uses same `game_stream.id` UUID as authenticated boxscore endpoint. Accept: `application/vnd.gc.com.public_team_schedule_event_details+json; version=0.0.0`. Coaching value: inning-by-inning scoring patterns, R/H/E totals, publicly accessible for any game with known game_stream_id. |
| 2026-03-04 | NEW endpoint: `GET /game-stream-processing/{game_stream_id}/boxscore` -- **UNBLOCKS E-002-03**. Per-game team box score for both home and away teams. Returns a JSON object keyed by team identifier (own team: public_id slug; opponent: UUID -- asymmetric). Each team entry has `players` (full roster with names/numbers), `groups` (array of lineup + pitching stat groups). Main batting stats: AB, R, H, RBI, BB, SO. Main pitching stats: IP, H, R, ER, BB, SO. Sparse "extra" stats: 2B, 3B, HR, TB, HBP, SB, CS, E (lineup); WP, HBP, #P, TS, BF (pitching). Position data encoded in `player_text` string (e.g., `"(CF)"`, `"(SS, P)"`, `"(2B, P, 2B)"`). Batting order is implicit (list order). `is_primary: false` flags substitutes. Player names included -- no join to /players needed. Pitch count (#P) and strikes (TS) in pitching extra array. **Critical ID mapping:** URL param is `game_stream.id` from game-summaries (NOT `event_id` / `game_stream.game_id`). Must go through game-summaries to get this ID; schedule does not expose it. No gc-user-action observed. Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`. |
| 2026-03-04 | NEW endpoint: `GET /public/teams/{public_id}/games/preview` -- **UNAUTHENTICATED sibling of `/games`**. No gc-token or gc-device-id required. Returns bare JSON array of 32 completed games for the same team as `/games` (QTiLIb2Lui3b), same records in same order. Key differences from `/games`: (1) UUID field named `event_id` not `id`, (2) `has_videos_available` field absent, (3) Accept header uses resource type `public_team_event` not `public_team_schedule_event`. 10 fields per record vs 11 in `/games`. All 32 records: `game_status: "completed"`, `has_live_stream: false`. Date range: 2025-05-27 to 2025-07-18. No pagination observed. Use `/games` when `has_videos_available` is needed; `/games/preview` is equivalent otherwise with the field naming caveat. |
| 2026-03-04 | NEW endpoint: `GET /me/user` -- authenticated user profile. Returns single JSON object with 12 top-level fields: `id` (user UUID), `email`, `first_name`, `last_name`, `registration_date`, `status`, `is_bats_account_linked`, `is_bats_team_imported`, `has_subscription`, `access_level`, `subscription_source`, `subscription_information`. The `subscription_information` object carries `best_subscription` (type, provider, billing_cycle, amount_in_cents, end_date, provider_details) and `highest_access_level`. Key use cases: token validity check (200 = valid, 401 = expired), user UUID retrieval. Accept: `application/vnd.gc.com.user+json; version=0.3.0`. No gc-user-action. PII endpoint -- email and names must be redacted in all stored files. |
| 2026-03-04 | NEW endpoint: `GET /public/teams/{public_id}/games` -- **UNAUTHENTICATED public game schedule**. No gc-token or gc-device-id required. Returns bare JSON array of all completed games for a team identified by its `public_id` slug. 32 records from team `QTiLIb2Lui3b` (confirmed live). 11 fields per record: `id` (UUID, matches authenticated schedule), `opponent_team` (name + optional avatar_url), `is_full_day`, `start_ts`, `end_ts`, `timezone`, `home_away`, `score` (team/opponent_team integers), `game_status`, `has_videos_available`, `has_live_stream`. All records: `game_status: "completed"`, `has_live_stream: false`. avatar_url present on 21/32 opponent records. No pagination observed. Accept: `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0`. No gc-user-action. Key coaching implication: final scores + home/away + opponent names available for any team with a known `public_id`, no credentials required. |
| 2026-03-04 | NEW endpoint: `GET /teams/{team_id}/opponents` -- team opponent registry list. Paginated (page size 50, `x-next-page` cursor). 70 records across 2 pages for Lincoln Rebels 14U. 5 fields per record: `root_team_id` (local registry UUID), `owning_team_id` (always matches path param), `name` (display name), `is_hidden` (bool), `progenitor_team_id` (canonical GC team UUID, present on 60/70 records). `progenitor_team_id` is the correct UUID to use with `GET /teams/{id}` and other team endpoints. `root_team_id` is a registry artifact -- do not use as team_id in other endpoints. Accept: `application/vnd.gc.com.opponent_team:list+json; version=0.0.0`, gc-user-action: `data_loading:opponents`. |
| 2026-03-04 | NEW endpoint: `GET /public/teams/{public_id}` -- **UNAUTHENTICATED public endpoint**. No gc-token or gc-device-id required. Returns public team profile: name, sport, ngb, location, age_group, team_season (season/year/record with win/loss/tie), avatar_url (signed CloudFront URL), and staff (array of name strings). Resource type `public_team_profile`, Accept header `application/vnd.gc.com.public_team_profile+json; version=0.1.0`. Key distinctions from authenticated GET /teams/{id}: `id` field is the public_id slug (not UUID), record uses singular keys (`win`/`loss`/`tie` vs `wins`/`losses`/`ties`), record is current-season only (not cumulative). Staff coaching roster available without any credentials. |
| 2026-03-04 | OPPONENT VALIDATION: `GET /teams/{team_id}` confirmed working with opponent `pregame_data.opponent_id` UUIDs from schedule. Sample: SE Elites 14U (Philadelphia PA, 4W/14L/1T). Full 25-field schema returned identically. gc-user-action value `data_loading:opponents` documented (distinct from `data_loading:team` used for own teams). Differences observed: `organizations: []` and `ngb: "[]"` for opponent (vs. populated values for own team -- reflect actual data, not access restrictions). Known Limitations updated to remove "unverified" note. `pregame_data.opponent_id` field in schedule schema marked CONFIRMED for team_id use. |
| 2026-03-04 | NEW endpoint: `GET /teams/{team_id}` -- single team detail object, 910 bytes, 25 fields. Accept header `application/vnd.gc.com.team+json; version=0.10.0` (singular, not list). gc-user-action `data_loading:team` (same as schedule). Key fields: team identity (name, city, state, age_group, competition_level), access levels (stat/scorekeeping/streaming), settings (innings_per_game, shortfielder_type, pitch_count_alerts, maxpreps integration), organizations array, record (wins/losses/ties), created_at, public_id, url_encoded_name, archived. Same ngb double-JSON-parse quirk as /me/teams. Updated gc-user-action table to note team detail uses `data_loading:team`. |
| 2026-03-04 | SCHEMA FULLY DOCUMENTED: `GET /teams/{team_id}/schedule` -- 228-record live capture (103 games, 90 practices, 35 other), 134 KB. Full schema: event object (14 fields), pregame_data (6 fields, games only), location (6 variants), google_place_details sub-object, full-day event handling. Key coaching data: opponent_id in pregame_data (usable as team_id in opponent endpoints), home_away, lineup_id. Date range 2024-11-08 to 2025-07-15. |
| 2026-03-04 | NEW endpoint: `GET /teams/{team_id}/players/{player_id}/stats` -- per-game player stats with rolling cumulative season totals and spray chart data. 80 records, 387 KB, single-page response. Accept header `application/vnd.gc.com.player_stats:list+json; version=0.0.0`, gc-user-action `data_loading:player_stats`. Spray charts confirmed: ball-in-play x/y coordinates, play type, play result, defender positions. Partially answers E-002-03 (per-game breakdowns now available per-player, not as a team box score). |
| 2026-03-04 | Fully documented `/me/teams` response schema: 27 fields across 15 teams, `ngb` double-JSON-parse quirk, `user_team_associations` roles, access level enums, organizations structure. Confirmed LSB high school teams absent -- a separate coaching account is needed. Added `Schema: me-teams` section. |
| 2026-03-04 | Documented `/teams/{team_id}/associations`: 244-record live capture, bare array, 3 fields per record, low player count warning, no pagination triggered. |
| 2026-03-04 | Documented `/teams/{team_id}/season-stats`: full-season batting/pitching/fielding aggregates, complete field tables, stat glossary cross-reference. |
| 2026-03-04 | Documented `/teams/{team_id}/game-summaries` pagination (page 2 of 2, 92 total records, `x-next-page` absence confirms end-of-pagination). |
| 2026-03-04 | Confirmed `/teams/{team_id}/game-summaries` page 1 live (50 records, full season). Documented CloudFront CDN delivery, optional clock fields (42% of records), `total_outs` semantics uncertain. |
| Pre-2026-03-01 | Initial capture of `/me/teams`, `/teams/{team_id}/schedule`, `/teams/{team_id}/players`, `/teams/{team_id}/video-stream/assets` from browser traffic (schemas not fully documented at that time). |
