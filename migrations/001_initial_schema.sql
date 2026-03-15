-- E-100-01: Complete schema rewrite (fresh-start authorized by user).
--
-- This single file replaces all prior migrations (001, 003-008).
-- Prior migrations archived in .project/archive/migrations-pre-E100/.
--
-- ID CONVENTION:
--   teams.id is an internal INTEGER PRIMARY KEY AUTOINCREMENT.
--   External GC identifiers live in dedicated columns:
--     gc_uuid:   team UUID from authenticated GC API (UNIQUE, nullable)
--     public_id: team slug from public GC URLs (UNIQUE, nullable)
--   ALL FK references to teams use teams(id) (INTEGER).
--   Never reference teams by gc_uuid or public_id in FK columns.
--   INTEGER AUTOINCREMENT PK applies to teams ONLY.
--   programs, seasons, and players keep TEXT PKs (GC-sourced or slug IDs).
--
-- IP_OUTS CONVENTION:
--   Innings pitched stored as integer outs: 1 IP = 3 outs, 6.2 IP = 20 outs.
--   Display: ip_outs / 3 whole innings + ip_outs % 3 thirds.
--   No floating-point innings anywhere in the schema.
--
-- CLASSIFICATION CHECK:
--   Mixed case is intentional: 'jv' lowercase (matching GC API),
--   age divisions uppercase ('8U'-'14U', matching USSSA/travel ball convention).
--
-- TIMESTAMP FORMAT:
--   All created_at / updated_at columns: TEXT ISO 8601 via datetime('now').
--   SQLite datetime('now') produces 'YYYY-MM-DD HH:MM:SS' (space, no T/Z).

-- ---------------------------------------------------------------------------
-- programs
-- ---------------------------------------------------------------------------
-- Umbrella entity grouping teams under an organizational program.
-- One seed row for Lincoln Standing Bear HS.
CREATE TABLE IF NOT EXISTS programs (
    program_id   TEXT PRIMARY KEY,               -- e.g., 'lsb-hs'
    name         TEXT NOT NULL,                   -- 'Lincoln Standing Bear HS'
    program_type TEXT NOT NULL CHECK(program_type IN ('hs', 'usssa', 'legion')),
    org_name     TEXT,                            -- org display name
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- teams
-- ---------------------------------------------------------------------------
-- Every team: Lincoln member teams and tracked opponent teams.
-- membership_type replaces the old is_owned boolean.
-- classification replaces the old level column.
-- source/is_active/last_synced preserve crawl configuration.
CREATE TABLE IF NOT EXISTS teams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    program_id      TEXT REFERENCES programs(program_id),
    membership_type TEXT NOT NULL CHECK(membership_type IN ('member', 'tracked')),
    -- classification: mixed case intentional (see header comment)
    classification  TEXT CHECK(
                        classification IS NULL OR classification IN (
                            'varsity', 'jv', 'freshman', 'reserve',
                            '8U', '9U', '10U', '11U', '12U', '13U', '14U', 'legion'
                        )),
    public_id       TEXT,                         -- GC slug (public URL identifier)
    gc_uuid         TEXT,                         -- GC UUID (authenticated API identifier)
    source          TEXT NOT NULL DEFAULT 'gamechanger',
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_synced     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- seasons
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS seasons (
    season_id   TEXT PRIMARY KEY,               -- e.g., '2026-spring-hs'
    name        TEXT NOT NULL,                   -- 'Spring 2026 High School'
    season_type TEXT NOT NULL,                   -- 'spring-hs', 'summer-legion', 'fall'
    year        INTEGER NOT NULL,
    program_id  TEXT REFERENCES programs(program_id),
    start_date  TEXT,
    end_date    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- players
-- ---------------------------------------------------------------------------
-- Stable identity per person across all teams and seasons.
-- gc_athlete_profile_id is the cross-team stable anchor from GC API.
CREATE TABLE IF NOT EXISTS players (
    player_id             TEXT PRIMARY KEY,
    first_name            TEXT NOT NULL,
    last_name             TEXT NOT NULL,
    bats                  TEXT CHECK(bats IN ('L', 'R', 'S')),
    throws                TEXT CHECK(throws IN ('L', 'R')),
    gc_athlete_profile_id TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- team_opponents
-- ---------------------------------------------------------------------------
-- Registry of opponent relationships between member teams and tracked teams.
CREATE TABLE IF NOT EXISTS team_opponents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    our_team_id      INTEGER NOT NULL REFERENCES teams(id),
    opponent_team_id INTEGER NOT NULL REFERENCES teams(id),
    first_seen_year  INTEGER,
    UNIQUE(our_team_id, opponent_team_id),
    CHECK(our_team_id != opponent_team_id)
);

-- ---------------------------------------------------------------------------
-- team_rosters
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_rosters (
    team_id       INTEGER NOT NULL REFERENCES teams(id),
    player_id     TEXT NOT NULL REFERENCES players(player_id),
    season_id     TEXT NOT NULL REFERENCES seasons(season_id),
    jersey_number TEXT,
    position      TEXT,
    PRIMARY KEY (team_id, player_id, season_id)
);

-- ---------------------------------------------------------------------------
-- games
-- ---------------------------------------------------------------------------
-- game_stream_id: GC game-stream UUID; used to fetch boxscores and plays.
CREATE TABLE IF NOT EXISTS games (
    game_id        TEXT PRIMARY KEY,
    season_id      TEXT NOT NULL REFERENCES seasons(season_id),
    game_date      TEXT NOT NULL,
    home_team_id   INTEGER NOT NULL REFERENCES teams(id),
    away_team_id   INTEGER NOT NULL REFERENCES teams(id),
    home_score     INTEGER,
    away_score     INTEGER,
    status         TEXT NOT NULL DEFAULT 'scheduled',
    game_stream_id TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- player_game_batting
-- ---------------------------------------------------------------------------
-- Per-player per-game batting stats from the boxscore endpoint.
-- batting_order: 1-indexed position in lineup (implicit from list order).
-- positions_played: text encoding, e.g., '(SS, P)'.
-- is_primary: 0 for substitutes (is_primary=false in boxscore).
-- stat_completeness: 'boxscore_only' for games loaded via boxscore only;
--   'supplemented' or 'full' when additional sources have enriched the row.
-- Excluded: pa (computable as ab+bb+hbp+shf+shb+ci), singles/1B (computable),
--   #P pitches seen, TS strikes seen (not in boxscore batting response).
CREATE TABLE IF NOT EXISTS player_game_batting (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id           TEXT NOT NULL REFERENCES games(game_id),
    player_id         TEXT NOT NULL REFERENCES players(player_id),
    team_id           INTEGER NOT NULL REFERENCES teams(id),
    batting_order     INTEGER,
    positions_played  TEXT,
    is_primary        INTEGER,
    stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only'
                      CHECK(stat_completeness IN ('full', 'supplemented', 'boxscore_only')),
    -- Main stats (always present per batter in boxscore)
    ab  INTEGER,
    r   INTEGER,
    h   INTEGER,
    rbi INTEGER,
    bb  INTEGER,
    so  INTEGER,
    -- Extra stats (sparse; only non-zero players appear in boxscore extras)
    doubles INTEGER,
    triples INTEGER,
    hr      INTEGER,
    tb      INTEGER,
    hbp     INTEGER,
    shf     INTEGER,
    sb      INTEGER,
    cs      INTEGER,
    e       INTEGER,
    UNIQUE(game_id, player_id)
);

-- ---------------------------------------------------------------------------
-- player_game_pitching
-- ---------------------------------------------------------------------------
-- Per-player per-game pitching stats from the boxscore endpoint.
-- decision: 'W', 'L', 'SV', or NULL (encoded in player_text in boxscore).
-- Excluded: HR allowed (not present in boxscore pitching extras).
-- r = runs allowed (total, not just earned runs).
CREATE TABLE IF NOT EXISTS player_game_pitching (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id           TEXT NOT NULL REFERENCES games(game_id),
    player_id         TEXT NOT NULL REFERENCES players(player_id),
    team_id           INTEGER NOT NULL REFERENCES teams(id),
    decision          TEXT CHECK(decision IN ('W', 'L', 'SV')),
    stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only'
                      CHECK(stat_completeness IN ('full', 'supplemented', 'boxscore_only')),
    -- Main stats (always present per pitcher in boxscore)
    ip_outs INTEGER,  -- integer outs; see ip_outs convention in header
    h       INTEGER,
    r       INTEGER,  -- total runs allowed
    er      INTEGER,
    bb      INTEGER,
    so      INTEGER,
    -- Extra stats (sparse; only non-zero players appear in boxscore extras)
    wp            INTEGER,
    hbp           INTEGER,
    pitches       INTEGER,
    total_strikes INTEGER,
    bf            INTEGER,
    UNIQUE(game_id, player_id)
);

-- ---------------------------------------------------------------------------
-- player_season_batting
-- ---------------------------------------------------------------------------
-- Season aggregate batting stats from the season-stats endpoint.
-- gp = games played (GC API field name).
-- Advanced stats (qab, hard, weak, etc.) are countable only -- no rates stored.
-- Split columns are nullable; null means insufficient data or not provided.
CREATE TABLE IF NOT EXISTS player_season_batting (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id         TEXT NOT NULL REFERENCES players(player_id),
    team_id           INTEGER NOT NULL REFERENCES teams(id),
    season_id         TEXT NOT NULL REFERENCES seasons(season_id),
    stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only'
                      CHECK(stat_completeness IN ('full', 'supplemented', 'boxscore_only')),
    games_tracked     INTEGER,   -- count of games this row was built from
    -- Standard batting stats
    gp      INTEGER,  -- games played
    pa      INTEGER,  -- plate appearances
    ab      INTEGER,
    h       INTEGER,
    singles INTEGER,  -- 1B (computable but stored from season-stats endpoint)
    doubles INTEGER,
    triples INTEGER,
    hr      INTEGER,
    rbi     INTEGER,
    r       INTEGER,
    bb      INTEGER,
    so      INTEGER,
    sol     INTEGER,  -- strikeouts looking
    hbp     INTEGER,
    shb     INTEGER,  -- sacrifice bunts (SHB in GC)
    shf     INTEGER,  -- sacrifice flies
    gidp    INTEGER,
    roe     INTEGER,  -- reached on error
    fc      INTEGER,  -- fielder's choice
    ci      INTEGER,  -- catcher's interference
    pik     INTEGER,  -- picked off
    sb      INTEGER,
    cs      INTEGER,
    tb      INTEGER,  -- total bases
    xbh     INTEGER,  -- extra base hits
    lob     INTEGER,
    three_out_lob INTEGER,
    ob      INTEGER,  -- times on base
    gshr    INTEGER,  -- grand slams
    two_out_rbi INTEGER,
    hrisp   INTEGER,  -- hits with RISP
    abrisp  INTEGER,  -- at-bats with RISP
    -- Advanced batting stats (countable only, no rates)
    qab         INTEGER,  -- quality at-bats
    hard        INTEGER,
    weak        INTEGER,
    lnd         INTEGER,  -- line drives
    flb         INTEGER,  -- fly balls (batting)
    gb          INTEGER,  -- ground balls (batting)
    ps          INTEGER,  -- pitches seen
    sw          INTEGER,  -- swings
    sm          INTEGER,  -- swings and misses
    inp         INTEGER,  -- in play
    full        INTEGER,  -- full count PA
    two_strikes INTEGER,
    two_s_plus_3 INTEGER,
    six_plus    INTEGER,
    lobb        INTEGER,  -- left on base in big spots
    -- Home/away splits (nullable)
    home_ab INTEGER, home_h INTEGER, home_hr INTEGER, home_bb INTEGER, home_so INTEGER,
    away_ab INTEGER, away_h INTEGER, away_hr INTEGER, away_bb INTEGER, away_so INTEGER,
    -- vs LHP/RHP splits (nullable)
    vs_lhp_ab INTEGER, vs_lhp_h INTEGER, vs_lhp_hr INTEGER, vs_lhp_bb INTEGER, vs_lhp_so INTEGER,
    vs_rhp_ab INTEGER, vs_rhp_h INTEGER, vs_rhp_hr INTEGER, vs_rhp_bb INTEGER, vs_rhp_so INTEGER,
    UNIQUE(player_id, team_id, season_id)
);

-- ---------------------------------------------------------------------------
-- player_season_pitching
-- ---------------------------------------------------------------------------
-- Season aggregate pitching stats from the season-stats endpoint.
-- gp_pitcher = games pitched (avoids collision with gp in batting context).
-- total_strikes / total_balls: renamed from strikes/tb to avoid confusion.
-- fb = fly balls (pitching); gb = ground balls (pitching).
-- Split naming: vs_lhb/vs_rhb = vs left-/right-handed batter.
CREATE TABLE IF NOT EXISTS player_season_pitching (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id         TEXT NOT NULL REFERENCES players(player_id),
    team_id           INTEGER NOT NULL REFERENCES teams(id),
    season_id         TEXT NOT NULL REFERENCES seasons(season_id),
    stat_completeness TEXT NOT NULL DEFAULT 'boxscore_only'
                      CHECK(stat_completeness IN ('full', 'supplemented', 'boxscore_only')),
    games_tracked     INTEGER,   -- count of games this row was built from
    -- Standard pitching stats
    gp_pitcher INTEGER,  -- games pitched
    gs         INTEGER,  -- games started
    ip_outs    INTEGER,  -- integer outs; see ip_outs convention in header
    bf         INTEGER,  -- batters faced
    pitches    INTEGER,
    h          INTEGER,
    er         INTEGER,
    bb         INTEGER,
    so         INTEGER,
    hr         INTEGER,
    bk         INTEGER,  -- balks
    wp         INTEGER,
    hbp        INTEGER,
    svo        INTEGER,  -- save opportunities
    sb         INTEGER,
    cs         INTEGER,
    go         INTEGER,  -- ground outs
    ao         INTEGER,  -- air outs
    loo        INTEGER,  -- left on base (opponent)
    zero_bb_inn INTEGER, -- innings with 0 walks
    inn_123    INTEGER,  -- 1-2-3 innings
    fps        INTEGER,  -- first pitch strikes
    lbfpn      INTEGER,  -- last batter faced plate number
    -- Win/loss/save records and additional season counts
    gp         INTEGER,  -- games played (all roles)
    w          INTEGER,
    l          INTEGER,
    sv         INTEGER,
    bs         INTEGER,  -- blown saves
    r          INTEGER,  -- total runs allowed
    sol        INTEGER,  -- strikeouts looking
    lob        INTEGER,
    pik        INTEGER,
    total_strikes INTEGER,  -- total strikes thrown
    total_balls  INTEGER,   -- total balls thrown
    lt_3       INTEGER,
    first_2_out INTEGER,
    lt_13      INTEGER,
    bbs        INTEGER,
    lobb       INTEGER,
    lobbs      INTEGER,
    sm         INTEGER,  -- swings and misses (pitching)
    sw         INTEGER,  -- swings
    weak       INTEGER,
    hard       INTEGER,
    lnd        INTEGER,  -- line drives allowed
    fb         INTEGER,  -- fly balls (pitching)
    gb         INTEGER,  -- ground balls (pitching)
    -- Home/away splits (nullable)
    home_ip_outs INTEGER, home_h INTEGER, home_er INTEGER, home_bb INTEGER, home_so INTEGER,
    away_ip_outs INTEGER, away_h INTEGER, away_er INTEGER, away_bb INTEGER, away_so INTEGER,
    -- vs LHB/RHB splits (nullable)
    vs_lhb_ab INTEGER, vs_lhb_h INTEGER, vs_lhb_hr INTEGER, vs_lhb_bb INTEGER, vs_lhb_so INTEGER,
    vs_rhb_ab INTEGER, vs_rhb_h INTEGER, vs_rhb_hr INTEGER, vs_rhb_bb INTEGER, vs_rhb_so INTEGER,
    UNIQUE(player_id, team_id, season_id)
);

-- ---------------------------------------------------------------------------
-- spray_charts
-- ---------------------------------------------------------------------------
-- Ball-in-play events with coordinate data from the player-stats endpoint.
-- pitcher_id: nullable FK for offensive charts (who threw the pitch).
CREATE TABLE IF NOT EXISTS spray_charts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id          TEXT REFERENCES games(game_id),
    player_id        TEXT REFERENCES players(player_id),
    team_id          INTEGER REFERENCES teams(id),
    pitcher_id       TEXT REFERENCES players(player_id),  -- nullable
    chart_type       TEXT CHECK(chart_type IN ('offensive', 'defensive')),
    play_type        TEXT,
    play_result      TEXT,
    x                REAL,
    y                REAL,
    fielder_position TEXT,
    error            INTEGER DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- opponent_links
-- ---------------------------------------------------------------------------
-- Maps GC opponents endpoint entries to resolved teams(id).
-- root_team_id: GC internal registry key from opponents endpoint (NOT a canonical UUID).
-- resolved_team_id: FK to teams(id) after resolution via progenitor_team_id.
CREATE TABLE IF NOT EXISTS opponent_links (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    our_team_id       INTEGER NOT NULL REFERENCES teams(id),
    root_team_id      TEXT NOT NULL,
    opponent_name     TEXT NOT NULL,
    resolved_team_id  INTEGER REFERENCES teams(id),
    public_id         TEXT,
    resolution_method TEXT,
    resolved_at       TEXT,
    is_hidden         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(our_team_id, root_team_id)
);

-- ---------------------------------------------------------------------------
-- scouting_runs
-- ---------------------------------------------------------------------------
-- Tracks each opponent scouting pipeline execution.
-- run_type: 'full' (default), 'schedule_only', 'boxscores_only', etc.
-- UNIQUE(team_id, season_id, run_type): one active run per opponent per season per type.
CREATE TABLE IF NOT EXISTS scouting_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id       INTEGER NOT NULL REFERENCES teams(id),
    season_id     TEXT NOT NULL REFERENCES seasons(season_id),
    run_type      TEXT NOT NULL DEFAULT 'full',
    started_at    TEXT,
    completed_at  TEXT,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    games_found   INTEGER,
    games_crawled INTEGER,
    players_found INTEGER,
    error_message TEXT,
    first_fetched TEXT NOT NULL DEFAULT (datetime('now')),
    last_checked  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(team_id, season_id, run_type)
);

-- ---------------------------------------------------------------------------
-- Auth tables
-- ---------------------------------------------------------------------------
-- users: simplified -- no user_id alias, no display_name, no is_admin.
-- E-100-02 migrates auth.py to use these new column names.
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- user_team_access: which users can access which teams.
CREATE TABLE IF NOT EXISTS user_team_access (
    user_id INTEGER NOT NULL REFERENCES users(id),
    team_id INTEGER NOT NULL REFERENCES teams(id),
    UNIQUE(user_id, team_id)
);

-- magic_link_tokens: passwordless login tokens.
CREATE TABLE IF NOT EXISTS magic_link_tokens (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL
);

-- passkey_credentials: WebAuthn passkey storage.
CREATE TABLE IF NOT EXISTS passkey_credentials (
    credential_id TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    public_key    TEXT NOT NULL,
    sign_count    INTEGER NOT NULL DEFAULT 0
);

-- sessions: active user sessions.
-- session_id replaces old session_token_hash column name.
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL
);

-- coaching_assignments: coach-to-team role assignments.
-- No season_id column (removed from old schema; role is team-level, not season-level).
-- UNIQUE(user_id, team_id): one role per user per team.
CREATE TABLE IF NOT EXISTS coaching_assignments (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    team_id INTEGER NOT NULL REFERENCES teams(id),
    role    TEXT NOT NULL DEFAULT 'assistant',
    UNIQUE(user_id, team_id)
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
-- Partial unique indexes for nullable external IDs (allow multiple NULLs).
CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_gc_uuid
    ON teams(gc_uuid) WHERE gc_uuid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_public_id
    ON teams(public_id) WHERE public_id IS NOT NULL;

-- Core query pattern indexes
CREATE INDEX IF NOT EXISTS idx_team_rosters_team_season ON team_rosters(team_id, season_id);
CREATE INDEX IF NOT EXISTS idx_team_rosters_player ON team_rosters(player_id);
CREATE INDEX IF NOT EXISTS idx_games_season_id ON games(season_id);
CREATE INDEX IF NOT EXISTS idx_games_home_team_id ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team_id ON games(away_team_id);
CREATE INDEX IF NOT EXISTS idx_games_game_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_pgb_game_id ON player_game_batting(game_id);
CREATE INDEX IF NOT EXISTS idx_pgb_player_id ON player_game_batting(player_id);
CREATE INDEX IF NOT EXISTS idx_pgb_team_id ON player_game_batting(team_id);
CREATE INDEX IF NOT EXISTS idx_pgp_game_id ON player_game_pitching(game_id);
CREATE INDEX IF NOT EXISTS idx_pgp_player_id ON player_game_pitching(player_id);
CREATE INDEX IF NOT EXISTS idx_pgp_team_id ON player_game_pitching(team_id);
CREATE INDEX IF NOT EXISTS idx_psb_player_season ON player_season_batting(player_id, season_id);
CREATE INDEX IF NOT EXISTS idx_psb_team_season ON player_season_batting(team_id, season_id);
CREATE INDEX IF NOT EXISTS idx_psp_player_season ON player_season_pitching(player_id, season_id);
CREATE INDEX IF NOT EXISTS idx_psp_team_season ON player_season_pitching(team_id, season_id);
CREATE INDEX IF NOT EXISTS idx_scouting_runs_team_season ON scouting_runs(team_id, season_id);
CREATE INDEX IF NOT EXISTS idx_coaching_assignments_user ON coaching_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_coaching_assignments_team ON coaching_assignments(team_id);

-- ---------------------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO programs (program_id, name, program_type, org_name) VALUES
    ('lsb-hs', 'Lincoln Standing Bear HS', 'hs', 'Lincoln Standing Bear');
