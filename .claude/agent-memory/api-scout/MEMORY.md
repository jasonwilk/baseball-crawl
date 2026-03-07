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

As of 2026-03-07. All API knowledge is empirical -- discovered by running curl commands provided by the user, plus proxy capture analysis.

### iOS App Identity (confirmed 2026-03-05)

- **Odyssey app UA:** `Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0`
- **gc-app-version on iOS:** `2026.7.0.0` (not `0.0.0` -- that is the web app value)
- **Our browser headers confirmed correct** for api.team-manager.gc.com. No changes needed.
- **Media CDN hostnames discovered:** `media-service.gc.com` (signed image delivery) and `vod-archive.gc.com` (AWS IVS video archive).

### Live Probe Session (2026-03-07) -- Key Findings

50 of 64 endpoints returned 200 OK. Key discoveries:

**NEW CONFIRMED ENDPOINTS:**
- `/teams/{team_id}/opponents/players` -- 758 records, 61 teams. Includes handedness (batting_side, throwing_hand) inline. Best bulk opponent data call.
- `/teams/{team_id}/opponent/{opponent_id}` -- singular form. 5 fields: root_team_id, owning_team_id, name, is_hidden, progenitor_team_id.
- `/teams/{team_id}/lineup-recommendation` -- GC algorithm. Returns 9 players with field_position and batting_order. generated_at changes each call (live calculation).
- `/bats-starting-lineups/latest/{team_id}` -- actual coach-entered lineup. latest_lineup wrapper with entries[] array (order = batting order). DH fields present but null when not used.
- `/bats-starting-lineups/{event_id}` -- HTTP 403 for away game event. Try home game event_id.
- `/player-attributes/{player_id}/bats` -- {player_id, throwing_hand, batting_side}. Prefer /opponents/players for bulk.
- `/game-streams/{game_stream_id}/events` -- 319 events, 10 codes (set_teams, fill_lineup_index, reorder_lineup, fill_position, sub_players, pitch, transaction, base_running, edit_group, replace_runner, undo). event_data is JSON-encoded STRING -- must JSON.parse it.
- `/game-streams/gamestream-viewer-payload-lite/{event_id}` -- accepts event_id (NOT game_stream_id). Returns stream_id, latest_events (319), all_event_data_ids, marker.
- `/events/{event_id}` -- two-key object: event{} + pregame_data{}. pregame_data.lineup_id links to bats-starting-lineups.
- `/me/schedule` -- 26 teams, 71 events, config{max_future_days:180, max_past_days:90, max_teams:150}. Events include RSVPs and video status inline. expire_in_seconds:30.
- `/me/associated-players` -- cross-team player tracking. teams{}, players{}, associations{}. Shows same player UUID per team across seasons (longitudinal tracking).
- `/me/archived-teams` -- 8 archived teams (2019-2023). Same schema as /me/teams. ngb field is double-serialized JSON string.
- `/me/advertising/metadata` -- ppid, do_not_sell, is_staff, targeting{age-groups, comp-levels, sports, subscription-type}.
- `/me/subscription-information` -- best_subscription{type, provider_type, end_date, access_level, billing_cycle, amount_in_cents, provider_details{will_renew}}, highest_access_level, is_free_trial_eligible.
- `/me/team-tile/{team_id}` -- compact team + record + badge_count.
- `/subscription/details` -- full subscription with plan{provider, code, level, tier, max_allowed_members}, status flags, billing_info, dates{start, end}, is_owner.
- `/subscription/recurly/plans` -- 6 plans (plus-month $9.99, plus-year $39.99, premium-month $14.99, premium-year $99.99, premium-shared-month $24.99, premium-shared-year $179.99).
- `/search/history` -- max_results:10. Each result: type:"team" with id, public_id, name, sport, season, location, staff[], number_of_players.
- `/announcements/user/read-status` -- {"read_status": "read"}.
- `/sync-topics/me/updated-topics` -- {"status":"update-all", "updates":[], "next_cursor":"v2_{seq}_{ts}_{user_id}_{n}_{uuid}"}.
- `/organizations/{org_id}/standings` -- array per team: home/away/overall/last10 W-L-T, winning_pct, runs{scored/allowed/differential}, streak{count/type}.
- `/organizations/{org_id}/team-records` -- same schema as /standings (identical response structure).
- `/organizations/{org_id}/pitch-count-report` -- CSV STRING (not JSON). Columns: Game Date, Start Time, Pitcher, Team, Opponent, Pitch Count, "Last Batter First Pitch #", IP, IC, Final Score, Scored By.
- `/organizations/{org_id}/events` and `/game-summaries` -- return [] for travel ball org.
- `/organizations/{org_id}/scoped-features` -- {"scoped_features": {}}.
- `/teams/public/{public_id}/id` -- {"id": UUID}. Reverse bridge confirmed: a1GFM9Ku0BbF -> 72bb77d8-...
- `/teams/public/{public_id}/access-level` -- {"paid_access_level": null}.
- `/teams/{team_id}/users` -- FULL user list with PII (id, status, first_name, last_name, email).
- `/teams/{team_id}/users/count` -- {"count": 243}.
- `/teams/{team_id}/avatar-image` -- {"full_media_url": "https://media-service.gc.com/..."}.
- `/teams/{team_id}/team-notification-setting` -- {team_id, event_reminder_setting:"never"}.
- `/teams/{team_id}/web-widgets` -- [{id, type:"schedule"}].
- `/teams/{team_id}/scoped-features` -- {"scoped_features": {}}.
- `/teams/{team_id}/relationships` -- [{team_id, user_id, player_id, relationship:"primary"|"self"}].
- `/teams/{team_id}/relationships/requests` -- [].
- `/teams/{team_id}/external-associations` -- [].
- `/teams/{team_id}/video-stream/videos` -- [].
- `/teams/{team_id}/schedule/events/{event_id}/video-stream` -- stream config with publish_url (SENSITIVE), ingest_endpoints, status:"ended".
- `/teams/{team_id}/schedule/events/{event_id}/video-stream/assets` -- 3 assets with duration, thumbnail_url.
- `/teams/{team_id}/schedule/events/{event_id}/video-stream/live-status` -- {"isLive": false}.
- `/teams/{team_id}/schedule/events/{event_id}/rsvp-responses` -- [].
- `/users/{user_id}` -- {id, status, first_name, last_name, email}. PII -- redact all.
- `/events/{event_id}/highlight-reel` -- multi_asset_video_id, status:"finalized", playlist[] with CloudFront-signed HLS URLs.

**HTTP 500 (pagination bugs -- blocked):**
- `/organizations/{org_id}/teams` -- "page_starts_at undefined"
- `/me/organizations` -- "page_size undefined"
- `/me/related-organizations` -- "page_starts_at undefined"
- **Workaround to test:** Try `?page_size=50` or `?start_at=0` query params.

**HTTP 403:**
- `/bats-starting-lineups/{event_id}` with away game event_id. Try home game event_id.

**HTTP 404 (route does not exist on API domain):**
- All `/teams/{public_id}/{season-slug}/*` endpoints -- these are web app routes, not API routes.
- `/public/teams/{public_id}/live` -- 404 when no active game.
- `/game-streams/insight-story/bats/{event_id}` and `/player-insights/bats/{event_id}` -- feature not available.

**HTTP 501:**
- `/me/permissions` -- Not Implemented server-side.

### Previously Confirmed Endpoints (pre-2026-03-07)

| Endpoint | Status | Discovered |
|----------|--------|------------|
| `GET /me/user` | CONFIRMED LIVE, 12 fields. Token validity check. | 2026-03-04 |
| `GET /me/teams` | Schema FULLY DOCUMENTED, 15 teams, 27 fields | 2026-03-04 |
| `GET /teams/{id}` | Schema FULLY DOCUMENTED, 25 fields. Opponent UUID confirmed. | 2026-03-04 |
| `GET /teams/{id}/schedule` | FULLY DOCUMENTED, 228 events (103 games) | 2026-03-04 |
| `GET /teams/{id}/game-summaries` | CONFIRMED, 92 total records, 2 pages | 2026-03-04 |
| `GET /teams/{id}/players` | Schema CONFIRMED (5 fields: id, first_name, last_name, number, avatar_url). | 2026-03-04 |
| `GET /teams/public/{public_id}/players` | CONFIRMED LIVE. 20 players. URL uses `/teams/public/` NOT `/public/teams/`. | 2026-03-04 |
| `GET /teams/{id}/video-stream/assets` | Confirmed, 3 pages | Pre-2026-03-01 |
| `GET /teams/{id}/season-stats` | CONFIRMED LIVE | 2026-03-04 |
| `GET /teams/{id}/associations` | CONFIRMED, 244 records | 2026-03-04 |
| `GET /teams/{id}/players/{player_id}/stats` | CONFIRMED, 80 records, per-game + spray charts | 2026-03-04 |
| `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` | CONFIRMED, 106 KB, 25 players both teams, spray charts | 2026-03-05 |
| `GET /public/teams/{public_id}` | CONFIRMED, NO AUTH REQUIRED | 2026-03-04 |
| `GET /public/teams/{public_id}/games` | CONFIRMED, NO AUTH REQUIRED | 2026-03-04 |
| `GET /teams/{id}/opponents` | CONFIRMED, 70 records, 2 pages | 2026-03-04 |
| `GET /game-stream-processing/{game_stream_id}/boxscore` | CONFIRMED LIVE. Asymmetric keys: own=public_id, opp=UUID. | 2026-03-04 |
| `GET /game-stream-processing/{game_stream_id}/plays` | CONFIRMED LIVE. 58 plays, 6-inning game. | 2026-03-04 |
| `GET /public/game-stream-processing/{game_stream_id}/details` | CONFIRMED, NO AUTH REQUIRED. include=line_scores for per-inning. | 2026-03-04 |
| `GET /events/{event_id}/best-game-stream-id` | CONFIRMED. Returns {"game_stream_id": UUID}. | 2026-03-04 |
| `GET /teams/{id}/public-team-profile-id` | CONFIRMED. UUID -> public_id bridge. | 2026-03-04 |
| `POST /auth` | HTTP 400 (stale signature). Endpoint exists. Signing key unknown. | 2026-03-04 |

### Boxscore Endpoint Critical Facts (confirmed 2026-03-04)

- **URL param is `game_stream.id` from game-summaries** (NOT `event_id` or `game_stream.game_id`)
- **Asymmetric team key format**: own team key = public_id slug; opponent key = UUID
- **Player names included** in `players` array (id, first_name, last_name, number)
- **Groups**: `"lineup"` (batting: AB/R/H/RBI/BB/SO) and `"pitching"` (IP/H/R/ER/BB/SO)
- **Sparse extras (lineup)**: 2B, 3B, HR, TB, HBP, SB, CS, E -- only non-zero players listed
- **Batting order**: implicit -- list order = batting order
- Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`

### Areas Not Yet Explored / High-Priority Follow-Ups

**CRITICAL PRIORITY:**
- **`GET /bats-starting-lineups/{event_id}` with home game event_id** -- previous test returned 403 with away game event. Test with home game where user's team was scorer.
- **`?page_size=50` workaround for HTTP 500 endpoints** -- test `/me/organizations`, `/me/related-organizations`, and `/organizations/{org_id}/teams` with this parameter to bypass pagination bug.
- **LSB coaching account gc-token** -- all current credentials are travel ball account. LSB HS teams not visible.

**HIGH PRIORITY:**
- `GET /organizations/{uuid}/game-summaries` -- likely returns data for school program orgs. Test with LSB org UUID when credentials available.
- PUBLIC-TEAM-PROFILE-ID with opponent UUIDs -- does `/teams/{opponent_uuid}/public-team-profile-id` work? Unlocks public API access for opponents.

**ONGOING:**
- AUTH FLOW PARTIAL: `POST /auth` confirmed (400 received). Successful response schema unknown. Signing key unknown.
- Opponent endpoint access: `/teams/{opponent_id}/season-stats`, game-summaries, boxscore
- `streak_C` (cold streak, unconfirmed); `total_outs` semantics; ETag conditional requests
- BOXSCORE: Does game_stream_id for opponent's own game-summaries work in boxscore?
- PLAYS: Public unauthenticated variant? Extra-innings behavior? Pitch speed/location data?

## JWT Payload Fields (Confirmed 2026-03-04)

Actual fields: `id` (compound `{session_uuid}:{refresh_token_uuid}`), `cid` (= gc-client-id header), `uid` (user UUID), `email`, `iat`, `exp`. Previous docs listed `type`, `userId`, `rtkn` -- these were NOT observed. Consider them unconfirmed/incorrect until re-verified.

**NEW 2026-03-07:** The JWT `type` field observed in `/subscription/details` response (value: `"team_manager"`) refers to the subscription type, NOT the JWT payload type. The JWT payload does not contain a `type` field in our captures.

## Security Rules

Never display/log/store credentials. Use `{AUTH_TOKEN}` placeholders. Strip auth headers from raw responses.

**PII hotspots identified 2026-03-07:**
- `/teams/{team_id}/users` -- full user list with emails
- `/users/{user_id}` -- name + email
- `/me/associated-players` -- player names across teams
- `/me/advertising/metadata` -- `targeting.gc_user-id_v1` is the user UUID
- `/sync-topics/me/updated-topics` -- `next_cursor` contains user UUID
- `/teams/{team_id}/schedule/events/{event_id}/video-stream` -- `publish_url` and `stream_key` are live stream credentials

## Key File Paths

API spec: `docs/gamechanger-api.md` | Stat glossary: `docs/gamechanger-stat-glossary.md` | Creds: `.env` | HTTP: `src/http/headers.py`, `src/http/session.py`
