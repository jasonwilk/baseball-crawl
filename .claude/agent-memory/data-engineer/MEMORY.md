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
- Migrations are append-only. Never edit an applied migration.
- Track applied state in a `_migrations` metadata table
- **Current state (verified 2026-03-26)**: `migrations/` contains 001–005 (`001_initial_schema.sql`, `002_add_user_role.sql`, `003_add_crawl_jobs.sql`, `004_add_team_season_year.sql`, `005_backfill_teams_public_id.sql`). Next migration: `006`.

## Schema Conventions

### ip_outs Convention
- Innings pitched stored as integer outs: 1 IP = 3 outs, 6.2 IP = 20 outs
- Storage format is always integer outs. No floating-point innings in the database.
- Display formatting is a valid read-time concern: `ip_outs // 3` for full innings, `ip_outs % 3` for partial

### Referential Integrity
- FK-safe orphan handling: when a player_id is not in `players`, insert a stub row (first_name='Unknown', last_name='Unknown') before writing the stat row. Log a WARNING for operator backfill.
- Foreign keys declared and enforced (`PRAGMA foreign_keys = ON`)
- Stub rows ensure FK constraints are never violated during ingestion

### Splits
- Home/away and L/R splits stored as nullable columns in season stats tables
- Column naming: `home_obp`, `away_obp`, `vs_lhp_obp`, `vs_rhp_obp`
- Not separate rows. Null means "not enough data to split."

### Timestamps
- All `created_at` and `updated_at` columns: text in SQLite `datetime('now')` format (e.g., `2026-03-01 14:30:00` -- space-separated, no `T`, no `Z`)

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
- Event-level data (plate appearances) is the source of truth; aggregate tables valid when query-time computation is impractical
- Player identity across teams is the hard problem -- `PlayerTeamSeason` junction handles it
- Opponent data is first-class: same schema structure as own-team data
- Normalize first; denormalize only for proven performance needs

## Topic File Index

- [endpoint-schema-notes.md](endpoint-schema-notes.md) -- Detailed schema implications for all discovered GameChanger API endpoints (team-detail, /me/teams, player-stats, schedule, public endpoints, opponents, boxscore, plays, roster, bridge endpoints). Response shapes, field types, join keys, normalization guidance, raw sample paths.
- [etl-patterns.md](etl-patterns.md) -- Token lifetime and ETL scheduling (14-day window), raw-to-processed pipeline, idempotent ingestion, pagination patterns (cursor-based, x-next-page), project file paths for migrations/DB/API spec/stat glossary.
