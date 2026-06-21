# E-241-02: Migration 006 — drop `report_generation_runs.season_fallback` + season_id fragmentation safety

## Epic
[E-241: Remove the cross-season machinery residue from the core](epic.md)

## Status
`DONE`

## Description
After this story is complete, migration 006 removes the now-unreferenced
`report_generation_runs.season_fallback` column and guarantees that no persisted
database can fragment a team's season into two partitions after the derivation
collapse. `tests/test_migrations.py` reflects the column's absence.

## Context
E-241-01 removes every code reference to `season_fallback` but leaves the column
physically present so its own staging boundary stays green. This story drops the
column. It is blocked by **E-241-01** because `apply_migrations` runs at startup and
any remaining read of the column would break the instant it disappeared — by the time
006 lands, nothing references it. It is ALSO blocked by **E-241-06** because the
migration's preferred no-op-default fragmentation safety is durable only once BOTH
compound-slug producers (loaders + scouting crawler) emit year-only, and the crawler
producer is collapsed in 06 — otherwise the next report run re-creates the compound
slug and re-fragments (per Technical Notes TN-7). The migration also addresses the
season_id fragmentation risk: `season_id` is an FK target and join/group key, so a
persisted DB still holding a compound `2026-spring-hs` slug while derivation now emits
`2026` would split that team's season and the single-season report query would
silently
miss half the data. Per Technical Notes TN-7.

## Acceptance Criteria
- [ ] **AC-1**: `migrations/006_*.sql` removes the `season_fallback` column from
  `report_generation_runs` (a direct `DROP COLUMN`; no table rebuild is required —
  the column has no index/FK/generated-column/view dependency). Per Technical Notes
  TN-7.
- [ ] **AC-2**: After migration 006, `report_generation_runs` has no
  `season_fallback` column, and applying the full migration chain on a fresh DB
  succeeds.
- [ ] **AC-3**: The migration guarantees no persisted DB fragments a season
  partition after the derivation collapse, per the mechanism in Technical Notes
  TN-7. The **no-op default** (DROP COLUMN only, no season_id rewrite) is the
  preferred mechanism — correct because live data is already year-only and E-241-06's
  crawler fix stops new compound slugs. A normalization is required ONLY if persisted
  compound `season_id` values are actually found; if so, it follows the
  insert-year-only-parent → repoint-all-7-FK-children (including
  `report_generation_runs.season_id_used`) → delete-old-parent mechanism, with
  detect-and-fail collision handling — NOT a plain `UPDATE` and NOT "FK-safe
  ordering" (no such ordering exists under `foreign_keys=ON`). Per Technical Notes
  TN-7.
- [ ] **AC-4**: `tests/test_migrations.py` asserts the post-006 state (column
  absent); the prior assertions that `season_fallback` exists and defaults to 0 are
  removed or replaced accordingly.
- [ ] **AC-5**: The full test suite passes with E-241-01 and this story applied.
- [ ] **AC-6**: `tests/test_report_golden.py` passes with the golden JSON
  un-regenerated, and `tests/test_aggregate_parity.py` passes — the in-suite
  zero-stat-change gate (`bb report verify-aggregates` needs `data/` and cannot run
  in-worktree). The column drop and any season_id normalization must not perturb stat
  computation. Per Technical Notes TN-3.

## Technical Approach
Author `migrations/006_*.sql` per Technical Notes TN-7. Confirm the migration
runner picks up 006 and that the existing `report_generation_runs` round-trip tests
in `tests/test_migrations.py` are updated to the post-drop schema. For the
fragmentation-safety mechanism, prefer the **no-op default** (DROP COLUMN only) —
it is correct because live data is already year-only and E-241-06's crawler fix
stops new compound slugs (TN-7). Add a season_id normalization ONLY if persisted
compound values are actually found, and if so follow the
insert-year-only-parent → repoint-all-7-FK-children → delete-old-parent mechanism
(detect-and-fail on collision) from TN-7 — a plain `UPDATE` is impossible under
`foreign_keys=ON`. Record the chosen mechanism and its reasoning in the migration
file's header comment.

## Dependencies
- **Blocked by**: E-241-01, E-241-06
- **Blocks**: E-241-05

## Files to Create or Modify
- `migrations/006_*.sql` (new — final name at implementer's discretion)
- `tests/test_migrations.py`

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Migration number 006 confirmed by glob (005 is the current highest:
`migrations/005_scheduled_report_runs.sql`). This story owns `test_migrations.py`
exclusively — E-241-01 must not touch it.
