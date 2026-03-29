# E-186-02: Wire gc_uuid Resolution into Report Generator

## Epic
[E-186: Fix Spray Charts for Standalone Reports](epic.md)

## Status
`DONE`

## Description
After this story is complete, the report generator resolves a tracked team's `gc_uuid` via `POST /search` + `public_id` filtering before invoking the spray chart pipeline. The resolved gc_uuid is persisted on the team row and passed to the spray crawler. Reports for teams whose gc_uuid can be resolved now include spray charts.

## Context
The report generator (`src/reports/generator.py`) already fetches the team name from the public API in Step 1b (lines 477-496). It then calls `_crawl_and_load_spray()` at line 589, which delegates to `ScoutingSprayChartCrawler.crawl_team()`. Currently, if the team row has `gc_uuid=NULL`, the spray crawler (after E-186-01) will skip with an empty result. This story adds the resolution step between fetching the team name and invoking the spray pipeline: search by name, filter by `public_id`, store the result, and pass it through to the crawler. See TN-2 for the resolution protocol and `.project/research/epic-prompt-fix-spray-asymmetry.md` for the verified API behavior.

## Acceptance Criteria
- [ ] **AC-1**: When `generate_report()` is called for a team with `gc_uuid=NULL`, the generator executes `POST /search` with the team name and filters results by `public_id` exact match per TN-2. A matching `result.id` is returned as the resolved gc_uuid.
- [ ] **AC-2**: When `POST /search` returns no hit matching the team's `public_id`, the report renders successfully without spray charts. No error is raised; an INFO log is emitted.
- [ ] **AC-3**: When the team row already has a non-NULL `gc_uuid`, the resolution step is skipped entirely (no search API call).
- [ ] **AC-4**: The `_crawl_and_load_spray` function accepts and passes through the resolved `gc_uuid` to `ScoutingSprayChartCrawler.crawl_team()` per TN-7.
- [ ] **AC-5**: The gc_uuid storage uses a conditional update (`UPDATE teams SET gc_uuid = ? WHERE id = ? AND gc_uuid IS NULL`) to never overwrite an existing gc_uuid.
- [ ] **AC-6**: `POST /search` failures (network error, auth error, unexpected response shape) are caught and logged as warnings. The report continues without spray charts. `CredentialExpiredError` propagates.
- [ ] **AC-7**: Tests verify: (a) successful resolution stores gc_uuid and passes it to spray crawler, (b) no-match case renders report without spray charts, (c) existing gc_uuid skips search, (d) search failure is non-fatal.
- [ ] **AC-8**: `python -m pytest tests/test_report_generator.py tests/test_scouting_spray_crawler.py -v` passes with zero failures.

## Technical Approach
Add a resolution function that uses the authenticated `GameChangerClient` to call `POST /search`. The function takes the team name and `public_id`, returns a `gc_uuid` or None. Wire this into `generate_report()` between Step 1b and Step 4b. Update `_crawl_and_load_spray` to accept and forward the gc_uuid. Reference `src/gamechanger/resolvers/gc_uuid_resolver.py` for the `_SEARCH_CONTENT_TYPE` constant and search call pattern, but implement the resolution as a focused function rather than modifying the existing three-tier cascade.

## Dependencies
- **Blocked by**: E-186-01 (clean crawl_team that skips on gc_uuid=None)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` (add resolution function, wire into generate_report, update _crawl_and_load_spray signature)
- `tests/test_report_generator.py` (add tests for resolution success, no-match, existing gc_uuid, search failure)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `POST /search` Content-Type is `application/vnd.gc.com.post_search+json; version=0.0.0` -- this is already defined as `_SEARCH_CONTENT_TYPE` in `src/gamechanger/resolvers/gc_uuid_resolver.py`.
- The search response shape: `{"hits": [{"result": {"id": "<gc_uuid>", "public_id": "<public_id>", ...}}, ...]}`.
- The resolution costs 1 authenticated API call per report generation for teams without gc_uuid. This is acceptable.
- The `GameChangerClient` instance already exists in `generate_report()` at line 532.
