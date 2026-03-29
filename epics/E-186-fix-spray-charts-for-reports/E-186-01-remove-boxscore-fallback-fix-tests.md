# E-186-01: Remove Boxscore-UUID Fallback and Fix Test Failures

## Epic
[E-186: Fix Spray Charts for Standalone Reports](epic.md)

## Status
`TODO`

## Description
After this story is complete, the scouting spray crawler no longer contains the harmful boxscore-UUID fallback that fetches spray data for opponents instead of the scouted team. When a team has no `gc_uuid`, the crawler logs an INFO message and returns an empty result. Additionally, the two pre-existing E-185 test failures in `tests/test_report_renderer.py` are fixed.

## Context
The boxscore-UUID fallback (`_build_boxscore_uuid_map` and `_crawl_team_season_with_uuid_map`) was added in E-176-01 based on the false premise that the spray endpoint returns both teams' data regardless of which UUID is used. Live API verification (2026-03-29) proved this is wrong -- calling with an opponent's UUID returns only the opponent's spray data, not the scouted team's. The fallback is actively harmful: it fetched 2,021 spray events for Lincoln Sox 12U that were all attributed to opponents, with zero data for the actual scouted team. See `.project/research/spray-endpoint-asymmetry.md` for full evidence.

The two test failures are an E-185 regression where `patch("src.charts.spray.render_spray_chart")` targets a module not yet imported at patch time.

## Acceptance Criteria
- [ ] **AC-1**: The methods `_build_boxscore_uuid_map` and `_crawl_team_season_with_uuid_map` no longer exist in `src/gamechanger/crawlers/scouting_spray.py`.
- [ ] **AC-2**: `crawl_team()` with `gc_uuid=None` (and no gc_uuid in the database) logs an INFO-level message containing the `public_id` and returns a `CrawlResult` with all counters at zero. It does NOT attempt any API calls.
- [ ] **AC-3**: The module docstring of `src/gamechanger/crawlers/scouting_spray.py` no longer contains the false claim about the boxscore-UUID fallback or the "both teams regardless of which UUID" statement. The docstring accurately describes the asymmetric endpoint behavior per TN-1.
- [ ] **AC-4**: `tests/test_report_renderer.py::TestSprayChartSection::test_spray_charts_as_base64_data_uris` passes. Fix per TN-4.
- [ ] **AC-5**: `tests/test_report_renderer.py::TestSprayChartSection::test_spray_chart_render_failure_is_non_fatal` passes. Fix per TN-4.
- [ ] **AC-6**: All existing tests in `tests/test_scouting_spray_crawler.py` that exercise the fallback path are updated or removed to reflect the new behavior (gc_uuid=None -> skip with empty result).
- [ ] **AC-7**: `python -m pytest tests/test_scouting_spray_crawler.py tests/test_report_renderer.py -v` passes with zero failures.
- [ ] **AC-8**: `crawl_team(public_id, gc_uuid="some-uuid")` uses the provided `gc_uuid` for API calls without performing a database lookup. This existing behavior (lines 203-204, 225-231) is preserved after the fallback removal.

## Technical Approach
Remove the three code elements described in TN-3. Update the `crawl_team` method so the `gc_uuid is None` branch returns an empty `CrawlResult` with an INFO log. Update the module docstring to describe the asymmetric behavior. Fix the two test failures per TN-4. Update or remove existing tests that assert on the fallback behavior. Reference `.project/research/spray-endpoint-asymmetry.md` for the correct endpoint behavior description.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-186-02

## Files to Create or Modify
- `src/gamechanger/crawlers/scouting_spray.py` (remove fallback methods, update crawl_team, update docstring)
- `tests/test_scouting_spray_crawler.py` (update/remove fallback tests, add gc_uuid=None skip test)
- `tests/test_report_renderer.py` (fix two deferred-import patch failures per TN-4)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-186-02**: A clean `crawl_team` method that accepts an optional `gc_uuid` parameter and uses it when provided. E-186-02 will wire the resolved gc_uuid from the report generator into this parameter.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `_crawl_team_season` method (lines 265-358) is NOT removed -- it is the correct path used when gc_uuid IS available.
- The `_lookup_gc_uuid` method (lines 529-547) is NOT removed -- it is still used for database lookup.
- The `crawl_team` method already accepts an optional `gc_uuid` parameter (line 178) -- this parameter stays.
- The test file has 7 fallback-specific tests (lines 597-744) that will need to be removed or replaced: `test_fallback_path_crawls_spray_via_boxscore_uuids`, `test_fallback_no_boxscores_returns_empty`, `test_fallback_mixed_some_games_have_boxscores`, `test_fallback_idempotency_skips_existing_spray_file`, `test_fallback_credential_expired_propagates`, `test_fallback_api_error_counted_and_continues`, and `test_boxscore_uuid_regex_ignores_slug_keys`.
