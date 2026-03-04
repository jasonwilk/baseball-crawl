# API Scout -- Agent Memory

## Credential Lifecycle

Credentials are short-lived. The user provides curl commands containing live tokens. The script `scripts/refresh_credentials.py` extracts and stores them in `.env`. Tokens expire frequently -- always check for auth errors before assuming an endpoint has changed.

Credentials are NEVER logged, committed, or displayed. Redact to `{AUTH_TOKEN}` in all documentation and output. If the user pastes a curl with real tokens, acknowledge receipt and immediately work with the redacted version.

## API Spec Location

Single source of truth: `docs/gamechanger-api.md`

Every documented endpoint follows this structure:
- URL pattern (with path parameters)
- HTTP method
- Required headers (credentials as `{PLACEHOLDER}`)
- Query parameters (name, type, required/optional, description)
- Response schema (JSON structure with types)
- Example response (sensitive data redacted)
- Known limitations
- Discovery date
- Changelog entry

All discoveries go into the spec immediately. Do not accumulate findings in memory or conversation -- write to the spec file.

## Exploration Status

As of 2026-03-04. All API knowledge is empirical -- discovered by running curl commands provided by the user.

### Confirmed Endpoints

| Endpoint | Status | Discovered |
|----------|--------|------------|
| `GET /me/teams` | **Schema FULLY DOCUMENTED LIVE**, 15 teams, 27 fields | 2026-03-04 |
| `GET /teams/{id}` | **Schema FULLY DOCUMENTED LIVE**, single team object, 25 fields. **Opponent UUID confirmed works** (2026-03-04) | 2026-03-04 |
| `GET /teams/{id}/schedule` | **Schema FULLY DOCUMENTED LIVE**, 228 events (103 games), google_place_details, pregame_data with opponent_id | 2026-03-04 |
| `GET /teams/{id}/game-summaries` | Confirmed LIVE, **92 total records, 2 pages complete -- full season** | 2026-03-04 |
| `GET /teams/{id}/players` | Confirmed from capture | Pre-2026-03-01 |
| `GET /teams/{id}/video-stream/assets` | Confirmed, 3 pages | Pre-2026-03-01 |
| `GET /teams/{id}/season-stats` | Confirmed LIVE, 200 OK | 2026-03-04 |
| `GET /teams/{id}/associations` | Confirmed LIVE, 244 records, single page | 2026-03-04 |
| `GET /teams/{id}/players/{player_id}/stats` | **CONFIRMED LIVE**, 80 records, 387 KB, single page, per-game stats + spray charts | 2026-03-04 |
| `GET /public/teams/{public_id}` | **CONFIRMED LIVE, NO AUTH REQUIRED**. 200 OK without gc-token/gc-device-id. Returns: name, sport, ngb, location, age_group, team_season (record), avatar_url, staff. | 2026-03-04 |
| `GET /teams/{id}/opponents` | **CONFIRMED LIVE**, 70 records across 2 pages (50+20). 5 fields: root_team_id, owning_team_id, name, is_hidden, progenitor_team_id (optional). **Use progenitor_team_id for other endpoints.** | 2026-03-04 |

### /me/teams Key Facts (schema confirmed 2026-03-04)

- Returns bare JSON array of 15 team objects (13.6 KB response)
- `include=user_team_associations` query param adds the user's roles to each team object
- **CRITICAL DISCOVERY**: LSB high school teams (Freshman, JV, Varsity, Reserve) NOT present -- this gc-token belongs to Jason's personal travel ball account. A separate LSB coaching account token is needed.
- `ngb` field is a **JSON-encoded string** (string containing JSON array), not a native JSON array -- must double-parse: `json.loads(team["ngb"])`
- `team_player_count` and `team_avatar_image` always null in this sample
- `paid_access_level` sometimes null, sometimes `"premium"`
- All teams have `team_type: "admin"` in this sample
- `user_team_associations` values: `"manager"`, `"player"`, `"family"`, `"fan"` (multiple per user possible)
- `record` object (wins/losses/ties) always present, even for archived teams
- No pagination triggered (all 15 in one response despite `x-pagination: true`)
- Accept header: `application/vnd.gc.com.team:list+json; version=0.10.0`
- No `gc-user-action` in this capture (optional header)
- ETags returned; CloudFront CDN delivery

### Team Detail Key Facts (2026-03-04, opponent validation 2026-03-04)

- Endpoint: `GET /teams/{team_id}` -- returns a **single JSON object** (not an array), 910 bytes
- Accept header: `application/vnd.gc.com.team+json; version=0.10.0` (singular -- no `:list` cardinality, unlike /me/teams)
- gc-user-action: `data_loading:team` for own teams; `data_loading:opponents` for opponent teams (both return 200 OK with same schema)
- 25 fields: id, name, team_type, city, state, country, age_group, competition_level, sport, season_year, season_name, stat_access_level, scorekeeping_access_level, streaming_access_level, paid_access_level, settings, organizations, ngb, team_avatar_image, team_player_count, created_at, public_id, url_encoded_name, archived, record
- `settings.scorekeeping.bats` contains: innings_per_game (int), shortfielder_type (string), pitch_count_alert_1/2 (int or null)
- `settings.maxpreps` is null for travel ball; may be configured for LSB high school teams
- `organizations` is an array of `{organization_id: UUID, status: string}` -- own team shows one org; opponent team shows empty array `[]` (may reflect actual data or limited visibility)
- Same ngb double-JSON-parse quirk as /me/teams
- `record` object `{wins, losses, ties}` -- includes all historical games
- **CONFIRMED**: `pregame_data.opponent_id` from schedule works as `team_id` here. Opponent sample: SE Elites 14U (Philadelphia, PA), 4W/14L/1T, `organizations: []`, `ngb: "[]"`. Full 25-field schema returned identically to own-team response.
- No pagination (single object response by design)

### Associations Key Facts (2026-03-04)

- Returns all user-team memberships: `manager`, `player`, `family`, `fan` roles
- Response is a **bare JSON array** (3 fields per record: `team_id`, `user_id`, `association`)
- 244 records in one response (29 KB) -- no pagination triggered despite `x-pagination: true` being sent
- **Low player count warning**: only 2 `association: "player"` records vs. 12-15 expected roster size -- this is NOT an authoritative roster list; use `/players` for that
- No `gc-user-action` header in capture (like `/players`) -- confirmed optional for this endpoint
- ETags returned; CloudFront CDN delivery
- `user_id` for player records may or may not match player UUIDs from `/players` endpoint -- mapping unconfirmed
- Accept header: `application/vnd.gc.com.team_associations:list+json; version=0.0.0`

### Season-Stats Key Facts (2026-03-04)

- Returns full-season batting/pitching/fielding aggregates for all players on a team
- Response is a single object (not array), no pagination observed
- Players keyed by UUID only -- no names; must join with /players endpoint
- Defense section merges pitching AND fielding into one object (use GP:P / GP:F to split)
- `IP:POS` fields (IP:1B, IP:2B, etc.) are in fractional thirds (218.67 = 218 innings + 2 outs)
- `AB/HR` field only appears when HR > 0
- New gc-user-action value: `data_loading:team_stats`
- Accept header: `application/vnd.gc.com.team_season_stats+json; version=0.2.0`
- **Stat glossary**: `docs/gamechanger-stat-glossary.md` created alongside this endpoint. Maps all GC stat abbreviations to definitions (sourced from GC UI). Includes API field name mapping table for abbreviations that differ between UI and API (e.g., K-L -> SOL, HHB -> HARD). The API spec's season-stats schema cross-references this glossary.

### Game-Summaries Key Facts (confirmed across 2 pages, 2026-03-04)

- **Full season confirmed**: 92 total records across 2 pages (page 1: 50, page 2: 42, cursor `start_at=136418700`)
- **End-of-pagination confirmed**: page 2 returned no `x-next-page` header -- this is the reliable termination signal
- Pagination: `x-pagination: true` request header enables pagination; page size = 50 max (last page may have fewer)
- Next page URL is in `x-next-page` **response header** (full URL with `?start_at={cursor}`)
- Response body is a **bare JSON array** -- no wrapper object, no in-body pagination metadata
- `event_id` == `game_stream.game_id` always (confirmed on all 92 records)
- `game_stream.id` != `game_stream.game_id` always (confirmed on all 92 records)
- `scoring_user_id` is non-null on all 92 records
- Clock fields (`game_clock_*`) are optional; present on ~42% of records combined (23/50 page 1, 16/42 page 2)
- `game_clock_elapsed_seconds_at_last_pause` and `game_clock_start_time_milliseconds` are **strings** not ints
- `sport_specific.bats` always present; contains `total_outs` (int) and `inning_details.{inning, half}`
- `total_outs` semantics unclear -- not straightforwardly 3*innings; needs further investigation
- `last_scoring_update` is an ISO 8601 timestamp (non-null on all 42 page 2 records; may be null on in-progress games)
- Does NOT contain per-player stats (confirmed)
- API served via AWS CloudFront CDN; ETags returned (conditional requests untested)
- `access-control-expose-headers` includes `gc-signature`, `gc-timestamp` -- not yet observed in responses
- `x-server-epoch` response header = server Unix timestamp (seconds)
- gc-user-action value: `data_loading:events` (plural) -- confirmed on both page 1 and page 2

### Player-Stats Key Facts (2026-03-04)

- **New endpoint**: `GET /teams/{team_id}/players/{player_id}/stats`
- Returns bare JSON array of per-game records for one player (80 records, 387 KB)
- Each record has: `event_id`, `stream_id`, `game_date`, `player_stats`, `cumulative_stats`, `offensive_spray_charts`, `defensive_spray_charts`
- `event_id` matches `game_stream.game_id` in game-summaries (join key)
- `player_stats.stats` has conditional sections: `offense` absent for pitcher-only games (2/80), `defense` absent for DH-only games (4/80), `general` always present
- Cumulative stats are rolling (running totals through each game) -- records NOT in chronological order
- Spray charts: `offensive_spray_charts` present 56/80 games, `defensive_spray_charts` present 13/80 games. Each item has `playType`, `playResult`, defenders with `position`, `location.x`, `location.y`, `error`
- `cumulative_stats.offense` has 3 extra fields vs per-game: `SB`, `CS`, `PIK`
- New gc-user-action: `data_loading:player_stats`
- Accept header: `application/vnd.gc.com.player_stats:list+json; version=0.0.0`
- **THIS IS THE E-002-03 BLOCKER ANSWER** (see below)

### Schedule Key Facts (schema confirmed 2026-03-04)

- Returns bare JSON array of schedule items; each item wraps `event` object (always) and `pregame_data` (games only)
- 228 total events in one response (no pagination observed): 103 game, 90 practice, 35 other
- Date range seen: 2024-11-08 to 2025-07-15 (full team history, not filtered to current season)
- `event.id` == `pregame_data.id` == `pregame_data.game_id` always (confirmed 103 games)
- `event_type` values: `"game"`, `"practice"`, `"other"` -- `sub_type` always empty array
- `status` values: `"scheduled"`, `"canceled"` (162 / 66)
- **Full-day events**: when `full_day=true`, `start`/`end` use `{"date": "YYYY-MM-DD"}` not `{"datetime": "ISO8601"}`, and `timezone` is `null`
- `arrive` field (arrival time) present on 86/228 events (mostly games)
- **`location` has 6 possible shapes**: empty, name-only, name+coords+address, coords+address, name+google_place_details+place_id, google_place_details+place_id
- Coordinates use DIFFERENT key names: `{latitude, longitude}` in `location.coordinates` vs `{lat, long}` in `google_place_details.lat_long`
- `notes` field (free text, e.g., field number like "Field 7") present on 49/228 events
- **`pregame_data.opponent_id`**: present on all 103 game events; **CONFIRMED** usable as `team_id` in `GET /teams/{team_id}` (validated 2026-03-04). Usability in season-stats, players, game-summaries for opponent teams not yet tested.
- `pregame_data.home_away`: `"home"`, `"away"`, or `null` (all observed)
- `pregame_data.lineup_id`: null on 25/103, non-null on 78/103
- gc-user-action: `data_loading:team` (also used for schedule)
- Accept header: `application/vnd.gc.com.event:list+json; version=0.2.0`

### Public Team Profile Key Facts (2026-03-04)

- **NO AUTH REQUIRED** -- 200 OK with no gc-token/gc-device-id. Uses `public_id` slug, NOT UUID.
- Accept: `application/vnd.gc.com.public_team_profile+json; version=0.1.0`
- Fields: `id` (slug), `name`, `sport`, `ngb`, `location`, `age_group`, `team_season.record` (win/loss/tie singular), `avatar_url` (signed CF URL, expiring), `staff` (name strings)
- **vs GET /teams/{id}**: `id` = slug not UUID; `win`/`loss`/`tie` singular keys; current-season only (not all-time); `team_season` wrapper
- ngb double-decode quirk applies. No gc-user-action. Rate limits for unauthenticated: unknown.

### Opponents Endpoint Key Facts (2026-03-04)

- **New endpoint**: `GET /teams/{team_id}/opponents` -- bare JSON array, paginated (size 50), 70 records/2 pages
- **5 fields**: `root_team_id`, `owning_team_id`, `name`, `is_hidden`, `progenitor_team_id` (optional, 60/70)
- **CRITICAL**: Use `progenitor_team_id` (not `root_team_id`) with `/teams/{id}` and other endpoints. `root_team_id` is a local registry key only.
- `progenitor_team_id` == `pregame_data.opponent_id` from schedule (validated SE Elites 14U)
- `is_hidden=false`: 57/70 active opponents. `is_hidden=true`: 13/70 (dupes, bad entries)
- gc-user-action: `data_loading:opponents` | Accept: `application/vnd.gc.com.opponent_team:list+json; version=0.0.0`

### E-002-03 Blocker Update

`/teams/{team_id}/players/{player_id}/stats` provides per-game player stats BUT is player-centric (not a game box score). Reconstruct per-game by calling once per player. May unblock E-002-03 with revised approach -- notify PM.

### Areas Not Yet Explored

- Auth flow (token acquisition, refresh), player profile endpoint, season scoping query params
- Game endpoints (true team box score) -- per-player stats available; team box score may still exist
- Opponent endpoint access: `/teams/{opponent_id}/season-stats`, `/players/{player_id}/stats` -- not yet tested
- `streak_C` (cold streak, unconfirmed); `total_outs` semantics; ETag conditional requests
- **HIGH PRIORITY**: LSB coaching account access -- need gc-token with coach role on LSB HS teams
- **PUBLIC API FOLLOW-UPS**: Do opponent teams have `public_id`? Other `/public/` endpoints?
- **OPPONENTS FOLLOW-UPS**: Use `progenitor_team_id` from `/opponents` to batch-fetch opponent season-stats

## Security Rules

Never display/log/store credentials. Use `{AUTH_TOKEN}` placeholders. Strip auth headers from raw responses. Flag credentials outside `.env` immediately. See full rules in system prompt.

## HTTP Request Discipline
See CLAUDE.md. Canonical header set in `src/http/headers.py`.

## Agent Interactions

- **baseball-coach** defines what data is most important to find -- prioritize exploration accordingly
- **data-engineer** consumes the spec to design schemas and ingestion pipelines
- **general-dev** consumes the spec to implement API client code
- **product-manager** uses discoveries to write informed stories

## Key File Paths

API spec: `docs/gamechanger-api.md` | Stat glossary: `docs/gamechanger-stat-glossary.md` | Creds: `scripts/refresh_credentials.py` -> `.env` | HTTP: `src/http/headers.py`, `src/http/session.py`
