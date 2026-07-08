# E-073-05: Documentation Correction Sweep

## Epic
[E-073: API Documentation Validation Sweep](epic.md)

## Status
`TODO`

## Description
After this story is complete, all findings from the validation scripts (Stories 01-04) will be applied to the API documentation layer. Every endpoint doc file, global reference file, and header profile will reflect verified ground truth. The documentation will be internally consistent with no known inaccuracies.

## Context
Stories 01-04 produce validation reports identifying discrepancies between documentation and reality:
- Story 01: frontmatter errors and proxy coverage gaps
- Story 02: web profile live validation mismatches (status codes, response shapes, Accept headers, last_confirmed dates)
- Story 03: auth flow schema discrepancies
- Story 04: mobile profile header and behavior differences

This story applies all corrections. It is the final story in the epic and depends on all findings being available.

## Acceptance Criteria
- [ ] **AC-1**: Given the frontmatter validation report from Story 01, when corrections are applied, then all endpoint doc files pass frontmatter schema validation with zero errors.
- [ ] **AC-2**: Given the web live validation report from Story 02, when corrections are applied, then every web-verified endpoint has: `last_confirmed` set to the validation date, `profiles.web.status: confirmed`, and `response_shape` matching the actual API response.
- [ ] **AC-3**: Given the auth flow validation report from Story 03, when corrections are applied, then `docs/api/endpoints/post-auth.md` and `docs/api/auth.md` accurately reflect the programmatically confirmed request/response schemas for all five body types.
- [ ] **AC-4**: Given the mobile analysis report from Story 04 (if available), when corrections are applied, then `docs/api/headers.md` accurately documents mobile header differences and endpoint docs have `profiles.mobile.status` updated for all observed endpoints.
- [ ] **AC-5**: Given `src/http/headers.py`, when compared against validated header captures, then BROWSER_HEADERS and MOBILE_HEADERS match the ground truth from proxy captures (or issues are documented as follow-up items if header changes require coordinated code updates).
- [ ] **AC-6**: Given `docs/api/README.md`, when the index is reviewed, then all status values, auth requirements, and descriptions match the corrected endpoint files.
- [ ] **AC-7**: After all corrections are applied, the existing `scripts/validate_api_docs.py` tests (36 tests) still pass with no regressions.

## Technical Approach
This is primarily a documentation editing story. The implementing agent reads the validation reports from Stories 01-04, then systematically updates the affected files. The scope of changes depends entirely on what the validation scripts found -- it could be minor (a few stale dates) or significant (wrong response shapes, incorrect auth requirements).

Key files to review and potentially update:
- `docs/api/endpoints/*.md` -- frontmatter fields (status, last_confirmed, profiles, response_shape, accept, etc.)
- `docs/api/auth.md` -- auth flow schemas if Story 03 found discrepancies
- `docs/api/headers.md` -- header documentation if Story 04 found parity issues
- `docs/api/README.md` -- index table if any status or description changes affect it
- `src/http/headers.py` -- ONLY if header captures reveal the canonical dicts are wrong (coordinate with proxy-refresh-headers workflow)

The implementing agent should NOT blindly update -- it should read each validation report, understand each finding, and apply corrections that make the documentation accurate. If a finding is ambiguous (e.g., an endpoint returned a different shape than documented but the doc might be for a different parameter combination), document the ambiguity rather than making a potentially wrong correction.

## Dependencies
- **Blocked by**: E-073-01, E-073-02, E-073-03 (all validation reports must be available)
- **Soft dependency on**: E-073-04 (mobile findings, if available)
- **Blocks**: None

## Files to Create or Modify
- `docs/api/endpoints/*.md` (up to 90 files -- frontmatter corrections)
- `docs/api/auth.md` (if auth schema corrections needed)
- `docs/api/headers.md` (if header documentation corrections needed)
- `docs/api/README.md` (if index updates needed)
- `src/http/headers.py` (only if canonical header dicts need correction)

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- If Story 04 (mobile) was not executed or had no mobile data, the mobile-related ACs (AC-4, mobile portion of AC-5) should be noted as "not applicable -- no mobile data available" in the story completion notes, and the story can still be marked DONE.
- The `last_confirmed` date should only be updated for endpoints that were actually verified via live API call (Story 02). Endpoints that were only checked for frontmatter consistency (Story 01) should NOT get a new `last_confirmed` date.
- If header changes in `src/http/headers.py` are needed, the agent should verify the existing `proxy-refresh-headers` workflow can handle it, or flag it as a separate code change that needs testing.
- The README.md completeness check section at the bottom should be updated if the endpoint count changes.
