# E-127-02: `bb creds extract-key` Multi-Match Disambiguation

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`DONE`

## Description
After this story is complete, `bb creds extract-key` will correctly handle JS bundles containing multiple `EDEN_AUTH_CLIENT_KEY` entries by logging all matches and selecting the web client key. Currently `_EDEN_KEY_PATTERN.search()` returns the first match, which may be the mobile key rather than the web key.

## Context
GameChanger's JS bundle now contains multiple `EDEN_AUTH_CLIENT_KEY` composite values (web and mobile). The existing `key_extractor.py` uses `re.search()` which returns only the first match. During a real session, this returned the mobile client ID instead of the web one, causing `bb creds extract-key --apply` to write incorrect credentials to `.env`. The disambiguation strategy is defined in Technical Notes TN-2 of the epic.

**Client ID rotation**: Proxy session data confirms that the iOS client ID rotates with app updates (e.g., `0f18f027-...` in Odyssey 2026.8.0 → `23e37466-...` in Odyssey 2026.9.0, observed between Mar 9-12). This means the multi-match set is not static -- new app versions introduce new client IDs. The disambiguation logic must not hardcode specific UUIDs; matching against the operator's `GAMECHANGER_CLIENT_ID_WEB` is the correct approach.

## Acceptance Criteria
- [ ] **AC-1**: Given a JS bundle containing multiple `EDEN_AUTH_CLIENT_KEY` entries, when `bb creds extract-key` runs, then all matches are discovered and logged (UUID portion only, not the key material).
- [ ] **AC-2**: Given `GAMECHANGER_CLIENT_ID_WEB` is present in `.env`, when multiple keys are found, then the key whose UUID matches the known client ID is selected automatically.
- [ ] **AC-3**: Given `GAMECHANGER_CLIENT_ID_WEB` is NOT in `.env` and multiple keys are found, when `bb creds extract-key` runs, then all candidates are presented with their UUIDs and the command exits without writing to `.env`, prompting the operator to re-run with `--apply` after setting `GAMECHANGER_CLIENT_ID_WEB`. No silent heuristic -- the operator must disambiguate.
- [ ] **AC-4**: Given a JS bundle containing a single `EDEN_AUTH_CLIENT_KEY` entry, when `bb creds extract-key` runs, then behavior is unchanged from the current implementation.
- [ ] **AC-5**: Tests cover single-match, multi-match with known ID, and multi-match without known ID scenarios.

## Technical Approach
The fix is in `src/gamechanger/key_extractor.py`. The disambiguation strategy is defined in epic Technical Notes TN-2. The core change is replacing `.search()` with `.findall()` and adding selection logic.

Key files to study: `src/gamechanger/key_extractor.py` (extraction pipeline), `src/cli/creds.py` (`extract_key` command, dry-run and --apply modes).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/key_extractor.py` -- replace `.search()` with `.findall()`, add disambiguation logic
- `src/cli/creds.py` -- pass known client ID context to extractor, handle multi-match presentation
- `tests/test_key_extractor.py` -- tests for multi-match scenarios

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
