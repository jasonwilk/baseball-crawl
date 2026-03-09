# API Scout -- Agent Memory

## Credential Lifecycle

**Three-token architecture confirmed 2026-03-07. Programmatic refresh CONFIRMED WORKING.**

**gc-signature CRACKED 2026-03-07.** Algorithm: `{nonce}.{hmac}` where nonce=Base64(32 random bytes) and hmac=HMAC-SHA256(clientKey, timestamp|nonce_bytes|sorted_body_values[|prevSig_bytes]). Full details: `data/raw/gc-signature-algorithm.md`, `docs/api/auth.md`.

**Three token types:**
- **CLIENT token** (exp-iat = 600s = 10 min): `type:"client"`, `sid`, `cid`, `iat`, `exp`. Anonymous session token.
- **ACCESS token** (~61 min web / ~12 hours mobile): `type:"user"`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp`. Sent as gc-token in all standard API calls.
- **REFRESH token** (14 days, self-renewing): `id` (uuid:uuid), `cid`, `uid`, `email`, `iat`, `exp`. No `type` field, different `kid`. Sent as gc-token in POST /auth refresh calls.

**.env variables:** `GAMECHANGER_REFRESH_TOKEN_WEB`, `GAMECHANGER_CLIENT_ID_WEB`, `GAMECHANGER_CLIENT_KEY_WEB` (SECRET), `GAMECHANGER_DEVICE_ID`, `GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`.

**Mobile profile:** Mobile client ID `0f18f027-...` differs from web `07cb985d-...`. Mobile client key UNKNOWN (iOS binary). Programmatic mobile refresh NOT POSSIBLE.

**Token validity check**: `GET /me/user` returns 200 OK (valid) or 401 (expired).

**REFRESH TOKEN EXPIRED (2026-03-09)** -- programmatic refresh failed. User must re-capture via proxy.

Credentials are NEVER logged, committed, or displayed. Redact to `{AUTH_TOKEN}` in all docs.

## API Spec Location

Single source of truth: `docs/api/` -- index at `docs/api/README.md`, per-endpoint files in `docs/api/endpoints/` (104 files as of 2026-03-09).

## Exploration Status

As of 2026-03-09. See `docs/api/README.md` for full endpoint index.

### iOS App Identity (updated 2026-03-09)

- **Odyssey app UA (UPDATED):** `Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0` (was 2026.7.0 prior to session 2026-03-09_062610)
- **gc-app-version on iOS (UPDATED):** `2026.8.0.0` (was `2026.7.0.0`; web app value is `0.0.0`)
- **Media CDN hostnames:** `media-service.gc.com` (signed image delivery) and `vod-archive.gc.com` (AWS IVS video archive).

### Opponent ID Hierarchy (CONFIRMED AND EXPANDED 2026-03-09)

Three IDs per opponent from `GET /teams/{team_id}/opponents`, each used with DIFFERENT endpoints:

| ID | Used With |
|----|-----------|
| `root_team_id` | /opponent/{id}, /teams/{root_team_id}/players, /teams/{root_team_id}/avatar-image |
| `progenitor_team_id` | GET /teams/{progenitor_team_id} -- FULL access to ALL /teams/{id}/* endpoints |
| `public_id` | All /public/teams/{public_id} endpoints |

**KEY DISCOVERY (session 2026-03-09_063531):** `progenitor_team_id` gives FULL access to the opponent's team data via all `/teams/{team_id}/*` endpoints:
- `/teams/{progenitor_team_id}` -- team metadata
- `/teams/{progenitor_team_id}/game-summaries` -- all their games
- `/teams/{progenitor_team_id}/schedule` -- full schedule
- `/teams/{progenitor_team_id}/schedule/events/{event_id}/player-stats` -- per-game player stats (55 calls all 200!)
- `/teams/{progenitor_team_id}/season-stats` -- season aggregates
- `/teams/{progenitor_team_id}/players` -- roster
- `/teams/{progenitor_team_id}/opponents` -- their opponents
- `/teams/{progenitor_team_id}/opponents/players` -- all their opponent player data
- `/teams/{progenitor_team_id}/users` -- team users
- `/teams/{progenitor_team_id}/associations` -- org memberships

This means: by obtaining an opponent's `progenitor_team_id` from search results or our own opponents list, we have the SAME data access for any team as we do for our own teams. This is the foundation of the entire scouting data pipeline.

**Nighthawks Navy AAA 14U example:** root=`bd05f3d5-...`, progenitor=`14fd6cb6-...`, public_id=`smgRExWHuBJJ`

**CORRECTION (2026-03-09):** Previous docs incorrectly said "use progenitor_team_id for /players and /avatar-image". That is WRONG. Use `root_team_id` for both. Endpoint files updated.

### 2026-03-09 Key Findings (session 2026-03-09_061156)

- **NEW: `POST /clips/search/v2`** -- video clip search POST body query. CT: `application/vnd.gc.com.video_clip_search_query+json; version=0.0.0`. Body/response schema unknown.
- **NEW: `PATCH /players/{player_id}`** -- update player attributes. CT: `application/vnd.gc.com.patch_player+json; version=0.1.0`. Body/response schema unknown.
- **NEW: `GET /game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}`** -- HTTP 404 only. Route registered; purpose unclear (stat correction tracking?).
- **`/public/game-stream-processing/{id}/details` accepts event_id directly** -- confirmed 200 OK with event_id. No need for /best-game-stream-id lookup when using this endpoint.
- **`/teams/{id}/avatar-image` returns HTTP 404** (not 200 with null) when team has no avatar set.
- **`/bats-starting-lineups/{event_id}` confirmed 200 OK** for home game event_id `387c28f7-...` (2026-03-09).

### 2026-03-09 Key Findings (session 2026-03-09_062610, MOBILE)

**App version update:** iOS app upgraded to `2026.8.0` / `gc-app-version: 2026.8.0.0`. All mobile UA strings and header examples updated in `docs/api/headers.md`.

**Opponent Import Flow (fully documented):**
1. `GET /search/opponent-import` (search-as-you-type, 3 calls per user interaction)
2. `GET /teams/{opponent_uuid}/import-summary` (check available stats -- NEW endpoint)
3. `POST /teams/{my_team_id}/opponent/import` (create association -- NEW endpoint, HTTP 201)
4. `GET /teams/{my_team_id}/opponent/{opponent_id}` (fetch result)
5. `GET /teams/{opponent_id}/players` + `GET /player-attributes/{id}/bats` ×11 (populate roster)

**Game Creation Flow:** `POST /teams/{team_id}/schedule/events` (HTTP 201, NEW) followed within 8 seconds by `PATCH /teams/{team_id}/schedule/events/{event_id}` (HTTP 200, NEW) -- create-then-patch pattern.

**Mobile-only third-party token endpoints (startup sequence, not relevant for ingestion):**
- `POST /me/tokens/stream-chat` -- Stream.io chat JWT (HTTP 200)
- `POST /me/tokens/firebase` -- Firebase push notification device token (HTTP 204, no body)

**Mobile clip search:** iOS uses `POST /clips/search` (no /v2 suffix); web uses `POST /clips/search/v2`. Same content-type. Both documented.

**Write endpoint content-types confirmed:**
- `POST /opponent/import`: `application/vnd.gc.com.post_opponent_team_import+json; version=0.0.0`
- `PATCH /opponent/{id}`: `application/vnd.gc.com.patch_opponent_team+json; version=0.0.0` (resp: text/plain)
- `POST /schedule/events`: `application/vnd.gc.com.post_event+json; version=0.3.0`
- `PATCH /schedule/events/{id}`: `application/vnd.gc.com.patch_event+json; version=0.6.0` (resp: JSON)

### HTTP 500 (pagination bugs)
- `/organizations/{org_id}/teams`, `/me/organizations`, `/me/related-organizations` -- try `?page_size=50` or `?start_at=0`.

### Confirmed HTTP 404 / 403 patterns
- `/bats-starting-lineups/{event_id}` -- HTTP 403 for away game event_id (scorer access only)
- `/teams/{team_id}/avatar-image` -- HTTP 404 when team has no avatar (not an error -- treat as "no avatar")
- `/teams/{team_id}/public-team-profile-id` -- HTTP 403 for opponent team UUIDs (own-team only)
- `/teams/public/{public_id}/id` -- HTTP 403 for opponent public_ids (own-team only)
- `/game-streams/insight-story/bats/{event_id}` and `/player-insights/bats/{event_id}` -- feature not available

### 2026-03-09 Key Findings (session 2026-03-09_063531, MOBILE SEARCH + OPPONENT NAVIGATION)

**NEW: `POST /search`** -- Main mobile GC app search. Content-type: `application/vnd.gc.com.post-search+json; version=0.0.0`. Query param: `start_at_page`. 6 hits (search-as-you-type for "nighthawks"). Body/response schema unknown.

**NEW: `POST /search/history`** -- Records a user's search selection. Content-type: `application/vnd.gc.com.add_search_history+json; version=0.0.0`. Response is text/plain HTTP 200. Called after user taps a result.

**MOBILE SEARCH FLOW confirmed:** `GET /search/history` (on open) → `POST /search` (repeated as user types) → `POST /search/history` (on selection) → navigate to team.

**OPPONENT FULL ACCESS via progenitor_team_id CONFIRMED:** The mobile app navigates into the Nighthawks team using `progenitor_team_id` (`14fd6cb6`) and calls ALL the same `/teams/{id}/*` endpoints as it does for own teams. 55 calls to `/schedule/events/{event_id}/player-stats` all returned HTTP 200. This is the core scouting data access pattern.

### Areas Not Yet Explored / High-Priority

- **`POST /search` BODY SCHEMA** -- request body and response body not captured. Live curl needed to see query field names and response structure.
- **`GET /search/opponent-import` RESPONSE BODY** -- endpoint confirmed 200 OK (both mobile and web profiles) but proxy only captures metadata, not JSON. Live curl needed.
- **`GET /teams/{team_id}/import-summary` RESPONSE BODY** -- endpoint confirmed 200 OK but body not captured. Schema unknown.
- **LSB coaching account credentials** -- current credentials are travel ball only. LSB HS teams not visible.
- **`POST /clips/search` and `/v2` schemas** -- body and response format unknown for both.
- **`PATCH /players/{player_id}` schema** -- body and response format unknown.
- **`GET /organizations/{uuid}/game-summaries`** -- test with LSB org UUID when credentials available.
- **DELETE /teams/{team_id}/schedule/events/{event_id}** -- user "deleted a game" in this session but no DELETE was observed; either it uses a PATCH with a cancel/delete field or was not captured.

### Boxscore Endpoint Critical Facts

- **URL param is `game_stream.id` from game-summaries** (NOT `event_id` or `game_stream.game_id`)
- **Asymmetric team key format**: own team key = public_id slug; opponent key = UUID
- **Groups**: `"lineup"` (batting: AB/R/H/RBI/BB/SO) and `"pitching"` (IP/H/R/ER/BB/SO)
- Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`

## JWT Payload Decode Tips

`exp-iat < 1000` = client (10 min). `exp-iat < 50000` = access (~61 min web OR ~12 hours mobile). `exp-iat > 1000000` = refresh (14 days).

## Security Rules

Never display/log/store credentials. Use `{AUTH_TOKEN}` placeholders. Strip auth headers from raw responses.

**PII hotspots:** `/teams/{team_id}/users` (emails), `/users/{user_id}` (name+email), `/me/associated-players` (player names across teams).
