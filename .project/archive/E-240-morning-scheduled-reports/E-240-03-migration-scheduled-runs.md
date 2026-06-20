# E-240-03: Migration 005 — `scheduled_report_runs` + Cascade Line; Revive `opponent_links`

## Epic
[E-240: Morning-of-Game Scheduled Reports](../E-240-morning-scheduled-reports/epic.md)

## Status
`DONE`

## Description
After this story is complete, the database has a new `scheduled_report_runs`
audit table (migration 005) recording every scheduled opponent slot and its
outcome, the canonical team-deletion cascade deletes its rows when a team is
removed, and the dormant `opponent_links` table is documented as the revived
`root_team_id → public_id` mapping store (no new DDL — it already has the right
shape). This is the data foundation the resolution ladder (E-240-04),
`map-opponent` (E-240-05), and the morning-run orchestration (E-240-07) write to.

## Context
Scheduler runs cannot reuse `report_generation_runs` — that table is NOT NULL
`report_id` + `UNIQUE(report_id)`, 1:1 with a PRODUCED report, and cannot
represent unresolved / no-presence / deferred slots or carry a
`(team, opponent, date)` key. A NEW table is required (data-engineer finding).
`opponent_links` (migrations/001) already has the exact mapping shape
(`our_team_id`, `root_team_id TEXT`, `opponent_name`, `resolved_team_id`,
`public_id`, `resolution_method`, `resolved_at`, `UNIQUE(our_team_id,
root_team_id)`) — it is revived as the mapping store with no schema change. The
table schema and constraints are specified in Technical Notes TN-6 (the
data-engineer's recommended schema). The cascade addition is governed by the
Cleanup-Detection Mirror Invariant (`.claude/rules/data-model.md`).

## Acceptance Criteria
- [ ] **AC-1**: A new `migrations/005_*.sql` creates the `scheduled_report_runs`
  table with the columns, CHECK constraints, FK behaviors, and UNIQUE index
  specified in Technical Notes TN-6 — including the `resolution_outcome` CHECK,
  the `delivery_status` CHECK (`generated`/`no_games`/`failed`/`skipped`, NULLABLE
  per TN-11), `report_id` FK **ON DELETE SET NULL** (not cascade), and the
  `UNIQUE INDEX (own_team_id, opponent_root_team_id, game_date)`.
- [ ] **AC-2**: The migration is idempotent and concatenation-safe per
  `.claude/rules/migrations.md` (`CREATE TABLE/INDEX IF NOT EXISTS`,
  parenthesized `datetime()` defaults) and loads cleanly via
  `conftest.load_real_schema`.
- [ ] **AC-3**: The canonical team-deletion cascade in
  `src/reports/generator.py` (the `_delete_team_scoped_data` DELETE set) gains a
  `DELETE FROM scheduled_report_runs WHERE own_team_id IN (...)` in this same
  story, per the Cleanup-Detection Mirror Invariant and Technical Notes TN-6.
- [ ] **AC-4**: The `opponent_links` revival convention (its role as the
  `root_team_id → public_id` mapping store, the three `resolution_method` states,
  the resolve-once per-owning-team `UNIQUE(our_team_id, root_team_id)` key, and
  that writers set `resolved_at` on a positive/negative resolution) is documented
  in a code/migration doc-comment per Technical Notes TN-6. No DDL change to
  `opponent_links`; `is_hidden` is left alone.
- [ ] **AC-5**: Tests verify the new table's schema (columns, both CHECK value
  sets, UNIQUE index) and that the team-deletion cascade deletes
  `scheduled_report_runs` rows on team deletion. Schema tests follow
  Test-Validates-Spec against the migration file.
- [ ] **AC-6**: A test asserts the AUDIT-SURVIVAL invariant (Technical Notes
  TN-6): a `scheduled_report_runs` row SURVIVES report deletion (`_delete_report`)
  with its `report_id` set to NULL (ON DELETE SET NULL) — it is NOT cascade-deleted
  with the report. This is the deliberate mirror-image of E-235's "run row gone
  after report delete" and guards against an implementer copying the CASCADE
  pattern.
- [ ] **AC-7**: Epic A golden stat tables and `bb report verify-aggregates`
  parity are unchanged — the cascade addition is additive cleanup and touches no
  stat computation. Per Technical Notes TN-1.

## Technical Approach
Add the migration as the next sequential number — confirm it is `005` by
`ls migrations/*.sql` (do not trust a remembered number). Model the table on the
schema in Technical Notes TN-6; mirror the existing migration files' header-comment
and idempotency conventions (002–004 are the local reference). Add the cascade
DELETE alongside the other team-scoped deletes in the canonical deletion helper
(locate it via `.claude/rules/data-model.md`'s Cleanup-Detection Mirror Invariant
reference; do not duplicate cleanup logic elsewhere). The NULL-distinct UNIQUE
footgun (TN-6) is a schema fact noted here; the loader's non-NULL-key guarantee
is E-240-07's responsibility.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-240-04 (writes `opponent_links` + reads namespaces),
  E-240-05 (writes `opponent_links`), E-240-07 (writes `scheduled_report_runs`)

## Files to Create or Modify
- `migrations/005_scheduled_report_runs.sql` — new migration (scheduled_report_runs table + opponent_links revival doc-comment); confirm `005` is next by `ls migrations/*.sql`
- `src/reports/generator.py` — add `scheduled_report_runs` to the team-deletion cascade DELETE set (`_delete_team_scoped_data`)
- `tests/test_schema.py` and/or `tests/test_migrations.py` — schema assertions (columns, both CHECK sets, UNIQUE index)
- `tests/test_admin_reports.py` — the report-delete audit-survival test (AC-6: row survives `_delete_report` with `report_id` nulled); SE/DE may relocate to the existing team-deletion-cascade test file if that is where the cascade tests live

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-240-04 / E-240-05**: the `opponent_links` mapping store and
  the documented three resolution states.
- **Produces for E-240-07**: the `scheduled_report_runs` table + idempotency
  UNIQUE key the orchestration upserts per scheduled slot.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
`.claude/rules/data-model.md` documentation of the new table + revival + NULL
footgun is a closure context-layer obligation (claude-architect, TN-10), NOT
part of this story — this story documents the revival in a code/migration
comment only (data-model.md is a context-layer file routed to claude-architect).
