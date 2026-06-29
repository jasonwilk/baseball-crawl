# E-245-01: Add `pitch_type` + `pitch_speed_mph` columns to `play_events` (migration 007)

## Epic
[E-245: High-Fidelity Play Ingestion](epic.md)

## Status
`DONE`

## Description
After this story is complete, the `play_events` table will carry two new nullable columns —
`pitch_type TEXT` and `pitch_speed_mph INTEGER` — ready to store the per-pitch type and velocity
that the parser will capture in E-245-02. This is the schema foundation; no parsing or population
happens here.

## Context
The plays endpoint emits pitch type and velocity as a trailing annotation on pitch templates (see
epic TN-2 and the endpoint doc in TN-1). The user decided to store both values while the parser is
being touched, consistent with the project's store-every-stat preference. The columns must exist
before the parser (E-245-02) can write them. Keeping the migration as its own story isolates the
schema change (data-engineer domain) from the parser change (software-engineer domain).

## Acceptance Criteria
- [ ] **AC-1**: Given the migrations directory, when the next sequential migration is added, then
      it is named `007_*.sql` (verified the highest existing number is 006 via `ls migrations/*.sql`)
      and follows `.claude/rules/migrations.md`.
- [ ] **AC-2**: Given the migration is applied, when the schema is inspected, then `play_events`
      has a nullable `pitch_type TEXT` column and a nullable `pitch_speed_mph INTEGER` column, with
      no CHECK constraint on `pitch_type` (per epic TN-4).
- [ ] **AC-3**: Given the migration has already been applied, when `apply_migrations.py` runs
      again, then it does not error or duplicate (additive `ALTER TABLE ADD COLUMN` is run exactly
      once via the `_migrations` tracking table, per `.claude/rules/migrations.md`).
- [ ] **AC-4**: Given a fresh `bb db reset`, when the schema is built, then existing `play_events`
      rows/inserts that do not set the new columns continue to work (columns default to NULL).

## Technical Approach
Add an additive migration that introduces the two nullable columns described in epic TN-4. SQLite
has no `ALTER TABLE ADD COLUMN IF NOT EXISTS`; idempotency comes from the migration runner's
`_migrations` tracking, not DDL guards (per `.claude/rules/migrations.md`).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-245-02

## Files to Create or Modify
- `migrations/007_play_events_pitch_columns.sql` (create; final name/number confirmed against `ls migrations/*.sql`)
- A schema/round-trip test under `tests/` covering AC-2 through AC-4 (e.g. extend an existing migrations or play_events schema test)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-245-02**: the `pitch_type` / `pitch_speed_mph` columns the parser and loader populate.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Next migration number is 007 per the live directory (`006_drop_season_fallback.sql` is highest) —
re-confirm by glob before authoring, per `.claude/rules/migrations.md`.
