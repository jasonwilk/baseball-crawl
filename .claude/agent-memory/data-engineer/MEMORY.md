# Data Engineer -- Agent Memory

## Storage Architecture (E-009 Decision, 2026-02-28)

- SQLite everywhere. Local dev and production both use SQLite. No D1. No Wrangler.
- Local dev DB path: `./data/app.db` (host-mounted Docker volume)
- Production: SQLite in Docker volume with WAL mode + Litestream backup
- Dev/prod parity: `docker compose up` runs the same stack locally and in production

## Migration Tooling

- Migration runner: `apply_migrations.py` (runs at app startup, applies unapplied migrations in order)
- Migration files: `migrations/001_*.sql`, `migrations/002_*.sql`, etc.
  - Three-digit prefix, underscore, descriptive slug, `.sql` extension
  - Example: `migrations/001_initial_schema.sql`, `migrations/002_add_splits.sql`
- Migrations are append-only. Never edit an applied migration.
- Track applied state in a `_migrations` metadata table

## Schema Conventions

### ip_outs Convention
- Innings pitched stored as integer outs: 1 IP = 3 outs, 6.2 IP = 20 outs
- Always integer outs. No floating-point innings. No exceptions.
- To display: `ip_outs // 3` for full innings, `ip_outs % 3` for partial

### Referential Integrity
- FK-safe orphan handling: when a player_id is not in `players`, insert a stub row (first_name='Unknown', last_name='Unknown') before writing the stat row. Log a WARNING for operator backfill.
- Foreign keys declared and enforced (`PRAGMA foreign_keys = ON`)
- Stub rows ensure FK constraints are never violated during ingestion

### Splits
- Home/away and L/R splits stored as nullable columns in season stats tables
- Column naming: `home_obp`, `away_obp`, `vs_lhp_obp`, `vs_rhp_obp`
- Not separate rows. Null means "not enough data to split."

### Timestamps
- All `created_at` and `updated_at` columns: ISO 8601 text (e.g., `2026-03-01T14:30:00Z`)

### IDs
- GameChanger-sourced entities: `TEXT` primary keys (their IDs are opaque strings)
- Internally-generated entities: `INTEGER PRIMARY KEY` (SQLite rowid alias)

## Core Entity Model

| Entity | Purpose |
|--------|---------|
| `Team` | A team identity (LSB Varsity, opponent teams) |
| `Player` | A unique person (cross-team, cross-season identity) |
| `PlayerTeamSeason` | Junction: which player was on which team in which season |
| `Game` | A single game event (date, opponent, location, result) |
| `Lineup` | A player's position in a game lineup (batting order, fielding position) |
| `PlateAppearance` | A single plate appearance event (outcome, counts, matchup context) |
| `PitchingAppearance` | A pitcher's appearance in a game (outs recorded, runs, K, BB) |

### Key Design Decisions
- Store events (plate appearances), compute aggregates on read
- Player identity across teams is the hard problem -- `PlayerTeamSeason` junction handles it
- Opponent data is first-class: same schema structure as own-team data
- Normalize first; denormalize only for proven performance needs

## Team Detail Endpoint (confirmed 2026-03-04)

The `GET /teams/{team_id}` endpoint returns full metadata for a single team. Key schema implications beyond `/me/teams`:

- **`settings.scorekeeping.bats.innings_per_game`** (int): 7 for travel ball, likely 9 for HS varsity. Critical for stat normalization -- K/9, BB/9, and rate stats must be scaled to the correct game length. Store this per-team and use it when computing per-9 stats.
- **`settings.scorekeeping.bats.shortfielder_type`** (string): `"none"` observed. May affect fielding position mapping for younger divisions.
- **`settings.scorekeeping.bats.pitch_count_alert_1/2`** (int or null): Pitch count thresholds set by the team. Null when not configured. Could feed into arm health monitoring.
- **`settings.maxpreps`**: null for travel ball; may contain MaxPreps integration config for HS teams. Cross-reference source if non-null.
- **`organizations`** (array of `{organization_id, status}`): League/org affiliations at team level.
- **Opponent metadata use case**: Use `opponent_id` from schedule as `team_id` here to fetch opponent city, state, competition_level, record, innings_per_game. **CONFIRMED** working (2026-03-04): opponent UUID returns identical 25-field schema, `stat_access_level: confirmed_full`. Same endpoints, same schema -- no access restrictions for opponent teams. Opponent sample: `data/raw/team-detail-opponent-sample.json`.
- Same `ngb` double-JSON-parse quirk as `/me/teams`.
- Raw sample: `data/raw/team-detail-sample.json` (910 bytes, Lincoln Rebels 14U travel ball)

## /me/teams -- Team Metadata (confirmed 2026-03-04)

The `/me/teams` endpoint returns team-level metadata that maps to the `Team` entity. Key schema-relevant fields:
- `id` (UUID string) -- team identifier, used as path param for all `/teams/{id}/*` endpoints
- `name` (string) -- human-readable team name
- `season_year` (int) -- 2019-2026 observed
- `competition_level` (string) -- `"club_travel"`, `"recreational"` observed (expect `"high_school"` or similar for LSB teams)
- `archived` (boolean) -- 8 of 15 teams archived in sample
- `record` (object) -- `{wins, losses, ties}` always present, even for archived teams
- `organizations` (array of `{organization_id, status}`) -- league/org associations

Note: Current gc-token only covers travel ball teams. LSB high school teams require a separate coaching account token. See api-scout memory for details.

## Player-Stats Endpoint (confirmed 2026-03-04)

The `/teams/{team_id}/players/{player_id}/stats` endpoint returns per-game stat records for a single player. Key schema implications:

- **Response**: Bare JSON array of per-game records (80 records, 387 KB observed for one player)
- **Join key**: `event_id` matches `game_stream.game_id` from game-summaries (links player stats to games)
- **Per-game stats**: `player_stats.stats.offense` (84 batting fields), `player_stats.stats.defense` (34-129 pitching/fielding fields), `player_stats.stats.general` -- same field set as season-stats
- **Conditional sections**: `offense` absent for pitcher-only games, `defense` absent for DH-only games -- schema must handle nullable stat blocks
- **Cumulative stats**: `cumulative_stats` provides rolling season totals per game (same structure as player_stats) -- useful for trend analysis but records are NOT chronologically ordered
- **Spray charts**: `offensive_spray_charts` and `defensive_spray_charts` -- array of ball-in-play events with `playType`, `playResult`, `location.x`, `location.y`, defender `position`, `error` flag. Present on ~70% of games (offensive) and ~16% (defensive). This is a NEW data type not in any other endpoint.
- **Player-centric, not game-centric**: To reconstruct a full box score for one game, must call once per roster player (e.g., 12 API calls for 12-player roster) and filter by `event_id`
- **Schema impact**: Spray chart data needs its own table (normalized: game_id, player_id, chart_type, play_type, play_result, x, y, fielder_position, error)

## Schedule Endpoint (confirmed 2026-03-04)

The `/teams/{team_id}/schedule?fetch_place_details=true` endpoint returns the full event schedule for a team. Key schema implications:

- **Response**: Bare JSON array of schedule items; 228 events in one response (no pagination observed)
- **Event types**: `"game"` (103), `"practice"` (90), `"other"` (35) -- only games have `pregame_data`
- **Game entity mapping**: Each game event maps to the `Game` entity. `event.id` == `pregame_data.game_id` (confirmed on all 103 games). This `game_id` also matches `event_id` in game-summaries and player-stats -- universal join key.
- **`opponent_id`**: UUID in `pregame_data`, present on all 103 games. **CONFIRMED** usable as `team_id` in `/teams/{team_id}` (2026-03-04). Likely works in `/teams/{id}/season-stats`, `/teams/{id}/players` etc. -- season-stats/players not yet tested but team-detail access level (`stat_access_level: confirmed_full`) suggests they will work.
- **`home_away`**: `"home"`, `"away"`, or `null` -- maps directly to home/away split columns
- **`lineup_id`**: UUID or null (78/103 non-null) -- may link to an undiscovered lineup endpoint
- **Status filtering**: `"scheduled"` vs `"canceled"` (66 canceled) -- ETL must filter canceled games
- **Location polymorphism**: 6 distinct shapes from empty `{}` to full Google Place enrichment. Schema options: (a) flatten all fields into nullable columns, (b) store as JSON blob. Recommendation: nullable columns for lat/long/name/address (commonly queried), ignore Google Place details for now.
- **Full-day events**: When `full_day=true`, datetime format changes from `{"datetime": "ISO8601"}` to `{"date": "YYYY-MM-DD"}` and `timezone` is null. Parser must handle both formats.
- **Coordinate key inconsistency**: `{latitude, longitude}` in `location.coordinates` vs `{lat, long}` in `google_place_details.lat_long` -- normalize to one convention during ETL.
- **Date range**: 2024-11-08 to 2025-07-15 observed (full team history, not filtered to current season) -- may need season filtering.

## Public Team Profile Endpoint (confirmed 2026-03-04)

The `GET /public/teams/{public_id}` endpoint is the first confirmed **unauthenticated** endpoint. No `gc-token` or `gc-device-id` required. Key schema implications:

- **No-auth data pipeline**: If opponents have `public_id` values (available from authenticated `/teams/{team_id}` response), basic profile data (name, location, record, staff) can be fetched without credential rotation. ETL can split into auth-required vs. no-auth pipelines.
- **Different ID type**: Uses `public_id` slug (short alphanumeric string like `"a1GFM9Ku0BbF"`), NOT the internal UUID. The `id` field in the response IS the slug. Mapping between `public_id` and UUID requires the authenticated `/teams/{team_id}` response. The `Team` entity must store both `id` (UUID) and `public_id` (slug) if this endpoint is used.
- **Record key naming conflict**: Authenticated endpoint uses `record.wins`/`record.losses`/`record.ties` (plural). Public endpoint uses `team_season.record.win`/`team_season.record.loss`/`team_season.record.tie` (singular), wrapped in a `team_season` object. ETL parsers must normalize both shapes to the same schema columns.
- **Current-season only**: Public endpoint `team_season.record` is current season only, vs authenticated endpoint `record` which is cumulative all-time. If both sources are ingested, must track which represents what.
- **`staff` array**: Array of coach/manager name strings (no roles, no IDs). New data type not in any authenticated endpoint. May warrant a `team_staff` table or a JSON column on `Team` if coaching staff tracking is a requirement.
- **`avatar_url`**: Signed CloudFront URL (time-limited). Do NOT store the URL for long-term use; it will expire.
- **Missing fields vs authenticated**: No `competition_level`, `stat_access_level`, `settings`, `organizations`, `url_encoded_name`, `archived`, `created_at`. Cannot replace authenticated endpoint for full team metadata.
- Raw sample: `data/raw/public-team-profile-sample.json`

## ETL Patterns

- Raw-to-processed pipeline: (1) store raw API JSON blobs as audit trail, (2) parse and normalize into schema tables
- Ingestion must be idempotent: `INSERT OR IGNORE` or `INSERT ... ON CONFLICT` patterns
- Bulk-load a full game's worth of data in a single transaction
- Handle missing/null fields gracefully: log warnings, do not crash

### Pagination (confirmed 2026-03-04)
- game-summaries uses cursor-based pagination via `x-next-page` response header
- End-of-pagination signal: `x-next-page` header absent from response (do NOT check for empty body)
- Page size: 50 records max; final page may have fewer
- Full season for one team: 92 game records across 2 pages
- Working pagination loop pattern with code is in `docs/gamechanger-api.md` (Notes for Implementers section)

## Project File Paths

- Migrations: `migrations/`
- Database: `./data/app.db`
- API spec (source of truth for response shapes): `docs/gamechanger-api.md`
- Stat glossary (authoritative stat abbreviation definitions): `docs/gamechanger-stat-glossary.md`
  - Includes API field name mapping table (UI abbreviation -> API field name) -- critical for mapping season-stats API fields to schema columns
  - Covers: batting (standard + advanced), pitching (standard + advanced), pitch types, fielding, catcher, positional innings
- Source code: `src/`
- Tests: `tests/`
