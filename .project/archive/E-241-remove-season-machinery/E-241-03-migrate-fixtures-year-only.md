# E-241-03: Migrate the two shared fixtures to year-only slugs; delete the dead compound-season test class

## Epic
[E-241: Remove the cross-season machinery residue from the core](epic.md)

## Status
`DONE`

## Description
After this story is complete, the two named shared test fixtures and their tightly
coupled tests carry year-only `season_id` slugs instead of the compound
`2026-spring-hs` / `2025-summer-legion` taxonomy slugs, and the one test class that
asserts the compound-season concept itself is deleted. The golden JSON is unchanged
(byte-identical, no regen).

## Context
The compound-slug taxonomy this epic removes leaves a dead footprint in the test
fixtures. Migrating it removes the honesty gap (fixtures encoding a concept the code
no longer has). Scope is deliberately narrow: only the two named shared fixtures and
their verified consumer tests are migrated — the ~30 inline-season test files use
compound slugs as opaque partition-key literals and are out of scope (churn). The
two-season structure is KEPT as the cross-scope filter guard (distinct YEARS, so no
PK collision). One consumer tests the compound-season *concept* and must be deleted
rather than slug-swapped. This story has no file overlap with E-241-01 or E-241-02,
so it is independent. Per Technical Notes TN-5.

## Acceptance Criteria
- [ ] **AC-1**: `tests/fixtures/seed.sql` and `tests/fixtures/parity_consistent.sql`
  use year-only slugs — **every occurrence** of each compound slug is replaced
  (`2026-spring-hs` → `2026`, `2025-summer-legion` → `2025`), not just the `seasons`
  INSERT but every child row that carries the slug (`games`, `player_season_*`,
  `team_rosters`, `player_game_*`, and any comment). A partial replace leaves the
  fixture FK-inconsistent or breaks the parity scope-derivation (which reads
  `season_id` via the `games` join). Those seasons' `season_type` is set to `default`,
  keeping the two-season structure intact as the cross-scope guard. Per Technical
  Notes TN-5.
- [ ] **AC-2**: The fixtures' coupled tests are updated to the year-only slugs:
  `tests/test_schema_queries.py` (the `WHERE season_id = ...` query literals),
  `tests/test_report_golden.py` (`PRIMARY_SEASON_ID`), and
  `tests/test_aggregate_parity.py` (both slug literals).
- [ ] **AC-3**: The test class in `tests/test_schema_queries.py` that filters
  `season_type = 'spring-hs'` / `'summer-legion'` and asserts
  `season_id == '2026-spring-hs'` is DELETED (or rewritten to filter by `year`) —
  not mechanically slug-swapped, because it tests the dead compound-season concept.
  Per Technical Notes TN-5.
- [ ] **AC-4**: `tests/fixtures/golden/report_stats.json` is byte-identical (no
  regeneration) — the report output keys on the `season_year` integer, not the
  `season_id` slug, so the migration is invisible to rendered output.
- [ ] **AC-5**: `test_report_golden.py`, `test_schema_queries.py`, and
  `test_aggregate_parity.py` all pass.

## Technical Approach
Update the two fixture files and the three coupled test files per Technical Notes
TN-5. Verify (e.g. via grep) that no remaining consumer of the two named fixtures
expects a compound slug, and that the golden JSON is untouched. Delete the dead
compound-concept test class.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/fixtures/seed.sql`
- `tests/fixtures/parity_consistent.sql`
- `tests/test_schema_queries.py`
- `tests/test_report_golden.py`
- `tests/test_aggregate_parity.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Verified consumer sets (recon): `seed.sql` → `test_report_golden.py` +
`test_schema_queries.py`; `parity_consistent.sql` → `test_aggregate_parity.py`. No
file overlap with E-241-01/02, so this story can run in any order relative to them.
