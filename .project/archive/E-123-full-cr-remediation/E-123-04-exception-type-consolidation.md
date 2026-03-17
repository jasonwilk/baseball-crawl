# E-123-04: GameChangerAPIError Type Consolidation

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, `team_resolver.py` will use the shared `GameChangerAPIError` from `src.gamechanger.exceptions` instead of defining a local duplicate. Exception handling across the codebase will catch the correct type.

## Context
CR2-C2 confirmed that `src/gamechanger/team_resolver.py:43-44` defines a local `GameChangerAPIError(Exception)` that is a different Python type from `src.gamechanger.exceptions.GameChangerAPIError`. Any pipeline code catching the exceptions module version will miss errors raised by `team_resolver.resolve_team()`. The local `TeamNotFoundError(ValueError)` at line 47 should also be assessed. See `/.project/research/full-code-review/cr2-verified.md` (C-2) for evidence.

## Acceptance Criteria
- [ ] **AC-1**: `team_resolver.py` imports `GameChangerAPIError` from `src.gamechanger.exceptions` instead of defining it locally
- [ ] **AC-2**: The local `GameChangerAPIError` class definition is removed from `team_resolver.py`
- [ ] **AC-3**: If `TeamNotFoundError` is used outside `team_resolver.py`, move it to `exceptions.py`; if local-only, it may remain but should inherit from the shared exception hierarchy
- [ ] **AC-4**: All callers of `team_resolver` functions that catch exceptions still work correctly (verify via existing tests or add test if none exist)
- [ ] **AC-5**: All existing tests pass

## Technical Approach
Read `team_resolver.py` to identify all exception raises and the local class definitions. Read `exceptions.py` to understand the shared hierarchy. Replace local definitions with imports. Check all callers of `resolve_team()` to verify they catch the correct type. See TN-4 in the epic for details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/team_resolver.py`
- `src/gamechanger/exceptions.py` (if moving `TeamNotFoundError`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
