-- Migration 008: Add gc_uuid to teams (E-097-02)
--
-- Purpose: Adds a nullable gc_uuid column to the teams table, enabling teams
-- to store their canonical GameChanger UUID separately from team_id. This
-- supports UUID opportunism: the scouting pipeline does NOT require UUIDs to
-- operate, but whenever a UUID is encountered in an API response (boxscore
-- response keys, opponent_links.resolved_team_id, progenitor_team_id chains),
-- it is saved to teams.gc_uuid as a write-through update.
--
-- Design rationale:
--   - Avoids a PK migration that would cascade through 9+ FK tables. The
--     teams.team_id PK stays as-is (may hold a UUID or a public_id slug
--     depending on how the team was first discovered). gc_uuid is a separate
--     column for opportunistic UUID storage.
--   - Partial unique index: enforces uniqueness for non-NULL values while
--     allowing multiple rows with gc_uuid = NULL. Same pattern as
--     idx_teams_public_id from migration 005.
--
-- Crawler write-through pattern:
--   UPDATE teams SET gc_uuid = ? WHERE team_id = ? AND gc_uuid IS NULL
--   (check for NULL first to avoid overwriting a known UUID with a different value)
--
-- ALTER TABLE ADD COLUMN is not idempotent at the DDL level in SQLite
-- (no IF NOT EXISTS syntax). This is safe because apply_migrations.py tracks
-- applied migrations in _migrations and runs each migration exactly once.
-- Precedent: migration 005 (ALTER TABLE teams ADD COLUMN public_id TEXT).
--
-- This migration depends on:
--   - 001_initial_schema.sql: teams table must exist
--   - 007_scouting_runs.sql: logical ordering (gc_uuid is used by the E-097 crawler)
-- Run order: 001 -> 003 -> 004 -> 005 -> 006 -> 007 -> 008
--
-- See E-097 for full schema rationale and design decisions.

-- ---------------------------------------------------------------------------
-- Add gc_uuid column to teams
-- ---------------------------------------------------------------------------
-- gc_uuid is the canonical GameChanger internal UUID for a team. Nullable because:
--   - Teams discovered via public_id slug may not have a resolved UUID at all.
--   - UUID is saved opportunistically when encountered; never required upfront.
-- The existing team_id PK is unchanged (can hold either a UUID or a slug).
ALTER TABLE teams ADD COLUMN gc_uuid TEXT;

-- Partial unique index: enforces uniqueness for non-NULL gc_uuid values while
-- allowing multiple rows with gc_uuid = NULL (SQLite partial index since 3.8.0).
-- Same pattern as idx_teams_public_id (migration 005).
CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_gc_uuid
    ON teams(gc_uuid)
    WHERE gc_uuid IS NOT NULL;
