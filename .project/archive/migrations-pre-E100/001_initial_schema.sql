-- Migration 001: Core schema (rewritten by E-003-01)
--
-- Creates all core tables for baseball-crawl.
-- Rewritten from the initial schema to incorporate:
--   - seasons as a first-class entity (season_id FK replaces bare season TEXT)
--   - teams crawl configuration (source, is_active, last_synced)
--   - player_season_pitching table with home/away and vs_lhb/vs_rhb splits
--   - expanded player_season_batting splits (hr, bb, so per split group)
-- WAL mode and foreign key enforcement are enabled by apply_migrations.py
-- before this file runs.
--
-- Conventions:
--   - Primary keys: <table_singular>_id (TEXT for GameChanger IDs, INTEGER for
--     surrogate keys)
--   - Timestamps:   TEXT in ISO 8601 format, e.g., datetime('now')
--   - Booleans:     INTEGER 0/1 (SQLite has no native boolean type)
--   - Innings pitched: ip_outs (INTEGER) -- 1 IP = 3 outs, e.g., 6.2 IP = 20
--     outs. Display layer converts: ip_outs/3 whole innings + ip_outs%3 thirds.
--
-- NOTE: Any existing data/app.db must be deleted and recreated to apply
-- this rewritten migration. The migration runner tracks by filename only;
-- an in-place rewrite will NOT re-apply automatically to an existing database.
--
-- See E-003 for full schema rationale and design decisions.

-- ---------------------------------------------------------------------------
-- seasons (NEW -- first-class entity)
-- ---------------------------------------------------------------------------
-- Seasons are the temporal anchor for rosters, games, and player stats.
-- season_id is a human-readable slug, e.g., '2026-spring-hs'.
-- season_type: 'spring-hs' | 'summer-legion' | 'fall'
CREATE TABLE seasons (
    season_id   TEXT    PRIMARY KEY,              -- e.g., '2026-spring-hs'
    name        TEXT    NOT NULL,                 -- 'Spring 2026 High School'
    season_type TEXT    NOT NULL,                 -- 'spring-hs', 'summer-legion', 'fall'
    year        INTEGER NOT NULL,
    start_date  TEXT,                             -- ISO 8601, nullable until known
    end_date    TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- players (UNCHANGED)
-- ---------------------------------------------------------------------------
-- Stable identity for every person who has ever appeared in our data.
-- GameChanger player IDs are used as the primary key.
CREATE TABLE players (
    player_id   TEXT    PRIMARY KEY,
    first_name  TEXT    NOT NULL,
    last_name   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- teams (REFINED -- crawl configuration added)
-- ---------------------------------------------------------------------------
-- Every team: both Lincoln teams we own and opponent teams.
-- is_active controls whether the crawler fetches this team: 1 = crawl, 0 = skip.
-- Defaults to 1 -- newly discovered teams are crawled by default.
-- The crawler reads: SELECT * FROM teams WHERE is_active = 1
CREATE TABLE teams (
    team_id     TEXT    PRIMARY KEY,
    name        TEXT    NOT NULL,
    -- Level within the Lincoln program (null for opponents)
    level       TEXT,                             -- 'varsity' | 'jv' | 'freshman' | 'reserve' | 'legion' | NULL
    -- 1 if this is a Lincoln team we manage; 0 for opponents
    is_owned    INTEGER NOT NULL DEFAULT 0,
    -- Crawl configuration
    source      TEXT    NOT NULL DEFAULT 'gamechanger',  -- data source identifier
    is_active   INTEGER NOT NULL DEFAULT 1,              -- 1 = crawl this team, 0 = skip
    last_synced TEXT,                                    -- ISO 8601 timestamp of last crawl
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- team_rosters (REFINED -- season_id FK replaces season TEXT)
-- ---------------------------------------------------------------------------
-- Player roster membership scoped to a team and season.
-- A player appears here once per team per season they were on.
CREATE TABLE team_rosters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id       TEXT    NOT NULL REFERENCES teams(team_id),
    player_id     TEXT    NOT NULL REFERENCES players(player_id),
    season_id     TEXT    NOT NULL REFERENCES seasons(season_id),
    jersey_number TEXT,
    position      TEXT,
    UNIQUE(team_id, player_id, season_id)
);

-- ---------------------------------------------------------------------------
-- games (REFINED -- season_id FK replaces season TEXT)
-- ---------------------------------------------------------------------------
-- Every game played.
CREATE TABLE games (
    game_id      TEXT    PRIMARY KEY,
    season_id    TEXT    NOT NULL REFERENCES seasons(season_id),
    game_date    TEXT    NOT NULL,                -- ISO 8601 date string
    home_team_id TEXT    NOT NULL REFERENCES teams(team_id),
    away_team_id TEXT    NOT NULL REFERENCES teams(team_id),
    home_score   INTEGER,
    away_score   INTEGER,
    status       TEXT    NOT NULL DEFAULT 'completed'
);

-- ---------------------------------------------------------------------------
-- player_game_batting (UNCHANGED)
-- ---------------------------------------------------------------------------
-- Per-player per-game batting stats.
CREATE TABLE player_game_batting (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id   TEXT    NOT NULL REFERENCES games(game_id),
    player_id TEXT    NOT NULL REFERENCES players(player_id),
    team_id   TEXT    NOT NULL REFERENCES teams(team_id),
    ab        INTEGER,
    h         INTEGER,
    doubles   INTEGER,
    triples   INTEGER,
    hr        INTEGER,
    rbi       INTEGER,
    bb        INTEGER,
    so        INTEGER,
    sb        INTEGER,
    UNIQUE(game_id, player_id)
);

-- ---------------------------------------------------------------------------
-- player_game_pitching (UNCHANGED)
-- ---------------------------------------------------------------------------
-- Per-player per-game pitching stats.
CREATE TABLE player_game_pitching (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id   TEXT    NOT NULL REFERENCES games(game_id),
    player_id TEXT    NOT NULL REFERENCES players(player_id),
    team_id   TEXT    NOT NULL REFERENCES teams(team_id),
    ip_outs   INTEGER,                            -- total outs recorded (3 outs = 1 inning)
    h         INTEGER,
    er        INTEGER,
    bb        INTEGER,
    so        INTEGER,
    hr        INTEGER,
    UNIQUE(game_id, player_id)
);

-- ---------------------------------------------------------------------------
-- player_season_batting (REFINED -- season_id FK, expanded splits)
-- ---------------------------------------------------------------------------
-- Season aggregate batting stats (from API, not computed).
-- Split columns are nullable -- populated only when the API provides them.
-- Split naming: vs_lhp/vs_rhp = vs left-handed PITCHER / right-handed PITCHER.
CREATE TABLE player_season_batting (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   TEXT    NOT NULL REFERENCES players(player_id),
    team_id     TEXT    NOT NULL REFERENCES teams(team_id),
    season_id   TEXT    NOT NULL REFERENCES seasons(season_id),
    games       INTEGER,
    ab          INTEGER,
    h           INTEGER,
    doubles     INTEGER,
    triples     INTEGER,
    hr          INTEGER,
    rbi         INTEGER,
    bb          INTEGER,
    so          INTEGER,
    sb          INTEGER,
    -- Home/away splits (nullable)
    home_ab     INTEGER,
    home_h      INTEGER,
    home_hr     INTEGER,
    home_bb     INTEGER,
    home_so     INTEGER,
    away_ab     INTEGER,
    away_h      INTEGER,
    away_hr     INTEGER,
    away_bb     INTEGER,
    away_so     INTEGER,
    -- Left/right pitcher splits (nullable)
    vs_lhp_ab   INTEGER,
    vs_lhp_h    INTEGER,
    vs_lhp_hr   INTEGER,
    vs_lhp_bb   INTEGER,
    vs_lhp_so   INTEGER,
    vs_rhp_ab   INTEGER,
    vs_rhp_h    INTEGER,
    vs_rhp_hr   INTEGER,
    vs_rhp_bb   INTEGER,
    vs_rhp_so   INTEGER,
    UNIQUE(player_id, team_id, season_id)
);

-- ---------------------------------------------------------------------------
-- player_season_pitching (NEW)
-- ---------------------------------------------------------------------------
-- Season aggregate pitching stats (from API, not computed).
-- ip_outs convention: 1 IP = 3 outs (see header comment).
-- Split naming: vs_lhb/vs_rhb = vs left-handed BATTER / right-handed BATTER.
-- This intentionally differs from player_season_batting splits (vs_lhp/vs_rhp).
CREATE TABLE player_season_pitching (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   TEXT    NOT NULL REFERENCES players(player_id),
    team_id     TEXT    NOT NULL REFERENCES teams(team_id),
    season_id   TEXT    NOT NULL REFERENCES seasons(season_id),
    games       INTEGER,
    ip_outs     INTEGER,                          -- total outs recorded (3 outs = 1 inning)
    h           INTEGER,
    er          INTEGER,
    bb          INTEGER,
    so          INTEGER,
    hr          INTEGER,
    -- Pitch counts (nullable -- populated when API provides them)
    pitches     INTEGER,
    strikes     INTEGER,
    -- Home/away splits (nullable)
    home_ip_outs INTEGER,
    home_h       INTEGER,
    home_er      INTEGER,
    home_bb      INTEGER,
    home_so      INTEGER,
    away_ip_outs INTEGER,
    away_h       INTEGER,
    away_er      INTEGER,
    away_bb      INTEGER,
    away_so      INTEGER,
    -- vs LHB/RHB splits (nullable)
    vs_lhb_ab   INTEGER,
    vs_lhb_h    INTEGER,
    vs_lhb_hr   INTEGER,
    vs_lhb_bb   INTEGER,
    vs_lhb_so   INTEGER,
    vs_rhb_ab   INTEGER,
    vs_rhb_h    INTEGER,
    vs_rhb_hr   INTEGER,
    vs_rhb_bb   INTEGER,
    vs_rhb_so   INTEGER,
    UNIQUE(player_id, team_id, season_id)
);

-- ---------------------------------------------------------------------------
-- Indexes for common query patterns
-- ---------------------------------------------------------------------------
CREATE INDEX idx_team_rosters_team_season       ON team_rosters(team_id, season_id);
CREATE INDEX idx_team_rosters_player            ON team_rosters(player_id);
CREATE INDEX idx_games_season                   ON games(season_id);
CREATE INDEX idx_games_home_team                ON games(home_team_id);
CREATE INDEX idx_games_away_team                ON games(away_team_id);
CREATE INDEX idx_player_game_batting_game       ON player_game_batting(game_id);
CREATE INDEX idx_player_game_batting_player     ON player_game_batting(player_id);
CREATE INDEX idx_player_game_pitching_game      ON player_game_pitching(game_id);
CREATE INDEX idx_player_season_batting_ps       ON player_season_batting(player_id, season_id);
CREATE INDEX idx_player_season_pitching_ps      ON player_season_pitching(player_id, season_id);
CREATE INDEX idx_teams_is_active                ON teams(is_active);
