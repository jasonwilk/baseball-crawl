-- ===========================================================================
-- Migration 011: drop the stored season-aggregate tables
--   * player_season_batting   (whole table)
--   * player_season_pitching  (whole table)
-- ===========================================================================
-- Epic E-259 (story E-259-03), Technical Notes TN-3.
--
-- WHAT: Removes the two stored season-aggregate tables. Since the E-259
--   query-time cutover (E-259-01) the season line is derived at read time from
--   the per-game tables (``src.api.db.get_season_batting`` /
--   ``get_season_pitching``), and E-259-02 retired every writer, so these tables
--   are a pure derived cache with zero readers and zero writers.
--
-- WHY:  Retiring the tables retires the entire parity/footgun apparatus they
--   supported (E-259-04 deletes ``aggregate_parity.py`` / ``verify-aggregates``
--   / ``validate_plays_stats.py`` once nothing reads the tables). A frozen
--   archive is deliberately NOT built: the live DB has zero member rows (DE
--   survey: batting/pitching both 100% ``boxscore_only``), and a stale archive
--   is a data-trap dressed as safety. The DDL is recoverable verbatim from
--   ``001_initial_schema.sql`` if a recreate is ever needed.
--
-- REFUSE-ON-MEMBER-ROW PREFLIGHT (AC-2): the ONLY non-re-derivable data these
--   tables could hold is a member row (``stat_completeness IN
--   ('full','supplemented')``) -- those came straight from the season-stats API
--   and are NOT rebuildable from the per-game rows. If any such row is present
--   the DROP is REFUSED: a resurrected member row means a writer we believed
--   deleted has come back, and the correct response is to STOP and understand
--   that, not to silently destroy it. The preflight below RAISEs (naming the
--   offending table) before either DROP runs. Because plain ``RAISE`` is valid
--   only inside a trigger, it is implemented as two connection-local temp
--   triggers fired by a single sentinel INSERT: if either table holds a member
--   row, the matching trigger aborts the statement. The migration runner
--   (E-253, ``apply_migrations.apply_migration``) wraps the whole file in one
--   ``BEGIN``/``COMMIT`` and rolls back + re-raises on ANY ``sqlite3.Error``, so
--   a refusal (a) leaves BOTH tables intact and (b) records NO ``_migrations``
--   row -- a corrected DB can re-run the migration later (AC-2/AC-3).
--
-- LEAF STATUS (checked, not assumed): verified by grep across ``migrations/``
--   that NO other table declares ``REFERENCES player_season_batting`` /
--   ``REFERENCES player_season_pitching`` and that no ``CREATE VIEW`` /
--   ``CREATE TRIGGER`` reads either table -- so ``DROP TABLE`` cannot fail on a
--   dangling dependency (the one runtime failure mode for a table DROP). Their
--   own indexes (``idx_psb_*`` / ``idx_psp_*``, 001:658-661) are dropped
--   automatically with the tables.
--
-- LAYERED PATTERN (follows 006/008): ``001_initial_schema.sql``'s CREATE TABLE
--   DDL is intentionally left unchanged; this migration performs the DROPs. A
--   fresh DB runs 001 -> 011 and converges with a DB migrated up from earlier.
--
-- IDEMPOTENCY: the runner applies each file exactly once (tracked by filename in
--   ``_migrations``); re-running is prevented by the runner, not the SQL.
-- ---------------------------------------------------------------------------

-- Preflight sentinel: a single INSERT fires the member-row guard triggers.
CREATE TEMP TABLE _e259_drop_preflight (ok INTEGER);

CREATE TEMP TRIGGER _e259_refuse_batting_member
BEFORE INSERT ON _e259_drop_preflight
WHEN (SELECT COUNT(*) FROM player_season_batting
      WHERE stat_completeness IN ('full', 'supplemented')) > 0
BEGIN
    SELECT RAISE(ABORT,
        'E-259-03 REFUSED: player_season_batting holds member (full/supplemented) rows; DROP aborted to preserve non-re-derivable member data');
END;

CREATE TEMP TRIGGER _e259_refuse_pitching_member
BEFORE INSERT ON _e259_drop_preflight
WHEN (SELECT COUNT(*) FROM player_season_pitching
      WHERE stat_completeness IN ('full', 'supplemented')) > 0
BEGIN
    SELECT RAISE(ABORT,
        'E-259-03 REFUSED: player_season_pitching holds member (full/supplemented) rows; DROP aborted to preserve non-re-derivable member data');
END;

-- Fires the guards. Aborts the whole migration (runner rollback, no _migrations
-- row) if either table holds a member row; otherwise proceeds to the DROPs.
INSERT INTO _e259_drop_preflight (ok) VALUES (1);

DROP TRIGGER _e259_refuse_batting_member;
DROP TRIGGER _e259_refuse_pitching_member;
DROP TABLE _e259_drop_preflight;

DROP TABLE player_season_batting;
DROP TABLE player_season_pitching;
