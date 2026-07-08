# E-073-01: API Doc Frontmatter Validation Script

## Epic
[E-073: API Documentation Validation Sweep](epic.md)

## Status
`TODO`

## Description
After this story is complete, the project will have a comprehensive validation script that checks all 90 endpoint doc files for frontmatter consistency and cross-references documented endpoints against proxy session capture data. The script produces a structured report identifying frontmatter errors, undocumented endpoints seen in proxy traffic, and documented endpoints never seen in any proxy session.

## Context
There is an existing `scripts/validate_api_docs.py` (36 tests) from E-062 that validates structural correctness of the endpoint doc files. This story extends the validation to include proxy capture cross-referencing -- comparing what the docs say exists against what was actually observed in mitmproxy traffic. The two validation dimensions are: (1) is each doc file internally consistent and complete? (2) does the set of documented endpoints match observed reality?

## Acceptance Criteria
- [ ] **AC-1**: Given the 90 endpoint files in `docs/api/endpoints/`, when the script runs, then it validates every file's YAML frontmatter against the schema defined in `/.claude/rules/api-docs.md` and reports any missing required fields, invalid status values, or malformed Accept headers.
- [ ] **AC-2**: Given proxy session data exists in `proxy/data/sessions/` with endpoint-log.jsonl files, when the script runs with a `--proxy` flag (or `--session <id>` / `--all`), then it cross-references documented endpoint paths against proxy-observed paths and reports: (a) paths seen in proxy traffic with no matching doc file, (b) doc files with status CONFIRMED but path never seen in any proxy traffic.
- [ ] **AC-3**: Given the script finds validation issues, when it completes, then it outputs a structured report (JSON to stdout or a file, with a human-readable summary) listing all issues categorized by type (frontmatter error, undocumented endpoint, unobserved endpoint).
- [ ] **AC-4**: Given the script runs with no proxy data available, when the `--proxy` flag is omitted, then it performs frontmatter-only validation without errors.
- [ ] **AC-5**: The script has tests covering: frontmatter parsing, status value validation, proxy cross-referencing with mock JSONL data, and edge cases (empty JSONL, endpoint with path parameters vs. concrete proxy paths).
- [ ] **AC-6**: The path-matching logic handles parameterized paths correctly: a doc file for `/teams/{team_id}/players` matches proxy entries like `/teams/abc-123/players`.

## Technical Approach
The existing `scripts/validate_api_docs.py` validates doc structure. This story either extends that script or creates a companion (e.g., `scripts/validate_api_coverage.py`). The key challenge is path-matching between parameterized doc paths (e.g., `/teams/{team_id}/schedule`) and concrete proxy paths (e.g., `/teams/550e8400.../schedule`). The YAML frontmatter schema is fully specified in `/.claude/rules/api-docs.md`. Proxy endpoint-log.jsonl entries have fields defined in `/workspaces/baseball-crawl/proxy/addons/endpoint_logger.py` (method, path, status_code, source, etc.).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-073-05 (documentation corrections use this script's output)

## Files to Create or Modify
- `scripts/validate_api_coverage.py` (new -- or extend `scripts/validate_api_docs.py`)
- `tests/test_validate_api_coverage.py` (new)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-073-05**: Validation report output (JSON or text) listing all frontmatter errors and proxy coverage gaps. E-073-05 uses this to know which doc files need correction.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The endpoint-log.jsonl `path` field contains the concrete path (e.g., `/teams/550e8400-e29b-41d4-a716-446655440000/players`), NOT the parameterized template. Path matching must extract the template pattern from doc frontmatter and match against concrete paths.
- Some endpoints use UUID path segments, others use public_id slugs (e.g., `lincoln-standing-bear-hs-varsity-baseball-spring-2026`). The matcher must handle both.
- The `web-routes-not-api.md` file documents paths that are NOT API endpoints. These should be excluded from the "undocumented endpoint" report.
