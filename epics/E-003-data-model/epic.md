# E-003: Data Model and Storage Schema

## Status
`ACTIVE`

## Overview
Design and implement the SQLite database schema that stores all baseball data ingested from GameChanger. The schema must support multi-team, multi-season, and player tracking across organizations -- a player's history should be queryable regardless of which teams they played for and in which years. Seasons are first-class entities with type-based filtering (spring HS, summer legion, fall). Teams carry crawl configuration so the ingestion pipeline knows what to fetch.

## Background & Context
The data model has some non-obvious complexity:
- **Multi-team**: Four Lincoln teams (Freshman, JV, Reserve, Varsity) plus future Legion/travel teams
- **Multi-season**: 30-game seasons, data should accumulate year over year. Seasons have types (spring-hs, summer-legion, fall) and temporal ordering.
- **Player mobility**: Players move between teams (Freshman -> JV -> Varsity progression is standard). A player has one `player_id` (from GameChanger) that is stable across their career.
- **Opponent data**: Stats exist for opponents we've played but whose teams we don't "own." They need to live in the same schema.
- **Splits**: Home/away and left/right splits are stored as columns in season stats tables (nullable -- populated only when the API provides them).
- **Coaching assignments**: Coach-to-team-to-season relationships are a domain concept (separate from auth). This has a cross-epic dependency on the `users` table from E-023.
- **PBP extensibility**: The schema is designed so that `plate_appearances` and `pitching_appearances` tables can be added later without modifying existing tables. Game totals now, play-by-play later.

### What already exists
- `migrations/001_initial_schema.sql` -- an initial schema that predates several design decisions. It lacks: the `seasons` table (uses bare `season TEXT` columns), crawl configuration on `teams`, `player_season_pitching`, and expanded splits.
- `migrations/apply_migrations.py` -- migration runner (delivered by E-009-02). Works correctly.
- E-001-03 (API spec) is DONE -- GameChanger IDs are TEXT/UUID format, confirmed.

### Expert consultation
- **data-engineer**: No formal consultation required. The schema decisions were made collaboratively with the user. The migration is straightforward DDL.
- **baseball-coach**: No formal consultation required. The user provided the pitching stat columns and coaching assignment roles directly. The stats follow standard baseball counting stat conventions.

## Goals
- A rewritten `001_initial_schema.sql` that creates all data tables with the finalized schema: `seasons`, `teams` (with crawl config), `players`, `team_rosters` (with season FK), `games` (with season FK), `player_game_batting`, `player_game_pitching`, `player_season_batting` (with expanded splits), `player_season_pitching` (new)
- A `coaching_assignments` migration that establishes coach-team-season relationships (depends on E-023 auth schema)
- Seed data and query validation tests proving the schema supports coaching queries
- Indexes optimized for common queries: player season stats, game history, team roster by season, team crawl config

## Non-Goals
- Computed/derived stats (batting average, OBP, etc.) -- store raw counting stats; compute in queries or a view layer
- Play-by-play tables (plate_appearances, pitching_appearances) -- designed for future addition but not built now
- Full-text search
- Real-time subscriptions or change notifications
- Any API layer (that's E-004)
- Data retention or archival policies
- The `users` table itself (that's E-023-01)

## Success Criteria
- The rewritten `001_initial_schema.sql` applies cleanly to a fresh SQLite database via `python migrations/apply_migrations.py`
- The `seasons` table supports temporal ordering and type-based filtering
- The `teams` table supports crawl configuration queries: `SELECT * FROM teams WHERE is_active = 1`
- The `players` table correctly handles a player appearing on multiple teams across multiple seasons
- `player_season_pitching` exists alongside `player_season_batting` with parallel structure and splits
- Seed data inserts for all tables complete without FK violations
- At least three representative coaching queries run in under 100ms against realistic data volume (4 teams, 30 games, 60 players)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-003-01 | Rewrite core schema migration with seasons, crawl config, and pitching | DONE | None | - |
| E-003-02 | Coaching assignments migration | TODO | E-003-01, E-023-01 | - |
| E-003-03 | Write migration tooling and local dev setup | ABANDONED | - | - |
| E-003-04 | Seed data and query validation tests | DONE | E-003-01 | - |

## Technical Notes

### Schema specification

#### seasons (NEW first-class entity)
```sql
CREATE TABLE seasons (
    season_id   TEXT PRIMARY KEY,  -- e.g., '2026-spring-hs'
    name        TEXT NOT NULL,     -- 'Spring 2026 High School'
    season_type TEXT NOT NULL,     -- 'spring-hs', 'summer-legion', 'fall'
    year        INTEGER NOT NULL,
    start_date  TEXT,              -- ISO 8601, nullable until known
    end_date    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```
Rationale: Players tracked across HS, Legion, and travel ball over time. "2025 Summer Legion" and "2026 Spring HS" are distinct seasons that need temporal ordering and type filtering.

#### teams (REFINED -- crawl configuration added)
```sql
CREATE TABLE teams (
    team_id    TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    level      TEXT,              -- 'varsity' | 'jv' | 'freshman' | 'reserve' | 'legion' | NULL
    is_owned   INTEGER NOT NULL DEFAULT 0,
    source     TEXT NOT NULL DEFAULT 'gamechanger',  -- data source identifier
    is_active  INTEGER NOT NULL DEFAULT 1,           -- 1 = crawl this team, 0 = skip
    last_synced TEXT,                                 -- ISO 8601 timestamp of last crawl
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```
The crawler reads: `SELECT * FROM teams WHERE is_active = 1`. The `/me/teams` API call seeds/discovers teams, then `is_active` is the explicit config that controls what gets crawled.

#### players (UNCHANGED)
```sql
CREATE TABLE players (
    player_id   TEXT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### team_rosters (REFINED -- season_id FK replaces season TEXT)
```sql
CREATE TABLE team_rosters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id       TEXT NOT NULL REFERENCES teams(team_id),
    player_id     TEXT NOT NULL REFERENCES players(player_id),
    season_id     TEXT NOT NULL REFERENCES seasons(season_id),
    jersey_number TEXT,
    position      TEXT,
    UNIQUE(team_id, player_id, season_id)
);
```

#### games (REFINED -- season_id FK replaces season TEXT)
```sql
CREATE TABLE games (
    game_id      TEXT PRIMARY KEY,
    season_id    TEXT NOT NULL REFERENCES seasons(season_id),
    game_date    TEXT NOT NULL,
    home_team_id TEXT NOT NULL REFERENCES teams(team_id),
    away_team_id TEXT NOT NULL REFERENCES teams(team_id),
    home_score   INTEGER,
    away_score   INTEGER,
    status       TEXT NOT NULL DEFAULT 'completed'
);
```

#### player_game_batting (UNCHANGED)
```sql
CREATE TABLE player_game_batting (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id   TEXT NOT NULL REFERENCES games(game_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id   TEXT NOT NULL REFERENCES teams(team_id),
    ab INTEGER, h INTEGER, doubles INTEGER, triples INTEGER,
    hr INTEGER, rbi INTEGER, bb INTEGER, so INTEGER, sb INTEGER,
    UNIQUE(game_id, player_id)
);
```

#### player_game_pitching (UNCHANGED)
```sql
CREATE TABLE player_game_pitching (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id   TEXT NOT NULL REFERENCES games(game_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id   TEXT NOT NULL REFERENCES teams(team_id),
    ip_outs   INTEGER,
    h INTEGER, er INTEGER, bb INTEGER, so INTEGER, hr INTEGER,
    UNIQUE(game_id, player_id)
);
```

#### player_season_batting (REFINED -- season_id FK, expanded splits)
```sql
CREATE TABLE player_season_batting (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   TEXT NOT NULL REFERENCES players(player_id),
    team_id     TEXT NOT NULL REFERENCES teams(team_id),
    season_id   TEXT NOT NULL REFERENCES seasons(season_id),
    games       INTEGER,
    ab INTEGER, h INTEGER, doubles INTEGER, triples INTEGER,
    hr INTEGER, rbi INTEGER, bb INTEGER, so INTEGER, sb INTEGER,
    -- Home/away splits (nullable)
    home_ab INTEGER, home_h INTEGER, home_hr INTEGER, home_bb INTEGER, home_so INTEGER,
    away_ab INTEGER, away_h INTEGER, away_hr INTEGER, away_bb INTEGER, away_so INTEGER,
    -- Left/right pitcher splits (nullable)
    vs_lhp_ab INTEGER, vs_lhp_h INTEGER, vs_lhp_hr INTEGER, vs_lhp_bb INTEGER, vs_lhp_so INTEGER,
    vs_rhp_ab INTEGER, vs_rhp_h INTEGER, vs_rhp_hr INTEGER, vs_rhp_bb INTEGER, vs_rhp_so INTEGER,
    UNIQUE(player_id, team_id, season_id)
);
```

#### player_season_pitching (NEW)
```sql
CREATE TABLE player_season_pitching (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   TEXT NOT NULL REFERENCES players(player_id),
    team_id     TEXT NOT NULL REFERENCES teams(team_id),
    season_id   TEXT NOT NULL REFERENCES seasons(season_id),
    games       INTEGER,
    ip_outs     INTEGER,  -- total outs recorded (3 outs = 1 inning)
    h INTEGER, er INTEGER, bb INTEGER, so INTEGER, hr INTEGER,
    -- Pitch counts (nullable -- populated when API provides them)
    pitches     INTEGER,
    strikes     INTEGER,
    -- Home/away splits (nullable)
    home_ip_outs INTEGER, home_h INTEGER, home_er INTEGER, home_bb INTEGER, home_so INTEGER,
    away_ip_outs INTEGER, away_h INTEGER, away_er INTEGER, away_bb INTEGER, away_so INTEGER,
    -- vs LHB/RHB splits (nullable)
    vs_lhb_ab INTEGER, vs_lhb_h INTEGER, vs_lhb_hr INTEGER, vs_lhb_bb INTEGER, vs_lhb_so INTEGER,
    vs_rhb_ab INTEGER, vs_rhb_h INTEGER, vs_rhb_hr INTEGER, vs_rhb_bb INTEGER, vs_rhb_so INTEGER,
    UNIQUE(player_id, team_id, season_id)
);
```
Note: Pitching splits use `vs_lhb` / `vs_rhb` (vs left-handed BATTERS / right-handed BATTERS), not `vs_lhp` / `vs_rhp` which is the batting table convention (vs left-handed PITCHERS / right-handed PITCHERS).

#### coaching_assignments (NEW -- migration 004, depends on E-023 users table)
```sql
CREATE TABLE coaching_assignments (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(user_id),
    team_id   TEXT NOT NULL REFERENCES teams(team_id),
    season_id TEXT NOT NULL REFERENCES seasons(season_id),
    role      TEXT NOT NULL DEFAULT 'assistant',  -- 'head_coach', 'assistant', 'volunteer'
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, team_id, season_id)
);
```
This is a DOMAIN table ("Coach Smith runs JV in Spring 2026"), not an auth/access table. The `user_team_access` table in E-023 controls dashboard visibility; this table records the coaching relationship.

### Migration numbering
- `001_initial_schema.sql` -- REWRITTEN by E-003-01 (all data model tables)
- `003_auth.sql` -- E-023-01 (auth tables, unchanged)
- `004_coaching_assignments.sql` -- E-003-02 (coaching assignments, after auth)

Migration 002 slot is unused. The migration runner handles gaps (applies files in numeric order for whatever files are present). E-023-01 previously noted "Migration 002 is reserved for the stats schema (E-003-02)" -- that reservation is no longer needed since everything is in the rewritten 001.

### PBP extensibility
The schema is designed so these tables can be added later in a new migration without modifying existing tables:
- `plate_appearances` (FK to games, player_game_batting)
- `pitching_appearances` (FK to games, player_game_pitching)

Game-level totals live in the existing `player_game_*` tables. PBP adds granularity without touching them.

### ip_outs convention
Innings pitched stored as integer outs (1 IP = 3 outs). A pitcher who throws 6.2 innings has 20 outs. Display layer converts: `ip_outs / 3` whole + `ip_outs % 3` thirds.

### Pre-production database reset
Since the project is pre-production with no real data, the rewrite of `001_initial_schema.sql` requires deleting any existing `data/app.db` and re-running migrations. This is documented in E-003-01's acceptance criteria.

### SQLite constraints
- All ID fields use `TEXT` (GameChanger IDs may be UUIDs or opaque strings)
- Booleans stored as `INTEGER 0/1` (SQLite has no native boolean type)
- Timestamps stored as `TEXT` in ISO 8601 format
- `PRAGMA foreign_keys=ON` is set by `apply_migrations.py` before running migrations
- `PRAGMA journal_mode=WAL` is set by `apply_migrations.py` for read concurrency

## Open Questions
None. All design decisions have been made by the user.

## History
- 2026-02-28: Created as DRAFT pending E-001-03 completion
- 2026-02-28: Architecture superseded by E-009 decision (Docker + SQLite replaces Cloudflare D1).
- 2026-03-01: Clarify pass -- replaced all Cloudflare D1/Wrangler references with SQLite per E-009 tech stack decision. Migration tooling references updated to apply_migrations.py. E-003-03 ABANDONED in favor of E-009-02. Title updated.
- 2026-03-03: Major refinement. Incorporated comprehensive data model decisions: seasons as first-class entity, teams crawl configuration, season_id FKs replacing season TEXT, player_season_pitching table, expanded splits, coaching_assignments (cross-epic dep on E-023). Rewrote all stories. Removed E-001-03 blocker (now DONE). Status set to READY.
- 2026-03-03: Spec review refinement. (1) P2 fix: Added `scripts/reset_dev_db.py` to E-003-01 Reference files -- AC-14 references this script for seed verification but the implementing agent would not have known to read it. (2) P3 deferred: E-003-01 sizing (15 ACs, 4 files) acknowledged but not split -- seed alignment must stay in the same story as the migration rewrite because `reset_dev_db.py` couples them (migrations then seed load; broken seed = broken dev reset). Data-engineer consultation not performed (Task tool unavailable); PM analysis confirmed no additional schema or migration concerns.
- 2026-03-03: Dispatch started. Epic set to ACTIVE. E-003-01 dispatched to general-purpose agent. E-003-02 remains BLOCKED (cross-epic dep on E-023-01). E-003-04 will dispatch after E-003-01 completes.
- 2026-03-03: Data-engineer consultation. Two P3 findings reviewed. (1) Finding: `tests/test_seed.py` missing from E-003-01 Reference files -- DEFERRED (already present at line 55 with explicit note about `_CORE_TABLES`; data-engineer finding was incorrect). (2) Finding: E-003-04 `seeded_db` fixture uses relative `Path("migrations")` instead of `_PROJECT_ROOT` pattern from existing `test_seed.py` -- REFINED, updated fixture example to use `_PROJECT_ROOT = Path(__file__).resolve().parent.parent`. Data-engineer confirmed: E-003-01 sizing correct (no split needed), schema model solid, `tests/fixtures/` creation obvious, E-003-02 cross-epic blocker correctly captured.
- 2026-03-03: E-003-01 DONE. Schema rewrite complete -- 15/15 ACs met. 214 tests pass (68 new schema/FK/crawl-config tests, 146 existing). Files: `migrations/001_initial_schema.sql` (rewritten), `data/seeds/seed_dev.sql` (updated), `tests/test_schema.py` (new), `tests/test_seed.py` (updated).
- 2026-03-03: E-003-04 DONE. Seed data and query validation complete -- 12/12 ACs met. 258 tests pass (44 new query tests, 214 existing). Files: `tests/fixtures/seed.sql` (new), `tests/test_schema_queries.py` (new). All coaching queries validated: batting avg/OBP/K-rate, roster by OBP, W-L record, home/away splits, K/9 leaderboard, crawl config, season type filtering. All queries under 100ms.
- 2026-03-03: E-003-02 remains TODO, blocked on E-023-01 (auth schema). Epic stays ACTIVE until E-003-02 can be dispatched.
