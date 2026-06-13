# E-235-01: Migration 002 — `report_generation_runs` table

## Epic
[E-235: Report Run Records, Trust Signals & Quality Gates](../E-235-report-run-records/epic.md)

## Status
`TODO`

## Description
After this story is complete, the database has a `report_generation_runs` table — one wide row per report generation — that records per-stage status, per-stage counts, and report-level trust flags, FK-linked to `reports`. This is the storage layer every other story in the epic reads from or writes to.

## Context
Today `reports` records only a coarse `status` (`generating`/`ready`/`failed`) with no per-stage visibility (ROADMAP §2). The run record is the foundation for the admin list surfacing (story 06), the footer trust block (story 07), and the quality-gate flags (story 03). Per data-engineer's design, the telemetry lives in a NEW table mirroring the existing `scouting_runs` shape, NOT on the thin `reports` row. The full column set, the wide-row rationale, and the migration constraints are in **epic Technical Notes §TN-1**.

## Acceptance Criteria
- [ ] **AC-1**: Migration `migrations/002_*.sql` creates `report_generation_runs` as a single wide table (one row per generation) per the column set in §TN-1, with `report_id` FK → `reports(id)` ON DELETE CASCADE and a `UNIQUE(report_id)` index. Stage set and counts are named columns (no generic `count_a/count_b`).
- [ ] **AC-2**: The migration is idempotent — `CREATE TABLE IF NOT EXISTS` + `CREATE UNIQUE INDEX IF NOT EXISTS`; re-running it does not fail or duplicate (per `.claude/rules/migrations.md`).
- [ ] **AC-3**: `overall_status` and `identity_match_method` carry CHECK constraints per §TN-1 (`running`/`completed`/`failed` and `anchor`/`name_only`); `enrichment_status` accepts the canonical Tier-2 vocabulary (`success`/`unavailable-no-key`/`failed`) and is NOT a newly-invented enum. Booleans are `INTEGER 0/1`.
- [ ] **AC-4**: Applying migrations from a clean DB (`migrations/apply_migrations.py`) succeeds and the table is present with the documented columns; a test verifies the table exists and the column set + constraints match §TN-1.
- [ ] **AC-5**: `bb db reset` produces the new empty table alongside the existing schema (no seed rows), consistent with the empty-reset convention in `.claude/rules/data-model.md`.

## Technical Approach
Add `migrations/002_report_generation_runs.sql` following the `scouting_runs` table as the structural precedent. Final column names, types, nullability, and CHECK vocabularies are the data-engineer's call per §TN-1 — confirm the `reports.status` interaction with story 03's no-games terminal value is not constrained here (status is a free-text column on `reports`, untouched by this migration). Do not ALTER `reports`. Add or extend a migration/schema test that asserts the table and its constraints exist.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-235-02 (writes the run record), E-235-05 (delete-path cleanup); the table is transitively required by 06's admin-list join down the chain

## Files to Create or Modify
- `migrations/002_report_generation_runs.sql` (create)
- A migration/schema test (e.g. `tests/test_migrations.py` or the existing schema test) — create or extend to assert the table + constraints

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-235-02**: the `report_generation_runs` table the restructured generator writes per-stage status/counts to.
- **Produces for E-235-05**: the FK relationship (`report_id` ON DELETE CASCADE) the cleanup-mirror story wires into the report/team delete paths.
- **Produces for E-235-06**: the columns the admin list joins on (1:1 via `UNIQUE(report_id)`).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md) and migration conventions
- [ ] No regressions in existing tests

## Notes
Column set and constraints are specified in epic §TN-1. The wide-row-vs-child-table decision and its rationale are settled (wide row) — do not normalize into a per-stage child table.
