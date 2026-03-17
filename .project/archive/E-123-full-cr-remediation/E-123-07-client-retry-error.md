# E-123-07: Client Retry Error Message Fix

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, when `_get_with_retries` exhausts all retry attempts on a 5xx error, the raised exception will include retry context (e.g., "Server error after 3 attempts") instead of the generic "Unexpected status" message.

## Context
CR2-H3 confirmed that `src/gamechanger/client.py:539-558` has a control flow bug: on the final retry attempt for a 5xx, `last_error` is set but execution falls through to the generic "Unexpected status" error at line 555-558 instead of raising `last_error`. The `assert last_error is not None; raise last_error` at lines 560-561 is unreachable for this code path. See `/.project/research/full-code-review/cr2-verified.md` (H-3) for evidence.

## Acceptance Criteria
- [ ] **AC-1**: When `_get_with_retries` exhausts all retries on 5xx responses, the raised exception includes retry context (not "Unexpected status")
- [ ] **AC-2**: Non-5xx unexpected statuses still raise the "Unexpected status" error (existing behavior preserved)
- [ ] **AC-3**: A test verifies that three consecutive 5xx responses produce an error with retry context
- [ ] **AC-4**: All existing tests pass

## Technical Approach
Read `_get_with_retries` in `src/gamechanger/client.py` around lines 539-561. The fix should ensure `last_error` is raised when the retry loop exhausts for 5xx. One approach: restructure the loop so the 5xx case on the final attempt raises `last_error` directly. Another: use a `for/else` pattern. See TN-7 in the epic for details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/client.py`
- `tests/test_gc_client.py` (or equivalent test file)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
