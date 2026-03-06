# API Scout -- Agent Memory

## Credential Lifecycle

**Token lifetime: 14 days** (confirmed 2026-03-04 from decoded JWT payload: exp - iat = 1,209,600 seconds). Previous 1-hour estimate was wrong.

Credentials from browser captures are valid for up to 14 days. The `scripts/refresh_credentials.py` script extracts and stores them in `.env`.

**Token validity check**: `GET /me/user` returns 200 OK if the token is valid, 401 if expired. Use as a lightweight auth check before long ingestion runs.

**gc-signature freshness**: When the user provides a curl for `POST /auth` (token refresh), the `gc-signature`/`gc-timestamp` headers are time-bound. A signature 22,316 seconds (~6.2 hours) old was rejected with HTTP 400. Execute auth curl commands immediately -- within minutes, not hours.

**Programmatic refresh: NOT YET POSSIBLE.** The `POST /auth` endpoint requires a `gc-signature` computed with an unknown signing key. Until the signing algorithm is known, fresh tokens must come from browser captures.

**gc-client-id**: New credential field discovered 2026-03-04. Stable UUID matching the `cid` field in the JWT payload. Store alongside `gc-device-id` in `.env`.

Credentials are NEVER logged, committed, or displayed. Redact to `{AUTH_TOKEN}` in all documentation and output.

## API Spec Location

Single source of truth: `docs/gamechanger-api.md`

All discoveries go into the spec immediately. Do not accumulate findings in memory or conversation -- write to the spec file.

## Exploration Status

As of 2026-03-05. All API knowledge is empirical -- discovered by running curl commands provided by the user, plus proxy capture analysis.

### iOS App Identity (confirmed 2026-03-05)

- **Odyssey app UA:** `Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0`
- **gc-app-version on iOS:** `2026.7.0.0` (not `0.0.0` -- that is the web app value)
- **Our browser headers confirmed correct** for api.team-manager.gc.com. No changes needed.
- **Media CDN hostnames discovered:** `media-service.gc.com` (signed image delivery) and `vod-archive.gc.com` (AWS IVS video archive).

### Confirmed Endpoints

| Endpoint | Status | Discovered |
|----------|--------|------------|
| `GET /me/user` | CONFIRMED LIVE, 12 fields. Token validity check. | 2026-03-04 |
| `GET /me/teams` | Schema FULLY DOCUMENTED, 15 teams, 27 fields | 2026-03-04 |
| `GET /teams/{id}` | Schema FULLY DOCUMENTED, 25 fields. Opponent UUID confirmed. | 2026-03-04 |
| `GET /teams/{id}/schedule` | FULLY DOCUMENTED, 228 events (103 games) | 2026-03-04 |
| `GET /teams/{id}/game-summaries` | CONFIRMED, 92 total records, 2 pages | 2026-03-04 |
| `GET /teams/{id}/players` | Schema CONFIRMED (5 fields: id, first_name, last_name, number, avatar_url). No pagination. Backfilled from public variant. | Pre-2026-03-01, schema 2026-03-04 |
| `GET /teams/public/{public_id}/players` | CONFIRMED LIVE, 200 OK. 20 players (LSB JV). Same 5 fields as authenticated /players. URL uses `/teams/public/` NOT `/public/teams/`. Accept: `public_player:list+json; version=0.0.0`. Auth requirement unverified (credentials included but may not be required). First names returned as initials on this team -- may be data-entry pattern, not API behavior. | 2026-03-04 |
| `GET /teams/{id}/video-stream/assets` | Confirmed, 3 pages | Pre-2026-03-01 |
| `GET /teams/{id}/season-stats` | CONFIRMED LIVE, 200 OK | 2026-03-04 |
| `GET /teams/{id}/associations` | CONFIRMED, 244 records, single page | 2026-03-04 |
| `GET /teams/{id}/players/{player_id}/stats` | CONFIRMED, 80 records, per-game + spray charts | 2026-03-04 |
| `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` | CONFIRMED LIVE, 200 OK. 106 KB, 25 players (both teams). Three sections: player_stats (this-game), cumulative_player_stats (season for own team, single-game for opponents), spray_chart_data (x/y coordinates). No player names -- join needed. Accept: `application/json, text/plain, */*` (unique -- not vendor-typed). stream_id returned inline. Raw sample: `data/raw/player-stats-sample.json`. | 2026-03-05 |
| `GET /public/teams/{public_id}` | CONFIRMED, NO AUTH REQUIRED | 2026-03-04 |
| `GET /public/teams/{public_id}/games` | CONFIRMED, NO AUTH REQUIRED, 32 games | 2026-03-04 |
| `GET /public/teams/{public_id}/games/preview` | CONFIRMED, NO AUTH REQUIRED, sibling of /games | 2026-03-04 |
| `GET /teams/{id}/opponents` | CONFIRMED, 70 records, 2 pages | 2026-03-04 |
| `GET /game-stream-processing/{game_stream_id}/boxscore` | **CONFIRMED LIVE, 200 OK. UNBLOCKS E-002-03.** JSON object keyed by team (public_id slug for own team, UUID for opponent). Two groups per team: lineup (batting) and pitching. Main stats + sparse extra array. Player names included. See `endpoint-notes.md` for critical details. | 2026-03-04 |
| `GET /game-stream-processing/{game_stream_id}/plays` | **CONFIRMED LIVE, 200 OK.** Pitch-by-pitch play log. 58 plays, 6-inning game, 37 KB. JSON object: `sport`, `team_players` (same asymmetric slug/UUID keys as boxscore), `plays` (array). Each play: `order`, `inning`, `half`, `name_template`, `home_score`, `away_score`, `did_score_change`, `outs`, `did_outs_change`, `at_plate_details` (pitch sequence), `final_details` (outcome narration), `messages` (always empty). Player UUIDs embedded as `${uuid}` in all template strings. Same `game_stream.id` param as boxscore. No gc-user-action. Accept: `event_plays+json; version=0.0.0`. | 2026-03-04 |
| `GET /public/game-stream-processing/{game_stream_id}/details` | **CONFIRMED LIVE, NO AUTH REQUIRED.** Single game object with inning-by-inning line score. `include=line_scores` param required for `line_score` field. `line_score.*.scores` = runs per inning array; `line_score.*.totals` = [R, H, E]. Same `game_stream_id` as boxscore. Complementary: public details for line score, authenticated boxscore for player stats. | 2026-03-04 |
| `GET /events/{event_id}/best-game-stream-id` | **CONFIRMED LIVE, 200 OK.** Resolves schedule `event_id` to `game_stream_id`. Single-field response: `{"game_stream_id": "<UUID>"}`. Accept: `game_stream_id+json; version=0.0.2`. No gc-user-action. Bridge between schedule and game-stream-processing endpoints. | 2026-03-04 |
| `GET /teams/{id}/users` | **CONFIRMED LIVE, 200 OK.** Team user roster. PAGE 2 ONLY (start_at=100), 33 records. HEAVY PII: id (UUID), first_name, last_name, email, status. No role field. status values: "active" (majority), "active-confirmed" (2/33). gc-user-action: data_loading:team. Accept: `team_user:list+json; version=0.0.0`. Team UUID cb67372e (unidentified, not primary LSB team). | 2026-03-04 |
| `GET /teams/{id}/public-team-profile-id` | **CONFIRMED LIVE, 200 OK. UUID-to-public_id BRIDGE.** Returns single JSON object `{"id": "<slug>"}`. team UUID cb67372e -> public_id `KCRUFIkaHGXI`. Auth required (gc-token present in capture). gc-user-action: data_loading:team. Accept: `team_public_profile_id+json; version=0.0.0`. **Critical: opponent UUID behavior unverified -- highest priority follow-up.** Enables full opponent public API access from schedule opponent_id. | 2026-03-04 |
| `POST /auth` | **HTTP 400 received (stale gc-signature, ~6.2 hrs old). Endpoint confirmed to exist.** First POST endpoint. Body: `{"type":"refresh"}`. New headers: `gc-signature` (time-bound HMAC, format: `{b64}.{b64}`), `gc-timestamp` (Unix seconds, server validates freshness), `gc-client-id` (UUID = JWT `cid` field), `gc-app-version` (`"0.0.0"`). Accept: `*/*`. No gc-user-action. Successful response schema UNKNOWN -- cannot replicate (signing key unknown). Annotated sample at `data/raw/auth-refresh-sample.json`. | 2026-03-04 |

### Proxy-Observed Endpoints (2026-03-05, schema unknown)

50 new endpoint patterns observed in iOS mitmproxy capture. Full details in spec section "Proxy-Discovered Endpoints (2026-03-05)". Key patterns:
- `/organizations/{uuid}/*` -- teams, events, game-summaries, standings, opponents, users, etc.
- `/teams/{uuid}/opponents/players` -- bulk opponent roster (paginated, 24 hits)
- `/teams/{uuid}/schedule/events/{uuid}/player-stats` -- CRITICAL (72 hits, may replace boxscore flow)
- `/me/archived-teams`, `/me/schedule`, `/me/associated-players`, `/me/teams-summary`
- `/game-streams/gamestream-viewer-payload-lite/{uuid}`, `/game-streams/gamestream-recap-story/{uuid}`
- `/clips/{uuid}`, `POST /clips/search`, `GET /users/{uuid}`, `GET /places/{place_id}`
- `PATCH /me/user`, `POST /teams/{uuid}/follow`

### Boxscore Endpoint Critical Facts (confirmed 2026-03-04)

- **URL param is `game_stream.id` from game-summaries** (NOT `event_id` or `game_stream.game_id`)
- **ID chain (via game-summaries)**: game-summaries -> `game_stream.id` -> boxscore URL
- **ID chain (via schedule)**: schedule -> `event.id` -> `GET /events/{event_id}/best-game-stream-id` -> `game_stream_id` -> boxscore URL
- **Asymmetric team key format**: own team key = public_id slug; opponent key = UUID
- **Player names included** in `players` array (id, first_name, last_name, number) -- no join needed
- **Groups**: `"lineup"` (batting: AB/R/H/RBI/BB/SO) and `"pitching"` (IP/H/R/ER/BB/SO)
- **Sparse extras (lineup)**: 2B, 3B, HR, TB, HBP, SB, CS, E -- only non-zero players listed
- **Sparse extras (pitching)**: WP, HBP, #P (pitch count), TS (strikes), BF (batters faced)
- **Batting order**: implicit -- list order = batting order
- **`is_primary: false`** flags substitutes in lineup group; absent from pitching group
- **`player_text`**: position string in lineup (e.g., `"(CF)"`, `"(SS, P)"`), decision in pitching (`"(W)"`, `"(L)"`, `""`)
- **No gc-user-action** in this capture -- likely optional
- Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`

### E-002-03 Status: UNBLOCKED

`GET /game-stream-processing/{game_stream_id}/boxscore` is the true team box score endpoint. It provides per-player batting and pitching lines for both teams. **E-002-03 is now unblocked.** Notify PM.

### Key Facts Reference

Detailed per-endpoint facts moved to `endpoint-notes.md` to keep this file under 200 lines.

### Areas Not Yet Explored / High-Priority Follow-Ups

**CRITICAL PRIORITY:**
- **`GET /teams/{uuid}/schedule/events/{uuid}/player-stats`**: CONFIRMED 2026-03-05. Returns both teams' per-game + cumulative stats + spray charts in one call. No game_stream_id needed. Accept: `application/json, text/plain, */*`. stream_id returned inline. No player names (join needed). This IS the optimal ingestion path. Full doc in API spec and `data/raw/player-stats-sample.json`.
- **`GET /organizations/{uuid}/game-summaries`**: If available on LSB coaching account, returns all org games in one call vs. per-team pagination. Execute with LSB org UUID when LSB coaching credentials are available.
- **`GET /teams/{uuid}/opponents/players`**: Bulk opponent player endpoint -- 24 hits in proxy. May be the most efficient way to load all opponent rosters. Schema unknown.

**HIGH PRIORITY:**
- LSB coaching account gc-token -- all current credentials are travel ball account. LSB HS teams not visible.
- `GET /organizations/{uuid}/teams` -- may return all LSB teams (Freshman, JV, Varsity, Reserve) in one call if LSB has an org UUID.
- PUBLIC-TEAM-PROFILE-ID with opponent UUIDs -- does `/teams/{opponent_uuid}/public-team-profile-id` work? Unlocks all public API endpoints for opponents.
- `GET /me/archived-teams` -- historical season data.

**ONGOING:**
- AUTH FLOW PARTIAL: `POST /auth` confirmed (400 received). Successful response schema unknown. Signing key unknown.
- Opponent endpoint access: `/teams/{opponent_id}/season-stats`, game-summaries, boxscore
- `streak_C` (cold streak, unconfirmed); `total_outs` semantics; ETag conditional requests
- BOXSCORE: Does game_stream_id for opponent's own game-summaries work in boxscore?
- PLAYS: Public unauthenticated variant? Extra-innings behavior? Pitch speed/location data?
- ROSTER: Does `/teams/public/{public_id}/players` work without gc-token?
- BEST-GAME-STREAM-ID: Works for future/scheduled games? Opponent event_ids?

## JWT Payload Fields (Confirmed 2026-03-04)

Actual fields: `id` (compound `{session_uuid}:{refresh_token_uuid}`), `cid` (= gc-client-id header), `uid` (user UUID), `email`, `iat`, `exp`. Previous docs listed `type`, `userId`, `rtkn` -- these were NOT observed. Consider them unconfirmed/incorrect until re-verified.

## Security Rules

Never display/log/store credentials. Use `{AUTH_TOKEN}` placeholders. Strip auth headers from raw responses.

## Key File Paths

API spec: `docs/gamechanger-api.md` | Stat glossary: `docs/gamechanger-stat-glossary.md` | Creds: `.env` | HTTP: `src/http/headers.py`, `src/http/session.py`
