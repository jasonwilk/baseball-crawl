-- Migration 013: Fix stale season_ids for teams without program_id
--
-- E-197 changed season_id derivation to produce year-only values (e.g., "2026")
-- for teams where program_id IS NULL. Pre-existing rows still carry old suffixed
-- values (e.g., "2026-spring-hs"). This migration corrects all affected tables
-- to match the new derivation: CAST(COALESCE(season_year, strftime('%Y','now')) AS TEXT).
--
-- Scope: all teams where program_id IS NULL, dynamically identified (TN-5).
-- Teams with a program_id are not touched (their suffixed season_ids are correct).
--
-- Idempotent (TN-2): all UPDATEs/DELETEs scope on the old suffixed season_id
-- (contains a '-' character). After the first successful run, WHERE clauses
-- match zero rows -- safe to re-run.

-- Step 1: FK enforcement (executescript resets connection state per migrations.md)
PRAGMA foreign_keys=ON;

-- ---------------------------------------------------------------------------
-- Step 2: Create year-only season rows as FK prerequisites (AC-3)
-- One INSERT OR IGNORE per distinct year value among affected teams.
-- ---------------------------------------------------------------------------
INSERT OR IGNORE INTO seasons (season_id, name, season_type, year)
SELECT DISTINCT
    CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT),
    CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT),
    'default',
    COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER))
FROM teams t
WHERE t.program_id IS NULL;

-- ---------------------------------------------------------------------------
-- Step 3: Correct games (TN-1 item 2)
-- Only update games where BOTH teams lack a program_id. Games where at
-- least one team has a program_id were loaded by that team's loader with
-- the correct suffixed season_id and must not be changed.
-- ---------------------------------------------------------------------------
UPDATE games
SET season_id = (
    SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
    FROM teams t
    WHERE t.program_id IS NULL
      AND t.id = games.home_team_id
)
WHERE games.season_id LIKE '%-%'
  AND NOT EXISTS (
    SELECT 1 FROM teams t
    WHERE t.id = games.home_team_id AND t.program_id IS NOT NULL
  )
  AND NOT EXISTS (
    SELECT 1 FROM teams t
    WHERE t.id = games.away_team_id AND t.program_id IS NOT NULL
  );

-- ---------------------------------------------------------------------------
-- Step 4: Correct plays (TN-1 item 3)
-- plays has no team_id -- join through games to identify affected rows.
-- Only target games where BOTH teams lack a program_id (same scope as Step 3).
-- Run AFTER games are corrected so we can copy the corrected game season_id.
-- ---------------------------------------------------------------------------
UPDATE plays
SET season_id = (
    SELECT g.season_id FROM games g WHERE g.game_id = plays.game_id
)
WHERE plays.season_id LIKE '%-%'
  AND plays.game_id IN (
    SELECT g.game_id FROM games g
    WHERE NOT EXISTS (
      SELECT 1 FROM teams t
      WHERE t.id = g.home_team_id AND t.program_id IS NOT NULL
    )
    AND NOT EXISTS (
      SELECT 1 FROM teams t
      WHERE t.id = g.away_team_id AND t.program_id IS NOT NULL
    )
  );

-- ---------------------------------------------------------------------------
-- Step 5: Correct player_season_batting (TN-1 item 4, TN-3 dedup)
-- Composite UNIQUE(player_id, team_id, season_id) -- must dedup first.
-- ---------------------------------------------------------------------------

-- 5a: DELETE old-season_id rows where a year-only row already exists
DELETE FROM player_season_batting
WHERE season_id LIKE '%-%'
  AND team_id IN (SELECT id FROM teams WHERE program_id IS NULL)
  AND EXISTS (
    SELECT 1 FROM player_season_batting psb2
    WHERE psb2.player_id = player_season_batting.player_id
      AND psb2.team_id   = player_season_batting.team_id
      AND psb2.season_id = (
        SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
        FROM teams t WHERE t.id = player_season_batting.team_id
      )
  );

-- 5b: UPDATE remaining old-season_id rows
UPDATE player_season_batting
SET season_id = (
    SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
    FROM teams t WHERE t.id = player_season_batting.team_id
)
WHERE season_id LIKE '%-%'
  AND team_id IN (SELECT id FROM teams WHERE program_id IS NULL);

-- ---------------------------------------------------------------------------
-- Step 6: Correct player_season_pitching (TN-1 item 5, TN-3 dedup)
-- Composite UNIQUE(player_id, team_id, season_id) -- must dedup first.
-- ---------------------------------------------------------------------------

-- 6a: DELETE old-season_id rows where a year-only row already exists
DELETE FROM player_season_pitching
WHERE season_id LIKE '%-%'
  AND team_id IN (SELECT id FROM teams WHERE program_id IS NULL)
  AND EXISTS (
    SELECT 1 FROM player_season_pitching psp2
    WHERE psp2.player_id = player_season_pitching.player_id
      AND psp2.team_id   = player_season_pitching.team_id
      AND psp2.season_id = (
        SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
        FROM teams t WHERE t.id = player_season_pitching.team_id
      )
  );

-- 6b: UPDATE remaining old-season_id rows
UPDATE player_season_pitching
SET season_id = (
    SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
    FROM teams t WHERE t.id = player_season_pitching.team_id
)
WHERE season_id LIKE '%-%'
  AND team_id IN (SELECT id FROM teams WHERE program_id IS NULL);

-- ---------------------------------------------------------------------------
-- Step 7: Correct team_rosters (TN-1 item 6, TN-3 dedup)
-- PRIMARY KEY (team_id, player_id, season_id) -- must dedup first.
-- ---------------------------------------------------------------------------

-- 7a: DELETE old-season_id rows where a year-only row already exists
DELETE FROM team_rosters
WHERE season_id LIKE '%-%'
  AND team_id IN (SELECT id FROM teams WHERE program_id IS NULL)
  AND EXISTS (
    SELECT 1 FROM team_rosters tr2
    WHERE tr2.team_id   = team_rosters.team_id
      AND tr2.player_id = team_rosters.player_id
      AND tr2.season_id = (
        SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
        FROM teams t WHERE t.id = team_rosters.team_id
      )
  );

-- 7b: UPDATE remaining old-season_id rows
UPDATE team_rosters
SET season_id = (
    SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
    FROM teams t WHERE t.id = team_rosters.team_id
)
WHERE season_id LIKE '%-%'
  AND team_id IN (SELECT id FROM teams WHERE program_id IS NULL);

-- ---------------------------------------------------------------------------
-- Step 8: Correct spray_charts (TN-1 item 7)
-- season_id is nullable, no FK constraint. Simple UPDATE.
-- ---------------------------------------------------------------------------
UPDATE spray_charts
SET season_id = (
    SELECT CAST(COALESCE(t.season_year, CAST(strftime('%Y', 'now') AS INTEGER)) AS TEXT)
    FROM teams t WHERE t.id = spray_charts.team_id
)
WHERE season_id LIKE '%-%'
  AND team_id IN (SELECT id FROM teams WHERE program_id IS NULL);
