# Software Engineer -- Agent Memory

## Project Code Conventions

### Python Style
See CLAUDE.md Code Style section and `.claude/rules/python-style.md`.
- Conventional commits: `feat(E-NNN-SS):`, `fix(E-NNN-SS):`, `test(E-NNN-SS):`, etc.

### Data Handling
- Parse defensively: missing fields produce warnings, not crashes
- Loaders must be idempotent -- re-running the same data must not create duplicates
- Store raw API responses before transforming (raw -> processed pipeline)
- Use dataclasses or Pydantic models between functions, not raw dicts

## Key File Paths

### Source Code
- `src/` -- all source modules (crawlers, parsers, loaders, utilities)
- `src/http/session.py` -- HTTP session factory (`create_session()`). ALWAYS use this for HTTP clients.
- `tests/` -- all test files, mirroring `src/` structure
- `scripts/` -- utility and operational scripts (e.g., `scripts/refresh_credentials.py`)

### Data and Docs
- `data/` -- local dev data outputs, SQLite database (`data/app.db`)
- `data/raw/` -- raw API response samples (gitignored). game-summaries: `game-summaries-sample.json` (page 1, 50 records), `game-summaries-page2-sample.json` (page 2, 42 records). me-teams: `me-teams-sample.json` (15 teams, 18 KB). me-user: `me-user-sample.json` (PII-redacted user profile, subscription info). player-stats: `player-stats-sample.json` (80 per-game records, 387 KB). schedule: `schedule-sample.json` (228 events, 134 KB). team-detail: `team-detail-sample.json` (own team, 910 bytes), `team-detail-opponent-sample.json` (opponent team via opponent_id, same schema). boxscore: `boxscore-sample.json` (13 KB, both teams' batting and pitching lines, game_stream_id-keyed). game-plays: `game-plays-sample.json` (37 KB, 58 plays, pitch-by-pitch play log for both teams, same game_stream_id as boxscore). public-team-profile: `public-team-profile-sample.json` (unauthenticated, ~1.2 KB). public-team-games: `public-team-games-sample.json` (unauthenticated, 32 game records, 25.7 KB, team `QTiLIb2Lui3b`). public-team-games-preview: `public-team-games-preview-sample.json` (unauthenticated, 32 records, near-duplicate of `/games` -- uses `event_id` instead of `id`, no `has_videos_available`; prefer `/games` sample for implementation). opponents: `opponents-sample.json` (70 records across 2 pages combined, 17 KB). public-game-details: `public-game-details-sample.json` (unauthenticated, single game object with inning-by-inning line score, ~500 bytes)
- `data/raw/` also includes: `players-roster-sample.json` (20 players, LSB JV roster, 2.3 KB, bare JSON array of 5-field objects), `best-game-stream-id-sample.json` (single-field response: `{"game_stream_id": "<UUID>"}`, 58 bytes), `team-users-sample.json` (33 user records, PII-redacted, bare JSON array of 5-field objects: id/status/first_name/last_name/email; admin/auth plumbing -- no coaching or schema value), `public-team-profile-id-sample.json` (single-field response: `{"id": "<slug>"}`, ~20 bytes; UUID-to-public_id bridge)
- `docs/` -- API specs and documentation
- `docs/api/README.md` -- API documentation index; per-endpoint files in `docs/api/endpoints/`
- `docs/gamechanger-stat-glossary.md` -- authoritative data dictionary for all GameChanger stat abbreviations (batting, pitching, fielding, catcher, positional innings). Includes API field name mapping table for abbreviations that differ between UI and API. Reference when parsing season-stats response fields.

### Token Health Check (confirmed 2026-03-04)
- `GET /me/user` returns 200 OK if the `gc-token` is valid, 401 if expired
- Use as a lightweight pre-flight check before long ingestion runs (e.g., batch opponent scouting)
- Accept header: `application/vnd.gc.com.user+json; version=0.3.0`
- Response contains user UUID (`id` field) -- same as `uid` in the decoded JWT payload
- Also contains subscription info (`has_subscription`, `access_level`, `subscription_source`) -- useful for validating account tier
- Raw sample: `data/raw/me-user-sample.json` (PII redacted)

### Token Lifetime and Credential Management (confirmed 2026-03-04)
- **Token lifetime is 14 days** (JWT `exp - iat = 1,209,600 seconds`). Previous assumption of ~1 hour was wrong.
- **Programmatic token refresh NOT possible**: `POST /auth` requires a `gc-signature` HMAC header computed with an unknown signing key embedded in browser JavaScript. Until the signing algorithm is reversed, tokens must come from browser captures.
- **JWT payload fields**: `id` (compound: `{session_uuid}:{refresh_token_uuid}`), `cid` (= gc-client-id header), `uid` (user UUID), `email`, `iat`, `exp`. Previously documented fields `type`, `userId`, `rtkn` were NOT observed -- consider them incorrect.
- **New credential headers discovered**: `gc-signature` (time-bound HMAC), `gc-timestamp` (Unix seconds), `gc-client-id` (stable UUID), `gc-app-version` (`"0.0.0"`). These are used by `POST /auth` but NOT by GET endpoints.
- **Implementation impact**: Batch ingestion pipelines can run for days under a single token. Pre-flight health check (`GET /me/user`) should check token validity before starting, but mid-run expiration is much less likely than previously assumed.
- Raw sample: `data/raw/auth-refresh-sample.json` (annotated schema, no live tokens)

### API Parsing Quirks
- `/me/teams` and `/teams/{team_id}` `ngb` field: **JSON-encoded string**, not a native JSON array. Must double-parse: `json.loads(team["ngb"])`. The outer response is JSON, but this particular field's value is a string containing another JSON structure.

### Team Detail Endpoint (confirmed 2026-03-04, opponent validation 2026-03-04)
- `GET /teams/{team_id}` -- returns a single JSON object (not an array), 910 bytes
- Raw samples: `data/raw/team-detail-sample.json` (own team), `data/raw/team-detail-opponent-sample.json` (opponent team)
- **Opponent access confirmed**: `pregame_data.opponent_id` from schedule works as `team_id` -- identical 25-field schema returned. gc-user-action differs (`data_loading:opponents` vs `data_loading:team`) but both return 200 OK.
- Contains `settings.scorekeeping.bats.innings_per_game` (int: 7 for travel ball, likely 9 for HS varsity) -- needed for stat normalization (K/9, BB/9, etc.)
- `competition_level` (string: `"club_travel"` observed) -- useful for tier filtering
- `record` object `{wins, losses, ties}` -- cumulative, always present
- Same ngb double-parse quirk as `/me/teams`

### Pagination Pattern (confirmed 2026-03-04)
- game-summaries uses cursor-based pagination: `x-pagination: true` request header, `x-next-page` response header with full URL
- End of data: `x-next-page` header absent (NOT empty body)
- Page size: 50 max; final page may have fewer records
- Working Python pagination loop in `docs/api/pagination.md` -- use as reference implementation

### Player-Stats Endpoint (confirmed 2026-03-04)
- `GET /teams/{team_id}/players/{player_id}/stats` -- per-game stats for one player
- Returns bare JSON array; 80 records / 387 KB observed for a full season
- No pagination observed (single response with all games)
- **Player-centric**: Must call once per player to build a full game box score (e.g., 12 calls for a 12-player roster)
- `event_id` joins to game-summaries `game_stream.game_id` for per-game filtering
- `player_stats.stats.offense` (84 fields) absent for pitcher-only games; `defense` (34-129 fields) absent for DH-only games -- parse defensively
- Spray chart data: `offensive_spray_charts` / `defensive_spray_charts` -- arrays of ball-in-play events with x/y coordinates, play type/result, fielder position. Unique to this endpoint (not in season-stats)
- `cumulative_stats` = rolling season totals; records NOT in chronological order

### Schedule Endpoint (confirmed 2026-03-04)
- `GET /teams/{team_id}/schedule?fetch_place_details=true` -- full event schedule for a team
- Returns bare JSON array; 228 events / 134 KB observed (no pagination)
- Raw sample: `data/raw/schedule-sample.json` (228 events: 103 game, 90 practice, 35 other)
- Each item wraps `event` (always present) and `pregame_data` (game events only)
- `event.id` == `pregame_data.game_id` always -- same UUID used across schedule, game-summaries, player-stats
- **Location polymorphism**: 6 distinct shapes -- empty `{}`, name-only, name+coords+address, coords+address, name+google_place+place_id, google_place+place_id. Parse defensively.
- **Coordinate key inconsistency**: `{latitude, longitude}` in `location.coordinates` vs `{lat, long}` in `google_place_details.lat_long` -- normalize during parsing
- **Full-day format change**: When `full_day=true`, datetime fields use `{"date": "YYYY-MM-DD"}` instead of `{"datetime": "ISO8601"}`, and `timezone` is null. Must handle both formats in the same parser.
- `pregame_data.opponent_id` (UUID) on all 103 games -- **CONFIRMED** works as `team_id` in `/teams/{team_id}` (2026-03-04). Same 25-field schema for opponents. Opponent sample: `data/raw/team-detail-opponent-sample.json`
- `pregame_data.home_away`: `"home"`, `"away"`, or `null`
- `status`: `"scheduled"` or `"canceled"` (66 canceled) -- filter canceled in ETL

### Opponents Endpoint (confirmed 2026-03-04)
- `GET /teams/{team_id}/opponents` -- complete opponent registry for a team
- Returns bare JSON array; paginated (page size 50, cursor-based -- same `x-next-page` pattern as game-summaries)
- 70 records across 2 pages observed (50 + 20)
- Raw sample: `data/raw/opponents-sample.json` (70 records, 17 KB)
- **Three UUID fields with different semantics -- CRITICAL**:
  - `root_team_id`: Local registry key. Do NOT use with other endpoints.
  - `owning_team_id`: Always equals the path `team_id`. Informational only.
  - `progenitor_team_id` (optional, 60/70 present): **Canonical GC team UUID.** Use THIS with `/teams/{id}`, `/season-stats`, `/players`, etc.
- `progenitor_team_id` == `pregame_data.opponent_id` from schedule (confirmed)
- `is_hidden` (boolean): 57 visible, 13 hidden (dupes/bad entries). Filter hidden records in ETL.
- `name` (string): Display name of the opponent team
- gc-user-action: `data_loading:opponents` | Accept: `application/vnd.gc.com.opponent_team:list+json; version=0.0.0`
- **Batch scouting workflow**: Enumerate `progenitor_team_id` values where `is_hidden=false`, then call `/teams/{id}/season-stats` for each to build opponent scouting database

### Boxscore Endpoint (confirmed 2026-03-04)
- `GET /game-stream-processing/{game_stream_id}/boxscore` -- per-game box score for BOTH teams
- Returns JSON object (NOT array); top-level keys are team identifiers (exactly 2)
- Raw sample: `data/raw/boxscore-sample.json` (13 KB, both teams' batting and pitching lines)
- **Critical ID mapping**: URL param is `game_stream.id` from game-summaries, NOT `event_id`, NOT `game_stream.game_id`. Must crawl game-summaries first to get this ID.
- **Asymmetric top-level keys**: Own team key = `public_id` slug (short alphanumeric, no dashes); opponent key = UUID (with dashes). Detect via regex or match against known `public_id` from `/me/teams`.
- **Player names embedded**: `players` array per team has `id`, `first_name`, `last_name`, `number` (string). No join to `/players` needed for display.
- **Two stat groups**: `groups` array with `category: "lineup"` (batting) and `category: "pitching"`.
- **Main stats** (always present per player): Batting: `AB`, `R`, `H`, `RBI`, `BB`, `SO`. Pitching: `IP`, `H`, `R`, `ER`, `BB`, `SO`. All int.
- **Sparse extras pattern**: `extra` array contains `{stat_name: str, stats: [{player_id: uuid, value: int}]}`. Only non-zero players listed. Must iterate and merge into per-player stat dicts.
  - Batting extras: `2B`, `3B`, `HR`, `TB`, `HBP`, `SB`, `CS`, `E`
  - Pitching extras: `WP`, `HBP`, `#P` (pitch count), `TS` (strikes), `BF` (batters faced)
- **Batting order**: Implicit in `stats` array order within lineup group. Index 0 = leadoff, index 1 = #2 hole, etc.
- **Substitutes**: `is_primary: false` in lineup group (absent from pitching group). Subs may have `player_text: ""`.
- **`player_text` encoding**: Lineup = positions played (e.g., `"(CF)"`, `"(SS, P)"`, `"(2B, P, 2B)"`). Pitching = decision (`"(W)"`, `"(L)"`, `"(SV)"`, `""`).
- **Team totals**: `team_stats` dict per group has aggregate totals (same fields as individual). Use for validation.
- Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`
- No `gc-user-action` observed -- may be optional for this endpoint

### Plays Endpoint (confirmed 2026-03-04)
- `GET /game-stream-processing/{game_stream_id}/plays` -- pitch-by-pitch play log for both teams
- Returns JSON object (NOT array); top-level keys: `sport` (always "baseball"), `team_players` (roster dict), `plays` (array)
- Raw sample: `data/raw/game-plays-sample.json` (37 KB, 58 plays, 6-inning game)
- **Critical ID mapping**: Same as boxscore -- URL param is `game_stream.id` from game-summaries
- **Asymmetric `team_players` keys**: Same slug/UUID pattern as boxscore top-level keys. Reuse boxscore key-detection logic.
- **Player UUID template pattern**: All player references are `${uuid}` tokens embedded in template strings. Must regex-extract (pattern: `\$\{([0-9a-f-]{36})\}`) and resolve against `team_players` dict.
- **`at_plate_details`** (array of template objects): Pitch-by-pitch sequence ("Ball 1", "Strike 1 looking", "Foul", "In play") plus in-AB events (stolen bases, balks, pickoff attempts, wild pitches, lineup changes, courtesy runners). Each element has a single `template` string field.
- **`final_details`** (array of template objects): Outcome narration ("${uuid} singles on a hard ground ball to shortstop ${uuid}"). May contain multiple entries for multi-event plays (runner scoring, advancing, errors).
- **`name_template.template`**: Outcome label string ("Fly Out", "Single", "Walk", "Strikeout", "Error", "Double", "Hit By Pitch", "Runner Out", "Fielder's Choice", "Pop Out", "Line Out", "Ground Out"). Note: NOT a flat string -- it is `play["name_template"]["template"]`.
- **Contact quality in templates**: Hit descriptions include contact quality ("hard ground ball", "line drive", "fly ball", "bunt"). Can be regex-extracted for batted ball type classification.
- **Lineup changes inline**: "Lineup changed: ${uuid} in at pitcher" and "Pinch runner ${uuid} in for designated hitter ${uuid}" appear in `at_plate_details`, not as separate plays.
- **Courtesy runner pattern**: "Courtesy runner ${uuid} in for ${uuid}" -- distinct from pinch runners.
- **Last play edge case**: Final play (order 57) has `name_template.template` = "${uuid} at bat" with empty details arrays and scores reset to 0/0. This is an incomplete/abandoned at-bat. Skip plays where `final_details` is empty.
- **`messages`** (array): Empty on all 58 plays. Unknown content when non-empty. Preserve as-is.
- Accept: `application/vnd.gc.com.event_plays+json; version=0.0.0`
- No `gc-user-action` header observed

### Public-Team-Profile-ID Endpoint (confirmed 2026-03-04)
- `GET /teams/{team_id}/public-team-profile-id` -- returns `{"id": "<slug>"}` (UUID-to-public_id bridge)
- Raw sample: `data/raw/public-team-profile-id-sample.json` (~20 bytes)
- Accept header: `application/vnd.gc.com.team_public_profile_id+json; version=0.0.0`
- gc-user-action: `data_loading:team`
- Auth required (gc-token present in capture)
- **Bridge pattern**: Given a team UUID (from schedule `opponent_id`, opponents `progenitor_team_id`, or `/me/teams`), this returns the `public_id` slug needed for all public API endpoints (`/public/teams/{public_id}/*`). Simplest response in the API alongside best-game-stream-id (single JSON field).
- **Implementation note**: When building the opponent scouting pipeline, call this once per opponent UUID to populate the `public_id` column on the Team entity. Then use public endpoints for bulk data (games, profile, roster, line scores) without auth.
- **Opponent UUID behavior unverified**: Highest priority follow-up -- does this work with opponent UUIDs from `pregame_data.opponent_id`? If yes, enables automatic public API access for the entire opponent catalog.

### Best-Game-Stream-ID Endpoint (confirmed 2026-03-04)
- `GET /events/{event_id}/best-game-stream-id` -- resolves schedule `event_id` to `game_stream_id`
- Returns single-field JSON: `{"game_stream_id": "<UUID>"}`
- Raw sample: `data/raw/best-game-stream-id-sample.json` (58 bytes)
- Accept header: `application/vnd.gc.com.game_stream_id+json; version=0.0.2` (note: version `0.0.2`, higher than most endpoints which use `0.0.0`)
- No `gc-user-action` header observed
- **Bridge endpoint**: Converts schedule `event.id` (= `pregame_data.game_id`) to the `game_stream_id` required by boxscore and plays endpoints. Provides an alternative to crawling game-summaries when you already have an event_id.
- **Two paths to game_stream_id**: (1) game-summaries pagination (bulk, preferred for full ingestion), (2) this endpoint per event_id (on-demand, one extra call per game but avoids pagination)

### Players/Roster Endpoint (confirmed 2026-03-04)
- `GET /teams/{team_id}/players` (authenticated) and `GET /teams/public/{public_id}/players` (public variant)
- Returns bare JSON array; 20 players in a single response (no pagination triggered)
- Raw sample: `data/raw/players-roster-sample.json` (20 players, LSB JV, 2.3 KB)
- **5 fields per player**: `id` (UUID), `first_name` (string), `last_name` (string), `number` (string), `avatar_url` (string)
- **`id` is the canonical player UUID**: Same UUID used in player-stats, season-stats per-player breakdowns, and boxscore `player_id` values. THE join key for Player entity.
- **`first_name` may be initials**: LSB JV returned single-letter first names ("A", "B") -- data-entry pattern, not API limitation. Other teams may return full names. Store as-is.
- **Jersey `number` is a string**: Two players share #15 in sample. NOT unique within a team. Do not use as key.
- **`avatar_url` empty string when unset**: Key present with value `""` (not null, not absent). Different from public-team-games where key is absent entirely. Use `.get("avatar_url") or None` to normalize both patterns.
- **URL PATTERN WARNING**: Public variant uses `/teams/public/{public_id}/players` -- the INVERSE of other public endpoints which use `/public/teams/{public_id}`. Both path structures coexist in the API. When building URL constructors, do NOT assume all public endpoints follow `/public/teams/` pattern.
- **Auth requirement unclear**: Captured WITH gc-token. Whether it works without auth is untested.
- Accept header: `application/vnd.gc.com.public_player:list+json; version=0.0.0`

### Public Team Profile Endpoint (confirmed 2026-03-04)
- `GET /public/teams/{public_id}` -- **NO AUTH REQUIRED** (first unauthenticated endpoint)
- Uses `public_id` slug (short alphanumeric like `"a1GFM9Ku0BbF"`), NOT UUID
- Returns: name, sport, ngb, location, age_group, team_season (with record), avatar_url, staff
- Raw sample: `data/raw/public-team-profile-sample.json`
- **No-auth HTTP client**: When calling this endpoint, do NOT include `gc-token` or `gc-device-id` headers. The `create_session()` factory may need a mode or a separate function for unauthenticated public API calls.
- **Record key normalization**: Public endpoint uses singular keys (`win`/`loss`/`tie`) inside a `team_season.record` wrapper. Authenticated endpoint uses plural keys (`wins`/`losses`/`ties`) in a top-level `record` object. Parsers must normalize both shapes.
- **`id` field is the slug, not UUID**: `response["id"]` returns the `public_id` slug. The internal UUID is NOT exposed. Must map via authenticated `/teams/{team_id}` response's `public_id` field.
- Same ngb double-parse quirk as other team endpoints
- `staff` field: array of plain name strings (e.g., `["Jason Smith", "Mike Jones"]`) -- no roles, no IDs
- `avatar_url`: signed CloudFront URL, will expire -- do not cache long-term

### Public Game Details Endpoint (confirmed 2026-03-04)
- `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` -- **NO AUTH REQUIRED** (fourth unauthenticated endpoint)
- Uses `game_stream_id` (same ID as authenticated boxscore -- from game-summaries `game_stream.id`)
- Returns single JSON object (NOT array)
- **`line_score` is conditional**: Only present when `?include=line_scores` query param is included. Without the param, the field is absent.
- `line_score.team.scores`: array of integer runs per inning (e.g., `[2, 0, 0, 0, 0]`). Variable length -- depends on number of innings played.
- `line_score.team.totals`: `[R, H, E]` (3-element positional array, NOT a named object). `totals[0]` = Runs, `totals[1]` = Hits, `totals[2]` = Errors. Same for `opponent_team`.
- Metadata fields overlap with public-team-games: `score`, `home_away`, `start_ts`/`end_ts`, `timezone`, `game_status`, `has_videos_available`, `opponent_team.name`
- **No-auth HTTP client**: Same pattern as other public endpoints -- do NOT include `gc-token` or `gc-device-id`
- Accept header: likely the same pattern as other public endpoints (check api spec)
- **Complementary to boxscore**: Public details = game-level scoring (line score, R/H/E). Authenticated boxscore = per-player stats (batting/pitching lines, batting order). Same `game_stream_id` links them.
- Raw sample: `data/raw/public-game-details-sample.json`

### Public Team Games Endpoint (confirmed 2026-03-04)
- `GET /public/teams/{public_id}/games` -- **NO AUTH REQUIRED** (second unauthenticated endpoint)
- Uses `public_id` slug (same as public-team-profile), NOT UUID
- Returns bare JSON array of game records (32 observed, no pagination)
- **No-auth HTTP client**: Same as public-team-profile -- do NOT include `gc-token` or `gc-device-id`. Use the no-auth client mode.
- Accept: `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0`
- **`opponent_team.avatar_url` absent vs null**: When no avatar, the key is MISSING from the object entirely (not `null`). Use `.get("avatar_url")` not `["avatar_url"]`.
- `score.team` / `score.opponent_team`: integer run totals, directly embedded. No join needed for game results.
- `id` (UUID): Matches authenticated `event.id` from schedule -- join key for cross-referencing to authenticated data
- `start_ts`/`end_ts`: ISO 8601 UTC strings (e.g., `"2025-06-15T22:00:00Z"`). Different format from authenticated schedule's `{"datetime": "..."}` nested object -- parser must handle both shapes.
- `timezone`: IANA timezone string (e.g., `"America/New_York"`)
- `game_status`: All 32 records are `"completed"` -- future/scheduled game status values unknown
- Raw sample: `data/raw/public-team-games-sample.json`

### Project Management
- `epics/` -- active epics and story files
- `migrations/` -- numbered SQL migration files (`001_*.sql`, `002_*.sql`, etc.)

## Testing Rules
See CLAUDE.md Testing section and `.claude/rules/testing.md`.
- Use `respx` for `httpx` mocking, `responses` for `requests` mocking.
- Test data files go in `tests/fixtures/` or inline in the test.

## HTTP Request Discipline
See CLAUDE.md HTTP Request Discipline section.
- Session factory: `src/http/session.py`, function `create_session()`
- **NEVER create raw `httpx.Client()` or `requests.Session()` directly** -- always use `create_session()`

## Database Conventions (from data-engineer)
- `ip_outs`: Innings pitched as integer outs (1 IP = 3 outs). Always.
- FK-safe orphan handling: when a player_id is not in `players`, insert a stub row (first_name='Unknown', last_name='Unknown') before writing the stat row. Log a WARNING for operator backfill.
- Splits: nullable columns (home_obp, away_obp, vs_lhp_obp, vs_rhp_obp), not separate rows
- Local dev DB path: `data/app.db`

## Security
- NEVER hardcode credentials in code, tests, or docs
- Use `.env` for local dev (always in `.gitignore`)
- Redact auth headers before storing raw API responses
- GameChanger session tokens are sensitive data -- always

## FastAPI Patterns
- Routes returning `HTMLResponse | RedirectResponse` MUST use `response_model=None` on the decorator
  (otherwise FastAPI tries to make a Pydantic model from the Union and raises FastAPIError)
- `Form(...)` parameters require `python-multipart` installed -- add to requirements.txt
- `BaseHTTPMiddleware` from starlette: use `app.add_middleware(MyMiddleware)` before routers

## Auth System (E-023)
- `src/api/auth.py` -- SessionMiddleware + hash_token + create_session helpers
- `src/api/routes/auth.py` -- /auth/* routes (login/verify/logout)
- `src/api/email.py` -- Mailgun helper (stdout when MAILGUN_API_KEY not set)
- `src/api/templates/auth/` -- login.html, check_email.html, verify_error.html
- DEV_USER_EMAIL bypasses login; auto-creates is_admin=1 user if missing
- Session cookie: name=session, HttpOnly, SameSite=Lax, Max-Age=604800
- Tokens: token_urlsafe(32) for magic links (43 chars), token_hex(32) for sessions (64 chars)
- DB only stores SHA-256 hashes of tokens, never the raw value

## Test Database Pattern (auth-aware)
- Tests that touch the app must include auth tables in schema SQL (users, user_team_access,
  magic_link_tokens, passkey_credentials, sessions) for SessionMiddleware to not raise errors
- Set DEV_USER_EMAIL in test env_overrides to bypass auth for endpoint tests
