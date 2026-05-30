# E-228-01: Make `bb db reset` Produce an Empty Schema (Remove Dev Seed)

## Epic
[E-228: Make `bb db reset` Produce a Useful Dev Environment](epic.md)

## Status
`DONE`

## Description
After this story is complete, `bb db reset` will produce a database containing only the migrated schema and the migration's `programs` bootstrap row -- no fake demo teams, games, players, or stats. The dev seed file and its now-dead loading code are removed, the reset CLI output accurately reflects an empty schema, and the test suite asserts the empty-reset outcome.

## Context
The reset currently loads `data/seeds/seed_dev.sql` (310 rows of fabricated demo data) as its final step. The operator re-crawls real data after a reset, so the fake rows are noise. DE confirmed there is nothing in the seed worth preserving: the only legitimate bootstrap row (`programs` = `'lsb-hs'`) comes from migration 001, not the seed. This story removes the seed and the seed-loading step entirely (per Technical Notes TN-2), making the empty schema the default reset outcome. The bulk of the work is updating the three test files that currently assert the seeded outcome (per Technical Notes TN-7).

## Acceptance Criteria
- [ ] **AC-1**: Given a fresh checkout, when `bb db reset` (or `reset_database()`) runs, then every user data table has zero rows while the schema and the `programs` = `'lsb-hs'` bootstrap row exist, per Technical Notes TN-1 (which enumerates the exact tables the inverse assertion must check).
- [ ] **AC-2**: Given the reset completes, when the CLI prints its result, then the output communicates an empty schema and does NOT imply seeded rows were loaded, per Technical Notes TN-3.
- [ ] **AC-3**: Given this story is complete, then `data/seeds/seed_dev.sql`, the `load_seed()` function and `_SEED_FILE` constant in `src/db/reset.py`, and `scripts/seed_dev.py` are removed; `scripts/reset_dev_db.py` still runs and resets the DB, per Technical Notes TN-2.
- [ ] **AC-4**: Given the production guard sequencing in the CLI, when `reset` runs, then `check_production_guard` still fires before the confirmation prompt and the guard behavior is unchanged.
- [ ] **AC-5**: Given the seed-loading step is gone, when the reset code is read, then the dead `FileNotFoundError`/"Seed file error" handling and stale "seed"/"rows inserted" messaging are removed and the `reset_database()` docstring is corrected, across `src/cli/db.py`, `src/db/reset.py`, AND `scripts/reset_dev_db.py`, per Technical Notes TN-9.
- [ ] **AC-6**: Given the test suite, when it runs, then `tests/test_seed.py`, `tests/test_cli_db.py`, and `tests/test_db_reset_guards.py` are updated per Technical Notes TN-7 (including the collection-time import fallout and the `load_seed` patch/seed-not-found cases), and the full suite passes with no regressions.

## Technical Approach
Remove the seed-loading step from `reset_database()` in `src/db/reset.py` and adjust the return shape per Technical Notes TN-3 (DE's low-churn default is keeping the `(int, int)` tuple as `(table_count, 0)`). Delete the seed file, the dead loading code, and `scripts/seed_dev.py`. Reword the CLI output and remove the now-dead seed-error handling in `src/cli/db.py`, apply the same messaging cleanup to the `scripts/reset_dev_db.py` wrapper, and update the `reset_database()` docstring per Technical Notes TN-9. Update the three affected test files per Technical Notes TN-7 -- this is the main work surface, and it includes collection-time import fallout and `patch()` targets, not just assertions. Do NOT edit migration 001 or the `programs` bootstrap row (Technical Notes TN-1). Do NOT add a `--seed` flag or replacement seed (Technical Notes TN-2). Do NOT edit documentation files -- doc updates are handled by the closure doc-assessment gate (Technical Notes TN-8).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/db/reset.py` -- remove `load_seed()` call, `load_seed()`, and `_SEED_FILE`; adjust return shape; update `reset_database()` docstring per Technical Notes TN-9
- `src/cli/db.py` -- reword reset output to reflect empty schema; remove the now-dead `FileNotFoundError`/"Seed file error" handler per Technical Notes TN-9
- `scripts/reset_dev_db.py` -- clean stale seed/"rows inserted" messaging and remove the dead `FileNotFoundError` handler per Technical Notes TN-9 (the script stays in service per TN-2)
- `data/seeds/seed_dev.sql` -- delete
- `scripts/seed_dev.py` -- delete (now dead)
- `tests/test_seed.py` -- remove the `load_seed`/`_SEED_FILE` import and `TestSeedFile` class (collection-time fallout), remove seed-row-existence tests, add empty-reset inverse assertion, keep schema/guard/idempotency tests per Technical Notes TN-7
- `tests/test_cli_db.py` -- update mocked return tuples, drop row-count output assertions, remove/repurpose the seed-not-found test per Technical Notes TN-7
- `tests/test_db_reset_guards.py` -- remove the `load_seed` patch and reconcile the `rows` assertion with `(table_count, 0)` per Technical Notes TN-7

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
`scripts/reset_dev_db.py` is a thin wrapper over `reset_database` and stays valid -- do not delete it. Documentation referencing seed data (`docs/admin/getting-started.md`, `docs/agent-browsability-workflow.md`) is stale after this change but is updated through the closure doc-assessment gate, not in this story (Technical Notes TN-8).
