-- Test scenario: Lincoln Varsity + JV vs 3 opponents, 10 games across 2 seasons
-- Seasons: 2026-spring-hs (primary), 2025-summer-legion (secondary)
--
-- Teams use INTEGER AUTOINCREMENT PKs (new E-100 schema).
-- Child tables reference teams via (SELECT id FROM teams WHERE gc_uuid = '...') subqueries.
-- gc_uuid values act as stable symbolic names: 'TEAM_VARSITY', 'TEAM_JV', etc.
--
-- Teams: TEAM_VARSITY (active, membership_type='member', classification='varsity')
--         TEAM_JV (active, membership_type='member', classification='jv')
--         TEAM_OPP_A (active, membership_type='tracked')
--         TEAM_OPP_B (inactive, is_active=0, membership_type='tracked')
--         TEAM_OPP_C (active, membership_type='tracked')
-- Player IDs: PLAYER_VARSITY_01..15, PLAYER_JV_01..15
-- Pitchers (Varsity): PLAYER_VARSITY_01, PLAYER_VARSITY_02, PLAYER_VARSITY_03
-- Pitchers (JV):      PLAYER_JV_01, PLAYER_JV_02
--
-- Key computed values for query assertions:
--   PLAYER_VARSITY_01: ab=20, h=7, bb=3, so=4
--     BA  = 7/20       = 0.350
--     OBP = (7+3)/(20+3) = 10/23 ≈ 0.43478
--     Krate = 4/20     = 0.200
--     home_ab=10, home_h=4  => home BA = 0.400
--     away_ab=10, away_h=3  => away BA = 0.300
--
--   Varsity season batting OBP order (descending) for AC-6:
--     PLAYER_VARSITY_02: ab=18, h=7, bb=4  OBP=(7+4)/(18+4)=11/22=0.500
--     PLAYER_VARSITY_01: ab=20, h=7, bb=3  OBP=(7+3)/(20+3)=10/23≈0.4348
--     PLAYER_VARSITY_03: ab=16, h=5, bb=2  OBP=(5+2)/(16+2)=7/18≈0.3889
--     PLAYER_VARSITY_04: ab=18, h=5, bb=2  OBP=(5+2)/(18+2)=7/20=0.350
--     PLAYER_VARSITY_05..15: ab=15, h=4, bb=1  OBP=(4+1)/(15+1)=5/16=0.3125
--
--   TEAM_VARSITY record in 2026-spring-hs (7 games):
--     Game 1: TEAM_VARSITY(home) 5 vs TEAM_OPP_A(away) 3  => W
--     Game 2: TEAM_OPP_A(home) 4 vs TEAM_VARSITY(away) 2  => L
--     Game 3: TEAM_VARSITY(home) 6 vs TEAM_OPP_C(away) 1  => W
--     Game 4: TEAM_OPP_C(home) 3 vs TEAM_VARSITY(away) 4  => W
--     Game 5: TEAM_VARSITY(home) 2 vs TEAM_OPP_A(away) 3  => L
--     Game 6: TEAM_OPP_A(home) 1 vs TEAM_VARSITY(away) 5  => W
--     Game 7: TEAM_VARSITY(home) 7 vs TEAM_OPP_C(away) 2  => W
--     W-L = 5-2
--
--   Varsity pitchers K/9 (so * 27.0 / ip_outs):
--     PLAYER_VARSITY_01: ip_outs=54, so=22  K/9 = 22*27/54 = 11.000
--     PLAYER_VARSITY_02: ip_outs=36, so=12  K/9 = 12*27/36 = 9.000
--     PLAYER_VARSITY_03: ip_outs=18, so=5   K/9 = 5*27/18  = 7.500
--
--   vs_lhb/vs_rhb splits for PLAYER_VARSITY_01 (pitcher):
--     vs_lhb: ab=24, h=5, hr=0, bb=3, so=11
--     vs_rhb: ab=32, h=9, hr=1, bb=4, so=11

-- ---------------------------------------------------------------------------
-- Seasons
-- ---------------------------------------------------------------------------
INSERT INTO seasons (season_id, name, season_type, year, start_date, end_date) VALUES
    ('2026-spring-hs',     'Spring 2026 High School', 'spring-hs',     2026, '2026-03-01', '2026-06-01'),
    ('2025-summer-legion', 'Summer 2025 Legion',      'summer-legion', 2025, '2025-06-15', '2025-08-15');

-- ---------------------------------------------------------------------------
-- Teams
-- gc_uuid is used as a stable symbolic name for FK subquery lookups.
-- TEAM_VARSITY / TEAM_JV are member teams; TEAM_OPP_* are tracked opponents.
-- ---------------------------------------------------------------------------
INSERT INTO teams (name, membership_type, classification, gc_uuid, source, is_active, last_synced) VALUES
    ('Lincoln Varsity',   'member',  'varsity', 'TEAM_VARSITY', 'gamechanger', 1, '2026-03-01 08:00:00'),
    ('Lincoln JV',        'member',  'jv',      'TEAM_JV',      'gamechanger', 1, NULL),
    ('Opponent A Eagles', 'tracked', NULL,      'TEAM_OPP_A',   'gamechanger', 1, NULL),
    ('Opponent B Tigers', 'tracked', NULL,      'TEAM_OPP_B',   'gamechanger', 0, NULL),
    ('Opponent C Rockets','tracked', NULL,      'TEAM_OPP_C',   'gamechanger', 1, NULL);

-- ---------------------------------------------------------------------------
-- Players -- Varsity (15)
-- ---------------------------------------------------------------------------
INSERT INTO players (player_id, first_name, last_name) VALUES
    ('PLAYER_VARSITY_01', 'Aaron',   'Adams'),
    ('PLAYER_VARSITY_02', 'Ben',     'Baker'),
    ('PLAYER_VARSITY_03', 'Carlos',  'Cruz'),
    ('PLAYER_VARSITY_04', 'Derek',   'Davis'),
    ('PLAYER_VARSITY_05', 'Evan',    'Evans'),
    ('PLAYER_VARSITY_06', 'Frank',   'Foster'),
    ('PLAYER_VARSITY_07', 'George',  'Green'),
    ('PLAYER_VARSITY_08', 'Henry',   'Hill'),
    ('PLAYER_VARSITY_09', 'Ivan',    'Ingram'),
    ('PLAYER_VARSITY_10', 'James',   'Jackson'),
    ('PLAYER_VARSITY_11', 'Kyle',    'King'),
    ('PLAYER_VARSITY_12', 'Liam',    'Lane'),
    ('PLAYER_VARSITY_13', 'Marcus',  'Moore'),
    ('PLAYER_VARSITY_14', 'Nathan',  'Nash'),
    ('PLAYER_VARSITY_15', 'Owen',    'Owens');

-- Players -- JV (15)
INSERT INTO players (player_id, first_name, last_name) VALUES
    ('PLAYER_JV_01', 'Peter',   'Park'),
    ('PLAYER_JV_02', 'Quinn',   'Quinn'),
    ('PLAYER_JV_03', 'Ryan',    'Reed'),
    ('PLAYER_JV_04', 'Sam',     'Shaw'),
    ('PLAYER_JV_05', 'Tom',     'Todd'),
    ('PLAYER_JV_06', 'Uriah',   'Upton'),
    ('PLAYER_JV_07', 'Victor',  'Vance'),
    ('PLAYER_JV_08', 'Will',    'Wade'),
    ('PLAYER_JV_09', 'Xavier',  'Xu'),
    ('PLAYER_JV_10', 'Yusuf',   'Young'),
    ('PLAYER_JV_11', 'Zane',    'Zell'),
    ('PLAYER_JV_12', 'Abel',    'Avery'),
    ('PLAYER_JV_13', 'Brady',   'Burns'),
    ('PLAYER_JV_14', 'Cole',    'Carr'),
    ('PLAYER_JV_15', 'Dean',    'Dunn');

-- ---------------------------------------------------------------------------
-- Team rosters -- Varsity (2026-spring-hs)
-- ---------------------------------------------------------------------------
INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number, position) VALUES
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_01', '2026-spring-hs', '1',  'P'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_02', '2026-spring-hs', '2',  'P/1B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_03', '2026-spring-hs', '3',  'P/OF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_04', '2026-spring-hs', '4',  'C'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_05', '2026-spring-hs', '5',  'SS'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_06', '2026-spring-hs', '6',  '2B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_07', '2026-spring-hs', '7',  '3B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_08', '2026-spring-hs', '8',  'CF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_09', '2026-spring-hs', '9',  'LF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_10', '2026-spring-hs', '10', 'RF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_11', '2026-spring-hs', '11', '1B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_12', '2026-spring-hs', '12', 'DH'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_13', '2026-spring-hs', '13', 'OF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_14', '2026-spring-hs', '14', 'OF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_15', '2026-spring-hs', '15', 'C/OF');

-- Team rosters -- JV (2026-spring-hs)
INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number, position) VALUES
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_01', '2026-spring-hs', '1',  'P'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_02', '2026-spring-hs', '2',  'P/SS'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_03', '2026-spring-hs', '3',  'C'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_04', '2026-spring-hs', '4',  '1B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_05', '2026-spring-hs', '5',  '2B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_06', '2026-spring-hs', '6',  '3B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_07', '2026-spring-hs', '7',  'SS'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_08', '2026-spring-hs', '8',  'CF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_09', '2026-spring-hs', '9',  'LF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_10', '2026-spring-hs', '10', 'RF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_11', '2026-spring-hs', '11', 'OF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_12', '2026-spring-hs', '12', 'DH'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_13', '2026-spring-hs', '13', 'OF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_14', '2026-spring-hs', '14', 'OF'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), 'PLAYER_JV_15', '2026-spring-hs', '15', '1B/OF');

-- Varsity also played summer-legion (same players, same team)
INSERT INTO team_rosters (team_id, player_id, season_id, jersey_number, position) VALUES
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_01', '2025-summer-legion', '1',  'P'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_02', '2025-summer-legion', '2',  'P/1B'),
    ((SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 'PLAYER_VARSITY_03', '2025-summer-legion', '3',  'P/OF');

-- ---------------------------------------------------------------------------
-- Games
-- 7 games in 2026-spring-hs (TEAM_VARSITY plays all 7)
-- 3 games in 2025-summer-legion (TEAM_VARSITY plays all 3)
--
-- TEAM_VARSITY record in 2026-spring-hs: W-L = 5-2 (see header for breakdown)
-- ---------------------------------------------------------------------------
INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status) VALUES
    -- 2026-spring-hs games (7 total)
    ('GAME_001', '2026-spring-hs', '2026-03-10',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_A'),
     5, 3, 'completed'),  -- V wins
    ('GAME_002', '2026-spring-hs', '2026-03-17',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_A'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     4, 2, 'completed'),  -- V loses
    ('GAME_003', '2026-spring-hs', '2026-03-24',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_C'),
     6, 1, 'completed'),  -- V wins
    ('GAME_004', '2026-spring-hs', '2026-03-31',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_C'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     3, 4, 'completed'),  -- V wins
    ('GAME_005', '2026-spring-hs', '2026-04-07',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_A'),
     2, 3, 'completed'),  -- V loses
    ('GAME_006', '2026-spring-hs', '2026-04-14',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_A'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     1, 5, 'completed'),  -- V wins
    ('GAME_007', '2026-spring-hs', '2026-04-21',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_C'),
     7, 2, 'completed'),  -- V wins
    -- 2025-summer-legion games (3 total)
    ('GAME_008', '2025-summer-legion', '2025-07-01',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_A'),
     4, 2, 'completed'),
    ('GAME_009', '2025-summer-legion', '2025-07-08',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_A'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     3, 6, 'completed'),
    ('GAME_010', '2025-summer-legion', '2025-07-15',
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'),
     (SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP_C'),
     5, 1, 'completed');

-- ---------------------------------------------------------------------------
-- Player game batting
-- Only including TEAM_VARSITY batters for brevity (sufficient for query tests).
-- All 15 Varsity players bat in each of the 7 spring-hs games.
-- Stats are chosen so the season rollup totals match exactly.
-- ---------------------------------------------------------------------------

-- GAME_001 (spring-hs, home)
INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('GAME_001', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_001', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 1, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_001', 'PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_001', 'PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_001', 'PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0);

-- GAME_002 (spring-hs, away)
INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('GAME_002', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_002', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 1, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_002', 'PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_002', 'PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_002', 'PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0);

-- GAME_003 (spring-hs, home)
INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('GAME_003', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 1, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 2, 1, 0, 0, 2, 1, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 1, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 1, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_003', 'PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0);

-- GAME_004 (spring-hs, away)
INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('GAME_004', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 1, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 1, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_004', 'PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0);

-- GAME_005 (spring-hs, home)
INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('GAME_005', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_005', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 1, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_005', 'PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 0, 0, 0, 0, 0, 1, 1, 0),
    ('GAME_005', 'PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_005', 'PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_005', 'PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_005', 'PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 1, 0);

-- GAME_006 (spring-hs, away)
INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('GAME_006', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 1, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 0, 0, 0, 0, 0, 0, 1, 0),
    ('GAME_006', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 1, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 0, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_006', 'PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 0, 0);

-- GAME_007 (spring-hs, home)
INSERT INTO player_game_batting (game_id, player_id, team_id, perspective_team_id, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('GAME_007', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 2, 1, 0, 0, 0, 1, 0, 1, 0),
    ('GAME_007', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 2, 0, 0, 0, 2, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 1, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 1, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0),
    ('GAME_007', 'PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 3, 1, 0, 0, 0, 0, 0, 0, 0);

-- ---------------------------------------------------------------------------
-- Player game pitching
-- TEAM_VARSITY pitchers: PLAYER_VARSITY_01 (ace), PLAYER_VARSITY_02 (starter),
--                        PLAYER_VARSITY_03 (spot starter/reliever)
-- Column order: game_id, player_id, team_id, ip_outs, h, r, er, bb, so
-- Note: hr excluded per AC-14 (not in boxscore pitching extras).
--       r = total runs allowed (set equal to er here; no unearned runs in test data).
-- ---------------------------------------------------------------------------

-- GAME_001 (home, V wins 5-3): PLAYER_VARSITY_01 starts (18 outs = 6 IP)
INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so) VALUES
    ('GAME_001', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 18, 5, 3, 3, 2, 7);

-- GAME_002 (away, V loses 4-2): PLAYER_VARSITY_02 starts (15 outs = 5 IP)
INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so) VALUES
    ('GAME_002', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 15, 6, 4, 4, 2, 4);

-- GAME_003 (home, V wins 6-1): PLAYER_VARSITY_01 starts CG (21 outs = 7 IP)
INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so) VALUES
    ('GAME_003', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 21, 3, 1, 1, 1, 8);

-- GAME_004 (away, V wins 4-3): PLAYER_VARSITY_02 starts (12 outs = 4 IP),
--           PLAYER_VARSITY_03 relieves (9 outs = 3 IP)
INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so) VALUES
    ('GAME_004', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 12, 5, 3, 3, 2, 5),
    ('GAME_004', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 9, 2, 0, 0, 0, 3);

-- GAME_005 (home, V loses 2-3): PLAYER_VARSITY_01 starts (15 outs = 5 IP)
INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so) VALUES
    ('GAME_005', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 15, 7, 3, 3, 3, 4);

-- GAME_006 (away, V wins 5-1): PLAYER_VARSITY_02 starts (21 outs = 7 IP)
INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so) VALUES
    ('GAME_006', 'PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 21, 4, 1, 1, 1, 5);

-- GAME_007 (home, V wins 7-2): PLAYER_VARSITY_03 starts (9 outs = 3 IP),
--           PLAYER_VARSITY_01 closes (15 outs = 5 IP)
INSERT INTO player_game_pitching (game_id, player_id, team_id, perspective_team_id, ip_outs, h, r, er, bb, so) VALUES
    ('GAME_007', 'PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 9, 3, 2, 2, 2, 2),
    ('GAME_007', 'PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), 15, 4, 3, 3, 1, 7);

-- ---------------------------------------------------------------------------
-- Player season batting (2026-spring-hs, all 15 Varsity players)
-- gp = games played (per season-stats API field name; replaces old 'games' column)
--
-- OBP order for TEAM_VARSITY in 2026-spring-hs (descending):
--   PLAYER_VARSITY_02: ab=18, h=7, bb=4  OBP=11/22=0.500     (rank 1)
--   PLAYER_VARSITY_01: ab=20, h=7, bb=3  OBP=10/23≈0.43478   (rank 2)
--   PLAYER_VARSITY_03: ab=16, h=5, bb=2  OBP=7/18≈0.38889    (rank 3)
--   PLAYER_VARSITY_04: ab=18, h=5, bb=2  OBP=7/20=0.350      (rank 4)
--   PLAYER_VARSITY_05..15: ab=15, h=4, bb=1  OBP=5/16=0.3125 (ranks 5-15, same OBP)
-- ---------------------------------------------------------------------------
INSERT INTO player_season_batting
    (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb,
     home_ab, home_h, home_hr, home_bb, home_so,
     away_ab, away_h, away_hr, away_bb, away_so,
     vs_lhp_ab, vs_lhp_h, vs_lhp_hr, vs_lhp_bb, vs_lhp_so,
     vs_rhp_ab, vs_rhp_h, vs_rhp_hr, vs_rhp_bb, vs_rhp_so) VALUES
    -- PLAYER_VARSITY_01: ab=20, h=7, bb=3, so=4
    --   home_ab=10, home_h=4; away_ab=10, away_h=3  (AC-8 split values)
    ('PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 20, 7, 1, 0, 0, 4, 3, 4, 1,
     10, 4, 0, 1, 2,   10, 3, 0, 2, 2,
     8, 3, 0, 1, 2,    12, 4, 0, 2, 2),
    -- PLAYER_VARSITY_02: ab=18, h=7, bb=4, so=3  OBP=11/22=0.500
    ('PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 18, 7, 2, 0, 0, 6, 4, 3, 0,
     10, 4, 0, 2, 1,    8, 3, 0, 2, 2,
     7, 3, 0, 1, 1,    11, 4, 0, 3, 2),
    -- PLAYER_VARSITY_03: ab=16, h=5, bb=2, so=1  OBP=7/18≈0.389
    ('PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 16, 5, 1, 0, 0, 3, 2, 1, 0,
     8, 3, 0, 1, 0,     8, 2, 0, 1, 1,
     6, 2, 0, 1, 0,    10, 3, 0, 1, 1),
    -- PLAYER_VARSITY_04: ab=18, h=5, bb=2, so=1  OBP=7/20=0.350
    ('PLAYER_VARSITY_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 18, 5, 0, 0, 0, 5, 2, 1, 0,
     9, 3, 0, 1, 0,     9, 2, 0, 1, 1,
     NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL),
    -- PLAYER_VARSITY_05..15: ab=15, h=4, bb=1, so=0  OBP=5/16=0.3125
    ('PLAYER_VARSITY_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 2, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 1, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 2, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 3, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 1, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 1, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 1, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 2, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 2, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 2, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL),
    ('PLAYER_VARSITY_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 7, 15, 4, 0, 0, 0, 1, 1, 0, 0,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL,   NULL, NULL, NULL, NULL, NULL);

-- JV season batting (2026-spring-hs) -- used for roster query completeness
INSERT INTO player_season_batting
    (player_id, team_id, season_id, gp, ab, h, doubles, triples, hr, rbi, bb, so, sb) VALUES
    ('PLAYER_JV_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 16, 5, 1, 0, 0, 3, 2, 3, 0),
    ('PLAYER_JV_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 15, 4, 0, 0, 0, 2, 1, 2, 0),
    ('PLAYER_JV_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 17, 5, 1, 0, 0, 2, 1, 2, 0),
    ('PLAYER_JV_04', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 18, 5, 0, 0, 0, 3, 2, 1, 0),
    ('PLAYER_JV_05', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 16, 4, 0, 0, 0, 2, 1, 2, 0),
    ('PLAYER_JV_06', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 15, 4, 0, 0, 0, 1, 1, 1, 0),
    ('PLAYER_JV_07', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 15, 4, 0, 0, 0, 2, 1, 1, 0),
    ('PLAYER_JV_08', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 15, 4, 0, 0, 0, 1, 1, 2, 0),
    ('PLAYER_JV_09', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 15, 3, 0, 0, 0, 1, 1, 2, 0),
    ('PLAYER_JV_10', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 14, 3, 0, 0, 0, 1, 1, 3, 0),
    ('PLAYER_JV_11', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 14, 3, 0, 0, 0, 1, 0, 2, 0),
    ('PLAYER_JV_12', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 14, 3, 0, 0, 0, 1, 0, 2, 0),
    ('PLAYER_JV_13', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 14, 3, 0, 0, 0, 1, 0, 3, 0),
    ('PLAYER_JV_14', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 13, 3, 0, 0, 0, 1, 0, 2, 0),
    ('PLAYER_JV_15', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_JV'), '2026-spring-hs', 5, 13, 2, 0, 0, 0, 0, 0, 3, 0);

-- ---------------------------------------------------------------------------
-- Player season pitching (2026-spring-hs)
-- Varsity pitchers only: PLAYER_VARSITY_01, _02, _03
-- gp_pitcher = games pitched (per season-stats API field name; replaces old 'games')
-- total_strikes = total strikes thrown (replaces old 'strikes' column name)
--
-- K/9 = so * 27.0 / ip_outs:
--   PLAYER_VARSITY_01: ip_outs=54, so=22  K/9 = 22*27/54 = 11.000  (rank 1)
--   PLAYER_VARSITY_02: ip_outs=36, so=12  K/9 = 12*27/36 = 9.000   (rank 2)
--   PLAYER_VARSITY_03: ip_outs=18, so=5   K/9 =  5*27/18 = 7.500   (rank 3)
--
-- vs_lhb/vs_rhb splits for PLAYER_VARSITY_01:
--   vs_lhb: ab=24, h=5, hr=0, bb=3, so=11
--   vs_rhb: ab=32, h=9, hr=1, bb=4, so=11
-- ---------------------------------------------------------------------------
INSERT INTO player_season_pitching
    (player_id, team_id, season_id, gp_pitcher, ip_outs, h, er, bb, so, hr,
     pitches, total_strikes,
     home_ip_outs, home_h, home_er, home_bb, home_so,
     away_ip_outs, away_h, away_er, away_bb, away_so,
     vs_lhb_ab, vs_lhb_h, vs_lhb_hr, vs_lhb_bb, vs_lhb_so,
     vs_rhb_ab, vs_rhb_h, vs_rhb_hr, vs_rhb_bb, vs_rhb_so) VALUES
    -- PLAYER_VARSITY_01: ace, K/9=11.0
    ('PLAYER_VARSITY_01', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 3, 54, 15, 7, 6, 22, 1,
     NULL, NULL,
     39, 8, 4, 3, 15,   15, 7, 3, 3, 7,
     24, 5, 0, 3, 11,   32, 9, 1, 4, 11),
    -- PLAYER_VARSITY_02: starter, K/9=9.0
    ('PLAYER_VARSITY_02', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 3, 36, 15, 8, 5, 12, 1,
     NULL, NULL,
     21, 5, 1, 1, 5,    15, 10, 7, 4, 7,
     NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL),
    -- PLAYER_VARSITY_03: spot starter/reliever, K/9=7.5
    ('PLAYER_VARSITY_03', (SELECT id FROM teams WHERE gc_uuid = 'TEAM_VARSITY'), '2026-spring-hs', 2, 18, 5, 2, 2, 5, 0,
     NULL, NULL,
     9, 3, 2, 2, 2,      9, 2, 0, 0, 3,
     NULL, NULL, NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL);
