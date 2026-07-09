-- Synthetic "teeth" fixture for the plays-vs-boxscore reconciliation scoreboard
-- (E-257-01).  Used ONLY by tests/test_recon_scoreboard.py.  NOT seed.sql.
--
-- This seeds a POPULATED, KNOWN state -- not an empty DB -- so the scoreboard
-- tests assert against non-trivial values on every axis:
--
--   * Per-stat fidelity: PB_agree (batter) and PP_agree (pitcher) have plays
--     that EXACTLY reconstruct their boxscore lines, so every scored stat's
--     exact% is 100% and abs-Δ is 0 (AC-6a).
--   * dropped_pitch_events == 2: two event_type='other' rows whose raw_template
--     carries a (PitchType) suffix (re-classify to 'pitch'); a third 'other'
--     row with a NON-pitch parenthetical proves the counter does not over-count
--     the way a naive LIKE '%(%)%' would (AC-6b / AC-9).
--   * no_plays_units == 3: PB_noplays + PP_noplays are boxscore units with zero
--     plays anywhere; PB_persp is a boxscore unit under perspective T whose only
--     plays live under perspective OPP.
--   * perspective_only_misses == 1: PB_persp (display-only breakdown of
--     no_plays_units; TN-5).
--   * self_games == 1: G_SELF has home_team_id == away_team_id (AC-6b).
--
-- Team T (gc_uuid 'TEAM_T') is the scouted/perspective team; OPP ('TEAM_OPP')
-- is the counter-party used for the perspective-only miss.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Season / teams / players
-- ---------------------------------------------------------------------------
INSERT INTO seasons (season_id, name, year) VALUES
    ('2026', 'Spring 2026 High School', 2026);

INSERT INTO teams (name, membership_type, gc_uuid) VALUES
    ('Team T',        'tracked', 'TEAM_T'),
    ('Opponent Side', 'tracked', 'TEAM_OPP');

INSERT INTO players (player_id, first_name, last_name) VALUES
    ('PB_agree',   'Bat',   'Agree'),
    ('PB_noplays', 'Bat',   'NoPlays'),
    ('PB_persp',   'Bat',   'Perspective'),
    ('PP_agree',   'Pitch', 'Agree'),
    ('PP_noplays', 'Pitch', 'NoPlays');

-- ---------------------------------------------------------------------------
-- Games.  G1 is a normal game (T home, OPP away); G_SELF is the self-game
-- (home == away) that drives self_games == 1.
-- ---------------------------------------------------------------------------
INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, status) VALUES
    ('G1', '2026', '2026-03-10',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP'), 'completed'),
    ('G_SELF', '2026', '2026-03-17',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'), 'completed');

-- ---------------------------------------------------------------------------
-- Boxscore lines (all perspective_team_id = team_id = T).
--   PB_agree:   ab3 h2 bb1 so1 hbp0  -- matches plays -> 100%
--   PB_noplays: ab2 h1 bb0 so1 hbp0  -- no plays anywhere -> no-plays unit
--   PB_persp:   ab2 h1 bb0 so0 hbp0  -- plays only under OPP -> perspective-only
--   PP_agree:   bf4 so1 bb1 h2 hbp0  -- matches plays -> 100%
--   PP_noplays: bf3 so1 bb0 h1 hbp0  -- no plays -> no-plays unit
-- ---------------------------------------------------------------------------
INSERT INTO player_game_batting
    (game_id, player_id, team_id, perspective_team_id, ab, h, bb, so, hbp) VALUES
    ('G1', 'PB_agree',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     3, 2, 1, 1, 0),
    ('G1', 'PB_noplays',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     2, 1, 0, 1, 0),
    ('G1', 'PB_persp',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     2, 1, 0, 0, 0);

INSERT INTO player_game_pitching
    (game_id, player_id, team_id, perspective_team_id, bf, so, bb, h, hbp) VALUES
    ('G1', 'PP_agree',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     4, 1, 1, 2, 0),
    ('G1', 'PP_noplays',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     3, 1, 0, 1, 0);

-- ---------------------------------------------------------------------------
-- Plays under perspective T, G1: PB_agree batting vs PP_agree pitching.
-- Four PAs -> Single, Double, Strikeout, Walk.  These reconstruct BOTH lines:
--   batter PB_agree: PA=4, AB=4-(Walk)=3, H=2, SO=1, BB=1, HBP=0
--   pitcher PP_agree: BF=4, H=2, SO=1, BB=1, HBP=0
-- ---------------------------------------------------------------------------
INSERT INTO plays
    (game_id, play_order, inning, half, season_id, batting_team_id,
     perspective_team_id, batter_id, pitcher_id, outcome) VALUES
    ('G1', 1, 1, 'bottom', '2026',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     'PB_agree', 'PP_agree', 'Single'),
    ('G1', 2, 1, 'bottom', '2026',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     'PB_agree', 'PP_agree', 'Double'),
    ('G1', 3, 1, 'bottom', '2026',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     'PB_agree', 'PP_agree', 'Strikeout'),
    ('G1', 4, 1, 'bottom', '2026',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_T'),
     'PB_agree', 'PP_agree', 'Walk');

-- Plays under perspective OPP, G1: PB_persp has plays ONLY here.  This makes the
-- perspective-T boxscore unit for PB_persp a no-plays unit AND a perspective-only
-- miss (the (game, player) DOES have plays under a different perspective).
INSERT INTO plays
    (game_id, play_order, inning, half, season_id, batting_team_id,
     perspective_team_id, batter_id, pitcher_id, outcome) VALUES
    ('G1', 1, 1, 'bottom', '2026',
     (SELECT id FROM teams WHERE gc_uuid='TEAM_T'), (SELECT id FROM teams WHERE gc_uuid='TEAM_OPP'),
     'PB_persp', NULL, 'Single');

-- ---------------------------------------------------------------------------
-- play_events attached to G1 / perspective T / play_order 1 (PB_agree's Single).
-- Two stranded annotated pitches (re-classify to 'pitch' -> counted) and one
-- NON-pitch parenthetical near-miss (base 'Wild pitch' is not a pitch template
-- -> stays 'other' -> NOT counted).  dropped_pitch_events == 2.
-- ---------------------------------------------------------------------------
INSERT INTO play_events (play_id, event_order, event_type, raw_template) VALUES
    ((SELECT id FROM plays WHERE game_id='G1' AND play_order=1
        AND perspective_team_id=(SELECT id FROM teams WHERE gc_uuid='TEAM_T')),
     1, 'other', 'Strike 1 looking (Curveball)'),
    ((SELECT id FROM plays WHERE game_id='G1' AND play_order=1
        AND perspective_team_id=(SELECT id FROM teams WHERE gc_uuid='TEAM_T')),
     2, 'other', 'Ball 1 (Fastball)'),
    ((SELECT id FROM plays WHERE game_id='G1' AND play_order=1
        AND perspective_team_id=(SELECT id FROM teams WHERE gc_uuid='TEAM_T')),
     3, 'other', 'Wild pitch (passed ball)');
