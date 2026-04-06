# E-214-01: Thread `reference_date` Through the Prediction Engine

## Epic
[E-214: Fix Predicted Starter Rest Day Anchoring](epic.md)

## Status
`TODO`

## Description
After this story is complete, the predicted starter engine will accept a `reference_date: datetime.date` parameter and use it for all rest/availability calculations instead of the internally-computed `latest_game_date`. All internal functions that compute rest days, apply exclusions, or score rest-based likelihood will use `reference_date` as their anchor.

## Context
The core bug: `compute_starter_prediction()` computes `latest_game_date` from the pitching history data and passes it to four internal functions for rest calculations. This means rest days are measured from the team's last game, not from today. The rest TABLE (built by `_build_rest_table()` from `get_pitching_workload()`) already uses today/generation_date as its reference, creating conflicting rest day values for the same pitcher.

This story changes the engine internals. Story E-214-02 updates callers to pass the new parameter.

## Acceptance Criteria
- [ ] **AC-1**: `compute_starter_prediction()` accepts a required `reference_date: datetime.date` parameter (no default value) per TN-1 in Technical Notes.
- [ ] **AC-2**: `_is_excluded_within_1_day()`, `_is_excluded_high_pitch_short_rest()`, `_build_reasoning()`, and `_compute_rotation_likelihoods()` use `reference_date: datetime.date` for rest/availability calculations per TN-1 in Technical Notes.
- [ ] **AC-3**: All existing tests in `tests/test_starter_prediction.py` are updated to pass a `reference_date` argument and continue to pass.
- [ ] **AC-4**: New test: Given a pitcher who last appeared on 2026-03-28, a team game on 2026-03-31 (so `latest_game_date` would be 2026-03-31 under the old logic), at least 4 total team games (to avoid the suppress path), and `reference_date=2026-04-06`, the reasoning string contains "9 days rest" (proving anchor is `reference_date`, not `latest_game_date` which would produce "3 days rest").
- [ ] **AC-5**: New test: Given a pitcher who last appeared on 2026-03-28 with 80 pitches and `reference_date=2026-04-02` (5 days rest), the pitcher is NOT excluded by `_is_excluded_high_pitch_short_rest()`. With `reference_date=2026-03-31` (3 days rest), the pitcher IS excluded.
- [ ] **AC-6**: New test: Given a pitcher who last appeared on 2026-04-05 and `reference_date=2026-04-06` (1 day rest), the pitcher IS excluded by `_is_excluded_within_1_day()`.

## Technical Approach
The engine is a pure function with no DB or HTTP access. The change is mechanical: replace the `latest_game_date: str` parameter in four internal functions with `reference_date: datetime.date`, and update the main entry point to accept and thread it through. The rotation sequence detection in `_compute_rotation_likelihoods()` does not use the date parameter -- only the rest scoring block does. Existing tests need their `compute_starter_prediction()` calls updated to include a `reference_date` argument.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-214-02

## Files to Create or Modify
- `src/reports/starter_prediction.py` (modify -- engine internals)
- `tests/test_starter_prediction.py` (modify -- update existing tests + add new)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-214-02**: Updated public API signature for `compute_starter_prediction()` -- callers must now pass `reference_date: datetime.date`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- SE recommended `datetime.date` over `str` to eliminate redundant `fromisoformat()` calls in internal functions.
- The `_build_rest_table()` function is NOT changed by this story -- it already uses `workload` data with the correct anchor.
- `_build_reasoning()` uses the date parameter in TWO separate blocks: rest display (lines 183-189) and availability-unknown check (lines 200-211). Both must use `reference_date`.
- `_check_tournament_density()` is correctly data-relative (uses game dates from history) and should NOT receive `reference_date`. Do not refactor it.
