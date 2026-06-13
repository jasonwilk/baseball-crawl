# E-234-01: Golden stat tables for the report query surface

## Epic
[E-234: Report Regression Guards](epic.md)

## Status
`DONE`

## Description
After this story is complete, the test suite contains a golden-stat-table test that seeds a fixture DB, runs the full report query surface, and deep-equals the result against a committed golden JSON file. Any future change that alters a report stat value, a computed formula (ERA/WHIP/K9/OBP), or a heat level fails this test. This is the primary "did we regress the numbers" guard for every later roadmap epic.

## Context
The reports flow is the protected core (ROADMAP §3); Epics B–E all refactor code it depends on. There is no golden-file pattern in the repo yet (greenfield), so this establishes the simplest workable one. The fixture `tests/fixtures/seed.sql` already exists with hand-computed expected values in its header — reuse it rather than authoring a new fixture. See Technical Notes §TN-1 for the collector surface, exclusions, golden-storage rule, and the anti-silent-overwrite regen mechanism.

## Acceptance Criteria
- [ ] **AC-1**: A new test seeds a fixture DB from `tests/fixtures/seed.sql` via `load_real_schema()` and runs the full collector surface (all `_query_*` functions in `src/reports/generator.py` plus `get_pitching_workload`, `get_pitching_history`, `build_pitcher_profiles` from `src/api/db.py`) for the seed's TEAM_VARSITY across its primary season, passing `get_pitching_workload` a FIXED `reference_date` anchored to the fixture's game dates (never the default today, which would make the golden non-deterministic), per Technical Notes §TN-1.
- [ ] **AC-2**: The collected result is compared against committed `tests/fixtures/golden/report_stats.json` by deep equality, with timestamps, `slug`, `generated_at`, and LLM/Tier-2 narrative normalized out before comparison, per Technical Notes §TN-1.
- [ ] **AC-3**: The test never writes the golden file. Golden regeneration is a separate explicit path (a standalone `scripts/regen_report_golden.py` preferred over a pytest addoption), so a regenerated golden surfaces in `git diff`, per Technical Notes §TN-1.
- [ ] **AC-4**: The committed golden carries a top-level `_meta` provenance object (`reviewed_by`, `reviewed_date`, `basis`) recording the one-time hand-review of its values against the seed.sql header math (no current bug encoded as truth); the `_meta` block is normalized out before comparison, per Technical Notes §TN-1. The test passes green against the committed golden.
- [ ] **AC-5**: No change to any `src/` behavior — additive test, fixture, and regen-script files only.
- [ ] **AC-6**: The test and/or golden explicitly scopes the spray-chart and plays-stats surfaces as shape/no-crash coverage only — seed.sql has no `spray_charts`/`plays`/`play_events` rows, so those queries return empty and are NOT value-guarded (story 05's e2e is their value guard) — and documents that the golden is data-layer only (it does not guard `renderer.py`/`scouting_report.html`), per Technical Notes §TN-1.

## Technical Approach
Reuse the existing fixture and schema loader. Build one collector helper that assembles a single dict from the query surface named in §TN-1, then a normalizer that strips the excluded fields before compare. Store the golden as committed JSON; keep regeneration out of the test path. Follow the existing fixture-DB test pattern in `tests/test_report_generator.py` (disk-backed `load_real_schema` connection). See Technical Notes §TN-1.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_report_golden.py` (new)
- `tests/fixtures/golden/report_stats.json` (new, committed golden)
- `scripts/regen_report_golden.py` (new, regen path)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE consultation confirmed ~200 LOC sizing and the regen-as-separate-path gate. The seed.sql header already did the stat math for hand-review.
