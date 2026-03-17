# E-122-01: Scouting Crawler — Abort on CredentialExpiredError

## Epic
[E-122: E-100 Family Code Review Remediation (Wave 2)](epic.md)

## Status
`DONE`

## Description
After this story is complete, the scouting crawler will immediately abort when it encounters a `CredentialExpiredError` (HTTP 401) during boxscore fetching, instead of logging a warning and continuing to the next game. This matches the behavior of the member-team crawlers, which correctly let 401 propagate.

## Context
CR-4-6 confirmed that `_fetch_boxscores()` in `scouting.py` catches `(CredentialExpiredError, ForbiddenError, GameChangerAPIError)` as a group and continues the loop. When auth expires mid-crawl, the crawler wastes time attempting remaining games (all of which will also fail) instead of surfacing the error immediately. The outer `scout_all()` method has a broad `except Exception` that also swallows errors. See `/.project/research/cr-e100-family/verified-findings.md` finding CR-4-6 for line numbers and full context.

## Acceptance Criteria
- [ ] **AC-1**: `_fetch_boxscores()` does not catch `CredentialExpiredError` in the per-game exception handler. When a 401 occurs, it propagates out of `_fetch_boxscores()`.
- [ ] **AC-2**: `ForbiddenError` and `GameChangerAPIError` remain caught in the per-game handler (these are expected for non-owned team boxscores).
- [ ] **AC-3**: `CredentialExpiredError` is not swallowed by the `scout_all()` outer exception handler. It either propagates to the caller or is re-raised after logging.
- [ ] **AC-4**: A test verifies that `CredentialExpiredError` raised during boxscore fetching propagates out of the scouting crawl (not silently continued).
- [ ] **AC-5**: All existing tests pass.

## Technical Approach
See epic Technical Notes TN-2 for the auth abort pattern. The verified findings file at `/.project/research/cr-e100-family/verified-findings.md` (CR-4-6) provides exact line numbers. The fix separates `CredentialExpiredError` from the exception group in `_fetch_boxscores()` and ensures `scout_all()` does not suppress it.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/scouting.py`
- `tests/test_scouting.py` (or appropriate test file)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
