# E-127-08: Boxscore Crawler Uses Wrong ID for Endpoint

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, the game stats crawler will use `event_id` (not `game_stream.id`) as the path parameter for `GET /game-stream-processing/{id}/boxscore`, the misleading code comments claiming `game_stream.id` is the correct ID will be corrected, and the game loader's summaries index will support lookup by both `event_id` and `game_stream_id` so that boxscore files named by `event_id` can be matched to game summaries. This bug caused all 17 boxscore fetches to fail with HTTP 500 "Cannot find event" during crawl testing.

## Pre-Implementation Status
**Partially pre-implemented in the working tree** (not yet committed). The core ID extraction fix and the loader dual-key index are already applied:
- `_extract_game_stream_id()` already returns `record.get("event_id")` -- correct.
- `game_loader.py` `_build_summaries_index()` already indexes by both `event_id` and `game_stream_id` -- correct.

**Remaining work** (NOT yet done):
- The module docstring's "CRITICAL ID MAPPING" section (lines 15-21) still documents the OLD wrong mapping -- must be corrected (AC-2).
- `_fetch_boxscore()` docstring (line ~193) still says "The `game_stream.id` value" -- stale (AC-3).
- `_game_path()` docstring (line ~258) still says "The `game_stream.id` UUID" -- stale (AC-3).
- The variable named `game_stream_id` on line ~142 of `_crawl_team()` now holds `event_id` -- rename to `event_id` to eliminate the naming confusion (AC-3).
- `game_loader.py` `_build_summaries_index()` docstring (line ~303) still says "game_stream_id -> GameSummaryEntry" -- update to reflect dual-key indexing (AC-6).
- `game_loader.py` module-level docstring (lines 6-21) still references `games/{game_stream_id}.json` file naming and stale ID mapping descriptions -- update to reflect `event_id` file naming (AC-6).
- Tests for correct ID extraction and dual-key matching (AC-7, AC-8).

## Context
The boxscore endpoint `GET /game-stream-processing/{id}/boxscore` expects the `event_id` from game-summaries records. The game stats crawler at `src/gamechanger/crawlers/game_stats.py` extracts `game_stream.id` instead (via `_extract_game_stream_id()` at line ~226-241). The module docstring (lines 15-21) and the helper's docstring explicitly -- and incorrectly -- state that `game_stream.id` is the correct path parameter and that it is NOT `event_id`. This was verified by the user: switching to `event_id` returns HTTP 200 with full boxscore data. The fix is defined in epic Technical Notes TN-8.

**Two boxscore ID contexts exist**:
- **Authenticated flow** (`game_stats.py`): Game-summaries records contain `event_id` (the boxscore path parameter) and `game_stream.id` (a different identifier). The crawler was incorrectly using `game_stream.id`. This is the bug.
- **Public/scouting flow** (`scouting.py`): The public `/games` endpoint returns an `id` field per game. The scouting crawler uses this `id` as the boxscore path parameter and this is correct -- it maps to the same concept as `event_id` in the authenticated flow. No fix needed for the scouting path.

**Loader impact**: Once the crawler is fixed to use `event_id`, cached boxscore files will be named by `event_id` instead of `game_stream.id`. The game loader at `src/gamechanger/loaders/game_loader.py` builds an index of game summaries keyed by `game_stream_id` to match boxscore files. It must also index by `event_id` so files named either way can be matched. See epic TN-8 for details.

## Acceptance Criteria
- [ ] **AC-1**: The game stats crawler uses `event_id` from game-summaries records as the boxscore endpoint path parameter.
- [ ] **AC-2**: The module docstring's "CRITICAL ID MAPPING" section is corrected to reflect that the boxscore endpoint uses `event_id`.
- [ ] **AC-3**: All stale `game_stream.id` references in `game_stats.py` are corrected: (a) the `_extract_game_stream_id()` helper is renamed to reflect `event_id` extraction; (b) `_fetch_boxscore()` docstring (line ~193) and `_game_path()` docstring (line ~258) are updated; (c) the variable named `game_stream_id` in `_crawl_team()` (line ~142) that now holds `event_id` is renamed; (d) the log message at line ~147 ("Missing game_stream.id") is updated.
- [ ] **AC-4**: File naming for cached boxscore JSON files uses `event_id` consistently.
- [ ] **AC-5**: The scouting crawler's boxscore path is confirmed correct (uses `id` from public games endpoint). Clarifying comment is handled by E-127-09 (which owns `scouting.py`).
- [ ] **AC-6**: The game loader's summaries index supports lookup by both `event_id` and `game_stream_id`, so boxscore files named by either key are matched correctly.
- [ ] **AC-7**: Tests verify the correct ID is extracted from a game-summaries record and used in the API call.
- [ ] **AC-8**: Tests verify the game loader can match boxscore files named by `event_id` to their game summary entries.

## Technical Approach
The core change is in `src/gamechanger/crawlers/game_stats.py`: the ID extraction helper and its call sites need to use `event_id` from the game-summaries record instead of `game_stream.id`. The module docstring's "CRITICAL ID MAPPING" section (lines 15-21) documents the wrong mapping and must be corrected. The `_BOXSCORE_ACCEPT` header is already correctly defined and passed -- no changes needed there.

The scouting crawler (`src/gamechanger/crawlers/scouting.py`, line ~237) uses `game.get("id")` from the public games endpoint. This is correct -- the public games `id` field is the equivalent of `event_id` in the authenticated flow. The clarifying comment is handled by E-127-09 (which owns all `scouting.py` changes).

The game loader (`src/gamechanger/loaders/game_loader.py`) builds a summaries index in `_build_summaries_index()`. Currently keyed only by `game_stream_id`. After the crawler fix, boxscore files will be named by `event_id`. The index must store each entry under both `event_id` and `game_stream_id` so that file-to-summary matching works regardless of which key was used for file naming.

Key files: `src/gamechanger/crawlers/game_stats.py` (ID extraction and API call), `src/gamechanger/loaders/game_loader.py` (dual-key index).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/game_stats.py` -- fix ID extraction, update docstrings and comments
- `src/gamechanger/loaders/game_loader.py` -- dual-key summaries index (event_id + game_stream_id)
- `tests/test_game_stats_crawler.py` -- test correct ID extraction and usage
- `tests/test_game_loader.py` -- test dual-key index matching

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
