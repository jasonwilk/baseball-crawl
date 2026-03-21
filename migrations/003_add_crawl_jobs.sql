-- Migration 003: Add crawl_jobs table
--
-- Creates a `crawl_jobs` table for tracking per-team crawl execution status,
-- timestamps, and outcomes for all UI-triggered syncs (both member-team crawls
-- and tracked-team scouting syncs triggered from the admin teams page).
--
-- This table provides:
--   - "Last synced" timestamps and success/failure indicators for the admin UI.
--   - A full history of every crawl invocation per team.
--
-- `teams.last_synced` remains the quick-lookup field for the most recent sync;
-- `crawl_jobs` provides the detailed history behind that summary.
--
-- sync_type values:
--   member_crawl   -- Full pipeline crawl for a member team (owned in GC).
--   scouting_crawl -- Opponent scouting crawl for a tracked team.
--
-- status values:
--   running    -- Crawl is currently in progress.
--   completed  -- Crawl finished successfully.
--   failed     -- Crawl encountered a fatal error; see error_message.

CREATE TABLE IF NOT EXISTS crawl_jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id       INTEGER NOT NULL REFERENCES teams(id),
    sync_type     TEXT    NOT NULL CHECK(sync_type IN ('member_crawl', 'scouting_crawl')),
    status        TEXT    NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    started_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT,
    error_message TEXT,
    games_crawled INTEGER
);

-- Index: look up the most recent job per team (for "Last synced" UI display).
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_team_id ON crawl_jobs(team_id, started_at DESC);
