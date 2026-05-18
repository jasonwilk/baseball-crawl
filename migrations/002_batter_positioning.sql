-- Migration 002: batter positioning (E-229 v2 schema)
-- Supersedes E-228 v1 in-place per epic E-229 TN-1 (branch-stack chain).
--
-- One row per (batter player, batter's team, season, perspective_team, fielding
-- position) on `batter_positioning`. The positioning engine (E-229-02) computes
-- a recommendation per opposing batter per covered fielding position
-- (LF, CF, RF, 3B, SS, 2B) and writes it here. The bundle assembler reads these
-- rows at render time. The engine refreshes rows via a delete-then-insert
-- within the (team_id, season_id, perspective_team_id) scope.
--
-- The new `team_position_aggregate` table stores the team-level alignment star
-- per (team_id, season_id, perspective_team_id, position): the engine's
-- aggregate centroid (`star_x`, `star_y`) plus BIP count and a low-confidence
-- flag. Per-batter rows on `batter_positioning` represent deviations from the
-- team-level star; the star itself lives on `team_position_aggregate`.
--
-- ARCHITECTURE (epic TN-13/TN-14):
--   Tier 1 (these tables): deterministic engine writes the call; reproducible
--     and auditable.
--   Tier 2 (optional, render-time only): LLM may produce a plain-English
--     rationale; never persisted; bundle assembler threads it in-memory only.
--
-- PERSPECTIVE PROVENANCE:
--   perspective_team_id records whose API pull produced the underlying spray
--   rows that fed the engine. It is part of both tables' primary keys so two
--   teams scouting the same opponent get independent recommendations without
--   collision (same invariant as spray_charts.perspective_team_id).
--
-- COORDINATE / DEVIATION CONVENTION (epic TN-15):
--   direction_deviation: signed ordinal step on the L-R axis. Negative = toward
--     LF, positive = toward RF. NULL when the batter has no L-R signal.
--   depth_deviation: signed ordinal step on the in-out axis. Negative = "in"
--     (toward home plate), positive = "deep" (toward CF wall). NULL when the
--     batter is below the depth-signal sample-size gate.
--   zone_id: A..H labels the eight zones around the team-aggregate star. NULL
--     when the batter shows no outlier zone (default alignment is fine).
--   The SVG render projection (`y_offset = -depth_dev * scale_y`) is a render
--     layer concern (TN-15); the engine stores raw signed deviations only.

CREATE TABLE IF NOT EXISTS batter_positioning (
    player_id            TEXT    NOT NULL REFERENCES players(player_id),
    team_id              INTEGER NOT NULL REFERENCES teams(id),
    season_id            TEXT    NOT NULL REFERENCES seasons(season_id),
    perspective_team_id  INTEGER NOT NULL REFERENCES teams(id),
    position             TEXT    NOT NULL CHECK (position IN ('LF','CF','RF','3B','SS','2B')),
    direction_deviation  INTEGER,
    depth_deviation      INTEGER,
    zone_id              TEXT    CHECK (zone_id IS NULL OR zone_id IN ('A','B','C','D','E','F','G','H')),
    is_thin              INTEGER NOT NULL DEFAULT 0,
    bip_count            INTEGER NOT NULL,
    hr_count             INTEGER NOT NULL DEFAULT 0,
    computed_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, team_id, season_id, perspective_team_id, position)
);

-- Supports the bundle-render read pattern: fetch all positioning rows for a
-- scouted opponent within a season from a given perspective. The PK leads with
-- player_id, so a separate index puts (team_id, season_id, perspective_team_id)
-- first for the scoped fetch.
CREATE INDEX IF NOT EXISTS idx_batter_positioning_lookup
    ON batter_positioning (team_id, season_id, perspective_team_id);

CREATE TABLE IF NOT EXISTS team_position_aggregate (
    team_id              INTEGER NOT NULL REFERENCES teams(id),
    season_id            TEXT    NOT NULL REFERENCES seasons(season_id),
    perspective_team_id  INTEGER NOT NULL REFERENCES teams(id),
    position             TEXT    NOT NULL CHECK (position IN ('LF','CF','RF','3B','SS','2B')),
    star_x               REAL    NOT NULL,
    star_y               REAL    NOT NULL,
    bip_count            INTEGER NOT NULL,
    is_low_confidence    INTEGER NOT NULL DEFAULT 0,
    computed_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, season_id, perspective_team_id, position)
);
-- No separate index: the PK leads with (team_id, season_id, perspective_team_id)
-- and serves the render-time per-position lookup natively.
