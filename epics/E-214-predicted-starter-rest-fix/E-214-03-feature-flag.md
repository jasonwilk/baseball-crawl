# E-214-03: Add `FEATURE_PREDICTED_STARTER` Feature Flag

## Epic
[E-214: Fix Predicted Starter Rest Day Anchoring](epic.md)

## Status
`TODO`

## Description
After this story is complete, the predicted starter section can be disabled in production by omitting `FEATURE_PREDICTED_STARTER` or setting it to any value other than `1`/`true`/`yes`. Dev environments enable it via `.env`. A helper function centralizes the env var check.

## Context
The user wants to disable predicted starter on production while the rest-days fix (E-214-01, E-214-02) is verified in dev. This is the project's first feature flag -- keep it simple with `os.environ.get()`, no framework.

## Acceptance Criteria
- [ ] **AC-1**: `is_predicted_starter_enabled()` function exists in `src/reports/starter_prediction.py` and returns `True` only when `FEATURE_PREDICTED_STARTER` env var is one of `1`, `true`, or `yes` (case-insensitive); returns `False` for all other values and when the env var is absent, per TN-3 in Technical Notes.
- [ ] **AC-2**: `src/reports/generator.py` skips the predicted starter computation when `is_predicted_starter_enabled()` returns `False` and passes `show_predicted_starter=False` to the template context per TN-4 in Technical Notes.
- [ ] **AC-3**: `src/api/routes/dashboard.py` opponent detail route skips the predicted starter block when `is_predicted_starter_enabled()` returns `False`.
- [ ] **AC-4**: `src/api/routes/dashboard.py` print view route skips the predicted starter block when `is_predicted_starter_enabled()` returns `False`.
- [ ] **AC-5**: The report template (`scouting_report.html`) wraps the entire predicted starter section (header, cards, rest table, bullpen, disclaimer) in `{% if show_predicted_starter %}` so the section is completely absent when the flag is disabled -- no header, no "No pitching data available" placeholder.
- [ ] **AC-6**: Test: `is_predicted_starter_enabled()` returns `True` for `"1"`, `"true"`, `"yes"`, `"TRUE"`; returns `False` for `""`, `"0"`, `"false"`, and when the env var is absent.
- [ ] **AC-7**: `.env.example` (repo root) includes `FEATURE_PREDICTED_STARTER=1` so dev environments pick up the flag.

## Technical Approach
Add `is_predicted_starter_enabled()` to `starter_prediction.py` (keeps the env var name in one place). Each call site wraps its predicted starter block in an `if is_predicted_starter_enabled():` check. The flag check is at the call site, not inside the engine, to preserve the engine's purity as a computation function.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/starter_prediction.py` (modify -- add `is_predicted_starter_enabled()`)
- `src/reports/generator.py` (modify -- wrap predicted starter block in flag check, add `show_predicted_starter` to data dict)
- `src/reports/renderer.py` (modify -- forward `show_predicted_starter` from data dict to template context)
- `src/api/routes/dashboard.py` (modify -- wrap two predicted starter blocks in flag check)
- `src/api/templates/reports/scouting_report.html` (modify -- wrap entire predicted starter section in `{% if show_predicted_starter %}`)
- `tests/test_starter_prediction.py` (modify -- add tests for `is_predicted_starter_enabled()`)
- `.env.example` (modify -- add `FEATURE_PREDICTED_STARTER=1`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- This story is independent of E-214-01/02. The flag wraps the entire predicted starter block -- it works regardless of whether the block uses `reference_date` or `latest_game_date`.
- If executing after E-214-02, preserve all existing arguments on the `compute_starter_prediction()` call (including `reference_date`) when wrapping the block in the flag check. The flag gates whether the block runs, not what arguments it passes.
- `.env` is git-ignored; `.env.example` is tracked and is the canonical template for dev environment setup.
