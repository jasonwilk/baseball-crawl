# E-214-02: Update Callers to Pass `reference_date`

## Epic
[E-214: Fix Predicted Starter Rest Day Anchoring](epic.md)

## Status
`DONE`

## Description
After this story is complete, all three call sites that invoke `compute_starter_prediction()` will pass an explicit `reference_date` argument: `datetime.date.today()` for dashboard routes and `datetime.date.fromisoformat(generated_at[:10])` for the report generator.

## Context
Story E-214-01 adds the required `reference_date` parameter to the engine. This story updates the three callers to pass it. Without this change, callers would fail at runtime due to the missing required argument.

## Acceptance Criteria
- [ ] **AC-1**: `src/reports/generator.py` passes `reference_date=datetime.date.fromisoformat(generated_at[:10])` to `compute_starter_prediction()` per TN-2 in Technical Notes.
- [ ] **AC-2**: `src/api/routes/dashboard.py` opponent detail route (~line 1644) passes `reference_date=datetime.date.today()` to `compute_starter_prediction()`.
- [ ] **AC-3**: `src/api/routes/dashboard.py` print view route (~line 1833) passes `reference_date=datetime.date.today()` to `compute_starter_prediction()`.
- [ ] **AC-4**: No other call sites exist in `src/` that invoke `compute_starter_prediction()` without `reference_date` (verified by grep).
- [ ] **AC-5**: At least one new test in `tests/test_starter_prediction.py` verifies that `compute_starter_prediction()` uses the provided `reference_date` for rest calculations rather than an internally-derived date (e.g., call with two different `reference_date` values on the same history data and confirm the reasoning strings differ accordingly).

## Technical Approach
Mechanical update at three call sites. Each caller already has the appropriate date available in scope. The dashboard routes use `datetime.date.today()`; the report generator uses `generated_at[:10]` which is already computed for the pitching workload call.

## Dependencies
- **Blocked by**: E-214-01
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` (modify -- add `reference_date` argument)
- `src/api/routes/dashboard.py` (modify -- add `reference_date` argument at two call sites)
- `tests/test_starter_prediction.py` (modify -- add integration-level test per AC-5)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- AC-4 can be verified with a grep for `compute_starter_prediction` across `src/`.
