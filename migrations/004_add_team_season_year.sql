-- Migration 004: Add season_year to teams
--
-- Adds a `season_year INTEGER` column to the `teams` table so each team
-- can be explicitly mapped to a season year instead of deriving it from
-- stat tables (which produced incorrect results for multi-season teams).
--
-- Known corrections (per TN-2): team 8 → 2025, team 78 → 2026.
-- All other teams start NULL; the self-healing pipeline fills them from
-- the API on the next sync.

ALTER TABLE teams ADD COLUMN season_year INTEGER;

-- Backfill known corrections (explicit, not stat-derived).
UPDATE teams SET season_year = 2025 WHERE id = 8;
UPDATE teams SET season_year = 2026 WHERE id = 78;
