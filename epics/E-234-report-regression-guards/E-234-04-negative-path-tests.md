# E-234-04: Report-generation negative-path characterization tests

## Epic
[E-234: Report Regression Guards](epic.md)

## Status
`TODO`

## Description
After this story is complete, the suite pins the current behavior of `generate_report()` under failure and degraded-data conditions — no completed games, public-profile fetch failure, auth expiry mid-run — plus a crawler-level roster-fetch-failure test. These characterize present behavior (including the known ready-but-empty case) so Epic B's quality gates have a verified before-anchor.

## Context
ROADMAP §2 documents several silent-degradation weaknesses (the ready-but-empty report path, season-scope fallback, etc.) that Epic B will fix. Note: `generator.py:1098-1102` is the crawl-FAILURE guard (`errors > 0 AND games_crawled == 0`), NOT the ready-but-empty render — the ready-but-empty outcome occurs downstream at post-load render when a zero-games crawl returns zero errors (see Technical Notes §TN-4). Before fixing, we must lock current behavior in tests so the Epic B change is a visible, asserted diff. The mock seams already exist in `tests/test_report_generator.py`. See Technical Notes §TN-4 for per-case mock approach and the boundary split. **This story characterizes current behavior; it does NOT fix any bug** (epic Non-Goals).

## Acceptance Criteria
- [ ] **AC-1**: A test drives `generate_report()` with a crawl result of zero completed games and zero errors (`ScoutingCrawlResult(team_id=<varsity team id>, season_id="2026-spring-hs", games_crawled=0, errors=0, games=[], boxscores={})` — `team_id`/`season_id` are required positionals, illustrative form) and asserts the **current** ready-but-empty outcome, explicitly labeled in the test as the before-anchor for Epic B's no-completed-games gate (not desired behavior), per Technical Notes §TN-4.
- [ ] **AC-2**: Public-profile fetch failure is already exercised by `tests/test_report_generator.py::test_ac3_no_backfill_when_api_fails` (patches `src.http.session.create_session` to raise), which asserts the no-`public_id`-backfill branch. This story EXTENDS that coverage with the uncovered behavior: assert that generation still reaches a terminal/ready outcome and uses the team-name fallback when the public profile is unavailable — NOT a re-characterization of the already-covered backfill branch, per Technical Notes §TN-4.
- [ ] **AC-3**: Auth-expiry-mid-run coverage asserts which pipeline stages did and did not run (extending the existing auth-expiry tests rather than duplicating them), per Technical Notes §TN-4.
- [ ] **AC-4**: A `ScoutingCrawler` unit test in `tests/test_scouting_crawler.py` simulates a roster-fetch failure and asserts the crawler's resilience/error behavior at that layer (not at the generator boundary), per Technical Notes §TN-4.
- [ ] **AC-5**: No `src/` behavior change — additive tests only; the tests assert current behavior and must not require any pipeline fix to pass.

## Technical Approach
Use the established patch-at-module-level seams from `tests/test_report_generator.py` (`GameChangerClient`, `ScoutingCrawler`/`scout_team`, `ScoutingLoader`/`load_team`, `_crawl_and_load_spray`, `_crawl_and_load_plays`, `get_connection`). Put the generator-boundary cases in a new `tests/test_report_negative_paths.py`; put the roster-fetch case one layer down in `tests/test_scouting_crawler.py`. See Technical Notes §TN-4.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_report_negative_paths.py` (new — generator-boundary cases)
- `tests/test_scouting_crawler.py` (modify — roster-fetch-failure crawler unit test)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE flagged roster-fetch as belonging one layer down (inside `ScoutingCrawler.scout_team`), hence the split to `tests/test_scouting_crawler.py`. The no-games test is the only one that pins a known bug — keep its intent explicit in comments.
