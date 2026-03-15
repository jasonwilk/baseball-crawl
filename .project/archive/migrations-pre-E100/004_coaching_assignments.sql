-- Migration 004: Coaching assignments (E-003-02)
--
-- Purpose: Records the coaching relationship between a user (coach), a team,
-- and a season. This is a DOMAIN table ("Coach Smith is head coach of JV in
-- Spring 2026"), not an auth/access table.
--
-- Distinction from user_team_access (003_auth.sql):
--   - user_team_access controls what a user can SEE on the dashboard (auth layer)
--   - coaching_assignments records the coaching relationship (domain layer)
--   A coach may be assigned to a team here without dashboard access, and a
--   user may have dashboard access without a coaching assignment. The two
--   tables are maintained independently and serve different purposes.
--
-- Role values (convention-based, no CHECK constraint -- new roles can be added
-- without a migration):
--   'head_coach'  -- primary coach responsible for the team
--   'assistant'   -- default; assistant coach on the staff
--   'volunteer'   -- volunteer coach (unofficial / part-time role)
--
-- This migration depends on:
--   - 001_initial_schema.sql: teams(team_id) and seasons(season_id) must exist
--   - 003_auth.sql: users(user_id) must exist
-- Run order: 001 -> 003 -> 004
--
-- See E-003 for full schema rationale and design decisions.

-- ---------------------------------------------------------------------------
-- coaching_assignments
-- ---------------------------------------------------------------------------
-- Links a coaching staff member (user) to a team in a specific season.
-- A coach can hold different roles on different teams in the same season.
CREATE TABLE IF NOT EXISTS coaching_assignments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(user_id),
    team_id    TEXT    NOT NULL REFERENCES teams(team_id),
    season_id  TEXT    NOT NULL REFERENCES seasons(season_id),
    role       TEXT    NOT NULL DEFAULT 'assistant',  -- 'head_coach', 'assistant', 'volunteer'
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, team_id, season_id)
);

-- Index for looking up all assignments for a specific coach
CREATE INDEX IF NOT EXISTS idx_coaching_assignments_user
    ON coaching_assignments(user_id);

-- Index for looking up the coaching staff for a team in a season
CREATE INDEX IF NOT EXISTS idx_coaching_assignments_team_season
    ON coaching_assignments(team_id, season_id);
