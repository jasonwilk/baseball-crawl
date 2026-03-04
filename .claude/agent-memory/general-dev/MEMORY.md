# General Dev -- Agent Memory

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
- `data/raw/` -- raw API response samples (gitignored). game-summaries: `game-summaries-sample.json` (page 1, 50 records), `game-summaries-page2-sample.json` (page 2, 42 records). me-teams: `me-teams-sample.json` (15 teams, 18 KB). player-stats: `player-stats-sample.json` (80 per-game records, 387 KB). schedule: `schedule-sample.json` (228 events, 134 KB). team-detail: `team-detail-sample.json` (own team, 910 bytes), `team-detail-opponent-sample.json` (opponent team via opponent_id, same schema). public-team-profile: `public-team-profile-sample.json` (unauthenticated, ~1.2 KB)
- `docs/` -- API specs and documentation
- `docs/gamechanger-api.md` -- THE single source of truth for GameChanger API knowledge
- `docs/gamechanger-stat-glossary.md` -- authoritative data dictionary for all GameChanger stat abbreviations (batting, pitching, fielding, catcher, positional innings). Includes API field name mapping table for abbreviations that differ between UI and API. Reference when parsing season-stats response fields.

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
- Working Python pagination loop in `docs/gamechanger-api.md` (Notes for Implementers section) -- use as reference implementation

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
