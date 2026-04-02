-- Migration 011: Fix season_id for Lincoln Rebels 14U (team_id 126)
--
-- The Rebels 14U team was crawled under the HS config directory, producing
-- season_id='2026-spring-hs' in all DB rows. The correct season_id is
-- '2025-summer-usssa' (season_year=2025, program_type=usssa).
--
-- This migration corrects team 126 and any opponents scouted through it.
-- scouting_runs.season_id is NOT updated (file-discovery column per TN-1).
--
-- Safe to re-run: all UPDATEs scope on the OLD value in the WHERE clause,
-- so they are no-ops after the first successful run.

-- Step 1: FK enforcement (executescript resets connection state)
PRAGMA foreign_keys=ON;

-- Step 2: Create USSSA program and assign team 126
INSERT OR IGNORE INTO programs (program_id, name, program_type)
VALUES ('rebels-usssa', 'Lincoln Rebels', 'usssa');

UPDATE teams
SET program_id = 'rebels-usssa'
WHERE id = 126 AND program_id IS NULL;

-- Step 3: Create the target season row (FK prerequisite for UPDATEs)
INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)
VALUES ('2025-summer-usssa', '2025-summer-usssa', 'summer-usssa', 2025);

-- Step 4: Correct season_id in all affected tables
-- Affected teams: team 126 + any opponents linked via team_opponents

-- 4a: games
UPDATE games
SET season_id = '2025-summer-usssa'
WHERE season_id = '2026-spring-hs'
  AND (
    home_team_id IN (
      SELECT 126
      UNION
      SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126
    )
    OR away_team_id IN (
      SELECT 126
      UNION
      SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126
    )
  );

-- 4b: plays (run AFTER games UPDATE -- join through corrected games rows)
UPDATE plays
SET season_id = '2025-summer-usssa'
WHERE season_id = '2026-spring-hs'
  AND game_id IN (
    SELECT game_id FROM games WHERE season_id = '2025-summer-usssa'
  );

-- 4c: player_season_batting
UPDATE player_season_batting
SET season_id = '2025-summer-usssa'
WHERE season_id = '2026-spring-hs'
  AND team_id IN (
    SELECT 126
    UNION
    SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126
  );

-- 4d: player_season_pitching
UPDATE player_season_pitching
SET season_id = '2025-summer-usssa'
WHERE season_id = '2026-spring-hs'
  AND team_id IN (
    SELECT 126
    UNION
    SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126
  );

-- 4e: team_rosters
UPDATE team_rosters
SET season_id = '2025-summer-usssa'
WHERE season_id = '2026-spring-hs'
  AND team_id IN (
    SELECT 126
    UNION
    SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126
  );

-- 4f: spray_charts (season_id is nullable on this table)
UPDATE spray_charts
SET season_id = '2025-summer-usssa'
WHERE season_id = '2026-spring-hs'
  AND team_id IN (
    SELECT 126
    UNION
    SELECT opponent_team_id FROM team_opponents WHERE our_team_id = 126
  );
