-- ===========================================================================
-- Migration 005: scheduled_report_runs (+ opponent_links revival)
-- ===========================================================================
-- Epic E-240 (story E-240-03), Technical Notes TN-6.
--
-- WHAT: Adds the `scheduled_report_runs` audit table -- one row per scheduled
--       opponent slot the morning-run (E-240-07) processes -- recording the
--       slot's `(team, opponent, date)` key, its resolution outcome, and (when
--       a report was attempted) its delivery status. NO new DDL for
--       `opponent_links`; this file documents its REVIVAL as the
--       `root_team_id -> public_id` mapping store (migrations/001 already gave
--       it the right shape).
--
-- WHY:  The morning run must record EVERY scheduled slot and its outcome --
--       including unresolved / no-GC-presence / deferred-placeholder slots that
--       produced NO report. The existing `report_generation_runs` (migration
--       002) cannot represent these: it is NOT NULL `report_id` +
--       UNIQUE(report_id), 1:1 with a PRODUCED report, and carries no
--       `(team, opponent, date)` key. A separate audit table is required (the
--       data-engineer finding pinned in TN-6). This is the data foundation the
--       resolution ladder (E-240-04), `map-opponent` (E-240-05), and the
--       morning-run orchestration (E-240-07) write to.
--
-- DESIGN (TN-6):
--   * `opponent_root_team_id` is the GC `root_team_id` REGISTRY namespace --
--     NOT a `gc_uuid`. It carries NO FK: it is an opaque GC token, not a
--     `teams(id)` / `teams.gc_uuid` reference. (Storing it in a `gc_uuid`
--     column is a documented namespace error -- CLAUDE.md "Opponent entry
--     duality".)
--   * `report_id` is FK `reports(id)` ON DELETE SET NULL -- the AUDIT-SURVIVAL
--     invariant. This is the DELIBERATE MIRROR-IMAGE of E-235's
--     `report_generation_runs.report_id` ON DELETE CASCADE: the per-generation
--     run row is 1:1 with a produced report and dies with it, but a SCHEDULED
--     run row is an AUDIT record that MUST OUTLIVE report cleanup/expiry. When
--     the report is deleted, its `report_id` is nulled, the audit row remains.
--     `report_slug` is a frozen-string fallback so the audit trail still names
--     the report after the FK is nulled. DO NOT copy the CASCADE pattern here.
--   * `resolution_outcome` CHECK -- the per-slot resolution result (TN-11):
--     `auto_resolved` (rungs a/c/prior-operator; a report was attempted),
--     `unresolved_mappable` (on GC, not auto-matched -> operator queue),
--     `no_gc_presence` (operator-declared via `map-opponent --no-presence`),
--     `deferred_placeholder` (TBD/Winner/Seed... re-polled near game time).
--   * `delivery_status` CHECK + NULLABLE (TN-11): non-NULL ONLY when generation
--     was attempted (an `auto_resolved` slot) -- `generated` / `no_games` /
--     `failed` / `skipped`. NULL means generation was NOT attempted, and
--     `resolution_outcome` carries the reason.
--   * IDEMPOTENCY KEY: `UNIQUE INDEX (own_team_id, opponent_root_team_id,
--     game_date)` so the morning run UPSERTs one row per scheduled slot and a
--     re-run never duplicates it. NULL FOOTGUN: SQLite treats NULLs as DISTINCT
--     in UNIQUE indexes, so a NULL in any of the three key columns silently
--     breaks idempotency. The LOADER (E-240-07) must guarantee a non-NULL key
--     on all three columns (fall back to the `opponent_id` token when
--     `opponent_root_team_id` would be NULL). That guarantee is E-240-07's job;
--     this migration only states the schema fact.
--
-- CASCADE MIRROR INVARIANT (.claude/rules/data-model.md): adding this table
--   requires the canonical team-deletion cascade
--   (`src/reports/generator.py::_delete_team_scoped_data`) to gain a
--   `DELETE FROM scheduled_report_runs WHERE own_team_id IN (...)` -- done in
--   THIS SAME story (E-240-03). The two cleanups are distinct: team deletion
--   REMOVES the audit rows (the slots belonged to a now-gone team), but report
--   deletion only NULLS `report_id` (the slot's audit value outlives the
--   report).
--
-- OPPONENT_LINKS REVIVAL (NO new DDL -- migrations/001 already has the shape):
--   `opponent_links` is REVIVED as the `root_team_id -> public_id` mapping
--   store. Its `UNIQUE(our_team_id, root_team_id)` key is LOCAL to the owning
--   team: an opponent is resolved ONCE PER team-opponent pairing (one real
--   opponent faced by several LSB teams needs one mapping per team). The three
--   states read from `public_id` + `resolution_method` ONLY (never
--   `resolved_team_id`):
--     * not-resolved        -- `public_id NULL AND resolution_method NULL`
--                              (the auto-ladder's rung-(d) pending row).
--     * resolved-positive   -- `public_id NOT NULL`, `resolution_method` in
--                              `progenitor` / `search` / `operator`.
--     * resolved-negative   -- `public_id NULL AND resolution_method='no_presence'`
--                              (operator-declared via `map-opponent
--                              --no-presence`; the auto-ladder NEVER writes this).
--   Writers: the auto-ladder (E-240-04) persists resolved-positive / not-resolved
--   rows; `map-opponent` (E-240-05) UPDATEs a pending row to resolved-positive,
--   or -- with `--no-presence` -- to resolved-negative. ALL writers set
--   `resolved_at` on a positive/negative resolution. `is_hidden` is left alone.
--   (The `.claude/rules/data-model.md` write-up of this revival is a closure
--   context-layer obligation -- TN-10 -- not part of this story.)
--
-- IDEMPOTENCY: pure CREATE TABLE / CREATE INDEX IF NOT EXISTS -- concatenation-
--   safe for `conftest.load_real_schema` (which globs + concatenates every
--   numbered migration). No ALTER, so the SQLite "no ADD COLUMN IF NOT EXISTS"
--   caveat never applies. The FK target `reports(id)` already exists
--   (migration 001). SQLite column defaults that call functions MUST be
--   parenthesized (a bare `DEFAULT datetime(...)` is a syntax error).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS scheduled_report_runs (
    -- identity --------------------------------------------------------------
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,

    -- scheduled-slot key (the idempotency triple) ---------------------------
    -- LOCAL date of the scheduled game (YYYY-MM-DD; derived by E-240-07 from
    -- the UTC start + timezone). Part of the UNIQUE key.
    game_date               TEXT NOT NULL,
    -- The LSB team whose schedule produced this slot. Part of the UNIQUE key.
    own_team_id             INTEGER NOT NULL REFERENCES teams(id),
    -- The opponent's GC `root_team_id` REGISTRY token (NOT a gc_uuid; NO FK --
    -- it is an opaque GC namespace value). Part of the UNIQUE key.
    opponent_root_team_id   TEXT NOT NULL,
    -- Free-text opponent name from the schedule's pregame_data (audit context).
    opponent_name           TEXT,

    -- resolution outcome (TN-11) -------------------------------------------
    -- The per-slot resolution result. CHECK pins the four-state vocabulary.
    resolution_outcome      TEXT NOT NULL
                            CHECK(resolution_outcome IN (
                                'auto_resolved',
                                'unresolved_mappable',
                                'no_gc_presence',
                                'deferred_placeholder'
                            )),
    -- The resolved opponent public_id (set only for an auto_resolved slot).
    resolved_public_id      TEXT,

    -- report linkage (AUDIT-SURVIVAL: ON DELETE SET NULL, NOT cascade) -------
    -- FK to the produced report. ON DELETE SET NULL so this AUDIT row OUTLIVES
    -- report cleanup/expiry (the deliberate mirror-image of E-235's CASCADE).
    report_id               INTEGER REFERENCES reports(id) ON DELETE SET NULL,
    -- Frozen-string fallback so the audit trail still names the report after
    -- `report_id` is nulled by the report delete.
    report_slug             TEXT,

    -- delivery status (TN-11; NULLABLE) -------------------------------------
    -- Non-NULL ONLY when generation was attempted (an auto_resolved slot).
    -- NULL = generation not attempted; `resolution_outcome` carries the reason.
    delivery_status         TEXT
                            CHECK(delivery_status IS NULL OR delivery_status IN (
                                'generated',
                                'no_games',
                                'failed',
                                'skipped'
                            )),
    -- Per-slot failure detail (the per-game try/except records here; TN-9).
    error_message           TEXT,

    -- timestamps ------------------------------------------------------------
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Idempotency key: one row per scheduled slot. The morning run UPSERTs on
-- conflict (ON CONFLICT(own_team_id, opponent_root_team_id, game_date)), so a
-- re-run updates the existing row rather than duplicating it. NULL FOOTGUN:
-- SQLite treats NULLs as DISTINCT in UNIQUE indexes, so the loader MUST
-- guarantee a non-NULL key on all three columns (E-240-07's responsibility).
CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduled_report_runs_slot
    ON scheduled_report_runs(own_team_id, opponent_root_team_id, game_date);
