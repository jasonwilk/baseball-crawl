-- Migration 005: Add public_id to teams (E-042-01)
--
-- Purpose: Adds a nullable public_id column to the teams table, enabling teams
-- to be identified by their GameChanger public identifier (slug) in addition
-- to the existing team_id (UUID). Required for URL-based team onboarding via
-- the public GameChanger API.
--
-- The column is nullable because opponents discovered via authenticated endpoints
-- (schedule opponent_id, opponents progenitor_team_id) may not have a resolved
-- public_id until later. The unique partial index enforces uniqueness only for
-- non-NULL values, allowing multiple opponent rows without a public_id.
--
-- This migration depends on:
--   - 001_initial_schema.sql: teams table must exist
-- Run order: 001 -> 003 -> 004 -> 005
--
-- See E-042 for full schema rationale and design decisions.

-- ---------------------------------------------------------------------------
-- Add public_id column to teams
-- ---------------------------------------------------------------------------
-- public_id is the short alphanumeric slug used by the GameChanger public API
-- and web UI (e.g., "a1GFM9Ku0BbF"). Nullable to support opponents that have
-- not yet had their public profile resolved.
ALTER TABLE teams ADD COLUMN public_id TEXT;

-- Unique partial index: enforces uniqueness for non-NULL values while allowing
-- multiple rows with public_id = NULL (SQLite supports partial indexes since 3.8.0).
CREATE UNIQUE INDEX idx_teams_public_id ON teams(public_id) WHERE public_id IS NOT NULL;
