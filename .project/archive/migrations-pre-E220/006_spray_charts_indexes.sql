-- E-158-01: Add idempotency key, timestamp, season columns, and query indexes
-- to spray_charts.
--
-- The spray_charts table was defined in 001_initial_schema.sql but is unpopulated,
-- so ALTER TABLE ADD COLUMN is safe with no backfill needed.
--
-- ALTER TABLE ADD COLUMN does not support IF NOT EXISTS in SQLite, but this is
-- safe: apply_migrations.py tracks applied migrations in _migrations and runs
-- each file exactly once.
--
-- event_gc_id: GC UUID per spray event (TN-2). UNIQUE index enables INSERT OR
--   IGNORE idempotency in the loader (TN-6).
-- created_at_ms: API createdAt as Unix milliseconds INTEGER (TN-2).
-- season_id: full season slug from the file path, e.g., '2026-spring-hs'
--   (TN-11, fresh-start philosophy). Enables per-season filtering.

ALTER TABLE spray_charts ADD COLUMN event_gc_id    TEXT;
ALTER TABLE spray_charts ADD COLUMN created_at_ms  INTEGER;
ALTER TABLE spray_charts ADD COLUMN season_id      TEXT;

-- UNIQUE index on event_gc_id: idempotency key for INSERT OR IGNORE (TN-6).
CREATE UNIQUE INDEX IF NOT EXISTS idx_spray_charts_event_gc_id
    ON spray_charts(event_gc_id);

-- Composite index: per-player per-team per-season spray chart lookup.
-- Covers the primary dashboard query: fetch a player's BIP for a given team+season.
CREATE INDEX IF NOT EXISTS idx_spray_charts_player
    ON spray_charts(player_id, team_id, season_id);

-- Index on game_id: look up all spray events for a specific game.
CREATE INDEX IF NOT EXISTS idx_spray_charts_game
    ON spray_charts(game_id);
