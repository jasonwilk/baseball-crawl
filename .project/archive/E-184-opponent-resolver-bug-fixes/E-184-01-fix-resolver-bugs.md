# E-184-01: Fix Resolver Bugs and Revert Test Workarounds

## Epic
[E-184: Fix Opponent Resolver Phantom Errors and Negative Unlinked Count](epic.md)

## Status
`DONE`

## Description
After this story is complete, `_search_fallback_team()` will return the correct tuple on all early-exit paths, `resolve()` will no longer produce negative unlinked counts, and all 13 test assertions plus 3 comments that E-179 modified to match the buggy behavior will be reverted to their correct intended values.

## Context
Two bugs in `src/gamechanger/crawlers/opponent_resolver.py` produce incorrect `ResolveResult` counts. Bug 1: a bare `return 0` causes a TypeError when the caller unpacks it as a tuple, caught by a broad exception handler that inflates `errors` by +1. Bug 2: subtracting `search_count` from `unlinked` can produce negative values because the search fallback resolves opponents from prior runs, not just the current run. E-179 updated tests to match the buggy behavior; those assertions must be reverted atomically with the production fixes. See epic Technical Notes TN-1, TN-2, and TN-3 for full analysis.

## Acceptance Criteria
- [ ] **AC-1**: Given a resolution run where all opponents for a member team are already resolved, when `_search_fallback_team()` finds no unlinked rows and returns early, then the caller successfully unpacks the return value without error and `ResolveResult.errors` is not incremented
- [ ] **AC-2**: Given a resolution run where the search fallback resolves opponents from prior runs (not inserted in the current run), when `resolve()` completes, then `ResolveResult.unlinked` is >= 0 (never negative)
- [ ] **AC-3**: All 13 test assertions and 3 comments in `test_opponent_resolver.py` that E-179 modified are reverted to their correct intended values per TN-3
- [ ] **AC-4**: `python -m pytest tests/test_crawlers/test_opponent_resolver.py -v` passes with zero failures
- [ ] **AC-5**: `python -m pytest tests/ -v` passes with no new failures (no regressions)

## Technical Approach
Two targeted fixes in `opponent_resolver.py` (see TN-1 and TN-2), plus mechanical reversion of 13 assertion values and 3 comments in the test file (see TN-3). The production fixes and test reversions must be applied together -- the tests validate the corrected behavior.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/opponent_resolver.py`
- `tests/test_crawlers/test_opponent_resolver.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- All early-return paths in `_search_fallback_team` should be verified to return `tuple[int, int]` (the `internal_id is None` guard already returns `(0, 0)` correctly).
- The `ResolveResult.unlinked` docstring should still accurately describe the field as "Opponents inserted as unlinked" after the fix.
- Use the pattern-based guidance in TN-3 to locate assertions -- line numbers are approximate.
