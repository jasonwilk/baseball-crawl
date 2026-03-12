-- Migration 007: scouting_runs table (E-097-02)
--
-- Purpose: Creates the scouting_runs table that tracks when each opponent was
-- last scouted, what data was collected, and whether the run succeeded.
-- This is a crawl-metadata table (NOT a data table) -- it tracks the scouting
-- process, not the scouted data itself. Intentionally separate from
-- teams.last_synced, which tracks own-team crawl cycles.
--
-- Key design decisions:
--   - UNIQUE(team_id, season_id, run_type) prevents duplicate concurrent runs.
--     The crawler uses ON CONFLICT(team_id, season_id, run_type) DO UPDATE to
--     update status/counts/last_checked on re-runs while preserving first_fetched.
--     Do NOT use INSERT OR REPLACE -- it deletes-and-reinserts, losing first_fetched.
--   - first_fetched: set on first insert via DEFAULT, NEVER updated afterward.
--     Records when we first scouted this opponent for a given season/run_type.
--   - last_checked: set to same DEFAULT on first insert, updated by the crawler
--     on every re-run. Records how stale our data is.
--   - Season rows are created dynamically by the crawler/loader at runtime
--     (following the _ensure_season_row() pattern in game_loader.py).
--     This migration does NOT seed any season rows.
--
-- This migration depends on:
--   - 001_initial_schema.sql: teams and seasons tables must exist
-- Run order: 001 -> 003 -> 004 -> 005 -> 006 -> 007
--
-- See E-097 for full schema rationale and design decisions.

-- ---------------------------------------------------------------------------
-- scouting_runs table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scouting_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The opponent team being scouted (FK to teams)
    team_id         TEXT    NOT NULL REFERENCES teams(team_id),
    -- The season context for this scouting run (FK to seasons)
    -- Opponent season_id follows the same slug convention, e.g. '2025-spring-hs'.
    -- Created dynamically by the crawler via _ensure_season_row() if not yet present.
    season_id       TEXT    NOT NULL REFERENCES seasons(season_id),
    -- What data was collected: 'roster', 'boxscores', or 'full' (roster + boxscores)
    run_type        TEXT    NOT NULL,
    -- Run lifecycle
    started_at      TEXT    NOT NULL,                  -- ISO 8601 UTC
    completed_at    TEXT,                              -- NULL while running or if failed
    status          TEXT    NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'completed', 'failed')),
    -- Collection counts (nullable -- populated as data is discovered during the run)
    games_found     INTEGER,
    games_crawled   INTEGER,
    players_found   INTEGER,
    -- Error capture (NULL unless status = 'failed')
    error_message   TEXT,
    -- Fetch timestamps for re-fetch support (E-097 fetch timestamp pattern).
    -- first_fetched: set on INSERT, NEVER updated. Compare with last_checked to
    -- determine if a scouting result has been re-verified since original crawl.
    first_fetched   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    -- last_checked: updated by the crawler on every re-run of the same run_type.
    last_checked    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    -- Prevent duplicate concurrent runs for the same opponent/season/run_type.
    -- Crawler upsert pattern:
    --   INSERT INTO scouting_runs (...) VALUES (...)
    --   ON CONFLICT(team_id, season_id, run_type) DO UPDATE SET
    --     last_checked = excluded.last_checked,
    --     started_at   = excluded.started_at,
    --     status       = excluded.status,
    --     games_found  = excluded.games_found,
    --     games_crawled = excluded.games_crawled,
    --     players_found = excluded.players_found,
    --     error_message = excluded.error_message
    --   -- NOTE: first_fetched is NOT in the DO UPDATE list (preserves original timestamp)
    UNIQUE(team_id, season_id, run_type)
);

-- Index on (team_id, season_id) for efficient "when was this opponent last scouted?"
-- lookups. Primary query pattern:
--   SELECT * FROM scouting_runs
--   WHERE team_id = ? AND season_id = ?
--   ORDER BY last_checked DESC
CREATE INDEX IF NOT EXISTS idx_scouting_runs_team_season
    ON scouting_runs(team_id, season_id);
