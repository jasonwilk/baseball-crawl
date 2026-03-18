# E-127-09: Fix Scouting Crawler Public Games Accept Header

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, the scouting crawler will use the correct vendor Accept header for the public games endpoint (`/public/teams/{public_id}/games`), eliminating the HTTP 415 Unsupported Media Type error that prevented opponent schedule fetching.

## Pre-Implementation Status
**The constant change is already applied in the working tree** (not yet committed). `scouting.py` line 68 already has the correct `_PUBLIC_GAMES_ACCEPT` value. The remaining work for this story is: (1) verify the existing change matches AC-1, (2) update endpoint docs per AC-2, (3) add the clarifying comment per AC-3, (4) add the test per AC-4, and (5) commit.

## Context
The scouting crawler at `src/gamechanger/crawlers/scouting.py` had defined `_PUBLIC_GAMES_ACCEPT` as `application/vnd.gc.com.event:list+json; version=0.1.0`, which the public games endpoint rejects with HTTP 415. The correct header is `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0`. This was discovered during live scouting testing on 2026-03-18. The vendor media type name and version both differ from what was originally documented.

## Acceptance Criteria
- [ ] **AC-1**: `_PUBLIC_GAMES_ACCEPT` in `src/gamechanger/crawlers/scouting.py` is set to `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0`.
- [ ] **AC-2**: The public games endpoint doc (`docs/api/endpoints/get-public-teams-public_id-games.md`) is reviewed and updated in **three locations**: (a) if the Accept header value is stale, correct it; (b) update the `id` field description in the field table, the Known Limitations section, AND the see_also reason string to reflect that `id` equals `event_id` (the boxscore path parameter) -- not `game_stream.id`; (c) remove the "unresolved" caveat from the boxscore spec's `see_also` for this endpoint (`docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`).
- [ ] **AC-3**: A clarifying comment is added near the boxscore fetch code (line ~237) explaining that `game.get("id")` from the public games endpoint is the public-endpoint equivalent of `event_id` in the authenticated flow, and is correct.
- [ ] **AC-4**: A test verifies the correct Accept header constant value.

## Technical Approach
Single constant change in `src/gamechanger/crawlers/scouting.py` (line 68). Check whether the API endpoint doc for the public games endpoint references the old Accept header value and update if so.

Key files: `src/gamechanger/crawlers/scouting.py` (the `_PUBLIC_GAMES_ACCEPT` constant), `docs/api/endpoints/` (public games endpoint doc if it exists).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/scouting.py` -- verify pre-applied `_PUBLIC_GAMES_ACCEPT` constant, add clarifying comment near boxscore fetch
- `docs/api/endpoints/get-public-teams-public_id-games.md` -- fix `id` field description (equals `event_id`, not `game_stream.id`)
- `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md` -- remove "unresolved" caveat in see_also
- `tests/test_scouting_crawler.py` -- test correct Accept header value

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
