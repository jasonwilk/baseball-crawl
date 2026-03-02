-- Migration 001: Initial schema
--
-- Creates all core tables for baseball-crawl.
-- Schema designed per E-003 (Data Model) spec.
-- WAL mode is enabled by apply_migrations.py before this file runs.
--
-- Naming conventions:
--   - Primary keys: <table_singular>_id (TEXT for GameChanger IDs, INTEGER for joins)
--   - Timestamps:   TEXT in ISO 8601 format (datetime('now'))
--   - Booleans:     INTEGER 0/1
--   - Innings pitched: stored as total outs (INTEGER) to avoid decimal arithmetic

-- Stable identity for every person who has ever appeared in our data.
-- GameChanger player IDs are used as the primary key.
CREATE TABLE players (
    player_id   TEXT    PRIMARY KEY,
    first_name  TEXT    NOT NULL,
    last_name   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Every team: both Lincoln teams we own and opponent teams.
CREATE TABLE teams (
    team_id    TEXT    PRIMARY KEY,
    name       TEXT    NOT NULL,
    -- Level within the Lincoln program (null for opponents)
    level      TEXT,   -- 'varsity' | 'jv' | 'freshman' | 'reserve' | 'legion' | NULL
    -- 1 if this is a Lincoln team we manage; 0 for opponents
    is_owned   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Player roster membership scoped to a team and season.
-- A player appears here once per team per season they were on.
CREATE TABLE team_rosters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id       TEXT    NOT NULL REFERENCES teams(team_id),
    player_id     TEXT    NOT NULL REFERENCES players(player_id),
    season        TEXT    NOT NULL,  -- e.g. '2025', '2026'
    jersey_number TEXT,
    position      TEXT,
    UNIQUE(team_id, player_id, season)
);

-- Every game played.
CREATE TABLE games (
    game_id      TEXT    PRIMARY KEY,
    season       TEXT    NOT NULL,
    game_date    TEXT    NOT NULL,  -- ISO 8601 date string
    home_team_id TEXT    NOT NULL REFERENCES teams(team_id),
    away_team_id TEXT    NOT NULL REFERENCES teams(team_id),
    home_score   INTEGER,
    away_score   INTEGER,
    status       TEXT    NOT NULL DEFAULT 'completed'
);

-- Per-player per-game batting stats.
CREATE TABLE player_game_batting (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    TEXT    NOT NULL REFERENCES games(game_id),
    player_id  TEXT    NOT NULL REFERENCES players(player_id),
    team_id    TEXT    NOT NULL REFERENCES teams(team_id),
    ab         INTEGER,
    h          INTEGER,
    doubles    INTEGER,
    triples    INTEGER,
    hr         INTEGER,
    rbi        INTEGER,
    bb         INTEGER,
    so         INTEGER,
    sb         INTEGER,
    UNIQUE(game_id, player_id)
);

-- Per-player per-game pitching stats.
CREATE TABLE player_game_pitching (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id   TEXT    NOT NULL REFERENCES games(game_id),
    player_id TEXT    NOT NULL REFERENCES players(player_id),
    team_id   TEXT    NOT NULL REFERENCES teams(team_id),
    ip_outs   INTEGER,  -- total outs recorded (3 outs = 1 inning)
    h         INTEGER,
    er        INTEGER,
    bb        INTEGER,
    so        INTEGER,
    hr        INTEGER,
    UNIQUE(game_id, player_id)
);

-- Season aggregate batting stats (from API, not computed).
-- Splits columns are nullable -- populated only when the API provides them.
CREATE TABLE player_season_batting (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   TEXT    NOT NULL REFERENCES players(player_id),
    team_id     TEXT    NOT NULL REFERENCES teams(team_id),
    season      TEXT    NOT NULL,
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
    away_ab     INTEGER,
    away_h      INTEGER,
    -- Left/right pitcher splits (nullable)
    vs_lhp_ab   INTEGER,
    vs_lhp_h    INTEGER,
    vs_rhp_ab   INTEGER,
    vs_rhp_h    INTEGER,
    UNIQUE(player_id, team_id, season)
);

-- Indexes for the most common query patterns.
CREATE INDEX idx_team_rosters_team_season   ON team_rosters(team_id, season);
CREATE INDEX idx_team_rosters_player        ON team_rosters(player_id);
CREATE INDEX idx_games_season               ON games(season);
CREATE INDEX idx_games_home_team            ON games(home_team_id);
CREATE INDEX idx_games_away_team            ON games(away_team_id);
CREATE INDEX idx_player_game_batting_game   ON player_game_batting(game_id);
CREATE INDEX idx_player_game_batting_player ON player_game_batting(player_id);
CREATE INDEX idx_player_game_pitching_game  ON player_game_pitching(game_id);
CREATE INDEX idx_player_season_batting_ps   ON player_season_batting(player_id, season);
