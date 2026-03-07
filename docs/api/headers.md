# Request Headers

## Header Profiles

GameChanger has been tested with two header profiles: web browser (primary) and iOS mobile (observed via proxy). The web profile is what this project uses. The mobile profile is documented for reference.

### Web Profile (Primary)

Used by the GameChanger web app at `https://web.gc.com`. This is the profile implemented in `src/http/headers.py` as `BROWSER_HEADERS`.

#### Minimal Confirmed Headers (Authenticated Request)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: {resource-specific value}
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
```

#### Full Browser-Mimicking Header Set (Recommended)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
gc-user-action: {action string}
gc-user-action-id: {UUID}
Accept: {resource-specific value}
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

### Mobile Profile (iOS -- Observed)

Used by the GameChanger iOS Odyssey app. Observed via mitmproxy capture (2026-03-05). Not implemented as a code profile -- documented for reference.

Key differences from the web profile:

| Header | Web Value | iOS Value |
|--------|-----------|-----------|
| `gc-app-name` | `web` | `mobile` (inferred) |
| `gc-app-version` | (absent) | `2026.7.0.0` (iOS app version) |
| `User-Agent` | Chrome/145 UA | `GameChanger/2026.7.0.0 iOS/18.3.1` style |
| `x-gc-origin` | (absent) | `sync` (on sync endpoints only) |
| `x-datadog-origin` | (absent) | `rum` (Datadog RUM telemetry) |

## GC-Specific Headers

### Authentication Headers

| Header | Required | Description |
|--------|----------|-------------|
| `gc-token` | Yes (auth endpoints) | Access token JWT (~60 min lifetime). See `auth.md` for full three-token architecture. |
| `gc-device-id` | Yes (auth endpoints) | Stable 32-character hex string. Unique per device. Store alongside gc-token. |
| `gc-app-name` | Yes | Always `"web"` for the web profile. |

### Action Tracking Headers

| Header | Required | Description |
|--------|----------|-------------|
| `gc-user-action` | Optional | Telemetry string describing the user action that triggered this request. Include when mimicking browser behavior for endpoints where it was observed. |
| `gc-user-action-id` | Optional | UUID for the specific user action instance. Generate a new UUID per request when including this header. |

Observed `gc-user-action` values:

| Value | Seen on endpoint |
|-------|-----------------|
| `data_loading:events` | game-summaries, video-stream/assets |
| `data_loading:team` | team detail, schedule, users, public-team-profile-id |
| `data_loading:opponents` | team detail for opponent teams, opponents list |
| `data_loading:team_stats` | season-stats |
| `data_loading:player_stats` | players/{player_id}/stats |

### Signature Headers (POST /auth Only)

These headers are used exclusively by `POST /auth` and are not required for any GET endpoint:

| Header | Description |
|--------|-------------|
| `gc-signature` | HMAC-SHA256 signature computed from `clientKey`. Format: `{nonce}.{hmac}` where nonce is Base64(random 32 bytes) and hmac is HMAC-SHA256(clientKey, timestamp\|nonce_bytes\|sorted_body_values[\|previousSig_bytes]). Algorithm fully reverse-engineered 2026-03-07. See `auth.md` for full details. |
| `gc-timestamp` | Unix timestamp in seconds at signing time. Must be current -- stale timestamps (~6+ hours) are rejected with HTTP 400. |
| `gc-client-id` | Stable UUID matching the `cid` field in the JWT payload. The `clientId` half of the app bundle's `clientId:clientKey` string. |
| `gc-app-version` | Always `"0.0.0"` (web profile). Absent on GET endpoints; present on POST /auth. |

### Pagination Request Header

| Header | Value | Description |
|--------|-------|-------------|
| `x-pagination` | `true` | Must be sent with paginated requests. Absent on non-paginated endpoints. See `pagination.md`. |

## Accept Headers by Endpoint

The `Accept` header uses a vendor-typed media type specific to each resource. See each endpoint file's frontmatter `accept` field for the value to use.

Quick reference table:

| Endpoint | Accept header value |
|----------|---------------------|
| `GET /me/teams` | `application/vnd.gc.com.team:list+json; version=0.10.0` |
| `GET /me/user` | `application/vnd.gc.com.user+json; version=0.3.0` |
| `GET /teams/{id}` | `application/vnd.gc.com.team+json; version=0.10.0` |
| `GET /teams/{id}/schedule` | `application/vnd.gc.com.event:list+json; version=0.2.0` |
| `GET /teams/{id}/game-summaries` | `application/vnd.gc.com.game_summary:list+json; version=0.1.0` |
| `GET /teams/{id}/players` | `application/vnd.gc.com.player:list+json; version=0.1.0` |
| `GET /teams/public/{public_id}/players` | `application/vnd.gc.com.public_player:list+json; version=0.0.0` |
| `GET /teams/{id}/video-stream/assets` | `application/vnd.gc.com.video_stream_asset_metadata:list+json; version=0.0.0` |
| `GET /teams/{id}/season-stats` | `application/vnd.gc.com.team_season_stats+json; version=0.2.0` |
| `GET /teams/{id}/associations` | `application/vnd.gc.com.team_associations:list+json; version=0.0.0` |
| `GET /teams/{id}/players/{player_id}/stats` | `application/vnd.gc.com.player_stats:list+json; version=0.0.0` |
| `GET /public/teams/{public_id}` | `application/vnd.gc.com.public_team_profile+json; version=0.1.0` |
| `GET /public/teams/{public_id}/games` | `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0` |
| `GET /public/teams/{public_id}/games/preview` | `application/vnd.gc.com.public_team_event:list+json; version=0.0.0` |
| `GET /teams/{id}/opponents` | `application/vnd.gc.com.opponent_team:list+json; version=0.0.0` |
| `GET /game-stream-processing/{id}/boxscore` | `application/vnd.gc.com.event_box_score+json; version=0.0.0` |
| `GET /game-stream-processing/{id}/plays` | `application/vnd.gc.com.event_plays+json; version=0.0.0` |
| `GET /public/game-stream-processing/{id}/details` | `application/vnd.gc.com.public_team_schedule_event_details+json; version=0.0.0` |
| `GET /events/{event_id}/best-game-stream-id` | `application/vnd.gc.com.game_stream_id+json; version=0.0.2` |
| `GET /teams/{id}/users` | `application/vnd.gc.com.team_user:list+json; version=0.0.0` |
| `GET /teams/{id}/public-team-profile-id` | `application/vnd.gc.com.team_public_profile_id+json; version=0.0.0` |
| `POST /auth` | `*/*` (not vendor-typed -- unique exception) |

## Implementation Notes

### Auth Injection

The `src/http/session.py` factory creates sessions. GameChanger uses `gc-token` instead of `Authorization: Bearer`. Override session defaults:

```python
session = create_session()
session.headers["gc-token"] = gc_token          # from env
session.headers["gc-device-id"] = gc_device_id  # from env
session.headers["gc-app-name"] = "web"
```

### Optional vs. Required Headers

Based on observed captures:

- `gc-user-action` and `gc-user-action-id` are absent from `/players` and `/associations` captures -- both appear optional. Include when mimicking browser behavior for endpoints where they were observed.
- Navigation headers (`sec-fetch-*`, `cache-control`, `pragma`, `origin`, `priority`) appear in schedule and /me/teams captures -- likely browser-added during page navigation. May not be required by the API, but include them to match the browser fingerprint.

### Additional iOS-Only Headers (Not in Web Profile)

The following were observed in iOS traffic and are NOT included in `MOBILE_HEADERS` for the stated reasons:
- `x-gc-origin: sync` -- only on sync infrastructure endpoints, not data endpoints
- `x-datadog-origin: rum` -- Datadog telemetry, not needed
- `if-none-match` -- ETag conditional GET; could be added for efficiency but not currently implemented
- `priority: u=3, i` -- HTTP priority hint; browser sends `u=1, i` on some requests; optional
