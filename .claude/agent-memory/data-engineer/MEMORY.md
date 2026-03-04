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
