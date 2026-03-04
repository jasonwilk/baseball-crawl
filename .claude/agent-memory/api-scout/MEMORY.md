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
| `GET /teams/{id}/schedule` | Confirmed from capture | Pre-2026-03-01 |
| `GET /teams/{id}/game-summaries` | Confirmed LIVE, **92 total records, 2 pages complete -- full season** | 2026-03-04 |
| `GET /teams/{id}/players` | Confirmed from capture | Pre-2026-03-01 |
| `GET /teams/{id}/video-stream/assets` | Confirmed, 3 pages | Pre-2026-03-01 |
| `GET /teams/{id}/season-stats` | Confirmed LIVE, 200 OK | 2026-03-04 |
| `GET /teams/{id}/associations` | Confirmed LIVE, 244 records, single page | 2026-03-04 |
| `GET /teams/{id}/players/{player_id}/stats` | **CONFIRMED LIVE**, 80 records, 387 KB, single page, per-game stats + spray charts | 2026-03-04 |

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

### E-002-03 Blocker Update

E-002-03 was blocked pending a per-game stats endpoint. `/teams/{team_id}/players/{player_id}/stats` provides per-game player stats BUT it is player-centric, not game-centric. To reconstruct a box score for one game, you must call it once per player. This may unblock E-002-03 with a revised approach (call per-player rather than per-game) -- notify PM.

### Areas Not Yet Explored

- Authentication flow (token acquisition, refresh, expiration behavior)
- Game endpoints (true team box score / play-by-play) -- per-player stats now available via `/players/{id}/stats`; true per-game team box score endpoint may still exist
- Player profile endpoint -- separate from stats (player bio, photo, etc.) -- not yet explored
- `/teams/{id}/players/{player_id}/stats` for opponent players -- does it work with opponent team_id + player_id?
- Opponent season-stats availability (does /season-stats work for opponent team UUIDs?)
- Opponent associations availability (does /associations work for opponent team UUIDs?)
- Season scoping (query params for filtering by season/year)
- Rate limiting behavior
- Cold streak data (`streak_C`) -- only hot streak `streak_H` confirmed
- ETag-based conditional requests on game-summaries (x-next-page header + etag both present)
- `sport_specific.bats.total_outs` semantics -- pattern observed but not fully explained (28 outs at inning=5 bottom for a completed game)
- `gc-signature` and `gc-timestamp` response headers (listed in `access-control-expose-headers` but not yet seen populated)
- Whether `user_id` in associations `player` records matches player UUIDs from `/players` endpoint
- **NEW HIGH PRIORITY**: LSB coaching account access -- need gc-token from an account with manager/coach role on LSB Freshman, JV, Varsity, or Reserve teams. Current token covers only travel ball teams.
- `/me/teams` with `include=user_team_associations` omitted -- does the field default to empty or disappear?
- Pagination behavior of `/me/teams` when a user belongs to more than ~50 teams

## Security Rules

These five rules are non-negotiable, every session:

1. NEVER display, log, or store actual API tokens, session cookies, or credentials in any committable file.
2. Use `{AUTH_TOKEN}`, `{SESSION_ID}`, or similar placeholders when documenting API calls.
3. When the user provides a curl with real credentials, immediately work with the redacted version in all documentation.
4. If credentials appear in any file outside `.env`, flag it as a security issue immediately.
5. Strip authentication headers from all stored raw API responses.

## HTTP Request Discipline
See CLAUDE.md HTTP Request Discipline section.
- Canonical header set lives in `src/http/headers.py`

## Agent Interactions

- **baseball-coach** defines what data is most important to find -- prioritize exploration accordingly
- **data-engineer** consumes the spec to design schemas and ingestion pipelines
- **general-dev** consumes the spec to implement API client code
- **product-manager** uses discoveries to write informed stories

## Key File Paths

- API spec: `docs/gamechanger-api.md`
- Stat glossary: `docs/gamechanger-stat-glossary.md` (cross-referenced from API spec's season-stats schema)
- Credential extraction: `scripts/refresh_credentials.py`
- HTTP headers module: `src/http/headers.py`
- HTTP session module: `src/http/session.py`
- Local credentials: `.env` (gitignored)
