# E-123-02: PII Scanner Regex Fix for Unquoted Values

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the PII scanner's `api_key_assignment` regex will detect unquoted YAML-style key-value assignments (e.g., `secret_key: xKfake_value`) in addition to quoted values. The currently failing test `test_secret_key_colon` will pass.

## Context
CR5-C1 confirmed that `src/safety/pii_patterns.py:67` requires values to be wrapped in quotes (`["\']`), so unquoted YAML assignments bypass detection entirely. The test at `tests/test_pii_scanner.py:228-236` was correctly written to catch this but is actively failing (`assert 0 == 1`). This is a safety tool blind spot. See `/.project/research/full-code-review/cr5-verified.md` (C-1) for evidence.

## Acceptance Criteria
- [ ] **AC-1**: The `api_key_assignment` regex in `pii_patterns.py` matches unquoted YAML-style key-value assignments (e.g., `secret_key: xKfake_secret_value_here_long_enough`)
- [ ] **AC-2**: The regex still matches quoted assignments (existing behavior preserved)
- [ ] **AC-3**: `pytest tests/test_pii_scanner.py::test_secret_key_colon` passes
- [ ] **AC-4**: All existing PII scanner tests pass (no regressions)
- [ ] **AC-5**: All existing tests pass

## Technical Approach
Read the current regex at `src/safety/pii_patterns.py:67`. Modify it to make the quote requirement optional or add an alternative branch for unquoted values. Run the full PII scanner test suite to verify no regressions. See TN-2 in the epic for details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/safety/pii_patterns.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The test is already written and correct -- this is purely a regex fix, no new tests needed.
