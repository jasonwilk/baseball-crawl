-- Migration 006: opponent_links table (E-088-01)
--
-- Purpose: Creates the opponent_links table that bridges local GC opponent
-- registry entries to resolved canonical GameChanger team UUIDs. Supports
-- three resolution states:
--   - auto-resolved: resolution_method='auto', resolved_team_id and public_id both set
--   - manually linked: resolution_method='manual', public_id set, resolved_team_id NULL
--   - unlinked: resolved_team_id NULL, public_id NULL, resolution_method NULL
--
-- root_team_id is intentionally NOT a FK to teams. It is GC's local opponent
-- registry key (from GET /teams/{id}/opponents) -- not a canonical team UUID.
-- The canonical UUID is resolved_team_id (when resolved).
--
-- updated_at is NOT maintained by a trigger. Callers must set
--   updated_at = datetime('now') on every UPDATE explicitly.
--
-- This migration depends on:
--   - 001_initial_schema.sql: teams table must exist
-- Run order: 001 -> 003 -> 004 -> 005 -> 006
--
-- See E-088 for full schema rationale and design decisions.

-- ---------------------------------------------------------------------------
-- opponent_links table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS opponent_links (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    our_team_id         TEXT    NOT NULL REFERENCES teams(team_id),
    root_team_id        TEXT    NOT NULL,  -- GC's local opponent registry key, NOT a canonical team UUID
    opponent_name       TEXT    NOT NULL,
    resolved_team_id    TEXT    REFERENCES teams(team_id),
    public_id           TEXT,
    resolution_method   TEXT CHECK (resolution_method IN ('auto', 'manual') OR resolution_method IS NULL),
    resolved_at         TEXT,
    is_hidden           INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(our_team_id, root_team_id)
);

-- Partial index on resolved_team_id: covers scouting report lookups that
-- join opponent_links to teams via resolved_team_id. Partial index keeps
-- it small -- only rows that have been resolved are indexed.
CREATE INDEX IF NOT EXISTS idx_opponent_links_resolved
    ON opponent_links(resolved_team_id)
    WHERE resolved_team_id IS NOT NULL;

-- Partial index on public_id: covers public-API lookups (public game details,
-- public team profile) that start from a known public_id slug. Partial keeps
-- unresolved rows out of the index.
CREATE INDEX IF NOT EXISTS idx_opponent_links_public_id
    ON opponent_links(public_id)
    WHERE public_id IS NOT NULL;
