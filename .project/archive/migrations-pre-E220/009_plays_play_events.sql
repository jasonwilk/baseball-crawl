-- E-195-02: Plays and play_events tables for play-by-play data.
--
-- Two tables:
--   plays      -- one row per plate appearance
--   play_events -- one row per event within a plate appearance
--
-- Idempotent: uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.

-- ---------------------------------------------------------------------------
-- plays
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plays (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id               TEXT    NOT NULL REFERENCES games(game_id),
    play_order            INTEGER NOT NULL,
    inning                INTEGER NOT NULL,
    half                  TEXT    NOT NULL CHECK(half IN ('top', 'bottom')),
    season_id             TEXT    NOT NULL REFERENCES seasons(season_id),
    batting_team_id       INTEGER NOT NULL REFERENCES teams(id),
    batter_id             TEXT    NOT NULL REFERENCES players(player_id),
    pitcher_id            TEXT    REFERENCES players(player_id),
    outcome               TEXT,
    pitch_count           INTEGER NOT NULL DEFAULT 0,
    is_first_pitch_strike INTEGER NOT NULL DEFAULT 0,
    is_qab                INTEGER NOT NULL DEFAULT 0,
    home_score            INTEGER,
    away_score            INTEGER,
    did_score_change      INTEGER,
    outs_after            INTEGER,
    did_outs_change       INTEGER,
    UNIQUE(game_id, play_order)
);

-- ---------------------------------------------------------------------------
-- play_events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS play_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    play_id       INTEGER NOT NULL REFERENCES plays(id),
    event_order   INTEGER NOT NULL,
    event_type    TEXT    NOT NULL CHECK(event_type IN ('pitch', 'baserunner', 'substitution', 'other')),
    pitch_result  TEXT    CHECK(pitch_result IS NULL OR pitch_result IN (
                      'ball', 'strike_looking', 'strike_swinging', 'foul', 'foul_tip', 'in_play'
                  )),
    is_first_pitch INTEGER NOT NULL DEFAULT 0,
    raw_template  TEXT,
    UNIQUE(play_id, event_order)
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_plays_game_id
    ON plays(game_id);

CREATE INDEX IF NOT EXISTS idx_plays_batter_id
    ON plays(batter_id);

CREATE INDEX IF NOT EXISTS idx_plays_pitcher_id
    ON plays(pitcher_id);

-- Partial index for efficient FPS% queries (excludes HBP and IBB from denominator).
CREATE INDEX IF NOT EXISTS idx_plays_fps
    ON plays(pitcher_id, is_first_pitch_strike)
    WHERE outcome NOT IN ('Hit By Pitch', 'Intentional Walk');
