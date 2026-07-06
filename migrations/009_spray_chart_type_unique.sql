-- ===========================================================================
-- Migration 009: widen spray_charts uniqueness to include chart_type
-- ===========================================================================
-- Epic E-253 (story E-253-02), Technical Notes TN-3.
--
-- WHAT: Widens the spray_charts table-level UNIQUE constraint from
--   ``UNIQUE(event_gc_id, perspective_team_id)`` (001:417) to
--   ``UNIQUE(event_gc_id, perspective_team_id, chart_type)``.
--
-- WHY:  A single ball-in-play event produces TWO spray rows from one
--   perspective -- an ``offensive`` row (batter's hit location) and a
--   ``defensive`` row (fielding view) -- that share the same ``event_gc_id``
--   and ``perspective_team_id``. The narrow UNIQUE treated them as the same
--   row, so the loader's second ``INSERT OR IGNORE`` (the defensive row) was
--   silently ignored: 100% of defensive spray rows were dropped and miscounted
--   as idempotent skips. Adding ``chart_type`` to the key lets offense and
--   defense for one event coexist. Defensive coverage self-heals on the next
--   report generation (spray loads in-memory during generation -- no backfill).
--
-- MECHANISM: SQLite cannot ALTER a table-level UNIQUE in place, and a bare
--   ``CREATE UNIQUE INDEX`` does not help -- the narrow TABLE constraint fires
--   first regardless of any added index. This therefore requires the canonical
--   table rebuild: create a new table carrying the wider UNIQUE, copy every row
--   via ``INSERT INTO ... SELECT`` (explicit column list -- preserves ``id`` and
--   every value), drop the old table, rename the new one into place, and
--   recreate the two indexes (they are dropped with the old table).
--
-- FK SAFETY UNDER THE E-253-03 RUNNER: apply_migrations.py wraps every
--   migration body in ``PRAGMA foreign_keys=ON;\nBEGIN;\n{body}\n...\nCOMMIT;``
--   and runs it through a single executescript(). PRAGMA foreign_keys is a
--   no-op inside a transaction, so this rebuild CANNOT (and does not need to)
--   toggle it off. It is FK-safe under enforcement because:
--     * spray_charts has only OUTGOING FKs (game_id->games, player_id->players,
--       team_id/perspective_team_id->teams, pitcher_id->players). Every
--       existing row already satisfies them, so the INSERT ... SELECT re-check
--       passes.
--     * NO table has an incoming FK REFERENCES spray_charts, so DROP TABLE
--       needs no child teardown and the RENAME rewrites no external reference.
--   Verified: post-rebuild ``PRAGMA foreign_key_check`` reports zero rows.
--   Do NOT add BEGIN/COMMIT or PRAGMA statements here -- the runner owns them.
--
-- ROW PRESERVATION: widening a UNIQUE key can only make more combinations
--   distinct, never fewer, so no row that was valid under the narrow key
--   becomes a duplicate under the wider one; the old table already enforced the
--   narrow key, so every row copies across. Post-rebuild row count equals
--   pre-rebuild row count (E-253-02 AC-6).
--
-- IDEMPOTENCY: the migration runner applies each file exactly once (tracked by
--   filename in ``_migrations``), and the E-253-03 runner makes a failed apply
--   atomic (full rollback, no tracking row) -- so no half-rebuilt state can
--   linger. The leading ``DROP TABLE IF EXISTS spray_charts_new`` is a cheap
--   defensive guard against any pre-existing scratch table; re-running is
--   otherwise prevented by the runner, not by the SQL (same posture as 008).
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS spray_charts_new;

CREATE TABLE spray_charts_new (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id             TEXT REFERENCES games(game_id),
    player_id           TEXT REFERENCES players(player_id),
    team_id             INTEGER REFERENCES teams(id),
    perspective_team_id INTEGER NOT NULL REFERENCES teams(id),
    pitcher_id          TEXT REFERENCES players(player_id),  -- nullable
    chart_type          TEXT CHECK(chart_type IN ('offensive', 'defensive')),
    play_type           TEXT,
    play_result         TEXT,
    x                   REAL,
    y                   REAL,
    fielder_position    TEXT,
    error               INTEGER DEFAULT 0,
    event_gc_id         TEXT,
    created_at_ms       INTEGER,
    season_id           TEXT,
    UNIQUE(event_gc_id, perspective_team_id, chart_type)
);

INSERT INTO spray_charts_new (
    id, game_id, player_id, team_id, perspective_team_id, pitcher_id,
    chart_type, play_type, play_result, x, y, fielder_position, error,
    event_gc_id, created_at_ms, season_id
)
SELECT
    id, game_id, player_id, team_id, perspective_team_id, pitcher_id,
    chart_type, play_type, play_result, x, y, fielder_position, error,
    event_gc_id, created_at_ms, season_id
FROM spray_charts;

DROP TABLE spray_charts;

ALTER TABLE spray_charts_new RENAME TO spray_charts;

-- Recreate the two spray_charts indexes (dropped with the old table).
CREATE INDEX IF NOT EXISTS idx_spray_charts_player
    ON spray_charts(player_id, team_id, season_id);
CREATE INDEX IF NOT EXISTS idx_spray_charts_game
    ON spray_charts(game_id);
