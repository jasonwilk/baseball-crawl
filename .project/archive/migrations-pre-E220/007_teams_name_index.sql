-- Migration 007: Add case-insensitive name+season_year index on teams
--
-- Supports both the dedup detection query in find_duplicate_teams() and the
-- name-based lookup step in ensure_team_row().

CREATE INDEX IF NOT EXISTS idx_teams_name_season_year
    ON teams(name COLLATE NOCASE, season_year);
