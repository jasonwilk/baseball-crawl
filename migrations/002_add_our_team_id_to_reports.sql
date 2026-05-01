-- ---------------------------------------------------------------------------
-- Migration 002: add our_team_id to reports for matchup analysis (E-228)
-- ---------------------------------------------------------------------------
-- Adds a nullable INTEGER FK to ``teams(id)``.  When NULL (the default for
-- existing rows and reports generated WITHOUT the matchup option), the
-- renderer hides the matchup section entirely; the report renders identically
-- to today's standalone scouting reports.  When populated, downstream stories
-- (E-228-12, E-228-14) build a "Game Plan" section comparing the LSB team's
-- stats to the report subject.
--
-- Path C per the epic Technical Notes -- additive opt-in.  No backfill
-- needed; existing rows simply have ``our_team_id IS NULL``.
--
-- SQLite ``ALTER TABLE ADD COLUMN`` is safe per
-- ``.claude/rules/migrations.md`` -- the migration runner tracks applied
-- files in ``_migrations`` so this migration runs exactly once.

ALTER TABLE reports ADD COLUMN our_team_id INTEGER REFERENCES teams(id);
