# E-236-01: Migration 003 + shared stage-status classifier

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, `report_generation_runs` will carry four new additive count columns and the reports package will have a single shared `classify_stage_status` helper that every stage will call to map its outcome to an honest status string. This is the foundation the per-stage honesty stories (02-04) and the operator-surface story (07) build on.

## Context
The epic's unifying invariant (epic Technical Notes TN-1) requires one place that maps `(loaded, errors, expected)` to `completed`/`partial`/`failed` so no stage hardcodes status literals or invents its own partial logic. The new count columns (TN-2) make the partial story legible to an unattended monitor. This story delivers both with their own tests and changes NO generator behavior yet — the helper and columns are wired into stages in 02-04.

## Acceptance Criteria
- [ ] **AC-1**: `migrations/003_*.sql` adds the four nullable `INTEGER` columns to `report_generation_runs` (`boxscores_fetched`, `load_errors`, `plays_errors`, `spray_games_with_data`) via `ALTER TABLE ... ADD COLUMN`, per Technical Notes TN-2. NULL means "stage didn't run".
- [ ] **AC-2**: A shared `classify_stage_status(loaded, errors, expected)` helper returns exactly `"completed"`, `"partial"`, or `"failed"` per the semantics in Technical Notes TN-1, with module-level status constants (no bare string literals at the eventual call sites). The helper docstring states the TN-1 F3 guardrail: `expected`/`loaded` are "units ATTEMPTED where a shortfall implies failure," NOT raw data coverage.
- [ ] **AC-3**: Unit tests cover the classifier's outcomes across a table of cases including the boundaries: full+zero-errors → completed; some-loaded-with-errors AND loaded<expected → partial; zero-loaded-of-nonzero-expected → failed; AND `expected == 0` → `completed` (nothing attempted = no failure).
- [ ] **AC-4**: `GenerationResult` (`generator.py:67-75`) gains the additive field `outcome: Literal["ready", "no_games", "failed"]` with default `"failed"` (per Technical Notes TN-5; pulled into this foundation story so stories 03/05/08 consume it without an inter-story ordering edge). This story ONLY defines the field with its default — it sets NO values and changes NO behavior (story 05 sets `"ready"`/`"no_games"`; all current `success=False` returns inherit the default).
- [ ] **AC-5**: `tests/test_migrations.py` adds a round-trip assertion that the four new columns exist and accept INTEGER + NULL values after migration.
- [ ] **AC-6**: The migration preserves the explicit-column-list invariant (Technical Notes TN-2): no existing `INSERT INTO report_generation_runs` is converted to positional form, and the new columns are not added to any insert that would make it positional.
- [ ] **AC-7**: No generator behavior change — existing report-generation tests stay green (the helper and columns are unused, and the `outcome` field is unset/default, until stories 02-05/09).

## Technical Approach
Mirror the E-235 migration 002 shape and the existing additive-column conventions in `migrations/`. The classifier is a pure function; place it in the reports package (e.g. a small module under `src/reports/`) so `generator.py` can import it and unit tests can exercise it in isolation. Document the `expected == 0` semantics AND the F3 guardrail in the helper's docstring. Do not wire the helper into any stage in this story. The `outcome` field is a one-line `dataclass` addition with a default — define it, set nothing.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-236-02, E-236-03, E-236-04, E-236-05, E-236-07, E-236-08, E-236-09

## Files to Create or Modify
- `migrations/003_*.sql` (create — name per existing migration numbering convention)
- `src/reports/` — new module for `classify_stage_status` + status constants (implementer chooses filename)
- `src/reports/generator.py` (modify — add the `outcome` field to `GenerationResult`, default `"failed"`; no value-setting)
- `tests/test_migrations.py` (modify — round-trip assertion for new columns)
- New unit test for the classifier (e.g. `tests/test_run_status.py`, name per chosen module)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-236-02/03/04/09**: `classify_stage_status` + status constants and the four count columns the per-stage honesty stories write.
- **Produces for E-236-03/05/08**: the `GenerationResult.outcome` field (default `"failed"`) — story 05 sets its values; story 03's all-blocked path inherits the default; story 08 asserts it.
- **Produces for E-236-07**: the count columns the admin run-record view surfaces.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
DE D1/D2/D4. `"partial"` needs no migration for the status VALUE (per-stage `*_status` columns are free-text TEXT, no CHECK). The migration is only the four count columns.
