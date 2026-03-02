# E-003: Data Model and Storage Schema

## Status
`ACTIVE`

## Overview
Design and implement the SQLite database schema that stores all baseball data ingested from GameChanger. The schema must support multi-team, multi-season, and player tracking across organizations -- a player's history should be queryable regardless of which teams they played for and in which years.

## Background & Context
The data model has some non-obvious complexity:
- **Multi-team**: Four Lincoln teams (Freshman, JV, Reserve, Varsity) plus future Legion/travel teams
- **Multi-season**: 30-game seasons, data should accumulate year over year
- **Player mobility**: Players move between teams (Freshman -> JV -> Varsity progression is standard). A player has one identity (`player_id`) but multiple team-season memberships.
- **Opponent data**: Stats exist for opponents we've played but whose teams we don't "own." They need to live in the same schema.
- **Splits**: Home/away and left/right splits may not come directly from the API -- they may need to be derived and stored.

This epic should be started after E-001-03 (API spec) is at least partially complete, because the schema should reflect what data is actually available.

## Goals
- A SQLite database with a schema that supports all entities: teams, players, seasons, games, player-game stats, player-season stats, and rosters
- Migration tooling: a set of numbered SQL migration files and a script to apply them
- A local development setup: ability to run the schema against a local SQLite file for development and testing
- The schema handles player-across-organizations tracking via a stable `player_id`
- Indexes optimized for the most common queries: player season stats, game history, team roster by season

## Non-Goals
- Computed/derived stats (batting average, OBP, etc.) -- store raw counting stats; compute in queries or a view layer
- Full-text search
- Real-time subscriptions or change notifications
- Any API layer (that's E-004)
- Data retention or archival policies

## Success Criteria
- All migration files apply cleanly to a fresh SQLite database with `python migrations/apply_migrations.py`
- A developer can run `python migrations/apply_migrations.py` to create a local SQLite file at `data/app.db` for development
- The `players` table correctly handles a player appearing on multiple teams across multiple seasons
- All load stories in E-002 (E-002-06, E-002-07) can write to this schema without errors
- At least three representative queries run in under 100ms against a populated local database with realistic data volume (4 teams, 30 games, 60 players)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-003-01 | Define core schema: teams, players, seasons, rosters | TODO | E-001-03 | - |
| E-003-02 | Define stats schema: games, player-game stats, season stats | TODO | E-003-01 | - |
| E-003-03 | Write migration tooling and local dev setup | ABANDONED | E-003-01 | - |
| E-003-04 | Write seed data and query validation tests | TODO | E-003-02, E-009-02 | - |

## Technical Notes

### SQLite
The database is a plain SQLite file at `data/app.db`. Migrations are applied via `python migrations/apply_migrations.py`, which reads numbered SQL files from `migrations/` and applies them in order.

### Recommended Schema (Sketch)

This is a starting sketch. The implementing agent should refine based on what E-001-03 reveals.

```sql
-- Stable identity for every person who has ever appeared in our data
CREATE TABLE players (
    player_id TEXT PRIMARY KEY,  -- GameChanger's ID
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Every team (owned or opponent)
CREATE TABLE teams (
    team_id TEXT PRIMARY KEY,    -- GameChanger's ID
    name TEXT NOT NULL,
    level TEXT,                  -- 'varsity', 'jv', 'freshman', 'reserve', 'legion', null for opponents
    is_owned INTEGER NOT NULL DEFAULT 0,  -- 1 if this is a Lincoln team we manage
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Players on teams, scoped to a season
CREATE TABLE team_rosters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    season TEXT NOT NULL,
    jersey_number TEXT,
    position TEXT,
    UNIQUE(team_id, player_id, season)
);

-- Every game
CREATE TABLE games (
    game_id TEXT PRIMARY KEY,
    season TEXT NOT NULL,
    game_date TEXT NOT NULL,
    home_team_id TEXT NOT NULL REFERENCES teams(team_id),
    away_team_id TEXT NOT NULL REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    status TEXT NOT NULL DEFAULT 'completed'
);

-- Per-player per-game batting stats
CREATE TABLE player_game_batting (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL REFERENCES games(game_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    ab INTEGER, h INTEGER, doubles INTEGER, triples INTEGER,
    hr INTEGER, rbi INTEGER, bb INTEGER, so INTEGER, sb INTEGER,
    UNIQUE(game_id, player_id)
);

-- Per-player per-game pitching stats
CREATE TABLE player_game_pitching (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL REFERENCES games(game_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    ip_outs INTEGER,  -- store as outs to avoid decimal arithmetic
    h INTEGER, er INTEGER, bb INTEGER, so INTEGER, hr INTEGER,
    UNIQUE(game_id, player_id)
);

-- Season aggregate stats (from API, not computed)
CREATE TABLE player_season_batting (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    season TEXT NOT NULL,
    games INTEGER, ab INTEGER, h INTEGER, doubles INTEGER, triples INTEGER,
    hr INTEGER, rbi INTEGER, bb INTEGER, so INTEGER, sb INTEGER,
    -- splits (if available from API)
    home_ab INTEGER, home_h INTEGER,
    away_ab INTEGER, away_h INTEGER,
    vs_lhp_ab INTEGER, vs_lhp_h INTEGER,
    vs_rhp_ab INTEGER, vs_rhp_h INTEGER,
    UNIQUE(player_id, team_id, season)
);
```

### Migration Naming
Use three-digit numbered prefixes: `migrations/001_initial_schema.sql`, `migrations/002_add_splits.sql`, etc. Never modify existing migrations; only add new ones.

### Local Development
Run `python migrations/apply_migrations.py` to create and migrate the SQLite database at `data/app.db`. There is a single database target -- no distinction between local and production environments at the migration level.

## Open Questions
- Should splits (home/away, L/R) be stored as columns in the season stats table, or as a separate `player_splits` table? (Separate table is more flexible if more split types are added later.)
- What is the GameChanger `player_id` format? (UUID? Integer? String?) -- affects PRIMARY KEY choice.
- Do we need a `raw_json` column on any table for debugging (store the raw API response alongside the normalized data)?

## History
- 2026-02-28: Created as DRAFT pending E-001-03 completion
- 2026-02-28: Architecture superseded by E-009 decision (Docker + SQLite replaces Cloudflare D1).
- 2026-03-01: Clarify pass -- replaced all Cloudflare D1/Wrangler references with SQLite per E-009 tech stack decision. Migration tooling references updated to apply_migrations.py. E-003-03 ABANDONED in favor of E-009-02. Title updated.
