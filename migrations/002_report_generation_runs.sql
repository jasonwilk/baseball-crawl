-- ===========================================================================
-- Migration 002: report_generation_runs
-- ===========================================================================
-- Epic E-235 (story E-235-01), Technical Notes TN-1.
--
-- WHAT: Adds a single wide telemetry table -- one row per standalone report
--       generation -- recording per-stage status, per-stage counts, and
--       report-level trust flags, FK-linked 1:1 to `reports`.
--
-- WHY:  Today `reports` carries only a coarse `status`
--       (generating/ready/failed) with no per-stage visibility. A degraded
--       report (half-loaded, spray-failed, zero-games) is indistinguishable
--       from a complete one -- tolerable when an operator watches, fatal for
--       Epic E's unattended morning-of-game scheduled runs. This run record
--       is the storage foundation the rest of E-235 reads from / writes to:
--       the generator restructure (02) writes it, the quality gates (03) set
--       its trust flags, the cleanup-mirror (05) cascades it, the admin list
--       (06) joins on it, and the footer trust block (07) is fed from it.
--
-- DESIGN (TN-1): one WIDE row per generation, NOT a per-stage child table.
--   The stage set is fixed (7 known stages) and the counts are heterogeneous
--   (games vs plays-games vs discrepancies), so a normalized
--   (run_id, stage, ...) child table would force generic count_a/count_b
--   columns (breaking the recognizable-column-name convention) and a 7xN
--   admin-list fan-out. A wide row gives a flat 1:1 join, one row per report.
--   Mirrors the existing `scouting_runs` shape rather than inventing a new
--   pattern. All trust flags live HERE -- `reports` is intentionally NOT
--   altered; it stays the thin artifact-identity row the public serve path
--   reads.
--
-- IDEMPOTENCY: pure CREATE TABLE IF NOT EXISTS + CREATE UNIQUE INDEX IF NOT
--   EXISTS. All telemetry lands on this new table, so the SQLite
--   "no ADD COLUMN IF NOT EXISTS" caveat never applies. The FK target
--   `reports(id)` already exists (migration 001).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS report_generation_runs (
    -- identity / lifecycle ---------------------------------------------------
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 1:1 with the report it describes; ON DELETE CASCADE so deleting a
    -- report removes its run record (cleanup-mirror invariant, story 05).
    report_id       INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    started_at      TEXT,
    completed_at    TEXT,
    -- Lifecycle of the generation as a whole. Created 'running'; finalized
    -- 'completed' or 'failed' at the end of the pipeline.
    overall_status  TEXT NOT NULL DEFAULT 'running'
                    CHECK(overall_status IN ('running', 'completed', 'failed')),

    -- per-stage status -------------------------------------------------------
    -- NULL means "this stage did not run". Per-stage vocabularies vary, so
    -- these intentionally carry NO CHECK constraint (TN-1, DE-3 affirm) --
    -- EXCEPT enrichment_status, which reuses the canonical Tier-2 vocabulary.
    crawl_status            TEXT,
    load_status             TEXT,
    gc_uuid_status          TEXT,
    spray_status            TEXT,
    plays_status            TEXT,
    reconciliation_status   TEXT,
    -- enrichment_status IS the Tier-2 status: reuse the canonical vocabulary
    -- established by E-233 (.claude/rules/architecture-subsystems.md, LLM
    -- package). NOT a newly-invented enum. NULL = enrichment did not run.
    enrichment_status       TEXT
                            CHECK(enrichment_status IS NULL OR enrichment_status IN (
                                'success', 'unavailable-no-key', 'failed'
                            )),

    -- per-stage counts (named, per-game distinct-game counts) ----------------
    -- M: distinct completed games on the fetched schedule (played to date).
    completed_games             INTEGER,
    -- N: distinct completed games we actually have stat data for
    --    (the _query_freshness count). N <= M makes the footer's N-of-M
    --    point self-evident. NOT load_result.loaded (that counts records).
    completed_games_with_data   INTEGER,
    spray_games                 INTEGER,
    plays_games_expected        INTEGER,
    plays_games_covered         INTEGER,
    discrepancies_found         INTEGER,
    discrepancies_corrected     INTEGER,

    -- trust flags ------------------------------------------------------------
    -- season actually used for this generation (nullable).
    season_id_used          TEXT REFERENCES seasons(season_id),
    -- 1 when derive_season_id_for_team() resolved via the current-year /
    -- year-only fallback rather than team metadata (silent-wrong-season risk).
    season_fallback         INTEGER NOT NULL DEFAULT 0,
    -- 'anchor'    : team matched/attached by gc_uuid or public_id (reliable).
    -- 'name_only' : matched by name+season only, no external-id anchor
    --               (lower trust -- the silent-wrong-team risk).
    -- NULL until determined (stashed at the ensure_team_row site, written when
    -- the run row is created -- TN-1 run-row-creation timing).
    identity_match_method   TEXT
                            CHECK(identity_match_method IS NULL OR identity_match_method IN (
                                'anchor', 'name_only'
                            )),

    -- failure ----------------------------------------------------------------
    error_stage     TEXT,
    error_message   TEXT
);

-- UNIQUE(report_id) triples as: the 1:1 enforcer, the idempotency key, and
-- the admin-list join index (story 06). Each generation mints a fresh
-- reports row/slug, so report_id never collides today. (If in-place
-- regeneration ever arrives, drop UNIQUE and add a run_number -- out of
-- scope here.)
CREATE UNIQUE INDEX IF NOT EXISTS idx_report_generation_runs_report_id
    ON report_generation_runs(report_id);
