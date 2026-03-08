# E-073-02: Web Profile Live Endpoint Validation

## Epic
[E-073: API Documentation Validation Sweep](epic.md)

## Status
`TODO`

## Description
After this story is complete, every documented GameChanger API endpoint accessible via the web profile will have been called programmatically, and the results compared against the documented frontmatter. The script produces a per-endpoint validation report showing whether the actual HTTP status, response shape, and Accept header match what is documented. Endpoint doc files that pass validation get their `last_confirmed` and `profiles.web.status` updated.

## Context
We have 89 documented API endpoints (plus 1 web-routes reference file). Of these, most have `status: CONFIRMED` based on curl captures or proxy observations, but many have stale `last_confirmed` dates (2026-02-28 through 2026-03-07). This story programmatically confirms every reachable endpoint and updates the confirmation dates, turning point-in-time captures into systematic validation.

The `GameChangerClient` has working auth with programmatic token refresh. Most endpoints require path parameters (team_id, event_id, etc.) that must be resolved from upstream API calls.

## Acceptance Criteria
- [ ] **AC-1**: Given valid web profile credentials in `.env`, when the validation script runs, then it calls every documented authenticated endpoint that can be safely called (non-destructive, no special preconditions) and records the HTTP status code, response Content-Type, and response shape (array/object/string/empty).
- [ ] **AC-2**: Given the validation results, when compared against endpoint doc frontmatter, then the script reports per-endpoint: (a) status code match (expected 200 for CONFIRMED, actual), (b) response_shape match (frontmatter vs actual), (c) Accept header acceptance (no 406 response).
- [ ] **AC-3**: Given endpoints that require path parameters (team_id, event_id, game_stream_id, player_id, etc.), when the script resolves these, then it follows a dependency chain starting from `GET /me/teams` and progressively resolves required IDs from upstream responses.
- [ ] **AC-4**: Given endpoints that are destructive (PATCH /me/user), require special conditions (event-series, RSVP), or are known to return errors (the three HTTP 500 endpoints), when the script encounters them, then it skips them with a documented reason in the report.
- [ ] **AC-5**: Given all public endpoints (no-auth), when the script calls them, then it does so WITHOUT gc-token or gc-device-id headers and confirms they return 200.
- [ ] **AC-6**: Given successful validation of an endpoint, when the report is generated, then the report entry for that endpoint includes the recommended `last_confirmed` date (current date) and recommended `profiles.web.status` value (`confirmed`). Doc file updates are deferred to Story 05.
- [ ] **AC-7**: The script respects rate limiting: minimum 2 seconds between API calls, exponential backoff on errors, and stops if it receives 3 consecutive auth failures (credential expiry mid-run).
- [ ] **AC-8**: The script has tests for the report generation logic and parameter resolution chain (mocked HTTP -- no live API calls in tests).

## Technical Approach
Build a validation runner script that:
1. Loads all endpoint doc YAML frontmatter
2. Groups endpoints by parameter dependency (endpoints needing no params first, then those needing team_id, then event_id, etc.)
3. Resolves path parameters progressively from upstream responses
4. Calls each endpoint, records result
5. Compares against frontmatter expectations
6. Generates a structured report (JSON) with per-endpoint pass/fail and recommended doc updates

The dependency chain for parameter resolution: `GET /me/teams` -> team_ids -> `GET /teams/{id}/game-summaries` -> game_stream_ids, event_ids -> `GET /teams/{id}/players` -> player_ids -> etc.

Credential safety: use `GameChangerClient` exclusively. Never log token values. The script output references paths and status codes only.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-073-05 (documentation corrections use this story's report)

## Files to Create or Modify
- `scripts/validate_api_live.py` (new)
- `tests/test_validate_api_live.py` (new)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-073-04**: Confirmed web profile behavior (status codes, response shapes, headers) that mobile profile results can be compared against.
- **Produces for E-073-05**: Per-endpoint validation report listing all mismatches between docs and live API behavior.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Some endpoints return different data depending on team context (e.g., opponent-players returns 758 records for one team). The validation should confirm the response is non-empty and matches the expected shape, not validate specific record counts.
- The `Content-Type` header on responses is often `application/json` regardless of the vendor-typed Accept header sent. Validate that the Accept header is accepted (no 406), not that the response Content-Type matches it.
- The three HTTP 500 endpoints (org-level: opponent-players, possibly others) should be included in the skip list with documentation.
- Running this script requires live API access and valid credentials. It is NOT run in CI -- it is an operator tool.
