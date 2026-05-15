-- E-228-01: batter_positioning -- Tier 1 deterministic defensive positioning recommendation.
--
-- One row per (batter player, batter's team, season, perspective_team, fielding position).
-- The positioning engine (E-228-02) computes a recommendation per opposing batter per
-- covered fielding position (SS, 2B, 3B, LF, CF, RF) and writes it here. The report
-- bundle reads these rows at render time. The engine refreshes rows via a
-- delete-then-insert within the (team_id, season_id, perspective_team_id) scope
-- (epic E-228 TN-2 / TN-6).
--
-- ARCHITECTURE (epic TN-1):
--   Tier 1 (this table): deterministic engine decides alignment; reproducible, auditable.
--   Tier 2 (optional): LLM writes the plain-English rationale only; never touches the call.
--   The call sheet must be fully usable with the LLM layer disabled.
--
-- PERSPECTIVE PROVENANCE:
--   perspective_team_id records whose API pull produced the underlying spray rows that
--   fed the engine. It is part of the primary key so two teams scouting the same
--   opponent get independent recommendations without collision (same invariant as
--   spray_charts.perspective_team_id from 001_initial_schema.sql).
--
-- ABSOLUTE FIELD DIRECTION:
--   call_state / direction_shade values use absolute field direction ('LEFT'/'RIGHT',
--   'left'/'right'), NOT handedness-relative pull/oppo. Batter handedness is not
--   available on every data path E-228 uses, and absolute direction matches the
--   existing classify_field_zone() output. The configurable display vocabulary
--   (e.g. "shade left") is resolved at render time (epic TN-5); this table stores
--   the stable absolute enum keys.
--
-- DEVIATION COLUMNS (direction_deviation / depth_deviation):
--   Signed ordinal step buckets on the L-R and in-out axes respectively (epic TN-3
--   Stage A). These persist the finer-grained per-axis step magnitude that the
--   categorical call_state / direction_shade / depth_shade enums discard. The
--   render path consumes them; the categorical state is for the call sheet's
--   CALL column. They are INTEGER (not REAL) because the SVG-space delta they
--   quantize is anisotropic and unanchored -- continuous magnitudes would
--   over-promise precision the geometry does not have.
--
-- TEAM-STATE CALL DENORMALIZATION:
--   team_state_call is a per-batter determination (one value per batter) but is
--   written identically to all 6 of the batter's per-position rows. Same pattern
--   as is_thin. The render path reads it directly instead of re-deriving the
--   TN-4a MIXED-rule lattice from the per-position call_state values in SQL.

CREATE TABLE IF NOT EXISTS batter_positioning (
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id INTEGER NOT NULL REFERENCES teams(id),              -- batter's team (scouted opponent)
    season_id TEXT NOT NULL REFERENCES seasons(season_id),      -- season slug, e.g. '2026-spring-hs'
    perspective_team_id INTEGER NOT NULL REFERENCES teams(id),  -- whose API pull produced the spray rows
    position TEXT NOT NULL,             -- 'SS','2B','3B','LF','CF','RF'
    call_state TEXT NOT NULL,           -- this position's own call: 'TRUE','LEFT','LEFT_SHALLOW','LEFT_DEEP','RIGHT','RIGHT_SHALLOW','RIGHT_DEEP','MIXED'
    team_state_call TEXT NOT NULL,      -- the batter's team-state call (TN-4a): same 8-key enum as call_state. Per-batter determination denormalized onto all 6 of the batter's rows (same pattern as is_thin) -- never NULL, every batter has a call even if 'TRUE'. The render path reads this for the call sheet's CALL column instead of re-deriving the TN-4a MIXED-rule lattice in SQL.
    direction_shade TEXT,               -- 'left','center','right' (NULL when TRUE) -- absolute field direction, matches classify_field_zone() output
    depth_shade TEXT,                   -- 'in','normal','deep' (NULL below 25-BIP gate)
    bip_count INTEGER NOT NULL,
    hr_count INTEGER NOT NULL,          -- separate: over-the-fence HRs have NULL x/y
    is_thin INTEGER NOT NULL DEFAULT 0,
    zone_concentration REAL,
    direction_deviation INTEGER,        -- signed ordinal step bucket on the L-R axis (0 = on base, ±1 = slight shade, ±2 = significant shade); NULL when call_state='TRUE' (direction_shade NULL). Negative = toward LF, positive = toward RF (absolute orientation). Quantized from the SVG-space delta via the per-axis (x) # RECALIBRATE threshold ladder + BASE_POSITIONS defined in E-228-02 (TN-3 Stage A) in positioning.py.
    depth_deviation INTEGER,            -- signed ordinal step bucket on the in-out axis (0 = on base, ±1 = slight shade, ±2 = significant shade); NULL below the 25-BIP depth gate (depth_shade NULL). Negative = shallower, positive = deeper. Quantized from the SVG-space delta via the per-axis (y) # RECALIBRATE threshold ladder + BASE_POSITIONS defined in E-228-02 (TN-3 Stage A) in positioning.py.
    computed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, team_id, season_id, perspective_team_id, position)
);

-- Index supports the report-bundle read pattern: fetch all positioning rows for a
-- given scouted opponent in a given season from a given perspective. This is the
-- only known read pattern -- the report render fetches rows scoped to
-- (team_id, season_id, perspective_team_id), then groups in application code by
-- batter / position. The primary key prefix (player_id, team_id, season_id,
-- perspective_team_id) does not serve this query because the leading column is
-- player_id; this dedicated index puts team_id first so the scoped fetch is a
-- range scan rather than a full-table scan.
CREATE INDEX IF NOT EXISTS idx_batter_positioning_lookup
    ON batter_positioning (team_id, season_id, perspective_team_id);
