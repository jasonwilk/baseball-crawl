# E-174-01: Add Asset Chunk Fallback to Key Extractor

## Epic
[E-174: Fix Key Extractor to Search Asset Chunks](epic.md)

## Status
`TODO`

## Description
After this story is complete, `extract_client_key()` will search code-split asset chunks when the `EDEN_AUTH_CLIENT_KEY` is not found in the index bundle. The index bundle is tried first (preserving backward compatibility), and asset chunks are searched sequentially with early exit on first match. The `ExtractedKey.bundle_url` field reflects the actual chunk the key was found in.

## Context
GameChanger moved the `EDEN_AUTH_CLIENT_KEY` from the index bundle into a code-split asset chunk around 2026-03-25. The existing regex pattern is correct but only searches the wrong file. This story adds fallback search across all discoverable JS chunks in the HTML, making the extractor resilient to future chunk reorganization.

## Acceptance Criteria
- [ ] **AC-1**: Given the key is present in the index bundle, when `extract_client_key()` is called, then the key is returned from the index bundle (existing behavior unchanged).
- [ ] **AC-2**: Given the key is NOT in the index bundle but IS in an asset chunk, when `extract_client_key()` is called, then the key is returned from the asset chunk and `ExtractedKey.bundle_url` reflects that chunk's URL.
- [ ] **AC-3**: Given the key is NOT in the index bundle and NOT in any asset chunk, when `extract_client_key()` is called, then `KeyExtractionError` is raised with a message indicating how many chunks were searched.
- [ ] **AC-4**: Given multiple asset chunks exist and the key is in the Nth chunk (N > 1), when `extract_client_key()` is called, then earlier chunks are fetched and skipped without error, the key is returned from the correct chunk, and chunks after the match are not fetched.
- [ ] **AC-5**: Given the index bundle `<script>` tag is not found in the HTML but asset chunks exist, when `extract_client_key()` is called, then asset chunks are still searched (graceful degradation per Technical Notes).
- [ ] **AC-6**: Given an asset chunk returns a network error, when the fallback loop processes that chunk, then the error is logged and the next chunk is tried (no abort).
- [ ] **AC-7**: All existing tests in `tests/test_key_extractor.py` continue to pass. Tests whose assertions conflict with the new fallback behavior (e.g., `test_bundle_url_not_found_in_html`, `test_eden_key_not_in_bundle`) are updated to reflect the graceful degradation path -- not deleted.

## Technical Approach
The changes are confined to `src/gamechanger/key_extractor.py` and `tests/test_key_extractor.py`.

**Source changes** (`src/gamechanger/key_extractor.py`):
- Add a new compiled regex pattern for discovering asset chunk URLs from HTML (matching `href` and `src` attributes pointing to `/assets/*.js`).
- Add a new helper function to extract asset chunk URLs from the homepage HTML, resolving relative URLs against `_GC_HOME_URL`. Should exclude the index bundle URL (which is tried separately).
- Restructure `extract_client_key()` to: (a) widen the `httpx.Client` scope to cover the full search (per Technical Notes "HTTP Client Scope" section), (b) try index bundle first, (c) on `KeyExtractionError` from `_find_composites`, fall back to asset chunk search, (d) handle the case where `_find_bundle_url` itself fails (graceful degradation -- skip to asset chunks).
- Update the module docstring at the top of `key_extractor.py` to reflect the new fallback extraction flow.
- Log each chunk fetch at DEBUG level and log which chunk yielded the key at INFO level.

**Test changes** (`tests/test_key_extractor.py`):
- Add unit tests for the new asset URL discovery helper.
- Add integration tests with mocked HTTP for: key in asset chunk (AC-2), key missing everywhere (AC-3), multi-chunk early exit (AC-4), no index bundle but key in chunk (AC-5), chunk network error handling (AC-6).
- Update existing tests whose assertions conflict with the new fallback behavior: `test_bundle_url_not_found_in_html` (now triggers asset chunk search instead of immediate error) and `test_eden_key_not_in_bundle` (verify error message match string still works with the new fallback error path).

Reference files:
- `/workspaces/baseball-crawl/src/gamechanger/key_extractor.py` -- the module being modified
- `/workspaces/baseball-crawl/tests/test_key_extractor.py` -- the test file being extended

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/key_extractor.py` -- add asset chunk discovery and fallback search logic
- `tests/test_key_extractor.py` -- add tests for fallback scenarios, update affected existing tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] Test scope discovery per `/.claude/rules/testing.md` -- grep for all test files importing from `key_extractor` (including `tests/test_cli_creds.py`) and run them

## Notes
- The multi-key disambiguation logic (`known_client_id` parameter) applies regardless of whether the key came from the index bundle or an asset chunk -- no changes needed there.
- Rate limiting between chunk fetches is not required per `/.claude/rules/http-discipline.md` scope note: these are public static asset fetches, not API calls. However, the sequential fetch pattern naturally avoids hammering the CDN.
